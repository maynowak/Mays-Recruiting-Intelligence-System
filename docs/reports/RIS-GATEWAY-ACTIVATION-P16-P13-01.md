# RIS-GATEWAY-ACTIVATION-P16-P13-01 — Gateway Activation

STATUS: GREEN (8 Routen live, JWT + bestehende Proxy-Integration, 0 add / 0 change / 0 destroy im Fresh Plan)

- Datum: 2026-10-04 UTC
- Branch/HEAD: `main`, `9443f21`
- Account/Region/Workspace: `240571105849` (`user/Mayaws`) / `eu-central-1` / `mays-ris`
- API: `mays-ris-dev-api` (`aboqolpm0f`), Stage `$default` (AutoDeploy)
- Basis: P19 GREEN (Lambda `yaKXvStx…`, Env 3/3)

## 1. Context (Schritt 1)

| Prüfung | Ergebnis |
|---|---|
| Branch / HEAD | `main` / `9443f21` |
| `git status` | tracked clean (nur 9 vorbestehende untracked) |
| `AWS_PROFILE` | `mayaws` für alle AWS-/Terraform-Kommandos |
| Account | `240571105849` = `arn:aws:iam::240571105849:user/Mayaws` ✔ |
| Region | `eu-central-1` ✔ |
| Workspace | `mays-ris` ✔ |
| API | `mays-ris-dev-api` / `aboqolpm0f`, HTTP, Endpoint `https://aboqolpm0f.execute-api.eu-central-1.amazonaws.com` |
| JWT Authorizer | `mays-ris-dev-jwt` / `9ghezn`, Typ JWT, IdentitySource `$request.header.Authorization` — **bestehend, wiederverwendet** |
| Integrationen | `ewy9u57` = AWS_PROXY → `mays-ris-dev-agent` (bestehend); `8yo7f44` → `mays-ris-dev-orders-reader` (bestehend) — **keine neue Integration** |

## 2. Ausgangszustand (Schritt 2, nur gelesen)

12 Routen live, alle mit `integrations/ewy9u57` außer den drei `/orders`-Routen (`8yo7f44`). Authorizer-Zuordnung: `/health` = NONE, alle übrigen JWT/`9ghezn`.

**P13 und P16 fehlten vollständig.** Weder `GET /v1/introspection` noch eine `/v1/apiprofiles/{apiProfileId}/credentials`-Route war vorhanden. Keine Teilaktivierung, kein `$default`, kein `ANY`, keine Greedy-Route.

## 3. Plan (Schritt 3)

`fmt` (`modules/api/main.tf`) clean, `validate` Success.

Erster gezielter Plan über die 8 Routen: **`8 to add, 1 to change, 0 to destroy`** — die eine change war `module.cognito…user_pool.users` (`auto_verified_attributes: ["email"] → []`).

**Ursachenanalyse:** `terraform/variables.tf:38-42` definiert `identity_email_verification_enabled` mit `default = false`; `terraform/modules/cognito/main.tf:27` leitet daraus `auto_verified_attributes` ab. Es existiert **keine `.tfvars`-Datei**, der Pool wurde also mit `true` provisioniert. Live ist `AutoVerifiedAttributes: ["email"]`. Der Plan wollte diese bewusst gesetzte Konfiguration zurücksetzen — ein Variablen-Artefakt des Defaults, kein P13/P16-Thema und laut Auftrag eine **verbotene** Cognito-Änderung.

Mit `-var=identity_email_verification_enabled=true` wird der Pool zum no-op: **`Plan: 8 to add, 0 to change, 0 to destroy`**, Cognito `no-op`, Lambda `no-op`, alle IAM-/SQS-/DynamoDB-Ressourcen `no-op`. Kein Replacement, kein Destroy.

## 4. Freigabe (Schritt 4)

