# RIS-DEV2-PERSISTENCE-FIX-16

**Datum:** 2026-11-26
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `dbb4a79f721361c592dc9f87187446eacb1fa979`
**AWS:** `262370457690` / `eu-central-1` / `ris-dev2`
**Status:** **DEPLOYMENT PLAN PENDING APPROVAL**
**Modus:** Code-Fix + Tests + Bundle-Rebuild + neuer Plan; keine AWS-Writes, kein Apply

## 1. Ursache (offline reproduziert)

Der Dispatch-Ingress ubergab die WorkItem-Transaktion an
`table.meta.client`. Dieser Client tragt die Resource-Dokument-
Transformation und serialisiert das bereits explizite DynamoDB-JSON ein
zweites Mal:

| Client | `workId` auf der Leitung |
| --- | --- |
| Resource (`table.meta.client`, bisher) | `{"M":{"S":{"S":"work-..."}}}` |
| Low-Level (`_ddb_transaction_client()`) | `{"S":"work-..."}` |

DynamoDB lehnt den doppelt verschachtelten Schlussel der
Fence-`ConditionCheck` mit `ValidationError` ab. Das erklart die
wiederholten Cancellation-Codes `index 0 ValidationError` /
`index 1 None` ohne IAM-, Key- oder Fence-Problem.

## 2. Fix

`agents/runtime/work_queue.py`

- Transaktion nutzt den vorhandenen `_ddb_transaction_client()`
  (Plain-Low-Level-Client). Der `table.put_item`-Fallback fur
  Test-Doubles bleibt erhalten.
- Neue Klassifikation `_raise_for_cancellation()` anhand des
  Operations-Index:
  - Index 0 `ConditionalCheckFailed` -> `WorkEnqueueError`
    ("subject fence is active"), kein Duplicate-Pfad.
  - `ValidationError` -> `WorkEnqueueError`, fail closed.
  - `TransactionConflict` -> `WorkEnqueueError`, fail closed.
  - Nur ein Put-Condition-Failure (Index 1) erreicht die
    Duplicate-/Reuse-Prufung.
- `CancellationReasons` werden weiterhin ausschliesslich als sichere
  Codes (Index + Code) geloggt, nie Werte oder Payloads.
- Die strenge `_reuse_problem()`-Validierung aus Fix 13A bleibt aktiv.

## 3. Tests

| Lauf | Ergebnis |
| --- | --- |
| `test_work_queue.py` inkl. neuer Falle | PASS |
| `test_dispatch_ingress_lambda.py` | PASS |
| `test_agent_order_dispatch_e2e.py` (MO `db4f9e7`) | PASS |
| `test_analysis_ecosystem_wiring.py` (neuer Bundle-Pin) | PASS |
| `test_mo_dispatch_handoff.py` | PASS |
| `test_ris_dynamodb_marshalling_offline.py` (offline, ohne AWS) | PASS |
| Fokussiert gesamt | **69 passed** |

Neue Falle: Fence-Ablehnung, `ValidationError`, `TransactionConflict`,
Put-Condition-Duplicate, Low-Level-Client-Nutzung sowie der
Wire-Request-Vergleich Resource- vs. Low-Level-Client.

## 4. Reproduzierbare Bundles

| Bundle | SHA-256 |
| --- | --- |
| Agent (`terraform/lambda.zip`) | `cf0958a6a9b95f95ad84e0a77b08ebb8d950948944ab0b7030601580a72ef304` |
| Analysis (`terraform/analysis-lambda.zip`) | `2f74cab915fdb0ca909ff64c47b786d58cc140a5fc31e34d26f10002b98c1346` |
| Reader | unverandert `610004f6...` |
| MO-Modul | unverandert `aa70eaaa...` |

## 5. Frischer Plan

| Feld | Wert |
| --- | --- |
| Datei | `C:\tmp\ris-dev2-workitem-persistence-fix-16.tfplan` |
| Grosse | 252 638 Bytes |
| SHA-256 | `2dacb48de56fb014a529fb868b436d1a86e76ccfdf771b942b5d3d354285ed57` |
| Diff | **0 Add / 3 Change / 0 Destroy / 0 Replace** |
| Funktionen | `agent`, `agent-dispatch-ingress`, `analysis` |
| Attribute | nur `source_code_hash` + `last_modified` |
| Code-Hashes | Agent/Ingress `zwlYpqm5X5WthOCnewjruNlQlIlEqwtwMGAVgKcu8wQ=`, Analysis `L3TKuRX9sMqQn/ZMR7eG1YzBQKX8MeNNJvEAArmME0Y=` |
| Synthetic-Env | unverandert `MODE=true` |
| State | Serial **74**, Lineage `a0bd361d-...` unverandert |
| S3-State | `d24K7fWhqup_DQtI_PNDlL85DoML9fpE.`, unverandert |
| Drift | keine |

Der Plan enthalt ausschliesslich die drei erwarteten
Lambda-Code-Updates; IAM, Queues, Cognito, API, Offer, Entitlement und
Synthetic-Konfiguration sind unverandert.

## 6. AWS-Zustand (unverandert, Snapshot 2026-11-26T09:00Z)

| Prufung | Ergebnis |
| --- | --- |
| Alte Order `ord_676668...` | `PENDING`, unangetastet |
| Altes WorkItem `work-eb1185...` | weiterhin nur `workId` + `enqueuedAt` |
| Neue Order `ord_a566f4...` | `PENDING`, Dispatch `SENT`, kein Processing |
| Neues WorkItem | 0 |
| Dispatch-Queue / DLQ | 0 / 0 (1 in-flight) |
| Work-Queue / DLQ | 0 / 1 (alte Nachricht unverandert) |
| State / S3 | Serial **74** / `d24K7fWh...` |
| Synthetic-Modus | `true`, Ablauf 2026-11-26T17:40:28Z |

## 7. Grenzen

Kein AWS-Write ausser dem bereits genehmigten Plan-Lauf aus 13A; kein
Apply, kein Redrive, keine neue Order, keine Datenkorrektur, kein
Cleanup, kein neuer Grant, kein Main-Merge. Die beiden bestehenden
Orders und das beschadigte WorkItem bleiben unangetastet.

## 8. Nachster Schritt

Separate Freigabe fur **genau diesen** Plan `2dacb48d...` (0/3/0)
einholen. Nach dem Apply sind die drei Lambdas zu verifizieren; danach
ist fur den E2E erneut eine eigene Freigabe fur genau eine neue Order
erforderlich (vor `2026-11-26T17:40:28Z`).
