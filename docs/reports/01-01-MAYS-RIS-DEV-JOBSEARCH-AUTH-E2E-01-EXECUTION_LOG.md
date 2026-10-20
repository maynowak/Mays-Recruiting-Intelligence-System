# 01-01 — MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01 — EXECUTION LOG

==================================================
EXECUTION LOG / CRASH RECOVERY — MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01
==================================================

CHECKPOINT: 2026-10-20 10:25 UTC — Phase 1 RIS Development (Branch: main, HEAD: 407b6ac)

- Current status: PHASE 1 COMPLETED — dauerhafte Development-Installation `ris-development` mit 169 Ressourcen applied; Phase 2/3/4 offen.
- Audit date/time: 2026-10-20 10:05–10:25 UTC
- Current Git branch and HEAD: `main`, HEAD = `407b6ac` (Arbeitsbaum mit uncommitted Alt-Änderungen)
- Audit scope: Phase 1 aus MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01 — AWS-/State-Abgleich, Workspace-Isolation, Terraform-Plan, Apply, Smoke-Tests. Keine Cognito-/DNS-Änderung.
- Completed audit sections:
  §1 AWS-/State-Bestand gegen Reports vom 2026-10-19 geprüft
  §2 Workspace-/Backend-Isolation geprüft und Workspace `ris-development` angelegt
  §3 Terraform-Plan erzeugt und auf Ownership geprüft
  §4 Apply ausgeführt (169 Ressourcen)
  §5 Post-Apply-Smoke-Tests (State, API, CloudFront, Cognito, Lambda/SQS/DynamoDB)
  §6 Read-only-Bestand für Phase 2/3 erhoben (Cognito-Client, ACM, DNS, Jobsearch-Repo)
- Actual findings (verified facts):
  - Workspace `ris-development` existierte **nicht**. `terraform workspace list` zeigte nur
    `default`, `mays-ris-test-e2e-01`, `ris-a`, `ris-b`.
  - Im Bucket existiert ein Root-`terraform.tfstate` (Default-Workspace, serial 13, **0 Ressourcen**).
    Der vorgegebene Befehl `workspace select ris-development >/dev/null 2>&1` wäre also still
    fehlgeschlagen und hätte im Default-Workspace geplant.
  - Plan: `169 to add, 0 to change, 0 to destroy` (169 create + 6 data read).
  - Alle 78 im Plan sichtbaren Namensstrings beginnen mit `ris-development`; `grep -c mays-ris-dev` = **0**.
  - Apply: `169 added, 0 changed, 0 destroyed`, Exitcode **0**, keine Errors.
  - State nach Apply: **169** Nicht-Data-Ressourcen, Workspace `ris-development`.
  - API: `https://klklimekab.execute-api.eu-central-1.amazonaws.com` (Stage `$default`).
    `/health`, `/me`, `/platform`, `/agents` liefern ohne JWT jeweils **401**.
  - Cognito RIS-Pool: `ris-development-dev-users` (`eu-central-1_7QCp09XEZ`),
    Prefix-Domain `ris-development-dev`, `custom:tenant_id` vorhanden, 0 Benutzer.
  - App-Client `ris-development-dev-client` (`6c82k6c90bk877hlj5v8pipcie`) ist public
    (`generate_secret=false`), aber **OAuth ist AUS**:
    `AllowedOAuthFlowsUserPoolClient=false`, keine `CallbackURLs`, keine `LogoutURLs`,
    `ExplicitAuthFlows=[ALLOW_USER_PASSWORD_AUTH, ALLOW_REFRESH_TOKEN_AUTH]`.
  - Insgesamt 6 Lambdas (`ris-development-dev-agent`, `-orders-reader`, `-health-writer`,
    `-health-publisher`, `ris-development-handler`, `ris-development-sqs-worker`),
    6 SQS-Queues, 11 DynamoDB-Tabellen, 6 Lambda-Log-Groups.
  - Zwei Cognito-Pools: RIS-Pool `ris-development-dev-users` **und** der im
    `module.mays_orders` eingebettete Pool `ris-development-users` (`eu-central-1_f53oRl4jy`).
    Für Jobsearch-Login ist ausschließlich der RIS-Pool zu verwenden.
  - `auth.mays-job-matcher.app`: ACM-Zertifikat in **us-east-1** `ISSUED`,
    `InUseBy=[]`, SAN exakt `auth.mays-job-matcher.app`; **kein DNS-Record** (A/CNAME leer).
    Apex `mays-job-matcher.app` → `216.198.79.1` (Vercel), NS = `ns.checkdomain.de` /
    `ns2.checkdomain.de`. ACM-Validierungs-CNAME existiert bei checkdomain.
  - AWS-Doku (verifiziert 2026-10-20): Cognito-Custom-Domain verlangt ein ACM-Zertifikat
    in **us-east-1**, unabhängig von der Pool-Region; Parent-Domain braucht einen A-Record.
    Das vorhandene us-east-1-Zertifikat ist damit wiederverwendbar.
  - Jobsearch-Repo (`installer/projects/mays_jobsearch`, eigener Git-Clone, HEAD `29d8b73`):
    LoginForm/RegisterForm sind reine UI-Platzhalter (kein `fetch`, kein Cognito).
    Kein OAuth-/PKCE-/Session-Code vorhanden.
