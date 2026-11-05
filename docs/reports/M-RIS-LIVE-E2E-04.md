# M-RIS-LIVE-E2E-04 — Jobsearch ↔ RIS Live-Verbindung

- **Datum:** 2026-11-05
- **Modus:** bestehende Implementierungen verbunden, synthetischer E2E, dauerhafte Surface-Aktivierung
- **Ergebnis:** **E2E PASS** — Jobsearch-Browser-Login → BFF → RIS-Partner-Gateway → ApplicationV1

---

## 1. Bestandsabgleich

| Element | Befund |
|---|---|
| Jobsearch-Checkout | Branch `feature/jm-ris-testuser-allowlist-reconciliation-01`, HEAD `2382ab4` (nicht `main`) |
| Commit `242c4c9` | vorhanden („add RIS ApplicationV1 BFF and remote adapter") |
| BFF heute | weiterentwickelt: `api/ris/applications.mjs` + `api/_lib/ris/{config,auth,client,map}.mjs` |
| Entscheidung | **bestehende Implementierung verwendet**, keine zweite BFF-Version erstellt |
| Jobsearch-Cognito | Pool `ZURSMpD2O`, Client `5hb3…`, Domain `auth.mays-job-matcher.app` — unverändert |

Der BFF verifiziert Access-Tokens selbst (RS256, JWKS, Issuer/Audience/`token_use`), erzwingt eine Test-User-Allowlist und setzt `X-Api-Credential` ausschließlich serverseitig.

---

## 2. Wirkungsbereich von `PARTNER_SURFACE_ENABLED`

Vor der dauerhaften Aktivierung geprüft:

| Frage | Befund |
|---|---|
| Welche Routen öffnet das Flag? | alle `/v1/partner/me/*` auf **beiden** APIs (Kernel + Jobsearch-Edge) |
| Ersetzt es Authentifizierung? | **nein** — API-GW-JWT + `X-Api-Credential` + ACTIVE-Partner + APIProfile + Tenant bleiben Pflicht |
| Welche Partner sind ACTIVE? | nur `mays-jobsearch` (Credential `cred_5bf0…` ACTIVE) |
| Kernel-Partner? | `ris-dev-e2e-20261105` ist **INACTIVE** → kernel-seitig 403 |
| Unautorisierte Öffnung? | **nein** — ohne gültiges Partner-Credential keine Nutzung |

Ergebnis: Aktivierung ist sicher für den dauerhaft vorgesehenen Betrieb. **Keine** automatische Freigabe echter Bewerberdaten — der BFF begrenzt zusätzlich über die Test-User-Allowlist.

### Umsetzung (dauerhaft)

- `PARTNER_SURFACE_ENABLED` von Hardcode auf Terraform-Variable umgestellt (`partner_surface_enabled`, Default `false`).
- `ris-dev`-Overlay: `true`.
- Plan: **1 Update** (`module.lambda.aws_lambda_function.agent`), 0 add/delete/replace.
- Apply: `0 added, 1 changed, 0 destroyed`; Live-Wert `true`.

---

## 3. E2E-Durchführung

- Synthetischer Nutzer im Jobsearch-Pool (nur für den Test), Login über den **echten Authorization-Code-/PKCE-Flow** (Hosted UI, Playwright), Access-Token mit `token_use=access`, `client_id=5hb3…`, Issuer `ZURSMpD2O`.
- BFF lokal mit den produktiven Handler-Modulen gestartet (kein zweiter Code), Env: `RIS_APPLICATION_STORAGE_ENABLED=true`, `RIS_API_BASE_URL=https://c7e9pdwe78…`, Jobsearch-Issuer/Client, Partner-Credential serverseitig, Allowlist `issuer|sub`.

| Schritt | Ergebnis |
|---|---|
| Auth-Code + PKCE + Token-Exchange | ✅ Access-Token |
| `GET /api/ris/applications?action=metrics` | **200** |
| `POST /api/ris/applications` (Create) | **201**, Betrag `50000.5` |
| `GET` Liste | **200** |
| `GET ?id=…` Detail | **200** |
| `PATCH` (`60000.75`, `If-Match: 1`) | **200**, Version 1 → 2 |
| Reload (`GET ?id=…`) | **200**, Betrag `60000.75` |
| `GET ?action=export` | **200** |
| `DELETE` | **200** |
| Metrics danach | **200** |
| Ungültiges Token | **401** |

Damit ist die Kette **Jobsearch-Login → BFF → RIS-Edge-API → Partner-Credential → ApplicationV1** vollständig belegt.

---

## 4. Cleanup

| Objekt | Zustand |
|---|---|
| Synthetische Applications | **0** (Test- und Probe-Datensätze gelöscht) |
| Synthetischer Jobsearch-Nutzer | gelöscht (0 `e2e-live`-Nutzer) |
| Lokale Token-/User-Dateien | entfernt |
| BFF-Harness | beendet |
| Gateway `c7e9pdwe78` | **bleibt** |
| Partner `mays-jobsearch` | **bleibt ACTIVE** |
| APIProfile `aprof_5197…` | **bleibt ACTIVE** |
| Credential `cred_5bf0…` | **bleibt ACTIVE** (bis 2027-11-05) |
| `PARTNER_SURFACE_ENABLED` | **true** (dauerhaft) |

---

## 5. Nicht durchgeführt / offen

1. **Vercel-Test-Env** (`RIS_API_BASE_URL`, `RIS_API_KEY`) nicht gesetzt — der E2E lief mit lokalem BFF; eine Vercel-Änderung war nicht Teil der Freigabe.
2. **Produktionsdeployment Jobsearch** nicht erfolgt.
3. **Reale Bewerberdaten** bleiben unzugelassen; RG-09-Freigabe steht weiterhin aus.
4. Jobsearch-Repo wurde nicht verändert (nur gelesen); Checkout blieb auf dem Feature-Branch.

---

## 6. Sicherheitsbewertung

- Keine Änderung an Cognito-Pools/-Clients/-Domains, CloudFront, DNS, ACM oder Mays-Orders.
- Kein Secret in Git, Reports oder Logs; Credential weiterhin nur in der 600er-Datei.
- Der BFF prüft Signatur, Issuer, Audience und `token_use`; ohne gültiges Token 401, ohne Allowlist 403.
- Surface-Aktivierung öffnet keine zusätzlichen Partner: nur `mays-jobsearch` ist ACTIVE mit Credential.
