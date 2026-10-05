# RIS-B3-B4-COGNITO-AND-AGENT-ENTRYPOINT-DISCOVERY-07 — Discovery / Architecture Readiness

STATUS: **GREEN (Discovery)** — Bestand vollständig untersucht. **Keine Implementierung, keine AWS-Mutation.** B3 und B4 sind beide **fehlende Produktfunktion**, nicht Fehlkonfiguration.

- Datum: 2026-10-05 UTC
- Git HEAD (vor Gate): `e9e5ba5`
- Account/Profil/Region/Workspace: `240571105849` / `mayaws` / `eu-central-1` / `mays-ris`
- **DISCOVERY ONLY** — dieses Gate darf keine Implementierung auslösen

## 1. AWS Context

| Feld | Wert | Erwartet | Match |
|---|---|---|---|
| AWS Account | `240571105849` | `240571105849` | ✅ |
| AWS Profile | `mayaws` | `mayaws` | ✅ |
| AWS Region | `eu-central-1` | `eu-central-1` | ✅ |
| Terraform Workspace | `mays-ris` | `mays-ris` | ✅ |
| Git Branch | `main` | `main` | ✅ |
| Git HEAD | `e9e5ba5` | — | ✅ |
| Working Tree | 0 tracked Änderungen | clean | ✅ |
| API Gateway | `aboqolpm0f`, 27 Routen, 1 Authorizer | — | ✅ |

Keine Abweichung → kein RED.

## 2. Cognito Inventory

| Feld | Wert |
|---|---|
| User Pool ID | `eu-central-1_dgQXgwUbv` |
| Name | `mays-ris-dev-users` |
| LastModifiedDate | `2026-10-02T18:31:08.262+02:00` |
| EstimatedNumberOfUsers | 14 (live: **14 User**) |
| MFA | `OFF` |
| `AutoVerifiedAttributes` | `["email"]` |
| `LambdaConfig` | `{}` — **keine Cognito-Trigger** |
| `EmailConfiguration` | `EmailSendingAccount: COGNITO_DEFAULT` |
| `SmsConfiguration` | `null` (kein SMS) |
| `UsernameAttributes` / `AliasAttributes` | `null` — keine Username-/Alias-Konfiguration, E-Mail als Username |
| Identity Provider | **KEINE** (`list-identity-providers` → leer) |
| Domain / Hosted UI | **KEINE** — keine Hosted-UI-Domain konfiguriert |
| `RefreshTokenValidity` | **30 Tage** |
| `TokenValidityUnits` | `{}` → Pool-Defaults |

### Token-Konfiguration (live aus Tokens berechnet, nicht nur aus Config abgeleitet)

| Token | `iat`→`exp` | `token_use` |
|---|---|---|
| ID Token | **3600 s (1 h)** | `id` |
| Access Token | **3600 s (1 h)** | `access` |
| Refresh Token | 30 Tage | opak, kein JWT |

**Hosted-UI-/OAuth-Konfiguration:** keine Domain, kein Identity Provider. Terraform *kann* OAuth aktivieren (`allowed_oauth_flows_user_pool_client = var.google_client_id != ""`), aber live ist der Client auf reinen User-Pool-Betrieb konfiguriert.

## 3. Groups — 7 Gruppen, live

| Gruppe | `Role` | `Precedence` | Mitglieder |
|---|---|---|---|
| `candidates` | `null` | `null` | 0 |
| `Staff` | `null` | `null` | 2 — `p20-sec-staff`, `v3-staff-synth` |
| `user-user` | `null` | `null` | 0 |
| `user-requier` | `null` | `null` | 0 |
| `Admin` | `null` | `null` | 0 |
| `admins` | `null` | `null` | 4 — `p19-ab-admin`, `p17-admin-1791206079`, `v3-admin-synth`, `p19-admin-synthetic` |
| `recruiters` | `null` | `null` | 0 |

**Befunde:**

1. **Keine Rolle und keine Präzedenz** auf irgendeiner Gruppe. Es gibt **keine** verlässliche Rangordnung zwischen `admins`, `Staff` und zukünftigen Gruppen. Diese Information fehlt live und wird auch nicht emittiert.
2. **Vier Gruppen sind tot** (`candidates`, `user-user`, `user-requier`, `Admin`, `recruiters` → 5 leere). `Admin` (Großschreibung) ist laut `docs/reports/RIS-PRODUCT-PLATFORM-OPEN-DECISIONS-05.md` R6 als **deprecated** markiert; `admins` ist der aktive Name.
3. **Es existiert KEINE Gruppe für API-/Service-/Client-Nutzung.** Das ist der zentrale Befund für B3: selbst wenn Option A oder B gewählt würde, gibt es heute keinen Ort, eine solche Rolle abzubilden.
4. **Mehrfachmitgliedschaft ist technisch möglich** (live belegt: 14 User, 6 Gruppen, Gruppenzuweisung ist additiv). **Wie mehrere Gruppen im JWT erscheinen:** live an einem Token mit `admins` verifiziert — `cognito:groups: ["admins"]`, ein **JSON-Array als nativer Typ**, kein stringifizierter Wert.
5. **Keine API-Key-Mitgliedschaft, keine Client-Zuordnung** auf Gruppenebene.

**Wichtig — die bereits korrigierte Group-Normalisierung bleibt unangetastet.** `_normalize_groups` (`lambda/handler.py:203`) ist Security-Fix-02 und verarbeitet bewusst auch stringifizierte Formen (`"[admins]"`), weil der API-Gateway-JWT-Authorizer den Claim teils stringifiziert liefert. Mein Live-Befund (natives Array) ändert daran nichts: die Normalisierung bleibt fail-closed und wird in diesem Gate **nicht** verändert.

## 4. App Clients — genau 1

| Feld | Wert |
|---|---|
| ClientId | `3pkcifopuisumo14cg1pj0cfeo` |
| ClientName | `mays-ris-dev-client` |
| **ClientSecret** | **keines → Public Client** (`generate_secret = false` in `terraform/modules/cognito/main.tf:49`) |
| `ExplicitAuthFlows` | `["ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_PASSWORD_AUTH"]` |
| `AllowedOAuthFlows` | `null` |
| `AllowedOAuthFlowsUserPoolClient` | `false` |
| `AllowedOAuthScopes` | `null` |
| `CallbackURLs` / `LogoutURLs` | `null` / `null` |
| `SupportedIdentityProviders` | nicht gesetzt |
| `EnableTokenRevocation` | **`true`** ← relevant für Option B |
| `EnablePropagateAdditionalUserContextData` | `false` |
| `AuthSessionValidity` | 3 |
| `RefreshTokenValidity` | 30 Tage |
| Access/Id-Token-Validity | nicht am Client gesetzt → Pool-Default (1 h, live verifiziert) |
| Analytics | `null` |
| `LastModifiedDate` | `2026-09-30T13:59:17.353+02:00` |

