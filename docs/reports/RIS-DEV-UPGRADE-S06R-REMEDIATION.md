# RIS-DEV-UPGRADE-S06-R — Release Gate Remediation

- **Datum:** 2026-11-03
- **Modus:** gezielte Nacharbeit, keine AWS-Mutation, kein Apply
- **Baseline:** `main` @ `ab2aa40` · `240571105849` · `eu-central-1` · Workspace `ris-dev`
- **Entscheidung:** **NO-GO** (unverändert), aber alle vier Blocker sind jetzt **entscheidungsreif** statt unbestimmt.

---

## 1. Executive Summary

| Blocker | Vorher | Nachher |
|---|---|---|
| Cursor-Secret | BLOCKED, unklar was fehlt | **READY FOR AUTHORIZED PROVISIONING** (Vertrag + Anleitung + Verify) |
| Privacy/Legal | BLOCKED, keine Vorlage | **Entscheidungsvorlage mit 7 Feldern**, technisch verifiziert |
| PITR/Recovery | BLOCKED, unbestimmt | **Tabelle je Ressource + getrennter Änderungsumfang** |
| Orders-SQS | BLOCKED, offen | **Handoff mit Soll-Policy, Tests, Rollback** |

Kein Gate wurde ohne Nachweis auf PASS gesetzt. RG-07/09/10/11 bleiben BLOCKED, bis die genannten Verantwortlichen freigeben.

---

## 2. Git-Baseline

