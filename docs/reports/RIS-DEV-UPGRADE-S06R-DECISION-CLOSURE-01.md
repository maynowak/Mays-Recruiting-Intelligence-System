# RIS-DEV-UPGRADE-S06R-DECISION-CLOSURE-01

**Final Decision Closure & Release Authorization Preparation**

- **Datum:** 2026-11-03
- **Modus:** Decision Closure / Read-only Verification
- **Deployment:** **NOT AUTHORIZED** · **Terraform Apply:** PROHIBITED
- **Ergebnis:** **BLOCKED – DECISIONS PENDING**

---

## 1. Executive Summary

Alle vier offenen Gates sind vollständig beschrieben, aber **keine** Freigabe wurde erteilt. Damit ist der Status unverändert: kein Deployment.

| Gate | Vorher | Nachher | Verantwortlich | Noch offen |
|---|---|---|---|---|
| RG-07 Cursor Secret | BLOCKED | **BLOCKED – AWAITING APPROVAL** | Plattform-Verantwortlicher RIS | Secret anlegen, ARN setzen, Verify |
| RG-09 Privacy/Legal | BLOCKED | **BLOCKED – AWAITING APPROVAL** | Datenschutz/Recht | DEC-03, DEC-04, DEC-05 |
| RG-10 PITR/Recovery | BLOCKED | **BLOCKED – AWAITING APPROVAL** | Recht + RIS-Betrieb | DEC-06, DEC-07, DEC-08 |
| RG-11 Orders-SQS | BLOCKED | **BLOCKED – AWAITING APPROVAL** | Mays-Orders-Eigentümer | DEC-09 oder DEC-10 |
| RG-15 Deployment | NO-GO | **NO-GO** | Release-Verantwortlicher | DEC-11 |

**Tatsächlich erteilte Freigaben: keine.**

---

## 2. Git-/AWS-/State-Baseline

