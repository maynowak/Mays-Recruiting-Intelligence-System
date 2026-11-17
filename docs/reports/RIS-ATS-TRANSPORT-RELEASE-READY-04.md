# RIS-ATS-TRANSPORT-RELEASE-READY-04

**Status:** Release-Baseline hergestellt. Orders-Fix veröffentlicht, Pin aus
frischem Clone reproduziert, Plan geprüft. **Kein AWS Apply, Destroy,
Rollback oder Main-Merge.**
**Datum:** 2026-11-17
**RIS-Branch / HEAD:** `feature/ris-dev2-ats-agent-pinned-core-01` / `e81609b`
**Orders-Branch / Commit:** `fix/order-result-signature-domain-01` /
`016cdfd6ac62565dcec9a2fee78cb898fb919e59`

## 1. Phase 1 — Orders-Fix veröffentlicht

- Branch `fix/order-result-signature-domain-01` sauber, HEAD
  `016cdfd6ac62565dcec9a2fee78cb898fb919e59`.
- Orders-Lambda-Suite: **225 Tests, OK** (auch im frischen Clone).
- Auditlog `[ORDER-RESULT-SIGNATURE-DOMAIN-01]` vorhanden und korrekt.
- Push ausschließlich dieses Feature-Branches nach `origin`; Upstream-Tracking
  gesetzt. **`main` unverändert** (`1eaa14ec5ed652a34e1dae4775e0b298be708a6c`),
  **keine Tags** auf `016cdfd`.
- Remote-Head des Branches: `016cdfd6ac62565dcec9a2fee78cb898fb919e59`.

## 2. Phase 2 — RIS-Pin und frischer Clone

| Prüfung | Wert |
|---|---|
| Builder-Pin | `016cdfd6ac62565dcec9a2fee78cb898fb919e59` |
| `PINNED_COMMIT` | identisch |
| Frischer Clone | `https://github.com/maynowak/mays-order-aws.git`, Branch `fix/order-result-signature-domain-01` |
| Clone-HEAD | `016cdfd6ac62565dcec9a2fee78cb898fb919e59` |
| Clone-Zip | `48ddd5e52d07b40fc333b67e5e34fb1b67701cf823536e20c7b2816a78a05f94` |
| Zip-Rebuild im Clone | identisch (`48ddd5e5…`) |
| Manifest `source.commit` | `016cdfd6ac62565dcec9a2fee78cb898fb919e59` |
| Manifest `artifacts_sha256` | `48ddd5e52d07b40fc333b67e5e34fb1b67701cf823536e20c7b2816a78a05f94` |
| Modul-Outputs | 23 (20 Pflicht + 3 Result-Transport) |
| RIS Agent-Bundle | `4a6603e0c316fa5e870e9e886fb604b80bd950b02b981ae6a6333f8b45260f56` |
| RIS Reader-Bundle | `417e5b5f583e4f37248d0022a4cb0e387ad572d119b04cab92ca1575100d27bb` |
| Build-Determinismus | zweiter Lauf identisch |

Der Modul-Build wurde über einen temporären Junction auf den frischen Clone
ausgeführt und der lokale Clone danach unverändert wiederhergestellt. Keine
Änderung an Mays-Jobsearch.

## 3. Phase 3 — Release-Plan

