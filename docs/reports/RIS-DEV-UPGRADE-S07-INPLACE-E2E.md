# RIS-DEV-UPGRADE-S07 — In-Place Upgrade, CloudFront Preservation & E2E Consolidation

- **Datum:** 2026-11-04
- **Baseline:** `main` @ `259a19d` · `240571105849` · `eu-central-1` · Workspace `ris-dev`
- **Apply:** **NICHT ausgeführt** — Gate-Entscheidung **B (NO-GO für Apply)**
- **Ergebnis:** Plan und Schutzgüter sind sauber; der Plan aktiviert jedoch zwangsläufig personenbezogene Endpunkte ohne RG-09-Freigabe.

---

## 1. Git-Baseline

| Feld | Wert |
|---|---|
| Branch | `main` |
| HEAD bei Beginn | `259a19d` ✅ |
| Neue Commits | `cfb2685` (Erasure-Gate), Report-Commit folgt |
| Working Tree | sauber bis auf geschützte fremde Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` |

---

## 2. AWS-/Terraform-Baseline

| Prüfung | Wert |
|---|---|
| STS | `240571105849`, `Mayaws` ✅ |
| Workspace | `ris-dev` |
| Backend | `mays-ris-tf-state-dev`, Key `env:/ris-dev/dev/terraform.tfstate` |
| Lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` ✅ |
| Serial | 36 ✅ |
| Ressourcen | 185 ✅ |
| API-Routen | 35 (keine Applications-Routen) |
| RIS-Lambdas | 6 |
| RIS-Tabellen | 11 |
| IAM-Policies der Agent-Rolle | 10 (keine `lambda_cursor_secret`) |

Zusätzlich vorhanden (fremd, unverändert): Cognito-Pool `eu-central-1_OZ7TK51EK` (`mays-orders-rc4-test-users`) aus der MO-Arbeit.

---

## 3. Komponentenübernahme (Ist → Plan)

| Komponente | Ist | Im Plan | Bewertung |
|---|---|---|---|
| Applications-Tabelle + `gsi-owner`/`gsi-user` | fehlt | CREATE | additiv |
| Partner Profiles | fehlt | CREATE | additiv |
| Privacy Receipts | fehlt | CREATE | additiv, Flags aus |
| Erasure Operations | fehlt | CREATE | additiv, Flags aus |
| S3 Erasure Phases | fehlt | CREATE | additiv, Flags aus |
| Upload Ticket Ledger | fehlt | CREATE | additiv, Flags aus |
| Upload Cutover | fehlt | CREATE | additiv, Flags aus |
| 34 API-Routen (Applications, CV, Profiles, Privacy) | fehlen | CREATE | **aktivieren Endpunkte** |
| 8 IAM-Policies | teilweise | CREATE/UPDATE | geprüft |
| Lambda Code/Env | älter | UPDATE | inkl. `RIS_CURSOR_SECRET_ARN`, `ERASURE_APPLICATIONS_ENABLED=false` |
| Cursor-Secret | existiert | ARN-Referenz | RG-07 wird mit Apply wirksam |

---

## 4. Tatsächlich durchgeführte AWS-Aktionen

**Keine.** Nur lesende Abfragen und zwei Terraform-Pläne (lokal). Kein Apply, kein State-Schreibvorgang, kein Secret neu angelegt.

---

## 5. CloudFront-/Cognito-/DNS-Vorher-Nachher-Vergleich

| Ressource | Vorher (2026-11-04) | Nachher | Status |
|---|---|---|---|
| RIS-Pool `ojbmoiYGM` | `ris-dev-dev-users`, Domain `ris-dev-dev`, Clients `7ldh…`, `82ji…` | unverändert | ✅ |
| Jobsearch-Pool `ZURSMpD2O` | Custom Domain `auth.mays-job-matcher.app`, Client `5hb3…` | unverändert | ✅ |
| Orders-Pool `cmJWXujnb` | eigener Client, keine Domain | unverändert | ✅ |
| Health-CloudFront `E1IP0DIEAXAZPY` | Deployed | im Plan `no-op` | ✅ |
| Fremd-CloudFront `E1R3BHTJNMC6XW` | Deployed | nicht im Plan | ✅ |
| OAC `E29OZUCWF2PIIJ` / `E1AEAL7JW5EP6Q` | vorhanden | nicht im Plan | ✅ |
| ACM `0bfb2603…` | ISSUED, von Account `590490809858` genutzt | unverändert | ✅ |
| DNS `auth` CNAME | `dsv3el0c1dn2.cloudfront.net` | unverändert | ✅ |
| Jobsearch-Auth-Endpoint | HTTPS 302 (Managed Login) | unverändert | ✅ |
| RIS-Health | HTTPS 401 (JWT erzwungen) | unverändert | ✅ |

