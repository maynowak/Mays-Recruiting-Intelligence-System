# RIS-DEV2-PERSISTENCE-APPLY-14

**Datum:** 2026-11-26
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `d6ceb7ad55cd3d349d66262af2f3c37d9fa1e4da`
**AWS:** `262370457690` / `eu-central-1` / `ris-dev2`
**Status:** **PERSISTENCE FIX APPLIED — LIVE VERIFIED**

## 1. Preflight (PASS)

| Prüfung | Ergebnis |
| --- | --- |
| HEAD / STS / Region / Workspace | `d6ceb7a…`, `262370457690`, `eu-central-1`, `ris-dev2` |
| State | Lineage `a0bd361d…`, Serial **73**, kein Lock |
| S3-State | Version `5UJcb…`, `2026-11-26T06:37:04Z` |
| Plan | `C:\tmp\ris-dev2-workitem-persistence-fix-13a.tfplan` |
| SHA-256 | `41fef4bcf4c1c779b20378cbf2899a8e69099f2a0828725c46bc3fc844c582d3` |
| Diff | 0 Add / 3 Change / 0 Destroy; nur agent, dispatch-ingress, analysis |
| Bundles | Agent `71bf3c9d…`, Analysis `7b3c8e6e…`; Plan-Hashes geprüft |
| Modus | `MODE=true`, Identität vollständig |

## 2. Apply

```text
terraform apply -auto-approve -no-color C:\tmp\ris-dev2-workitem-persistence-fix-13a.tfplan
→ exit 0
Apply complete! Resources: 0 added, 3 changed, 0 destroyed.
```

| Ergebnis | Wert |
| --- | --- |
| State | **73 → 74**, 288 Blöcke, Lineage unverändert |
| S3-State | Version `d24K7fWhqup_DQtI_PNDl85DoML9fpE.`, `2026-11-26T08:42:26Z` |

## 3. Live-Verifikation

| Prüfung | Ergebnis |
| --- | --- |
| `ris-dev2-dev-agent` | `cb88nW8g…`, `Successful` |
| `ris-dev2-dev-agent-dispatch-ingress` | `cb88nW8g…`, `Successful` |
| `ris-dev2-dev-analysis` | `ezyObh3l…`, `Successful` |
| reader / MO handler/worker/consumer | unverändert (`YQAE9urj…` / `qnDqqhy2…`), `Successful` |
| Analysis-IAM | weiterhin nur `dynamodb:GetItem` |
| Ingress-WorkItems | weiterhin die fünf Aktionen inkl. `ConditionCheckItem` |
| Analysis-Env | `MODE=true`, Tenant/User/Partner/Issuer/Ablauf exakt, Consent/Notice false |
| Cognito | 1 User, 3 Clients, 7 Gruppen (unverändert) |
| CloudFront / DNS | 2 Distributions, 0 Hosted Zones (unverändert) |
| WorkItem `work-eb1185…` | weiterhin nur `workId` + `enqueuedAt` (unverändert) |
| Order `ord_676668…` | weiterhin `PENDING`, `processing=null` |
| Work-DLQ | 1 (unverändert); Dispatch-DLQ 0; Work-Queue 0 |
| Deployment-Fehler | keine; alle drei Updates `Successful` |

## 4. Nächster Schritt (separate Freigabe)

Der Fix ist live. Die bestehende beschädigte WorkItem-Zeile und die Order
bleiben unverändert. Für den E2E ist der dokumentierte Recovery-Weg nötig:
Work-DLQ-Body prüfen, marker-only-Zeile durch den validierten vollständigen
WorkItem ersetzen (oder gezielt löschen und Dispatch erneut ausführen), dann
einmal redriven — Datenkorrektur und Redrive sind **nicht** freigegeben.
Alternativ neue Order mit neuer WorkId. Das Testfenster endet
**2026-11-26T17:40:28Z**.

## 5. Grenzen eingehalten

Keine Datenkorrektur, kein Redrive, keine neue Order, kein Cleanup, kein
weiterer Apply, kein neuer Grant, kein Main-Merge.
