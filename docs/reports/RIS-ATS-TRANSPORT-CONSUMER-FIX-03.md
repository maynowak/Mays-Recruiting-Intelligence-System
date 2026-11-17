# RIS-ATS-TRANSPORT-CONSUMER-FIX-03

**Status:** Consumer-Blocker B1/B2 behoben, Pin aktualisiert, Modul reproduzierbar
neu gebaut, Plan geprüft. **Kein AWS Apply, Deploy, Destroy, Rollback oder
Main-Merge.**
**Datum:** 2026-11-17
**RIS-Branch / HEAD:** `feature/ris-dev2-ats-agent-pinned-core-01` / `206f222`
**Orders-Branch / HEAD:** `fix/order-result-signature-domain-01` / `016cdfd`
(lokal, nicht gepusht)

## 1. Commits

| Repo | Commit | Inhalt |
|---|---|---|
| Mays-Orders | `016cdfd` | Consumer-Fix: Signatur über Envelope-`messageId`, Batch-Failures bei Secret-/Infra-Fehlern, Härtungen, Tests, neuer `lambda.zip` |
| RIS | `206f222` | Pin-Update auf `016cdfd`, Bridge-Test auf Envelope-ID, Secret-Whitespace-Normalisierung, Auditlog |

Der Orders-Commit liegt auf einem lokalen Branch, `main` bleibt unberührt
(`origin/main` unverändert).

## 2. HMAC-Vertragsnachweis

- Producer: `HMAC-SHA256(secret, envelope.messageId + "\n" + body)`, gesendet
  als SQS-Attribut `serviceSignature`; `body` ist exakt der signierte String.
- Consumer (neu): parst zuerst den Body, verlangt eine nicht-leere
  String-`messageId`, verifiziert **über diese Envelope-ID**, und validiert
  erst danach das Envelope. Die SQS-`record.messageId` (UUID) wird nur noch als
  `itemIdentifier` für Batch-Failures verwendet.
- Lokaler Cross-SQS-Nachweis mit dem echten Consumer:
  - Envelope-ID signiert, Record-ID = UUID → `processed:1, rejected:0`
  - Signatur über die SQS-UUID → `rejected:1`, kein Write
  - manipulierte Envelope-ID → Signatur ungültig, kein Write
- Transport V1 bleibt unverändert; `ORDER_RESULT` und `ORDER_FAILED` nutzen
  dieselbe Basis.

## 3. Retry-/DLQ-/Batch-Verhalten

- Fehlendes/leeres/unlesbares Secret: **kein Erfolg**. Alle Records werden als
  `batchItemFailures` gemeldet (Retry, dann DLQ nach `maxReceiveCount=3`).
  Generische Secret-Read-Fehler (AccessDenied, Throttling, Netz) werden
  ebenfalls so behandelt.
- Infrastrukturfehler werden pro Record gesammelt und nur diese Records
  retried; erfolgreiche Records werden bestätigt.
- Permanente Fehler (ungültige Signatur, ungültiges JSON, fehlende
  `messageId`, Envelope-/Order-Fehler) werden konsumiert, nicht in die DLQ
  geschrieben.
- Nicht-ASCII-Signaturen lösen keinen Invocation-Fehler mehr aus, sondern
  werden permanent abgelehnt.
- Ein Record ohne SQS-`messageId` löst einen Invocation-Fehler aus und wird
  niemals still bestätigt.
- Offener Betriebsrisikopunkt: Visibility 60 s gegen Consumer-Timeout 30 s
  (2×, Guideline 6×); keine DLQ-Alarmierung.

## 4. Tests

| Suite | Ergebnis |
|---|---|
| Orders-Lambda (`lambda/tests`, unittest discover) | **225 passed** |
| RIS Cross-Repo (Bridge, MO-Contract, Dispatch-Handoff, Transport-Contract, Generated-Artifact) | **91 passed** |
| RIS Targeted Regression | **150 passed / 318 subtests** |
| RIS Volle Suite | **2640 passed / 128 skipped / 434 subtests**, unverändert 29 vorbestehende Fehler, 4 Collection-Errors |

Neue Orders-Tests: Envelope-ID vs SQS-ID (positiv/negativ), fehlendes/leeres
Secret als Batch-Failure, partieller Infrastrukturfehler, ungültiges
JSON/fehlende `messageId`, Nicht-ASCII-Signatur, Blank-Secret-Parsing,
Record ohne SQS-ID.

## 5. Reproduzierbarer Modul-Build

| Prüfung | Wert |
|---|---|
| Builder-Pin | `016cdfd6ac62565dcec9a2fee78cb898fb919e59` |
| Manifest `source.commit` | `016cdfd6ac62565dcec9a2fee78cb898fb919e59` |
| `lambda/dist/lambda.zip` | `48ddd5e52d07b40fc333b67e5e34fb1b67701cf823536e20c7b2816a78a05f94` |
| Modul-Outputs | 23 (20 Pflicht + 3 Result-Transport) |
| RIS Agent-Bundle | `4a6603e0c316fa5e870e9e886fb604b80bd950b02b981ae6a6333f8b45260f56` |
| RIS Reader-Bundle | `417e5b5f583e4f37248d0022a4cb0e387ad572d119b04cab92ca1575100d27bb` |
| Build-Determinismus | zweiter Lauf identisch |