Plan-Auswertung: **0 aktive Änderungen** an Cognito, CloudFront, OAC, DNS, ACM, Orders.

---

## 6. Terraform-Plan und SHA

| Feld | Wert |
|---|---|
| Plan | `/tmp/opencode/ris-dev-s07b.tfplan` |
| JSON | `/tmp/opencode/ris-dev-s07b-plan.json` |
| **SHA-256** | **`93fbd41c69ffb30251aa3e4343e03352b2357cc15ac499dc20dc5934c2348674`** |
| State danach | serial 36, Version `3tey8lIH…` unverändert |

| Aktion | Anzahl |
|---|---:|
| CREATE | 49 |
| UPDATE | 3 |
| DELETE | 0 |
| REPLACE | 0 |
| MOVE | 54 |
| no-op | 167 |
| DRIFT | 1 (berechnetes Cognito-`domain`) |

Der zuvor erzeugte Plan `e1c7d588…` ist durch die Erasure-Gate-Korrektur überholt und nicht mehr gültig.

---

## 7. Apply-Ergebnis

**Nicht ausgeführt.** Keine Freigabe erteilt; Gate-Entscheidung B.

---

## 8. Neue Ressourcen (geplant, nicht erstellt)

7 Tabellen, 34 Routen, 8 IAM-Policies, 1 Lambda-Update (Code + Env).

---

## 9. Bestehende Ressourcen unverändert

Cognito-Pools/-Clients/-Domains, CloudFront, OAC, ACM, DNS, Orders, 11 bestehende Tabellen, 35 bestehende Routen, 6 Lambdas: **0 Delete/Replace**, keine aktive Änderung außer den 3 genehmigten Lambda-/IAM-Updates.

---

## 10. E2E-Testmatrix

| Test | Status | Evidence |
|---|---|---|
| E2E-01 CloudFront/DNS Preservation (Vorher) | **PASS** | §5 Snapshot |
| E2E-01 Nachher | **NOT EXECUTED** | kein Apply |
| E2E-02 Unauthentifizierter Zugriff | **PASS** | `/health` → 401 |
| E2E-02 Positive JWT/Auth | **BLOCKED** | keine synthetische Identität, kein Deployment |
| E2E-03 ApplicationV1 CRUD/Idempotenz/Pagination | **BLOCKED** | Tabelle/Routen nicht deployed |
| E2E-03 Cursor nach Kaltstart | **BLOCKED** | Lambda ohne ARN |
| E2E-04 UserProfile/CV/Search | **BLOCKED** | Routen nicht deployed |
| E2E-05 Erasure lokal | **PASS (historisch)** | 14 Tests, S05 |
| E2E-05 produktive Löschung | **NOT ACTIVATED** | Flag `false` |

Historisch wiederverwendet: S05/S06 (267 Tests), DEC-01 (Secret), S06-R (Register). Keine Wiederholung ohne Anlass.

---

## 11. Datenschutz-Evidence-Konsolidierung

| Bereich | Status |
|---|---|
| Application-Erasure-Semantik | TECHNICALLY VERIFIED (14 Tests) |
| Partnerübergreifende Löschung | TECHNICALLY VERIFIED |
| Tenant-/User-Isolation | TECHNICALLY VERIFIED |
| Privacy Inspect/Export | IMPLEMENTED, nicht deployed |
| Privacy Receipt Writes | Flag `false` |
| S3-Erasure/Cutover/Freeze | Flags `false` |
| Application-Erasure-Aktivierung | **neu gegated** (`ERASURE_APPLICATIONS_ENABLED=false`) |
| Rechtsfreigabe | **offen (RG-09)** |