- Evidence / file references:
  - `/tmp/ris-development.log` (Plan, 4249 Zeilen)
  - `/tmp/ris-development.tfplan`, `/tmp/ris-development.plan.json`
  - `/tmp/apply_ris-development.log` (`Apply complete! Resources: 169 added`)
  - `terraform/modules/cognito/main.tf` (OAuth nur bei Google aktiv)
  - `terraform/main.tf` (Modul-Verdrahtung, `prefix = project-environment`)
  - `lambda/handler.py` (`/me`, `/me/profile`, Dispatch)
  - `installer/projects/mays_jobsearch/src/components/LoginForm.tsx` (Platzhalter)
  - `installer/projects/mays_jobsearch/vercel.json` (Rewrites)
- Classification: **GREEN** (Phase 1), Gesamtaufgabe **YELLOW** (Phase 2/3/4 offen)
- Terraform checks actually executed and their results:
  - `terraform init -reconfigure` (S3-Backend `mays-ris-tf-state-dev`, Lock `mays-ris-tf-lock`): PASS
  - `terraform workspace select -or-create ris-development`: PASS (`WS=ris-development`)
  - `terraform plan -out=/tmp/ris-development.tfplan`: `169 to add, 0 to change, 0 to destroy`
  - `terraform state list` (Nicht-Data): **169**
  - `terraform output`: API-/Cognito-/DynamoDB-/SQS-Outputs vorhanden
- Git status: uncommitted Alt-Änderungen aus vorherigen Sessions (`AGENTS.md`, `installer/ris.py`,
  `terraform/.terraform.lock.hcl`, `terraform/modules/monitoring/*`), viele untracked Root-Notizen;
  diese Session hat nur `docs/reports/` und `docs/AI_AUDITLOG.md` ergänzt.
- Files changed:
  - `docs/reports/01-01-MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01-EXECUTION_LOG.md` (neu, dieser Log)
  - `docs/AI_AUDITLOG.md` (Checkpoint ergänzt)
  - Keine Änderung an Terraform-Code in Phase 1.
- Explicit confirmation when no files were changed: Terraform-Code, Lambda-Code und
  Jobsearch-Code wurden in Phase 1 **nicht** verändert; nur Dokumentation.
- Open questions:
  - Welche Callback-/Logout-URLs sind für Vercel-Preview-Deployments verbindlich?
  - Token-Storage im SPA: `sessionStorage` (Dev) vs. Memory + Refresh-Cookie?
  - Soll Managed Login v2 oder die klassische Hosted UI verwendet werden?
  - Testbenutzer: selbst registrieren oder per Admin-API mit `custom:tenant_id` anlegen?
- Risks:
  - `terraform/modules/mays_orders/` ist im RIS-Repo **untracked**, wird aber von
    `terraform/main.tf` referenziert → frische Clones können den 169-Plan nicht reproduzieren.
  - DNS für `auth.mays-job-matcher.app` liegt bei **checkdomain.de** (extern), nicht Route 53;
    der Alias-Record ist ein manueller/externer Schritt.
  - Zwei Cognito-Pools im selben Stack; falscher Pool im Frontend würde Benutzer isolieren.
  - App-Client hat aktuell keinen OAuth-Code-Flow; ein Frontend-Redirect würde ohne
    Terraform-Änderung mit `invalid_request` scheitern.
