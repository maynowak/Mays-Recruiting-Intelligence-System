# Parallel-Test-Manifeste – was testet welcher Test?

**Prinzip (Vorgabe):** Jeder Test muss explizit benennen, was er testet —
Ziel-Installation, Ressourcen-Präfix, erwartete Werte, Ownership.
Kein „irgendwas läuft", sondern „ris-a besitzt X, und X ist Y".

## Ownership-Register (gilt für alle Tests)

| Ressource | Besitzer | Regeln |
|---|---|---|
| Präfix `ris-a-*` | Workspace `ris-a`, `project_name=ris-a` | nur A-Test prüft, nur A-Destroy löscht |
| Präfix `ris-b-*` | Workspace `ris-b`, `project_name=ris-b` | nur B-Test prüft, nur B-Destroy löscht |
| `mays-ris-e2e-*` / CF `E1R3BHTJNMC6XW` | fremd, vorgefunden | **nie anfassen, nie als Treffer werten** |
| `mays-ris-tf-lock`, `mays-ris-tf-state-dev` | Backend | behalten, in keinem Zähler als App-Ressource |

## T-1: Test A nach Install (Ziel: ris-a)

| # | Was wir testen | Warum | Erwartung |
|---|---|---|---|
| T1.1 | Plan-Idempotenz ris-a | Ist State == Konfiguration? | `plan -detailed-exitcode` → Exit 0 |
| T1.2 | Ressourcenzählung A | Hat A wirklich seine 167? | 167 in State, Präfix `ris-a-*` |
| T1.3 | Präfix-Isolation | A darf **keine** `mays-ris-dev-*` besitzen | 0 Treffer `mays-ris-dev` bei A |
| T1.4 | B-Lambda = 0 | B darf zu diesem Zeitpunkt nicht existieren | 0 Functions `ris-b-*` |
| T1.5 | Auth-Smoke A | API antwortet geschützt | `/health` → 401, `/orders` → 401 |
| T1.6 | Verkabelung A | Env zeigt auf **A**-Ressourcen | `ORDERS_TABLE=ris-a`, Queue `ris-a-orders-queue` |
| T1.7 | Monitoring A | A besitzt eigene Dashboards/Alarme | `ris-a-overview` + `ris-a-orders-overview`, 13 Alarme |
| T1.8 | ESM A | A-Queue → A-Worker | Enabled, Batch 5, Präfix `ris-a` |
| T1.9 | PyTest | Code-Vertrag heil | 12/12 + 25/25 |
| T1.10 | Fremd-Ressourcen unberührt | A darf e2e nicht beschädigen | e2e-CF + e2e-OAC existieren weiter |

## T-2: Test A+B parallel (Ziel: beide gleichzeitig)

| # | Was wir testen | Erwartung |
|---|---|---|
| T2.1 | Beide APIs antworten | A `/health` 401 **und** B `/health` 401 |
| T2.2 | Zählung getrennt | `ris-a`-Lambda = 6 **und** `ris-b`-Lambda = 6 |
| T2.3 | Kein Cross-Talk in Env | A-Reader → `ris-a`, B-Reader → `ris-b` |
| T2.4 | Doppelte Präfixe verboten | kein Ressourcenname existiert in beiden Installationen |
| T2.5 | Doppelte Dashboards | `ris-a-overview` **und** `ris-b-overview` existieren, keiner überschreibt den anderen |
| T2.6 | Destroy-Unabhängigkeit (vorab) | A-Plan nach B-Install weiterhin Exit 0 |

## T-3: Test nach Destroy B (Ziel: B weg, A heil)

| # | Was wir testen | Erwartung |
|---|---|---|
| T3.1 | B ist wirklich weg | 0 `ris-b-*` (Lambda/Tables/Queues/APIs/Dashboards/CF/OAC) |
| T3.2 | A unberührt | A-Plan Exit 0 (kein Drift), alle A-Zähler unverändert |
| T3.3 | A weiter online | `/health` 401, `/orders` 401 |
| T3.4 | A-Tests wiederholen | T1.5–T1.9 grün |
| T3.5 | Backend erhalten | tf-lock + tf-state noch da |

## T-4: Test nach Destroy A (Ziel: alles sauber)

| # | Was wir testen | Erwartung |
|---|---|---|
| T4.1 | A weg | 0 `ris-a-*` |
| T4.2 | State leer | `terraform state list` = 0 in ris-a |
| T4.3 | Konto bereinigt | nur Backend + fremde e2e-Ressourcen |

