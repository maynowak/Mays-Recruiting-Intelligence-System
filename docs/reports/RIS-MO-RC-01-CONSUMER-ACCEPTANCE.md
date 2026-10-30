# RIS-MO-RC-01 — CONSUMER ACCEPTANCE REPORT

**Status:** COMPLETE — **RC GO** (isolierte Testinstallation `ris-dev2`; F-03 bleibt Production-Gate)
**Datum:** 2026-10-30
**Pipeline:** BUILD → APPLY → LIVE TEST → DESTROY → CLEAN → DOCUMENTED (real ausgeführt)

---

## 1. Ausgangslage und Scope

Abschluss der Integration des Mays-Orders-AWS Module Builders in Mays-RIS
auf dem aktuell ausgecheckten Branch. Kein neuer Branch, kein Checkout
alter Commits. Bestehende untracked Dateien wurden erhalten und nicht
committet.

| Element | Wert |
|---|---|
| Repository | `C:\Users\DCI-Student\projekte\Mays-Recruiting-Intelligence-system` |
| Branch (Start **und** Ende) | `feature/mo-module-installer-ris-dev2-2026` |
| HEAD bei Sitzungsstart | `f60d8291403357abf3ccb06f77e5f2fd835ff58c` (7 Commits vor Origin, nicht gepusht) |
| MO Module Builder Pin | `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d` (`installer/mays-orders-builder.pinned.json`) |
| AWS Account | `262370457690` |
| Region | `eu-central-1` |
| Workspace | `ris-dev2` |
| AWS-Identität | `arn:aws:iam::262370457690:user/devnemo` (STS-verified) |
| Backend | S3 `ris-dev2-tf-state-dev` + DynamoDB `ris-dev2-tf-lock` (**erhalten**) |
| State-Pfad | `env:/ris-dev2/dev/terraform.tfstate` (workspace_key_prefix `env:`, key `dev/terraform.tfstate`) |

Hinweis zur Isolation: State-Key, Namensprefix (`ris-dev2-*`) und Workspace
trennen diese Installation vollständig von bestehenden `ris-dev`-Ressourcen.
Der State war zu Sitzungsbeginn leer (serial 1, 0 Ressourcen) — die
Installation war ein reiner Create-Lauf, kein Eingriff in fremde Ressourcen.

## 2. AWS Preflight (PASS)

| Prüfung | Ergebnis | Nachweis |
|---|---|---|
| STS GetCallerIdentity → Account `262370457690` | PASS | `02-aws-identity.json` |
| Region `eu-central-1` (aws configure get region) | PASS | `02-aws-identity.json` |
| S3 Backend-Bucket vorhanden (head-bucket, BucketArn) | PASS | `04-terraform-pipeline.txt` |
| DynamoDB Lock-Tabelle ACTIVE, PAY_PER_REQUEST | PASS | `04-terraform-pipeline.txt` |
| State leer (0 Ressourcen), keine Locks bei Start | PASS | `04-terraform-pipeline.txt` |
| Fremde Ressourcen unverändert | PASS (kein Zugriff) | — |

## 3. Build / Deploy

| Schritt | Exit-Code | Ergebnis | Evidence |
|---|---|---|---|
| `terraform init` (Backend-Config via `-backend-config`) | 0 | 21 Module, aws 6.67.0, time 0.14.2 | `04-terraform-pipeline.txt [1]` |
| `terraform workspace select ris-dev2` | 0 | Switched | `04-terraform-pipeline.txt [2]` |
| `terraform plan -out=plan.out` | 0 | **169 add, 0 change, 0 destroy**; kein `must be replaced` | `04-terraform-pipeline.txt [3]`, `../plan-ris-dev2.txt` |
| `terraform apply -auto-approve plan.out` | 0 | Deploy vollständig; 2 Zwischenabbrüche durch 120s-CLI-Timeout, verwaiste State-Locks per `force-unlock` gelöst | `04-terraform-pipeline.txt [4]` |
| `terraform apply -target health_public` (CloudFront + OAC + Bucket-Policy) | 0 | vervollständigt | `04-terraform-pipeline.txt [5]` |
| **Post-Deploy No-Op-Check** `terraform plan -detailed-exitcode` | **0** | "No changes. Your infrastructure matches the configuration." | `04-terraform-pipeline.txt [6]` |

## 4. Live-Integrationstests

Getestet wurde die real deployte Installation (Terraform Outputs: 28,
siehe `../tf-outputs.json`).