- Recommended next actions:
  1. Phase 2a: Terraform-Cognito-Modul erweitern (OAuth Code + PKCE, Callback-/Logout-URLs,
     Custom Domain `auth.mays-job-matcher.app` mit vorhandenem us-east-1-Cert).
  2. `terraform plan` für Phase 2 vorlegen; **Apply erst nach expliziter Freigabe**.
  3. Phase 2b: Nach Apply Alias-Target aus `describe-user-pool-domain` holen und
     CNAME `auth` bei checkdomain.de setzen (externe DNS-Mutation, Freigabe nötig).
  4. Phase 3: PKCE-Login im Jobsearch-Repo implementieren (kein zweiter Auth-Stack).
  5. Phase 4: E2E (Login → Callback → RIS `/me` → Profil → Logout → ungültiges JWT).
- Current resume point: `ris-development` ist live (169 Ressourcen, API `klklimekab`);
  nächster Schritt ist der **Phase-2-Plan** (Cognito OAuth + Custom Domain), noch ohne Apply.

AWS MUTATIONS (Phase 1): 169 Ressourcen erstellt (Workspace `ris-development`), 0 geändert,
0 gelöscht. Keine DNS-Änderung, kein Cognito-Custom-Domain, kein Destroy, kein Push.

---

## Phase-2/3-Implementierungsplan (Grundlage: verifizierter Bestand)

### Phase 2 — Cognito Custom Domain + OAuth Code/PKCE

**Ist-Zustand**
- Pool `ris-development-dev-users` (`eu-central-1_7QCp09XEZ`), Domain-Prefix `ris-development-dev`.
- Public Client `ris-development-dev-client` ohne Secret, aber OAuth deaktiviert.
- ACM `auth.mays-job-matcher.app` in us-east-1, `ISSUED`, unbenutzt.
- DNS bei checkdomain.de; `auth` existiert nicht; Apex-A-Record vorhanden.

**Geplante Terraform-Änderung (RIS, `terraform/modules/cognito`)**
1. Neue Variablen: `oauth_enabled` (bool), `oauth_callback_urls` (list), `oauth_logout_urls` (list),
   `custom_domain_name` (string, default `""`), `custom_domain_certificate_arn` (string, default `""`).
2. App-Client:
   - `allowed_oauth_flows_user_pool_client = var.oauth_enabled || var.google_client_id != ""`
   - `allowed_oauth_flows = ["code"]`
   - `allowed_oauth_scopes = ["openid", "email", "profile"]`
   - `supported_identity_providers = var.google_client_id != "" ? ["COGNITO","Google"] : ["COGNITO"]`
   - `callback_urls` / `logout_urls` aus den neuen Variablen
   - `ALLOW_USER_PASSWORD_AUTH` bleibt für bestehende Nicht-Browser-Clients erhalten.
3. Neue Ressource `aws_cognito_user_pool_domain.custom` (count = custom_domain_name != ""):
   - `domain = "auth.mays-job-matcher.app"`
   - `certificate_arn = <us-east-1 ACM ARN>`
   - Prefix-Domain `ris-development-dev` bleibt bestehen.
4. Outputs: `cognito_custom_domain`, `cognito_hosted_ui_base_url`, `cognito_client_id`, `cognito_issuer`.
5. Keine Secrets im Repo; Cert-ARN ist kein Secret, wird aber per Variable übergeben.

**Callback-/Logout-URLs (Vorschlag, vor Apply bestätigen)**
- `http://localhost:5173/auth/callback`
- `https://mays-job-matcher.vercel.app/auth/callback`
- optional Preview: `https://*.vercel.app/auth/callback` (Cognito unterstützt Wildcards nur begrenzt)
- Logout: `http://localhost:5173/`, `https://mays-job-matcher.vercel.app/`

**Nach Apply (DNS, externe Mutation — Freigabe nötig)**
- `aws cognito-idp describe-user-pool-domain --domain auth.mays-job-matcher.app`
  → `CloudFrontDistribution` (Alias-Target) auslesen.
- Bei checkdomain.de: CNAME `auth` → Alias-Target (TTL 300).
- Verifikation: `https://auth.mays-job-matcher.app/.well-known/openid-configuration` → 200 JSON.

### Phase 3 — Jobsearch-Login (bestehende UI vervollständigen)

**Ist-Zustand**
- `LoginForm.tsx` / `RegisterForm.tsx` sind UI-Platzhalter ohne Backend.
- Vite-SPA, Routing über `window.location.pathname` + `vercel.json`-Rewrites.

