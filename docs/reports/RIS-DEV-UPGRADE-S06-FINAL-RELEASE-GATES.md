# RIS-DEV-UPGRADE-S06 — Final Release Gates

- **Datum:** 2026-11-03
- **Modus:** lokale Verifikation + Read-only AWS + Terraform-Plan
- **Ziel:** `ris-dev` · `mayaws` · `240571105849` · `eu-central-1`
- **Deployment:** **NICHT AUTORISIERT**
- **Entscheidung:** **NO-GO** (technisch sauber, drei Pflichtgates offen)

---

## 1. Executive Summary

Der technische Upgrade-Pfad ist stabil und zerstörungsfrei: **0 DELETE, 0 REPLACE, 54 Moves**, alle Schutzgüter unverändert. Regression und Packaging sind grün.

Vier Pflichtgates sind jedoch nicht erfüllt:

1. **Cursor-Secret** existiert nicht (ARN leer, kein Secret im Account).
2. **Privacy/Legal** für Application-Erasure ist nicht freigegeben.
3. **PITR/Recovery** ist nicht entschieden (10 Kern-Tabellen `DISABLED`).
4. **Orders-SQS** `Principal="*"` ist offen und nicht risikofreigegeben.

Damit ist die Entscheidung **NO-GO** — nicht wegen des Plans, sondern wegen fehlender Freigaben.

---

## 2. Git-Baseline

| Feld | Wert |
|---|---|
| Branch | `main` |
| HEAD | `364769f` |
| Working Tree | sauber bis auf geschützte fremde Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` |
| Lokale Commits | `8e42e6c`, `8535646`, `7a8e27d`, `364769f` (+ frühere) |
| Neue Commits S06 | Report-Commit (Auditlog) |

Keine fremde Datei verändert oder gestaged.

---

## 3. AWS-/State-Baseline

| Prüfung | Wert |
|---|---|
| STS | `240571105849`, `arn:aws:iam::240571105849:user/Mayaws` ✅ |
| Region | `eu-central-1` |
| Workspace | `ris-dev` |
| Backend | `mays-ris-tf-state-dev`, Key `env:/ris-dev/dev/terraform.tfstate` |
| Lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` ✅ |
| Serial | 36 ✅ |
| Ressourcen | 185 ✅ |
| Version | `3tey8lIHFnMBSsaWeFErDer8a2BucoCK` (nach Plan unverändert) |

---

## 4. Cursor-Secret-Readiness

| Kriterium | Befund |
|---|---|
| Secret existiert | ❌ nur fremdes `github-token-xxxxx` |
| ARN in Konfiguration | ❌ leer (Default) |
| Nur nichtgeheime Referenz | ✅ `RIS_CURSOR_SECRET_ARN` |
| Wert im State | ✅ nicht vorhanden |
| Wert in Git/Reports/Logs | ✅ nicht vorhanden |
| IAM minimal | ✅ bedingte `GetSecretValue`-Policy auf genau den ARN |
| KMS | keine eigene Key-Nutzung; bei CMK wäre `kms:Decrypt` zusätzlich nötig |
| Rotation | dokumentiert; Cache pro Prozess; alte Cursor werden ungültig |
| Fail-closed | ✅ fehlend/unlesbar → 503 |

**Provisionierungsanleitung (nicht ausgeführt):**

1. Freigabe durch Verantwortlichen.
2. `secretsmanager:CreateSecret` mit 32+ Byte Zufallswert (nur im Secret, nie im Ticket).
3. ARN per Installer-`--var applications_cursor_secret_arn=…` oder Overlay setzen.
4. Plan erneut erzeugen → erwartet +1 IAM-Policy.
5. Verify: Lambda-Env enthält ARN; `GetSecretValue` erfolgreich; Cursor-Issue/Resolve im Test.
6. Rollback: ARN entfernen → Policy fällt weg, Pagination fail-closed; Secret bleibt lesbar für Audit.

