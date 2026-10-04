# RIS-WORKER-ENTITLEMENT-RECHECK-08 — Worker Entitlement Re-check (Execution-Time Authorization)

STATUS: GREEN (implementiert + getestet; KEIN AWS, KEIN TF, KEINE Migration)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, 019c120 (+ uncommitted: 2 Code + 1 Test + diese Reports)
- Basis (verbindlich): P01-P06 (SQS = Aktivierung, keine Autorisierung; Union-Entitlements; P7-Statusgrenze unveraendert) + Bestand (Handler-Gates, Pipeline, SQS/DLQ, Gates 5/10/12).
- Scope: NUR Worker-FRESH-Re-check (SQS -> validieren -> registrieren -> Re-check -> Eligibility/Selection ist vorhanden -> Engine). NICHT: Credential Verification, APIProfile-Auth/Selection, Offer/Credential-CRUD, Sandboxing, Admin-Migration, OAuth/M2M, neue Entitlement-Domaene, neue Statuslogik (P7 unveraendert).
- Classification: GREEN (20 Negativ-/Funktions-Tests + Suite ohne Regression).
- Terraform/AWS/Cognito/DB/Gateway: KEINE Mutation (verifiziert). Migration: NONE.
- Git: nur P8-Dateien (s. Commit).
- Next: Folge-Gates per P6-R8 (Credential-Einfuehrung + Sandboxing + Group-Migration) -> HARD STOP.

## 1. Ausgangsbefunde ZS1 (B1-B7, vor Aenderung, ohne Eingriff erhoben)

- B1: KEIN Entitlement-Touchpoint im gesamten Worker-Pfad (agents/runtime + Ecosystem: nur "future checks"-Parameter; Pruefung nur Handler-Sync-Pfad).
- B2: Entitlement-Vertrag (EXISTING, wiederverwendet): Query per userId (GSI), Filter agentId + tenant (tenant-lose Zeilen = global) + Fenster validFrom/validUntil (UTC, dateutil; unparsbar = ignoriert-mit-Warnung); 403 ohne; /agents-Positivliste. NUR user-weit (KEIN profile-bound implementiert — zukuenftig).
- B3: WorkItem-Identitaet: Execute legt userId/tenantId/agentId serverseitig an (NACH Handler-Check); Pipeline-Pflicht = workId/type/tenantId/idempotencyKey (userId NICHT Pflicht!); DDB-Record speichert tenantId, aber KEIN userId; agentId im Record = DECISION (post-selection).
- B4: Fehler-Semantik (EXISTING, wiederverwendet): PERMANENT_ERROR_CODES -> konsumiert; sonst FAILED + Raise -> Redelivery -> DLQ (maxReceiveCount); TERMINAL_DUPLICATE = {COMPLETED} (FAILED -> Retry-Resume).
- B5: Ausfuehrung via engine.execute_from_decision(decision, envelope) — decision.agent_id laeuft.
- B6: Handler-SQS-Pfad ruft process_record({'body': work_item}) (messageId-los, ok).
- B7: KEINE Tenant-/User-Pruefung im Worker (nur Handler-/Repo-Ebene).

## 2. Entitlement-Vertrag + Autorisierungsquelle (ZS2/ZS3 — DECIDED)

- Vertrag = B2, unveraendert wiederverwendet (KEINE zweite Welt; Handler-Logik unangetastet).
- Quelle: Identitaets-Claim aus validiertem WorkItem (userId/tenantId) + ENTSCHIEDENER Agent (post-selection, Registry-Wahrheit, NICHT Nachrichten-Feld) -> Verifikation gegen REGISTRIERTEN Entitlement-Bestand. Fehlende userId/tenantId/agentId -> DENIED (nie geraten).
- Sicherheitsbegruendung (dokumentiert): Nachricht behauptet Identitaet, Server PRUEFT sie (ohne passendes Entitlement -> DENIED; Tenant-Bindung enthaelt Cross-Tenant-Faelschung); Queue-Write selbst = IAM-Grenze (EXISTING). Zur Profilleere: KEIN profile-bound heute (P02/P04-future; Re-check deckt user-weite ab).

## 3. Zentrale Re-check-Funktion (ZS4 — NEU: agents/ecosystem/worker_authorization.py)

- `check_worker_entitlement(userId, tenantId, agentId, workId, requestTime=None, resolver)` -> AUTHORIZED (reason + entitlementId-Ref) ODER DENIED (missing-identity / no-entitlement / tenant-mismatch / time-window). Gueltigkeit = Handler-Zeitvertrag (ZS2). Store-Fehler PROPAGIEREN (transient, KEIN Denied).
- `DynamoDBEntitlementResolver` (lazy boto3, read-only, gleiche userId-Query wie Handler; ENTITLEMENTS_TABLE-Env; IAM-Read besteht bereits in Lambda-Rolle — KEIN IAM-Eingriff).
- `is_entitlement_valid` pure Teilfunktion (identischer Zeitvertrag, injizierbares now -> testbar).

## 4. Freshness + Worker-Integration (ZS5/Schritt 6 — pipeline.py + handler-Verdrahtung)

