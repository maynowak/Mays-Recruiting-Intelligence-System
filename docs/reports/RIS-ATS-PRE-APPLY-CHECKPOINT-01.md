# RIS-ATS-PRE-APPLY-CHECKPOINT-01 — Read-only-Verifikation

**Status:** Verifikation abgeschlossen, eine lokale Konfigurationskorrektur,
neuer Plan geprüft. **Kein AWS Apply, Deploy, Destroy, Rollback oder Merge.**
**Datum:** 2026-11-17
**Branch / HEAD:** `feature/ris-dev2-ats-agent-pinned-core-01` / `4d612e8`
**Konto / Region / Workspace:** `262370457690` / `eu-central-1` / `ris-dev2`

## 1. Ergebnis in einem Satz

Der Result-Transport ist noch nicht deployt (kein Secret, keine Queue, keine
Consumer-Lambda), die Projektkonfiguration ist aber konsistent und der neue
Plan ist clean (`13 add / 2 change / 0 destroy / 0 replace`). Der einzige
verbleibende Produktblocker ist die Identität: beide Cognito-Pools sind leer,
und der Reader akzeptiert den vorhandenen M2M-Client nicht.

## 2. Änderung und Commit

| Commit | Inhalt |
|---|---|
| `4d612e8` | `fix(orders): point the worker at the live RIS orders facade` |

Die RIS-Fassade (`module.api.api_endpoint` = `https://r95qvhg2p3.execute-api.eu-central-1.amazonaws.com`)
wird jetzt als `ORDERS_BASE_URL` in die Worker-Env verdrahtet. Ohne diese
Korrektur fiel `agents/orders/function.py` auf `aboqolpm0f` zurück — eine
gelöschte API (API-NotFound + DNS NXDOMAIN). Keine Cognito-, Queue- oder
Identitätsänderung.

## 3. Konfigurationsstatus (live, read-only)

### 3.1 HMAC-Secret und Result-Queue

| Objekt | Status |
|---|---|
| Secret `ris-dev2-mays-orders-agent-result-hmac` | **nicht vorhanden** |
| Secrets Manager Secrets im Konto (eu-central-1) | **0** |
| Secret-Versionen / AWSCURRENT | keine (Container existiert nicht) |
| Queue `…-agent-results` | **nicht vorhanden** |
| Queue `…-agent-results-dlq` | **nicht vorhanden** |
| Consumer-Lambda `…-agent-result-consumer` | **nicht vorhanden** |
| `module.mays_orders[0].module.agent_transport` | **nicht im State** |

Der Terraform-Plan legt Container, Queue, DLQ, Policies und Consumer an. Das
Secret bleibt bewusst container-only: **kein `aws_secretsmanager_secret_version`**,
kein Secret-Wert in State, Plan oder Git.

### 3.2 Producer-/Consumer-Bindung

- Worker-Lambda live: `ris-dev2-dev-agent` mit Rolle
  `arn:aws:iam::262370457690:role/ris-dev2-dev-agent`.
- `module.lambda.lambda_role_arn` liefert genau diese Rolle (Plan-Output
  `lambda_role_arn = arn:aws:iam::262370457690:role/ris-dev2-dev-agent`).
- Die Orders-Queue-/Secret-Policy erhält damit den **richtigen** Principal.
  `ris-dev2-lambda-role` ist die Health-Plane-Rolle und wird hier nicht verwendet.
- Die bestehende Orders-Queue `…-orders-queue` erlaubt `SendMessage` nur dem
  Account-Root; sie ist nicht die Result-Queue.

### 3.3 Orders-API

| API-ID | Name | Zuordnung | Status |
|---|---|---|---|
| `r95qvhg2p3` | `ris-dev2-dev-api` | RIS (`ris-dev2`) | aktiv |
| `7ency74vs0` | `ris-dev2-mays-orders-api` | Orders (`ris-dev2-mays-orders`) | aktiv |
| `n4rhy1qpo0` | `ris-agent-dev-api` | Legacy-Stack | aktiv |
| `aboqolpm0f` | — | Adapter-Default | **gelöscht** |

`ORDERS_BASE_URL` war weder live noch in Terraform gesetzt. Mit `4d612e8`
zeigt der Worker jetzt auf die RIS-Fassade; `ORDERS_ID_TOKEN` bleibt ungesetzt,
Work-Items mit `auth.idToken` funktionieren, token-lose nicht.

### 3.4 Effektive RIS-Env