**Gate: BLOCKED.**

---

## 5. Application-Erasure-Readiness

| Kriterium | Ergebnis |
|---|---|
| Benutzerweite Löschung im Tenant | ✅ `gsi-user` auf `tenant\|user` |
| Alle Partner erfasst | ✅ Index schließt Partner/Issuer aus |
| Alle Kinddatensätze | ✅ META + HISTORY + COVER_LETTER + IDEMP |
| Fremde Tenants/User | ✅ nicht erreichbar (Tenant im Key, `ownerKey`-Condition) |
| Issuer-/Partnergrenzen | ✅ Löschung personenbezogen, Autorisierung über `ownerKey` |
| Idempotenz | ✅ zweiter Lauf `(0, False)` |
| Unvollständige Löschung | ✅ `pending` → `complete: false`, Schritt `ok=false` |
| Fehlende Komponente | ✅ Deleter `None` → no-op, kein falscher Erfolg |

### GSI-Konsistenz

`gsi-user` ist eventual consistent. Konsequenzen:

- Ein unmittelbar zuvor erstellter Datensatz kann in einem Lauf fehlen. Deshalb ist **ein einzelner Lauf kein Vollständigkeitsnachweis**.
- Der Statusvertrag bleibt ehrlich: `complete` nur, wenn alle Schritte ok sind; ein späterer Lauf findet Reste.
- Empfehlung: Erasure-Abschluss erst nach zwei aufeinanderfolgenden Läufen ohne Treffer plus Receipt.
- Freeze/Quiescence ist nicht aktiv; parallele Schreiber können zwischen Läufen neue Daten erzeugen.

**Technisch verifiziert: `TECHNICALLY VERIFIED`. Rechtlich: `NOT APPROVED`.**

---

## 6. Datenschutz- und Rechtsfreigaben

| Thema | Status | Entscheider |
|---|---|---|
| Rechtsgrundlage Bewerbungsdaten | offen | Datenschutz/Recht |
| Löschfrist nach Kontoschließung | offen | Recht |
| Aufbewahrung von Privacy Receipts | offen | Recht |
| Backup-/PITR-Aufbewahrung | offen | Recht + Betrieb |
| Rollen RIS ↔ Jobsearch (Verantwortlicher/Auftragsverarbeiter) | offen | Vertrag/Recht |
| Datenschutzhinweise für Bewerber | offen | Recht |
| DSFA-Erforderlichkeit | offen | Datenschutz |

Keine Frist wird hier festgelegt.

**Gate: BLOCKED.**

---

## 7. PITR-/Recovery-Entscheidungen

| Tabelle | Datenkategorie | PITR IST | PITR SOLL | Entscheidung |
|---|---|---|---|---|
| Applications | Bewerbungen, Anschreiben | Neu | **ja** | offen |
| Partner Profiles | Profil-/CV-Metadaten | Neu | **ja** | offen |
| Privacy Receipts | Datenschutznachweise | Neu | **ja** | Aufbewahrung nötig |
| Erasure Operations | Löschoperationen | Neu | ja | offen |
| S3 Erasure Phases | Löschphasen | Neu | optional | offen |
| Upload Ticket Ledger | Upload-Nachweise | Neu | ja | offen |
| Upload Cutover | Upload-Steuerung | Neu | optional | offen |
| user-profile | personenbezogen | DISABLED | **ja** | offen |
| credentials | Sperr-/Hash-Historie | DISABLED | **ja** | offen |
| partner-applications | Partnerbindung | DISABLED | **ja** | offen |
| jobsearches | Suchhistorie | DISABLED | **ja** | offen |
| work-items | Idempotenznachweis | DISABLED | **ja** | offen |
| offers | Geschäftsdaten | DISABLED | **ja** | offen |
| api-profiles | Konfiguration | DISABLED | optional | offen |
| entitlements | Rechte | DISABLED | optional | offen |
| agent-state | Laufzeitzustand | DISABLED | optional | offen |
| agent-catalog | Seeds | DISABLED | nein | entschieden (technisch) |
| mays-orders | Orders | ENABLED | unverändert | entschieden |