- Re-check NACH Selection/Decision + NACH Registrierung/Duplikat-Handling, VOR `engine.execute_from_decision` (= unmittelbar vor fachlicher Ausfuehrung; prueft GENAU den Agenten, der laeuft — kein Selection-Substitutions-Gap).
- Duplikat-terminal (COMPLETED): fruehe Rueckgabe OHNE Re-check (kein Processing-Versuch — Schritt-11-konform). Retry-Resume + Neu-Registrierung: Re-check laeuft (pro Attempt frisch).
- Produktion: `handler._process_work_item` injiziert IMMER `DynamoDBEntitlementResolver()` (lazy — keine Import-/Netz-Kosten ohne Nutzung). `process_record(..., entitlement_resolver=None)` = Test-/Harness-Modus (debug-geloggt, explizit dokumentiert — KEIN stilles Fail-Open; bestehende Tests ohne Resolver laufen unveraendert).
- DENIED: FAILED persistieren (Typ ENTITLEMENT_DENIED) + RETURN (konsumiert — KEIN Retry-Loop, KEIN falscher Success; Handler mappt denied/Reason durch, success=False).
- TRANSIENT (Store-Fehler): FAILED persistieren + RAISE (exakt Engine-Infra-Pfad — Redelivery -> neuer Attempt -> frischer Re-check). KEIN Fail-Open, KEIN falsches DENIED.
- P7-Boundary (Schritt 8): UNVERAENDERT — nach AUTHORIZED gilt bestehende P7-Eligibility/Status-Grenze (Tests 14/15 belegen Zusammenspiel); KEINE Statuslogik-Duplikation.

## 5. Tests (Schritte 9-11 — tests/test_worker_entitlement_recheck.py, 20/20 GRUEN)

- Gueltigkeit (4): ohne Fenster/ok, abgelaufen, zukuenftig, offenes Fenster.
- Freshness-Kern: revoked-zwischen-zwei-Checks -> AUTHORIZED dann DENIED (Test 12/13-Mechanismus identisch: Retry-Pfad mit geleertem Store -> DENIED).
- Negativ (2-7/9/11): fehlend, abgelaufen, zukuenftig, falscher User/Tenant/Agent, manipulierter Tenant, fehlende userId (missing-identity, kein Raten). Fall 8 (revoked-Flag) = N/A (Modell kennt nur Zeitfenster — dokumentiert statt erfunden). Fall 10 (manipulierter agentId) = Discovery-No-Match (ValueError, keine Ausfuehrung — staerker als DENIED; Fall 7 deckt registrierten Fremd-Agent per DENIED).
- P7-Zusammenspiel (14/15): INACTIVE + UNKNOWN-Status trotz Entitlement blockiert (keine Ausfuehrung).
- Transient (16): Store-Raise -> Raise (kein DENIED-Outcome), FAILED persistiert, KEIN ENTITLEMENT_DENIED-Eintrag, keine Ausfuehrung.
- Idempotenz (17): Duplikat-terminal -> gespeichertes COMPLETED, KEIN neuer Run, Resolver NICHT aufgerufen (Re-check umgeht Idempotenz nicht).
- Lazy-Resolver-Bau ohne AWS-Kontakt (Test 20).

## 6. Audit (Schritt 12 — EXISTING-Modell, keine Secrets)

- DENIED: warning-Log (workId/agentId/userId/tenantId/reason/attempt — KEINE Secrets/Credentials/Header/JWT/Token/Keys; Entitlements enthalten keine) + FAILED-Item (Fehler-Typ + Nachricht) + Outcome (denied/reason/result_reference-Kette).
- AUTHORIZED: kein Extra-Event (Ausfuehrungs-Logs/Audit bestehen; kein Log-Spam).
- Correlation: workId + attempt_no + result_reference + processing/execution-Chain (EXISTING-IDs durchgereicht, kein neues Schema).

## 7. Regression (Schritt 13) / Scope (Schritt 14)

- Neu: 20/20 GRUEN. Gesamt-Suite: 418 passed (398 + 20), 8 skipped; 15 failed + 1 ERROR = IDENTISCHE Menge wie Baseline (pre-existing, u.a. platform_handlers-Modul mit Standalone-Collection-Problem — vor/nach per stash-Vergleich identisch belegt).
- Scope: NUR Code (Worker-Auth-Modul + Pipeline-Integration + Handler-Verdrahtung) + Tests + Reports. KEIN TF/AWS/Cognito/DDB/GW, KEINE Migration, KEINE Secrets/Keys, KEINE Live-E2E (verboten wie vorgegeben).

## 8. Folge-Gaps (UNVERAENDERT aus P6-R8, naechster Kandidat)

Credential-Einfuehrung (P03-C1-Typ) + Worker-Nachpruefung JETZT ERLEDIGT -> naechster Gate-Kandidat: Agent Sandboxing (In-Process-Rollen-Teilung) BZW. Offer/APIProfile-CRUD per P6-R8-Reihenfolge (Status-Norm P7 + Worker-Re-check P8 = Enforcement-Basis steht).

**HARD STOP (keine weiteren Gates in diesem Auftrag).**