| Feld | Wert |
|---|---|
| Branch | `main` |
| HEAD | `62ae32f` ✅ |
| Working Tree | sauber bis auf geschützte fremde Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` |
| Upstream | 15 lokale Commits voraus, 0 zurück (kein Push erfolgt) |
| AWS | `240571105849`, `arn:aws:iam::240571105849:user/Mayaws` ✅ |
| Region | `eu-central-1` |
| State | `env:/ris-dev/dev/terraform.tfstate`, Version `3tey8lIH…`, serial 36, Lineage `9cec61e5…`, 185 Ressourcen |

Die S06-R-Nachweise sind damit weiterhin gültig: keine Code-, Terraform- oder AWS-Änderung seither.

---

## 3. Relevante S06-R-Evidence

| Dokument | Verwendung |
|---|---|
| `RIS-DEV-UPGRADE-S06-FINAL-RELEASE-GATES.md` | Gate-Matrix, Plan-SHA `6ccb94fe…` |
| `RIS-DEV-UPGRADE-S06R-REMEDIATION.md` | Verträge, Entscheidungsvorlagen, PITR-Matrix |
| `RIS-DEV-UPGRADE-S06R-ORDERS-SQS-HANDOFF.md` | Soll-Policy, Rollen, Tests, Rollback |
| `RIS-DEV-UPGRADE-S05-SECURITY-ERASURE-RECOVERY.md` | Erasure-Architektur, 267 Tests |
| `RIS-DEV-UPGRADE-S06R-DECISION-REGISTER.md` | DEC-01…DEC-11 |

Keine dieser Quellen enthält eine Freigabe.

---

## 4. Cursor-Secret-Entscheidung (RG-07)

### Vertrag (bestätigt)

- Secrets Manager, `SecretString`, ≥ 32 Byte Zufallswert
- Name `ris-dev/applications/cursor-hmac`, Account `240571105849`, `eu-central-1`
- Terraform sieht nur den ARN (`applications_cursor_secret_arn`)
- Lambda-Env `RIS_CURSOR_SECRET_ARN`
- IAM-Policy nur für die Agent-Rolle, nur `GetSecretValue` auf genau diesen ARN
- KMS: AWS-managed Key → keine Zusatzrechte; CMK → `kms:Decrypt`
- Cache pro Prozess; Rotation wirkt beim Cold Start
- Fehlend/unlesbar → fail-closed (503)

### Provisionierungsauftrag (separat autorisierbar)

1. AWS-Identitätsguard (`sts` = `240571105849`).
2. Kollisionsprüfung: `aws secretsmanager describe-secret --name ris-dev/applications/cursor-hmac` muss „not found" liefern.
3. Wert erzeugen: `openssl rand -base64 48` — niemals ausgeben, nur direkt übergeben.
4. Schreiben: `create-secret` mit diesem Wert.
5. ARN ermitteln und in die Installer-Konfiguration übernehmen.
6. IAM prüfen: `GetSecretValue` durch die Agent-Rolle; Negativtest mit fremder Rolle.
7. Verify: Cursor issue/resolve, Neustart-Test, keine Wertausgabe in Logs.
8. Recovery: bei Fehlschlag ARN nicht setzen; Secret löschen nur nach Rücksprache.
9. Freigabeschritt: schriftliche Zustimmung des Plattform-Verantwortlichen.

**In diesem Auftrag wurde kein Secret erzeugt und kein AWS-Zugriff geschrieben.**

**RG-07 bleibt BLOCKED.** Anleitung ≠ PASS.

---

## 5. Datenschutzfreigabe (RG-09)

### Rollenabgrenzung (Vorschlag, nicht entschieden)

- RIS betreibt die Plattform und speichert Bewerbungsdaten → Verantwortlicher für diese Verarbeitung.
- Mays-Jobsearch ist eine eigenständige Site mit eigener Anmeldung → eigene Verantwortlichkeit für ihren Bereich.
- Keine gemeinsame Verantwortlichkeit ohne ausdrückliche rechtliche Prüfung.

### Entscheidungsmatrix

| Feld | Erforderliche Entscheidung | Status |
|---|---|---|
| Verantwortlichkeit | Wer bestimmt Zwecke/Mittel | AWAITING APPROVAL |
| Rechtsgrundlage | Art. 6 DSGVO konkret | AWAITING APPROVAL |
| Aufbewahrung | Fristen je Kategorie | AWAITING APPROVAL |
| Löschung | Zeitpunkt/Voraussetzungen | AWAITING APPROVAL |
| Backups | Restore-Abgleich mit Löschungen | AWAITING APPROVAL |
| Datenschutzhinweise | Inhalte/Zeitpunkt | AWAITING APPROVAL |
| Freigabe | Zuständige Person | AWAITING APPROVAL |

### Abgedeckte Datenarten

Bewerbungsmetadaten, Anschreibentexte, Statushistorien, Profil-/CV-Referenzen, Exporte, Löschoperationen, S3-Dokumente, Backup-/PITR-Daten, technische Logs.

### Technischer Pflichtnachweis (bestanden)

| Prüfung | Ergebnis |
|---|---|
| User-weite Löschung | ✅ |
| Tenant-Isolation | ✅ |
| Partnerübergreifende Löschung | ✅ |
| Kinddatensätze | ✅ |
| Pending-Semantik | ✅ |
| Wiederholbarkeit | ✅ |
| Fehlerbehandlung | ✅ |
| Fehlender Deleter = kein Erfolg | ✅ |
| GSI-Verzögerung | dokumentiert: zwei Läufe + Receipt |
| Globale Flags | alle `false` |

**Technisch verifiziert, rechtlich nicht freigegeben. RG-09 bleibt BLOCKED.**

---

## 6. PITR-/Recovery-Entscheidungen (RG-10)

| Tabelle | Kategorie | IST | SOLL | Zeitraum | RPO/RTO | Status |
|---|---|---|---|---|---|---|
| `ris-dev-dev-applications` | personenbezogen | neu | ja | 35 T (Vorschlag) | 5 min / 1 h | AWAITING APPROVAL |
| `ris-dev-dev-partner-profiles` | personenbezogen | neu | ja | 35 T | 5 min / 1 h | AWAITING APPROVAL |
| `ris-dev-dev-privacy-receipts` | Audit | neu | ja | 35 T | 5 min / 1 h | AWAITING APPROVAL |
| `ris-dev-dev-erasure-operations` | Audit | neu | ja | 35 T | 5 min / 1 h | AWAITING APPROVAL |
| `ris-dev-dev-upload-ticket-ledger` | Audit | neu | ja | 35 T | 5 min / 1 h | AWAITING APPROVAL |
| `ris-dev-dev-s3-erasure-phases` | technisch | neu | optional | 7 T | 15 min / 4 h | AWAITING APPROVAL |
| `ris-dev-dev-upload-cutover` | technisch | neu | optional | 7 T | 15 min / 4 h | AWAITING APPROVAL |
| `ris-dev-dev-user-profile` | personenbezogen | DISABLED | ja | 35 T | 5 min / 1 h | AWAITING APPROVAL |
| `ris-dev-dev-credentials` | personenbezogen | DISABLED | ja | 35 T | 5 min / 1 h | AWAITING APPROVAL |
| `ris-dev-dev-partner-applications` | personenbezogen | DISABLED | ja | 35 T | 5 min / 1 h | AWAITING APPROVAL |
| `ris-dev-dev-jobsearches` | personenbezogen | DISABLED | ja | 35 T | 5 min / 1 h | AWAITING APPROVAL |
| `ris-dev-dev-work-items` | technisch | DISABLED | ja | 35 T | 5 min / 1 h | AWAITING APPROVAL |
| `ris-dev-dev-offers` | Geschäftsdaten | DISABLED | ja | 35 T | 5 min / 1 h | AWAITING APPROVAL |
| `ris-dev-dev-api-profiles` | technisch | DISABLED | optional | 7 T | 15 min / 4 h | AWAITING APPROVAL |
| `ris-dev-dev-entitlements` | technisch | DISABLED | optional | 7 T | 15 min / 4 h | AWAITING APPROVAL |
| `ris-dev-dev-agent-state` | technisch | DISABLED | optional | 7 T | 15 min / 4 h | AWAITING APPROVAL |
| `ris-dev-dev-agent-catalog` | Seeds | DISABLED | nein | — | reproduzierbar | PROPOSED |
| `ris-dev-mays-orders` | Orders | ENABLED | unverändert | — | — | PROPOSED |

**Erasure-Abgleich:** Restore in neue Tabelle, dann Abgleich gegen `erasure-operations`/Receipts; bereits gelöschte Subjekte werden vor Cutover entfernt. Ohne diesen Abgleich kein Cutover.

**Change-Scope (nicht angewendet):** neue Tabellen additiv im Create; bestehende Tabellen als eigener Scope mit 10 Updates. PITR hält gelöschte personenbezogene Daten bis zu 35 Tage — deshalb erst nach DEC-04.

**RG-10 bleibt BLOCKED.**

---

## 7. Orders-SQS-Eigentümer-Handoff (RG-11)

| Entscheidungspunkt | Vorschlag | Status |
|---|---|---|
| Producer | `ris-dev-dev-agent` | PROPOSED |
| Consumer | `ris-dev-mays-orders-sqs-worker-role` | PROPOSED |
| Aktionen | Send vs. Receive/Delete/GetAttributes getrennt | PROPOSED |
| Principal | genau zwei Rollen-ARNs | PROPOSED |
| Cross-Account | nicht erforderlich | PROPOSED |
| Conditions | `aws:SourceAccount=240571105849` | PROPOSED |
| Negativtest | fremde Rolle → `AccessDenied` | PROPOSED |
| Ausfallerkennung | `SendMessage`-403, `ApproximateAgeOfOldestMessage` | PROPOSED |
| Rollback | alte Policy aus Handoff wiederherstellen | PROPOSED |

Keine Änderung an Mays-Orders, Modulen oder Policies. Freigabe durch den Eigentümer fehlt.

**RG-11 bleibt BLOCKED.**

---

## 8. Zentrales Decision Register

Vollständig in `docs/reports/RIS-DEV-UPGRADE-S06R-DECISION-REGISTER.md`.

Zusammenfassung: **11 Entscheidungen, 0 APPROVED, 0 IMPLEMENTED (für diese Gates), 0 VERIFIED.**

| Status | Anzahl | IDs |
|---|---:|---|
| AWAITING APPROVAL | 8 | DEC-01, 03, 04, 05, 06, 07, 08, 09 |
| PROPOSED | 1 | DEC-02 |
| BLOCKED | 2 | DEC-10, DEC-11 |

---

## 9. Offene Genehmigungen

1. Secret-Anlage + ARN + Verify (DEC-01, DEC-02)
2. Rechtsgrundlage, Aufbewahrung, Löschzusage, Rollen, DSFA (DEC-03, DEC-04)
3. PITR je Tabelle + Restore-Verfahren (DEC-06, DEC-07, DEC-08)
4. SQS-Eigentümerkorrektur oder Risikoakzeptanz (DEC-09, DEC-10)

---

## 10. Technische und rechtliche Grenzen

- Technische Tests belegen Verhalten, nicht Zulässigkeit.
- GSI-Eventual-Consistency verhindert einen Ein-Lauf-Vollständigkeitsnachweis.
- PITR verlängert Retention und kollidiert mit Löschfristen.
- Die Jobsearch-Domain-/ACM-/CloudFront-Zuordnung bleibt unangetastet; ACM wird von Account `590490809858` genutzt.
- `orders_lifecycle=managed` und die 54 Moves bleiben unverändert.

---

## 11. Release-Gate-Matrix

| Gate | Status | Grund |
|---|---|---|
| RG-01 Git | PASS | `62ae32f`, Tree sauber |
| RG-02 AWS Account | PASS | `240571105849` |
| RG-03 State Ownership | PASS | Lineage/serial 36/185 |
| RG-04 Cognito Protection | PASS | keine Änderung |
| RG-05 CloudFront/DNS | PASS | keine Änderung |
| RG-06 Orders Protection | PASS | keine Änderung |
| RG-07 Cursor Secret | **BLOCKED** | Secret fehlt |
| RG-08 Erasure | PASS (technisch) | 14 + 267 Tests |
| RG-09 Privacy/Legal | **BLOCKED** | keine Freigabe |
| RG-10 PITR/Recovery | **BLOCKED** | keine Entscheidung |
| RG-11 Orders-SQS | **BLOCKED** | keine Eigentümerfreigabe |
| RG-12 Regression | PASS | historisch |
| RG-13 Packaging | PASS | `c3055648…` |
| RG-14 Terraform | PASS (historisch) | `4dc29473…`, 0/0 |
| RG-15 Deployment | **NO-GO** | 4 Gates offen |

---

## 12. Konkrete nächste Aktionen

| # | Aktion | Voraussetzung | Ergebnis |
|---|---|---|---|
| 1 | Secret anlegen + ARN + Verify | DEC-01 durch Plattform-Verantwortlichen | RG-07 PASS |
| 2 | Rechtsfreigabe dokumentieren | DEC-03/04 durch Datenschutz | RG-09 PASS |
| 3 | PITR-Entscheidungen + Change-Scope umsetzen | DEC-06/07/08 | RG-10 PASS |
| 4 | SQS-Policy korrigieren | DEC-09 durch Eigentümer | RG-11 PASS |
| 5 | Neuen Plan erzeugen + Schutzgüter prüfen | 1–4 abgeschlossen | RG-14 aktuell |

---

## 13. GO/NO-GO

**NO-GO.** Keine Entscheidung wurde erteilt; vier Pflichtgates sind offen.

**READY FOR DEPLOYMENT APPROVAL** ist nicht erreicht und darf nicht behauptet werden.

---

## 14. Voraussetzungen für das kontrollierte Deployment

1. DEC-01…DEC-09 auf `APPROVED`, Maßnahmen `IMPLEMENTED`/`VERIFIED`.
2. Neuer Terraform-Plan gegen State 36+ mit 0 DELETE / 0 REPLACE und unveränderten Schutzgütern.
3. Schriftliche Release-Freigabe durch den Release-Verantwortlichen.
4. Eigener Apply-Auftrag mit identischem Plan-Hash.

**STOP nach S06R-DECISION-CLOSURE-01. Kein Apply, keine AWS-Mutation, kein Push.**