Der Orders-Bundle enthält den Fix (`result_handler.py` verifiziert die
Body-`messageId`, `batchItemFailures` vorhanden).

## 6. Plan-Reconciliation

| Prüfung | Wert |
|---|---|
| STS | `arn:aws:iam::262370457690:user/devnemo` |
| Workspace | `ris-dev2` |
| Orders-Lifecycle | `managed` |
| Backend / Key | `ris-dev2-tf-state-dev` / `env:/ris-dev2/dev/terraform.tfstate` |
| Lineage / Serial | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` / **58 vor/nach Plan** |
| **Plan-SHA-256** | **`69F5687CDB2B463DE8B4551A5ADEBD292F927530ACD9412AAACC5804D793A68B`** |
| Aktionen | **13 add, 4 change, 0 destroy, 0 replace** |

**13 Adds:** Catalog-Seed `ats-agent`; 2 Worker-IAM-Policies; 10
Result-Transport-Ressourcen (Queue, DLQ, Queue-Policy, Secret, Secret-Policy,
Consumer-Rolle, Consumer-Policy, Log-Group, Consumer-Lambda,
Event-Source-Mapping).

**4 Changes:**
1. `module.lambda.aws_lambda_function.agent` — neues RIS-Bundle, Env
   `ORDERS_BASE_URL`, `ORDER_RESULT_QUEUE_URL`, `ORDER_RESULT_SECRET_ARN`.
2. `module.orders_reader[0].aws_lambda_function.reader` — neues Bundle, Env
   `ORDERS_COGNITO_ISSUER/CLIENT_ID`.
3. `module.mays_orders[0].module.lambda.aws_lambda_function.handler` —
   **nur `source_code_hash`** (gemeinsamer Orders-Bundle).
4. `module.mays_orders[0].module.sqs_worker.aws_lambda_function.worker` —
   **nur `source_code_hash`** (gemeinsamer Orders-Bundle).

Keine Cognito-, CloudFront-, Route53/DNS-, ACM- oder S3-Änderung; kein
`secret_version`; kein Delete/Replace. Der Orders-Handler und -Worker werden
in-place mit demselben Bundle aktualisiert, das auch den Consumer-Fix enthält;
ihre Konfiguration und Umgebung bleiben unverändert.

## 7. Verbleibende Risiken

1. Secret-Wert existiert erst nach dem Apply; danach sofort als roher
   64-Zeichen-Hex-String setzen (kein JSON/Newline). Vor dem Apply existiert
   der Container nicht.
2. Keine Identität: beide Cognito-Pools haben 0 Benutzer; der M2M-Client wird
   vom Reader-Audience-Check abgelehnt. Ein Live-Owner-E2E ist ohne separate
   Identitätsentscheidung nicht möglich.
3. Zwei-Pool-Modell: nur Aufträge über die RIS-Fassade sind für den Reader
   lesbar; der Worker zeigt seit `4d612e8` dorthin.
4. `ORDERS_ID_TOKEN` bleibt für Work-Items ohne `auth.idToken` ungesetzt.
5. Visibility 60 s / Consumer-Timeout 30 s; keine DLQ-Alarmierung.
6. Kein `ORDER_FAILED`-Versand durch die RIS-Pipeline (Consumer akzeptiert es).
7. Der Orders-Fix-Commit ist lokal und nicht gepusht; ein frischer Clone kann
   den Pin noch nicht bauen. Vor einem CI-/Apply-Lauf muss der Branch bewusst
   verfügbar gemacht werden (kein Main-Merge in diesem Auftrag).

## 8. GO/NO-GO

**GO (bedingt) für den Transport-Apply:**
B1/B2 sind behoben und durch Cross-SQS-Tests sowie 225 Orders-Tests belegt; der
Plan ist nicht destruktiv (0 Destroy/Replace) und enthält keine geschützten
Ressourcen. Bedingungen:

1. Orders-Fix-Commit für den Apply verfügbar machen (Push auf den
   Feature-Branch oder kontrollierter Merge; **nicht** Teil dieses Auftrags).
2. Plan gegen `206f222` neu erzeugen und `13/4/0/0` bestätigen.
3. Unmittelbar nach dem Apply Secret-Wert setzen und verifizieren.
4. Kein Partner-Traffic, bis Secret und Identität verifiziert sind.

**NO-GO für Partner-Traffic/Produkt-Abnahme**, bis eine Testidentität
freigegeben/angelegt und der Secret-Wert gesetzt ist.

**HARD STOP vor jedem AWS Apply.**
