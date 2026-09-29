# RIS-API-HANDLER-02

## 1. Ergebnis

EINE Lambda (`agent`) beantwortet ALLE API-Routen UND konsumiert SQS (Dispatch
nach Event-Form). 5 API-GW-Routen vorhanden; Handler kennt mehr Pfade (u. a.
Execute) OHNE GW-Route. Handler spricht REST-Event (`httpMethod`/`path`), GW-
Integration liefert Payload 2.0 (`routeKey`/`rawPath`) — Format-Bruch PROVEN.
JWT via Authorizer, Claims in `requestContext.authorizer.jwt.claims`. KEINE
Mays-Orders-Verbindung im Pfad.

## 2. Route → Handler Matrix

| Method | Route | Lambda | Handler | Service | Status |
|---|---|---|---|---|---|
| GET | /health | agent | — (kein Branch → 404) | — | GW-Route ohne Handler |
| GET | /platform | agent | `_handle_platform` (static info) | — | OK (JWT-Gate, keine Identitätsprüfung) |
| GET | /me | agent | `_handle_me` (401 ohne sub) | user context | OK |
| GET | /me/profile | agent | `_handle_me_profile` → `_get_user_profile` | DynamoDB user-profile | OK |
| GET | /agents | agent | `_handle_agents` → entitlements + catalog | DynamoDB ×2 | OK |
| POST | /api/agents/{id}/execute | agent (NUR Handler-intern) | `_execute_agent` (401/403/404-Gates) | DynamoDB + SQS | KEINE GW-Route (NOT FOUND auf GW-Ebene) |
| GET/POST/PUT/DELETE | /me/jobsearches* | agent (NUR Handler-intern) | `_handle_jobsearch_*` | JobSearch-Repo | KEINE GW-Route |
| POST/GET | /work* | agent (NUR Handler-intern) | `_create_work`/`_get_work` | Work-Items | KEINE GW-Route |

## 3. Lambda Inventory

| Lambda | Runtime | Handler | Trigger | Zweck |
|---|---|---|---|---|
| `agent` (`${project}-${env}-agent`, lambda/main.tf:163, python3.14/handler.lambda_handler per Default) | python3.14 | `handler.lambda_handler` (`lambda/handler.py:handler`) | API-GW (5 Routen) + SQS-Mapping (batch 5) | Gesamte Platform-API + Work-Verarbeitung |

EINE API-Lambda (keine weiteren). Env: 4 Tabellen-Namen + Queue-URL + LOG_LEVEL.

## 4. API Gateway Mapping

| Route | Integration | Lambda | Permission | Evidence |
|---|---|---|---|---|
| 5 Routen (health NONE, Rest JWT) | `AWS_PROXY` → `invoke_arn`, **payload 2.0** (api/main.tf:35-40) | agent | api-Modul (execution_arn, korrekt) | TF-Adressen + Handler-Dispatch |

## 5. Event Model

Handler nutzt: `httpMethod`, `path`, `pathParameters.*`, `body` (JSON),
`requestContext.authorizer.jwt.claims` (sub/email/custom:tenant_id/
cognito:groups), SQS-`Records[].body/messageId`. NICHT genutzt (trotz v2):
`routeKey`, `rawPath`, `requestContext.http` — PROVEN per Grep (0 Treffer).
BRUCH: GW sendet v2 (kein `httpMethod`/`path`) → Dispatch fällt auf `/`+GET
→ 404 für GW-getriggerte Calls (statisch PROVEN, kein Live-Beleg).

## 6. Cognito / JWT

Authorizer `jwt` (Issuer = Pool-Endpoint, Audience = Client-ID; api/main.tf:
21-33) an 4/5 Routen (health NONE). Handler: `_extract_user_context`
(requestContext→authorizer→jwt→claims; sub→userId, email, custom:tenant_id,
cognito:groups robust) — userId-Pflicht (401) in me/profile/agents/execute;
Entitlement-Gate (403) in agents/execute; tenantId-Scoping in Repo-Calls.

## 7. Route Traces

A) `/me/profile`: GW(JWT) → agent → `_handle_api_event` → user_context (401)
→ `_get_user_profile(userId, tenantId)` → 200/404.
B) `/agents`: GW(JWT) → agent → user_context → `_get_entitlements` +
`_get_agent_catalog` → gefilterte Liste.
C) Execute (NUR Handler-intern, KEINE GW-Route): → user_context → Entitlement-
403 → Katalog-404 → WorkItem (uuid, QUEUED, idempotencyKey) → DynamoDB-put
(WORK_ITEMS_TABLE) + SQS-send (WORK_QUEUE_URL, MessageAttributes workType/
agentId) → 202. Weiter S. 8.
D) `/me`: GW(JWT) → agent → user_context → 200-Echo (kein Repo-Zugriff).

## 8. SQS / Worker Chain (PROVEN)

API-`_execute_agent` → SQS (`WORK_QUEUE_URL`) → Event-Mapping
(`sqs_mapping`, batch 5, gleiche `agent`-Lambda) → `_handle_sqs_event`
(Records[].body → WorkItem) → `_process_work_item` → `AGENT_BODY.execute`
(handler.py:767). EINE Lambda für API + Worker (keine Worker-Lambda).

## 9. Mays-Orders Boundary

KEINE Verbindung (Grep über handler/lambda/agent_body leer). Agent-Execution
≠ Mays-Orders (Annahme explizit NICHT getroffen).

## 10. Offene Punkte

v2-vs-REST-Bruch (Laufzeit-Wirkung UNVERIFIED); `/health`-404; Execute-Routen
ohne GW-Anbindung (Absicht UNKNOWN); JobSearch-/Work-Routen ohne GW-Anbindung;
SQS-Receive-Recht-Herkunft (Vor-Audit); batch_size-Angemessenheit (Runtime).

## 11. Schlussfolgerung

1. `agent`-Lambda beantwortet alle API-Routen. 2. Ja — gemeinsame API-Lambda.
3. Nein (eine Lambda, zwei Trigger). 4. Code erwartet REST (`httpMethod`/`path`),
   GW liefert v2 (Bruch PROVEN). 5. `_extract_user_context` (jwt.claims).
6. `_execute_agent` → DynamoDB-put + SQS-send → 202. 7. SQS-Mapping → gleiche
   Lambda → AgentBody. 8. Nein (kein Beleg). 9. Fehlt: v2-Kompatibilitäts-
   Entscheidung, GW-Anbindung Execute/JobSearch/Work, SQS-Receive-Herkunft.

---

*Analyse: RIS-API-HANDLER-02 · Muster aus AI_AUDITLOG.md · nur Nachgewiesenes ·
kein Umbau · keine AWS-Mutation.*