Restore erzeugt eine neue Tabelle. Wiederhergestellte Daten können gelöschte personenbezogene Daten zurückbringen → Restore-Verfahren muss gegen Erasure-Receipts abgleichen, bevor Daten online gehen.

**Gate: BLOCKED (Entscheidung offen).**

---

## 8. Orders-SQS-Sicherheitsbewertung

Effektive Policy: `Principal:"*"`, Actions Send/Receive/Delete/GetQueueAttributes, keine Conditions, Resource = Queue-ARN.

| Aspekt | Bewertung |
|---|---|
| Anonymer Internetzugriff | **nicht nachgewiesen / unwahrscheinlich** (SigV4 erforderlich) |
| Cross-Account | **möglich**, jeder Principal mit eigener IAM-Erlaubnis |
| Condition-Schutz | keiner |
| Kritikalität | Receive/Delete = Exfiltration/Löschung |

**Handoff an den Eigentümer (Vorschlag):**

```json
"Principal": {"AWS": ["arn:aws:iam::240571105849:role/ris-dev-dev-agent",
                      "arn:aws:iam::240571105849:role/ris-dev-mays-orders-sqs-worker-role"]},
"Condition": {"StringEquals": {"aws:SourceAccount": "240571105849"}}
```

Aktionen trennen: Agent nur `SendMessage`; Worker `ReceiveMessage`/`DeleteMessage`/`GetQueueAttributes`.

**Gate: offen, nicht risikofreigegeben.**

---

## 9. Regression und Packaging

| Lauf | Ergebnis |
|---|---|
| 17 Testdateien (Application, Partner, Privacy, API, Installer, Contract) | **267 passed** |
| Testumgebung | moto 5.2.5 via `PYTHONPATH=/tmp/opencode/pylibs` |
| `terraform fmt -check -recursive` | PASS |
| `terraform validate` | PASS (bekannte Warnungen) |
| Bundle | `terraform/lambda.zip`, 76 Dateien |
| SHA-256 | `c30556483979768ac861b8af260955a77e32308d519c4ecdc5f8c2fcef4df8f3` |
| Reproduzierbarkeit | 2 Läufe identisch ✅ |
| Reader | `e405858718101db34a8d5c1237e36d41a47b7dceb8e0ebff8b01bd86d1c366e5` |
| Upload | keiner |

---

## 10. Terraform-Plan

| Feld | Wert |
|---|---|
| Plan | `/tmp/opencode/ris-dev-s06.tfplan` |
| JSON | `/tmp/opencode/ris-dev-s06-plan.json` |
| **SHA-256** | **`6ccb94fef6cd97547a3207d2dfa1ec79ff0e37c3df9496c4b1cbe37800c6e5fe`** |
| State danach | serial 36, Version unverändert |

| Aktion | Anzahl |
|---|---:|
| CREATE | 48 |
| UPDATE | 3 |
| DELETE | **0** |
| REPLACE | **0** |
| MOVE | 54 |
| READ | 0 |
| DRIFT | 1 (berechnetes Cognito-`domain`) |

Creates: 34 Routen, 7 Tabellen (applications mit `gsi-owner`+`gsi-user`, partner_profiles, privacy_receipts, erasure_operations, s3_erasure_phases, upload_ticket_ledger, upload_cutover), 7 IAM-Policies.
Updates: Lambda-Code/Env, `lambda_documents`, `lambda_dynamodb_platform`.

---

## 11. Geschützte Infrastruktur

| Bereich | Ergebnis |
|---|---|
| RIS Cognito | 0 Änderungen ✅ |
| Jobsearch Cognito | 0 Änderungen ✅ |
| Cognito-Domains | 0 Änderungen ✅ |
| CloudFront/OAC | 0 Änderungen ✅ |
| DNS/ACM | 0 Änderungen ✅ |
| Mays-Orders | 0 Änderungen ✅ |
| Bestehende Tabellen | 0 Delete/Replace ✅ |
| Modul-Moves | 54 ✅ |