| Prüfung | Wert |
|---|---|
| STS | `arn:aws:iam::262370457690:user/devnemo` |
| Workspace | `ris-dev2` |
| Orders-Lifecycle | `managed` |
| Backend / Key | `ris-dev2-tf-state-dev` / `env:/ris-dev2/dev/terraform.tfstate` |
| Lineage / Serial | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` / **58 vor/nach Plan** |
| Lock | nur MD5-Digests, keine aktive Lock |
| **Plan-SHA-256** | **`B6A167308A1FAABBD29C8F13F34F1D05E9FE11A457D9E195DE11D45897D85011`** |
| Aktionen | **13 add, 4 change, 0 destroy, 0 replace** |

**Keine** Cognito-, CloudFront-, Route53/DNS-, ACM- oder S3-Änderung; **kein**
`aws_secretsmanager_secret_version`, kein Secret-Wert; **keine** unerklärte
Drift (State unverändert, ETag/VersionId identisch).

### Adds (13)

1. `module.dynamodb.aws_dynamodb_table_item.agent_catalog_seed["ats-agent"]`
2. `module.lambda.aws_iam_role_policy.lambda_order_result_send[0]`
3. `module.lambda.aws_iam_role_policy.lambda_order_result_secret[0]`
4–13. `module.mays_orders[0].module.agent_transport[0].*`:
Log-Group, IAM-Rolle, IAM-Policy, Event-Source-Mapping, Consumer-Lambda,
HMAC-Secret, Secret-Policy, Result-Queue, DLQ, Queue-Policy.

### Changes (4)

1. `module.lambda.aws_lambda_function.agent` — neues RIS-Bundle, Env
   `ORDERS_BASE_URL`, `ORDER_RESULT_QUEUE_URL`, `ORDER_RESULT_SECRET_ARN`.
2. `module.orders_reader[0].aws_lambda_function.reader` — neues Bundle, Env
   `ORDERS_COGNITO_ISSUER/CLIENT_ID`.
3. `module.mays_orders[0].module.lambda.aws_lambda_function.handler` —
   **nur `source_code_hash`** (gemeinsamer Orders-Bundle).
4. `module.mays_orders[0].module.sqs_worker.aws_lambda_function.worker` —
   **nur `source_code_hash`** (gemeinsamer Orders-Bundle).

## 4. Tests

| Suite | Ergebnis |
|---|---|
| Orders-Lambda lokal | **225 passed** |
| Orders-Lambda im frischen Clone | **225 passed** |
| RIS Cross-Repo (frischer Clone + generiertes Modul) | **91 passed** |
| RIS Volle Suite | **2640 passed / 128 skipped / 434 subtests** |
| Vorbestehend | 29 Fehler, 4 Collection-Errors (unverändert) |

## 5. Verbleibende Apply- und E2E-Blocker

1. **Secret-Wert:** existiert erst nach dem Apply; unmittelbar danach als
   roher 64-Zeichen-Hex-String setzen (kein JSON/Newline).
2. **Identität:** beide Cognito-Pools haben 0 Benutzer; der M2M-Client wird
   vom Reader-Audience-Check abgelehnt. Owner-E2E braucht eine separaten,
   freigegebenen Testbenutzer oder eine M2M-Audience-Entscheidung.
3. **`ORDERS_ID_TOKEN`** bleibt für Work-Items ohne `auth.idToken` ungesetzt.
4. **Visibility 60 s** vs. Consumer-Timeout 30 s; keine DLQ-Alarmierung.
5. **Kein `ORDER_FAILED`-Versand** durch die RIS-Pipeline.
6. **Merge-Status:** Der Orders-Fix liegt auf dem Feature-Branch, nicht auf
   `main`; das ist beabsichtigt und Voraussetzung für einen kontrollierten
   Merge nach Freigabe.
7. **Generiertes Modul** muss vor jedem Plan neu gebaut werden; der getrackte
   `variables.tf`-Stub bleibt unverändert.

## 6. GO/NO-GO

**GO (bedingt) für den Transport-Apply:**
Der Orders-Fix ist veröffentlicht und aus einem frischen Clone reproduzierbar;
der Plan ist nicht destruktiv (0 Destroy/Replace), enthält keine geschützten
Ressourcen und keine Secret-Werte. Bedingungen:

1. Plan gegen den freigegebenen RIS-Commit neu erzeugen und `13/4/0/0`
   bestätigen.
2. `orders_agent_result_enabled=true` nur über den freigegebenen Plan.
3. Unmittelbar nach dem Apply Secret-Wert setzen und verifizieren.
4. Kein Partner-Traffic, bis Secret und Identität verifiziert sind.

**NO-GO für Partner-Traffic/Produkt-Abnahme**, bis eine Testidentität
freigegeben/angelegt und der Secret-Wert gesetzt ist.

**HARD STOP vor jedem AWS Apply.**
