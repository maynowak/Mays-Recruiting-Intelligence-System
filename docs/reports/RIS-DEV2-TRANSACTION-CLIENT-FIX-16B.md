# RIS-DEV2-TRANSACTION-CLIENT-FIX-16B

**Datum:** 2026-11-26  
**Branch:** `feature/ris-analysis-integration-07`  
**Baseline:** `c41d2405729764578f522e2d828aed315ce362bb`  
**AWS:** `262370457690` / `eu-central-1` / Workspace `ris-dev2`  
**Status:** **READY FOR FIX-16B APPLY APPROVAL**  
**Grenzen:** kein Apply, Redrive, neue Order oder sonstige Ressourcen-/Datenmutation

## 1. Fix-16B

In `agents/runtime/work_queue.py` darf der Duplicate-/Reuse-Pfad nach einer
`TransactionCanceledException` nur bei exakt diesen CancellationReasons
fortgesetzt werden:

```text
index 0: None
index 1: ConditionalCheckFailed
```

Unbekannte, leere, fehlende, falsch indizierte oder anderweitig abweichende
Reasons enden fail-closed mit `WorkEnqueueError`; kein SQS-Send und kein
Marker-Update. `CancellationReasons` werden weiterhin nur als sichere
Index-/Code-Paare geloggt. Ein direktes
`ConditionalCheckFailedException` bleibt als separater Fallback für den
Duplicate-/Reuse-Check erhalten.

## 2. Tests

Fokussierte Regression-Suite erneut ausgeführt:

```text
73 passed in 0.98s
```

Enthalten sind WorkQueue, Dispatch-Ingress, Agent-Order-Dispatch-E2E,
Analysis-Wiring, Mays-Orders-Handoff und Offline-Boto3-Marshalling.
Neue Fälle decken unbekannte Reasons, leere Reasons, fehlenden Code,
zulässige Put-Duplikat-Reasons und direkten
`ConditionalCheckFailedException`-Fallback ab.

## 3. Bundle-Rebuild

| Bundle | SHA-256 |
| --- | --- |
| Agent (`terraform/lambda.zip`) | `8ec50a61408d28efb2b85ff6c83b05dd0ee6075b9b46081ef16d649793cc6383` |
| Analysis (`terraform/analysis-lambda.zip`) | `276b4e4420272167dd32c590d6dbabed4008724a7091e4d86504d5444fe26b10` |
| Reader (unverändert) | `610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b` |

Der Wiring-Test pinnt die neuen Agent- und Analysis-Hashes.

## 4. Neuer backend-gebundener Plan

| Feld | Wert |
| --- | --- |
| Datei | `C:\tmp\ris-dev2-transaction-client-fix-16b.tfplan` |
| SHA-256 | `43ca49436dac5f0e0f23bcf2c0e4171c034e7f9f380947dbfb8cdf8e9c0af6bf` |
| Größe | 250 322 Bytes |
| Diff | **0 Add / 3 Change / 0 Destroy / 0 Replace** |
| Ressourcen | Agent, Dispatch-Ingress, Analysis |
| Attribute | ausschließlich `source_code_hash` + `last_modified` |
| Synthetic-Modus | `ANALYSIS_SYNTHETIC_MODE=true` |
| Drift | keine |
| State | Serial **74**, Lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |

`terraform show -json` bestätigte, dass die Plan-Quellhashes exakt den
neu gebauten Bundles entsprechen:

| Bundle | Base64-Quellhash im Plan |
| --- | --- |
| Agent + Dispatch-Ingress | `jsUKYUCNKO+yuF/2yDsF3Q7mB1ubRgge8W1kl5PMY4M=` |
| Analysis | `J2tORCAnIWfdMsWQ1tur7UAIckpwkeTYZQTVRE/iaxA=` |

## 5. Preflight / AWS-State

Vor dem Planlauf verifiziert: STS-Konto `262370457690`, CLI-Region
`eu-central-1`, Workspace `ris-dev2`, State Serial/Lineage wie oben.
S3-Backend-Key: `env:/ris-dev2/dev/terraform.tfstate`.

Die explizit freigegebene, übliche temporäre DynamoDB-State-Lock-Operation
für `terraform plan` war der einzige AWS-seitige Write-Vorgang. Es gab keinen
Apply oder sonstigen AWS-Eingriff. S3-State-Version blieb davor und danach:

```text
VersionId: d24K7fWhqup_DQtI_PNDl85DoML9fpE.
LastModified: 2026-11-26T08:42:26+00:00
```

## 6. Commits

| Commit | Inhalt |
| --- | --- |
| `23d51b70667cecc244e40260319ec467b49ca7d9` | Fail-closed Klassifikation + Regressionstests |
| `dca6c5657b413ce16afe890d01773a25d7a4d3c7` | Neue Bundle-Pins nach Rebuild |

Beide Commits wurden auf `feature/ris-analysis-integration-07` gepusht.
Bericht und Auditlog werden separat committed.

## 7. Nächster Schritt

Separate Apply-Freigabe für genau den Plan
`43ca49436dac5f0e0f23bcf2c0e4171c034e7f9f380947dbfb8cdf8e9c0af6bf`.
Kein Apply wurde ausgeführt.