---

## 12. Gezielt korrigierte Fehler

**Ein Defekt, reproduzierbar:** `_handle_me_erasure` übergab den Application-Deleter unbedingt. Ein Apply hätte damit die Application-Löschung ohne Datenschutzfreigabe aktiviert.

**Fix (`cfb2685`):** Deleter wird nur bei `ERASURE_APPLICATIONS_ENABLED=true` verdrahtet; Terraform setzt den Flag explizit auf `false`. Test ergänzt; 18 Tests PASS.

---

## 13. Nicht aktivierte Funktionen

Privacy-Receipt-Writes, Erasure-Operation-Repository, S3-Erasure, S3-Quiescence, Write-Freeze, Upload-Ticket-Ledger, Upload-Cutover, Application-Erasure — alle `false`.

---

## 14. Offene rechtliche und betriebliche Freigaben

| Gate | Status |
|---|---|
| RG-07 Cursor Secret | PARTIAL → mit Apply PASS-fähig |
| RG-09 Privacy/Legal | **BLOCKED** |
| RG-10 PITR/Recovery | **BLOCKED** |
| RG-11 Orders-SQS | **BLOCKED** |

---

## 15. Abschließender Release-Status

**NO-GO für Apply (Gate-Entscheidung B).**

Begründung: Der Plan erzeugt 7 Tabellen und 34 personenbezogene Endpunkte. Mit dem Apply werden Applications/CV/Profile-Endpunkte für autorisierte Nutzer erreichbar; damit beginnt Verarbeitung personenbezogener Daten, für die RG-09 (Rechtsgrundlage, Aufbewahrung, Rollen) nicht freigegeben ist. Die destruktive Application-Löschung ist jetzt zwar gegated, aber die Verarbeitung selbst bleibt ungenehmigt.

Der Plan ist technisch einwandfrei (0 Delete/Replace, Schutzgüter unverändert, 54 Moves). Ein sauberer Plan ersetzt keine Freigabe.

### Finale Übersicht

| Bereich | Vorher | Nachher | E2E | Status |
|---|---|---|---|---|
| RIS Cognito | unverändert | unverändert | Snapshot | ✅ |
| Jobsearch Cognito | unverändert | unverändert | Snapshot | ✅ |
| CloudFront | 2 Distributionen | unverändert | Snapshot | ✅ |
| DNS | `dsv3el0c1dn2` | unverändert | CNAME | ✅ |
| ACM | ISSUED | unverändert | — | ✅ |
| Mays-Orders | unverändert | unverändert | — | ✅ |
| ApplicationV1 | nicht deployed | nicht deployed | BLOCKED | ⛔ |
| UserProfile | deployed | unverändert | historisch | ✅ |
| CV/Profile | nicht deployed | nicht deployed | BLOCKED | ⛔ |
| Privacy Inspect/Export | nicht deployed | nicht deployed | BLOCKED | ⛔ |
| Erasure | Code, Flag aus | Flag aus | lokal PASS | ⚠️ |
| Cursor Secret | vorhanden | vorhanden | lokal PASS | ⚠️ |
| DynamoDB | 11 Tabellen | unverändert | — | ✅ |
| Lambda/API | 6 / 35 | unverändert | 401 | ✅ |

### Kennzahlen

- Git-HEAD: `259a19d` → `cfb2685` (+ Report-Commit)
- Plan-SHA-256: `93fbd41c69ffb30251aa3e4343e03352b2357cc15ac499dc20dc5934c2348674`
- Terraform: 49 CREATE · 3 UPDATE · 0 DELETE · 0 REPLACE · 54 MOVE
- State: serial 36 → 36
- E2E: 2 PASS (Preservation-Snapshot, 401), 5 BLOCKED, 1 NOT ACTIVATED
- Deployment: **nicht autorisiert**

**STOP nach S07. Kein Apply, keine weiteren AWS-Änderungen, kein Push.**
