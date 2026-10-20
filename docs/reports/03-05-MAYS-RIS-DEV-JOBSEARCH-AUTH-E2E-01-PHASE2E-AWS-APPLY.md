# MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01 — Phase 2E

**AWS Apply & Technical Verification**

- **Datum:** 2026-10-20
- **Branch:** `main` · **HEAD vor Apply:** `6886a0a` (`main == origin/main`)
- **Projekt:** `ris-dev` · **Workspace:** `ris-dev` · **Environment:** `dev`
- **Region:** `eu-central-1` · **Account:** `240571105849` (`arn:aws:iam::240571105849:user/Mayaws`)
- **Ergebnis:** **PHASE 2E: GREEN**

> **STOP eingehalten:** Keine DNS-Änderung, keine Testbenutzer, kein Frontend-/Orders-/Alpha-Branch-Change.

---

## 1. Preflight (alle Gates GREEN)

| Prüfung | Ergebnis |
|---|---|
| Git-Status | **sauber** |
| HEAD | `6886a0a2d244493316ee1d638f7daead98554cdf` |
| Branch | `main`, `main == origin/main` (0/0) |
| AWS-Account | `240571105849` (STS verifiziert) |
| Region | `eu-central-1` |
| Terraform-Backend | `s3://mays-ris-tf-state-dev`, key `dev/terraform.tfstate`, `workspace_key_prefix=env:` |
| Workspace | **`ris-dev`** (explizit) |
| Ressourcen im State | 169 |
| Overlay `ris-dev.json` | geladen; `identity_oauth_enabled=true`, `identity_custom_domain=auth.mays-job-matcher.app` |
| ACM-ARN | live verifiziert, identisch mit dem Overlay-Wert (**nicht geraten**) |
| ACM-Status | ISSUED (vor Apply) |

---

## 2. Terraform-Plan (aus aktuellem HEAD, neuer Plan)

```
Plan: 1 to add, 2 to change, 1 to destroy.
```

| Aktion | Ressource | Inhalt |
|---|---|---|
| create | `module.cognito.aws_cognito_user_pool_domain.custom[0]` | `auth.mays-job-matcher.app` + vorhandenes ACM |
| update | `module.cognito.aws_cognito_user_pool_client.client` | `code`+PKCE, Scopes, Callback/Logout, Provider `COGNITO` |
| update | `module.api.aws_apigatewayv2_api.ris_api` | CORS (explizite Origins) |
| destroy | `module.cognito.aws_cognito_user_pool_domain.domain[0]` | Prefix-Domain `ris-dev-dev` (freigegeben) |

**Harte Sicherheitsbedingungen — alle PASS:**

| Bedingung | Ergebnis |
|---|---|
| Keine Cognito-User-Pool-Replacements | ✅ |
| Keine Orders-Ressourcenänderungen | ✅ |
| Keine M2M-Änderungen | ✅ |
| Keine zusätzlichen Deletes (genau 1) | ✅ |
| Keine Replacements (`create`+`delete`) | ✅ |
| Keine IAM/DynamoDB/Lambda/SQS-Änderungen | ✅ |
| Fremde Workspaces unberührt | ✅ |

---

## 3. Apply-Ergebnis

```
Apply complete! Resources: 1 added, 2 changed, 1 destroyed.
```

- Gespeicherter, geprüfter Plan `/tmp/p2e.tfplan` angewandt; **keine** alten Plandateien wiederverwendet.
- **Keine** Reparatur-Applies, keine manuellen Änderungen außerhalb des Scopes.
- Log: `/tmp/p2e-apply.log`.

## 4. Post-Apply-Plan

```
No changes. Your infrastructure matches the configuration.
```

(`-detailed-exitcode` rc = 0 → Idempotenz wiederhergestellt.)

---

## 5. Technische Verifikation

### A. Terraform
Post-Apply-Plan **No changes** ✅ — State == Konfiguration.

### B. Cognito

| Prüfung | Ergebnis |
|---|---|
| RIS User Pool Identität | **unverändert** (`eu-central-1_ojbmoiYGM`, `ris-dev-dev-users`) |
| RIS App Client Identität | **unverändert** (`ris-dev-dev-client`, `7ldhihlpdgsgcl3puvu4oi7ksv`) |
| Authorization Code Flow | **aktiv** (`AllowedOAuthFlows=["code"]`, `AllowedOAuthFlowsUserPoolClient=true`) |
| Public Client ohne Secret | ✅ `ClientSecret = null` |
| OAuth-Scopes | `["email","openid","profile"]` ✅ |
| Callback-URLs | `http://localhost:5173/auth/callback`, `https://mays-job-matcher.vercel.app/auth/callback` ✅ |
| Logout-URLs | `http://localhost:5173/`, `https://mays-job-matcher.vercel.app/` ✅ |
| Custom Domain | **vorhanden**, Status **ACTIVE**, CloudFront `d1xd3gat3vr3ss.cloudfront.net` ✅ |
| Prefix-Domain `ris-dev-dev` | **entfernt** ✅ |
| Non-Browser-Login erhalten | `ALLOW_USER_PASSWORD_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH` ✅ |
| Orders Cognito Pool | **unverändert** (`eu-central-1_cmJWXujnb`, keine Domain) ✅ |
| M2M-Authentifizierung | **unverändert** (`ris-dev-dev-m2m-client`, `client_credentials`, Scope `ris-api/m2m:execute`) ✅ |