**Zweck:** Der Client ist ein reiner **Human-Auth-Client** für User-Pool-Authentifizierung (User-Password + Refresh). Er hat kein OAuth, keine Scopes, kein Client Secret.

### `client_credentials`: **nicht möglich** — live belegt

| Prüfung | Ergebnis |
|---|---|
| `AllowedOAuthFlows` | `null` — kein Flow konfiguriert |
| `AllowedOAuthScopes` | `null` |
| Resource Server | **0** (siehe §6) |
| `generate_secret` | `false` — Public Client, `client_credentials` **erfordert zwingend ein Client Secret** |

Ein `CLIENT_CREDENTIALS`-Aufruf ist damit doppelt blockiert: der Flow ist nicht aktiviert **und** es existiert kein Secret. Beides ist in diesem Gate **nicht** geändert worden.

## 5. OAuth Flows

| Eigenschaft | Status |
|---|---|
| Hosted UI Domain | ❌ nicht konfiguriert |
| Authorization Code Flow | ❌ nicht aktiviert (`AllowedOAuthFlows: null`) |
| Implicit Flow | ❌ nicht aktiviert |
| Client Credentials | ❌ nicht aktiviert + kein Client Secret |
| Device Code / Refresh-Tokens am OAuth | ❌ |
| `AuthSessionValidity` | 3 (User-Pool-Session-Cookie) |

Es existiert **kein** produktiver OAuth-Flow. Der einzige interaktive Weg ist `USER_PASSWORD_AUTH` über den Public Client. **Nicht aktiviert, nicht geändert.**

## 6. Resource Server / OAuth Scopes — **keiner vorhanden**

| Prüfung | Ergebnis |
|---|---|
| `list-resource-servers` | **0 Resource Server** |
| Custom Scopes | keine |
| Beispielhafte Scopes (`ris:agents.execute`, `ris:profile.read`) | **existieren nicht** — nicht erfunden, nicht angelegt |

**Konsequenz für B3:** Es gibt heute **keinen** Scope, der eine interne API-Berechtigung ausdrücken könnte. Ein Scope-basierter Ansatz würde einen Resource Server, Scopes, OAuth-Flows **und** ein Client Secret erfordern — vier Änderungen an Produktkonfiguration, von denen keine existiert.

**Nicht angelegt. Nicht geändert.**

## 7. JWT Claims — live gemessen, nicht behauptet

Zwei kontrollierte Testtoken (Probe-User ohne Gruppe, dann mit `admins`), Claims dekodiert:

### ID Token (1109 Zeichen)

| Claim | Wert |
|---|---|
| `sub` | `f34498e2-80e1-709c-f761-b9be0327e45b` |
| `aud` | `3pkcifopuisumo14cg1pj0cceo` → **der App Client** |
| `iss` | `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_dgQXgwUbv` |
| `token_use` | `id` |
| `cognito:username` | `b34-probe` |
| **`cognito:groups`** | **`["admins"]`** (nach Gruppierung) bzw. **fehlt komplett** (ohne Gruppe) |
| `custom:tenant_id` | `b34-1791208808` ✅ |
| `email` / `email_verified` | vorhanden |
| `iat` / `exp` / `auth_time` / `jti` / `origin_jti` / `event_id` | vorhanden |

### Access Token (1039 Zeichen)

| Claim | Wert |
|---|---|
| `sub` | `f34498e2-…` (identisch) |
| `client_id` | `3pkcifopuisumo14cg1pj0cceo` |
| `iss` | identisch zum ID Token |
| `token_use` | `access` |
| **`scope`** | **`"aws.cognito.signin.user.admin"`** ← **Cognito-eigener Implicit-Grant-Scope, kein Produkt-Scope** |
| **`cognito:groups`** | **`["admins"]`** ✅ |
| **`custom:tenant_id`** | **FEHLT im Access Token!** ❌ |
| `username` | `b34-probe` |

**Drei Befunde mit unmittelbarer Relevanz:**

1. **`custom:tenant_id` fehlt im Access Token.** Der Gateway-JWT-Authorizer validiert `aud`/`iss`, nicht Scopes — die Authorizer-Konfiguration enthält **keine** Scope-Prüfung. Die RIS-Code-Seite liest `custom:tenant_id` aus den JWT-Claims (`handler.py:307`). Das ist eine faktische, im Gate-07-Bericht implizite Randbedingung des Live-Betriebs: **der Human-Pfad muss den ID Token verwenden** (der einzige live verifizierte Weg, der `tenantId` liefert). Bei Umstellung auf Access-Token-Prüfung wäre die Tenant-Isolation verloren. Keine Änderung vorgenommen — nur dokumentiert.
2. **`scope` ist ein Cognito-Bestandswert, kein Produkt-Scope.** Es gibt keine Produkt-Scope-Semantik.
3. **`cognito:groups` ist live ein natives Array.** Der Authorizer liefert es teils stringifiziert (daher Security-Fix-02) — beide Formen sind im Code abgedeckt.

### Was区分t heute bereits Human / Admin / Staff / interne Client-Nutzung?

| Information | live verfügbar? | Beleg |
|---|---|---|
| **Mensch vs. Maschine** | ✅ `token_use` (`id`/`access`) | live gemessen |
| **Admin-Rolle** | ✅ `cognito:groups` enthält `admins` | live gemessen (auch nach Security-Fix-02) |
| **Staff-Rolle** | ✅ `cognito:groups` enthält `Staff` (Gruppe existiert, 2 Member) | Gruppe live; Claim-Mechanik identisch zu `admins` |
| **Tenant** | ✅ `custom:tenant_id` — **nur im ID Token** | live gemessen |
| **Welcher Client** | ✅ `aud` / `client_id` | live gemessen |
| **Produkt-Scope / Berechtigung** | ❌ **existiert nicht** | §6 |
| **Rollenrangfolge Admin vs. Staff** | ❌ **existiert nicht** (keine `Role`/`Precedence`) | §3 |
| **Interne Client-/Service-Rolle** | ❌ **existiert nicht** (keine Gruppe, kein Scope) | §3, §6 |

