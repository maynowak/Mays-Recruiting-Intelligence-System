# MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01 — Testbericht Phase 1 (2026-10-20)

**Ziel:** Verifizieren, dass die dauerhafte Development-Installation `ris-development`
vollständig, idempotent, ownership-sauber und auth-seitig korrekt aufgebaut ist —
und die Lücken für Phase 2/3 exakt benennen.

**Testobjekt:** Workspace `ris-development`, `project_name=ris-development`,
`environment=dev`, Prefix `ris-development-dev`, API `https://klklimekab.execute-api.eu-central-1.amazonaws.com`
**Runner:** `scripts/parallel_tests.sh` (neuer Target `ris-development`)
**Ausführungs-Log:** [01-01-…-EXECUTION_LOG.md](01-01-MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01-EXECUTION_LOG.md)

---

## 1. Static / Regression (keine AWS-Mutation)

`TF_DATA_DIR=/tmp/tfris-development AWS_PROFILE=mayaws ./scripts/parallel_tests.sh static`

| ID | Test | Erwartung | Ist | Status |
|---|---|---|---|---|
| R1.1 | `terraform fmt -check -recursive` | sauber | sauber | ✅ PASS |
| R1.2 | `terraform validate` | Success | Success | ✅ PASS |
| R1.3 | `tests/test_ris_installer.py` | 0 unerwartete Fehler | 1 dokumentierter Baseline-Defekt | ⚠️ WARN |
| R1.4 | API-Contract (`test_p20_api_contract_consistency.py`) | grün | 21 passed | ✅ PASS |
| R1.4 | Health-Contract (`test_p20_health_contract.py`) | grün | 12 passed | ✅ PASS |
| R1.4 | Credential-Lifecycle (`test_p17_credential_lifecycle.py`) | grün | 25 passed | ✅ PASS |
| R1.5 | Lambda-Bundles vorhanden | 4 Dateien | 4 Dateien (orders-reader, health-writer, health-publisher, agent) | ✅ PASS |

**Ergebnis: 9 PASS, 0 FAIL, 1 WARN** (Baseline `test_validate_skips_workspace_without_backend`, AGENTS.md Z.39).

## 2. Vollserie `ris-development` (read-only, 63 Checks)

`TF_DATA_DIR=/tmp/tfris-development AWS_PROFILE=mayaws ./scripts/parallel_tests.sh ris-development`

### 2.1 State / Ownership / Idempotenz

| ID | Test | Erwartung | Ist | Status |
|---|---|---|---|---|
| S1.1 | Workspace-Guard | `ris-development` | `ris-development` | ✅ |
| S1.2 | State-Ressourcen (ohne `data.*`) | 169 | **169** | ✅ |
| S1.3 | Fremd-Namen im State (`mays-ris-dev-`, `mays-orders-`, `ris-a`) | 0 | **0** | ✅ |
| S1.4 | Fremd-Präfix in geplanten Changes | 0 | **0** | ✅ |
| S1.5 | Idempotenz `plan -detailed-exitcode` | Exit 0 | **Exit 0** | ✅ |
| S1.6 | Output == Live-Name | `ris-development-dev-work-items` | dito | ✅ |
| S1.7 | S3-State `env:/ris-development/terraform.tfstate` | vorhanden | vorhanden (2026-10-20 10:18:55 UTC) | ✅ |

### 2.2 Inventar

