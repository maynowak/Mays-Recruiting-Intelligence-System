# MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01 — Phase 2

**Cognito OAuth / PKCE / CORS für die Jobsearch-Browser-Anmeldung**

- **Datum:** 2026-10-20
- **Branch:** `main`
- **Basis-Commit (Phase 2 Start):** `7492eb9`
- **Projekt:** `ris-dev` · **Workspace:** `ris-dev` · **Environment:** `dev`
- **Terraform-State:** `env:/ris-dev/dev/terraform.tfstate` (`s3://mays-ris-tf-state-dev`)
- **AWS-Region:** `eu-central-1` · **Account:** `240571105849`
- **Status:** Code + Tests umgesetzt, `terraform plan` erstellt. **Apply/DNS/Testnutzer gesperrt (Phase 2D Freigabegate).**

---

## 1. Phase 2A — Bestandsaufnahme (verifizierte Fakten)

| Gegenstand | Befund |
|---|---|
| Git | `main @ 7492eb9`, Baum sauber, `main == origin/main` |
| Workspace | `ris-dev` (explizit bestätigt), 169 verwaltete Ressourcen |
| RIS-Pool | `ris-dev-dev-users` (`eu-central-1_ojbmoiYGM`) |
| RIS-App-Client | `ris-dev-dev-client` (`7ldhihlpdgsgcl3puvu4oi7ksv`), **public** (kein Secret) |
| RIS-App-Client OAuth | **keine** — `AllowedOAuthFlows=false`, `CallbackURLs=[]`, `Scopes=[]` |
| RIS-App-Client AuthFlows | `ALLOW_USER_PASSWORD_AUTH`, `ALLOW_REFRESH_TOKEN_AUTH` |
| M2M-Client | `ris-dev-dev-m2m-client` (unberührt) |
| Pool-Domain | Prefix-Domain `ris-dev-dev` (Cognito-managed, CloudFront `d5cxcejge1ybj`), **keine** Custom Domain |
| ACM `auth.mays-job-matcher.app` | **ISSUED**, Amazon-issued, `us-east-1`, `InUseBy=[]` |
| DNS `auth.mays-job-matcher.app` | **kein Record** (keine Route53-Zone im Account; DNS extern) |
| API-GW CORS (`g6901and25`) | **`CorsConfiguration = null`** — nirgends konfiguriert (weder TF noch Handler) |
| Orders-Pool | `ris-dev-mays-orders-users` (`eu-central-1_cmJWXujnb`) — **unberührt** |

