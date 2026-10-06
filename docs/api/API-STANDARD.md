# Mays-RIS API Standard — Plattform-Anwendung (konsolidiert)

Meta-Standard (Format-, Versions-, Fehler-Regeln): `API_DOCUMENTATION_STANDARD.md`
(gilt weiter). Diese Datei wendet ihn auf die live Plattform an.

**Vertrag:** Alle Routen, Auth-Typen, Request-/Response-Felder und Statuscodes
in diesem Dokument sind aus drei Quellen abgeglichen — Terraform
(`terraform/modules/api/main.tf`, `terraform/modules/orders_reader/main.tf`),
Handler-Dispatch (`lambda/handler.py`, `lambda/orders_reader.py`) und den
Tests. Nicht abgeglichenes wird als **OPEN** markiert, nicht behauptet.
Konsistenz wird von `tests/test_p20_api_contract_consistency.py` geprüft.

- Stand: 2026-10-05, verifiziert gegen Gateway `aboqolpm0f` (28 Routen live)
- Basis-API-ID: `aboqolpm0f`, Stage `$default`, Region `eu-central-1`
- Basis-URL: `https://aboqolpm0f.execute-api.eu-central-1.amazonaws.com`
  (Stage `$default` ⇒ **kein** Stage-Pfad in der URL)

## 1. Zwei Auth-Flächen, 28 Routen

Es gibt **zwei** Autorisierungstypen, nicht einen:

| Typ | Anzahl | Credential |
|---|---|---|
| `JWT` | 26 | Cognito JWT (`Authorization: Bearer <JWT>`) |
| `NONE` | 2 | `/health` (keine) und die Machine-Route (`ris_…`-Credential) |

`POST /v1/m2m/agents/{agentId}/execute` ist ebenfalls `NONE`, weil sie mit
einem opaken `ris_…`-Credential arbeitet, nicht mit einem JWT. Die frühere
Fassung dieses Dokuments nannte nur `/health` als einzige Ausnahme und war
damit **unvollständig**. Beide `NONE`-Routen nehmen ein `Authorization`-Header
entgegen — die eine prüft nichts, die andere ein Credential.

Zwei Lambda-Backends:

| Backend | Routen | Zweck |
|---|---|---|
| `agent` (`mays-ris-dev-agent`) | 24 | Identity, Profile, Dokumente, Agents, APIProfiles, Credentials, Introspection, Machine |
| `orders-reader` (`mays-ris-dev-orders-reader`) | 4 | `/orders*`, read-mostly |

## 2. Plattform-Routen (agent)

| Route | Auth | Erfolg | Weitere Codes |
|---|---|---|---|
| `GET /health` | NONE | 200 | — |
| `GET /platform` | JWT | 200 | — |
| `GET /me` | JWT | 200 | — |
| `GET /me/profile` | JWT | 200 | 404 (kein Profil) |
| `POST /me/profile` | JWT | 201 | 409 (existiert), 400 (kein JSON) |
| `PUT /me/profile` | JWT | 200 | 400 (kein v1-Feld), 404 (kein Upsert) |
| `POST /me/documents` | JWT | 200 (Presigned PUT) | 400, 500 |
| `GET /me/documents/{docId}` | JWT | 200 (Presigned GET) | 400, 404, 500 |
| `DELETE /me/documents/{docId}` | JWT | 200 | 400, 404, 500 |
| `GET /agents` | JWT | 200 | — |
| `GET /v1/introspection` | JWT | 200 | 401, 404, 503 |
| `POST /v1/apiprofiles` | JWT | 201 | 400, 403, 409 |
| `GET /v1/apiprofiles` | JWT | 200 | — |
| `GET /v1/apiprofiles/{apiProfileId}` | JWT | 200 | 403, 404 |
| `PATCH /v1/apiprofiles/{apiProfileId}` | JWT | 200 | 400, 403, 404 |
| `POST /v1/apiprofiles/{apiProfileId}/status` | JWT | 200 | 400, 403, 404, 409 |
| `POST /v1/apiprofiles/{apiProfileId}/credentials` | JWT | 201 (200 bei Idempotenz-Wiederholung) | 400, 403, 404, 409 |
| `GET /v1/apiprofiles/{apiProfileId}/credentials` | JWT | 200 | 400, 403, 404 |
| `GET /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}` | JWT | 200 | 400, 403, 404 |
| `POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/rotate` | JWT | 201 (200 bei Wiederholung) | 400, 403, 404, 409 |
| `POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/disable` | JWT | 200 | 403, 404, 409 |
| `POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/enable` | JWT | 200 | 403, 404, 409 |
| `POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/revoke` | JWT | 200 | 403, 404, 409 |