| ID | Test | Erwartung | Ist | Status |
|---|---|---|---|---|
| S2.1 | Lambdas + Runtime | 6, `python3.14` | 6, `python3.14` | ✅ |
| S2.2 | Kern-Tabellen / Orders-Tabelle / Lock | 10 / ACTIVE / ACTIVE | 10 / ACTIVE / ACTIVE | ✅ |
| S2.3 | HTTP-APIs | 2 (`-dev-api`, `-api`) | 2 | ✅ |
| S2.4 | SQS + DLQ-Redrive | 6, Work-Queue → DLQ | 6, Redrive vorhanden | ✅ |
| S2.5 | S3-Buckets + Public-Block | 5, BlockPublicAcls=True | 5, True | ✅ |
| S2.6 | Cognito-Pools / Gruppe / E-Mail-Verify | 2 / `staff` / `email` | 2 / 1 / `email` | ✅ |
| S2.7 | Dashboards / Alarme / ALARM-Zustand | 2 / 13 / 0 | 2 / 13 / 0 | ✅ |
| S2.8 | CloudTrail multi-region / HomeRegion | 1 / True / eu-central-1 | 1 / True / eu-central-1 | ✅ |
| S2.9 | Log-Groups / Retention / ohne Retention | 6 / 7d+14d / 0 | 6 / 7+14 / 0 | ✅ |

### 2.3 API / Auth / Verkabelung

| ID | Test | Erwartung | Ist | Status |
|---|---|---|---|---|
| S3.1 | Orders-Routen auf Kern-API | 4, `POST /orders`, `PATCH /orders/{id}/status` | 4, vorhanden | ✅ |
| S3.2 | Orders-API-Routen / NONE | 4 / 0 | 4 / 0 | ✅ |
| S3.3 | Kern-API NONE / Authorizer | 0 / 2 | 0 / 2 (jwt-human, jwt-m2m) | ✅ |
| S3.4 | `/health`, `/platform`, `/me`, `/orders` ohne Token | je 401 | je **401** | ✅ |
| S4.1 | Reader-Env `ORDERS_TABLE` / Queue | `ris-development` / `…-orders-queue` | dito | ✅ |
| S4.2 | ESM orders→worker / work→agent | Enabled/5 / Enabled | dito | ✅ |
| S4.3 | Reader-IAM Least Privilege | PutItem/Query/SendMessage, gebunden | dito | ✅ |
| S5.1 | Alt-Präfixe `mays-ris-dev`/`mays-orders` | 0 | 0 | ✅ |
| S5.2 | Fremdinstallation `ris-a` | abwesend | 0 (Lambda/Tabelle/API/Dashboard) | ✅ |
| S5.3 | Fremde e2e-Ressourcen | unberührt | CF `E1R3BHTJNMC6XW` + OAC vorhanden | ✅ |
| S6.1 | Code-Kontrakte Health/Credential/API/Installer | grün | 12/25/21 passed, 1 Baseline-WARN | ✅/⚠️ |

**Ergebnis: 63 PASS, 0 FAIL, 1 WARN** — Installation ist vollständig, idempotent und frei von Fremd-Namen.

## 3. Vollständige pytest-Suite

`python3 -m pytest tests/ -q -p no:cacheprovider`

| Kennzahl | Wert |
|---|---|
| passed | **1581** |
| failed | **2** (dokumentierte Baseline-Defekte) |
| skipped | 11 |
| Laufzeit | 31,12 s |

Fehlgeschlagen (bekannt, nicht durch diese Installation verursacht):
- `tests/test_ris_installer.py::test_install_dry_run_performs_no_mutation`
- `tests/test_ris_installer.py::test_validate_skips_workspace_without_backend`

## 4. Auth-Tests (live, ohne Benutzeranlage)

### 4.1 M2M `client_credentials` (Cognito)

| Test | Erwartung | Ist | Status |
|---|---|---|---|
| Token-Endpoint `…/oauth2/token` | 200 + `access_token` | OK | ✅ |
| `token_use` | `access` | `access` | ✅ |
| `client_id` | M2M-Client `2mnues4isf9ergm80cru81037o` | dito | ✅ |
| `scope` | `ris-api/m2m:execute` | dito | ✅ |
| `iss` | RIS-Pool `eu-central-1_7QCp09XEZ` | dito | ✅ |
| `expires_in` | 3600 | 3600 | ✅ |

### 4.2 JWT-Vertrauensgrenze

