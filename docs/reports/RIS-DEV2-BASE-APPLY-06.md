# RIS-DEV2-BASE-APPLY-06

**Datum:** 2026-11-25
**Branch / Baseline:** `feature/ris-analysis-integration-07` / `97d4921d315951f5f8d836c4f4f354edac8e393c`
**MO-Pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`
**Status:** **BASE APPLIED — LIVE VERIFIED**

## 1. Freigabe und Preflight

Ausdrückliche Freigabe: **nur** der gespeicherte Basis-Plan, genau einmal.
Alle Checks unmittelbar vor dem Apply: **PASS (22/22)**.

| Prüfung | Ergebnis |
| --- | --- |
| Branch / HEAD / Remote | `97d4921…`, identisch |
| STS-Konto / Region | `262370457690` / `eu-central-1` |
| Workspace / Backend | `ris-dev2` / S3 `ris-dev2-tf-state-dev`, `dev/terraform.tfstate`, Prefix `env:` |
| State / S3 | Lineage `a0bd361d…`, Serial **69**, Version `21V4l…`, `2026-11-22T11:52:56Z` |
| Lock | keiner |
| Plan | `C:\tmp\ris-dev2-base-04.tfplan` |
| SHA-256 | `9b1e5a66384b593885d4f10061f7d55cbbcb91af04aa60e4f3091fc52a1f613c` |
| Diff | 2 Add / 8 Change / 0 Destroy / 0 Replace |
| Terraform | 1.17.0 |
| Rollback | 7 ZIPs + Configs + Manifest, alle Hashes gegen `CodeSha256` verifiziert |

## 2. Apply

```text
cd terraform
terraform apply -auto-approve -no-color C:\tmp\ris-dev2-base-04.tfplan
-> exit 0
Apply complete! Resources: 2 added, 8 changed, 0 destroyed.
```

Es wurde **kein** neuer Plan erzeugt; `-auto-approve` bestätigte ausschließlich
den gespeicherten Plan. Log: `C:\tmp\apply_base06.log`.

| Ergebnis | Wert |
| --- | --- |
| Adds / Changes / Destroys | **2 / 8 / 0** |
| State | **69 → 71**, Lineage unverändert |
| S3-State | Version `9Q1_MK4.XTJoF6upnr6XHCW3j0ZhH7xW`, `2026-11-25T17:25:44Z` |
| Ressourcen | 288 Blöcke; 274 Managed-Instanzen, 17 Data-Instanzen |
| Fehler/Warnungen | keine Fehler; nur die vorbestehende `dynamodb_table`-Deprecation |

## 3. Live-Verifikation (read-only)

| Prüfung | Ergebnis |
| --- | --- |
| Katalog `analysis-agent` | ACTIVE, `capabilities=["analysis.run"]`, v1.0.0, python3.14 |
| Route `POST /v1/apiprofiles/{apiProfileId}/binding` | vorhanden, `AuthorizationType=JWT`, Authorizer `0iqec5` (`ris-dev2-dev-jwt-human`), Issuer `…/eu-central-1_OYN9QiHc5`, Audience `5jg…` |
| Analysis-IAM-Policy | genau zwei Statements, beide nur `dynamodb:GetItem` (PartnerProfiles-Tabelle, WorkItems-Tabelle); kein Query/Scan/Write, kein Orders-ARN |
| `ris-dev2-dev-agent` | `mcRPFOT8…` ✔ |
| `ris-dev2-dev-agent-dispatch-ingress` | `mcRPFOT8…` ✔ |
| `ris-dev2-dev-analysis` | `WDBpUPbe…` ✔ |
| `ris-dev2-dev-orders-reader` | `YQAE9urj…` ✔ |
| `ris-dev2-mays-orders-handler` | `qnDqqhy2…` ✔ |
| `ris-dev2-mays-orders-sqs-worker` | `qnDqqhy2…` ✔ |
| `ris-dev2-mays-orders-agent-result-consumer` | `qnDqqhy2…` ✔ |
| Analysis-Env | 8 Synthetic-Keys vorhanden, `MODE=false`, alle Identitäten leer, `CONSENT/NOTICE=false` |
| Cognito | Pool `OYN9…` unverändert: 0 User, dieselben 2 Clients |
| CloudFront / DNS | 2 Distributions unverändert; 0 Hosted Zones; **keine** CloudFront-/Route53-/Cognito-Write-Events im Apply-Fenster |
| Lock | keiner |

Die Route war beim ersten Read nicht in der Default-Seite von `get_routes`;
mit Pagination vollständig gefunden (75 Routen). Das war kein Fehler.

## 4. Nicht ausgeführt (Freigabegrenzen eingehalten)

Keine Cognito-User oder App-Clients, keine API-Profile, Partner-Anwendungen,
Offers oder Entitlements, keine Synthetic-Aktivierung, kein weiterer Plan,
kein Rollback, kein Main-Merge. Der Rollback-Satz bleibt ungenutzt unter
`C:\tmp\ris-dev2-rollback-base04\`.

## 5. Nächster Schritt

Phase B benötigt eine **eigene** AWS-Write-Freigabe. Reihenfolge unverändert:
Cognito-User → Profil (ACTIVE) → dedizierter App-Client → Partner-Anwendung →
Bind (Issuer aus verifizierter Konfiguration) → Offer/Grant → Identitätskontext
prüfen. Danach folgt ein separater `mode=true`-Canary-Plan (Phase C).
