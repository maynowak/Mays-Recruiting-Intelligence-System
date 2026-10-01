# GATE-4 — MO Decimal Response Fix and Read E2E (eigene Lambda)

STATUS: GREEN

- Date/Time: 2026-10-01 12:20 UTC
- Branch + HEAD (RIS): main, e812676 (Gate-3-Commit) + Gate-4-Aenderungen (s. N)
- MO-Stand: Clone `installer/projects/mays_orders` @ 9c61237, clean (explizit ignoriert, nie committet)
- Scope-Korrektur waehrend Gate (User-Entscheid): KEINE Aenderung im fremden MO-Projekt (weder Repo noch live Funktionen). Stattdessen eigene Order-Fassade in unserem Bereich, verdrahtet auf unserer API, inkl. Deploy. Fremde Handler-Lambda nach Fix-Test auf Gate-3-Stand zurueckgesetzt.
- Sections: A–O unten
- Findings: Eigener Pfad GET/PATCH live 200 (Decimal-sicher); fremder Pfad unveraendert (POST→SQS→Worker→CONFIRMED intakt, GET dort weiter 500)
- Evidence: /tmp-Tests (59), Installer-Runs, AWS-CLI-Outputs, Lambda-Logs, API-Responses
- Classification: GREEN
- Terraform/AWS Checks: validate GREEN; targeted plan/apply (10 neu + 4 geteilt), 0 change/destroy an Bestand
- Git Status (RIS): nur eigene Dateien (s. N); Clone + Artefakte ignoriert
- Files Changed: `lambda/orders_reader.py` + `tests/test_orders_reader.py` (neu), `terraform/modules/orders_reader/` (neu, 3 Dateien), `terraform/main.tf`, `terraform/outputs.tf`, `terraform/modules/api/main.tf` (Issuer-Fix), `.gitignore`, Pin-Datei, diese Reports
- Open Questions: Upstream-Fix an Fremd-Team uebergeben (Decimal-Bug dort weiter offen); Full-Foundation-Plan vorbestehend defekt (lambda.zip fehlt)
- Risks: keine neuen (eigene Rolle Least-Privilege, Routen JWT, kein Public-Endpoint)
- Next Actions: Commit → Upstream-Handoff Decimal-Fix → Folgetore (RIS-Adapter etc.)
- Resume Point: nach Commit HARD STOP

## A. Gate-3 Ausgangslage

MO live (37/0/0/0), Kern-E2E GREEN, aber GET/PATCH → 500 (`Decimal is not JSON serializable`). YELLOW mit Auftrag Gate 4 = Minimal-Fix + Read-E2E.

## B. Reproduktion

Vor Code-Aenderung reproduziert (vollstaendiges DDB-Item mit `Decimal(2/100/200)` durch `ok()`): `TypeError: Object of type Decimal is not JSON serializable`. Betroffene Felder: `quantity`, `unitPrice`, `lineTotal`, `totalAmount`, `version` (alle DDB-Numbers → Decimal via Boto3). Serialisierungsstelle: `index.ok()` → `json.dumps(payload)` ohne `default`-Handler. POST unbehelligt (frische Python-ints), 409-Pfade unbehelligt (nur Strings). `encode_next_token` unbehelligt (nur String-Keys).

## C. Root Cause

Boto3-DynamoDB-Resource mappt Number → `decimal.Decimal`. GET-/PATCH-Pfade geben DDB-Reads zurueck; `ok()` serialisiert ohne Decimal-Behandlung → Exception → `fail()` → HTTP 500. Fachlogik (PUT/Update/Guards) korrekt — reiner Response-Serialisierungsfehler.

## D. Minimaler Fix + Kurskorrektur (User-Entscheid)

Der Fix (`_json_default`: ganzzahlig → int, sonst float; nur in Erfolgs-Responses) wurde zunaechst verifiziert (Repro gruen, 59 Tests), dann aber GEMAESS USER-VORGABE NICHT im fremden Projekt belassen:

