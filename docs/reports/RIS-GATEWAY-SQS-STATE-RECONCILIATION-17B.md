# RIS-GATEWAY-SQS-STATE-RECONCILIATION-17B — Gateway & SQS State Reconciliation

STATUS: **YELLOW** — alle 5 Imports erfolgreich, 4 Routen no-op; ESM hat einen **eindeutig erklärbaren** Rest-Change (Tags), kein Apply

- Datum: 2026-10-04 UTC
- Branch/HEAD: `main`, `acceabb`
- Account/Region/Workspace: `240571105849` (`user/Mayaws`) / `eu-central-1` / `mays-ris`
- Backend: S3 (`key = terraform.tfstate`, `encrypt = true`, Lock `mays-ris-tf-lock`) — remote, **nicht committet**
- **AWS-Mutation: NONE.** Terraform-State-Mutation: 5 Imports.

## 1. Context

| Prüfung | Ergebnis |
|---|---|
| Branch / HEAD | `main` / `acceabb` |
| `git status --short` | tracked clean (nur 9 vorbestehende untracked) |
| `AWS_PROFILE` | `mayaws` (keine Default-Credentials) |
| Account | `240571105849` = `arn:aws:iam::240571105849:user/Mayaws` ✔ |
| Region | `eu-central-1` ✔ |
| Workspace | `mays-ris` ✔ |
| Backend | S3 + DynamoDB-Lock, remote |

## 2. Live Route Inventory (Schritt 2)

API `mays-ris-dev-api` = `aboqolpm0f`. Die vier P17A-Routen anhand ihrer tatsächlichen Route-IDs identifiziert:

| HTTP-Methode | Path | Route ID | Authorizer | Target |
|---|---|---|---|---|
| GET | `/me` | `nzmp4se` | `9ghezn` (JWT) | `integrations/ewy9u57` |
| GET | `/me/profile` | `ezrgj81` | `9ghezn` (JWT) | `integrations/ewy9u57` |
| POST | `/me/profile` | `r5atqmf` | `9ghezn` (JWT) | `integrations/ewy9u57` |
| PUT | `/me/profile` | `sysdyq6` | `9ghezn` (JWT) | `integrations/ewy9u57` |

Gegenprobe vor dem Import: `GET /platform` und `GET /agents` sind live **nicht** vorhanden — damit ist ausgeschlossen, dass sie versehentlich importiert werden.

## 3. State Check vor Import (Schritt 3)

Alle fünf Adressen geprüft, **keine** war bereits im State:

- `module.api.aws_apigatewayv2_route.me` / `.profile` / `.profile_create` / `.profile_update` → nicht im State
- `module.lambda.aws_lambda_event_source_mapping.sqs_mapping` → nicht im State

## 4. Route Imports (Schritt 4)

Der erste Versuch mit der bloßen Route-ID schlug fehl (`wrong format of import ID, use: 'api-id/route-id'`) — ohne Nebenwirkung. Korrektes Format `api-id/route-id`, danach alle vier `Import successful!`:

| Terraform Resource Address | Import-ID | Ergebnis |
|---|---|---|
| `module.api.aws_apigatewayv2_route.me` | `aboqolpm0f/nzmp4se` | erfolgreich |
| `module.api.aws_apigatewayv2_route.profile` | `aboqolpm0f/ezrgj81` | erfolgreich |
| `module.api.aws_apigatewayv2_route.profile_create` | `aboqolpm0f/r5atqmf` | erfolgreich |
| `module.api.aws_apigatewayv2_route.profile_update` | `aboqolpm0f/sysdyq6` | erfolgreich |

Nicht importiert (wie gefordert): `/platform`, `/agents` (nicht live), `/health`, `/work`, `/api/agents/*`.

## 5. SQS Event Source Mapping Import (Schritt 5)

Vollständige UUID aus dem Live-Readback, nicht der Prefix: `7cc946b9-1c32-4f84-88b4-6f0918e486e7`.

`terraform import module.lambda.aws_lambda_event_source_mapping.sqs_mapping 7cc946b9-1c32-4f84-88b4-6f0918e486e7` → `Import successful!`

State-Readback: `batch_size 5`, `event_source_arn` → `mays-ris-dev-work-queue`, `function_arn` → `mays-ris-dev-agent`, `state Enabled`, `state_transition_reason USER_INITIATED`, `maximum_batching_window_in_seconds 0`, `function_response_types []`, `scaling_config` Default, keine Filter-Criteria. Keine Änderung am Mapping.

## 6. State/Live Parity

**4 Routen: GREEN.** `route_key`, `authorization_type`, `authorizer_id`, `target` und `id` stimmen für alle vier exakt mit Live überein (20/20 Einzelvergleiche OK).

**ESM: GREEN.** UUID, `event_source_arn`, `function_arn`, `batch_size`, `state`, `state_transition_reason`, `maximum_batching_window`, `function_response_types` identisch; `scaling_config` und Filter-Criteria in beiden Default.

## 7. Fresh Plan (Schritt 6)