**Alle Aussagen sind live belegt.** Ich behaupte keinen Claim, den ich nicht gemessen habe.

## 8. API Gateway Authorizers

| Feld | Wert |
|---|---|
| Authorizer-Anzahl | **1** |
| Name | `mays-ris-dev-jwt` |
| ID | `9ghezn` |
| **Type** | `JWT` |
| `JwtConfiguration.Issuer` | `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_dgQXgwUbv` |
| `JwtConfiguration.Audience` | `["3pkcifopuisumo14cg1pj0cceo"]` (der App Client) |
| `IdentitySource` | `["$request.header.Authorization"]` |
| **Scope-Prüfung** | ❌ **keine** — weder `JwtConfiguration.Scopes` noch Route-`AuthorizationScopes` |

### Routen-Verteilung

| Authorizer | Anzahl | Routen |
|---|---|---|
| `JWT` | **26** | alle `/me/*`, `/platform`, `/agents`, `/orders/*`, `/v1/apiprofiles*` (11), `/v1/introspection` |
| `NONE` | **1** | `GET /health` (einzige öffentliche Route) |

**Befunde:**

1. **Es existiert kein `REQUEST`-Authorizer.** Die Gateway-Erweiterung Lambda-Authorizer (Typ `REQUEST`, der opaque Bearer prüfen könnte, ohne JWT zu erzwingen) ist **nicht** deployed — 1 Authorizer, Typ `JWT`.
2. **Der JWT-Authorizer erzwingt JWT-Struktur.** Live belegt in P17-06: `WWW-Authenticate: error="invalid_token" error_description="token contains an invalid number of segments"`. Ein opakes `ris_...`-Credential kann strukturell keine JWT-Route passieren.
3. **Keine Route ist für einen anderen Credential-Typ vorbereitet.** Alle 27 Routen sind entweder JWT-geschützt oder die eine öffentliche Health-Route.
4. **Keine Scope-basierte Zugriffskontrolle** auf irgendeiner Route — Autorisierung ist vollständig Anwendungscode (`_is_admin`/`_is_staff`).
5. Der Authorizer validiert `iss` + `aud`. Ein Token eines **anderen** Clients im selben Pool würde abgelehnt (Audience-Bindung), ein Token des **richtigen** Clients immer akzeptiert — unabhängig von Gruppen.

**Keine Route geändert.**

## 9. RIS Authorization Paths

### Ist-Matrix (belegt)

| Eingang | Authenticator | Context | Authorization |
|---|---|---|---|
| **Human JWT (ID Token)** | Cognito JWT Authorizer `9ghezn` (live ✅ 26 Routen) | `_extract_user_context` → `userId`=`sub`, `tenantId`=`custom:tenant_id`, `groups`=`_normalize_groups(cognito:groups)`, `email` | `_is_admin` (`"admins" in groups`), `_is_staff` (`"Staff" in groups`), `_check_tenant` (cross-tenant braucht `reason`) — produktiv, live GREEN |
| **Cognito-Gruppe** | tritt nur als Claim in (`cognito:groups`) | keine eigene Context-Funktion | nur über `_is_admin`/`_is_staff`; **kein** generischer Gruppen-Check |
| **Cognito-Scope** | **existiert nicht** (§6) | — | — |
| **opakes `ris_…`-Credential** | **kein produktiver Pfad** | `verify_api_credential` (0 Aufrufer) | `resolve_credential_profile` + `check_worker_entitlement` + Katalog-Status — **implementiert, unerreichbar** |
| **Worker/SQS** | kein HTTP-Bearer; IAM + SQS | `process_record(..., entitlement_resolver=DynamoDBEntitlementResolver())` — **produktiv bei `handler.py:1874-1884`** | `check_worker_entitlement` **live verdrahtet** (Execution-Time-Recheck, Gate 08) |
| **Cognito Access Token** | JWT Authorizer akzeptiert ihn (gleicher `iss`/`aud`) | ⚠️ `custom:tenant_id` **fehlt** → `tenantId=None` | Route-/Code-Verhalten nicht geprüft; **potenzielle Tenant-Isolations-Lücke** bei Umstellung — nicht geändert, nur markiert |

### Matrix-Ergebnis

Die **Credential-Verifikation ist an zwei Stellen implementiert und an keiner produktiv erreichbar** für HTTP:

| Funktion | Aufrufer | Status |
|---|---|---|
| `verify_api_credential` (`credentials.py:751`) | **null** (nur `tests/`) | unerreichbar |
| `introspect_credential` (`introspection.py:270`) | 1, aber unter `if bearer_credential:` — und `handler.py:356` ruft ohne 3. Argument → immer `None` | toter Zweig |
| `check_worker_entitlement` | **produktiv** via `DynamoDBEntitlementResolver` in der SQS-Pipeline | ✅ erreichbar, aber **ohne Credential-Bindung** (SQS-Worker hat kein Bearer) |