| # | Test | Ergebnis | Beleg |
|---|---|---|---|
| T-01 | Cognito User Pool `eu-central-1_uhvqKPR7G` (ris-dev2-dev-users) | **PASS** | `06-live-tests.txt` |
| T-02 | API Gateway `tc1rtdwye1` unauthentifiziert → **401** (JWT-Authorizer greift) | **PASS** | `06-live-tests.txt` |
| T-03 | Lambda `ris-dev2-dev-agent` Invoke `GET /health` → **200** `{"status": "ok", ...}` | **PASS** | `06-live-tests.txt` |
| T-04 | Lambda `ris-dev2-dev-orders-reader` Invoke → 200/HTTP 400 VALIDATION_ERROR (erwartetes Fail-Closed für Bare-Event) | **PASS** | `06-live-tests.txt` |
| T-05 | DynamoDB: 12 Tabellen inkl. `ris-dev2-mays-orders` (ACTIVE) | **PASS** | `06-live-tests.txt` |
| T-06 | SQS: 6 Queues inkl. `ris-dev2-mays-orders-orders-queue` | **PASS** | `06-live-tests.txt` |
| T-07 | Worker-Roundtrip (SendMessage → Verarbeitung → Queue leer) | **PASS** | `08-live-roundtrip.txt` |

**T-07-Nachweis:** Ein eigener Testauftrag wurde in die Orders-SQS gestellt.
Der Worker setzte den DynamoDB-Status `PENDING → CONFIRMED`; anschließend
waren `ApproximateNumberOfMessages` und
`ApproximateNumberOfMessagesNotVisible` jeweils `0`. Vollständiger Nachweis:
`08-live-roundtrip.txt`.

**Wichtiger Vorfall (behoben):** Die Platzhalter-ZIPs enthielten
Orders-Modul-Dateien statt RIS-Handler → beide Lambdas warfen
`Runtime.ImportModuleError`. Reparatur über
`python lambda/build_zip.py --bundle all` (deterministische Bundles:
Agent 61 Dateien, Reader 1 Datei) + In-Place-Update (Plan 0 add / 2 change
/ 0 destroy, Apply Exit 0). Danach T-03/T-04 PASS. → Finding N-RC-01.

## 5. Destroy und Cleanup

| Schritt | Exit-Code | Ergebnis |
|---|---|---|
| `terraform destroy -auto-approve` | 0 | "Destroy complete! Resources: 0 destroyed."; State leer (`03-terraform-state-final.txt`) |

Kontrollierter Rückbau der Restbestände (nur eigene Ressourcen):

1. **S3 `ris-dev2-cloudtrail-262370457690`** — Destroy-Fehler
   `BucketNotEmpty` (CloudTrail-Logs) → Bucket geleert, Destroy
   fortgeführt, Bucket gelöscht (NoSuchBucket verifiziert).
2. **CloudFront** — OAC-Delete blockiert (`OriginAccessControlInUse`).
   Ursache: **4** Terraform-erzeugte Distributionen (CallerReference
   `terraform-*`, identischer Origin `ris-dev2-dev-health-public`),
   entstanden aus den abgebrochenen Apply-Versuchen. Alle 4 disabled
   (Enabled=false) → Status Deployed abgewartet → je Distribution
   `delete-distribution` → `NoSuchDistribution` verifiziert → OAC
   `E3N0SKHULOX36P` gelöscht → `NoSuchOriginAccessControl` verifiziert.
   → Finding N-RC-03.

**AWS-Restbestand-Verifikation (frisch nach Destroy, Exit-Codes 0):**

| Kategorie | Ergebnis |
|---|---|
| Lambda-Funktionen `ris-dev2*` | 0 |
| Cognito User Pools | 0 |
| DynamoDB | nur `ris-dev2-tf-lock` (Backend, erhalten) |
| SQS | 0 |
| API Gateway | 0 |
| IAM Rollen / Customer-Managed Policies | 0 / 0 |
| CloudWatch Log-Groups / Alarms / Dashboards | 0 / 0 / 0 |
| EventBridge Rules / CloudTrail | 0 / 0 |
| CloudFront Distributions / OAC | 0 / 0 |
| S3 | nur `ris-dev2-tf-state-dev` (Backend, erhalten) |
| State-Objekt | `env:/ris-dev2/dev/terraform.tfstate` (leerer Post-Destroy-State) |

→ **CLEAN bestätigt.** Backend-Bucket und Lock-Tabelle bleiben erhalten.

**Zweiter Abschlusslauf zur Nachholung von T-07:** Apply Exit 0 (169 add),
Post-Apply-No-Op Exit 0, Worker-Roundtrip PASS. Der erste Destroy-Aufruf
endete wegen eigener CloudTrail-Logs mit Exit 1 (`BucketNotEmpty`); der Bucket
wurde ausschließlich für diese Testinstallation geleert, der Destroy danach
mit Exit 0 wiederholt. Die unabhängige Prüfung in `09-cleanup-roundtrip.txt`
bestätigt erneut: keine `ris-dev2`-Laufzeitressourcen, Backend unverändert.

## 6. Findings

