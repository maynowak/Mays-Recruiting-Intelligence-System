# RIS-JOBSEARCH-DOMAIN-OAUTH-AUDIT-01

**Modus:** READ-ONLY AUDIT · Keine AWS/DNS/Terraform/Vercel-Änderungen
**Datum:** 2026-10-21
**Account:** 240571105849 (eu-central-1 + us-east-1 für ACM)
**Ziel:** Domain/Cognito/OAuth/CORS/Frontend Soll-Ist-Vergleich für Phase 3

## Zusammenfassung

Die Konfiguration ist **grundsätzlich konsistent** (OAuth Code+PKCE, kein Wildcard, Custom Domain ACTIVE in Cognito, CORS strikt). Es gibt **eine Abweichung zwischen Live-Domain und OAuth-Callback/CORS-Soll**:

- **Frontends/Domains:** `www.mays-job-matcher.app` (200, Vercel) und Apex `mays-job-matcher.app` (308 → `www.*`) sind live. **`auth.mays-job-matcher.app` löst derzeit nicht auf** (DNS-CNAME fehlt). Die Cognito Custom Domain `auth.mays-job-matcher.app` ist in AWS **ACTIVE** (CloudFront `d1xd3gat3vr3ss.cloudfront.net`), benötigt aber extern noch den CNAME `auth.mays-job-matcher.app` → `d1xd3gat3vr3ss.cloudfront.net`.
- **OAuth/Callbacks/CORS:** Der Terraform/Overlay-Soll ist auf **`https://mays-job-matcher.vercel.app`** (Vercel) ausgerichtet, **nicht** auf `https://www.mays-job-matcher.app`. Die aktuellen Live-URLs sind Vercel + localhost. Die `www`-Domain ist produktiv (Vercel-Deployment), aber **nicht** in CallbackURLs/CORS aufgenommen.
- **Frontend:** Das Jobsearch-Repo hat **keine** OAuth/Cognito-/Callback-Implementierung (`/auth/callback` existiert nicht). Login ist ein nicht-funktionaler Prototyp.
- **ACM:** Zertifikat `auth.mays-job-matcher.app` (us-east-1) ist **ISSUED**, `RenewalEligibility=ELIGIBLE`, `InUseBy` zeigt CloudFront in anderem Account (AWS-managed) — normal.

**Bewertung:** **YELLOW** — Anpassung erforderlich (www-Domain ins OAuth/CORS-Soll aufnehmen), aber kein Sicherheitsproblem. Vor Phase 3 sind zwei getrennte Freigaben sinnvoll: (a) DNS CNAME für `auth`, (b) Terraform/Overlay-Anpassung + Frontend-Auth-Implementierung.

## 1. Domain-Prüfung (Live)