**Frontend-URLs (geprüft):** Das Jobsearch-Frontend ist **noch nicht** an Cognito angebunden
(`LoginForm`: „kein Cognito"). Die kanonischen URLs stammen aus dem Phase-1-Report und der
Jobsearch-Repo-Doku:

- Produktion: `https://mays-job-matcher.vercel.app`
- Lokal (Vite): `http://localhost:5173`
- Callback-Pfad: `/auth/callback`

---

## 2. Phase 2B — Implementierung

### 2.1 Cognito-Modul (`terraform/modules/cognito/`)

- Neue Variablen (Defaults **rückwärtskompatibel AUS**): `oauth_enabled`, `oauth_scopes`
  (Default `openid,email,profile`), `oauth_callback_urls`, `oauth_logout_urls`,
  `custom_domain_enabled`, `custom_domain`, `custom_domain_certificate_arn`
  (Validation: ACM-ARN muss `us-east-1` sein).
- `locals.oauth_active = oauth_enabled || google_client_id != ""`.
  Der Authorization-Code-Flow ist damit **von der Google-Federation entkoppelt**.
- App-Client: bei aktivem OAuth `allowed_oauth_flows=["code"]` +
  `allowed_oauth_flows_user_pool_client=true` + Scopes + Callback/Logout-URLs +
  `supported_identity_providers=["COGNITO"]`. **PKCE** gilt implizit für den
  public Client (`generate_secret=false` + `code`) — kein eigenes Flag im Provider-Schema.
  Ohne OAuth werden die Argumente weggelassen (`null`) → kein Diff, Password-Login unberührt.
- **Fail-closed:** Ist OAuth aktiv, verlangt Cognito nicht-leere Callback-Listen; leere
  Listen lassen Plan/Apply bewusst fehlschlagen, statt eine ungültige Konfiguration zu schreiben.
- **Domain:** Cognito erlaubt pro Pool **entweder** Prefix-Domain **oder** Custom Domain.
  Die beiden Ressourcen sind daher wechselseitig exklusiv per `count`:
  `custom_domain_enabled=false` → Prefix-Domain (Bestand); `=true` → Custom Domain
  (`auth.mays-job-matcher.app`, reuse des vorhandenen ACM-Zertifikats). Das Entfernen der
  Prefix-Domain ist eine **Cognito-Vorgabe, kein Versehen**; sie wird nirgends sonst referenziert.
- Neues Output `domain` (aktive Domain je nach Modus).

### 2.2 API-Modul (`terraform/modules/api/`)

- Neue Variable `cors_origins` (Default `[]`, Validation gegen Wildcard-Origins via Regex).
- `aws_apigatewayv2_api.ris_api`: `dynamic "cors_configuration"` nur wenn Origins gesetzt
  (leer = kein Block = kein Diff). `allow_origins` explizit, **kein `*`**;
  `allow_methods=[GET,POST,PUT,PATCH,DELETE,OPTIONS]`;
  `allow_headers=[Authorization,Content-Type,X-Api-Credential,X-Api-Profile]`; `max_age=3600`.

### 2.3 Projekt-Overlay (`installer/project-configs/ris-dev.json`)

Die ris-dev-spezifischen Site-Werte gehören **nicht** in wiederverwendbare Modul-Defaults
(sonst würden sie auch `ris-a`/`ris-b`/Prod treffen). Deshalb ein **committetes, versioniertes
Overlay**, das nur für `project_name=ris-dev` greift:

```json
"terraform_vars": {
  "identity_oauth_enabled": "true",
  "identity_oauth_scopes": "[\"openid\",\"email\",\"profile\"]",
  "identity_oauth_callback_urls": "[\"http://localhost:5173/auth/callback\",\"https://mays-job-matcher.vercel.app/auth/callback\"]",
  "identity_oauth_logout_urls": "[\"http://localhost:5173/\",\"https://mays-job-matcher.vercel.app/\"]",
  "identity_custom_domain_enabled": "true",
  "identity_custom_domain": "auth.mays-job-matcher.app",
  "identity_custom_domain_certificate_arn": "arn:aws:acm:us-east-1:240571105849:certificate/0bfb2603-a919-4b06-b4b9-da246c4edf75",
  "api_cors_origins": "[\"http://localhost:5173\",\"https://mays-job-matcher.vercel.app\"]"
}
```

**Installer-Integration (kein zweiter Konfigurationsmechanismus):**

- `installer/ris.py` → `load_project_config(project)`: liest `installer/project-configs/<project>.json`,
  **fail-closed** (Projektnamen-Abgleich, Whitelist `PROJECT_CONFIG_ALLOWED_KEYS`, keine
  secret-artigen Keys, kein CORS-Wildcard).
- `RisInstallContext.terraform_vars()`: Präzedenz **Overlay → `--var` → Projekt-Identität**
  (Identität gewinnt immer; Rollback z. B. per `--var identity_oauth_enabled=false`).
- `scripts/parallel_tests.sh` → `project_overlay_vars()` ruft **denselben Loader** auf, damit
  Verifier und Installer nicht auseinanderdriften.

**Sicherheit:** keine Secrets im Repo; keine Wildcard-CORS; bestehende Nutzer/Clients/Authoren
unverändert.

---

## 3. Terraform-Plan (Phase 2D Freigabegate)

Erzeugt mit den **Overlay-Werten aus dem Loader** (siehe Report-Anhang), gespeichert als
`/tmp/p2-final.tfplan`.

```
Plan: 1 to add, 2 to change, 1 to destroy.
```

| Aktion | Ressource | Änderung |
|---|---|---|
| **update** | `module.api.aws_apigatewayv2_api.ris_api` | `cors_configuration: [] → […]` (explizite Origins) |
| **update** | `module.cognito.aws_cognito_user_pool_client.client` | Auth-Code + PKCE + Scopes + Callback/Logout + Provider `COGNITO` |
| **create** | `module.cognito.aws_cognito_user_pool_domain.custom[0]` | `auth.mays-job-matcher.app` + vorhandenes us-east-1-ACM-Zertifikat |
| **destroy** | `module.cognito.aws_cognito_user_pool_domain.domain[0]` | Prefix-Domain `ris-dev-dev` (Cognito erlaubt nur eine Domain) |

### Scope-Prüfung (Auftrag 2C/2D)

| Prüfung | Ergebnis |
|---|---|
| Änderungen ausschließlich im vorgesehenen Scope | ✅ 4 Ressourcen (2 Cognito-Client/Domain, 1 API, 1 Prefix-Domain) |
| Keine unbeabsichtigte Ressourcenerneuerung (replace) | ✅ **keine** Replacements |
| Kein Destroy bestehender RIS-/Orders-Komponenten | ✅ kein Pool-/Client-/Orders-Destroy; einziger Destroy = Prefix-Domain (Cognito-Vorgabe) |
| Keine Änderungen an fremden Workspaces | ✅ Workspace `ris-dev` isoliert (Backend + Workspace) |
| Keine Änderungen am Orders-Cognito-Pool | ✅ 0 Orders-Änderungen |
| Keine Änderungen an RIS-Human-/M2M-Authorizern, `X-Api-Credential` | ✅ unberührt |
| Keine Secrets im Repository | ✅ Overlay enthält nur öffentliche Werte |

**Freigabe-Vorlage:** Der Plan ist unten und in `docs/reports/` dokumentiert. **Apply ist gesperrt.**

---

## 4. Testbericht (Phase 2C)

| Prüfung | Ergebnis |
|---|---|
| `terraform fmt -check -recursive` | **FMT OK** |
| `terraform validate` | **Success** (nur vorbestehende Deprecation-Warnungen) |
| `bash -n scripts/parallel_tests.sh` | OK |
| `py_compile installer/ris.py`, `tests/test_project_config_overlay.py` | OK |
| Neue Overlay-Regression `tests/test_project_config_overlay.py` | **23 passed** (Scope, Safety, Defaults-AUS, Installer-Wiring, Fail-closed) |
| `tests/test_entitlement_provisioning.py` (Wildcard-Guard) | **passed** (Kommentare/Validation wildcard-neutral formuliert) |
| Vollständige pytest-Suite | **1616 passed, 2 known baseline failures, 3 skipped** (vorher 1593 → +23) |
| `./scripts/parallel_tests.sh ris-dev` | **63 PASS / 1 FAIL / 1 WARN** |

**Erwarteter, korrekter Einzel-FAIL:** `S1.5 IDEMPOTENZ: plan exit=2` — der Plan enthält
genau die 4 Phase-2-Änderungen, die **noch nicht applied** sind. Nach dem (gesperrten)
Apply wird S1.5 wieder `0`/grün. Der Verifier liest das Overlay und zeigt exakt dieselben
4 Ressourcen — kein weiterer Drift, keine Regression.

**WARN:** `S6.1 Installer-Unit-Tests` — ausschließlich die dokumentierten Baseline-Defekte
(`AGENTS.md`), kein Parallel-Regress.

---

## 5. Git

- Geänderte/neue Dateien siehe Commit.
- **Kein** Change am Installer-Alpha-Branch (`feature/integration`) — nur `main`.
- `docs/AI_AUDITLOG.md` aktualisiert (`[MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01-PHASE2-2026-10-20]`).
- CROSS-REPO-SOURCE-01 beachtet: Repo-Identität `Mays-Recruiting-Intelligent-System`,
  Branch `main`, sauberer Baum, Basis-SHA `7492eb9`.

---

## 6. Erforderliche Freigaben (STOP vor)

1. **`terraform apply`** des Phase-2-Plans auf Workspace `ris-dev`
   (ändert: RIS-App-Client OAuth, API-CORS, Custom Domain, entfernt Prefix-Domain).
2. **DNS:** CNAME `auth.mays-job-matcher.app` → Cognito-CloudFront (`d5cxcejge1y…`-Domain,
   wird nach Apply final). Extern bei checkdomain.de, **nicht** in Terraform.
3. **Testbenutzer:** Anlegen/Bestätigen im RIS-Pool `ris-dev-dev-users`
   (Voraussetzung für den Browser-Login-E2E in Phase 3).

---

## 7. Empfehlung für Phase 3

1. Nach Apply: Verifier-`S1.5` muss wieder `0` sein; OIDC-Discovery unter
   `https://auth.mays-job-matcher.app/.well-known/openid-configuration` muss 200 liefern
   (Phase-1-Lücke „404 auf Prefix-Domain").
2. Jobsearch-Frontend von einer der freigegebenen Origins gegen den RIS-Pool verdrahten
   (Authorization-Code + PKCE, Callback `/auth/callback`).
3. OPTIONS-Preflight (`/me`) von `https://mays-job-matcher.vercel.app` → 200 + ACAO
   (Phase-1-Lücke „404") verifizieren.
4. Erst danach Testbenutzer und vollständiger Login-E2E.

---

## Anhang — Reproduzierbarer Plan-Aufruf

Der Plan wird mit denselben Vars erzeugt, die der Installer über das Overlay liefert
(wörtlich aus `installer/project-configs/ris-dev.json`); Lambda-Zip-Pfade wie im Verifier,
damit der Plan den Phase-2-Scope isoliert zeigt:

```
terraform plan -input=false -lock=false \
  -var=project_name=ris-dev -var=environment=dev \
  -var=filename=<abs>/terraform/../lambda/dist/orders-reader.zip \
  -var=health_writer_zip_path=<abs>/terraform/../lambda/dist/health-writer.zip \
  -var=health_publisher_zip_path=<abs>/terraform/../lambda/dist/health-publisher.zip \
  -var=api_cors_origins=["http://localhost:5173","https://mays-job-matcher.vercel.app"] \
  -var=identity_oauth_enabled=true \
  -var=identity_oauth_scopes=["openid","email","profile"] \
  -var=identity_oauth_callback_urls=["http://localhost:5173/auth/callback","https://mays-job-matcher.vercel.app/auth/callback"] \
  -var=identity_oauth_logout_urls=["http://localhost:5173/","https://mays-job-matcher.vercel.app/"] \
  -var=identity_custom_domain_enabled=true \
  -var=identity_custom_domain=auth.mays-job-matcher.app \
  -var=identity_custom_domain_certificate_arn=arn:aws:acm:us-east-1:240571105849:certificate/0bfb2603-a919-4b06-b4b9-da246c4edf75 \
  -out=/tmp/p2-final.tfplan
```