| ID | Beschreibung | Status |
|---|---|---|
| F-01 | IAM Worker-Boundary: kontospezifischer ARN-Default, Portabilität über Konten ungeprüft | **OPEN** (vorbestehend, außerhalb Scope) |
| F-03 | MO-SQS-Policy `Principal="*"` ohne Conditions | **OPEN** — bleibt **Production-Gate** (für isolierte Testinstallation akzeptiert) |
| N-RC-01 | Platzhalter-Lambda-ZIPs ohne RIS-Handler → ImportModuleError; behoben via `build_zip.py --bundle all` + `filename`-Binding auf `lambda/dist/orders-reader.zip` | **RESOLVED** (Binding in lokalem tfvars dokumentiert) |
| N-RC-02 | 120s-Timeout-Abbrüche hinterlassen verwaiste DynamoDB-State-Locks → `terraform force-unlock` erforderlich | **DOKUMENTIERT** (Prozessverhalten, nicht Infrastrukturdefekt) |
| N-RC-03 | Abgebrochene Applies erzeugten 4 doppelte CloudFront-Distributionen (alle Terraform-erzeugt, gleicher Origin) | **RESOLVED** (alle 4 + OAC gelöscht, verifiziert) |
| N-RC-04 | Zweiter Destroy-Versuch traf auf eigene nichtleere CloudTrail-Bucket-Logs | **RESOLVED** (eigener Bucket geleert, Destroy erneut Exit 0) |

## 7. Evidence-Index

| Datei | Inhalt |
|---|---|
| `docs/reports/evidence/RIS-MO-RC-01-2026/01-git-baseline.txt` | Branch, HEAD, Status |
| `docs/reports/evidence/RIS-MO-RC-01-2026/02-aws-identity.json` | STS-Identität |
| `docs/reports/evidence/RIS-MO-RC-01-2026/03-terraform-state-final.txt` | Post-Destroy-State (0 Ressourcen, Workspace ris-dev2) |
| `docs/reports/evidence/RIS-MO-RC-01-2026/04-terraform-pipeline.txt` | Init/Plan/Apply/Destroy-Konsole mit Exit-Codes |
| `docs/reports/evidence/RIS-MO-RC-01-2026/05-aws-cleanup-verification.txt` | Restbestand-Check (frisch) |
| `docs/reports/evidence/RIS-MO-RC-01-2026/06-live-tests.txt` | Live-Tests T-01…T-07 |
| `docs/reports/evidence/RIS-MO-RC-01-2026/07-roundtrip-pipeline.txt` | Zweiter Apply/No-Op/Destroy-Lauf mit Exit-Codes |
| `docs/reports/evidence/RIS-MO-RC-01-2026/08-live-roundtrip.txt` | Echter SQS→Worker→DynamoDB-Roundtrip |
| `docs/reports/evidence/RIS-MO-RC-01-2026/09-cleanup-roundtrip.txt` | Unabhängige Cleanup-Prüfung nach dem zweiten Lauf |
| `docs/reports/evidence/plan-ris-dev2.txt` | Vollständiger Plan (169 add) |
| `docs/reports/evidence/tf-outputs.json` | 28 Terraform-Outputs |

## 8. Git-Commits (dieser Report)

| Commit | Inhalt |
|---|---|
| `7fbe3d5e9faaf9525af497398d25cfdff6e383d4` | Acceptance-Report, erster Apply/Live-Test/Destroy/Cleanup-Lauf, Evidence und AI_AUDITLOG |
| `f60d8291403357abf3ccb06f77e5f2fd835ff58c` | Wrapper-Validierung für den finalen Build erweitert |
| `d1b7594f1ea8fc624b881be0808264c24de7a4bc` | Wrapper-Defekt behoben und MO-Pin aktualisiert |
| lokaler Folgecommit | Zweiter vollständiger Lauf mit T-07 PASS, Cleanup-Evidence und aktualisiertem Report/Auditlog |

Nicht committet (bewusst erhalten, untracked): Scratch-Skripte im
Repository-Root (`apply_*.py`, `fix_*.py`, `check_*.py`, `verify*.py`,
`temp*.txt`, `bootstrap_backend.py` u. a.) sowie lokale Build-Artefakte
(`terraform/plan.out`, `terraform/apply_health.log`,
`terraform/ris-dev2.tfvars`, ZIPs). Keine Secrets gespeichert. Kein Push.

## 9. RC-Entscheidung

**RC GO** für den Consumer-Acceptance der MO-Integration in der isolierten
Testinstallation `ris-dev2`:

- Plan (169 add) → Apply (Exit 0) → Post-Deploy-No-Op (Exit 0)
- Live-Tests: 7 PASS (einschließlich Worker-Roundtrip)
- Destroy Exit 0, AWS-Restbestand unabhängig verifiziert = CLEAN
- Backend (S3 + DynamoDB-Lock) unbeschädigt erhalten

Bedingung: F-03 (SQS-Wildcard-Policy) bleibt blockierend für jede
Produktions- oder Multi-Tenant-Freigabe.

---
*Ende RIS-MO-RC-01 — Consumer Acceptance. Erstellt 2026-10-30.*
