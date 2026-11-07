# RIS-DEV-UPGRADE-S04-B — ApplicationV1 Release Blockers & Deployment Readiness

- **Datum:** 2026-11-03
- **Modus:** Codekorrektur + lokale Regression + Plan-only; **kein Apply, keine AWS-Mutation**
- **Ziel:** `ris-dev` · `mayaws` · `240571105849` · `eu-central-1`
- **Ergebnis:** **YELLOW** — Cursor-Secret sicher implementiert, Plan weiterhin zerstörungsfrei; Erasure-Verdrahtung und Secret-Provisionierung bleiben dokumentierte Deployment-Blocker.

---

## 1. Executive Summary

| Bereich | Ergebnis |
|---|---|
| Cursor-Secret | **implementiert** (Secrets Manager ARN, Cache, fail-closed) |
| Application-Erasure | **BLOCKED** (kein user-weiter Index, keine Rechtsfreigabe, keine lokale Integrationstestbasis) |
| PITR | **Entscheidungsvorlage** erstellt; keine Änderung |
| Orders-SQS | **Risiko bewertet**; Korrektur gehört dem Queue-Eigentümer |
| Regression | **217 passed, 8 skipped** |
| Packaging | reproduzierbar, SHA-256 `0ed0d4df…` |
| Neuer Plan | **0 DELETE, 0 REPLACE**, 48 CREATE, 3 UPDATE, 54 MOVE |
| Plan-SHA-256 | `5fd68662754b5d1f1eb6e8aa9598f7acc32a93a655a9f2f269b1b4815ce71da6` |

---

## 2. Git-Baseline

| Feld | Wert |
|---|---|
| Branch | `main` |
| HEAD bei Beginn | `3b32a76` |
| Neuer Commit | `8e42e6c` (Cursor-Secret) |
| Working Tree | sauber bis auf geschützte fremde Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` |

`moved`-Blöcke aus S04-A (`db0c0c2`) unverändert erhalten.

---

## 3. Cursor-Secret-Verfahren

### Umsetzung

`jobsearch/application_repository.py` löst den HMAC-Schlüssel jetzt in dieser Reihenfolge auf:

1. `RIS_CURSOR_SECRET` (nur Tests/lokal)
2. `RIS_CURSOR_SECRET_ARN` → Secrets Manager `GetSecretValue`, pro Prozess gecacht

Fehlt beides, ist der ARN leer oder schlägt der Abruf fehl → `RuntimeError` → HTTP 503. **Kein statischer Fallback**, keine Ausgabe des Werts, kein Logging.

Terraform stellt ausschließlich den **ARN** bereit:

- Root-Variable `applications_cursor_secret_arn` (Default `""`)
- Modul-Variable gleichen Namens
- Lambda-Env `RIS_CURSOR_SECRET_ARN` (nur ARN)
- Bedingte IAM-Policy `lambda_cursor_secret` (`count = ARN != ""`), ausschließlich `secretsmanager:GetSecretValue` auf genau diesen ARN
- Policy in `depends_on` der Agent-Lambda

Solange kein ARN gesetzt ist, entsteht **keine** IAM-Policy und Pagination bleibt fail-closed. Es wird **kein Secret erzeugt**.

### Tests

| Test | Ergebnis |
|---|---|
| Fehlende Konfiguration → fail-closed | PASS |
| ARN wird gelesen und gecacht (genau ein Abruf) | PASS |
| Nicht lesbares Secret → fail-closed | PASS |
| Tampered Cursor → `ValueError` | PASS (bestehend) |
| Cross-Tenant/Cross-User-Cursor → `ValueError` | PASS (bestehend, moto-abhängig, lokal skipped) |

### Freigabeschritt (offen)

Secret-Wert außerhalb Terraform anlegen, ARN per `--var`/Overlay setzen, IAM-Policy erzeugen, Rotation festlegen. **Keine AWS-Erstellung in diesem Auftrag.**

---

## 4. Application-Erasure-Verdrahtung

### Ist-Zustand

| Ebene | Befund |
|---|---|
| Executor | `ApplicationErasureExecutor` vorhanden, kontextgebunden, resumierbar |
| Orchestrator | `ProfileOnlyErasureExecutor._delete_applications` vorhanden |
| Runtime | `POST /me/erasure` nutzt `PrivacyErasure` **ohne** Applications |
| Flags | alle `false`, kein Application-spezifischer Flag |
| Rechtsfreigabe | `RIS-APPLICATION-V1-RETENTION-DECISION#APPROVAL_REQUIRED` offen |

### Technischer Blocker

Der Executor benötigt einen `ApplicationContext` (`tenantId`, `userId`, `partnerApplicationId`, `issuer`). `/me/erasure` kennt nur `userId` + `tenantId`.

Die Tabelle hat als Zugriffspfad ausschließlich `gsi-owner` auf `ownerKey = tenant|user|partner|issuer`. Damit ist eine **user-weite** Löschung über alle Partner/Issuer nicht möglich, ohne:

