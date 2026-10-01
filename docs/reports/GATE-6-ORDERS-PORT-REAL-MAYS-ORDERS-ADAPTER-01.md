# GATE-6 — OrdersPort / RealMaysOrdersAdapter

STATUS: GREEN

- Date/Time: 2026-10-01 18:00 UTC
- Branch + HEAD (RIS): main, 6f0b808 + Gate-6-Aenderungen (s. P)
- MO-Stand: 0 Aenderungen (SHAs beider Funktionen `F5rRldqx…`, Clone clean/ignoriert)
- Scope: Port konkretisieren, Real-Adapter + delegierende Agent-Function, minimaler POST auf eigener Route, Tests, Live-Nachweis. Gate 5 unangetastet (nur Bootstrap-Registrierung dazu). Kein Foundation-Apply (gezielt), kein Domain-Agent, kein ATS.
- Sections: A–Q unten
- Findings: Voller Pfad live: SQS→Worker→Orders-Function→Port→Real-Adapter→eigene API→MO-Tabelle→Result (POST 201→CONFIRMED→GET→CANCELLED, 2 Pipeline-Runs COMPLETED)
- Evidence: 18 Unit-Tests, API-Responses, DDB-Items, Worker-Logs, TF-State
- Classification: GREEN
- Terraform/AWS Checks: validate GREEN; gezielte Plaene (Reader: 1+2; Rest per CLI dokumentiert); 0 destroys; MO 0
- Git Status (RIS): nur Gate-6-Dateien (s. P)
- Files Changed: `agents/orders/{real,function}.py` (neu), `__init__`, `pipeline.py` (Bootstrap), `lambda/orders_reader.py` (POST), `modules/orders_reader` (+Route/Policy), `tests/test_real_orders_adapter.py` (neu), Reports
- Open Questions: POST-Reconciliation nach Timeout (OPEN, kontrolliert kein Retry); kein serverseitiger Idempotency-Key (OPEN, belegt); Tenant-Feld serverseitig absent (Isolation unsererseits)
- Risks: keine neuen (JWT-Routen, Least-Privilege, keine Secrets, Test-User geloescht)
- Next Actions: Commit → Folgetor (ATS/Domain-Ausbau)
- Resume Point: nach Commit HARD STOP

## A. Ausgangslage

Gate 5 GREEN (Runtime-Pfad + Idempotency). Offener Auftrag: Port-Anbindung. Bestand: OrdersPort-Abstract + DevelopmentOrdersAdapter (+Tests) vorhanden; Real-Adapter nur als Docstring-Referenz (nicht implementiert); kein HTTP-Client im Lambda-Pfad (jobsearch nutzt aiohttp — ungeeignet); Secrets per Env (kein Vault im Pfad).

## B. OrdersPort Bestand

`submit_order(work_item, capability, payload, tenant_id, actor_id, idempotency_key) -> OrderResult`, `get_order_status(order_id)`, `can_handle`, `port_id`; `OrderResult{success, order_id, result_type, reason, data}`. Unveraendert — Real-Adapter implementiert denselben Contract.

## C. DevelopmentOrdersAdapter

Unveraendert (Referenz + Tests gruen). Lokaler Dedup via dict (nicht DDB) — nur Dev-Semantik, kein Vorbild fuer live.

## D. Mays-Orders Contract (extern, nachgewiesen)

Eigene API (frontet live Tabelle): POST /orders → 201 + `ord_*` + PENDING (live 201); GET /{id} → 200 (live); PATCH /status → 200/409 (live); Validierung Integer≥1, 400-Codes, JWT auf allen Routen, Status sicht (PENDING→…→CANCELLED). Interne Dateien NICHT uebernommen (nur beobachtetes Verhalten).

## E. Contract Mapping

| Port | MO | Ergebnis |
|---|---|---|
| submit/orders.create | POST /orders | 201→PENDING-Result; 400→ERROR; 429/5xx/Timeout→POST_UNKNOWN kontrolliert (safe_to_retry False) |
| get_order_status | GET /orders/{id} | 200→APPROVED+order; 404→None; 5xx/Timeout→Transient (retrybar) |
| submit/orders.cancel | PATCH …/status {CANCELLED} | 200→APPROVED; 409→ERROR (kontrolliert) |
| Input/Output | Request/Response | 1:1 (customer/items/currency; orderId/status/amounts) |
| Error | HTTP/Domain | Tabelle in real.py (`_map_response`); nichts verschluckt |
| Idempotency | Server | OPEN: kein Key, jedes POST neue ID (live belegt: ord_a≠ord_b) |
| Correlation | Header/Meta | OPEN serverseitig (keine Felder); Kette via workId/processing/result_reference |
| Tenant/User/Actor | Claim/Context | JWT unsererseits; MO-Modell kennt keinen Tenant (Isolation unsere Aufgabe) |

## F. Authentication

Bestehender Weg: JWT (eigener Pool). Adapter nimmt `token_provider` (Tests: Fake; live: Temp-User, danach geloescht). Keine Secrets in Git/Reports/Tests/Logs (nur `Bearer`-Header im Transport, nie geloggt).

## G. Tenant/User/Actor/Correlation