### 2.1 Machine API

| Route | Auth | Erfolg | Weitere Codes |
|---|---|---|---|
| `POST /v1/m2m/agents/{agentId}/execute` | NONE (`ris_…`-Credential) | 202 | 401, 403, 500, 503 |

Request-Body (alle Felder optional):
`{"capability": string, "payload": object, "idempotencyKey": string}`

Antwort 202: `{"workId": string, "status": string, "requestId": string}`

`202` heißt **nicht** „fertig", sondern „WorkItem angelegt und eingereiht".
Der Status des Laufs wird asynchron erreicht; dieser Endpunkt ist read-only in
seiner eigenen Antwort.

HTTP-Semantik der Credential-Prüfung:
- **401** — Credential unbekannt, ungültig, fehlend oder fehlerhaft. Ein
  Cognito-JWT auf dieser Route ist **immer** 401 (drei Punkt-Segmente können
  kein opakes `ris_…` sein).
- **403** — Credential bekannt, aber unbenutzbar: disabled, revoked, abgelaufen,
  Profil nicht `ACTIVE`, Tenant-/Owner-Mismatch, kein Entitlement, Agent nicht
  ausführbar.
- **503** — Store-/Infrastrukturfehler. **Niemals** 401/403: ein nicht
  erreichbarer Store darf nicht als schlechtes Credential gemeldet werden.

### 2.2 Credential Management

Rollen sind aus den Cognito-Gruppen abgeleitet, nicht aus einem Rollen-Claim:

| Rolle | Quelle | Rechte |
|---|---|---|
| `owner` | kein Match | nur eigene Profile/Credentials |
| `staff` | Gruppe `Staff` | Support mit `reason`; **darf nicht anlegen, nicht revoken, nicht ausstellen** |
| `admin` | Gruppe `admins` | tenant-scoped; cross-tenant nur mit `reason` |

Header:

| Header | Wirkung |
|---|---|
| `X-Api-Profile` | Auswahlhinweis; **untrusted** — wird gegen den verifizierten Kontext geprüft. Abweichung ⇒ 400 `Profile mismatch` |
| `Idempotency-Key` | bei `POST` Issue und Rotate; ≤ 128 Zeichen, nicht leer. Wiederholung ⇒ 200 + `"duplicate": true` statt 201 |
| `X-Correlation-Id` | Korrelation; Fallback auf Gateway-`requestId` |

Body-Felder:

| Route | Erlaubte Felder | Pflicht |
|---|---|---|
| `POST /v1/apiprofiles` | `name`, `description`, `targetOwner`, `reason` | `name` |
| `PATCH /v1/apiprofiles/{apiProfileId}` | `name`, `description`, `reason` | — |
| `POST /v1/apiprofiles/{apiProfileId}/status` | `status`, `reason` | `status` |
| `POST /v1/apiprofiles/{apiProfileId}/credentials` | `label`, `expiresAt`, `clientRef`, `reason` | `expiresAt` |
| `POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/rotate` | `expiresAt`, `label`, `reason` | `expiresAt` |
| `POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/disable` | `reason` | — (Staff nur mit `reason`) |
| `POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/enable` | `reason` | — |
| `POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/revoke` | `reason` | — (admin-only) |

