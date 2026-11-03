# RIS-DEV-UPGRADE-S05 — Security, Erasure & Recovery Readiness

- **Datum:** 2026-11-03
- **Modus:** lokale Implementierung + Read-only-Planung; **kein Apply, keine AWS-Mutation**
- **Ziel:** `ris-dev` · `mayaws` · `240571105849` · `eu-central-1`
- **Ergebnis:** **YELLOW** — Erasure technisch implementiert und getestet; Deployment bleibt durch fehlende Secret-Provisionierung, PITR-Entscheidung und SQS-Eigentümer-Korrektur blockiert.

---

## 1. Executive Summary

| Bereich | Status |
|---|---|
| Erasure-GSI | **implementiert** (`gsi-user` auf `userKey = tenant\|user`) |
| Partner-übergreifende Löschung | **implementiert**, tenant-/user-isoliert, idempotent |
| Runtime-Verdrahtung | **implementiert** (`POST /me/erasure`), fail-closed bei fehlendem Tenant |
| Cursor-Secret | **implementiert** (S04-B), Rotation dokumentiert |
| PITR | **Entscheidungsvorlage**, keine Änderung |
| Orders-SQS | **Befund bestätigt**, Änderungsvorschlag für Eigentümer |
| Testumgebung | **hergestellt** (`pip --target` + moto 5.2.5), venv systemseitig blockiert |
| Regression | **267 passed** |
| Plan | **0 DELETE, 0 REPLACE**, 48 CREATE, 3 UPDATE, 54 MOVE |

---

## 2. Git-Baseline