- **Worker `ris-dev2-dev-agent`:** kein `ORDER_RESULT_QUEUE_URL`, kein
  `ORDER_RESULT_SECRET_ARN`, keine `ORDERS_*`-Variable. `RIS_CURSOR_SECRET_ARN`
  ist leer. Code `94exPsBrUKodt2hkj4qeiPKroyiAdiTWYe/6o1SEKcw=`.
- **Reader `ris-dev2-dev-orders-reader`:** nur `ORDERS_TABLE` und
  `ORDERS_SQS_QUEUE_URL`; `ORDERS_COGNITO_ISSUER`/`_CLIENT_ID` fehlen. Der
  Reader antwortet daher auf **jeder** `/orders`-Route mit `503`, bevor er
  DynamoDB berührt. Code `omwZAl7q+m8ItJnVW6UaFTjSmLQ1bi2O/pszTswpGlY=`.
- State und Live sind deckungsgleich (Serial 58, gleiche Code-Hashes).
- Der Plan fügt Reader-Issuer/Client und Worker-`ORDERS_BASE_URL`/`ORDER_RESULT_*`
  hinzu und aktualisiert beide Code-Pakete.

### 3.5 Identity und Owner-Bindung

| Prüfung | Ergebnis |
|---|---|
| RIS-Pool | `eu-central-1_OYN9QiHc5` (`ris-dev2-dev-users`), Client `5jgjivk9k9rrjos62so1qhq8o3` |
| Orders-Pool | `eu-central-1_GInnOix9P` (`ris-dev2-mays-orders-users`), Client `4ak93tau2hoiet56ug454qbgb1` |
| Benutzer in beiden Pools | **0** |
| M2M-Client RIS | `3mrg2mb0jbejredqelkffgnmr6` (client_credentials) |
| Authorizer | RIS pinnt RIS-Pool, Orders pinnt Orders-Pool; keine Audience-Überlappung |
| Owner-Key | byte-identisch (`sha256(strip().rstrip("/") + "\x00" + sub)`), `gsi3`/`gsi3sk` gleich |
| Orders-Tabelle | `ris-dev2-mays-orders`, **0 Items**, `gsi3` aktiv |

Der Owner-Key ist korrekt. Ein über die Orders-API (`7ency74vs0`) erzeugter
Auftrag trägt jedoch den Orders-Pool-Issuer und ist für den RIS-Reader nicht
lesbar. Konsistent ist nur der Pfad über die RIS-Fassade — genau dorthin zeigt
der Worker seit `4d612e8`.

## 4. Plan-Reconciliation

| Prüfung | Wert |
|---|---|
| STS-Prinzipal | `arn:aws:iam::262370457690:user/devnemo` (Default-Profil; ein Profil `devnemo` existiert nicht) |
| Region | `eu-central-1` |
| Workspace | `ris-dev2` |
| Backend | `ris-dev2-tf-state-dev`, Key `env:/ris-dev2/dev/terraform.tfstate` |
| Lock | `ris-dev2-tf-lock`, keine aktive Lock |
| Lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Serial vor/nach Plan | `58` / `58` (ETag unverändert) |
| Builder-Pin | `dad69ea28e8b952a8e76e9dfb4fb163f7a979b52` (Clone clean, Manifest identisch) |
| Legacy-Clone-Pin | `5cf50a0…` für den alten Composite-Pfad; nicht der Builder-Pfad (dokumentiert) |
| Bundles | Agent `8462e5de…`, Reader `417e5b5f…` — zweiter Build identisch |
| Generiertes Modul | 23 Outputs (20 Pflicht + 3 Result-Transport) |
| **Plan-SHA-256** | `2ED7B1A5C63E0427719F75500E763025612625D94D8040E7E31CADC6A2AB4C01` |

**Plan:** **13 to add, 2 to change, 0 to destroy, 0 to replace.**

### Adds (13)

1. `module.dynamodb.aws_dynamodb_table_item.agent_catalog_seed["ats-agent"]`
2. `module.lambda.aws_iam_role_policy.lambda_order_result_send[0]`
3. `module.lambda.aws_iam_role_policy.lambda_order_result_secret[0]`
4. `module.mays_orders[0].module.agent_transport[0].aws_cloudwatch_log_group.result_consumer`
5. `…agent_transport[0].aws_iam_role.result_consumer`
6. `…agent_transport[0].aws_iam_role_policy.result_consumer`
7. `…agent_transport[0].aws_lambda_event_source_mapping.results`
8. `…agent_transport[0].aws_lambda_function.result_consumer`
9. `…agent_transport[0].aws_secretsmanager_secret.result_hmac`
10. `…agent_transport[0].aws_secretsmanager_secret_policy.result_hmac`
11. `…agent_transport[0].aws_sqs_queue.results`
12. `…agent_transport[0].aws_sqs_queue.results_dlq`
13. `…agent_transport[0].aws_sqs_queue_policy.results`