Unbekannte Felder ⇒ **400** `Unknown fields: …`. Absichtlich *nicht* akzeptiert:
`clientRef`/`expiresAt` beim Anlegen eines Profils durch den Owner (nur Admin).

Credential-Metadaten (Antwort, 20 Felder): `credentialId`, `apiProfileId`,
`ownerUserId`, `tenantId`, `label`, `credentialType`, `status`, `clientRef`,
`createdAt`, `updatedAt`, `expiresAt`, `lastUsedAt`, `revokedAt`, `revokedBy`,
`revokeReason`, `disabledBy`, `rotationOf`, `idempotencyKey`, `createdBy` —
plus `digest` und `secret` **nur** beim Ausstellen/Rotieren. `digest` und
`secret` verlassen den Store nie (`_public_metadata` entfernt `digest`).

Credential-Lifecycle: `ACTIVE ⇄ DISABLED → REVOKED`, `REVOKED` ist terminal
(Reaktivierung ⇒ 409). Rotation revokiert das alte und legt ein neues `ACTIVE`
an (`rotationOf` verknüpft).

APIProfile-Lifecycle: `PENDING → ACTIVE | DISABLED | REVOKED`,
`ACTIVE ⇄ DISABLED`, `REVOKED` terminal. Aktivierung und Revoke sind
**admin-only**.

### 2.3 Introspection

`GET /v1/introspection` ist read-only und gibt die auflösbaren Fähigkeiten des
Aufrufers zurück. Pflicht-Keys in **jedem** Kontext: `context`, `subject`
(`userId`, `tenantId`), `capabilities`, `validity.checkedAt`, `resolution`
(`selectedBy`, `resolvedAt`, `request`). Im Kontext `profile` zusätzlich
`profile` (`apiProfileId`, `name`, `status`, `clientRef`, `expiresAt`,
`offerRefs`), `offers`, `validity.profileExpiresAt`; je Fähigkeit
`capabilities[]` mit `scopeRestricted` und `expiresHint`.

Kontextwahl: `context` ist `human` ohne `X-Api-Profile`, sonst `profile` bzw.
`credential`.

## 3. Orders-Routen (orders-reader)

| Route | Auth | Erfolg | Weitere Codes |
|---|---|---|---|
| `GET /orders` | JWT | 200 | 400 (`limit` nicht Integer oder nicht 1..100) |
| `GET /orders/{orderId}` | JWT | 200 | 400, 404 `ORDER_NOT_FOUND` |
| `POST /orders` | JWT | 201 (`PENDING` + SQS-Anstoß) | 400, 500 |
| `PATCH /orders/{orderId}/status` | JWT | 200 | 400, 404, 409 (`INVALID_TRANSITION`, `CONFLICT`) |

`GET /orders` Antwort: `{"orders": [...], "count": number}`, Query-Parameter
`limit` (Default 20, 1..100).

Statuswerte: `PENDING`, `CONFIRMED`, `PROCESSING`, `SHIPPED`, `DELIVERED`,
`CANCELLED`. Übergänge: `PENDING→{CONFIRMED,CANCELLED}`,
`CONFIRMED→{PROCESSING,CANCELLED}`, `PROCESSING→{SHIPPED}`, `SHIPPED→{DELIVERED}`;
`DELIVERED` und `CANCELLED` sind Endzustände.

## 4. Fehlerformat — zwei Formen, ehrlich benannt

Das ist die wichtigste Korrektur gegenüber der alten Fassung.

| Backend | Fehlerformat |
|---|---|
| `orders-reader` | `{"error": {"code": string, "message": string, "details"?: object}}` |
| `agent` | `{"error": "<string>"}` |