### C. ACM

| Prüfung | Ergebnis |
|---|---|
| Status | **ISSUED** ✅ |
| Domain-Zuordnung | `InUseBy = arn:aws:cloudfront::590490809858:distribution/EGVCW3XKINSHF` (Cognito-CloudFront) ✅ |
| RenewalEligibility | **ELIGIBLE** ✅ — die frühere `INELIGIBLE`-Auflage (A1) ist durch die Domain-Bindung **behoben** |
| Gültig bis | 2027-04-25 |

### D. API Gateway

| Prüfung | Ergebnis |
|---|---|
| CORS aktiv | ✅ (`AllowOrigins` gesetzt) |
| Nur freigegebene Origins | `http://localhost:5173`, `https://mays-job-matcher.vercel.app` ✅ |
| Kein Wildcard-Origin | ✅ |
| erlaubte Methoden | `GET,POST,PUT,PATCH,DELETE,OPTIONS` |
| erlaubte Header | `authorization, content-type, x-api-credential, x-api-profile` |
| Max-Age | 3600 |
| JWT-Authorizer | **unverändert** (`ris-dev-dev-jwt-human`/`-m2m`, Issuer `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ojbmoiYGM`) ✅ |
| API-Routen | **34 Routen unverändert** ✅ |

### E. Security

| Prüfung | Ergebnis |
|---|---|
| `/health` ohne Token | **401** ✅ |
| `/me` ohne Token | **401** ✅ |
| Secrets in Git/Report | keine (nur Variablen-Deklarationen; `client_secret` ausschließlich per `--var`) ✅ |
| IAM-Änderungen | keine ✅ |

---

## 6. Tests

| Prüfung | Ergebnis |
|---|---|
| `terraform fmt -check -recursive` | **FMT OK** |
| `terraform validate` | **Success** (nur vorbestehende Deprecation-Warnungen) |
| pytest (volle Suite) | **1616 passed, 2 failed, 3 skipped** |
| `./scripts/parallel_tests.sh ris-dev` | **64 PASS / 0 FAIL / 1 WARN** |

- **S1.5-Plan-Drift-FAIL ist verschwunden** (Idempotenz = 0, wie erwartet).
- Die 2 pytest-Fehler sind die **dokumentierten Baseline-Defekte** (`AGENTS.md`), **keine** Phase-2E-Regression.
- WARN `S6.1` = dieselben Baseline-Defekte.

---

## 7. Abweichungen

Keine. Der applyte Plan entsprach exakt dem freigegebenen Scope (1/2/1).

## 8. Offene Punkte (nicht Teil von 2E, gesperrt)

1. **DNS:** CNAME `auth.mays-job-matcher.app` → CloudFront `d1xd3gat3vr3ss.cloudfront.net` bei checkdomain.de — **nicht freigegeben**. Ohne DNS liefert die Custom-Domain extern noch keinen OIDC-Endpunkt.
2. **Testbenutzer** im Pool `ris-dev-dev-users` — **nicht freigegeben**.
3. **Jobsearch-Frontend**-Verdrahtung (Code+PKCE, `/auth/callback`) — Phase 3.
4. **Auflagen aus Phase 2D:** A1 (ACM-Renewal) ist **behoben**; A2 (Prefix entfällt) **bestätigt**; A3 (DNS extern) bleibt offen.

---

## 9. Abschlussgate

| Kriterium | Status |
|---|---|
| Apply erfolgreich | ✅ |
| Post-Apply-Plan No changes | ✅ |
| RIS Cognito unverändert in Identität | ✅ |
| Custom Domain angelegt | ✅ |
| OAuth korrekt | ✅ |
| CORS korrekt | ✅ |
| Orders unverändert | ✅ |
| Keine neuen kritischen Testfehler | ✅ |

### **PHASE 2E: GREEN**

**Phase 3 vorbereitet, aber NICHT gestartet.** Keine DNS-Änderung ohne neue Freigabe.