- einen neuen GSI (z. B. `gsi-user` auf `tenant|user`) **plus** Schreibpfad-Änderung, oder
- einen vollständigen `Scan` mit Filter (Kosten/Laufzeit, für Löschpfad ungeeignet).

Beides ist eine Schema-/Architekturentscheidung, keine reine Verdrahtung. Zusätzlich fehlt die Rechtsfreigabe.

### Testbarkeit

`moto` ist in dieser Umgebung nicht installiert (PEP 668, kein venv). Die bestehenden Repository-/Erasure-Integrationstests werden daher **übersprungen**. Eine destruktive Löschlogik ohne lauffähige Integrationstests zu verdrahten, wäre nicht vertretbar.

**Ergebnis: BLOCKED.** Keine Codeänderung. Empfehlung: eigener Auftrag mit GSI-Design, Backfill-Entscheidung, Rechtsfreigabe und lauffähiger Testumgebung.

---

## 5. PITR-/Backup-Bewertung

Keine Änderung, keine Aktivierung, keine Löschung. Stand: lesend.

### Bestehende Tabellen

| Tabelle | PITR | Datenkategorie | Empfehlung |
|---|---|---|---|
| `ris-dev-dev-user-profile` | DISABLED | personenbezogen | PITR aktivieren |
| `ris-dev-dev-credentials` | DISABLED | Secret-Metadaten (Hash) | PITR aktivieren |
| `ris-dev-dev-partner-applications` | DISABLED | Partner-/Tenant-Zuordnung | PITR aktivieren |
| `ris-dev-dev-api-profiles` | DISABLED | Konfiguration | PITR optional |
| `ris-dev-dev-entitlements` | DISABLED | Berechtigungen | PITR optional |
| `ris-dev-dev-jobsearches` | DISABLED | personenbezogen | PITR aktivieren |
| `ris-dev-dev-work-items` | DISABLED | Betriebsdaten | PITR aktivieren |
| `ris-dev-dev-offers` | DISABLED | Geschäftsdaten | PITR aktivieren |
| `ris-dev-dev-agent-catalog` | DISABLED | Seed-Daten | kein PITR nötig |
| `ris-dev-dev-agent-state` | DISABLED | Betriebsdaten | PITR optional |
| `ris-dev-mays-orders` | **ENABLED** | Orders | unverändert |

### Geplante neue Tabellen

| Tabelle | Vorhanden | PITR | Datenkategorie | Empfehlung |
|---|---|---|---|---|
| Partner Profiles | ❌ | — | personenbezogen | Create + PITR aktivieren |
| Privacy Receipts | ❌ | — | Rechtsnachweis | Create + PITR + Aufbewahrung entscheiden |
| Erasure Operations | ❌ | — | Betriebs-/Löschnachweis | Create + PITR |
| S3 Erasure Phases | ❌ | — | Betriebsdaten | Create, PITR optional |
| Upload Ticket Ledger | ❌ | — | Sicherheits-/Betriebsdaten | Create + PITR |
| Upload Cutover | ❌ | — | Betriebsdaten | Create, PITR optional |
| Applications | ❌ | — | personenbezogen (Bewerbungen, Anschreiben) | Create + PITR **stark empfohlen** |

Aufbewahrungsfristen werden **nicht** festgelegt; das ist eine Rechtsentscheidung.

---

## 6. Orders-SQS-Sicherheitsbewertung

Live-Policy (`ris-dev-mays-orders-orders-queue`):

```json
{"Sid":"AllowAccessFromAccount","Effect":"Allow","Principal":"*",
 "Action":["sqs:SendMessage","sqs:ReceiveMessage","sqs:DeleteMessage","sqs:GetQueueAttributes"],
 "Resource":"arn:aws:sqs:eu-central-1:240571105849:ris-dev-mays-orders-orders-queue"}
```

Quelle: generiertes Modul `terraform/modules/mays_orders/modules/sqs/main.tf:29-40`.

### Bewertung

| Aspekt | Befund |
|---|---|
| Internet-öffentlich? | **Nein** — SQS verlangt SigV4; anonyme Aufrufe scheitern |
| Cross-Account? | **Ja** — jeder AWS-Principal mit eigener IAM-Erlaubnis darf die vier Aktionen ausführen |
| Conditions | **keine** (`aws:SourceAccount`/`aws:SourceArn` fehlen) |
| Gefährlichste Rechte | `ReceiveMessage` + `DeleteMessage` (Exfiltration/Löschung) |
| Notwendige Nutzer | RIS-Agent (Send), Orders-SQS-Worker (Receive/Delete) |
| Eigentümer | RIS (`Project=ris-dev-mays-orders`), Modul generiert aus MO |

**Risiko: HOCH** für Vertraulichkeit/Verfügbarkeit, **MITTEL** für Integrität. Der Befund ist real, aber nicht „öffentlich“ im Internet-Sinn.

