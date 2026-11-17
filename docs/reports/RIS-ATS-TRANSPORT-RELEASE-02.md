# RIS-ATS-TRANSPORT-RELEASE-02 — Release-Manifest

**Status:** Release-Gate abgeschlossen. **NO-GO** für den Transport-Rollout.
**Datum:** 2026-11-17
**Branch / HEAD:** `feature/ris-dev2-ats-agent-pinned-core-01` / `caa5d6c`
**Konto / Region / Workspace:** `262370457690` / `eu-central-1` / `ris-dev2`
**Kein Apply, keine Secret-Mutation, keine Benutzeranlage, kein Merge.**

## 1. Freigegebener Zielstand und Plan

| Prüfung | Wert |
|---|---|
| STS-Prinzipal | `arn:aws:iam::262370457690:user/devnemo` (Default-Profil; kein Profil `devnemo`) |
| Workspace | `ris-dev2` |
| Orders-Lifecycle | `managed` |
| Backend | `ris-dev2-tf-state-dev`, Key `env:/ris-dev2/dev/terraform.tfstate` |
| Lock | `ris-dev2-tf-lock`, nur MD5-Digests, keine aktive Lock |
| Lineage / Serial | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` / **58 vor und nach Plan** |
| Builder-Pin | `dad69ea28e8b952a8e76e9dfb4fb163f7a979b52`, Clone clean, Manifest identisch |
| Bundles | Agent `8462e5de…`, Reader `417e5b5f…` (zweiter Build identisch) |
| Generiertes Modul | 23 Outputs (20 Pflicht + 3 Result-Transport) |
| **Plan-SHA-256** | **`5EA0619EBBEA092E650E66D10B526783165A812698E56E1AD54033A047702FAC`** |
| Aktionen | **13 add, 2 change, 0 destroy, 0 replace** |

Der Plan wurde gegen `caa5d6c` erzeugt, nachdem das generierte Modul mit
`python -m installer.build_mays_orders_module --project-name ris-dev2 --force`
neu gebaut wurde. **Der Rebuild ist Pflicht:** der getrackte
`terraform/modules/mays_orders/variables.tf`-Stub deklariert
`enable_agent_transport`/`ris_result_producer_role_arns` nicht; ohne Rebuild
schlägt `terraform validate` mit „Unsupported argument" fehl. Der Stub bleibt
unverändert und wird nicht committet.

## 2. Exakte Ressourcenänderungen

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
  `ORDERS_BASE_URL` (RIS-Fassade), `ORDER_RESULT_QUEUE_URL`,
  `ORDER_RESULT_SECRET_ARN`.
- `module.orders_reader[0].aws_lambda_function.reader` — neues Code-Paket,
  Env `ORDERS_COGNITO_ISSUER`, `ORDERS_COGNITO_CLIENT_ID`.
- Zusätzlich: Root-Output `lambda_role_arn`.

**Nicht enthalten:** Cognito-, CloudFront-, Route53/DNS-, ACM- oder
S3-Änderung; kein `aws_secretsmanager_secret_version`; kein Secret-Wert;
kein Delete/Replace.

## 3. Secret-Provisionierungsverfahren (nach Apply, nicht ausgeführt)

Format: **ein roher Hex-String, 64 Zeichen, kein JSON, kein Zeilenumbruch.**
Der Producer signiert den rohen `SecretString`; der Consumer akzeptiert zwar
auch `{"current","previous"}`, würde dann aber gegen `current` prüfen, während
der Producer den JSON-Text signiert — jede Signatur würde scheitern.

Ablauf (nach erfolgreichem Apply, Container existiert, noch keine Version):

1. 32 Byte Zufall erzeugen (PowerShell `RandomNumberGenerator`, POSIX
   `openssl rand -hex 32`), **ohne Ausgabe** in eine Datei mit restriktiven
   Rechten schreiben; Länge 64 prüfen, nie den Wert.
2. `aws secretsmanager put-secret-value --secret-id
   ris-dev2-mays-orders-agent-result-hmac --secret-string file://<tmp>`
   (kein Wert in argv/History).
3. Temp-Datei sofort löschen; `Test-Path` muss `False` sein; History prüfen.
4. Verifikation ohne Wert: `describe-secret` (Name, ARN, KmsKeyId) und
   `list-secret-version-ids` (genau eine Version, `AWSCURRENT`).
5. Shape-/Signatur-Nachweis in einem kurzlebigen Prozess: nur
   `keys=1 len=64 hex=true verify=true` ausgeben, niemals Wert oder Signatur.
6. Rotation: Traffic quiescen, neue Version setzen, **beide** Lambdas durch
   identische Env-Neusetzung recyceln (kein Cache-TTL), Canary senden,
   `AWSPREVIOUS` als Rollback behalten.

Kein `kms_key_id` gesetzt → AWS-managed Key; `GetSecretValue` genügt. Ein
Custom CMK würde `kms:Decrypt` beim Producer erfordern (nicht verdrahtet).

## 4. Vorschlag Testidentität (nur Design, nicht angelegt)