## Bekannte Fallstricke (dokumentiert aus Durchlauf 1)
1. **Plan-Dateien korrekt etikettieren** — ein falsch etikettierter Plan hat ris-a
   versehentlich mit `mays-ris-dev-*` gebaut (Ownership-Verletzung). Fix: Plan mit
   `-var=project_name=...` **vor** Apply prüfen (Spotcheck auf Präfix).
2. **CloudFront/Provider-Crash** hinterlässt Teil-State → danach immer
   `state list` + Ownership-Prüfung, nie blind weiter.
3. **BucketNotEmpty** bei Destroy → Bucket leeren, Destroy wiederholen (kein Defekt).

## Aktualisierung 2026-10-19: Vollserie statt Stichproben

Die 12–13 Prüfungen je Durchlauf waren unvollständig. Der Runner bildet jetzt die
dokumentierten Batterien ab (VOLLTEST 34, TRUE-Paralleltest-Gates, Regression):
**≈60 Checks je Installation, 20 Both, 16 Destroy-Check, 10 Static ≈ 230 je Zyklus.**
Herleitung und Abdeckungsmatrix: `docs/reports/PARALLEL-TESTABDECKUNG-ANALYSE-2026-10-19.md`.

Zusätzliche Prüfungen (Auswahl): STATE_OWNERSHIP (kein Fremd-Präfix im State),
PLAN_SAFETY_GATE, Workspace-Wahl gegen Ziel, Routen-/AuthorizationType-Checks,
Cognito-Gruppe `staff`, Log-Retention, DLQ-Redrive, CloudTrail-HomeRegion,
Public-Access-Block, `==0`-Prüfungen nach Destroy.

### Fallstricke ergänzt
4. **Workspace-Vorprüfung ist Pflicht** — ein Testlauf lief nach Destroy B im noch
   selektierten Workspace `ris-b` und zeigte „167 to add" statt „No changes".
   Der Runner bricht bei Workspace-Abweichung ab (S1.1), statt falsch zu grünen.
5. **Von Terraform unverwaltete Reste überleben Destroy** — `modules/health_plane`
   hat keine Log-Group-Ressource; Lambda erzeugt `/aws/lambda/*-health-{writer,publisher}`
   beim ersten Invoke selbst. Nach jedem Destroy `destroy-check` laufen lassen.
6. **Baseline-Defekte sind reell** — `tests/test_ris_installer.py` 2 failed/35 passed
   (Teil der 5 dokumentierten Baseline-Defekte). Der Runner meldet sie, statt sie zu
   verschweigen.
7. **`filename`-Pfade müssen identisch sein** — `terraform/../lambda/dist/x.zip` (Apply)
   und `lambda/dist/x.zip` (Test) sind für Terraform verschiedene Werte → Plan meldet
   Schein-Drift (`3 to change`). Immer die Apply-Schreibweise verwenden, sonst ist die
   Idempotenz-Prüfung wertlos.
8. **Pseudonyme sind keine Namen** — `ris-a` als Substring trifft `ris-api`
   (Cognito-Resource-Server-Kennung, pool-lokal, keine Kollision). Ownership-Prüfungen
   brauchen Wortgrenzen (`ris-a-*` oder exakt `ris-a`), keine naive `grep`-Suche.
9. **`aws --query length(...)` liefert pro Paginierungs-Seite eine Zeile** — bei
   mehrseitigen Listen (`get-routes`) entsteht `0\n0`. Über die Elementliste zählen.

---

## E. Ausgeführte Vollserie (2026-10-19, nach Log-Group-Fix)

| Lauf | Runner | Ergebnis (PASS/WARN/FAIL) |
|---|---|---|
| 0 | `static` (fmt/validate/Unit/Bundles) | 9 PASS · 1 WARN (Baseline) |
| 1 | Install A (`project_name=ris-a`) | 169 added, Exit 0 |
| 2 | `parallel_tests.sh ris-a` | **63 PASS**, 1 WARN |
| 3 | Install B (`project_name=ris-b`) | 169 added, Exit 0 |
| 4 | `parallel_tests.sh ris-b` | **63 PASS**, 1 WARN |
| 5 | `parallel_tests.sh both` | **22 PASS** |
| 6 | Destroy B (×2) + `destroy-check ris-b` | **16 PASS** (LogGroups→0) |
| 7 | `parallel_tests.sh ris-a` (nach B) | **63 PASS**, 1 WARN |
| 8 | Destroy A (×2) + `destroy-check ris-a` | **16 PASS** |

**Gesamt: 252 PASS, 0 FAIL, 4× Baseline-WARN.** Details:
`docs/reports/PARALLEL-VOLLSERIE-LAUF-2026-10-19.md` und
`docs/reports/PARALLEL-EXECUTION_LOG-2026-10-19.md` (Recovery-Template-konform).