`validate` Success, `fmt -check` clean (`modules/api/main.tf`, `modules/lambda/main.tf`).

**`Plan: 2 to add, 1 to change, 0 to destroy`** — sowie 0 Replace-Marker.

### A — Importiert / reconcilt (5)

| Adresse | Plan | Bewertung |
|---|---|---|
| `…route.me` | `no-op` | 🟢 |
| `…route.profile` | `no-op` | 🟢 |
| `…route.profile_create` | `no-op` | 🟢 |
| `…route.profile_update` | `no-op` | 🟢 |
| `…sqs_mapping` | **`update`** | 🟡 siehe unten |

### Der ESM-Rest-Change — eindeutig erklärt

Einziges geändertes Attribut:

```
tags_all: {} -> {'Environment': 'dev', 'Maker': 'mays-ris', 'Project': 'mays-ris'}
replace_paths: KEINE (kein Replace)
```

Ursache, dreifach belegt:

1. `terraform/main.tf:30-38` definiert `default_tags` mit `Project`, `Maker`, `Environment`.
2. Live hat das Mapping **keine** Tags: `aws lambda list-tags` auf dem Mapping-ARN liefert eine leere Liste.
3. Alle übrigen Terraform-verwalteten Ressourcen tragen die drei Tags (entitlements-Tabelle, work-queue, agent-Lambda) — die Queue live per `list-queue-tags` verifiziert.

Das Mapping wurde am `2026-10-01` per `USER_INITIATED` außerhalb von Terraform angelegt und hat die Provider-Default-Tags nie erhalten. Der Import hat diesen Zustand sichtbar gemacht. Kein Code-Drift, kein Runtime-Defekt, kein Replace — der Import hat die Lücke aufgedeckt, nicht verursacht.

**Kein Apply durchgeführt.** Das Tagging wäre eine AWS-Mutation und ist in diesem Gate nicht erlaubt.

### B — Aktueller Vertrag, live absent (Schritt 7)

| Adresse | Route | Plan | Vertrag |
|---|---|---|---|
| `module.api.aws_apigatewayv2_route.platform` | `GET /platform` | `create` | `modules/api/main.tf:49-55`, JWT, bestehende Integration |
| `module.api.aws_apigatewayv2_route.agents` | `GET /agents` | `create` | `modules/api/main.tf:89-96`, JWT, bestehende Integration |

Beide sind CREATE-Kandidaten, **nicht** Teil des State-Reconcile. Handler vorhanden (`_handle_platform`, `_handle_agents`), dokumentiert in `API-STANDARD.md:12`, getestet in `test_platform_handlers.py`. Nicht angewendet.

### C — Vorbestehender Fremd-Drift

`module.iam.aws_iam_role_policy.lambda_policy` → `create`. Betrifft eine **andere** Rolle (`lambda_role`, Logs+S3), ist vorbestehend und wurde nicht angefasst.

## 8. P17 Readiness

**GREEN für den State-Drift.** Die vier Live-Routen sind reconcilt; der Apply-Blocker aus P17A (CreateRoute-Kollision auf belegte Route-Keys) ist damit **auflöbar**. Beide ESM- und Routen-Deltas sind erklärt; kein unerklärbarer Change, kein Replace, kein Destroy.

Der verbleibende ESM-Tag-Change ist **kein** P17-Blocker: der Worker-Pfad (`Enabled`, Batch 5, korrekte Quelle/Ziel) ist unverändert funktionsfähig.

## 9. AWS Mutation Tracking (Schritt 10)

| Kategorie | Umfang |
|---|---|
| **AWS resource mutation** | **NONE** — kein Create/Update/Delete/Tagging |
| **Terraform state mutation** | **5 Imports** (4 Routen + 1 ESM) |

Terraform Import ist state-only und wird ausdrücklich nicht als AWS-Mutation gezählt.

## 10. Tests (Schritt 11)

Kein produktiver Code geändert, daher keine Test-Suite erzwungen (die bekannten credential-abhängigen Fehler aus P16/P17A würden nur Rauschen erzeugen):

- `terraform validate` → Success
- `terraform fmt -check` (beide berührten Module) → clean
- Fresh Plan + 25 State/Live-Einzelvergleiche → alle OK
- Keine Teständerungen in diesem Gate

## 11. Offene Punkte

1. **ESM-Tags:** `default_tags` fehlen live am Mapping. Ein Apply würde sie setzen (in-place, kein Replace). Bewusst nicht ausgeführt — separates Mini-Gate oder in das Apply-Gate für `platform`/`agents` integrieren.
2. **`GET /platform` und `GET /agents`** bleiben CREATE-Kandidaten. Erst nach einem Apply sind sie erreichbar; das ist der einzige verbleibende fachliche Gateway-Check.
3. **`module.iam.lambda_policy`** bleibt Fremd-Drift auf einer anderen Rolle.
4. `GET /health` weiterhin live ohne Handler-Pfad (aus P16/P17A bekannt).
5. `/work` und `/api/agents/*` weiterhin ohne Gateway-Route — kein Teil dieses Gates.
