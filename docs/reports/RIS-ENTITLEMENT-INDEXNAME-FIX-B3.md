# RIS-ENTITLEMENT-INDEXNAME-FIX-B3 — Entitlement Query IndexName Fix

STATUS: GREEN (fix + getestet; KEIN AWS, KEIN TF, KEINE Migration)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, cef09ba (+ uncommitted: 2 Code-Dateien + 1 Test + diese Reports)
- Basis: P17-Blocker-A-Nachweis + TF-Schema + Live-GSI-Read.
- Scope: NUR IndexName-Korrektur produktiver Entitlement-Queries. KEIN Deploy/Apply, KEINE Tabellen/IAM/Cognito/Gateway, KEINE neue Logik/Struktur/Migration, KEINE P10/P11/P12-Aenderung.
- Classification: GREEN (10 Tests + Suite ohne Regression).
- AWS: NUR 1 Read (describe-table GSI-Verifikation). Mutation: NONE (verifiziert).
- Git: nur B3-Dateien (s. Commit).
- Next: NICHT P17 (Blocker B bleibt) — naechst: Tabellen/IAM-Deployment-Gate -> HARD STOP.

## 1. Root Cause (verifiziert, nicht geraten)

- Tabelle `mays-ris-dev-entitlements`: PK `entitlementId` (TF + live describe bestaetigt).
- 3 produktive Queries filtern auf `userId` (Nicht-Schluessel) OHNE `IndexName`: `lambda/handler.py` (`_get_entitlement_for_agent`, `_get_entitlements`) + `agents/ecosystem/worker_authorization.py` (`DynamoDBEntitlementResolver.find_entitlements`).
- DynamoDB beantwortet das zur Laufzeit mit ValidationException -> Handler: still None/[] (403/leere Listen) bzw. Worker: transient FAILED + Raise -> Redelivery -> DLQ-Flut. Live-Logs 24h: KEINE Fehler (Pre-P8-Code ohne Re-check; Basis gesund — kein aktiver Schaden, nur latente Falle fuer jeden Deploy).
- Vorgesehener GSI: `gsi-user` (HASH userId) — in TF deklariert UND live provisioniert (describe verifiziert). NICHT aus Namen geraten: exakter Vertrags-/Live-Abgleich.

## 2. Fix (kleinstmoeglich, 3 Stellen, KEINE Semantik-Aenderung)

- `IndexName="gsi-user"` in beiden Handler-Queries (+ B3-Kommentar).
- `USER_INDEX = "gsi-user"`-Konstante + `IndexName`-Verwendung im P8-Resolver.
- Tenant-Isolation, Zeitfenster, Agent-/Profil-Pruefung, KeyCondition, Filter, Fehlerverhalten (None/[] bzw. Propagieren): UNVERAENDERT. P8-Entscheidungssemantik UNVERAENDERT (alle 20 P8-Tests weiter GRUEN ohne Anpassung).
- P11-Neucode war bereits korrekt (kein Eingriff). KEINE P10/P11/P12-Datei angeruehrt.

## 3. Fail-Closed (unveraendert, erneut belegt)

- Erfolgreiche Query -> bestehende Entscheidung (Tests A/B).
- Keine Berechtigung -> DENIED-Pfad (Tests C-F).
- Store-Fehler -> Propagieren (Test G), Handler: None/[] wie bisher. KEIN Fail-Open (kein neuer Pfad, kein Cache).

## 4. Tests (10, ALLE GRUEN — IndexName-Nachweis, keine reinen Returnwert-Tests)

- A) user-wide AUTHORIZED (+ IndexName-Assert auf Query-Kwargs). B) profile-bound AUTHORIZED (+ Assert). C) expired DENIED. D) Tenant-Mismatch DENIED. E) falscher Agent DENIED. F) leer DENIED (`no-entitlement`). G) Store-Raise propagiert (KEIN AUTHORIZED) — Kwargs trotzdem mit IndexName abgesetzt. H) P8-Datei-Suite + Handler-Helper-Tests (beide Helper mit IndexName-Assert + Filter-Ergebnis).
- Fake-Tabelle zeichnet Query-Kwargs auf (jede Assertion prueft `IndexName == "gsi-user"` + vorhandene KeyCondition).

## 5. Regression / Quality / Live-Reads

- B3-Datei: 10/10 GRUEN. Gesamt-Suite: 709 passed (699 + 10), 8 skipped; 15 failed + 1 ERROR Hash-IDENTISCH zur P17-Baseline (pre-existing).
- Quality: KEINE Formatter-/Linter-Konfig im Repo (Projektstandard: py_compile + pytest + diff --check — alle GRUEN/clean).
- AWS Reads: 1 (describe-table GSI). Mutation: NONE. KEINE Secrets/Tokens (keine gehandhabt).

## 6. Offene Folge-Punkte (explizit, B3 beendet NICHT P17)

Blocker B (Tabellen api-profiles/offers/credentials fehlen) besteht — naechst: Tabellen/IAM-Deployment-Gate, danach P17-Re-Run (Deploy + gezielte Applies + E2E + Cleanup).

**HARD STOP (kein Deploy, kein Apply, keine Mutation erfolgt).**