| Test | Erwartung | Ist | Status |
|---|---|---|---|
| Human-Routen (`/health`,`/platform`,`/me`,`/agents`) mit **M2M**-Token | 401 (Audience-Isolation) | je **401** | ✅ |
| `POST /v1/m2m/agents/dummy-a/execute` mit M2M-Token, **ohne** `X-Api-Credential` | 403 | **403** | ✅ |
| dieselbe Route ohne Token | 401 | **401** | ✅ |
| dieselbe Route mit ungültigem Token | 401 | **401** | ✅ |
| `/me` mit ungültigem Token | 401 | **401** | ✅ |

**Befund:** Die Zwei-Credential-Regel (JWT **+** `X-Api-Credential`) greift; die
Human-/M2M-Authorizer sind über die Audience sauber getrennt.

## 5. Phase-2-Lücken (verifiziert)

| Test | Erwartung (Ziel) | Ist | Status |
|---|---|---|---|
| OAuth-Authorize mit `redirect_uri=http://localhost:5173/auth/callback` | Login-Seite/Code | **302 → `/error?error=redirect_mismatch`** | ❌ Phase 2 |
| App-Client `AllowedOAuthFlowsUserPoolClient` | `true` | **`false`** | ❌ Phase 2 |
| Callback-/Logout-URLs am Client | gesetzt | **keine** | ❌ Phase 2 |
| OIDC-Discovery Prefix-Domain | 200 | **404** (AWS liefert `.well-known` nur auf Custom Domain) | ❌ Phase 2 |
| OIDC-Discovery `auth.mays-job-matcher.app` | 200 | **DNS 000** (kein Record) | ❌ Phase 2b |
| ACM `auth.mays-job-matcher.app` (us-east-1) | ISSUED | **ISSUED**, `InUseBy=[]` | ✅ vorhanden |
| API-CORS (`CorsConfiguration`) | Origins für Jobsearch | **`null`** | ❌ Phase 3 |
| OPTIONS `/me` von `https://mays-job-matcher.vercel.app` | 200 + ACAO | **404** | ❌ Phase 3 |
| OPTIONS `/me` von `http://localhost:5173` | 200 + ACAO | **404** | ❌ Phase 3 |
| Custom Domain DNS | CNAME/Alais | kein Record; NS `ns.checkdomain.de` | ❌ Phase 2b |

**Konsequenz:** Vor dem Jobsearch-Login sind zwingend nötig:
1. Terraform: OAuth Code + PKCE am public Client aktivieren (Scopes, Callback-/Logout-URLs).
2. Terraform: `aws_cognito_user_pool_domain.custom` mit dem vorhandenen us-east-1-Cert.
3. DNS: CNAME `auth` → Cognito-Alias-Target bei checkdomain.de.
4. CORS am API Gateway **oder** serverseitiger Proxy in Vercel (Entscheidung offen).

## 6. Nicht getestet (bewusst, Freigabe nötig)

- **Human-Login E2E** (Hosted UI → Code → Token → `/me`): erfordert OAuth-Fix (Phase 2)
  und einen Testbenutzer mit `custom:tenant_id` (Cognito-Mutation).
- **Profil-Schreibpfad** (`POST/PUT /me/profile`): erfordert menschliches JWT.
- **DNS-/Custom-Domain-Verifikation**: erfordert Änderung bei checkdomain.de.

## 7. Gesamtergebnis

| Block | PASS | FAIL | WARN |
|---|---|---|---|
| Static | 9 | 0 | 1 |
| Vollserie `ris-development` | 63 | 0 | 1 |
| pytest gesamt | 1581 | 2 (Baseline) | — |
| Auth live | 9 | 0 | 0 |
| Phase-2-Lücken | 1 (Cert) | 7 | — |

**Klassifikation:** Phase 1 **GREEN**; Auth-E2E **YELLOW** bis Phase 2/3 umgesetzt sind.
**Nächster Schritt:** Phase-2-Terraform-Plan (Cognito OAuth + Custom Domain + CORS-Entscheidung),
Apply und DNS erst nach expliziter Freigabe.
