# RIS-DEV-UPGRADE-S06R — Decision Register

**Stand:** 2026-11-03 · **Release:** `ris-dev` · **Status:** offen
**Regel:** Nur dokumentierte Freigaben erhalten `APPROVED`. Keine Namen, Unterschriften oder Genehmigungen werden erfunden.

| ID | Thema | Entscheidungsvorschlag | Zuständige Person/Rolle | Status | Nachweis |
|---|---|---|---|---|---|
| DEC-01 | Cursor Secret | Secret `ris-dev/applications/cursor-hmac` in `240571105849`/`eu-central-1` anlegen, ARN per `applications_cursor_secret_arn` setzen | Plattform-Verantwortlicher RIS | **AWAITING APPROVAL** | S06R-REMEDIATION §3; Code `jobsearch/application_repository.py`; Variable `terraform/variables.tf:339` |
| DEC-02 | Secret Rotation | Manuelle Rotation: neue Version → `AWSCURRENT`, Cold Start invalidiert Cache, alte Cursor werden ungültig und Clients starten die Liste neu; kein zweiter ARN | Plattform-Verantwortlicher RIS | **PROPOSED** | S06R-REMEDIATION §3; `_SECRET_CACHE` pro Prozess |
| DEC-03 | Datenverarbeitung | RIS als Verantwortlicher für Plattform-/Bewerbungsdaten, Jobsearch als eigenständige Site; Rechtsgrundlage Art. 6 Abs. 1 lit. b DSGVO prüfen und bestätigen | Datenschutz/Recht | **AWAITING APPROVAL** | S06R-REMEDIATION §4 |
| DEC-04 | Aufbewahrung | Getrennte Fristen für Bewerbungsmetadaten, Anschreibentexte, Statushistorien, Profil-/CV-Referenzen, Receipts und Backups; keine Frist ohne Recht | Datenschutz/Recht | **AWAITING APPROVAL** | S06R-REMEDIATION §4 |
| DEC-05 | Erasure | `/me/erasure` inkl. Applications aktivieren (zwei Läufe + Receipt), sobald DEC-03/DEC-04 freigegeben sind | Datenschutz/Recht + RIS-Betrieb | **AWAITING APPROVAL** | 14 Tests PASS; `gsi-user`; `PrivacyErasure._delete_applications` |
| DEC-06 | PITR Kern-Tabellen | PITR für user-profile, credentials, partner-applications, jobsearches, work-items, offers aktivieren; api-profiles/entitlements/agent-state optional; agent-catalog nein | Recht + RIS-Betrieb | **AWAITING APPROVAL** | S06R-REMEDIATION §5; Live-Status 10× DISABLED |
| DEC-07 | PITR neue Tabellen | PITR für applications, partner-profiles, privacy-receipts, erasure-operations, upload-ticket-ledger; optional s3-erasure-phases, upload-cutover | Recht + RIS-Betrieb | **AWAITING APPROVAL** | S06R-REMEDIATION §5; Create-Scope |
| DEC-08 | Recovery/Restore | Restore in neue Tabelle, Validierung, Abgleich gegen Erasure-Receipts, Cutover nur mit Freigabe; alte Tabelle bis Abschluss behalten | RIS-Betrieb | **AWAITING APPROVAL** | S06R-REMEDIATION §5 |
| DEC-09 | Orders-SQS Policy | Principal auf zwei Rollen-ARNs, Aktionen trennen (Send vs. Receive/Delete), `aws:SourceAccount=240571105849` | Mays-Orders-Eigentümer | **AWAITING APPROVAL** | S06R-ORDERS-SQS-HANDOFF |
| DEC-10 | Restrisiko SQS | Befristete Risikoakzeptanz nur schriftlich und namentlich; nicht erteilt | Release-Verantwortlicher | **BLOCKED** | S06R-ORDERS-SQS-HANDOFF §6 |
| DEC-11 | Release Readiness | Freigabe erst nach DEC-01…DEC-09 = APPROVED/VERIFIED und neuem Plan | Release-Verantwortlicher | **BLOCKED** | Gate-Matrix S06R-DECISION-CLOSURE-01 |

---

## Statuslegende

| Status | Bedeutung |
|---|---|
| PROPOSED | Vorschlag dokumentiert, keine Zustimmung |
| AWAITING APPROVAL | Zuständige Stelle muss entscheiden |
| APPROVED | Dokumentierte Freigabe liegt vor |
| REJECTED | Dokumentiert abgelehnt |
| BLOCKED | Entscheidung oder Voraussetzung fehlt |
| IMPLEMENTED | Maßnahme ausgeführt |
| VERIFIED | Ausführung mit Nachweis geprüft |

## Bereits belegte technische Fakten (keine Freigabe)

- Cursor-Secret-Auflösung, IAM-Bedingung und Fail-closed sind implementiert und getestet.
- Erasure ist implementiert, tenant-/user-isoliert, idempotent, pending-fähig; 14 Tests PASS.
- PITR-Status aller 11 bestehenden Tabellen wurde live erhoben.
- SQS-Ist-Policy und Nutzerrollen sind dokumentiert.

Diese Fakten ersetzen **keine** der oben offenen Entscheidungen.