1. Fremde Handler-Lambda kurz live getestet (GET → 200 bestaetigt), danach auf Gate-3-Original-Bundle zurueckgesetzt (`F5rRldqx…`, verifiziert; GET dort wieder 500). Worker durchgehend Original (`F5rRldqx…`).
2. Clone-Aenderungen vollstaendig zurueckgesetzt (`git checkout`, Testdatei entfernt) — Clone wieder pristine 9c61, clean.
3. Clone-Pfad auf User-Wunsch nach `installer/projects/mays_orders` umgezogen + in `.gitignore` explizit verankert (Zeile 58, Kommentar mit Fremdprojekt-Regel). Nichts aus dem Clone getrackt (verifiziert).
4. Stattdessen: EIGENE Lambda `mays-ris-dev-orders-reader` (unser Code, Decimal-sicher) + Verdrahtung auf UNSERER API — inkl. Deploy, eigener Pfad, fremdes Gateway unberuehrt (User-Antworten auf Rueckfragen).

## E. Betroffene Dateien (alle unser Bereich)

- `lambda/orders_reader.py` (neu, ~230 Zeilen): GET /orders (Liste, Limit 1..100), GET /orders/{orderId}, PATCH /orders/{orderId}/status; Transitionen 1:1 belegter Stand; Fehlercodes 400/404/409/500 kompatibel; interne Felder gestrippt.
- `terraform/modules/orders_reader/{main,variables,outputs}.tf` (neu): Rolle + Least-Privilege-Policy (nur DDB GetItem/Query/UpdateItem auf fremde Tabelle + Logs), Funktion (`orders_reader.handler`, python3.14, 128 MB, 10s), Log-Gruppe (7 Tage), Integration, 3 JWT-Routen, API-Permission.
- `terraform/main.tf` / `outputs.tf`: Modulaufruf + 2 Outputs.
- `terraform/modules/api/main.tf`: Issuer-Fix (`https://`-Prefix — Vorbefund: Authorizer war deshalb nie live erstellbar).
- `lambda/dist/orders-reader.zip`: Build-Artefakt (ignoriert).

## F. Regression Tests

- Eigene: `tests/test_orders_reader.py`, 8 Tests (Fake-Tabelle mit Decimals): GET 200 + Integer, kein Decimal-Leak, Liste, PATCH 200, 409, 400, 404, ID-Validierung → **8/8 PASS**.
- Technische Basis (in /tmp, Clone unberuehrt): MO-Bestand 51/51 + 8 Decimal-Regression → **59/59 PASS**.
- Installer-Suite nicht erneut (Installer ungeaendert).

## G. Deployment

- Installer `validate` GREEN (mit `AWS_PROFILE=mayaws`-Env — Flag allein reicht nicht, dokumentiert).
- Installer-`plan` scheitert vorbestehend (fehlendes `lambda.zip` des Agent-Moduls — NICHT angefasst). Deshalb: gezielter Plan/Apply nur `module.orders_reader` (+ Authorizer als geteilte Abhaengigkeit), gleicher Backend-/Workspace-/Profil-Mechanismus.
- Verlauf: Versuch 1 (10 Creates) → 2 heilbare Fehler: reservierter Key `AWS_REGION` (entfernt), Issuer ohne Schema (E, authorizer nie live gewesen). Versuch 2/3 → **Apply complete: 10 + 4 = 14 added, 0 changed, 0 destroyed** (Rolle, Policy, Funktion, Log-Gruppe, Integration, Permission, 3 Routen, 1 Authorizer).
- Live (verifiziert): Funktion `mays-ris-dev-orders-reader` (`gOgyxgFJ…`, Active, python3.14); 3 JWT-Routen auf `mays-ris-dev-api` (aboqolpm0f).

## H. Live GET Verification (eigener Pfad)

- `GET /orders/ord_67e31…` (fremd erzeugte Order, Worker-CONFIRMED): **200**, `"status":"CONFIRMED"`, `"totalAmount":250` (Integer, kein String) — Fix live.
- `GET /orders?limit=5`: **200**, 3 Orders, alle Betraege Integer.

## I. Live PATCH Verification (eigener Pfad)

- `PATCH …/status {"status":"CANCELLED"}` aus CONFIRMED: **200**, `"status":"CANCELLED"` (vorher 500).
- Re-GET: **200**, CANCELLED sichtbar.
- `PATCH CANCELLED→DELIVERED`: **409 INVALID_TRANSITION** (kein 500).