Aus WorkItem: tenantId/requestedBy/workId/idempotencyKey (+processing via Pipeline-Result). An MO: nichts Identitaetsfremdes (kein Feld dafuer); Kontext in `OrderResult.data` + DDB-Referenzkette. Keine Identitaet neu erfunden.

## H. Idempotency

AgentRun-Key (Gate 5) ≠ Order-Key (MO vergibt `ord_*`). POST nicht idempotent (belegt). Regel: POST_TIMEOUT/Unsicher → kontrolliert, NIE blindes Re-POST. GET idempotent, PATCH konvergent (Guard→409). Retry erzeugt keine zweite Order (Adapter wirft bei POST nie Transient).

## I. Error Mapping

2xx→Erfolg; 400/401/403/404/409→kontrolliert ERROR (Codes erhalten); 429/502/503/504/Timeout/Connect (ausser POST)→`TransientOrdersError(operation, status)`; Unbekannt→ERROR mit Payload. Runtime-kompatibel (PERMANENT-Codes ⊆ Pipeline-Set).

## J. Retry Semantics

Keine zweite Engine. Transient→Runtime-RETRY (SQS), Kontrolliert→CONSUMED. Timeout-nach-POST: kontrolliert (kein Doppel-POST); Reconciliation OPEN (Liste+Match moeglich, nicht implementiert).

## K. RealMaysOrdersAdapter

`agents/orders/real.py` (~230 Zeilen): stdlib-urllib (keine Deps), injizierbarer Transport/Token/Base-URL (Default eigene API), `can_handle{create,status,cancel}`. Keine URLs/Credentials im Agent-Code.

## L. Tests

`tests/test_real_orders_adapter.py`: 18 Tests (Contract, Mapping 201/400/503/Timeout/404/500/409, Capability-Guard, Transport-No-Secret (Auth-Header + Body ohne Token), Idempotency-OPEN-Beleg, Function-Delegation + Transient-Propagation + Engine-Wrap-Norm, Reader-POST 201/400/400) → **18/18 PASS**. Suite gesamt **293 passed** (4 pre-existing deselected).

## M. Live Evidence

1. Adapter-POST (eigene API, Temp-User): 201 `ord_0035…` PENDING → Worker → CONFIRMED (GET 200).
2. Pipeline `gate6-e2e-002` (orders.status, Token im Payload): COMPLETED attempt 1, Result mit Order (CONFIRMED) in DDB.
3. Pipeline `gate6-e2e-003` (orders.cancel): COMPLETED → Order CANCELLED (GET-verifiziert).
4. Vorlauf-Fund: Engine-Wrap (payload.payload + auth-Verlust) → `_payload`/`_token`-Norm (Unit-testiert).
5. Erster Live-Run FAILED korrekt (VALIDATION_ERROR kontrolliert, kein Retry) — Guardrail belegt.
6. DDB-Arbeitsitems + Test-User danach geloescht; Test-Order CANCELLED (nicht loeschbar — Praezedenz Gate 3/4).

## N. Security

Keine Secrets in Repo/Logs (Shred verifiziert); Temp-User beider Pfade geloescht; neue Rechte minimal (eigene Rolle +SQS-Send auf EINE fremde Queue +PutItem eigene Tabelle-nah; Routen JWT). Fremde IAM/TF/Lambda/SQS/State: 0.

## O. Mays-Orders Änderungen = 0

SHAs `F5rRldqx…` beider Funktionen bestaetigt; Clone clean; kein TF/State-Kontakt (lesen nur S3-Lock frueherer Gates).

## P. Git

M: `agents/orders/{__init__,real✦,function✦}`, `agents/runtime/pipeline.py`, `lambda/orders_reader.py`, `terraform/modules/orders_reader/{main,variables}.tf`. Neu: real.py, function.py, tests/test_real_orders_adapter.py, Reports. ✦neu. Secret-Scan sauber; Zips/States ignoriert bzw. /tmp.

## Q. Gate Decision

| Bereich | Ergebnis |
|---|---|
| OrdersPort | GREEN |
| Development Adapter | GREEN |
| Mays-Orders Contract | GREEN |
| Contract Mapping | GREEN |
| Authentication | GREEN |
| Tenant Context | GREEN |
| User/Actor Context | GREEN |
| Correlation | GREEN |
| Idempotency | GREEN (mit OPEN dokumentiert) |
| Error Mapping | GREEN |
| Retry Semantics | GREEN |
| RealMaysOrdersAdapter | GREEN |
| Unit Tests | GREEN (18/18) |
| Integration Tests | GREEN (live) |
| Live E2E | GREEN |
| Security | GREEN |
| Mays-Orders unchanged | GREEN |
| Git | GREEN |

**Entscheidung: GREEN** — Port klar, beide Adapter gleicher Contract, Contract nachgewiesen, Auth/Kontext/Fehler/Retry sauber, Live-Durchstich vollständig, MO unverändert.

- Report: `docs/reports/GATE-6-ORDERS-PORT-REAL-MAYS-ORDERS-ADAPTER-01.md` (+ Log folgt)
- Commit: folgt
- Offen: POST-Reconciliation (OPEN); serverseitiger Idempotency-Key (OPEN); Test-Order CANCELLED (bleibt)
- Nächstes Gate: ATS/Domain-Ausbau (Empfehlung)

**DANN HARD STOP.**
