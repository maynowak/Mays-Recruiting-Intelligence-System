# RIS-ORDER-RESULT-CORRELATION-FIX-01

**Datum:** 2026-11-25
**Repository:** `maynowak/Mays-Recruiting-Intelligence-System`
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `afb3397b4da49c5d2a290702133a541e1dada76d`
**Fix-Commit:** `f08dfff36b8d4727ebdbbe92b641fb60a4da88fd`
**MO-Pin (unverändert):** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`
**Verdict: FIXED + neuer Plan 0 Add / 7 Change / 0 Destroy / 0 Replace — Apply weiterhin gesperrt**

---

## 1. Fehlerbild (aus RELEASE-READINESS-01)

Der geplante Reader speicherte die validierte AgentOrder nur als
`orderDescription`. Der MO-Consumer (`db4f9e7`) liest die Korrelation aber aus
`item["agentOrder"]`:

- `lambda/src/order_service.py:467` → `agent_order = item.get("agentOrder") or {}`
- `lambda/src/order_service.py:470-473` → `ResultRejected("missing_correlation")`
- ebenso `lambda/src/dispatch.py:47` im MO-eigenen Dispatch-Builder.

Folge: ORDER_RESULTs für über den RIS-Reader angelegte Agent-Aufträge wurden
dauerhaft verworfen (`rejected`, kein Retry/DLQ).

---

## 2. Fix

`lambda/orders_reader.py`, `_create_agent_order()`:

- Die bereits aus `orderDescription` geparste und vollständig validierte
  AgentOrder V1 wird zusätzlich als **internes** `agentOrder` im
  DynamoDB-Datensatz gespeichert.
- Sie wird **nie** aus einem clientgelieferten Root-`agentOrder` übernommen:
  das öffentliche Create-Format bleibt
  `customer`, `items`, `currency`, `orderType`, `orderDescription`;
  ein Root-`agentOrder` wird weiterhin mit 400 abgelehnt.
- `metadata.requestId`, `metadata.apiProfileRef`, Target, `input.data` und
  `agentOrderFingerprint` stammen aus demselben Objekt — kein neuer
  Korrelationsalgorithmus, keine abweichende Kopie.

`_public()`:

- Für neue OrderV1-Zeilen (sie tragen immer `orderDescription`) wird die
  interne Kopie **nicht** veröffentlicht.
- Legacy-Zeilen ohne `orderDescription` behalten die bisherige
  Read-Projektion (minimiertes `agentOrder`) unverändert.

Es wurden **keine** MO-, Terraform-Ressourcen- oder Public-API-Dateien
geändert (`git diff afb3397..HEAD -- terraform installer` ist leer).

---

## 3. Privacy-/Datenminimierungs-Prüfung

| Pfad | Ergebnis |
| --- | --- |
| RIS-Reader `_public()` | interne Kopie für neue Zeilen ausgeblendet; Legacy unverändert |
| RIS-Reader `_list_item()` | enthält kein `agentOrder` (unverändert) |
| MO `to_public_order()` | `agentOrder`/`agentOrderFingerprint` sind in `INTERNAL_FIELDS` → nie öffentlich |
| MO `inspect_subject`/`export_subject`/`erase` | selektieren über `gsi2pk`/`subjectId`; die Reader-Zeile trägt **kein** `subjectId`/`gsi2*` → nicht im Scope dieser Operationen (im Test explizit geprüft) |
| MO `export_subject` | Projektion enthält weiterhin nur `orderDescription`, nie `agentOrder` |
| Anonymize | entfernt `orderDescription`; die interne Kopie bleibt — für Reader-Zeilen nicht erreichbar (kein GSI2). Als vorbestehende Semantik dokumentiert, nicht durch diesen Fix eingeführt. |

Der Fix stellt damit die vom MO-Consumer benötigte Korrelation wieder her,
ohne die interne Kopie öffentlich zu machen.

---

## 4. Verifikation

### Reader → Consumer E2E (gepinnt `db4f9e7`, **nicht übersprungen**)

`MO_ORDERS_SRC=<clone>/lambda/src python -m pytest tests/test_agent_order_dispatch_e2e.py -q`

**8 passed**, darunter:

- Create → Dispatch → Agent → ORDER_RESULT → Consumer → autorisierter Read-back
  (vollständig, `processed=1`),
- Duplicate Result (kein zweiter Write),
- falsche Correlation → `rejected`, kein `processing`-Write,
- falsche WorkId → `rejected`, kein `processing`-Write,
- ungültige Signatur → `rejected`, keine Persistenz,
- Fremdzugriff → 404,
- interner Datensatz: `agentOrder` == geparste `orderDescription`,
  Fingerprint konsistent, `to_public_order()` ohne `agentOrder`, keine
  `subjectId`/`gsi2*`,
- MO `dispatch.build_dispatch_envelope()` verarbeitet den gespeicherten
  Datensatz unverändert (OrderId, Correlation, WorkId, Target, ContextRef).

### Regressionen

| Lauf | Ergebnis |
| --- | --- |
| Breites RIS-Set (20 Dateien, inkl. Cross-Repo-Vertrag) | **362 passed, 9 skipped, 329 subtests** |
| `tests/test_lambda_bridge_e2e.py` isoliert | **5 passed** |
| MO-Lambda-Suite `db4f9e7` | **240 Tests OK** |
| Root-`agentOrder` im Create | weiterhin **400** (`test_root_agent_order_is_rejected`) |
| Legacy-Read-Projektion | unverändert (`test_agent_projection_is_whitelisted`) |

Bekannte, **vorbestehende** Harness-Interferenz: `test_cross_repo_mo_contract.py`
zusammen mit `test_lambda_bridge_e2e.py` in einem Prozess führt zu einem
`Order does not exist` im Bridge-Test. Der Fehler tritt identisch mit dem
Baseline-Reader (`afb3397`) auf, verschwindet ohne die Cross-Repo-Datei und
tritt in keinem Datei-Paar allein auf — kein Code-Regress dieses Fixes.

---

## 5. Bundles

| Bundle | SHA-256 | `source_code_hash` |
| --- | --- | --- |
| `terraform/lambda.zip` (unverändert) | `d767a198…dd06` | `12ehmEOp…` |
| `terraform/analysis-lambda.zip` (unverändert) | `e268b028…16db` | `4miwKAu5…` |
| `lambda/dist/orders-reader.zip` (**neu**) | `610004f6…ae6b` | `YQAE9urj…` |
| `terraform/modules/mays_orders/lambda/dist/lambda.zip` (unverändert) | `aa70eaaa…1c89` | `qnDqqhy2…` |

Reader-ZIP-Inhalt: 4/4 Dateien byte-identisch mit den Quellen.

---

## 6. Neuer RIS-DEV2-Plan

| Punkt | Wert |
| --- | --- |
| Datei | `C:\tmp\ris-dev2-correlation-fix.tfplan` |
| Größe | 250 940 Bytes |
| SHA-256 | `2bbf81424b9761712008ef698f5afe5bb6b5ac1db0eaa74220427e8f09b7facd` |
| Timestamp | `2026-11-25T07:07:04Z` (nach Fix-Commit `08:06:35` lokal) |
| Summary | **0 Add / 7 Change / 0 Destroy**, 0 Replace |
| No-ops | 265 (IAM 50, Cognito 15, DynamoDB 23, SQS 13, Secrets 2, ESM 4, CloudFront 2, API-GW 88, S3 27, CloudWatch 29, …) |

Die sieben Updates sind identisch zur vorherigen Freigabe, **nur der Reader
ändert sich zusätzlich**:

| Adresse | Hash |
| --- | --- |
| `module.orders_reader[0].aws_lambda_function.reader` | `RkuZH3hP…` → `YQAE9urj…` |
| `module.lambda.aws_lambda_function.agent` | `hXdfaF7a…` → `12ehmEOp…` |
| `module.agent_transport[0].aws_lambda_function.dispatch_ingress` | `hXdfaF7a…` → `12ehmEOp…` |
| `module.analysis_runtime.aws_lambda_function.analysis[0]` | `Qgv4YQkg…` → `4miwKAu5…` |
| `module.mays_orders[0].module.lambda.aws_lambda_function.handler` | `SN3V5S0H…` → `qnDqqhy2…` |
| `module.mays_orders[0].module.sqs_worker.aws_lambda_function.worker` | `SN3V5S0H…` → `qnDqqhy2…` |
| `module.mays_orders[0].module.agent_transport[0].aws_lambda_function.result_consumer` | `SN3V5S0H…` → `qnDqqhy2…` |

Jeweils nur `source_code_hash` + `last_modified`; keine Environment-, IAM-,
Cognito-, CloudFront-, DNS-, DynamoDB-, SQS-, Secrets- oder ESM-Änderung.

Gegenüber dem gesperrten Plan `cc140152…`: gleiche sieben Adressen, sechs
identische Ziel-Hashes, nur der Reader wechselt von `2PWEDXGy…` auf
`YQAE9urj…`.

---

## 7. Identität und State (read-only)

| Punkt | Wert |
| --- | --- |
| Workspace | `ris-dev2` |
| Account | `262370457690` |
| Region | `eu-central-1` |
| Backend | S3 `ris-dev2-tf-state-dev`, `env:/ris-dev2/dev/terraform.tfstate`, Lock `ris-dev2-tf-lock` |
| Lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Serial | **69** (270 managed + 17 data) |
| State unverändert | S3 `LastModified 2026-11-22T11:52:56Z`, VersionId unverändert |
| Lock | keine aktive Sperre |
| Plan-Prior-State vs Live | 248 identisch, 21 Provider-Schema-Normalisierungen, keine Drift |
| Deployed `CodeSha256`/Env | für alle sieben Funktionen == Plan-`before`; Env unverändert |

---

## 8. Nicht ausgeführt / offene Punkte

- Kein `terraform apply`, keine AWS-Mutation, kein State-Write, kein Main-Merge.
- Der alte Plan `cc140152…` bleibt **gesperrt** und ist durch diesen Plan
  ersetzt.
- Live-Nachweise bleiben offen (keine Live-Invocation der Bundles, kein
  Live-Roundtrip nach Apply). Nach dem Apply ist ein Smoke-Test des
  Result-Rückwegs erforderlich.
- Vorbestehend: `ORDER_DISPATCH_QUEUE_URL` wird vom MO-Code nicht gelesen;
  `PRIVACY_INTERNAL_SECRET` fehlt in der Env (Privacy fail-closed).