**Geplante Änderung (Jobsearch-Repo, nested clone)**
1. `src/lib/auth.ts`: PKCE-Helfer (`code_verifier`, `S256`-Challenge), Authorize-URL,
   Token-Exchange (`POST /oauth2/token`), Refresh, Logout, JWT-Claims-Decode/Expiry-Check.
2. `src/lib/authSession.ts`: Token-Storage (sessionStorage), Session-Recovery beim Load,
   `getValidAccessToken()` mit Refresh-Fallback, zentrale Fehlerbehandlung.
3. `LoginForm.tsx`: Submit → Redirect zu `https://auth.mays-job-matcher.app/oauth2/authorize`
   (response_type=code, client_id, redirect_uri, scope, code_challenge).
4. Neue Route `/auth/callback` (App.tsx + vercel.json-Rewrite): Code gegen Tokens tauschen,
   `state` prüfen, dann zu `/search` oder `/me` weiterleiten.
5. `src/lib/risApi.ts`: `GET /me`, `GET/POST/PUT /me/profile` mit Bearer-Token;
   401 → Refresh, danach Logout-Prompt; 404 Profil → Provisionierungs-CTA.
6. Logout: Tokens löschen + Redirect zu Cognito `/logout` mit `logout_uri`.
7. Öffentliche Jobsearch-Funktionen bleiben ohne Login nutzbar (kein globaler Auth-Gate).
8. Tests: PKCE-Vektoren, Callback-Parsing, Expiry/Refresh, 401-Handling, Logout.

### Phase 4 — End-to-End
- Browser-Login über `auth.mays-job-matcher.app` (Playwright).
- Callback → Tokens → RIS `/me` (200, `userId`/`email`/`tenantId`).
- Profil `GET/POST/PUT /me/profile`.
- Logout → Token weg, Cognito-Session beendet.
- Ungültiges/abgelaufenes JWT → RIS 401; Client räumt Session auf.
- Bestehende Jobsearch-Suche bleibt funktionsfähig.

**Freigabe-Gates:** Terraform-Apply (Phase 2), DNS-CNAME (Phase 2b), Testbenutzer-Anlage,
Jobsearch-Commits/Push. Phase 1 ist abgeschlossen und dokumentiert.

---

## Nachtrag: Testlauf 2026-10-20 10:26–10:40 UTC

- Current status: PHASE 1 COMPLETED + TESTED — 63/63 Live-Checks, 9/9 Static, 1581 pytest passed;
  Auth-Grundfunktionen grün; Phase-2-Lücken exakt lokalisiert.
- Terraform checks:
  - `terraform fmt -check -recursive`: PASS
  - `terraform validate`: PASS
  - `terraform plan -detailed-exitcode` nach Apply: **Exit 0** (kein Drift)
- Live-Vollserie `ris-development`: **63 PASS, 0 FAIL, 1 WARN** (Baseline).
- Static-Serie: **9 PASS, 0 FAIL, 1 WARN** (Baseline).
- Vollständige pytest-Suite: **1581 passed, 2 failed (Baseline), 11 skipped**.
- Auth-Tests:
  - M2M `client_credentials`: Token ausgestellt, `token_use=access`, `scope=ris-api/m2m:execute`, `iss` = RIS-Pool.
  - Human-Routen mit M2M-Token: 401 (Audience-Isolation).
  - M2M-Route ohne `X-Api-Credential`: 403; ohne/ungültigem Token: 401.
- Neue verifizierte Lücken:
  - OAuth-Authorize → `302 /error?error=redirect_mismatch` (keine Callback-URLs).
  - OIDC-Discovery Prefix-Domain → 404 (nur Custom Domain).
  - `auth.mays-job-matcher.app` → kein DNS-Record (000).
  - API-CORS `CorsConfiguration=null`; OPTIONS `/me` → 404 für Vercel- und localhost-Origin.
- Files changed:
  - `scripts/parallel_tests.sh` (+Target `ris-development`)
  - `docs/reports/01-02-MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01-TESTREPORT.md` (neu)
  - `docs/reports/01-01-MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01-EXECUTION_LOG.md` (dieser Nachtrag)
  - `docs/AI_AUDITLOG.md` (Test-Checkpoint)
- Current resume point: Phase 1 getestet und grün; nächster Schritt ist der Phase-2-Plan
  (Cognito OAuth Code+PKCE, Custom Domain, CORS-Entscheidung) — Apply/DNS nur mit Freigabe.
- AWS MUTATIONS (Testlauf): NONE (nur read-only AWS-Calls + Token-Ausstellung; kein Ressourcen-Change).