Der `agent`-Pfad nutzt durchgängig String-Fehler, z. B.
`{"error": "Not found"}`, `{"error": "Forbidden"}`,
`{"error": "Temporarily unavailable"}`. Codes wie `VALIDATION_ERROR` oder
`ORDER_NOT_FOUND` existieren **nur** im orders-reader-Pfad.

Codes live belegt (orders-reader): `VALIDATION_ERROR` (400),
`ORDER_NOT_FOUND` (404), `INVALID_TRANSITION` (409), `CONFLICT` (409),
`INTERNAL_ERROR` (500).

Die Meta-Standard-Form `{"error":{"code","message"}}` ist damit **nicht**
plattformweit erfüllt. Das ist eine bewusst dokumentierte Abweichung
(siehe §8, OPEN-2), keine Behauptung.

Gateway-eigene Fehler (401/404 bei fehlendem Token bzw. unbekannter Route)
stammen von API Gateway, nicht vom Handler: `{"message": "Unauthorized"}` /
`{"message": "Not Found"}`.

Statuscode-Konventionen im `agent`-Pfad:

| Code | Bedeutung | Quellcode |
|---|---|---|
| 400 | unbekanntes/fehlendes Feld, ungültiges JSON, Header-Konflikt | `_aprof_fail`, `_cred_fail`, `_aprof_body`, `_cred_body` |
| 401 | kein `userId` im JWT (nur bei JWT-Routen) | `_extract_user_context` |
| 403 | Rolle/Status/Tenant verbietet die Aktion | `_aprof_fail`, `_cred_fail` |
| 404 | fehlend **oder** fremd (neutral, kein Oracle) | `_aprof_fail`, `_cred_fail` |
| 409 | Konflikt, ungültige Transition, Store-Ausfall als Konflikt | `_aprof_fail`, `_cred_fail` |
| 503 | Store nicht konfiguriert/nicht erreichbar | `_aprof_store`, `_cred_sources`, `_machine_bearer`-Umfeld |
| 500 | unerwartet, ohne Stacktrace nach außen | `logger.exception` + neutraler Text |

Der neutrale 404 ist Absicht: für `owner` sind „fremd" und „existiert nicht"
nicht unterscheidbar. Für `admin`/`staff` liefert derselbe Fall 403.

## 5. Auth / Claims

`Authorization: Bearer <JWT>` aus Cognito-User-Pool `users`. Claims in Nutzung:
`sub` (userId), `email`, `preferred_username`, `cognito:groups`,
`custom:tenant_id`. Der JWT-Authorizer prüft `issuer` und `audience`; eine
Scope-Prüfung findet **nicht** statt — Autorisierung erfolgt im Handler über
`cognito:groups`.

Keine Signup-/Login-Routen im Repo; der User Pool erlaubt Self-Service-SignUp,
der Bestätigungsversand ist AWS-managed (Inbox-Eingabe nicht als PROVEN geführt).

Registrierung: SignUp → Confirm (E-Mail-Code) → Login (USER_PASSWORD_AUTH) →
JWT → `POST /me/profile` (Conditional Write, 409 bei Duplikat) → `GET /me/profile`.
**Niemals** Auto-Provisioning durch Reads.

## 6. Verbindliche Semantik

Synchroner API-Aufruf ≠ WorkItem ≠ Agent Run ≠ Attempt. Eine POST-Antwort
bedeutet **nicht** Verarbeitung, nur Registrierung plus Queue-Anstoß.

`/health` ist bewusst abhängigkeitsfrei (kein DynamoDB-, Cognito- oder
SQS-Zugriff). Ein Probe-Aufruf, der an einer Abhängigkeit hängt, würde das
Target während eines Ausfalls der Abhängigkeit als ungesund melden, obwohl die
Lambda startfähig ist. Abhängigkeits-Erreichbarkeit meldet `GET /platform`
(JWT-geschützt), nicht der Liveness-Probe.

## 7. Idempotency / Pagination / Filter

