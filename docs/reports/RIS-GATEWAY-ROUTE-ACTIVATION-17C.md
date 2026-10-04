# RIS-GATEWAY-ROUTE-ACTIVATION-17C — Gateway Route Activation

STATUS: GREEN (2 Routen live; 0 add / 0 change / 0 destroy im Fresh Plan für P17C)

- Datum: 2026-10-04 UTC
- Branch/HEAD: `main`, `b48998c`
- Account/Region/Workspace: `240571105849` (`user/Mayaws`) / `eu-central-1` / `mays-ris`
- **AWS-Mutation: 2× `CreateRoute`** auf `aboqolpm0f`. Sonst nichts.

## 1. Context (Schritt 1)

| Prüfung | Ergebnis |
|---|---|
| Branch / HEAD | `main` / `b48998c` |
| `git status --short` | tracked clean (nur 9 vorbestehende untracked) |
| `AWS_PROFILE` | `mayaws` (keine Default-Credentials) |
| Account | `240571105849` = `arn:aws:iam::240571105849:user/Mayaws` ✔ |
| Region | `eu-central-1` ✔ |
| Workspace | `mays-ris` ✔ |
| Backend | S3 `terraform.tfstate`, `encrypt = true`, Lock `mays-ris-tf-lock` |

## 2. Live Pre-Check (Schritt 2)

API `mays-ris-dev-api` = `aboqolpm0f`, 20 Routen vor Apply.

| Route | Erwartung | Befund |
|---|---|---|
| `GET /platform` | existiert nicht | **existiert nicht** ✔ CREATE zulässig |
| `GET /agents` | existiert nicht | **existiert nicht** ✔ CREATE zulässig |

Keine Kollision. Der P17A-Blocker (CreateRoute auf belegte Route-Keys) war durch das P17B-Reconcile bereits aufgelöst.

## 3. Terraform Plan (Schritt 3)

Gezielter Plan auf die zwei Adressen, mit `-var=identity_email_verification_enabled=true` (verhindert das bekannte Cognito-Default-Artefakt).

**`Plan: 2 to add, 0 to change, 0 to destroy`** — 0 Replace-/Destroy-Marker. Keine andere Ressource non-noop.

## 4. Route-Details vor Apply (Schritt 4)

| Route | route_key | Auth | Authorizer | Target | API |
|---|---|---|---|---|---|
| `platform` | `GET /platform` | JWT | `9ghezn` | `integrations/ewy9u57` | `aboqolpm0f` |
| `agents` | `GET /agents` | JWT | `9ghezn` | `integrations/ewy9u57` | `aboqolpm0f` |

Musterabgleich mit der in P17B importierten Route `GET /me`: `authorization_type = JWT`, `authorizer_id = 9ghezn`, `target = integrations/ewy9u57` — **identisch**.

Wiederverwendet, nichts neu erstellt: Authorizer `9ghezn` (`mays-ris-dev-jwt`, Typ JWT) und Integration `ewy9u57` (AWS_PROXY → `mays-ris-dev-agent`). Keine neue Lambda, kein neuer Authorizer, keine neue Integration.

## 5. Apply-Freigabe (Schritt 5)

Plan kompakt vorgelegt und **explizite Freigabe** erhalten.

| Bereich | Erwartung | Plan |
|---|---|---|
| `GET /platform` | 1 CREATE | ✔ |
| `GET /agents` | 1 CREATE | ✔ |
| Add / Change / Destroy | 2 / 0 / 0 | ✔ |
| Replacement | 0 | ✔ |
| Lambda / IAM / Cognito / DynamoDB / SQS-ESM | 0 | ✔ |

## 6. Gezielter Apply (Schritt 6)

Identität vor Apply erneut verifiziert (Account `240571105849`, Workspace `mays-ris`).

```
terraform apply -input=false -auto-approve /tmp/p17c.tfplan
  -target=module.api.aws_apigatewayv2_route.platform
  -target=module.api.aws_apigatewayv2_route.agents
→ Apply complete! Resources: 2 added, 0 changed, 0 destroyed.
```

## 7. Live Readback (Schritt 7)

| Route | Route ID | Auth | Authorizer | Target |
|---|---|---|---|---|
| `GET /platform` | **`wozrsmu`** | JWT | `9ghezn` | `integrations/ewy9u57` |
| `GET /agents` | **`9poa0wt`** | JWT | `9ghezn` | `integrations/ewy9u57` |

Routen gesamt: 20 → **22** (+2, exakt die zweiCreates).

Unverändertheitsnachweise:

- **Alle 20 Bestandsrouten unverändert** — `RouteId`, `AuthorizationType`, `AuthorizerId` und `Target` jeder einzelnen Route per Vorher/Nachher-Vergleich geprüft, 0 Abweichungen.
- **4 P17B-importierte Routen unverändert:** `GET /me` `nzmp4se`, `GET /me/profile` `ezrgj81`, `POST /me/profile` `r5atqmf`, `PUT /me/profile` `sysdyq6` — alle JWT/`9ghezn`/`ewy9u57`.
- **8 P13/P16-Routen unverändert:** `GET /v1/introspection` + 7 Credential-Routen, alle JWT/`9ghezn`.
- **Keine** `$default`-, `ANY`- oder Greedy-Route.
- **ESM nur gelesen, unverändert:** UUID `7cc946b9-1c32-4f84-88b4-6f0918e486e7`, `Enabled`, `USER_INITIATED`, Batch `5`, `LastModified 2026-10-01T18:04:22+02:00` — identisch zum P17B-Referenzwert. Tags weiterhin leer.
- **Lambda unverändert:** `CodeSha256 yaKXvStx/o/M/XHUiA01d18cFDoi35PMcAibequbZHc=`, `LastModified 2026-10-04T11:44:08Z` — P19-Referenzwert.
- **IAM unverändert:** 8 Role-Policies an `mays-ris-dev-agent` (P19-Referenz: 8).

