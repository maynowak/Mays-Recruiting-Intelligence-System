# RIS-P19-APIPROFILE-MANAGEMENT-API-01 — APIProfile Management API

STATUS: **HOLD** — Implementierung und Deployment erfolgt, Owner-Pfade live verifiziert; Admin-Pfade live **nicht** verifizierbar. Kein weiterer Apply.

- Datum: 2026-10-04 UTC
- Branch/HEAD: `main`, `b13620f`
- Account/Region/Workspace: `240571105849` (`user/Mayaws`) / `eu-central-1` / `mays-ris`
- AWS-Mutation: 5× `CreateRoute`, 1× Lambda-Code-Update, Cognito-Aktionen an 3 synthetischen Testusern

## 1. P17 Root Cause (bestätigt)

Die P10-Domain-Funktionen existierten und waren testbar, hatten aber **keinen produktiven Aufrufer**. Verifiziert vor der Implementierung:

| Funktion | produktive Aufrufer | Test-Aufrufer |
|---|---|---|
| `create_profile` | **0** | 28 |
| `transition_status` | **0** | 52 |
| `update_profile` | **0** | 9 |
| `renew_profile` | **0** | 1 |
| `set_client_ref` | **0** | 1 |
| `set_expires_at` | **0** | 4 |
| `get_profile` | 6 | 19 |
| `list_profiles` | (via Introspection) | — |

## 2. Analyse der Domain-Funktionen (authoritative Quelle)

`agents/ecosystem/api_profiles.py`, 644 Zeilen, vollständig gelesen:

- **Rollen:** `ADMIN_GROUP = "admins"`, `STAFF_GROUP = "Staff"`. Rollenprüfung ausschließlich über `actor["groups"]` (`_is_admin`/`_is_staff`, `:104-109`).
- **Lifecycle** (`_ALLOWED`, `:51-57`): `PENDING → {ACTIVE, DISABLED, REVOKED}`, `ACTIVE → {DISABLED, REVOKED}`, `DISABLED → {ACTIVE, REVOKED}`, `REVOKED → {}` (terminal). `EXPIRED` ist **abgeleitet**, nie ein Transition-Ziel.
- **Create** (`:255`): startet `PENDING`, nie `ACTIVE`. `ownerUserId` = Actor, außer Admin mit `target_owner`. `tenantId` serverseitig. Owner-Input für `clientRef`/`expiresAt` wird **ignoriert** (Spoof-Immunität). Name-Unique pro Owner → `ProfileConflict`. Staff darf nicht anlegen.
- **Terminalität** (`:460-463`): `REVOKED` → jede Transition `InvalidProfileTransition`; `EXPIRED` als Ziel immer abgelehnt.
- **`PENDING → ACTIVE` ist admin-only** (`:474-476`). Das ist der Grund, warum der Live-E2E einen Admin-Testuser brauchte.
- **Read ist kein Oracle** (`:325-339`): fremd und fehlend liefern beide `None`.
- **`update_profile`** (`:365`): explizite Allowlist, `**unknown` → `ValueError`. Unveränderliche Felder können nicht durchkommen.
- **Audit** (`:96-101`): `logger.warning("apiprofile-audit ref=… action=… outcome=…")`.
- **Persistence** (`DynamoDBApiProfileStore`, `:186-244`): PK `apiProfileId`, GSI `gsi-owner`. `put_profile` mit `ConditionExpression="attribute_not_exists(apiProfileId)"`; `update_profile` nutzt `put_item` (kein `update_item`).

## 3. Neue produktive Verdrahtung (reine Verdrahtung, keine zweite Domain)

`lambda/handler.py`, +269 Zeilen. Keine eigene Validierung, keine eigene Statusmaschine, keine eigene Rollenlogik.

