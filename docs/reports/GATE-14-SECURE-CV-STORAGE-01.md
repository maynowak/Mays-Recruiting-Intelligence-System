# GATE-14 — Secure CV & Document Storage Foundation

STATUS: GREEN

- Date/Time: 2026-10-03 UTC
- Branch + HEAD: main + Gate-14-Commits (s. Git)
- MO-Stand: 0 Änderungen. Gates 5–13A unangetastet (nur Handler/TF-Config im Scope + 2 Handler-Bugfixes).
- Scope: privater Dokumenten-Storage (S3+Presign+Isolation). KEIN Parsing/OCR/ATS/Matching, KEIN Backup/Restore, KEINE Jobsuche.
- Classification: GREEN (alle Bereiche; Backup/Restore explizit OPEN/separat)
- Terraform/AWS: validate GREEN; gezielt 5 created + Policy-Update + Env/Routen; No-Op leer; 0 destroys
- Git: Commits pro Bereich (s. Git); Repo clean
- Files Changed: TF (documents-Modul neu, main, lambda-Vars/Policy/Env), `lambda/documents.py` (neu), `lambda/handler.py` (Routen+Handler+2 Fixes), `lambda/build_zip.py` (documents im Bundle), `tests/test_secure_documents.py` (neu, 11), Docs (Arch/API), Reports
- Open: Backup/Restore (separat); Mail-Inbox/lambda.zip/Defekte (bekannt); regionaler Presign-Endpoint als Fix dokumentiert
- Risks: keine neuen (synthetische Daten, gelöscht; Secrets geschreddert)
- Next: Secure-Backup-Gate (separat) — danach HARD STOP-Vorgabe beachten
- Resume Point: nach Commit HARD STOP

## Discovery (Phase 0, getan vor Mutation)

EXISTIERT/WIEDERVERWENDBAR: Data-Bucket-Muster, Lambda-s3-Policyform, JWT/Authorizer/Routen, Gate-12-Identity, Trail (Mgmt), Logs/Alarme, Installer-Targeted-Flow, 338er-Suite. FEHLT: Dokumenten-Bucket, Key-Schema, Presign-Endpunkte, Policy, Env. NICHT ANFASSEN: MO, Data-Bucket, Trail, bestehende Policies, Pool/Client. Key-Schema `tenant/{t}/users/{sub}/documents/{uuid}`; Presigned PUT/GET/DELETE (900s, keine Creds); Object-Data-Events AUS (Kosten); kein DDB-Metastore.

## Storage/Identität/Upload/Read/Delete/IAM/Security (A–G, live belegt)

- Bucket `mays-ris-dev-documents` (Versioning Enabled, PAB 4×true, SSE AES256, KEINE Policy) — getrennt vom Data-Bucket.
- Keys servergebaut (sub+Tenant aus JWT; Spoof ignoriert; Regex-Guard; kein PII).
- POST → Presigned-PUT (Allowlist pdf/msword/docx/txt) → PUT 200 → GET → Presigned-GET → Bytes identisch (AES256-Objekt).
- B (fremder Tenant): GET/DELETE → 404. A DELETE → 200 → GET 404 (Delete-Marker, HeadObject 404). Unsigned GET → 403. Traversal (`..%2F`) → denied.
- IAM live: Put/Get/Delete nur `.../tenant/*` + ListBucket (Least Privilege).
- TLS via API-GW + S3-HTTPS; keine Secrets/Tokens in Code/Logs (Log-Grep 0); keine CV-Persistenz ausser Objekt; keine Passwörter (Cognito).

## CloudTrail/CloudWatch (H/I)

- Trail: Mgmt-Events (All, ohne Data-Resources) — Bucket-Policy-Änderungen etc. auditierbar; Objekt-Data-Events bewusst AUS (dokumentiert, kostenbewusst).
- Watch: Fehler via bestehendem lambda-errors-Alarm + Logs (ohne Inhalte/Secrets); keine neue Alarm-Flut.

## Handler-Befunde (behoben, eigene Dateien)

1. Presign-Endpoint global → 307 killt SigV4 → regionaler Endpoint (Fix + Test).
2. routeKey-Template statt echtem Pfad (`{docId}`) → pathParameters-zuerst (Fix).

## Tests (11 + Suite)

Neu 11 (Key-Schema, Presign-Expiry/Allowlist, 404-Semantik, Delete, Unauth, Spoof, Endpoint-Guard). Suite **360 passed** + 8 Skip (live-gated), 4 pre-existing + 1 Collection klassifiziert. Installer/Validate GREEN.

## Live E2E (synthetisch, 2 Tenants)

A (tenant-a): Upload-URL → PUT 200 → Read-URL → Bytes ok → DELETE 200 → 404. B (tenant-b): alles 404. Cleanup: User + Objekte gelöscht (Bucket leer verifiziert), Secrets geschreddert, Pool leer.

## Backup/Restore (explizit OPEN)

Gate 14 sichert: privat + verschlüsselt + versioniert + isoliert + auditierbar (Mgmt). NICHT getestet: Restore-Prozedur, Cross-Region, Lifecycle/Retention-Policy, Point-in-Time. Separates Gate nötig.

## Checkpoint

| Bereich | Ergebnis |
|---|---|
| Discovery | GREEN |
| S3 Storage | GREEN |
| Encryption | GREEN (AES256 Objekt+Bucket) |
| Public Access Protection | GREEN (PAB+403) |
| Upload | GREEN (200 + Allowlist) |
| Download | GREEN (Roundtrip identisch) |
| Delete | GREEN (200→404) |
| User Isolation | GREEN |
| Tenant Isolation | GREEN |
| IAM | GREEN (Least Privilege live) |
| CloudTrail | GREEN (Mgmt; Data-Events OPEN-dokumentiert) |
| CloudWatch | GREEN (keine Inhalte, bestehende Struktur) |
| Tests | GREEN (11 + 360) |
| Live AWS E2E | GREEN |
| Installer | GREEN (gezielt + No-Op) |
| Documentation | GREEN |
| Git | GREEN (folgt) |
| Backup/Restore | OPEN (separat) |

**GREEN. HARD STOP.**
