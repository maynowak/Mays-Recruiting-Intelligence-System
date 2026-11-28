# RIS-DEV2-DYNAMODB-TRANSACTION-CLIENT-FIX-16

**Datum:** 2026-11-26
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `dbb4a79f721361c592dc9f87187446eacb1fa979`
**AWS:** `262370457690` / `eu-central-1` / `ris-dev2`
**Status:** **READY FOR TRANSACTION CLIENT FIX APPLY APPROVAL**
**Modus:** Abschlusspruefung + Dokumentation; keine AWS-Writes, kein Apply

## 1. Gepruefter Fix-16-Stand

Vier Dateien, Commit `4f6cd65375cbfd9fe308078ad56ae385304b954e`:

| Datei | Aenderung |
| --- | --- |
| `agents/runtime/work_queue.py` | Transaktion ueber `_ddb_transaction_client()`; Cancellation-Klassifikation nach Index; fail closed |
| `tests/test_work_queue.py` | Fence-, Validation-, Conflict-, Put-Duplicate- und Low-Level-Client-Tests |
| `tests/test_analysis_ecosystem_wiring.py` | Bundle-Pin `cf0958a6...` / `2f74cab9...` |
| `tests/test_ris_dynamodb_marshalling_offline.py` | Offline-Wire-Test Resource vs. Low-Level (ohne AWS) |

### Ursache

`table.meta.client` (Resource-Client) wendet die Dokument-Transformation
auf bereits explizites DynamoDB-JSON an:

| Client | `workId` auf der Leitung |
| --- | --- |
| Resource (bisher) | `{"M":{"S":{"S":"work-..."}}}` |
| Low-Level (jetzt) | `{"S":"work-..."}` |

Deshalb lehnte DynamoDB die Fence-`ConditionCheck` mit
`ValidationError` ab (Cancellation-Reasons Index 0, Index 1 `None`).

### Verhalten

- Index 0 `ConditionalCheckFailed` -> Fence-Ablehnung,
  `WorkEnqueueError`, kein Duplicate-Pfad.
- `ValidationError` / `TransactionConflict` -> `WorkEnqueueError`,
  fail closed ohne SQS-Send, Marker oder bare Row.
- Nur ein Put-Condition-Failure (Index 1) erreicht die
  Duplicate-/Reuse-Pruefung; `_reuse_problem()` bleibt strikt.
- `CancellationReasons` werden ausschliesslich als sichere
  `{index, code}`-Paare geloggt.

## 2. Tests (erneut bestaetigt)

```text
tests/test_work_queue.py
tests/test_dispatch_ingress_lambda.py
tests/test_agent_order_dispatch_e2e.py
tests/test_analysis_ecosystem_wiring.py
tests/test_mo_dispatch_handoff.py
tests/test_ris_dynamodb_marshalling_offline.py
-> 69 passed in 1.14s
```

## 3. Bundles (finaler Code)

| Bundle | SHA-256 | Base64-Quellhash |
| --- | --- | --- |
| Agent (`terraform/lambda.zip`) | `cf0958a6a9b95f95ad84e0a77b08ebb8d950948944ab0b7030601580a72ef304` | `zwlYpqm5X5WthOCnewjruNlQlIlEqwtwMGAVgKcu8wQ=` |
| Analysis (`terraform/analysis-lambda.zip`) | `2f74cab915fdb0ca909ff64c47b786d58cc140a5fc31e34d26f10002b98c1346` | `L3TKuRX9sMqQn/ZMR7eG1YzBQKX8MeNNJvEAArmME0Y=` |

Der Test-Pin entspricht beiden Hashes; der Plan erwartet exakt dieselben
Base64-Quellhashes.

## 4. Gespeicherter Plan

| Feld | Wert |
| --- | --- |
| Datei | `C:\tmp\ris-dev2-workitem-persistence-fix-16.tfplan` |
| SHA-256 | `2dacb48de56fb014a529fb868b436d1a86e76ccfdf771b942b5d3d354285ed57` |
| Groesse | 252 638 Bytes |
| Diff | **0 Add / 3 Change / 0 Destroy / 0 Replace** |
| Ressourcen | `module.agent_transport[0].aws_lambda_function.dispatch_ingress`, `module.analysis_runtime.aws_lambda_function.analysis[0]`, `module.lambda.aws_lambda_function.agent` |
| Geaenderte Attribute | ausschliesslich `source_code_hash` + `last_modified` |
| Analysis-Env | `ANALYSIS_SYNTHETIC_MODE=true` |
| Terraform | CLI 1.17.0, Plan-Format 1.2 |
| Drift | keine (`resource_drift` leer) |
| State | Serial **74**, Lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |

Der Plan passt zum finalen Code: die im Plan erwarteten
`source_code_hash`-Werte sind byte-gleich mit den aktuellen Bundles.
Plan und State wurden read-only geprueft (Hash, `state pull`,
`show -json`).

## 5. S3-State-Version (verbindlicher AWS-Wert)

`aws s3api head-object` auf
`ris-dev2-tf-state-dev` / `env:/ris-dev2/dev/terraform.tfstate`:

| Feld | Wert |
| --- | --- |
| VersionId | `d24K7fWhqup_DQtI_PNDl85DoML9fpE.` |
| LastModified | `2026-11-26T08:42:26+00:00` |

Damit ist die im Work State kursierende Schreibweise mit zusaetzlichem
`L` (`...PNDlL85...`) falsch. Verbindlich ist
`d24K7fWhqup_DQtI_PNDl85DoML9fpE.`; die Angabe im Bericht
`RIS-DEV2-PERSISTENCE-FIX-16.md` wurde auf diesen Wert korrigiert.

## 6. AWS-Zustand (read-only, 2026-11-26T09:22:49Z)

| Pruefung | Ergebnis |
| --- | --- |
| Alte Order `ord_676668...` | `PENDING`, unangetastet |
| Altes WorkItem `work-eb1185...` | weiterhin nur `workId` + `enqueuedAt` |
| Neue Order `ord_a566f4...` | `PENDING`, Dispatch `SENT`, kein Processing |
| Neues WorkItem | 0 |
| Dispatch-Queue | 0 sichtbar / 0 in-flight |
| Dispatch-DLQ | **1** (automatische Retries erschoepft; nicht gelesen, nicht redriven) |
| Work-Queue | 0 / 0 |
| Work-DLQ | 1 (alte Nachricht unveraendert) |
| Results-Queue / DLQ | 0 / 0 |

Die Verschiebung der Dispatch-Nachricht in die Dispatch-DLQ erfolgte
durch die automatischen Lambda-/SQS-Retries, ohne manuellen Eingriff.

## 7. Grenzen

Kein Apply, kein Redrive, keine Order, keine Datenkorrektur, kein
Cleanup, kein neuer Grant, kein Main-Merge. Beide Orders und das
beschaedigte WorkItem bleiben unveraendert; die Dispatch-DLQ wird nicht
angeruehrt.

## 8. Nachster Schritt

Separate Freigabe fuer genau den Plan `2dacb48d...` (0/3/0). Nach dem
Apply: Verifikation der drei Lambdas; fuer den E2E danach eine eigene
Freigabe fuer genau eine neue Order (Fenster bis
`2026-11-26T17:40:28Z`).