**Empfohlene Korrektur (separater Auftrag, Eigentümer):** `Principal` auf die beiden Rollen-ARNs oder Account-Root begrenzen, `aws:SourceAccount`-Condition ergänzen, `ReceiveMessage`/`DeleteMessage` nur für den Worker. Keine Änderung in diesem Auftrag.

---

## 7. Durchgeführte Codeänderungen

| Datei | Änderung |
|---|---|
| `jobsearch/application_repository.py` | Secret-Auflösung über ARN, Prozess-Cache, fail-closed |
| `terraform/main.tf` | ARN an Lambda-Modul durchgereicht |
| `terraform/variables.tf` | Root-Variable `applications_cursor_secret_arn` |
| `terraform/modules/lambda/variables.tf` | Modul-Variable |
| `terraform/modules/lambda/main.tf` | Env `RIS_CURSOR_SECRET_ARN`, bedingte IAM-Policy, `depends_on` |
| `tests/test_application_repository.py` | 4 Secret-Tests |

Keine Änderung an Cognito, Domains, CloudFront, DNS, ACM, Orders-Lifecycle, Tabellen, Flags.

---

## 8. Testnachweise

| Lauf | Ergebnis |
|---|---|
| Application/Profile/CV/ATS/Privacy/API/Installer (14 Dateien) | **217 passed, 8 skipped** |
| Cursor-Secret-Tests | 4 passed (2 Repository-Integrationstests moto-bedingt skipped) |
| `terraform fmt -check -recursive` | PASS |
| `terraform validate` | PASS |

`moto` fehlt in der Umgebung; Installation scheiterte an PEP 668 und fehlendem `python3-venv`. Das ist ein Umgebungs-, kein Codebefund.

---

## 9. Packaging

| Feld | Wert |
|---|---|
| Bundle | `terraform/lambda.zip`, 76 Dateien |
| SHA-256 | `0ed0d4dfaa5eba0e85a6d3d8043f99f4bb52126c0d21b1b8b7c4b6ddaaba932a` |
| Reader | `lambda/dist/orders-reader.zip`, `e4058587…` |
| Reproduzierbarkeit | 2 Läufe, identischer Hash ✅ |
| Upload | **keiner** |

---

## 10. Neuer Terraform-Plan

| Feld | Wert |
|---|---|
| Plan | `/tmp/opencode/ris-dev-s04b.tfplan` (außerhalb Git) |
| JSON | `/tmp/opencode/ris-dev-s04b-plan.json` |
| **SHA-256** | **`5fd68662754b5d1f1eb6e8aa9598f7acc32a93a655a9f2f269b1b4815ce71da6`** |
| State-Serial danach | 36 (unverändert) |
| State-Version | `3tey8lIHFnMBSsaWeFErDer8a2BucoCK` |

| Aktion | Anzahl |
|---|---:|
| CREATE | 48 |
| UPDATE | 3 |
| DELETE | **0** |
| REPLACE | **0** |
| MOVE | 54 |
| no-op | 167 |
| Drift | 1 (berechnetes `domain`-Attribut) |

Creates: 34 Routen, 7 Tabellen, 7 IAM-Policies. Updates: Lambda-Code/Env, 2 IAM-Policies.

---

## 11. Geschützte Ressourcen

| Bereich | Ergebnis |
|---|---|
| RIS Cognito | 0 Änderungen ✅ |
| Jobsearch Cognito | 0 Änderungen ✅ |
| Cognito-Domains | 0 Änderungen ✅ |
| CloudFront/OAC | 0 Änderungen ✅ |
| DNS/ACM | 0 Änderungen ✅ |
| Mays-Orders | 0 Änderungen ✅ |
| Bestehende Tabellen | 0 Delete/Replace ✅ |
| Adressmigration | 54 Moves, alle no-op ✅ |

---

## 12. Offene Blocker

| # | Blocker | Auswirkung |
|---|---|---|
| 1 | Secret-ARN nicht provisioniert | Pagination → 503 bis zur Freigabe |
| 2 | Erasure ohne user-weiten Index + Rechtsfreigabe | Löschanfrage deckt Applications nicht ab |
| 3 | PITR auf Kerntabellen deaktiviert | kein Wiederherstellungsschutz |
| 4 | Orders-SQS `Principal="*"` | Cross-Account-Zugriff möglich |
| 5 | `moto` fehlt lokal | Integrationstests skipped |

---

## 13. GO/NO-GO

**YELLOW — kein Deployment.** Die Adressmigration und der Plan sind sauber (0 Delete/Replace), aber drei Freigaben fehlen: Secret-Provisionierung, Erasure-Architektur/Recht, PITR-Entscheidung.

Empfehlung: S05 mit (a) Secret-Anlage + ARN, (b) GSI-/Erasure-Design, (c) PITR-Entscheidung, (d) Orders-SQS-Korrektur durch den Eigentümer. Danach neuer Plan.

**STOP nach S04-B. Kein Apply, keine AWS-Mutation.**