## 8. Fresh Plan (Schritt 8)

`validate` Success, `fmt -check modules/api/main.tf` clean.

**P17C-Ressourcen:**

| Adresse | Aktion |
|---|---|
| `module.api.aws_apigatewayv2_route.platform` | `no-op` 🟢 |
| `module.api.aws_apigatewayv2_route.agents` | `no-op` 🟢 |

→ **0 add / 0 change / 0 destroy** für P17C.

**Rest, ausdrücklich außerhalb P17C:**

| Ressource | Aktion | Klassifizierung |
|---|---|---|
| `module.lambda.aws_lambda_event_source_mapping.sqs_mapping` | `update` | 🟡 ESM-Tags, bewusst unangetastet |
| `module.iam.aws_iam_role_policy.lambda_policy` | `create` | 🟡 Fremd-Drift, bewusst unangetastet |

Der ESM-Change ist unverändert **ausschließlich** `tags_all: {} -> {Environment: dev, Maker: mays-ris, Project: mays-ris}`, `replace_paths: KEINE`. Ursache unverändert: das Mapping wurde am 2026-10-01 per `USER_INITIATED` außerhalb Terraform angelegt und trägt die Provider-`default_tags` nie.

## 9. Tests (Schritt 9)

Kein produktiver Code geändert (`git status` tracked clean), daher kein Zwang zur vollen Suite:

| Lauf | Ergebnis |
|---|---|
| `terraform validate` | Success |
| `terraform fmt -check modules/api/main.tf` | clean |
| Gateway-Vertrag P13/P16 (`test_introspection_capability`, `test_credential_management_http`, `test_api_profiles`, `test_credential_management`) | **198 passed** |
| `test_identity_registration.py` | **11 passed** |
| Gesamtsuite (ohne `AWS_PROFILE`) | 15 failed / 709 passed / 8 skipped / 231 warnings / 1 error — MD5 `d0efae4dba6d8af196593535a46c3e57`, **identisch zur Baseline** seit P18 |

Bekannte, nicht durch P17C verursachte Testprobleme:

- `tests/test_platform_handlers.py` scheitert beim **Collect** an `ModuleNotFoundError: No module named 'handler'` (Import ohne `PYTHONPATH=lambda`). Das ist der 1 Error der Baseline.
- Mit `PYTHONPATH=lambda` gesammelt: 12 failed / 18 passed. Fehler-MD5 `5cbefee97f943c1e0853c56b6e061234`. Da P17C keinen Code geändert hat, sind diese Fehler präexistend; sie stehen **nicht** in der Baseline-MD5, weil die Suite sie ohne `PYTHONPATH` gar nicht sammelt.
- Keine Testdatei geändert.

## 10. P17 Readiness

**GREEN.**

- Alle Gateway-Routen des aktuellen Vertrags sind jetzt live: `health`, `platform`, `me`, `me/profile` (GET/POST/PUT), `me/documents` (3), `agents`, `v1/introspection`, 7× `credentials`, 4× `orders` = **22**.
- Beide P17-Blocker aus `RIS-CREDENTIAL-MANAGEMENT-LIVE-DEPLOYMENT-17.md` bleiben aufgelöst (B3+P19 bzw. P18/P18B+P19).
- Der Credential-Lifecycle braucht ausschließlich die 7 Credential-Routen, Handler, Tabellen, IAM und Env 3/3 — alles vorhanden.
- Der verbleibende ESM-Tag-Change und `module.iam.lambda_policy` sind kein P17-Blocker.

## 11. Offene Punkte

1. **ESM-Tags** (`tags_all`) weiterhin offen — Mapping ohne Provider-`default_tags`. In-place behebbar, bewusst nicht angefasst.
2. **`module.iam.lambda_policy`** weiterhin Fremd-Drift auf der Rolle `lambda_role` (andere Rolle als der Agent).
3. **`GET /health`** live, aber der Handler enthält keinen `/health`-Pfad (aus P16/P17A bekannt) — die Route antwortet 404.
4. **`/work` und `/api/agents/*`** weiterhin ohne Gateway-Route; der SQS-Produktionsweg ist nicht HTTP-erreichbar.
5. `tests/test_platform_handlers.py` bleibt ohne `PYTHONPATH=lambda` nicht sammelbar (12 Fehler bei korrigiertem Importpfad) — Testinfrastruktur-Thema, nicht Gateway.
6. Kein funktionaler Auth-Smoke gegen die beiden neuen Routen durchgeführt — P17C ist ein reines Routing-Gate; Verifikation erfolgte über Gateway-Konfiguration, nicht über Request-Authentisierung.
