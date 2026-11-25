# RIS-DEV2-LIVE-COMPLETION-05 — Phase A Preflight

**Datum:** 2026-11-25
**Branch / Baseline:** `feature/ris-analysis-integration-07` / `1d908a0aa21920a1d6fc42572b91c5af8ba04759`
**MO-Pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`
**Status:** **PREFLIGHT PASS — AWAITING EXPLICIT BASE APPLY APPROVAL**
**Modus:** read-only; kein Apply, keine AWS-Mutation, kein State-Write

## Ergebnis

Der gespeicherte Basis-Plan ist unverändert, der State ist unverändert, und die
sieben aktuell deployten Lambda-Artefakte sind hash-verifiziert gesichert. Es
fehlt ausschließlich die ausdrückliche Freigabe für den Apply.

## 1. Identität und Plan

| Prüfung | Ergebnis |
| --- | --- |
| Branch / HEAD / Remote | `feature/ris-analysis-integration-07`, `1d908a0…`, identisch |
| AWS-Konto / Region | `262370457690` / `eu-central-1` |
| Workspace | `ris-dev2` |
| Backend | S3 `ris-dev2-tf-state-dev`, Key `dev/terraform.tfstate`, Prefix `env:` |
| State | Lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, Serial **69** |
| S3-State | Version `21V4lPFLRfZO7YLrgBcxlVtFOZb5y8dW`, `2026-11-22T11:52:56Z` |
| Plan | `C:\tmp\ris-dev2-base-04.tfplan` |
| SHA-256 | `9b1e5a66384b593885d4f10061f7d55cbbcb91af04aa60e4f3091fc52a1f613c` |
| Diff | **2 Add / 8 Change / 0 Destroy / 0 Replace** (264 No-op) |
| Terraform / Provider | 1.17.0 / aws 6.67.0, time 0.14.2 |
| Lock | kein aktiver Lock |

Der Plan wurde nicht neu erzeugt; Hash und Diff wurden erneut geprüft.

**Drift:** unverändert die drei bekannten Refresh-Beobachtungen
(`dispatch_ingress.inline_policy`, `analysis.inline_policy`, `analysis.layers`
`null`/`[]`). Beide Rollen sind in `resource_changes` No-op.

## 2. Rollback-Artefakte (gesichert und verifiziert)

Verzeichnis: `C:\tmp\ris-dev2-rollback-base04\` (7 ZIPs + 7 Config-JSONs +
`manifest.json`). Jede ZIP wurde über die presigned `Code.Location`
heruntergeladen und gegen die deployte `CodeSha256` geprüft:

| Funktion | CodeSha256 | Match | Bytes |
| --- | --- | --- | ---: |
| `ris-dev2-dev-agent` | `hXdfaF7aV/vS9J5jUbQPWTAd4BUMY8tnKJ+1wySJcJY=` | ja | 348 733 |
| `ris-dev2-dev-agent-dispatch-ingress` | dito | ja | 348 733 |
| `ris-dev2-dev-analysis` | `Qgv4YQkg4Dho2vjlk6ccKp3nzGN8oAalGS3SgApKDJ4=` | ja | 295 959 |
| `ris-dev2-dev-orders-reader` | `RkuZH3hPDqFNp2H8o1XmdkkPmjmSCdTTwhSRZcJbHE0=` | ja | 22 327 |
| `ris-dev2-mays-orders-handler` | `SN3V5S0HtA/DM7Z+XjT7G2dwHPgjU24gx7KBanigX5Q=` | ja | 30 305 |
| `ris-dev2-mays-orders-sqs-worker` | dito | ja | 30 305 |
| `ris-dev2-mays-orders-agent-result-consumer` | dito | ja | 30 305 |

Die Config-Snapshots enthalten Runtime, Handler, Role, Timeout, Memory,
Architectures, Layers und Environment-Keys. Damit ist ein Rollback durch
erneutes `update-function-code` mit den gesicherten ZIPs möglich, ohne auf
nicht mehr vorhandene Build-Artefakte angewiesen zu sein. **Nicht ausgeführt.**

## 3. Regression (unverändert gültig, nicht neu dupliziert)

| Lauf | Ergebnis |
| --- | --- |
| MO-Suite `db4f9e7` | **240 OK** |
| RIS-Cross-Repo mit `MO_ORDERS_SRC` | **148 passed, 7 subtests**, 0 skipped |
| API-/Profil-/Katalog-/Offer-/Synthetic-Set | **250 passed, 322 subtests** |
| `terraform fmt` / `validate` | PASS |

Vollständige `tests/`-Sammlung bleibt `BLOCKED_ENV` (fehlendes `requests`,
Ledger-Collection) und wird nicht als PASS gewertet.

## 4. Dokumentationskorrekturen

- **`dynamodb:LeadingKeys`:** Die AWS-Dokumentation
  (`specifying-conditions.html`) belegt die Anwendung auch auf `GetItem` und
  andere Einzelitem-Aktionen. Die frühere Aussage in
  `RIS-DEV2-IAM-AUTHORIZATION-01` und
  `RIS-MO-WORKITEM-SECURITY-TEST-GATE-01` war falsch und ist korrigiert. Die
  Bewertung bleibt: Bei dynamischen `workId`/`resourceId`-Schlüsseln ergibt
  `LeadingKeys` keine statische Tenant-/Owner-Grenze.
- **Mays-Orders-Privacy:** `inspect/export/erase` sind implementiert und im
  isolierten Projekt `mays-orders-privacy-test` (separates AWS-Konto) live mit
  synthetischen Daten getestet (`MAYS-ORDERS-PRIVACY-FINAL-EVIDENCE-AND-
  DESTROY-01`, GREEN). Das ist ein wertvoller MO-Nachweis, ersetzt aber nicht
  die RIS-DEV2-Verifikation. Die fehlende `gsi2`-Verknüpfung der DEV2-Reader-
  Zeile ist eine Eigenschaft dieser Installation. Offen bleibt MO-seitig die
  dauerhafte Secret-Verwaltung/Rotation.

## 5. Freigabe-Anforderung

Für Phase A fehlt ausschließlich die ausdrückliche Freigabe, **genau** diesen
Plan (`9b1e5a66…`, 2/8/0) in `ris-dev2` anzuwenden. Nach dem Apply:

- Katalog-Item `analysis-agent`, Route `POST /v1/apiprofiles/{apiProfileId}/binding`,
  IAM-Policy (GetItem only) und die sieben Lambda-Versionen live verifizieren;
- State-Serial und S3-Version dokumentieren.

Phase B (Cognito-User, Profil, Client, Partner, Bind, Offer/Grant) und Phase C
(`mode=true`-Plan + Canary) benötigen jeweils eigene ausdrückliche
AWS-Write-Freigaben.

## 6. Nicht ausgeführt

Kein `terraform apply`, keine Cognito-/DynamoDB-Mutation, keine Provisionierung,
kein State-Write, kein Main-Merge.