| Bereich | Erwartung | Plan |
|---|---|---|
| P13 Introspection | 1 Route | ✔ `GET /v1/introspection` |
| P16 Credential Management | 7 Routes | ✔ 7 Credential-Routen |
| Authorizer | bestehender JWT | ✔ alle `JWT`/`9ghezn` |
| Integration | bestehende Lambda-Integration | ✔ alle `integrations/ewy9u57` |
| Lambda | 0 Änderungen | ✔ no-op |
| IAM | 0 Änderungen | ✔ no-op |
| Cognito | 0 Änderungen | ✔ no-op (mit `-var=true`) |
| Destroy | 0 | ✔ |
| Replacement | 0 | ✔ |

Explizite Freigabe erhalten, einschließlich der `-var`-Variante.

## 5. Mutation (Schritt 5)

Vor Apply erneut verifiziert: Account `240571105849`, Region `eu-central-1`, Workspace `mays-ris`.

```
terraform apply -input=false -auto-approve /tmp/gate1613b.tfplan
  -target=module.api.aws_apigatewayv2_route.{introspection,credentials_*}
  -var=identity_email_verification_enabled=true
→ Apply complete! Resources: 8 added, 0 changed, 0 destroyed.
```

Acht `CreateRoute`-Aufrufe, sonst nichts.

## 6. Live Readback (Schritt 6)

Gesamt 20 Routen = 12 vorbestehend + 8 neu. Alle 8 P13/P16-Routen:

| Route | Auth | Authorizer | Target |
|---|---|---|---|
| `GET /v1/introspection` | JWT | `9ghezn` | `integrations/ewy9u57` |
| `POST /v1/apiprofiles/{apiProfileId}/credentials` | JWT | `9ghezn` | `integrations/ewy9u57` |
| `GET /v1/apiprofiles/{apiProfileId}/credentials` | JWT | `9ghezn` | `integrations/ewy9u57` |
| `GET /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}` | JWT | `9ghezn` | `integrations/ewy9u57` |
| `POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/rotate` | JWT | `9ghezn` | `integrations/ewy9u57` |
| `POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/disable` | JWT | `9ghezn` | `integrations/ewy9u57` |
| `POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/enable` | JWT | `9ghezn` | `integrations/ewy9u57` |
| `POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/revoke` | JWT | `9ghezn` | `integrations/ewy9u57` |

1–7 bestanden: API existiert, Introspection vorhanden, 7/7 Credential-Routen, **alle** mit JWT/`9ghezn`, alle auf der bestehenden Agent-Proxy-Integration. Keine zusätzlichen Routen entstanden (20 = 12 + 8).

Unverändertheitsnachweise:

- Lambda: `CodeSha256 yaKXvStx/o/M/XHUiA01d18cFDoi35PMcAibequbZHc=`, `LastModified 2026-10-04T11:44:08Z`, `Active`/`Successful`, Env 11 Variablen mit 3/3 P18B-Tabellen — **identisch zu P19**
- Cognito: `AutoVerifiedAttributes ["email"]`, Pool `eu-central-1_dgQXgwUbv` — **unverändert**
- IAM, SQS, DynamoDB: nur gelesen, im Plan durchgehend `no-op`
- Keine `$default`-, `ANY`- oder Greedy-Route

**Auth-Ketten-Readback** (ausdrücklich erlaubt, kein Credential-E2E, keine Credentials übertragen):

- `GET /v1/introspection` → **401**
- `GET /v1/apiprofiles/p1/credentials` → **401**

Beide Routen sind erreichbar und die JWT-Kette greift. `GET /health` liefert 404 — das ist ein **vorbestehender, sachfremder Befund**: die Route `GET /health` ist unverändert live und zeigt auf dieselbe Integration, der Handler enthält jedoch keinen `/health`-Pfad (`grep` in `lambda/handler.py` findet keinen Health-Handler). Nicht von diesem Gate verursacht, nicht angefasst.

## 7. Fresh Plan (Schritt 7)

Gezielter P13/P16-Plan mit `-var=identity_email_verification_enabled=true`: **`No changes.`** → **0 add / 0 change / 0 destroy** für P13/P16.