| Feld | Wert |
|---|---|
| Branch | `main` |
| HEAD bei Beginn | `ab2aa40` |
| Neue Commits | Report + Handoff (Auditlog) |
| Working Tree | sauber bis auf geschützte fremde Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` |

Keine Codeänderung in diesem Auftrag. Keine fremde Datei berührt.

---

## 3. Cursor-Secret (R1)

### Vertrag

| Feld | Wert |
|---|---|
| AWS-Ressource | Secrets Manager Secret, Typ `SecretString` |
| Namensvorschlag | `ris-dev/applications/cursor-hmac` |
| Account/Region | `240571105849` / `eu-central-1` |
| Inhalt | Zufallswert ≥ 32 Byte, keine Struktur, kein Präfix nötig |
| Verwendung | HMAC-SHA256 über den Base64-Cursor-Payload |
| Konfiguration | ausschließlich ARN in `applications_cursor_secret_arn` |
| Lambda-Env | `RIS_CURSOR_SECRET_ARN` (nur ARN) |
| IAM | bedingte Policy `lambda_cursor_secret`, `secretsmanager:GetSecretValue` auf genau den ARN |
| KMS | bei AWS-managed Key keine Zusatzrechte; bei CMK `kms:Decrypt` auf den Key-ARN |
| Cache | pro Prozess und ARN, keine TTL; Rotation wirkt beim nächsten Cold Start |
| Fail-closed | ARN fehlt, Abruf scheitert oder Wert leer → `RuntimeError` → HTTP 503 |

### Provisionierung (nicht ausgeführt, Freigabe nötig)

1. Freigabe durch den Verantwortlichen dokumentieren.
2. Secret anlegen (Wert nur im Secret, nie im Ticket/Log):
   `aws secretsmanager create-secret --name ris-dev/applications/cursor-hmac --secret-string "$(openssl rand -base64 48)"`
3. ARN notieren und per Installer-Variable setzen: `--var applications_cursor_secret_arn=<arn>` oder im Overlay.
4. Neuen Plan erzeugen → erwartet **+1 IAM-Policy**, sonst unverändert.
5. Verify: `GetSecretValue` durch die Agent-Rolle, Cursor-Issue/Resolve, Neustart-Test (Cache leer).
6. Rollback: ARN entfernen → Policy fällt weg, Pagination fail-closed; Secret für Audit behalten.

### Rotation

- Neue Version (`AWSCURRENT`), alte wird `AWSPREVIOUS`.
- Bestehende Cursor werden ungültig → Client beginnt Liste neu; kein Datenverlust.
- Unterbrechungsfreie Rotation bräuchte zweiten ARN mit Verify-Fallback — **bewusst nicht implementiert** (keine unnötige Komplexität).

**Status: READY FOR AUTHORIZED PROVISIONING.** Gate bleibt BLOCKED bis Provisionierung + Verify.

---

## 4. Datenschutzentscheidung (R2)

### Technische Nachweise (14 Tests, moto 5.2.5)

| Prüfung | Ergebnis |
|---|---|
| Kein Erfolg ohne Deleter | ✅ Step `ok=True`, `affected=0`, keine Löschung |
| Kein Erfolg bei unvollständiger Löschung | ✅ `pending` → `ok=False`, `complete=False` |
| Tenant-übergreifender Zugriff | ✅ nicht erreichbar (Tenant im `userKey`, `ownerKey`-Condition) |
| User-übergreifender Zugriff | ✅ nicht erreichbar |
| Partnerübergreifende Löschung im Tenant | ✅ vollständig |
| Kinddatensätze (HISTORY/COVER/IDEMP) | ✅ mitgelöscht |
| Idempotenz | ✅ zweiter Lauf `(0, False)` |
| Globale Flags | ✅ alle `false` (8 Flags unverändert) |

**GSI-Konsistenz:** eventual consistent → ein Lauf ist kein Vollständigkeitsnachweis. Empfehlung: Abschluss erst nach zwei Läufen ohne Treffer plus Receipt; bei aktiven Schreibern Quiescence/F freeze vorher.

### Entscheidungsvorlage

| Entscheidung | Vorschlag | Verantwortlicher | Status |
|---|---|---|---|
| Rechtsgrundlage | Art. 6 Abs. 1 lit. b DSGVO (Bewerbungsverhältnis), Löschung nach Zweckfortfall | Datenschutz/Recht | **offen** |
| Aufbewahrung | je Kategorie (Bewerbung, Anschreiben, Receipts) getrennt; keine Frist ohne Recht | Recht | **offen** |
| Löschverfahren | `/me/erasure` inkl. Applications, zwei Läufe + Receipt | RIS-Betrieb | **technisch bereit** |
| Backup/Restore | Restore gegen Erasure-Receipts abgleichen, vor Online-Nahme | Betrieb + Recht | **offen** |
| Rollenverteilung | RIS = Verantwortlicher für Plattformdaten, Jobsearch = eigene Site | Vertrag/Recht | **offen** |
| Datenschutzhinweise | Löschzusage, Aufbewahrung, Empfänger | Recht | **offen** |
| DSFA | Prüfen (systematische Bewertung Bewerberdaten), Entscheidung dokumentieren | Datenschutz | **offen** |

Keine rechtliche Freigabe durch den Commander. **RG-09 bleibt BLOCKED.**

---

## 5. PITR / Recovery (R3)

| Tabelle | Kategorie | PITR IST | Empfehlung | Auswirkung | Freigabe |
|---|---|---|---|---|---|
| `ris-dev-dev-applications` | Bewerbungen, Anschreiben | neu | **ja** | 35 Tage Retention, Kosten gering | Recht + Betrieb |
| `ris-dev-dev-partner-profiles` | Profil-/CV-Metadaten | neu | **ja** | dito | Recht + Betrieb |
| `ris-dev-dev-privacy-receipts` | Datenschutznachweise | neu | **ja** | Aufbewahrung muss definiert sein | Recht |
| `ris-dev-dev-erasure-operations` | Löschoperationen | neu | ja | Nachweisbarkeit | Betrieb |
| `ris-dev-dev-upload-ticket-ledger` | Upload-Nachweise | neu | ja | Betrieb | Betrieb |
| `ris-dev-dev-s3-erasure-phases` | Löschphasen | neu | optional | kurzfristig | Betrieb |
| `ris-dev-dev-upload-cutover` | Cutover-Steuerung | neu | optional | kurzfristig | Betrieb |
| `ris-dev-dev-user-profile` | personenbezogen | DISABLED | **ja** | 35 Tage | Recht |
| `ris-dev-dev-credentials` | Sperr-/Hash-Historie | DISABLED | **ja** | 35 Tage | Recht |
| `ris-dev-dev-partner-applications` | Partnerbindung | DISABLED | **ja** | 35 Tage | Recht |
| `ris-dev-dev-jobsearches` | Suchhistorie | DISABLED | **ja** | 35 Tage | Recht |
| `ris-dev-dev-work-items` | Idempotenznachweis | DISABLED | **ja** | 35 Tage | Betrieb |
| `ris-dev-dev-offers` | Geschäftsdaten | DISABLED | **ja** | 35 Tage | Betrieb |
| `ris-dev-dev-api-profiles` | Konfiguration | DISABLED | optional | 35 Tage | Betrieb |
| `ris-dev-dev-entitlements` | Rechte | DISABLED | optional | 35 Tage | Betrieb |
| `ris-dev-dev-agent-state` | Laufzeitzustand | DISABLED | optional | 35 Tage | Betrieb |
| `ris-dev-dev-agent-catalog` | Seeds | DISABLED | nein | reproduzierbar | entschieden |
| `ris-dev-mays-orders` | Orders | ENABLED | unverändert | — | entschieden |

### Getrennter Änderungsumfang (vorbereitet, **nicht** angewendet)

Neue Tabellen (additiv im Create, keine Bestandsdaten):

```hcl
point_in_time_recovery { enabled = true }
```

Bestehende Tabellen (10 Updates, eigener Change-Scope):

```hcl
# je Tabelle, z. B. user_profile
point_in_time_recovery { enabled = true }
```

**Nicht umgesetzt**, weil PITR gelöschte personenbezogene Daten 35 Tage vorhält und damit direkt mit der noch offenen Lösch-/Aufbewahrungsentscheidung kollidiert. Eine Aktivierung vor der Rechtsfreigabe wäre eine stille Retention-Verlängerung.

### Recovery-Verfahren

1. Restore mit `restore-table-to-point-in-time` → **neue** Tabelle.
2. Integritätsprüfung (Item-Count, Stichproben, GSI-Status).
3. Abgleich gegen Erasure-Receipts; gelöschte Datensätze nicht wieder online nehmen.
4. Cutover nur mit Freigabe; alte Tabelle bis Abschluss behalten.
5. Verantwortlich: RIS-Betrieb; Fehlschlag → neue Tabelle verwerfen, Incident dokumentieren.

**RG-10 bleibt BLOCKED.**

---

## 6. Orders-SQS (R4)

Handoff erstellt: `docs/reports/RIS-DEV-UPGRADE-S06R-ORDERS-SQS-HANDOFF.md`

Kernpunkte: Producer nur `SendMessage`, Consumer nur `Receive/Delete/GetQueueAttributes`, Principal auf zwei Rollen-ARNs, `aws:SourceAccount`-Condition, Negativtest und Rollback beschrieben. Keine Änderung ausgeführt.

**RG-11 bleibt BLOCKED** bis Eigentümerfreigabe oder schriftliche Risikoakzeptanz.

---

## 7. Durchgeführte Änderungen

| Datei | Art |
|---|---|
| `docs/reports/RIS-DEV-UPGRADE-S06R-REMEDIATION.md` | neu (dieser Report) |
| `docs/reports/RIS-DEV-UPGRADE-S06R-ORDERS-SQS-HANDOFF.md` | neu |
| `docs/AI_AUDITLOG.md` | Eintrag |

**Keine Code-, Terraform-, AWS- oder Orders-Änderung.**

---

## 8. Regressionsevidence

| Lauf | Ergebnis |
|---|---|
| `tests/test_application_erasure.py` + `test_application_repository.py` | **14 passed** |
| S06-Gesamtlauf (17 Dateien) | 267 passed (Referenz, nicht wiederholt) |
| Flags | alle 8 Erasure-/Privacy-Flags `false` |

---

## 9. Terraform-Plan

| Feld | Wert |
|---|---|
| Plan | `/tmp/opencode/ris-dev-s06r.tfplan` |
| JSON | `/tmp/opencode/ris-dev-s06r-plan.json` |
| **SHA-256** | **`4dc294738be7d1dd61ac10272fa08fd268094006b3a6f4504d57ab1d89c7f511`** |
| State danach | serial 36, Version `3tey8lIH…` unverändert |

| Aktion | Anzahl |
|---|---:|
| CREATE | 48 |
| UPDATE | 3 |
| DELETE | 0 |
| REPLACE | 0 |
| MOVE | 54 |
| no-op | 167 |
| DRIFT | 1 (berechnetes Cognito-`domain`) |

---

## 10. Geschützte Infrastruktur

RIS/Jobsearch Cognito, Cognito-Domains, CloudFront/OAC, DNS/ACM, Mays-Orders, bestehende Tabellen: **0 Änderungen**, 54 Moves unverändert.

---

## 11. Offene Freigaben

| Gate | Was fehlt | Wer |
|---|---|---|
| RG-07 | Secret anlegen + ARN + Verify | Plattform-Verantwortlicher |
| RG-09 | Rechtsgrundlage, Fristen, Rollen, DSFA | Datenschutz/Recht |
| RG-10 | PITR-Entscheidung + Change-Scope | Recht + Betrieb |
| RG-11 | SQS-Policy-Korrektur oder Risikoakzeptanz | Orders-Eigentümer |

---

## 12. Gate-Matrix

| Gate | Status | Änderung zu S06 |
|---|---|---|
| RG-01…06 | PASS | unverändert |
| RG-07 Cursor Secret | **BLOCKED** | jetzt READY FOR AUTHORIZED PROVISIONING |
| RG-08 Erasure | PASS (technisch) | 14 Tests erneut bestätigt |
| RG-09 Privacy/Legal | **BLOCKED** | Entscheidungsvorlage vorhanden |
| RG-10 PITR | **BLOCKED** | Tabelle + Change-Scope vorbereitet |
| RG-11 SQS | **BLOCKED** | Handoff + Soll-Policy vorhanden |
| RG-12 Regression | PASS | 14 + 267 |
| RG-13 Packaging | PASS | `c3055648…` |
| RG-14 Terraform | PASS | SHA `4dc29473…` |
| RG-15 Deployment | **NO-GO** | 4 Gates offen |

---

## 13. Entscheidung

**NO-GO** für Deployment. Der Auftrag hat die Blocker von „unbestimmt" in „entscheidungsreif mit Verantwortlichem" überführt; keine Freigabe wurde ersetzt.

**CONDITIONAL GO** wäre möglich, sobald RG-07, RG-09, RG-10, RG-11 nachweislich geschlossen sind und ein neuer Plan mit unveränderten Schutzgütern vorliegt.

**STOP nach S06-R. Kein Apply, keine AWS-Mutation, kein Push.**
