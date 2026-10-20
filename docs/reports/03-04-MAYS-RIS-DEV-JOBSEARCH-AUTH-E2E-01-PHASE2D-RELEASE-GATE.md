# MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01 — Phase 2D

**Final Release Gate — GO / NO-GO für den AWS-Apply**

- **Datum:** 2026-10-20
- **Branch:** `main` · **Commit:** `05c6dcb` (gepusht, `main == origin/main`)
- **Projekt:** `ris-dev` · **Workspace:** `ris-dev` · **Environment:** `dev`
- **Region:** `eu-central-1` · **Account:** `240571105849`
- **Plan-Artefakt:** `/tmp/p2d.tfplan` (`Plan: 1 to add, 2 to change, 1 to destroy.`)
- **Ergebnis:** **GO für den AWS-Apply** — mit 3 dokumentierten Auflagen (siehe §7).

> **STOP eingehalten:** Kein `terraform apply`, keine DNS-Änderung, keine Testbenutzer.

---

## 1. Git-Status und Commit `05c6dcb`

| Prüfung | Ergebnis |
|---|---|
| Working Tree | **sauber** (`git status --porcelain` leer) |
| HEAD | `05c6dcb7623c7067221cfdfaf37e36eb2c4ec2c4` |
| `origin/main` | **identisch** (`05c6dcb…`) |
| Ahead/Behind | 0/0 |
| Push | **erfolgt**: `7492eb9..05c6dcb  main -> main` |
| Alpha-Branch `feature/integration` | **unberührt** |

Commit-Inhalt: 12 Dateien, +811/−13 (Cognito-Modul, API-Modul, `installer/project-configs/ris-dev.json`,
`installer/ris.py`, `scripts/parallel_tests.sh`, Overlay-Tests, Audit-Log, Phase-2-Report).

---

## 2. ACM-Zertifikat und Domain-Voraussetzungen

| Prüfung | Ergebnis |
|---|---|
| ACM `auth.mays-job-matcher.app` (us-east-1) | **ISSUED**, `AMAZON_ISSUED`, SAN exakt = Domain |
| Validierung | **DNS**, `ValidationStatus=SUCCESS` (Record `_ae77d705…auth.mays-job-matcher.app`) |
| `InUseBy` | `[]` (noch an keinen Alias gebunden) |
| Gültig bis | **2027-04-25** |
| `RenewalEligibility` | ⚠️ **INELIGIBLE** (Auflage A1, §7) |
| Region-Anforderung | ✅ Cognito verlangt us-east-1 — Zertifikat liegt in us-east-1 |
| Terraform-Referenz | Modul-Validation erzwingt `:acm:us-east-1:` im ARN |

**Domain-Voraussetzungen:** DNS-Validierung erfolgreich; der Custom-Domain-Alias-Target
entsteht erst durch den Apply (`describe-user-pool-domain` → `CloudFrontDistribution`).
DNS-CNAME bei checkdomain.de ist extern und separat freizugeben.

---

## 3. Abgleich Callback-/Logout-URLs mit dem Jobsearch-Frontend