Voller Plan zur klaren Trennung: **`Plan: 8 to add`** — ausschließlich vorbestehender Fremd-Drift, davon **0** P13/P16-Routen:

- 6 alte CLI-Routen: `platform`, `me`, `profile`, `profile_create`, `profile_update`, `agents`
- `module.iam.aws_iam_role_policy.lambda_policy`
- `module.lambda.aws_lambda_event_source_mapping.sqs_mapping`

Die zuvor im P19-Plan sichtbaren Drift-Punkte `sqs_mapping` und `lambda_policy` bleiben bestehen, Cognito- und Lambda-Updates sind verschwunden. Summe 90 Ressourcen: 82 no-op + 8 create.

## 8. Tests (Schritt 8)

- `terraform fmt -check modules/api/main.tf`: clean. `terraform validate`: Success.
- Ohne `AWS_PROFILE` (Baseline-Bedingung): **15 failed, 709 passed, 8 skipped, 231 warnings, 1 error**, Fehler-MD5 `d0efae4dba6d8af196593535a46c3e57` — **identisch zu P18/P18B/P19**.
- Mit `AWS_PROFILE=mayaws` erscheinen 3 zusätzliche Fehler. Alle drei sind **durch das eigene Export-Setzen verursacht, keine Regression** — belegt per Mengenvergleich der Fehlerlisten (mit: 19, ohne: 16, Differenz exakt diese 3):
  - `test_ris_installer.py::test_aws_context_flows_to_child_env` und `::test_runner_without_context_unchanged` prüfen `assert "AWS_PROFILE" not in os.environ` — sie schlagen fehl, weil ich die Variable für die AWS-Kommandos exportiert hatte.
  - `test_lambda_packaging.py::TestLiveContract::test_e_noop_live_hash_matches` baut mit einer **veralteten Dateiliste** `["lambda/handler.py", "agents", "jobsearch"]` (Zeile 130-131) — ohne `lambda/documents.py`. Ergebnis 51 Dateien / `714d91ef…` gegen den live deployed, kanonisch gebauten 52-Dateien-Bundle `c9a297bd…`. Der Test ist veraltet, **nicht** das Deployment: `build_agent_bundle` liefert weiterhin `c9a297bd…` (reproduziert).
- Keine neuen funktionalen Tests, die Credentials oder Entitlements benötigen.

## 9. AWS Mutation

Acht `apigatewayv2:CreateRoute` auf `aboqolpm0f`. Sonst keine Mutation: kein Cognito-, Lambda-, IAM-, SQS-, DynamoDB- oder Stage-Write.

## 10. Git

- Commit: nur die beiden P16/P13-Reports. **Kein** Terraform-Code geändert (die Routen waren bereits in `terraform/modules/api/main.tf:100-167` definiert).
- `terraform/lambda.zip` ist git-ignoriert, nicht committet.
- `git status --short` clean (tracked).

## 11. Offene Punkte

1. **Entitlements-IAM fehlt `TransactWriteItems`** — nächstes Gate, vor Grant-E2E.
2. `GET /health` liefert 404 (Route live, kein Handler-Pfad) — vorbestehend, sachfremd.
3. `identity_email_verification_enabled` hat `default = false` ohne `.tfvars`; jeder Plan ohne explizites `-var=true` schlägt eine unbeabsichtigte Cognito-Änderung vor. Ursache ist `terraform/variables.tf:38-42` — Korrektur nicht in diesem Gate.
4. `test_lambda_packaging.py:130-131` nutzt eine veraltete Dateiliste ohne `lambda/documents.py`; `test_e` schlägt fehl, sobald Credentials vorhanden sind. Keine Teständerung in diesem Gate.
5. 6 alte CLI-Routen + `lambda_policy` + `sqs_mapping` weiterhin nicht deployed — vorbestehender Drift, bewusst nicht angefasst.
6. Kein Credential-E2E, kein P17 — wie gefordert.