| Feld | Wert |
|---|---|
| Branch | `main` |
| HEAD bei Beginn | `7a8e27d` |
| Neue Commits | `8535646` (Erasure), Report-Commit folgt |
| Working Tree | sauber bis auf geschützte fremde Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` |

Die 54 `moved`-Blöcke aus `db0c0c2` sind unverändert.

---

## 3. Erasure-Datenmodell

| Schlüssel | Zusammensetzung | Zweck |
|---|---|---|
| `applicationId` / `entityKey` | Partition/Sort | Basis und Kinder (HISTORY, COVER_LETTER, IDEMP) |
| `ownerKey` | `tenant\|user\|partner\|issuer` | bestehende Autorisierungsgrenze (`gsi-owner`) |
| `userKey` (neu) | `tenant\|user` | user-weite Erasure-Sicht (`gsi-user`) |

`ownerKey` bleibt die **Autorisierungs**grenze: jede Löschung prüft weiterhin `ownerKey = :owner`. `userKey` ist ausschließlich ein **Auffinde**-Index und wird nur auf META-Zeilen geschrieben. Kinder tragen ihn nicht, damit der Index genau einen Treffer pro Bewerbung enthält.

Damit gilt:

- **Tenant-Isolation:** `userKey` beginnt mit dem Tenant; ein Tenant sieht keine fremden Zeilen.
- **Partnerübergreifend:** Partner und Issuer sind bewusst nicht enthalten.
- **Issuer-Isolation:** Löschung ist erlaubt (gleiche Person), Autorisierung bleibt über `ownerKey` erhalten.
- **Bestehende Datensätze:** Die Tabelle existiert in `ris-dev` noch nicht (Create im Plan), daher **kein Backfill**. Bei einer bereits existierenden Tabelle wäre ein Backfill nötig: jedes META-Item um `userKey` ergänzen, GSI aufbauen, erst danach löschen.
- **GSI-Konsistenz:** eventual consistent; die Löschung liest META-Zeilen und löscht die Partition anschließend konsistent (`ConsistentRead` auf der Basisabfrage).
- **Pagination:** `ExclusiveStartKey` über `gsi-user`; der Handler arbeitet maximal 20 Seiten à 25 ab und meldet sonst „pending“.
- **Idempotenz:** bereits gelöschte Zeilen erscheinen nicht mehr; ein zweiter Lauf liefert `(0, False)`.
- **Wiederaufnahme:** `pending` hält den Erasure-Status auf `complete: false`; der Aufrufer kann erneut starten.
- **Vollständigkeit:** GSI enthält alle META-Zeilen mit `userKey`; der Löschpfad entfernt META + HISTORY + COVER_LETTER je Bewerbung.

**Grenze:** Eine einzelne Transaktion ist auf 100 Items begrenzt (DynamoDB). Bei mehr als ~95 Kindzeilen pro Bewerbung schlägt die Transaktion fehl und die Bewerbung bleibt `pending`. Das ist ein bewusst sichtbarer Fehlerzustand, kein stiller Teil-Erfolg.

---

## 4. GSI-/Backfill-Konzept

| Schritt | Inhalt | Status |
|---|---|---|
| 1 | `userKey` auf META schreiben | ✅ implementiert |
| 2 | `gsi-user` deklarieren | ✅ Terraform |
| 3 | Erasure über `gsi-user` | ✅ implementiert |
| 4 | Backfill bestehender METAs | entfällt (Tabelle neu) / dokumentiert |
| 5 | Flag-Aktivierung | ❌ nicht erfolgt, Rechtsfreigabe offen |
| 6 | Rechtefreigabe Datenschutz | ❌ offen |

Keine zweite Erasure-Implementierung; der bestehende `ApplicationErasureExecutor` bleibt unverändert für die checkpoint-basierte Orchestrierung, der neue Pfad ist die user-weite Variante im selben Repository.

---

## 5. Cursor-Secret-Readiness

| Aspekt | Befund |
|---|---|
| Auflösung | `RIS_CURSOR_SECRET_ARN` → Secrets Manager, sonst Env (nur Tests) |
| IAM | bedingte Policy, nur `GetSecretValue` auf genau diesen ARN |
| KMS | kein eigener Customer-Key im Spiel; AWS-managed Key von Secrets Manager |
| Cache | pro Prozess, pro ARN; keine TTL, keine Persistenz |
| Logs | Wert wird nie geloggt oder zurückgegeben |
| Fehler | fehlend/unlesbar → `RuntimeError` → 503 |

### Rotation

1. Neue Secret-Version anlegen (`AWSCURRENT`, alte bleibt `AWSPREVIOUS`).
2. Lambda-Neustart/Deployment erzwingt neuen Cold Start → Cache leer → neuer Wert.
3. **Bestehende Cursor werden ungültig** (HMAC-Mismatch) → Client erhält `invalid cursor` und beginnt die Liste neu. Das ist fail-safe, kein Datenverlust.
4. Für unterbrechungsfreie Rotation wäre ein zweiter ARN (`…_PREVIOUS_ARN`) mit Verify-Fallback nötig — **nicht implementiert**, bewusst als Option dokumentiert.
5. Ohne separate Freigabe wird **kein Secret** angelegt.

---

## 6. PITR-/Backup-Bewertung

Keine Änderung. PITR-Restore erzeugt immer eine **neue** Tabelle; ein Cutover ist eine separate Entscheidung.

| Tabelle | PITR | Verlustfolge | Empfehlung |
|---|---|---|---|
| `user-profile` | DISABLED | Identitätsdaten weg | PITR aktivieren |
| `credentials` | DISABLED | Sperr-/Hash-Historie weg | PITR aktivieren |
| `partner-applications` | DISABLED | Partnerbindung weg | PITR aktivieren |
| `jobsearches` | DISABLED | Suchhistorie weg | PITR aktivieren |
| `work-items` | DISABLED | Idempotenznachweis weg | PITR aktivieren |
| `offers` | DISABLED | Geschäftsdaten weg | PITR aktivieren |
| `api-profiles` | DISABLED | Konfiguration weg | optional |
| `entitlements` | DISABLED | Rechte weg (TTL) | optional |
| `agent-state` | DISABLED | Laufzeitzustand weg | optional |
| `agent-catalog` | DISABLED | 2 Seeds, reproduzierbar | nicht nötig |
| `mays-orders` | ENABLED | — | unverändert |

Neue Tabellen: Applications und Partner Profiles **stark empfohlen**, Privacy Receipts **mit Aufbewahrungsentscheidung**, Erasure Operations und Upload Ticket Ledger **empfohlen**, S3 Phases und Upload Cutover optional.

Datenschutzfolge: Ein Restore bringt gelöschte personenbezogene Daten zurück. Deshalb muss ein Restore mit Erasure-Nachweisen abgeglichen werden (Receipts/Operations), bevor Daten wieder online gehen.

Kosten: PITR kostet pro GB/Monat zusätzlich; bei Dev-Datenvolumen vernachlässigbar.

---

## 7. Orders-SQS-Sicherheitsbefund

| Frage | Antwort |
|---|---|
| Anonymer Internetzugriff? | **Nein** — SQS verlangt SigV4 |
| Cross-Account? | **Ja**, jeder Principal mit eigener IAM-Erlaubnis |
| Conditions? | keine |
| Actions | Send, Receive, Delete, GetQueueAttributes |
| Eigentümer | RIS (`Project=ris-dev-mays-orders`), Code im generierten MO-Modul |

**Vorschlag an den Eigentümer (minimal):**

```json
Principal: {"AWS": ["arn:aws:iam::240571105849:role/ris-dev-dev-agent",
                    "arn:aws:iam::240571105849:role/ris-dev-mays-orders-sqs-worker-role"]}