---

## 12. Finale Release-Gate-Matrix

| Gate | Prüfung | Status | Evidence |
|---|---|---|---|
| RG-01 | Git-Baseline | PASS | `364769f`, Tree sauber |
| RG-02 | AWS Account Guard | PASS | STS `240571105849` |
| RG-03 | State Ownership | PASS | Lineage/Serial 36/185 |
| RG-04 | Cognito Protection | PASS | 0 Änderungen im Plan |
| RG-05 | CloudFront/DNS Protection | PASS | 0 Änderungen im Plan |
| RG-06 | Orders Protection | PASS | 0 Änderungen im Plan |
| RG-07 | Cursor Secret | **BLOCKED** | kein Secret, ARN leer |
| RG-08 | Application Erasure | PASS (technisch) | 267 Tests, GSI/Löschpfad |
| RG-09 | Privacy/Legal | **BLOCKED** | keine Freigabe |
| RG-10 | PITR/Recovery | **BLOCKED** | 10 Tabellen DISABLED, Entscheidung offen |
| RG-11 | Orders-SQS Security | **BLOCKED** | `Principal:"*"`, keine Risikofreigabe |
| RG-12 | Regression Tests | PASS | 267 passed |
| RG-13 | Lambda Packaging | PASS | reproduzierbar, `c3055648…` |
| RG-14 | Terraform Plan | PASS | 0/0, 48/3/54, SHA `6ccb94fe…` |
| RG-15 | Deployment Readiness | **NO-GO** | 4 offene Gates |

---

## 13. Offene Freigaben

1. Secret-Anlage + ARN + Rotation (RG-07)
2. Datenschutz-/Rechtsfreigabe für Löschung und Aufbewahrung (RG-09)
3. PITR-Aktivierung und Aufbewahrungsgrenzen (RG-10)
4. Orders-SQS-Policy-Korrektur und Risikofreigabe (RG-11)

---

## 14. Rollback-/Recovery-Voraussetzungen

- State-Version `3tey8lIH…` bleibt lesbar; vor Apply zusätzliche State-Kopie sichern.
- Kein Delete/Replace im Plan → Rollback = neuer Plan gegen unveränderten State.
- PITR-Restore in neue Tabelle, kein In-place-Overwrite; Cutover separat.
- Secret-Rollback: ARN entfernen; Secret nicht löschen, solange Cursor im Umlauf sind.
- Erasure-Rollback ist **nicht** vorgesehen (Löschung ist irreversibel); daher Rechtsfreigabe vor Aktivierung.

---

## 15. Entscheidung

**NO-GO.**

Der Plan ist deployment-fähig, aber vier Pflichtgates bleiben offen. Ein `0 DELETE/0 REPLACE` allein rechtfertigt keine Freigabe.

**CONDITIONAL GO** wäre erst möglich, wenn RG-07, RG-09, RG-10 und RG-11 mit benannten Verantwortlichen und Terminen vor Apply geschlossen sind.

---

## 16. Voraussetzungen für S07

1. Secret anlegen, ARN setzen, Plan erneut erzeugen (+1 IAM-Policy erwartet).
2. Datenschutzfreigabe schriftlich dokumentieren (Löschzusage, Aufbewahrung, Rollen).
3. PITR-Entscheidung je Tabelle treffen und Terraform-Änderung separat planen.
4. Orders-SQS-Policy korrigieren (Eigentümer) und Risiko dokumentieren.
5. Neuen Plan erzeugen, SHA dokumentieren, Gates RG-07/09/10/11 auf PASS setzen.
6. Erst dann Apply-Freigabe durch separaten Auftrag.

**STOP nach S06. Kein Apply, keine AWS-Mutation, kein Push.**