- **HTTP-Idempotency:** implementiert für Credential-Ausstellen und -Rotation
  (`Idempotency-Key`, siehe §2.2). **Nicht** implementiert für `POST /orders`,
  `POST /me/profile` (dort via Conditional Write → 409) und die Status-Aktionen.
- **Pagination:** `limit` (1..100, Default 20) auf `GET /orders`. Es gibt
  **keine** `nextToken`-Mechanik: im orders-reader-Code existiert weder
  `nextToken` noch `LastEvaluatedKey`. Die frühere Fassung dieses Dokuments
  behauptete das Gegenteil; die Behauptung war falsch (OPEN-4).
- **Filter:** `status` wird auf `PATCH /orders/{orderId}/status` als
  Zielfeld akzeptiert, nicht als Listenfilter. Weitere Filter existieren nicht.

## 8. Abweichungen und OPENs (nicht heimlich korrigiert)

- **OPEN-1 — Plattform-OpenAPI fehlt.** `jobsearch/openapi.yaml` beschreibt
  `/v1/jobs/*` eines externen Dienstes und deckt **keine** Plattform-Route ab.
  Dieses Dokument ist Prosa, kein maschinenlesbarer Vertrag.
- **OPEN-2 — Fehlerformat uneinheitlich.** `orders-reader` nutzt
  `{"error":{"code","message"}}`, `agent` nutzt `{"error":"<string>"}` (§4).
  Vereinheitlichen wäre ein API-Redesign und ist ausdrücklich nicht Teil dieses
  Gates.
- **OPEN-3 — Drei Routen ohne Terraform-Definition.** `POST /me/documents`,
  `GET /me/documents/{docId}` und `DELETE /me/documents/{docId}` sind live im
  Gateway, aber in **keiner** `.tf`-Datei des Repos deklariert; sie sind
  imperative Altlasten. Ein `terraform apply` verwaltet sie nicht, und ihre
  Löschung ist nicht durch Terraform abgesichert. Sie sind hier dokumentiert,
  weil sie live sind — eine Aufnahme in `terraform/modules/api` wäre eine
  eigene Änderung und wird hier **nicht** vorgenommen.
- **OPEN-4 — Keine `nextToken`-Pagination** (§7).
- **OPEN-5 — Handler-Zweige ohne Gateway-Route.** `_handle_api_event` bedient
  `/api/agents*`, `/work*` und `/me/jobsearches*`, für die es **keine**
  Gateway-Route gibt. Live liefern diese Pfade 404. Der Code ist vorhanden, der
  Zugang nicht exponiert; hier wird keine Route ergänzt.
- **OPEN-6 — `_handle_introspection` trägt einen veralteten Docstring**
  (`lambda/handler.py:959`: „NOT routed from API Gateway yet"). Die Route
  existiert seit P13 live. Nur der Kommentar war falsch.
- **Kein CI-Gate.** Die Pipeline prüft ausschließlich Terraform; weder `pytest`
  noch ein Linter laufen dort. Die Konsistenzprüfung aus
  `tests/test_p20_api_contract_consistency.py` schützt daher nur bei
  lokalem Testlauf.

## 9. Herkunft der Angaben

| Angabe | Quelle |
|---|---|
| Route ↔ Auth-Typ ↔ Backend | `aws apigatewayv2 get-routes` (28 live), `terraform/modules/api/main.tf`, `terraform/modules/orders_reader/main.tf` |
| Statuscodes, Fehlertexte, Body-Felder | `lambda/handler.py`, `lambda/orders_reader.py`, `lambda/documents.py` |
| Rollen- und Lifecycle-Regeln | `agents/ecosystem/api_profiles.py`, `agents/ecosystem/credentials.py`, `agents/ecosystem/introspection.py` |
| Orders-Übergänge, `limit` | `lambda/orders_reader.py` |
| Live-Verhalten der Kernrouten | `tests/test_p17_credential_lifecycle.py`, `tests/test_machine_entrypoint.py`, `tests/test_p20_health_contract.py` |