**Ist-Zustand Frontend (verifiziert):** `LoginForm.tsx`/`RegisterForm.tsx` sind reine
UI-Platzhalter („kein Cognito"); `.env.example` enthält **keine** Cognito/Redirect-Werte;
es gibt **keine** `/auth`-Route und **keinen** `vercel.json`-Rewrite dafür. Das Frontend ist
also noch nicht verdrahtet — die kanonischen URLs sind Design-Vorgabe aus Phase 1.

**Abgleich Overlay ↔ Phase-1-Vorgabe (`01-01-…-EXECUTION-LOG.md`, Z. 136-139):**

| Zweck | Phase-1-Vorgabe | Overlay (committed) | Match |
|---|---|---|---|
| Callback lokal | `http://localhost:5173/auth/callback` | dito | ✅ |
| Callback prod | `https://mays-job-matcher.vercel.app/auth/callback` | dito | ✅ |
| Logout lokal | `http://localhost:5173/` | dito | ✅ |
| Logout prod | `https://mays-job-matcher.vercel.app/` | dito | ✅ |
| CORS-Origins | (Phase 3) | `http://localhost:5173`, `https://mays-job-matcher.vercel.app` | ✅ |

**Nicht aufgenommen (bewusst):** Vercel-Preview-Wildcard `https://*.vercel.app/auth/callback`.
Cognito erlaubt Wildcards nur begrenzt; die Aufgabe verbietet pauschale Freigaben. Preview-URLs
sind bei Bedarf später explizit zu ergänzen.

**Kanonische Domain** für Authorize/Token/Logout: `https://auth.mays-job-matcher.app/oauth2/…`.

---

## 4. Terraform-Plan — Aktualität und Scope

Neu erzeugt aus dem **committeten HEAD** (Overlay-Werte aus `load_project_config`):

```
Plan: 1 to add, 2 to change, 1 to destroy.
```

| Aktion | Ressource | Inhalt |
|---|---|---|
| update | `module.api.aws_apigatewayv2_api.ris_api` | `cors_configuration: [] → [explizite Origins]` |
| update | `module.cognito.aws_cognito_user_pool_client.client` | `code` + PKCE + Scopes + Callback/Logout + Provider `COGNITO` |
| create | `module.cognito.aws_cognito_user_pool_domain.custom[0]` | `auth.mays-job-matcher.app` + vorhandenes ACM |
| destroy | `module.cognito.aws_cognito_user_pool_domain.domain[0]` | Prefix-Domain `ris-dev-dev` |

| Scope-Prüfung | Ergebnis |
|---|---|
| Plan aktuell (gegen committed HEAD, Baum sauber) | ✅ |
| Änderungen nur im vorgesehenen Scope | ✅ 4 Ressourcen |
| Keine unbeabsichtigte Erneuerung (replace) | ✅ **keine** |
| Kein Destroy von RIS-/Orders-Komponenten | ✅ einziger Destroy = Prefix-Domain (Cognito-Vorgabe) |
| Keine Fremd-Workspace-Änderung | ✅ Workspace `ris-dev` isoliert |
| Keine Orders-Pool-Änderung | ✅ 0 |
| Keine Secrets | ✅ |

---

## 5. Domain-Wechsel ohne Auth-Unterbrechung

**Zentrale Sicherheitsprüfung — der JWT-Authorizer hängt NICHT an der Domain:**

```
Issuer (live): https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ojbmoiYGM
```

Der Issuer ist der **regionale Cognito-Endpoint**, nicht die Hosted-UI-Domain. Der
Domain-Wechsel ändert daher **nicht** Issuer/Audience → bestehende und künftige JWTs werden
unverändert validiert.

| Frage | Befund |
|---|---|
| Betrifft der Domain-Wechsel die API-Authorizer? | **Nein** (Issuer = `cognito-idp…`, nicht Domain) |
| Bricht der Wechsel bestehende Nutzer/Clients? | **Nein** (Client bleibt derselbe, wird nur erweitert) |
| Bricht `USER_PASSWORD_AUTH` (Nicht-Browser-Login)? | **Nein** (`explicit_auth_flows` unverändert) |
| Ist die Prefix-Domain anderswo referenziert? | **Nein** (nur Modul-Namensformel; Orders-Pool hat keine Domain) |
| Neue Endpunkt-URL | `https://auth.mays-job-matcher.app/oauth2/authorize|token|logout` |
| Alte Prefix-URL betroffen | `ris-dev-dev.auth.eu-central-1.amazoncognito.com` entfällt — **ohne verifizierten Nutzer** |

**Kurz:** Der Domain-Wechsel ist auth-neutral für die API. Einzige Verhaltensänderung ist die
Hosted-UI-URL — und die war noch nie produktiv im Einsatz.

### ⚠️ Konflikt-Auflage (A2): Phase-1-Plan vs. Cognito-Realität

Der Phase-1-Entwurf (`01-01-…`, Z. 128-130) sagte: „**Prefix-Domain bleibt bestehen**" und
wollte die Custom Domain *zusätzlich* anlegen. **Cognito erlaubt pro Pool nur EINE Domain
(Prefix ODER Custom).** Phase 2 löst das korrekt, indem die Prefix-Domain weicht. Das ist
beabsichtigt und dokumentiert, weicht aber vom Phase-1-Wortlaut ab → im Freigabebericht
explizit zu bestätigen.

---

## 6. Freigabebericht — Vorlage

Der Apply ist vorbereitet und geprüft. Nach Freigabe wirkt genau dieser Plan:

```bash
cd terraform
terraform apply /tmp/p2d.tfplan     # 1 add, 2 change, 1 destroy
```

Danach (separat freizugeben):
1. `aws cognito-idp describe-user-pool-domain --domain auth.mays-job-matcher.app`
   → `CloudFrontDistribution` (Alias-Target) auslesen.
2. Bei checkdomain.de: CNAME `auth` → Alias-Target (TTL 300).
3. Verifikation: `https://auth.mays-job-matcher.app/.well-known/openid-configuration` → 200.
4. Testbenutzer im Pool `ris-dev-dev-users` (erst nach DNS, für Phase 3).

---

## 7. Ergebnis: **GO für den AWS-Apply**

**Begründung:** Der Plan ist sauber, minimal und vollständig im vorgesehenen Scope
(1 add / 2 change / 1 destroy, keine Replacements, kein Orders-/Pool-Destroy), er ist gegen
den gepushten HEAD `05c6dcb` reproduzierbar, und der Domain-Wechsel ist auth-neutral
(JWT-Issuer unabhängig von der Domain). Der einzige Destroy ist eine Cognito-Vorgabe, keine
Komponente.

**Auflagen (vor Apply zu bestätigen bzw. zu verfolgen):**

- **A1 — ACM-Renewal:** `RenewalEligibility = INELIGIBLE` bei Gültigkeit bis 2027-04-25.
  Nach dem Apply, sobald die Domain gebunden ist, Renewal-Status erneut prüfen; ggf. Cert
  neu ausstellen. (Kein Blocker für jetzt.)
- **A2 — Domain-Semantik:** Bestätigen, dass die **Prefix-Domain `ris-dev-dev` entfällt** und
  `auth.mays-job-matcher.app` die einzige Hosted-UI-Domain wird (Cognito erlaubt nur eine).
  Weicht vom Phase-1-Wortlaut ab, ist aber die einzig gültige Option.
- **A3 — DNS extern:** Der CNAME bei checkdomain.de ist **nicht** Teil von Terraform und
  bleibt gesperrt, bis separat freigegeben. Der Apply selbst berührt kein DNS.

**Nicht Blocker, aber für Phase 3 nötig:** Frontend-Verdrahtung (Code+PKCE, `/auth/callback`),
OIDC-Discovery-200, OPTIONS-Preflight-200, Testbenutzer.

---

## Anhang — Erst-Apply vs. Folge-Apply

- **Erst-Apply (dieser Plan):** 1 add / 2 change / 1 destroy. Nach Apply muss
  `parallel_tests.sh ris-dev` `S1.5` wieder grün zeigen (Idempotenz = 0).
- **Folge-Plan:** erwartet **No changes**.
- **Rollback:** `--var=identity_oauth_enabled=false` (Client ohne OAuth) bzw.
  `--var=identity_custom_domain_enabled=false` (zurück zur Prefix-Domain) — beide Overlay-Werte
  lassen sich so gezielt überschreiben, Projekt-Identität bleibt geschützt.