Condition: {"StringEquals": {"aws:SourceAccount": "240571105849"}}
Action: Send (Agent) bzw. Receive/Delete/GetQueueAttributes (Worker)
```

Keine Änderung in diesem Auftrag.

---

## 8. Lokale Testumgebung

| Option | Ergebnis |
|---|---|
| System-Python | PEP 668 geschützt, `--break-system-packages` verboten |
| `venv` | **BLOCKED** — `ensurepip` fehlt (`python3-venv` nicht installiert) |
| `uv` / `pipx` | nicht vorhanden |
| `pip --target` | **funktioniert**: `/tmp/opencode/pylibs`, moto 5.2.5 |

Reproduzierbar:

```bash
python3 -m pip install --target /tmp/opencode/pylibs --only-binary=:all: moto
PYTHONPATH=/tmp/opencode/pylibs python3 -m pytest tests/ -q
```

Destruktive Tests laufen ausschließlich gegen moto-In-Memory-Daten.

---

## 9. Regressionsergebnisse

| Lauf | Ergebnis |
|---|---|
| Application/Profile/CV/ATS/Privacy/API/Installer/Contract (17 Dateien) | **267 passed** |
| Davon Repository + Erasure mit moto | 14 passed |
| `terraform fmt -check -recursive` | PASS |
| `terraform validate` | PASS |

---

## 10. Terraform-Plan

| Feld | Wert |
|---|---|
| Plan | `/tmp/opencode/ris-dev-s05.tfplan` |
| JSON | `/tmp/opencode/ris-dev-s05-plan.json` |
| **SHA-256** | **`6908f4aff3e75c567d27321f8a5261df059ae6fba43a5fe2d818dba1ea0d059a`** |
| State-Serial danach | 36, Version `3tey8lIH…` (unverändert) |

| Aktion | Anzahl |
|---|---:|
| CREATE | 48 |
| UPDATE | 3 |
| DELETE | 0 |
| REPLACE | 0 |
| MOVE | 54 |
| no-op | 167 |
| Drift | 1 (berechnetes Cognito-`domain`) |

`applications` wird mit **`gsi-owner` und `gsi-user`** erzeugt. Neue IAM-Ressourcen entstehen nicht (Secret-ARN weiterhin leer).

---

## 11. Schutzgüter-Matrix

| Gate | Ergebnis |
|---|---|
| RIS Cognito | 0 Änderungen ✅ |
| Jobsearch Cognito | 0 Änderungen ✅ |
| Auth-Domain | 0 Änderungen ✅ |
| CloudFront/OAC | 0 Änderungen ✅ |
| DNS/ACM | 0 Änderungen ✅ |
| Mays-Orders | 0 Änderungen ✅ |
| Bestehende Tabellen | 0 Delete/Replace ✅ |
| Modul-Moves | 54, eindeutig ✅ |
| Secrets | nur ARN-Referenz, kein Klartext ✅ |
| Erasure | kein Flag aktiviert; Pfad nur über `/me/erasure` erreichbar ✅ |

---

## 12. Offene Entscheidungen

1. **Secret-Provisionierung:** Wert anlegen, ARN setzen, Rotation festlegen (Freigabe nötig).
2. **Datenschutzfreigabe Erasure:** Löschzusage, Aufbewahrung, Receipt-Pflicht.
3. **PITR:** Aktivierung und Aufbewahrungsgrenzen für Kern- und neue Tabellen.
4. **Orders-SQS:** Policy-Einschränkung durch den Eigentümer.
5. **Cursor-Rotation:** Übergangsfenster ja/nein (zweiter ARN).

---

## 13. GO/NO-GO

**YELLOW — kein Deployment.** Die technische Erasure-Lücke ist geschlossen und getestet, der Plan bleibt zerstörungsfrei. Ohne Secret-ARN, Datenschutzfreigabe und PITR-Entscheidung darf nicht applied werden.

Empfehlung: S06 mit Freigaben + Secret-Anlage + PITR-Aktivierung, danach neuer Plan und kontrollierter Apply.

**STOP nach S05. Kein Apply, keine AWS-Mutation.**