| Feld | Wert |
|---|---|
| Pool | `eu-central-1_OYN9QiHc5` (bestehend, keine Änderung) |
| Client | `5jgjivk9k9rrjos62so1qhq8o3` (bestehend, keine Änderung) |
| Username | `ris-dev2-e2e-rdbk-01` |
| E-Mail | `ris-dev2-e2e-rdbk-01@example.invalid` (reserved TLD) |
| `email_verified` | `true` |
| `custom:tenant_id` | `tenant-e2e-15` |
| Gruppen | keine |
| Status | `CONFIRMED`, `Enabled=true` |
| Passwort | zufällig, nur out-of-band; nie in Report/Git/Terraform/Log |
| Anlage | `admin-create-user --message-action SUPPRESS`, danach `admin-set-user-password --permanent` aus `read -rs` |

Token: `initiate-auth --auth-flow USER_PASSWORD_AUTH` (der Client erlaubt
**kein** `ADMIN_USER_PASSWORD_AUTH`). Erwartete Claims: `iss` RIS-Pool,
`sub` UUID, `token_use` `id`/`access`, `aud`/`client_id` RIS-Client.

Read-back braucht **keine** Datenzeilen (nur JWT + Owner-Binding). Der
ATS-Execute-Pfad bräuchte zusätzlich Entitlement (`userId=<sub>`,
`agentId=ats-agent`), API-Profil `ACTIVE`, Partner-Application `ACTIVE` und
Credential — das ist ein separater, freizugebender Schritt.

**Keine Pool-/Client-/Domain-Änderung nötig; jetzt wird kein Benutzer
angelegt.**

## 5. Release-Blocker (NO-GO)

### B1 — Signatur-Domäne stimmt nicht (kritisch)

- Producer signiert `HMAC(secret, envelope.messageId + "\n" + body)`
  (`agents/transport/order_result_sender.py`), also
  `msg_<workId>_order_result`.
- Der gepinnte Consumer prüft gegen `record["messageId"]` — die von SQS
  vergebene UUID (`installer/.../lambda/src/result_handler.py:75,78`).
- Lokaler Cross-SQS-Nachweis mit dem echten Consumer-Code:
  - `messageId = msg_work-1_order_result` → `{"processed":1,"rejected":0}`
  - `messageId = <SQS-UUID>` → `{"processed":0,"rejected":1}`
- Der Consumer liefert **kein** `batchItemFailures`; die Nachricht wird trotz
  `ReportBatchItemFailures` gelöscht. Ergebnis: **alle** Resultate werden
  still verworfen.
- Die vorhandenen Tests verdecken das, weil sie `record["messageId"]` auf die
  Envelope-ID setzen.

**Erforderlicher Fix (Orders-Seite, nicht in diesem Auftrag umgesetzt):**
Consumer verifiziert über die `messageId` **aus dem Body** (oder der Producer
setzt eine `messageId`-Message-Attribute und der Consumer liest sie). Danach
Pin-Bump des Orders-Moduls, neuer Plan, Cross-SQS-Test.

### B2 — Silent Drop bei fehlendem/leerem Secret (hoch)

`result_consumer.handler` liefert bei fehlendem ARN, `SecretUnavailable` oder
leerem Secret `200` ohne `batchItemFailures`; SQS löscht die Nachrichten.
Zusammen mit B1 ist der Verlust vollständig und still. Fix: Batch-Failure
melden oder Exception werfen, damit Redelivery/DLQ greift.

### B3 — Betriebliche Risiken

- Visibility 60 s gegen Consumer-Timeout 30 s (2×, Guideline 6× nicht erfüllt).
- Kein `ORDER_FAILED`-Versand; dauerhaft fehlgeschlagene Agenten bleiben für
  Orders unsichtbar.
- Beide Cognito-Pools haben 0 Benutzer; ohne Testidentität kein Live-E2E.
- `ORDERS_ID_TOKEN` ungesetzt für Work-Items ohne `auth.idToken`.
- Zwei-Pool-Modell: nur Aufträge über die RIS-Fassade sind für den Reader
  lesbar; Orders-API-Aufträge tragen den Orders-Issuer.
- Leere `ris_result_producer_role_arns` würden bei direktem Modulaufruf eine
  ungültige `Principal: []`-Policy erzeugen (bei deaktiviertem Modul latent).

## 6. GO/NO-GO

**NO-GO für den Transport-Apply.**

Der Terraform-Plan ist sauber und nicht destruktiv, aber der gepinnte Consumer
verwirft jedes korrekt signierte Resultat (B1) und löscht es still; ein Apply
würde eine dauerhaft nicht funktionierende Zustellung erzeugen. Zuerst müssen
B1 und B2 auf der Orders-Seite behoben, der Modul-Pin aktualisiert und ein
neuer Plan gegen den neuen Pin erzeugt und geprüft werden.

**Freigabebedingung für ein späteres Gate:**

1. Consumer-Signaturfix + Silent-Drop-Fix, Cross-SQS-Test (Envelope-ID und
   echte SQS-UUID), Orders-Pin-Bump.
2. Neuer Plan: 13/2/0/0, keine geschützten Ressourcen, State-Serial unverändert.
3. Secret-Wert nach dem Apply als roher Hex-String setzen und verifizieren.
4. Testidentität nur mit separater Freigabe anlegen; danach Owner-E2E.

**HARD STOP vor jedem AWS Apply.**