| URL | HTTP | Redirect | Finale URL | TLS | Bemerkung |
|---|---|---|---|---|---|
| `https://www.mays-job-matcher.app/` | 200 | — | `https://www.mays-job-matcher.app/` | OK (Let's Encrypt YR1, bis 2027-01-07) | Live (Vercel). Hauptdomain impliziert. |
| `https://mays-job-matcher.app/` | 200 (via -L) | 308 → `https://www.mays-job-matcher.app/` | `https://www.mays-job-matcher.app/` | OK (YR2) | Apex leitet korrekt auf `www` weiter. |
| `https://auth.mays-job-matcher.app/` | **NXDOMAIN/resolve failed (curl 6)** | — | — | — | **DNS fehlt.** Erwarteter CNAME noch nicht gesetzt. |
| `https://mays-job-matcher.vercel.app/` | 200 | — | `https://mays-job-matcher.vercel.app/` | OK | Vercel-Preview/Deploy-Domain (aktuell im Overlay genutzt). |

**DNS (dig):**
- `www.mays-job-matcher.app` → A `216.198.79.1` (Vercel)
- `mays-job-matcher.app` → A `216.198.79.1`
- `auth.mays-job-matcher.app` → **keine A/CNAME** (leer)
- `mays-job-matcher.vercel.app` → A `64.29.17.131`, `216.198.79.131`
- NS: `ns.checkdomain.de.`, `ns2.checkdomain.de.`

**ACM (us-east-1, auth.mays-job-matcher.app):**
- Status ISSUED, `RenewalEligibility=ELIGIBLE`, NotAfter 2027-04-25 01:59:59+02:00
- SANs: `auth.mays-job-matcher.app`
- Validation DNS: `_ae77d7056f02234410ab918987eefb7f.auth.mays-job-matcher.app.` → `_6ac51bd501d5f38f5a9abd33fff1bb1b.wzccmgtwzk.acm-validations.aws.` (ValidationStatus SUCCESS)
- InUseBy: CloudFront in `arn:aws:cloudfront::590490809858:distribution/EGVCW3XKINSHF` (AWS-managed für Cognito Custom Domain)

**Fazit Domain:** `www` ist die effektive Produktivdomain (Apex redirected). `auth` benötigt externen CNAME **`auth.mays-job-matcher.app` → `d1xd3gat3vr3ss.cloudfront.net`** (CloudFront-Target von Cognito Custom Domain). Ohne DNS ist OIDC-Discovery über Custom Domain nicht extern erreichbar (regional Endpoint funktioniert).

## 2. Cognito Live Audit

### Human App Client `7ldhihlpdgsgcl3puvu4oi7ksv` (Live-Ist)

| Feld | Live-Wert | Soll (Terraform/Overlay) | Abweichung |
|---|---|---|---|
| Name | `ris-dev-dev-client` | — | — |
| ClientSecret | `null` (public) | `generate_secret=false` | OK |
| AllowedOAuthFlows | `["code"]` | `["code"]` | OK (Authorization Code + PKCE) |
| AllowedOAuthScopes | `["email","openid","profile"]` | `["openid","email","profile"]` (Reihenfolge egal) | OK |
| AllowedOAuthFlowsUserPoolClient | `true` | `true` (bei oauth_active) | OK |
| ExplicitAuthFlows | `["ALLOW_REFRESH_TOKEN_AUTH","ALLOW_USER_PASSWORD_AUTH"]` | gesetzt | OK (bestehend) |
| SupportedIdentityProviders | `["COGNITO"]` | `["COGNITO"]` (+ optional Google) | OK |
| CallbackURLs | `["http://localhost:5173/auth/callback","https://mays-job-matcher.vercel.app/auth/callback"]` | identisch (Overlay) | **Ist = Soll (Overlay)** — **enthält NICHT `www`** |
| LogoutURLs | `["http://localhost:5173/","https://mays-job-matcher.vercel.app/"]` | identisch | **enthält NICHT `www`** |
| EnableTokenRevocation | `true` | — | OK |
| RefreshTokenValidity | `30` | Default | OK |

### M2M Client `82ji073smu1b3fsvj96sonso`
- Name `ris-dev-dev-m2m-client`, Secret gesetzt (confidential), Flows `["client_credentials"]`, Scopes `["ris-api/m2m:execute"]` — **unverändert, korrekt**.

### Cognito Custom Domain
- Domain `auth.mays-job-matcher.app`, Status **ACTIVE**, Version `20261020174210`, CloudFront `d1xd3gat3vr3ss.cloudfront.net`, ACM us-east-1 (validiert). **DNS-CNAME fehlt extern** (Phase 2b offengehalten).

**OAuth-Flow:** Authorization Code + PKCE ✅ (public client, `generate_secret=false`, `code`).

## 3. API Gateway CORS (Kernel API `g6901and25`)

| Feld | Live-Ist | Terraform-Soll (Overlay) | Bemerkung |
|---|---|---|---|
| AllowCredentials | `false` | (Default) | OK |
| AllowHeaders | `authorization, x-api-profile, x-api-credential, content-type` | — | OK (Partner Dual-Auth Headers enthalten) |
| AllowMethods | `POST,PUT,OPTIONS,PATCH,GET,DELETE` | — | OK |
| AllowOrigins | `["http://localhost:5173","https://mays-job-matcher.vercel.app"]` | identisch (`api_cors_origins`) | **enthält NICHT `www`** |
| MaxAge | `3600` | — | OK |

Preflight (OPTIONS): von `https://mays-job-matcher.vercel.app` → HTTP 204 + korrekte ACAO-Headers. Von `https://www.mays-job-matcher.app` **ist aktuell kein Origin in AllowOrigins** (würde CORS-Block erzeugen, sobald Frontend von `www` auf RIS zugreift).

**Orders-API (`zf8tc0k2r2`) CORS:** `null` (keine explizite CORS-Konfiguration) — nur Kernel relevant.

## 4. Terraform-Abgleich (Soll vs. Ist)

| Komponente | Live-Ist (AWS) | Terraform-Soll (Overlay/Vars) | Abweichung |
|---|---|---|---|
| OAuth enabled | `true` (Client + Flows) | `identity_oauth_enabled=true` (Overlay `ris-dev.json`) | OK |
| CallbackURLs | Vercel+localhost (ohne www) | identisch | **Soll entspricht Live, aber Ziel ist `www`** |
| LogoutURLs | Vercel+localhost (ohne www) | identisch | **ohne www** |
| Custom Domain enabled | `true` (ACTIVE) | `identity_custom_domain_enabled=true`, `domain=auth.mays-job-matcher.app` | OK (DNS extern fehlt) |
| ACM ARN | gesetzt (us-east-1) | identisch | OK |
| CORS Origins | Vercel+localhost | identisch (`["http://localhost:5173","https://mays-job-matcher.vercel.app"]`) | **ohne www** |
| API-Module CORS default | (empty) | `api_cors_origins` default `[]` (Root+API) | OK (Overlay überschreibt) |
| Wildcard-Verbot | geprüft (Overlay/Tests) | Tests erzwingen explizite Origins, kein `*` | OK |

**Overlay `installer/project-configs/ris-dev.json` (IST-Soll):**
```json
"identity_oauth_callback_urls": "[\"http://localhost:5173/auth/callback\",\"https://mays-job-matcher.vercel.app/auth/callback\"]",
"identity_oauth_logout_urls": "[\"http://localhost:5173/\",\"https://mays-job-matcher.vercel.app/\"]",
"api_cors_origins": "[\"http://localhost:5173\",\"https://mays-job-matcher.vercel.app\"]"
```

**Tests (Overlay):** `tests/test_project_config_overlay.py` erwartet exakt diese beiden Origins (Vercel + localhost) — prüft auch kein Wildcard. **Keine Test-Erwartung für `www`** aktuell.

**Fazit Terraform:** Live = Overlay-Soll. Anpassung auf `www` wäre **Overlay + ggf. Tests** (nur falls Tests auf `www` umgestellt werden sollen). Keine Terraform-Änderung notwendig, um bestehenden Soll anzuwenden; Änderung nur bei Domänenwechsel-Entscheidung.

## 5. Frontend-Abgleich (Jobsearch-Repo)

**Repo:** `installer/projects/mays_jobsearch/` (Nested Clone)

| Aspekt | Befund | Status |
|---|---|---|
| Vite Config | `vite.config.ts` — Standard, `port 5173`, `api/**` external | OK |
| Vercel Config | `vercel.json` — Functions 60s, Cron `/api/cron/digest`, Rewrites für `/search`, `/landingspage2`, `/registrieren`, `/anmelden` | OK (keine Auth-Rewrites) |
| Router/Routing | React Router nicht sichtbar (SPA-Rewrites vorhanden). Keine `/auth/callback`-Route | **Fehlend (Phase 3)** |
| Auth/Login/Logout | `LoginForm.tsx` ist **Prototyp** („kein Cognito, keine API, keine Persistenz, keine Session“). Kein OAuth-Flow, keine PKCE, keine Token-Speicherung | **Nicht implementiert** |
| Cognito/OAuth Referenzen | **keine** (nur generische React-Hooks, i18n) | **Fehlend** |
| API Base URL | `src/api.ts` vorhanden (API-Client), aber keine `VITE_*` RIS-URL sichtbar | unklar (serverseitig via Vercel Functions?) |
| `.env.example` | enthält **keine** RIS/Cognito/OAuth-Variablen (nur OpenRouter/EdenAI/Apify/Upstash/Resend) | **keine Verdrahtung** |
| `/auth/callback` implementiert? | **Nein** — keine Treffer | **Blocker Phase 3** |

**Vercel-Zugriff:** kein `.vercel/project.json` im Repo → **NICHT VERIFIZIERT** (Deployment-Zuordnung lokal nicht prüfbar).

**Fazit Frontend:** Für Phase 3 müssen **Code+PKCE, Authorization Code Flow, `/auth/callback`-Route, Token-Handling, Logout** implementiert werden (serverseitiger Proxy zu RIS gemäß Dual-Auth, Secret `RIS_API_KEY` **nur** serverseitig). Aktuell **0% Auth-Implementierung**.

## 6. Sicherheit

| Prüfung | Ist | Bewertung |
|---|---|---|
| Wildcard-Callbacks | Keine `*` in CallbackURLs | ✅ Sicher |
| Wildcard-CORS | Keine `*` in AllowOrigins | ✅ Sicher (explizit 2 Origins) |
| Client-Secrets im Frontend | Public Client, `ClientSecret=null` | ✅ Sicher (PKCE) |
| PKCE vorgesehen | Authorization Code + `generate_secret=false` → PKCE implizit | ✅ Sicher |
| HTTPS produktiv | `www`/Apex via HTTPS, `auth` (Cognito CF) HTTPS | ✅ Sicher |
| M2M-Client unverändert | `82ji073smu1b3fsvj96sonso` unverändert | ✅ Sicher |
| Orders-Cognito unverändert | `eu-central-1_cmJWXujnb` nicht geprüft (außer CORS null) — keine Änderung | ✅ Sicher |
| DNS Auth fehlt | `auth.mays-job-matcher.app` NXDOMAIN | ⚠️ **Betriebsblocker für Custom Domain OIDC** (extern), kein Sicherheitsproblem |

## 7. Soll-Ist-Tabelle (Kompakt)

| Komponente | Live-Ist | Terraform-Ist (Overlay) | Ziel (Phase 3, empfohl.) | Abweichung | Maßnahme |
|---|---|---|---|---|---|
| **OAuth CallbackURLs** | Vercel+localhost (ohne www) | identisch | **+ `https://www.mays-job-matcher.app/auth/callback`** | **Mittel** | Overlay/Vars erweitern (Callback+Logout). Nur nach Frontend-Readiness + DNS-Entscheidung. |
| **OAuth LogoutURLs** | Vercel+localhost (ohne www) | identisch | **+ `https://www.mays-job-matcher.app/`** (bzw. Post-Logout-URL) | Mittel | Ergänzen |
| **API CORS AllowOrigins** | Vercel+localhost (ohne www) | identisch | **+ `https://www.mays-job-matcher.app`** | Mittel | Ergänzen (damit Preflight von www funktioniert). |
| **auth.mays-job-matcher.app** | NXDOMAIN | ACTIVE (Cognito) | **CNAME → `d1xd3gat3vr3ss.cloudfront.net`** (extern DNS) | **Hoch (Betrieb)** | **Externe DNS-Änderung** (checkdomain.de). Kein Terraform. |
| **`/auth/callback` Route (Frontend)** | **nicht vorhanden** | — | Implementieren (Code+PKCE, Token-Exchange, Session) | **Hoch (Phase 3)** | Nur Frontend-Repo, separater Auftrag. |
| **OIDC Discovery (Custom Domain)** | NXDOMAIN extern | — | `https://auth.mays-job-matcher.app/.well-known/openid-configuration` erreichbar (200) | Hoch (Betrieb) | Abhängig von DNS-CNAME. |

## 8. Bewertung & Empfehlung

**Gesamtbewertung:** **YELLOW** (keine Sicherheitslücke, aber Integrationslücken vor Phase 3)

**Minimal erforderliche Änderungen (Phase 3):**

1. **DNS (extern):** CNAME `auth.mays-job-matcher.app` → `d1xd3gat3vr3ss.cloudfront.net` (checkdomain.de). **Ohne diese Änderung** ist die Custom Domain für OIDC extern nicht nutzbar (regionaler Endpoint bleibt funktionsfähig, aber Custom-Domain-Ziel ist nicht erreichbar).
2. **Terraform/Overlay (optional, empfohlen bei Nutzung von `www` als produktive Login-Domain):** `ris-dev.json` um `www.mays-job-matcher.app/auth/callback` (Callback+Logout) und `https://www.mays-job-matcher.app` (CORS) erweitern. **Hinweis:** `tests/test_project_config_overlay.py` testet die exakten Vercel+localhost-Werte (Test `test_callback_and_logout_urls_are_explicit`, `test_cors_origins_are_explicit_jobsearch_frontends`) — bei Erweiterung um `www` müssen **diese Tests ebenfalls angepasst** werden (oder Entscheidung treffen: Vercel vs. www als primäres Frontend).
3. **Frontend (Jobsearch):** OAuth2 Authorization Code + PKCE implementieren, `/auth/callback`-Route, Token-Speicherung (secure), Logout, serverseitiger Proxy zu RIS (`RIS_API_KEY` **nur** serverseitig, **nie** `VITE_*`). **Kein Cognito-Client-Secret im Browser.**

**Empfehlung (pragmatisch):** **Zwei getrennte Freigaben.** (A) DNS-CNAME für `auth` (unabhängig von www/Vercel-Entscheidung) — behebt Betriebsblocker Custom Domain. (B) Domänenwahl klären (primär `www` vs. `vercel.app`) und entsprechend Overlay+Tests+Frontend anpassen (Phase 3).

**Schlussfolgerung:** Konfiguration ist **sicher und konsistent**. Die Abweichung ist **rein domänenpolitisch** (Produktivdomain `www` vs. konfigurierte Vercel-Domain), kein Architektur-/Sicherheitsproblem.