### Changes (2)

- `module.lambda.aws_lambda_function.agent` — neues Code-Paket, Env
  `ORDERS_BASE_URL`, `ORDER_RESULT_QUEUE_URL`, `ORDER_RESULT_SECRET_ARN`.
- `module.orders_reader[0].aws_lambda_function.reader` — neues Code-Paket,
  Env `ORDERS_COGNITO_ISSUER`, `ORDERS_COGNITO_CLIENT_ID`.

**Nicht im Plan:** Cognito-, CloudFront-, Route53/DNS-, ACM-Ressourcen,
`aws_secretsmanager_secret_version`, Secret-Werte, KMS-Custom-Key.

Hinweis: Die Worker-Env erscheint im Plan als `(known after apply)`, weil der
Secret-ARN erst beim Apply entsteht; die Schlüsselbindung ist über
`terraform/modules/lambda/main.tf` und den statischen Vertragstest belegt.

## 5. Tests

| Suite | Ergebnis |
|---|---|
| Statische Wiring-/Transport-Verträge + Worker/Reader/Link | 216 passed |
| Volle Suite | **2639 passed / 128 skipped / 434 subtests**, 29 vorbestehende Fehler, 4 vorbestehende Collection-Errors |
| Terraform | `fmt -check` exit 0, `validate` erfolgreich (Warnungen) |
| Bundles | reproduzierbar (identische Hashes) |

## 6. Verbleibende Blocker

1. **Secret-Wert fehlt.** Nach dem Apply muss sofort
   `put-secret-value` auf `ris-dev2-mays-orders-agent-result-hmac` mit einem
   **rohen Hex-String** erfolgen (kein Rotations-JSON). Vor dem Apply existiert
   der Container nicht; ein Vorab-Setzen erfordert `create-secret` + Import.
2. **Keine nutzbare Identität.** Beide Pools haben 0 Benutzer; der M2M-Client
   wird vom Reader-Audience-Check abgelehnt. Ohne Entscheidung (M2M-Audience
   im Reader akzeptieren = Codeänderung, oder Testbenutzer anlegen = Cognito-
   Mutation mit separater Freigabe) ist kein Ende-zu-Ende-Read-back
   nachweisbar.
3. **Zwei-Pool-Modell.** Nur Aufträge über die RIS-Fassade sind für den Reader
   lesbar; Orders-API-Aufträge tragen den Orders-Issuer. Der Worker zeigt seit
   `4d612e8` auf die Fassade, aber andere Erzeuger müssen dasselbe tun.
4. **`ORDERS_ID_TOKEN` ungesetzt** für Work-Items ohne `auth.idToken`.
5. **Consumer-Visibility 60 s** gegen Lambda-Timeout 30 s (Empfehlung ≥ 6×);
   Modul-seitig, nicht geändert.
6. **Kein `ORDER_FAILED`-Versand.**
7. **Generiertes Modul:** vor jedem Plan neu bauen; der getrackte
   `variables.tf`-Stub bleibt unverändert.
8. **Profilname:** `devnemo` existiert nicht; Identität über Default-Profil.

## 7. GO/NO-GO

**GO (bedingt) für den Transport-Apply:**
Der Plan ist nicht destruktiv (0 Destroy/Replace), betrifft keine
Cognito-/DNS-/ACM-Ressourcen, enthält keinen Secret-Wert und ist auf den
freigegebenen Commit `4d612e8` reproduzierbar. Bedingungen:

1. Plan gegen `4d612e8` neu erzeugen und `13/2/0/0` erneut bestätigen.
2. `orders_agent_result_enabled=true` nur über den freigegebenen Plan.
3. Unmittelbar nach dem Apply Secret-Wert setzen (roher Hex-String).
4. Kein Partner-Traffic, bis Schritt 3 verifiziert ist.

**NO-GO für Partner-Traffic und Produkt-Abnahme**, bis eine Identitäts-
entscheidung getroffen ist (M2M-Audience im Reader oder freigegebene
Testbenutzer) und der Secret-Wert gesetzt ist.

**HARD STOP vor jedem AWS Apply.**
