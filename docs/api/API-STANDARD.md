# Mays-RIS API Standard — Plattform-Anwendung (konsolidiert)

Meta-Standard (Format-, Versions-, Fehler-Regeln): `API_DOCUMENTATION_STANDARD.md`
(gilt weiter). Diese Datei wendet ihn auf die live Plattform an und benennt
Abweichungen/OPENs ehrlich.

## 1. Routen (live, `mays-ris-dev-api`, JWT ausser /health)

| Route | Ziel | Erfolg |
|---|---|---|
| GET /health | agent | 200 (NONE) |
| GET /platform, /me, /me/profile, /agents | agent | 200 (JWT) |
| GET /orders, GET /orders/{orderId} | orders-reader | 200 |
| POST /orders | orders-reader | 201 (PENDING + SQS-Anstoss) |
| PATCH /orders/{orderId}/status | orders-reader | 200 / 409 |
| POST /me/profile | agent | 201 (explizite Provisionierung) / 409 (exists) |
| PUT /me/profile | agent | 200 (nur v1-Felder) / 400 / 404 (kein Upsert) |
| POST /me/documents | agent | 200 (Presigned-PUT, 15 min) / 400 / 401 |
| GET /me/documents/{docId} | agent | 200 (Presigned-GET) / 400 / 404 / 401 |
| DELETE /me/documents/{docId} | agent | 200 / 404 / 401 |

Registrierung (Gate 10): Cognito SignUp (self-service, Pool erlaubt) →
Confirm (E-Mail-Code NUR wenn Pool Auto-Verification konfiguriert — seit Gate 11
KONFIGURIERT: Template live, Versand AWS-managed; Inbox-Eingabe NOT PROVEN) →
Login (USER_PASSWORD_AUTH) → JWT → POST /me/profile (Conditional Write, 409 bei
Duplikat) → GET /me/profile. NIEMALS Auto-Provisioning durch Reads.

## 2. Auth / Claims (verwendet)

`Authorization: Bearer <JWT>` (Cognito-Pool `users`). Claims in Nutzung:
`sub` (userId), `email`, `cognito:groups`, `custom:tenant_id`. Keine
Signup-/Login-Routen im Repo (User extern verwaltet — CURRENT-Stand).

## 3. Fehler (verwendet)

`{"error":{"code","message","details?"}}`; Codes live belegt:
VALIDATION_ERROR(400), ORDER_NOT_FOUND(404), INVALID_TRANSITION/CONFLICT(409),
INTERNAL_ERROR(500). Kein Stacktrace nach aussen.

## 4. Verbindliche Semantik

Synchroner API-Aufruf ≠ WorkItem ≠ Agent Run ≠ Attempt (s. Architektur).
POST-Antwort bedeutet NICHT Verarbeitung (nur Registrierung + Queue).

## 5. Idempotency / Pagination / Filter (Stand)

- HTTP-Idempotency-Keys: NICHT implementiert (OPEN). Schutz nur via
  Runtime-Idempotency (gleiche workId) bzw. dokumentierte POST-Regel.
- Pagination: `limit` (1..100) auf GET /orders; `nextToken`-Mechanik im
  Reader-Code vorhanden, Token-Roundtrip live NICHT nachgewiesen (OPEN).
- Filter: JobSearch-List akzeptiert `status`; sonst keine Filter (OPEN).

## 6. Abweichungen (OPEN, nicht heimlich korrigiert)

- `jobsearch/openapi.yaml` beschreibt `/v1/jobs/*` (externer Job-Stil) und
  deckt KEINE Plattform-Routen (/me, /orders, …) ab — kein Widerspruch im
  Code, aber Lücke: Plattform-OpenAPI fehlt (OPEN).
- API-Doc vs Runtime: keine Widersprüche festgestellt (Codes/Routen/Claims
  code-geprüft).
