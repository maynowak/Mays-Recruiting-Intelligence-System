# RIS-DEV2-INGRESS-IAM-APPLY-11

**Datum:** 2026-11-26
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `87c218ac7cdeae4bb09b0963adb5eacf3cb6876d`
**AWS:** `262370457690` / `eu-central-1` / `ris-dev2`
**Status:** **INGRESS IAM APPLIED — LIVE VERIFIED**

## 1. Preflight (PASS)

| Prüfung | Ergebnis |
| --- | --- |
| HEAD / STS / Region / Workspace | `87c218a…`, `262370457690`, `eu-central-1`, `ris-dev2` |
| State | Lineage `a0bd361d…`, Serial **72**, kein Lock |
| S3-State | Version `21AxFw…`, `2026-11-25T19:08:55Z` |
| Plan | `C:\tmp\ris-dev2-ingress-iam-fix-10.tfplan` |
| SHA-256 | `41d4fdd7929ab3f7b7ff6fcac8787c78c225d7403a92e2cf57877f3ca3f846b0` |
| Diff | 0 Add / 1 Change / 0 Destroy; nur Ingress-IAM-Policy |
| Aktionen | exakt fünf inkl. `ConditionCheckItem`, kein `TransactWriteItems` |
| Synthetic-Modus | `true` |

## 2. Apply

```text
terraform apply -auto-approve -no-color C:\tmp\ris-dev2-ingress-iam-fix-10.tfplan
→ exit 0
Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

| Ergebnis | Wert |
| --- | --- |
| State | **72 → 73**, Lineage unverändert, 288 Blöcke |
| S3-State | Version `5UJcbUIuexOZ9jwgExAcgUgh2HIBuoaq`, `2026-11-26T06:37:04Z` |

## 3. Live-Verifikation

| Prüfung | Ergebnis |
| --- | --- |
| `WorkItems`-Aktionen | `GetItem`, `PutItem`, `UpdateItem`, `Query`, **`ConditionCheckItem`** |
| Resources | unverändert: Tabelle + `index/*` |
| `TransactWriteItems` | **nicht** gesetzt |
| Policy-Diff | nur `WorkItems.Action`; alle anderen Statements/Attribute identisch |
| Rollen-Policies | weiterhin 4 |
| Analysis-Lambda | `MODE=true`, Code `WDBpUPbe…` unverändert |
| Analysis-IAM | weiterhin nur `dynamodb:GetItem` |
| Testidentität/Entitlement | gültig |
| Order `ord_676668…` | unverändert `PENDING`, Dispatch `SENT` |
| Dispatch-DLQ | unverändert 1 Nachricht; Work-Queue/DLQ 0 |
| CloudWatch | keine neuen Ingress-`ERROR`-Events nach dem Apply |

## 4. Nächster Schritt (separate Freigabe)

Der IAM-Fix ist live. Für den E2E ist entweder ein **DLQ-Redrive** der einen
Nachricht oder eine **neue synthetische Order** nötig — beides nicht
freigegeben. Das Testfenster endet **2026-11-26T17:40:28Z**; danach wären ein
neuer Grant und ein neuer Plan erforderlich.

## 5. Grenzen eingehalten

Kein DLQ-Redrive, keine neue Order, kein Cleanup, kein weiterer Terraform-Apply,
kein neuer Grant, kein Main-Merge. Nach dem Apply nur read-only Prüfungen.