## J. Order/SQS Regression (fremder Pfad intakt)

- Neue Order `ord_67e31…` (12:02, nach Revert): POST 201 PENDING → Queue 0 → GET CONFIRMED (12:02:44) — Worker/SQS/POST unbehelligt, alles Original-Code.
- Eigene Lambda schreibt nur via Conditional-Writes (Race → 409), kein SQS-Kontakt.

## K. Cancellation Regression

- Siehe I: CANCELLED via eigenen Pfad wirksam + sichtbar; ungueltige Abgaenge 409. Endzustand beider Test-Orders: CANCELLED.

## L. Security Findings unverändert + eigene Haltung

- Fremd: SQS-`*`, kein DLQ — unveraendert/außer Scope (nicht angefasst).
- Eigen: Rolle nur DDB-Read/Update auf EINE fremde Tabelle + Logs; Routen JWT (kein Public-Endpoint); keine Secrets im Repo (Test-User geloescht, /tmp-Shred).

## M. AWS Resource Changes

- Neu (unser Bereich): 1 Funktion, 1 Rolle, 1 Policy, 1 Log-Gruppe, 1 Integration, 1 Permission, 3 Routen, 1 Authorizer. Kosten: vernachlaessigbar (128 MB, 7-Tage-Logs, pay-per-request Zugriffe).
- Geaendert: nichts am Bestand. Zerstoert: nichts. Fremd: 0 (beide Funktionen Original-SHA `F5rRldqx…`).

## N. Git Status

- Modified: `.gitignore`, `installer/mays-orders-clone.pinned.json` (Pfad + Live-State/Versions-/Rollback-/Update-Regel), `terraform/main.tf`, `terraform/outputs.tf`, `terraform/modules/api/main.tf`.
- Neu: `lambda/orders_reader.py`, `tests/test_orders_reader.py`, `terraform/modules/orders_reader/`, diese Reports.
- Unberuehrt: 8 Alt-Reports (untracked), Clone (ignoriert), `lambda.zip`-Luecke (offen dokumentiert).
- Pre-Commit: Secret-Scan ohne Befund (nur Client-/Pool-IDs = öffentliche Identifikatoren).

## O. Gate Decision

| Bereich | Ergebnis |
|---|---|
| Reproduktion | GREEN |
| Root Cause | GREEN |
| Minimal Fix | GREEN (eigene Lambda, fremd unberuehrt) |
| Unit Tests | GREEN (8/8 eigen; 59 techn. Basis) |
| Regression Tests | GREEN |
| Deployment | GREEN (14 added, 0/0) |
| GET /orders/{id} | GREEN (200, Integer) |
| PATCH /orders/{id}/status | GREEN (200; 409 bei ungueltig) |
| Status Regression | GREEN |
| SQS/Worker Regression | GREEN (fremder Pfad original + belegt) |
| Cancellation Regression | GREEN |
| Security Findings | GREEN (fremd unveraendert; eigen sauber) |
| Git | GREEN |

**Entscheidung: GREEN** — Decimal-Problem auf eigenem Pfad behoben (GET/PATCH 200, Integer korrekt), Fremd-Projekt zu 100 % unberuehrt, bestehende E2E-Kette intakt.

- Report: `docs/reports/GATE-4-MO-DECIMAL-RESPONSE-FIX-AND-READ-E2E-01.md` (+ Execution-Log folgt)
- Commit: folgt (nur eigene Dateien)
- Live-Evidence: Reader `gOgyxgFJ…` Active; Routen JWT; E2E B–E + Liste 200; Fremd-SHAs `F5rRldqx…`
- Offen: Upstream-Handoff (Decimal-Fix + Issuer-Hinweis an Fremd-Team); `lambda.zip`-Luecke (Full-Plan defekt); Remote-State/Team-Faehigkeit wie gehabt
- Naechstes Gate: RIS-Orders-Anbindung auf eigenem Pfad (Polling-Client gegen eigene Routen) — KEIN Foundation-Full-Apply ohne Freigabe, KEIN DLQ/Security hier

**DANN HARD STOP.**