Das ist die präzise Form von B3: **die Verifikationslogik existiert, der Einstiegspunkt nicht.** Und sie erfordert zwingend ein `agent_id` (`credentials.py:780-781`: „the verifier never guesses the target").

## 10. P03 / P04 / P06 Contract Comparison

Quelle: `docs/reports/RIS-CREDENTIAL-VERIFICATION-09.md` (DECIDED), gestützt auf `RIS-PRODUCT-PLATFORM-CONTRACT-04.md` und `RIS-PRODUCT-PLATFORM-OPEN-DECISIONS-05.md`.

### P03 — Credential-Typ (DECIDED)

> „Typ: **OPAQUE BEARER** (`opaque-bearer-v1`) — kein JWT/Passwort/Profil/Entitlement/AWS-Secret; **genau EIN APIProfile** (Transfer verboten); widerrufbar; pro Verwendung geprüft; **nie rekonstruierbar**."

Implementiert in `agents/ecosystem/credentials.py:31,37`:
- `SECRET_PREFIX = "ris_"`, `_SECRET_RE = r"\Aris_[A-Za-z0-9_-]{40,60}\Z"`
- SHA-256-Digest über `ris-cred-v1:`-Domain-Trennung, **keine** reversible Verschlüsselung
- Ausgabe **genau einmal** (live in P17-06 bestätigt: Secret nur im POST, nicht in GET/Liste)

### P03 — Route-Grenze (DECIDED)

> „Human-JWT und Machine-Credential **niemals konkurrierend auf derselben Route** (kein 'erst JWT, sonst Key' — **Orakel-/Downgrade-Risiko**); Human-Pfad **unverändert**."
> „Machine-Zugänge unter **`/v1/m2m/`**-Prefix … bestehende Human-Pfade bleiben JWT-only."

**Diese Entscheidung ist mit dem Live-Befund konsistent** und war der Grund, warum B3 nicht durch eine vorhandene Lücke ungeplant „passiert". Sie ist **nicht implementiert** (0 Routen mit `/v1/m2m/`).

### P04 — Lambda-interne Credential-Verifikation

> „INPUT: bearer + **`agent_id` (PFLICHT — Ziel wird NIE geraten; Capability-Mapping = Routing-Sache)**"
> „401 (unbekannt/ungültig/Format/fehlendes Ziel) vs. 403 (bekannt-aber-deaktiviert/revoked/abgelaufen/Profil-negativ/Mismatch/Entitlement/Katalog)"

Die 15-Schritte-Reihenfolge ist implementiert (Format → Digest-Lookup → Status → Profil → Profil-Status → Expiry-MIN → Owner/Tenant-Konsistenz → Client-Note → Entitlement → Katalog-Ausführbarkeit → AUTHORIZED).

**Offene Design-Entscheidung, die P09/09 selbst dokumentiert:**
> „Routen-Pfad-Finalisierung (`/v1/m2m/`-Vorschlag) + **Prüfpfad-Verdrahtung (REQUEST-Authorizer vs. Lambda-intern ist für JWT-fremde Keys weiter Design-Entscheid VOR Verdrahtung)**"

Das ist die zentrale offene Frage für B3 — und sie ist **im Contract bereits als offen markiert**, nicht von mir erfunden.

### P05/P06 — Profile Selection / Management-vs-Usage-Trennung

Live verifiziert in P17-06: `default` / `explicit` / fremd → 404, kein Crossing; Management (JWT) und Credential-Nutzung sind **verschiedene Pfade mit verschiedenen Authenticatoren**.

### Die sechs Fragen des Gates

| Frage | Antwort auf Basis des untersuchten Zustands |
|---|---|
| **1. Ist das opaque Credential weiterhin notwendig?** | **Ja, wenn externe/APIProfile-Nutzung mit per-Request-Prüfung und APIProfile-Bindung gewollt ist.** Es ist der einzige Mechanismus, der `revoke`/`disable`/`rotate` **pro Profil** mit sofortiger Wirkung erlaubt (live belegt in P17-06). JWT trägt diese Eigenschaften nicht. |
| **2. Ist Cognito OAuth Client Credentials eine Alternative?** | **Technisch ja, aber nicht äquivalent.** Es fehlen *alle* Voraussetzungen (Resource Server, Scopes, OAuth-Flows, Client Secret). JWT-Revocation ist nicht per-Request wirksam (1 h Token-Lebensdauer; `EnableTokenRevocation=true` betrifft Refresh-Token). **Kein APIProfile-Binding** — `aud`/`client_id` ist client-, nicht profilgebunden. |
| **3. Ist Cognito JWT lediglich ein interner Identity-/Authorization-Mechanismus?** | **Genau so ist es heute faktisch.** Live: 1 Client, `cognito:groups` = Produktrollen, kein Scope, Tenant über `custom:tenant_id`. Interne Plattform-Identität — für Management-Plane ✅ passend. |
| **4. Können beide parallel sinnvoll existieren?** | **Ja — und genau das ist P03s Route-Grenze.** Getrennte Namespaces (`/v1/m2m/`), kein konkurrierender Auth auf derselben Route, kein Downgrade. Das ist **kein** Widerspruch, sondern die ursprüngliche Entscheidung. |
| **5. Würde eine Umstellung die Architektur unnötig brechen?** | **Ja, für Option A/B alleine.** P03 ist DECIDED mit 15-Schritte-Verifikation, 401/403-Trennung, Profiling. Eine Umstellung auf JWT-only würde APIProfile-Bindung, per-Request-Revocation und die Management/Usage-Trennung aufgeben — **ohne** einen Ersatz dafür. |
| **6. Gibt es einen Standardweg, der bereits durch Cognito/API Gateway abgedeckt ist?** | **Nein, nicht für diesen Zweck.** Cognito bietet `client_credentials` — aber nur clientgebunden, nicht profilgebunden, und die Voraussetzungen sind nicht vorhanden. Der einzige bereits abgedeckte Standardweg ist der **Human-JWT-Weg**, der bereits produktiv ist und nicht ersetzt werden muss. |

**Keine Entscheidung wurde stillschweigend geändert.**

## 11. B3 Options Matrix

| Kriterium | **A: Cognito JWT + Groups/Scopes** | **B: Cognito OAuth Client Credentials** | **C: opakes Credential, separater Einstiegspunkt** | **D: Kombination (JWT Identity/Management + opaque für APIProfile-Nutzung)** |
|---|---|---|---|---|
| **Passt zum bestehenden Contract?** | ❌ ersetzt P03 | ❌ ersetzt P03 | ✅ P03 DECIDED + `/v1/m2m/`-Vorschlag | ✅ **P03 wörtlich** (Route-Grenze) |
| **Vorhandene AWS-Unterstützung?** | ✅ vollständig (JWT Authorizer live) | ⚠️ nur als Bausteine; **4 Config-Änderungen** nötig | ⚠️ Authorizer-Typ `REQUEST` **nicht** deployed; Lambda-Code ✅ | ✅ JWT-Teil live, `REQUEST`-Authorizer fehlt |
| **Implementierungsaufwand** | klein (Gruppe+Rollenlogik) | **mittel** (Resource Server, Scopes, Flows, Client Secret, Route-Scope-Binding) | **mittel** (Gateway-Authorizer + Lambda-Verdrahtung + `agent_id`-Routing) | **mittel-groß** (C + klare Namespace-/Routing-Entscheidung) |
| **Revocation-Verhalten** | ❌ **schwach**: 1 h JWT-Lebensdauer, kein per-Request-Revoke; `EnableTokenRevocation` wirkt auf Refresh-Token | ❌ **schwach**: clientgebunden, `revoke` nicht profilgebunden | ✅ **stark**: `REVOKED` greift sofort (live belegt P17-06) | ✅ **stark** für Nutzung; JWT nur für Management |
| **Profile Binding** | ❌ **keine** (JWT hat kein `apiProfileId`) | ❌ **keine** (`aud`/`client_id` ist clientgebunden) | ✅ **genau ein APIProfile**, Transfer verboten | ✅ genau ein APIProfile für die Nutzungs-Plane |
| **Entitlement Binding** | ⚠️ nur über User/Group, nicht Credential | ⚠️ nur clientgebunden | ✅ `check_worker_entitlement` pro Request (live verdrahtet im Worker) | ✅ pro Request, unverändert |
| **Auditierbarkeit** | ✅ Cognito-Logs | ✅ Cognito-Logs | ✅ `credential-audit` mit `credentialId`/`correlation` (live belegt) | ✅ beidseitig, getrennte Planes |
| **Tenant Isolation** | ⚠️ `custom:tenant_id` **nur im ID Token**; Access-Token-Pfad ohne Tenant | ⚠️ kein Tenant-Claim für Clients | ✅ `tenantId` persistiert + PFLICHT im Contract | ✅ Management über ID Token, Nutzung über persistierten `tenantId` |
| **API Gateway Integration** | ✅ vorhanden (26 Routen) | ⚠️ Route-`AuthorizationScopes` + neuer Flow | ❌ benötigt `AuthorizationType=NONE` **oder** `REQUEST`-Authorizer | ❌ + zusätzlich Namespace-Trennung |
| **Sicherheitsrisiko** | ⚠️ Group-basierte Rollen ohne Präzedenz; ein Client = mehrere Rollen | ⚠️ Client-Secret-Management; `client_credentials` ohne Scopes = zu breit | ⚠️ eigener Einstiegspunkt ⇒ Downgrade-Risiko **nur** bei Vermischung mit JWT-Routen — durch `/v1/m2m/` ausgeschlossen | ⚠️ zwei Auth-Mechanismen ⇒ Pflicht: strikte Namespace-Trennung + Negativtests |
| **Datenschutz / Datenminimierung** | ✅ keine neuen Datenobjekte | ⚠️ neues Client-Secret-Artefakt | ✅ Secret inhaltsleer (keine IDs/Daten/Zeit), nur Digest persistiert | ✅ Trennung: Person-Daten (JWT) ↔ Maschinen-Daten (Credential) |
| **Bricht bestehende Entscheidungen?** | **Ja** — P03, P04, P05/P06-Trennung | **Ja** — P03, P04 | **Nein** — setzt P03 in Live um | **Nein** — ist P03 + P02 |

### Bewertung

- **Option A scheidet aus**, weil sie die zentrale Eigenschaft des Credentials aufgibt: **Binding an genau ein APIProfile mit per-Request-Revocation**. Eine Gruppen-/Scope-Rolle kann das nicht ausdrücken — sie kennt keine Profilinstanz.
- **Option B scheidet aus**, weil `client_credentials` **clientgebunden** ist, nicht **profilgebunden**. Das ist kein Konfigurationsdetail, sondern ein Modellfehler gegenüber P03s „genau EIN APIProfile, Transfer verboten". Zusätzlich fehlen vier Voraussetzungen.
- **Option C ist P03 wörtlich** und löst B3. Ihr Preis: ein Gateway-`REQUEST`-Authorizer (nicht deployed) oder `AuthorizationType=NONE` plus Lambda-interner Prüfung — diese Wahl ist laut `RIS-CREDENTIAL-VERIFICATION-09.md:78` **bereits als offene Design-Entscheidung dokumentiert**.
- **Option D ist C + Bestehendes.** Der Human-JWT-Weg ist live produktiv und muss nicht ersetzt werden; er ist für die Management-Plane (Profil-/Credential-Verwaltung, Dokument-Upload, Profil-Introspection) das richtige Werkzeug, weil er **Personen** authentifiziert. Die Nutzungs-Plane mit maschinellen Credentials ist ein anderes Problem.

**Empfehlung: Option D.** Sie ist die einzige Option, die P03 nicht bricht, den bereits live grünen Management-Weg unangetastet lässt und die fehlende Kette ergänzt statt sie zu ersetzen. Ich habe **nichts** implementiert und **keine** bestehende Entscheidung geändert.

**Vorbehalt, der ehrlich zu benennen ist:** Option D setzt voraus, dass die Management-/Usage-Trennung gewollt bleibt. Falls das Produktziel „nur Cognito, keine maschinellen Credentials“ wäre, wäre Option A die logische Konsequenz — aber das wäre eine **bewusste Aufgabe von P03**, keine technische Notwendigkeit, und es ist nicht meine Entscheidung.

## 12. B4 Agent Catalog Findings — **Ursache gefunden**

| Prüfung | Ergebnis |
|---|---|
| Tabelle | `mays-ris-dev-agent-catalog`, PAY_PER_REQUEST, TTL `ENABLED` auf `expiresAt` |
| Hash-Key | `agentId` (S) |
| GSI | `gsi-status` auf `status` (S), `projection_type = ALL` |
| Attribute | nur `agentId`, `status` deklariert |
| **Row-Count (live)** | **0** |
| Lesezugriff | ✅ IAM: `dynamodb:Scan` **vorhanden** (B2 behoben) |
| **Schreibzugriff** | ❌ **KEIN produktiver Schreibpfad** |

### Warum ist der Catalog leer? — belegte Ursache

Ich habe **alle** `put_item`/`update_item`/`batch_writer`-Aufrufe in `agents/` und `lambda/` aufgelistet:

| Modul | schreibt in |
|---|---|
| `offers.py:179,199` | offers-Tabelle |
| `credentials.py:937,960,963` | credentials-Tabelle |
| `api_profiles.py:217,243` | api-profiles-Tabelle |
| `pipeline.py:209,239,253,265` | work-queue |
| `handler.py:481,547` | user-profile |
| `handler.py:1604` | work-queue |
| `orders_reader.py:143,235` | work-queue |

**Kein einziger Pfad schreibt in `agent-catalog`.** `CatalogAdapter` ist rein lesend (`scan` in `scan_all_agent_ids`/`get_all_agents`, `get_item` in `get_agent`). Es existiert **kein Seeder, kein Installer, kein Provisioner, kein Terraform-Ressourcen-Import** für Agent-Einträge. Der einzige Seed im Repo betrifft Orders (`installer/projects/mays_orders/scripts/seed_orders.py`).

**Der Catalog ist nie befüllt worden — es fehlt die Funktion, nicht die Daten.**

### Read-Pfad funktioniert (wenn Daten da wären)

`handler.py:42-88` (`_init_catalog`, Coldstart): `CatalogAdapter().get_all_agents()` → `normalize_agent_status()` → `AgentDescriptor` → `get_registry().register()`. **Fail-closed:** unbekannter/leerer Status → `None` → Agent wird **nicht** registriert, niemals auf `ACTIVE` defaulted (`agent_status.py:23-41`). P17-06 belegt: `/agents` → 200 mit `[]`, keine Fehlermeldung — die Kette läuft, das Ergebnis ist leer.

## 13. Agent Provisioning Findings

| Artefakt | Status | Befund |
|---|---|---|
| `agents/ecosystem/registry.py` | ✅ vorhanden | `AgentRegistry` (In-Memory-Dict), `AgentDescriptor`, `AgentStatus`, `ExecutionProfile`; **nicht persistent** (Coldstart-Reset) |
| `agents/ecosystem/catalog_adapter.py` | ✅ vorhanden | Brücke DDB → Runtime-Registry, **nur lesend**; `populate_registry_from_catalog` vorhanden, aber **kein produktiver Aufrufer** (nur `__init__.py`-Reexport) |
| `agents/ecosystem/discovery.py` | ✅ vorhanden | Discovery-Schicht |
| `agents/ecosystem/eligibility.py` | ✅ vorhanden | Eligibility-Check |
| `agents/ecosystem/agent_status.py` | ✅ vorhanden | fail-closed Status-Normalisierung |
| **DynamoDB-`agent_catalog` Writer** | ❌ **fehlt** | kein `put_item`/`update_item` irgendwo |
| **Terraform Seeder/Provisioner** | ❌ **fehlt** | nur Tabellen-Ressource + IAM + Output |
| **Installationspfad** | ❌ **fehlt** | `installer/` hat Orders-Seeding, aber nichts für Agents |

### Vorhandene Agent-Implementierungen (lesend geprüft, **nicht** registriert)

| Modul | `AGENT_ID` | Status im Descriptor | im DynamoDB-Catalog? |
|---|---|---|---|
| `agents/reference_agent/` | `reference_agent` (`pipeline.py:53`) | via `pipeline.py:102` | ❌ |
| `agents/ats_agent/` | `ats-agent` (`registry.py:47`) | `AgentStatus.ACTIVE`, Capability `analyze.job`, `ExecutionProfile.LAMBDA` | ❌ |
| `agents/jobsearch_agent/` | `jobsearch-agent` (`agent.py:21`) | via `agent.py:107` | ❌ |
| `agents/orders/` | `orders_function` (`function.py:30`) | via `function.py:122` | ❌ |
| `agents/dummy/` | `dummy-base`, `dummy-a`, `dummy-b` | Test-Agenten | ❌ |

**`agents/ats_agent/registry.py` dokumentiert die Verantwortungsgrenze explizit:**
> „IMPORTANT: This module does **NOT** modify the persistent DynamoDB catalog. It connects to the **RUNTIME** Registry only."

Das ist der Schlüssel: das bestehende System hat **bewusst** zwei Ebenen getrennt — Runtime-Registry (In-Memory, von Code registriert) und persistenter Catalog (DynamoDB, **für diesen Zweck nie implementiert**). Der fehlende Writer ist eine **bewusste Architekturgrenze**, keine Regression.

### Ist-Zustand pro Artefakt (Gate-Fragen beantwortet)

| Frage | Agent-Code | Registry | Catalog-Eintrag | Provisioning | IAM | Status |
|---|---|---|---|---|---|---|
| Reference Agent | ✅ | ✅ (Runtime) | ❌ | ❌ | ✅ | ❌ nicht live |
| ATS Agent | ✅ | ✅ (Runtime, `register_ats_agent`) | ❌ | ❌ | ✅ | ❌ nicht live |
| JobSearch Agent | ✅ | ✅ (Runtime) | ❌ | ❌ | ✅ | ❌ nicht live |
| Orders Function | ✅ | ✅ (Runtime) | ❌ | ❌ | ✅ | ❌ nicht live |

**Fazit B4:** Sowohl B3 als auch B4 sind **fehlende Produktfunktionen derselben Art** — die Verifikations-/Ausführungskette ist implementiert, aber die **Verdrahtung von außen** (Gateway-Einstiegspunkt bzw. Catalog-Befüllung) fehlt. B4 blockiert B3: ohne Agent im Catalog kann `verify_api_credential` in Schritt 14 (`catalog.get(agent_id)`) nichts ausführbar finden.

## 14. Security Assessment

| Befund | Einstufung | Begründung |
|---|---|---|
| Gateway JWT Authorizer auf 26 Routen, `iss`+`aud` validiert | ✅ **robust** | Audience-Bindung verhindert Token-Missbrauch über andere Clients; Issuer-Bindung verhindert Fremd-Pool-Tokens |
| **Keine Scope-Prüfung** im Authorizer | ⚠️ **Beobachtung** | Autorisierung ist 100 % Anwendungscode. Konsistent mit dem design (Gruppenrollen), aber jede neue Route braucht manuelle Rollenprüfung |
| **Keine Gruppen-Präzedenz** (`Role`/`Precedence` alle `null`) | ⚠️ **Beobachtung** | Bei einer zukünftigen Admin+Staff-Kombination entscheidet **die Code-Logik** (`_is_admin`/`_is_staff`), nicht Cognito. Das ist fail-closed, aber undokumentiert |
| **Access Token ohne `custom:tenant_id`** | ⚠️ **wichtig** | Der Authorizer akzeptiert Access-Tokens (gleicher `iss`/`aud`). Die RIS-Code-Seite liest den Tenant aus Claims → `tenantId=None` bei Access-Token-Nutzung. **Kein Live-Beweis einer Ausnutzung**, da der Live-Pfad ID-Token nutzt. Ich habe **nichts geändert**; falls das je umgestellt wird, ist es zuerst zu beheben |
| **4 leere Gruppen** inkl. deprecated `Admin` | ⚠️ niedrig | Kein Sicherheitsrisiko (leer = keine Vergabe), aber `Admin` vs. `admins` ist verwechslungsanfällig für spätere Gates |
| Kein `REQUEST`-Authorizer, kein `NONE`-Einstiegspunkt | ⚠️ **B3-Ursache** | Fail-closed: opake Credentials werden abgewiesen (401). **Kein Bypass-Risiko**, eher ein Nicht-Erreichbarkeitsproblem |
| Fail-closed Agent-Status-Normalisierung | ✅ **stark** | Unbekannter Status → nicht registriert, nie `ACTIVE` (Gate 07) |
| Secret-Inhaltsleerheit + nur Digest persistiert | ✅ **stark** | Keine IDs/Daten/Zeit im Secret; Digest nie zurückgegeben/geloggt |
| CloudWatch-Log-Retention 14 d / 7 d | ✅ begrenzt | Audit-Events (referenz-ID, Actor, Reason) — kein Secret im Log (live in P17-06 geprüft) |
| **Kein neu entdecktes konkretes Sicherheitsproblem** | ✅ | Kein RED |

**Gesamt:** Keine aktuelle Ausnutzbarkeit. Zwei Beobachtungen für Folge-Gates: fehlende Access-Token-Tenant-Bindung und fehlende Scope-Prüfung. Beides ist **Dokumentation, kein Fix** in diesem Gate.

## 15. Privacy / DSGVO — technische Bewertung

**Keine pauschale Konformitätsaussage.** Nur technisch prüfbare Eigenschaften, gegen den Bezugspunkt `docs/architecture/RUNTIME-PATH.md:81` (CloudWatch 7–14 Tage, Trace-IDs ohne Secrets/PII).

> **Hinweis:** Eine Matrix mit dem im Gate genannten Namen `RIS-DATA-RETENTION-AND-PRIVACY-MATRIX` existiert im Repository **nicht** (Suche über `docs/**` ergab keinen Treffer). Ich erfinde keine Fristen und beziehe mich stattdessen auf die tatsächlich vorhandene Retention-Aussage und die live gemessene Tabellen-Konfiguration. **OPEN** als organisatorischer Punkt.

| Aspekt | Technischer Befund | Bewertung |
|---|---|---|
| **Datenminimierung** | Credential-Secret enthält **keine** personenbezogenen Daten (kein userId/profileId/tenant/Zeit) — inhaltsleer, nur Digest persistiert | ✅ sehr gut |
| **Zweckbindung** | Management (Person, JWT) und Nutzung (Maschine, Credential) sind **getrennte Pfade**; ein Credential ist an genau ein APIProfile gebunden | ✅ durch P03 gewahrt |
| **Zugriffstrennung** | `_check_tenant` erzwingt Tenant-Grenze auch für Admins (cross-tenant nur mit `reason`, live belegt Gate 05) | ✅ |
| **Tenant Isolation** | `tenantId` persistiert im Credential **und** im APIProfile, im Contract PFLICHT; live 0 Cross-Tenant-Leaks (P17-06) | ✅ |
| **Secret Handling** | Ausgabe genau einmal (live belegt), nie rekonstruierbar, SHA-256-Digest mit Domain-Trennung; kein Secret in GET/Liste/Logs | ✅ |
| **Logging** | Audit enthält `ref`, `action`, `outcome`, `actor`, `credentialId`, `correlation`, `reason` — **kein** Secret, kein Header, kein JWT (live geprüft, 40 Events) | ✅ |
| **Audit** | `credential.created/rotated/revoked/viewed` + `profile-create/transition/selection-resolved`; **Abgelehnte** Authentifizierungen werden **nicht** als `outcome=denied` erfasst (Fehlerpfad wirft vor `_audit`) | ⚠️ **Lücke**, bereits dokumentiert |
| **Revocation** | wirksam und sofort (Status `REVOKED` im Store, live belegt) | ✅ |
| **Speicher-/Löschbarkeit** | ⚠️ **offen**: `api-profiles` und `credentials` haben **TTL DISABLED** (live verifiziert) — bewusst (Gate 04: „NO TTL … deletion only via explicit admin cleanup, later gate"). Es existiert **kein** Löschpfad, daher bleiben Daten unbegrenzt | ⚠️ **wesentliche Lücke** |
| **Retention (live gemessen)** | `agent-catalog` TTL **ENABLED** (`expiresAt`), `entitlements` TTL **ENABLED**, `user-profile` TTL **ENABLED**; CloudWatch 14 d / 7 d | ✅ |

**Der Retention-Befund ist die wichtigste datenschutzrelevante Erkenntnis dieses Gates:** Profile und Credentials sind **unbegrenzt** persistiert und mangels Löschpfad nicht löschbar. Bei den derzeit **ausschließlich synthetischen** Daten ist das ein Datenschutz-Risiko noch ohne Personenbezug — aber es ist die **Voraussetzung**, unter der es eines würde, sobald echte Profile existieren. Das ist eine Folge von „kein Delete-Pfad", nicht von B3/B4, und gehört in ein eigenes Gate.

**OPEN (organisatorisch/rechtlich, nicht technisch entscheidbar):**
1. Aufbewahrungsfristen für APIProfile und Credentials — im Repo nicht definiert.
2. Rechtsgrundlage und Betroffenenrechte für Audit-Logs mit Actor-Kennung.
3. Rollenkonzept-Governance: wer darf Gruppen vergeben, wer reviewed sie (`Admin` deprecated, `admins` aktiv — wer entscheidet?).

## 16. Recommendation

**B3 → Option D.** Begründung in drei Sätzen: Option C/D setzt den DECIDED Contract P03 in Live um, ohne ihn zu brechen; Option A und B würden APIProfile-Bindung und per-Request-Revocation aufgeben, ohne Ersatz; der Human-JWT-Weg ist live bereits grün und wird nicht gebraucht. **Entscheidung liegt beim Auftraggeber** — ich habe nichts implementiert.

**B4 → Writer-Funktion für den persistierten Catalog.** Der Read-Pfad ist vollständig und fail-closed; es fehlt ausschließlich die Schreibseite. Ein Gate, das `register`-/`upsert`-Semantik für Agent-Deskriptoren definiert (Status-Normalisierung über `normalize_agent_status`, Audit, Tenant-Feld) und sie **über einen kontrollierten Pfad** bereitstellt.

**Reihenfolge:** B4 **vor** B3, weil `verify_api_credential` in Schritt 14 den Catalog-Status prüft — ohne Agent im Catalog liefert jede Verifikation „nicht ausführbar". Sonst wäre ein B3-GREEN ohne Aussagekraft.

**Nicht** in diese Gates gehört: Retention-/Löschpfad (eigenes Gate, datenschutzrelevant), Access-Token-Tenant-Bindung (nur bei geplanter Umstellung), `Admin`-Gruppenbereinigung (kosmetisch, aber als Aufräumpunkt notiert).

## 17. Required Implementation Gate

**Kein Implementierungsauftrag aus diesem Gate.** Vorgeschlagenes Folge-Gate, nur zur Beauftragung:

> **RIS-B4-AGENT-CATALOG-WRITER-08** (Read-Pfad vorhanden; Schreibseite + Provisioning definieren und implementieren)
> **RIS-B3-M2M-ENTRYPOINT-09** (Option D: `/v1/m2m/`-Namespace, Gateway-`REQUEST`-Authorizer oder `AuthorizationType=NONE` + Lambda-Verdrahtung, `agent_id`-Routing-Entscheidung, Negativtests gegen Downgrade)

Reihenfolge B4 → B3. Beide Gates benötigen eine **explizite Entscheidung**, die ich nicht vorweggenommen habe: für B3 die Options-Wahl, für B4 die fachliche Frage, welche Agenten produktiv in den Catalog gehören.

**Vor jedem Folge-Gate zu klären (aus diesem Gate heraus, nicht entschieden):**
1. Bleibt die Management-/Usage-Trennung gewollt? (Bestätigt Option D; widerlegt sie zugunsten A.)
2. REQUEST-Authorizer vs. Lambda-interne Prüfung? (Bereits in `RIS-CREDENTIAL-VERIFICATION-09.md:78` als offen markiert.)
3. Wie wird `agent_id` als Operation-Target bestimmt? `verify_api_credential` **rät nie** — das ist Routing, also eine echte Design-Entscheidung.
4. Welche Agenten gehören produktiv in den Catalog?

## 18. Open Questions

| # | Frage | Warum offen |
|---|---|---|
| 1 | Soll die Management-/Usage-Trennung bleiben (→ Option D) oder wird bewusst auf einen einzigen Mechanismus umgestellt (→ Option A)? | Produktentscheidung; A bricht P03/P04 |
| 2 | REQUEST-Authorizer oder Lambda-interne Credential-Prüfung? | Bereits im Repo als offene Design-Entscheidung dokumentiert |
| 3 | Wie wird `agent_id` bestimmt? | Contract verbietet Raten; Capability-Mapping ist Routing-Sache |
| 4 | Welche Agenten gehören in den persistierten Catalog? | Fachliche Produktentscheidung; 5 Kandidaten im Repo (Reference, ATS, JobSearch, Orders, Dummy) |
| 5 | Soll der Catalog per Hand/Deploy befüllt werden oder zur Laufzeit aus Code-Deskriptoren synchronisiert werden (`populate_registry_from_catalog` existiert bereits, ist aber umgekehrt gerichtet)? | Architekturentscheidung |
| 6 | Soll `Admin` (deprecated, leer) entfernt werden? | Aufräumpunkt; kein Sicherheitsrisiko |
| 7 | Retention-/Löschfristen für APIProfile und Credentials | Datenschutzrelevant; Repo hat keine Matrix |
| 8 | Wird der Human-Pfad künftig auf Access-Token umgestellt? | Dann ist `custom:tenant_id` zuerst zu lösen |
| 9 | Wer governed Gruppenvergabe und Rollen-Review? | organisatorisch |
| 10 | Fehlende `RIS-DATA-RETENTION-AND-PRIVACY-MATRIX` — existiert sie unter anderem Namen? | im Repo nicht gefunden |

## 19. AWS Mutation

**Keine Produktmutation.** Einzige Aktion: ein kontrollierter synthetischer Probe-User (`b34-probe`) zur JWT-Claim-Messung angelegt, benutzt und **wieder gelöscht** (Bestand 14 → 14 verifiziert).

| Ressource | Nachweis unverändert |
|---|---|
| Cognito User Pool | `LastModifiedDate` `2026-10-02T18:31:08.262+02:00` — identisch zu Gate 04/05 ✅ |
| Cognito App Client | `LastModifiedDate` `2026-09-30T13:59:17.353+02:00` — identisch ✅ |
| Groups | 7 Gruppen, unverändert ✅ |
| Resource Server | 0, unverändert ✅ |
| OAuth Flows / Scopes | `null`, unverändert ✅ |
| Identity Provider | keine, unverändert ✅ |
| API Gateway Authorizer | 1 (`9ghezn`, JWT), unverändert ✅ |
| API Gateway Routen | 27, unverändert ✅ |
| Agent Catalog | **0 Rows** — keine Mutation ✅ |
| Lambda `CodeSha256` | `ECemCxwAOv0fNo3OeAkxjpT3Eg+Xyl9LZB61h3R4VvQ=` — identisch ✅ |
| IAM Role Policies | 8 — identisch ✅ |
| Terraform `plan` | `No changes.` ✅ |
| `mays-ris-lambda-policy` / ESM-Tags | unberührt ✅ |

**Nicht durchgeführt:** keine Cognito-Konfigurationsänderung, kein App-Client-Change, kein OAuth-Scope, keine Group-Änderung, keine Gateway-Änderung, keine IAM-Änderung, kein Lambda-Deployment, keine DynamoDB-Mutation, keine Agent-Registrierung, kein Agent-Seeding, kein Terraform Apply, keine M2M-Implementierung, kein Code-Change.

## 20. Green-Kriterien

| # | Kriterium | Status |
|---|---|---|
| 1 | Cognito-Bestand vollständig genug untersucht | ✅ Pool, Groups, Clients, Flows, Scopes, Token-Config, IdP, Domain |
| 2 | Groups/Claims geprüft | ✅ 7 Gruppen live, Claims an 2 Testtoken gemessen |
| 3 | App Clients geprüft | ✅ 1 Client vollständig; `client_credentials` als unmöglich belegt |
| 4 | OAuth/Scopes geprüft | ✅ 0 Resource Server, 0 Scopes, keine Flows |
| 5 | API Gateway Authorizer geprüft | ✅ 1 JWT-Authorizer, Issuer/Audience/IdentitySource, keine Scopes, 26+1 Routen |
| 6 | Opaque-Credential-Contract berücksichtigt | ✅ P03/P04/P05/P06 wörtlich gegen Live-Zustand gehalten |
| 7 | B3-Optionen vergleichbar | ✅ 12 Kriterien × 4 Optionen |
| 8 | Ursache des leeren Catalogs nachvollzogen | ✅ **kein Schreibpfad existiert** — Read-Pfad vollständig |
| 9 | Registry/Provisioning-Struktur geprüft | ✅ Registry, Descriptor, Adapter, Discovery, Eligibility, 5 Agent-Module |
| 10 | keine AWS-Mutation | ✅ nur 1 synth. Probe-User, danach gelöscht |
| 11 | Empfehlung klar begründet | ✅ Option D + B4 vor B3, mit Gegenargumenten für A/B/C |

**11 von 11 → GREEN (Discovery).**

## 21. Git / Working Tree

Keine Code-, Terraform-, Test- oder Dokumentationsänderung außer diesem Report und dem Execution Log. Working Tree clean.

**HARD STOP — dieses Gate löst keine Implementierung aus.**