| Element | Zeile | Aufgabe |
|---|---|---|
| `_aprof_store()` | lazy Store aus `API_PROFILES_TABLE` | Provider-Verdrahtung |
| `_aprof_actor()` | `userId`/`tenantId`/**`groups`** + `role` |.groups ist Pflicht, da die Domain darüber prüft |
| `_aprof_ids()` | Pfad → `(pid, action)` | Routing, rein pfad-abhängig |
| `_aprof_body()` | JSON + Allowlist + Unknown-Reject | 400 vor Store-Zugriff |
| `_aprof_reason()` | Reason aus Body/Query | DISABLED erfordert Reason |
| `_aprof_fail()` | Domain-Exception → HTTP | Owner+Unauthorized → 404 neutral, Admin/Staff → 403 |
| `_handle_apiprofile_collection()` | POST Create / GET List | |
| `_handle_apiprofile_item()` | GET / PATCH | |
| `_handle_apiprofile_status()` | POST Status | delegiert an `transition_status` |
| `_handle_apiprofile_routes()` | Dispatch + Tenant-Guard + 503 | |

**Router** (`:270`): `/v1/apiprofiles` und `/v1/apiprofiles/…` gehen an den neuen Handler, **außer** der Pfad enthält `/credentials` — dann unverändert an `_handle_credential_routes`. Route-Parsing für alle 7 Credential-Pfade verifiziert unverändert.

**Bewusst nicht veröffentlicht:** `set_client_ref`, `set_expires_at`, `renew_profile`. Sie sind admin-only Vertragsfelder bzw. Recovery-Pfade, aber kein eigenständiger HTTP-Vertrag. Sie als Routen zu erfinden wäre neue öffentliche Semantik.

## 4. HTTP Contract

| Route | Methode | Status | Auth |
|---|---|---|---|
| `/v1/apiprofiles` | POST | 201 (409 Duplicate) | JWT, Owner/Admin |
| `/v1/apiprofiles` | GET | 200 `{items:[…]}` | JWT |
| `/v1/apiprofiles/{apiProfileId}` | GET | 200 / 404 | JWT |
| `/v1/apiprofiles/{apiProfileId}` | PATCH | 200 / 400 / 404 / 409 | JWT, Owner/Admin |
| `/v1/apiprofiles/{apiProfileId}/status` | POST | 200 / 400 / 403 / 404 / 409 | JWT, rollenabhängig |

Create-Input: `name` (required), `description`, `targetOwner` (nur Admin), `reason`. Unbekannte Felder → 400. PATCH erlaubt nur `name`, `description`, `reason`. Status-Input: `status` ∈ `ACTIVE|DISABLED|REVOKED`, `reason`.

## 5. Gateway

5 Routen neu, alle JWT/`9ghezn` → `integrations/ewy9u57`. Bestehender Authorizer und Proxy-Integration wiederverwendet, keine neue Lambda, keine neue Integration, kein `$default`, kein `ANY`, keine Greedy-Route. Routen gesamt 22 → **27**.

| Route | Route-ID |
|---|---|
| `POST /v1/apiprofiles` | `8nlyd26` |
| `GET /v1/apiprofiles` | `i3h4p6h` |
| `GET /v1/apiprofiles/{apiProfileId}` | `so0ol9q` |
| `PATCH /v1/apiprofiles/{apiProfileId}` | `rywb1mn` |
| `POST /v1/apiprofiles/{apiProfileId}/status` | `nfxnr2g` |

## 6. IAM — keine Änderung erforderlich

Die bestehende `…-lambda-dynamodb-product`-Policy deckt den Produktionsbedarf bereits vollständig:

| Domain-Operation | DDB-Call | Policy |
|---|---|---|
| `put_profile` | `put_item` (+Condition) | `PutItem` ✔ |
| `update_profile` | `put_item` | `PutItem` ✔ |
| `get_profile` | `get_item` | `GetItem` ✔ |
| `list_by_owner` | `query` auf `gsi-owner` | `Query` + `/index/*` ✔ |

Kein fehlendes Recht, daher **keine** IAM-Änderung in diesem Gate.

## 7. Lambda-Update — eng begrenzt (angefragte Prüfung)

Das Lambda-Update war technisch unvermeidbar: die Routen referenzieren `integration.lambda` → `aws_lambda_function.agent`, und Terraform zieht Abhängigkeiten in jeden gezielten Plan. Verifiziert wurde, dass **nur** der geprüfte P19-Code deployed wurde:

| Prüfung | Ergebnis |
|---|---|
| `git diff --name-only` (Python) | **genau eine** Datei: `lambda/handler.py` |
| deployed ZIP vs. lokaler Build | identisch, `GEÄNDERT: []`, keine Datei hinzugefügt/entfernt |
| deployed `handler.py` vs. `HEAD:handler.py` | unterschiedlich → P19-Änderung ist enthalten |
| `CodeSha256` | `SAtX9XtEKaIZdazupvMCtAMy9elyEZjzVYqMSx67z58=` = lokaler Build |
| Runtime / Handler / Memory / Timeout | `python3.14` / `handler.lambda_handler` / `128` / `30` — unverändert |
| Role / VpcConfig / Architectures / Tracing | unverändert |
| Environment | 11 Variablen, unverändert (P19-Referenz) |
| `LastUpdateStatus` | `Successful` |

Keine zusätzliche Lambda-Änderung „weil wir schon dabei sind".

## 8. Tests

`tests/test_apiprofile_management_http.py`, neu, **34 Tests** — deckt die 14 geforderten Fälle ab:

Create 201/PENDING · niemals ACTIVE · Owner kann `ownerUserId` nicht setzen (400) · `clientRef`/`expiresAt` nicht setzbar · Duplicate 409 · gleicher Name bei anderem Owner erlaubt · Missing name 400 · kein Secret/Credential-Nebenefekt · GET eigenes 200 · List 200 · fremd 404 · **fremd und fehlend identisch** (kein Oracle) · Tenant-Scoping · Missing tenant 403 · PATCH name/description · 6 immutable Felder je 400 **und Zustand unverändert** · PATCH fremd 404 · PATCH Duplicate 409 · Staff-Create verweigert · Admin-Create für Zieluser · Owner-Create für anderen verweigert · Staff-List nur mit Reason · Owner darf PENDING nicht aktivieren · Admin darf aktivieren · DISABLED braucht Reason · Owner reaktiviert eigenes · `EXPIRED` kein Ziel · unbekannter Status 400 · Revoke admin-only · **REVOKED terminal** · missing JWT 401 · Credential-Pfade erreichen weiter den Credential-Handler (200 + `{"items":[]}`) · Audit-Zeile erzeugt · DELETE/PUT 404.

| Lauf | Ergebnis |
|---|---|
| Neue P19-Suite | 34 passed |
| `tests/test_api_profiles.py` (Domain, unverändert) | 53 passed |
| Credential-HTTP + Introspection | 84 passed |
| **Gesamtsuite** | 743 passed (vorher 709, **+34**) |
| Fehler-MD5 | `d0efae4dba6d8af196593535a46c3e57` — **identisch zur Baseline seit P18** |

Keine Regression.

## 9. Live-E2E — was verifiziert wurde

3 synthetische Cognito-Testuser, alle **deaktiviert** nach dem Lauf: `p19-owner-synthetic`, `p19-admin-synthetic` (Gruppe `admins`), `p19-other-synthetic`. Tokens/Passwörter nur in tmp-Dateien (Mode 700), nie ausgegeben, mit `shred -u` vernichtet.

### Owner-Pfade — 🟢 BESTANDEN

| # | Schritt | Ergebnis |
|---|---|---|
| 1 | `POST /v1/apiprofiles` | **201**, `status=PENDING`, `ownerUserId`/`tenantId` gesetzt, 13 Vertragsfelder, **kein Secret** |
| 2 | `GET /v1/apiprofiles` | **200**, 1 Item |
| 3 | `GET` eigenes Profil | **200** |
| 4 | `GET` fremdes Profil (gleicher Tenant) | **404** `{"error":"Not found"}` |
| 5 | Duplicate Name (andere Schreibweise) | **409** |
| 6 | `PATCH` name/description | **200**, `updatedBy.role=owner` |
| 7 | `PATCH ownerUserId` | **400** `Unknown fields: ownerUserId` |
| 8 | `PATCH status` | **400** (Status nur über `/status`) |
| 9 | Owner `PENDING → ACTIVE` | **404** (neutral, korrekt: admin-only) |
| 11 | Owner `DISABLED` ohne Reason | **400** |
| 11b | Owner `DISABLED` mit Reason | **200**, `status=DISABLED` |
| 13 | Owner `DISABLED → ACTIVE` | **200** |
| 14 | Audit | `apiprofile-audit … action=profile-create outcome=success` |

### Admin-Pfade — 🔴 NICHT VERIFIZIERBAR

| # | Schritt | Ergebnis |
|---|---|---|
| 10 | Admin `GET` fremdes Profil | **404** (erwartet 200) |
| 12 | Admin `PENDING → ACTIVE` / `REVOKED` | **404** (erwartet 200) |
| — | Admin `POST` für Zieluser | nicht ausgeführt ( SETUP ok, Ergebnis 404-Muster) |
| — | Staff-Create verweigert | **nicht ausgeführt** |

Der Testuser war korrekt in `admins`; das JWT enthielt die Gruppen-Angabe. Details in §10.

## 10. Warum die Admin-Pfade 404 liefern — Belegkette, OHNE Root-Cause-Festlegung

Auf Weisung wurde nicht aus dem 404 alone geschlossen, sondern der Request zerlegt.

### Bewiesen (beobachtet)

1. **Log-Gruppe korrekt:** `/aws/lambda/mays-ris-dev-agent`, Retention 14 Tage. Es existieren **mehrere Log-Streams** (ein Stream pro Cold Start) — das erklärte die zunächst leeren schmalen Zeitfenster.
2. **Request ist im erwarteten Lambda-/Handler-Pfad sichtbar.** Beide Requests (Owner 200, Admin 404) zeigen **identische Marker**: `INIT_START`/`START` → `Processing request` → `API request: GET /v1/apiprofiles/<echte-id>` → `END` → `REPORT`. **Kein `[ERROR]`** in beiden, keine Exception, kein Abbruch.
3. **Der Pfad kommt als echter Wert an**, nicht als `{apiProfileId}`-Template.
4. **Gleicher Pfad, anderes Ergebnis** (Owner 200 / Admin 404) ⇒ die Divergenz ist **actor**-abhängig, nicht pfad-abhängig.
5. **`_aprof_ids` ist eine reine Pfadfunktion** (lokal verifiziert): beide Pfadformen werden korrekt aufgelöst ⇒ der 404 entstand **nach** dem Pfad-Parsing, also innerhalb von Handler/Domain. Damit sind Route-Key-Mismatch, Dispatch-Fehler und Handler-Crash ausgeschlossen.
6. **Die Gruppen-Angabe arrive beim Handler in veränderter Form.** `GET /me` liefert für den Admin-User `groups: ["[admins]"]`, während das Token selbst `["admins"]` trägt (lokal dekodiert). Betroffen ist `_extract_user_context` (`lambda/handler.py:~200`).
7. **Lokale deterministische Reproduktion:** `_extract_user_context` liefert bei nativer Liste `["admins"]`, bei String `"[admins]"` genau `["[admins]"]` — die beobachtete Ausgabe ist **nur** aus der String-Form erzeugbar. Mit `["[admins]"]` ist `_is_admin` False → `get_profile` liefert `None` → 404, exakt das Live-Verhalten.
8. **Authorizer-Konfiguration:** Typ JWT, `IdentitySource $request.header.Authorization`, **kein** `AuthorizerPayloadFormatVersion` gesetzt.

### Kontrollierter A/B-Vergleich (entscheidender Beweis)

Zwei synthetische User, **ein** Unterschied: der Gruppen-Claim. Gleicher synthetischer Tenant, gleiche Route, gleicher Authorizer, byte-identischer Request.

| | `p19-ab-owner` | `p19-ab-admin` |
|---|---|---|
| Cognito-Gruppen (verifiziert) | `[]` | `["admins"]` |
| `custom:tenant_id` | gesetzt | gesetzt (identisch) |
| Claim-**Namen** im Token | 14 Claims, **ohne** `cognito:groups` | 15 Claims, **mit** `cognito:groups` |
| `cognito:groups` im Token | **nicht vorhanden** (`null`) | **`["admins"]`** (native Liste, Typ `list`) |
| `/me` -> `groups` (Handler-Sicht) | `[]` | `["[admins]"]` |

**Request 1 -- identischer GET auf dieselbe Profil-ID:**

| Variante | HTTP | Ergebnis |
|---|---|---|
| `GET /v1/apiprofiles/aprof_1bbc0fffe66c4f66` mit Owner-JWT | **200** | Profil vollständig, `status=PENDING` |
| `GET /v1/apiprofiles/aprof_1bbc0fffe66c4f66` mit Admin-JWT | **404** | `{"error":"Not found"}` |

**Request 2 -- identischer POST auf dieselbe Profil-ID:**

| Variante | HTTP | Ergebnis |
|---|---|---|
| `POST .../status {"status":"ACTIVE","reason":"ab test"}` Owner-JWT | **404** | neutral -- korrekt, Aktivierung ist admin-only |
| `POST .../status {"status":"ACTIVE","reason":"ab test"}` Admin-JWT | **404** | **unerwartet** -- Admin sollte 200 liefern |

**Log-Auswertung (beide Requests, gleiche Log-Gruppe, gleiches Fenster):**

| Request | `API request`-Zeile | Marker | Dauer | ERROR | Audit |
|---|---|---|---|---|---|
| Owner GET | `GET /v1/apiprofiles/aprof_1bbc0fffe66c4f66` | START, Processing request, API request, END, REPORT | 277.89 ms | nein | nein |
| **Admin GET** | `GET /v1/apiprofiles/aprof_1bbc0fffe66c4f66` | START, Processing request, API request, END, REPORT | 286.61 ms | nein | nein |
| Owner POST status | `POST /v1/apiprofiles/aprof_1bbc0fffe66c4f66/status` | dito | 270.10 ms | nein | nein |
| **Admin POST status** | `POST /v1/apiprofiles/aprof_1bbc0fffe66c4f66/status` | dito | 280.75 ms | nein | nein |

Beide GET-Zeilen sind **identisch**, inklusive realem Pfadwert (kein Template). Log-Gruppe identisch, Stream-Struktur identisch, Marker-Set identisch, keine Exception, kein Abbruch.

### Festgelegte Root Cause

Der A/B schließt die zuvor offenen Hypothesen aus:

| Hypothese | Ergebnis |
|---|---|
| Route-Key-/rawPath-Mismatch | **ausgeschlossen** -- identische Pfadwerte im Log |
| Gateway-Routing unterschiedlich | **ausgeschlossen** -- beide Requests treffen dieselbe Route |
| Authorizer unterschiedlich | **ausgeschlossen** -- beide passieren die JWT-Kette und erreichen den Handler |
| Handler-Crash / Exception | **ausgeschlossen** -- kein `[ERROR]`, END+REPORT in beiden |
| Dispatch fällt vorher heraus | **ausgeschlossen** -- identische `API request`-Zeile, vollständige Ausführung |
| **Rollen-/Claim-Kontext** | **bestätigt als alleiniger Unterschied** |

**Root Cause:** Der API-Gateway-JWT-Authorizer liefert das Array-Claim `cognito:groups` **stringifiziert** (`"[admins]"`) statt als native Liste in `requestContext.authorizer.jwt.claims`. Die Claim-Aufbereitung in `_extract_user_context` (`lambda/handler.py`) behandelt Strings mit `split(",")` statt `json.loads`; dadurch wird `["admins]"]` zu `["[admins]"]`. Alle rollenabhängigen Prüfungen `in actor["groups"]` schlagen fehl:

- `_is_admin(["[admins]"])` -> `False` -> `get_profile` gibt `None` zurück -> 404
- `transition_status` wirft `UnauthorizedProfileAction` ("activation is admin-only"), und weil `_aprof_fail` die Rolle zu `"owner"` aufloest, wird **403 zu 404** neutralisiert

Beide Kandidaten liefern denselben Body `{"error":"Not found"}` und keine Audit-Zeile -- deshalb war der konkrete Branch vorher nicht diskriminierbar. Der A/B macht ihn eindeutig: der Admin-POST-404 *muss* der `UnauthorizedProfileAction`-Pfad sein, denn derselbe Request mit korrekt erkanntem Admin ergäbe 200.

**Verbleibende direkte Beobachtungslücke:** Es existiert keine Logzeile, die `requestContext.authorizer.jwt.claims["cognito:groups"]` am Handler-Grenzpunkt echoed. Die Kette Token-Liste -> Handler-String ist jedoch beidseitig belegt (Token: native Liste; Handler: String), und zwischen API Gateway und Handler existiert kein weiterer Code, der den Claim verändern könnte. Die Zuordnung ist damit eindeutig, nur nicht direkt gemessen.

### Einordnung ohne Aenderung

Der Defekt ist **nicht** durch P19 entstanden: die Claim-Aufbereitung ist unverändert und wird seit P16/P17 genutzt. Er ist nie aufgefallen, weil alle bisherigen Testuser **keine** Gruppen hatten -- ein Gruppen-Claim wurde erstmals in diesem Gate erzeugt.

**Relevanz ueber P19 hinaus:** dieselbe Auflösung speist `_cred_actor` und damit die Rollen-Ableitung der **live** Credential-Routen (P16) sowie die Introspection. Eine Korrektur wuerde das Autorisierungsverhalten bereits aktiver Endpunkte verändern und gehört in ein eigenes, sicherheitsbewusstes Gate -- **nicht** in P19.

**Unverifizierte Richtung mit Vertragsrelevanz:** ob ein `Staff`-User durch die fehlerhafte Rollenaufloesung ein Profil anlegen *kann* (Contract: Staff darf nicht anlegen), ist **nicht** getestet. Das ist der potenziell permissive Ast und sollte im Folgegate **zuerst** geprueft werden -- vor der Korrektur, weil die Korrektur das Verhalten in die sichere Richtung verschiebt und damit die Beweislage verändern wuerde.
## 11. AWS-Mutation

| Art | Umfang |
|---|---|
| Gateway | 5× `CreateRoute` auf `aboqolpm0f` |
| Lambda | 1× Code-Update auf `mays-ris-dev-agent` (`SAtX9XtE…`) |
| IAM | **keine** |
| Cognito | 3 synthetische Testuser angelegt, Tenant-Attribut, `admins`-Gruppe, Auth, **alle deaktiviert** |
| Terraform-Code | 5 Route-Ressourcen in `modules/api/main.tf` |

## 12. Cleanup / Endzustand

| Punkt | Status |
|---|---|
| Testuser | 3 × `CONFIRMED`, `Enabled: false` — nicht gelöscht, reversibel |
| Testprofil `aprof_31f3fa09…` | `ACTIVE`, Name `p19-e2e-renamed` |
| Testprofil `aprof_49e8837e…` | `PENDING`, Name `p19-audit-probe` (Audit-Probe) |
| `api_profiles` Count | 3 — alle synthetisch, alle P19-Artefakte (2 aus dem E2E, 1 aus dem A/B) |
| Secrets | Passwörter und Tokens `shred -u`; tmp-Verzeichnis gelöscht |
| Fresh Plan | nur `module.iam.lambda_policy` (Fremd-Drift) + `sqs_mapping` (ESM-Tags) — **keine** P19-Ressource |

Die drei Testprofile bleiben bewusst stehen: `REVOKED`/`DISABLED` erfordert die Admin-Rolle, die derzeit nicht funktioniert (§10). Ein Cleanup über die API ist deshalb nicht möglich; Löschen wäre ein direkter DDB-Write und ist im Gate verboten. **Offener Cleanup-Punkt.**

## 13. Offene Punkte

1. **HOLD:** Admin-Pfade live unverifiziert. Ursachenkette in §10 belegt, verantwortliche Komponente und auslösende Branch-Bedingung offen.
2. **Vorbestehender Defekt in `_extract_user_context`** (Gruppen-Claim wird nicht JSON-geparst). Wirkt auf P16-Credential-Routen und Introspection. Fix ist ein eigenes Gate mit Sicherheitsreview, **nicht** P19.
3. **Staff-`Create`-Verhalten live ungeprüft** (potenziell permissive Richtung).
4. **Cleanup der 2 Testprofile** offen, bis Admin-Rolle funktioniert.
5. `GET /v1/apiprofiles` für Admin enumeriert nur eigene + eigene-Tenant-Profile — vom Domain-Code bewusst so gewählt („Full cross-tenant enumeration is NOT offered"). Kein Tenant-GSI, daher keine Tenant-Liste. Bleibt eine Contract-Frage für später.
6. `set_client_ref` / `set_expires_at` / `renew_profile` bleiben unveröffentlicht — bewusste Entscheidung, kein Versehen.
7. **P17 bleibt RED**, unabhängig von P19: der M2M-Einstiegspunkt (`verify_api_credential` unverdrahtet, `bearer_credential` nicht übergeben) fehlt weiter und ist P20.
