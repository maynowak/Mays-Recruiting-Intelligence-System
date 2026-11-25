# RIS-ERASURE-PARTNER-ROUTE-ALIGNMENT-01 — Partner-Edge Erasure Route Alignment

**Status:** `A — IMPLEMENTED / VERIFIED LOCAL / PUSH-READY`  
**Date:** 2026-11-25  
**Branch:** `feature/ris-erasure-partner-route-alignment-01`  
**Base:** `origin/main` `97a60df83a5db56ea750e4342d7a01b00c8ad56b`  
**No AWS / Terraform apply / plan-against-live / deploy / main merge.** Only local
static and unit verification.

## 1. Ausgangslage

Der Jobsearch-BFF-Vertrag ist:

```text
Jobsearch UI -> POST /api/ris/erasure
             -> RIS POST /v1/partner/me/erasure
                (Authorization: Bearer <Cognito JWT> + X-Api-Credential)
```

RIS `origin/main` (`97a60df`) implementierte nur `POST /me/erasure`
(Kernel-API, `terraform/modules/api/main.tf` + `lambda/handler.py`). Die
Partner-Route existierte ausschließlich auf älteren, nicht in `main` gemergten
Commits:

| Commit | Inhalt | Handler/TF identisch? |
|---|---|---|
| `451c12e` | `feat(privacy): expose partner-edge erasure route` | ja |
| `70a9fb9` | `fix(erasure): restore partner erasure route` | ja |

Beide Commits fügten lediglich hinzu:

- `lambda/handler.py`: ein Dispatch-Zweig, der `_partner_profile_context(event)`
  prüft und danach `_handle_me_erasure(event, context)` aufruft.
- `terraform/modules/partner_edge/main.tf`: `"POST /v1/partner/me/erasure"` in
  `local.routes`.

Ein `git grep "v1/partner/me/erasure"` auf `main` (ohne `docs/reports/`) lieferte
**keinen Treffer**: weder Handler, Terraform, OpenAPI, `API-STANDARD` noch
Tests kannten die Route.

## 2. Umsetzung

### 2.1 Handler (eine Lifecycle, keine zweite Lösch-Engine)

`lambda/handler.py`, direkt vor dem `consents`-Zweig:

```python
elif method == 'POST' and path == '/v1/partner/me/erasure':
    _partner_ctx, error = _partner_profile_context(event)
    if error:
        return error
    return _handle_me_erasure(event, context)
```

- Exakt die bewährte Verdrahtung aus `451c12e`/`70a9fb9`.
- `_handle_me_erasure` bleibt unverändert; `PrivacyErasure(` wird weiterhin
  genau **einmal** im Repository konstruiert (`lambda/handler.py:1562`).
- `POST /me/erasure` ist unverändert (gleicher Zweig, gleiche Funktion).

### 2.2 Authentifizierung / Tenant-Isolation

Die Route akzeptiert **keine** vom Browser gelieferten Tenant-, User-, Partner-
oder Application-IDs. Zwei Boundarys gelten nacheinander:

1. **API Gateway JWT-Authorizer** (beide Partner-APIs): Cognito-Signatur,
   Issuer und Audience, bevor die Lambda überhaupt läuft.
2. **`_partner_profile_context(event)`**: Access-Token (`token_use=access`),
   `X-Api-Credential` (Format + Store + Profil), ACTIVE Partner-Registry,
   `apiProfileId`- und `tenantId`-Bindung, Tenant-Konfliktprüfung,
   `sub`-Claim und `iss`.

Der Lifecycle selbst liest Identität ausschließlich aus
`_extract_user_context(event)`, also aus den vom Authorizer geprüften
JWT-Claims (`sub`, `custom:tenant_id`, `client_id`/`aud`,
`custom:partner_application_id`, `iss`). `event['body']`,
`queryStringParameters` und `pathParameters` werden im Erasure-Pfad nicht
gelesen (per Test gepinnt). Der bestehende
`partnerApplicationId`/`issuer`/`tenantId`-Registry-Rebind in
`_handle_me_erasure` bleibt aktiv.

Zusätzlich greift die vorhandene Fail-closed-Aktivierung:
`_handle_personal_api_boundary` liefert für **jedes** `/v1/partner/me/*` 503
solange `PARTNER_SURFACE_ENABLED != true`. Die Route ist damit genauso
gesperrt wie alle anderen Partner-Routen.

### 2.3 Terraform

| Datei | Änderung | Begründung |
|---|---|---|
| `terraform/modules/partner_edge/main.tf` | `"POST /v1/partner/me/erasure"` in `local.routes` | Partner-Gateway `ris-dev-jobsearch-api` ist der Host, den der Jobsearch-BFF aufruft |
| `terraform/modules/api/main.tf` | neues `aws_apigatewayv2_route.partner_erasure` (JWT) | Terraform-Provenance der Route, exakt wie bei allen anderen `/v1/partner/me/*`-Routen (`privacy_inspect`, `privacy_export`, consents, cvs, …) |

Beide Erweiterungen sind **additiv** und bestehen ausschließlich aus
API-Gateway-Routen. **Keine** IAM-, S3-, DynamoDB-, SQS-, Cognito- oder
Secret-Ressource wurde hinzugefügt oder geändert. Kein generiertes Modul wurde
hand-editiert (`terraform/modules/mays_orders/` unberührt).

Grund für die zweite Deklaration: Die bestehende Route-Governance-Invariante
(`tests/test_p20_api_contract_consistency.py`,
`tests/test_platform_openapi_contract.py`) verlangt, dass **jeder**
Handler-Dispatch-Zweig eine Terraform-deklarierte Route **und** einen
OpenAPI-Eintrag mit `x-infrastructure-governance: terraform-managed` besitzt.
Eine Partner-Edge-only-Route ohne Provenance hätte entweder den Dispatch-Test
gebrochen oder eine Ausnahme im Test erzwungen; beides wäre eine stille
Vertragslücke. Die Route wird deshalb – konsistent zum bestehenden Muster –
auf beiden APIs deklariert.

### 2.4 Doku / Contract

- `docs/api/API-STANDARD.md`: Zeile
  `| POST /v1/partner/me/erasure | JWT + X-Api-Credential | 200, 207 (partial) | 401, 403, 500, 503 |`
  in der Partner-Tabelle (§2.1.1).
- `docs/api/openapi-platform.yaml`: neue Operation `erasePartnerUserData`
  (`POST /v1/partner/me/erasure`) mit `ApiCredential`-Parameter, denselben
  `ErasureResult`-Schemas, `207`-Teilerfolg und den Markern
  `x-infrastructure-governance: terraform-managed`,
  `x-deletion-scope: ordered-lifecycle-credentials-first`,
  `x-is-account-erasure: true`, `x-terminal-work-retained: true`.
  Kein Request-Body: Identität kommt ausschließlich aus JWT + Credential.
- `docs/privacy/RIS_PRIVACY_CAPABILITY_CONTRACT.md`: eine Klarstellung, dass
  die Partner-Route ein **Alias** der bestehenden G5-Lifecycle ist und keine
  zweite Pipeline.

## 3. Tests

Neu: `tests/test_partner_erasure_route.py` (15 Tests)

| Test | Prüft |
|---|---|
| `test_partner_edge_declares_the_erasure_route` | Partner-Edge `local.routes` enthält die Route; kein `ANY`/`{proxy+}` |
| `test_kernel_api_declares_the_same_route_for_provenance` | `partner_erasure`-Ressource mit JWT-Authorizer; keine neuen Ressourcenfamilien im Block |
| `test_post_dispatches_to_the_existing_erasure_lifecycle` | POSITIV: `_partner_profile_context` → `_handle_me_erasure`, Status 207 durchgereicht |
| `test_denied_partner_context_never_invokes_the_lifecycle` | NEGATIV: 403, Lifecycle nicht aufgerufen |
| `test_non_post_method_does_not_reach_the_lifecycle` | GET/PUT/DELETE/PATCH → 404, weder Context noch Lifecycle |
| `test_kernel_me_erasure_still_dispatches_to_the_lifecycle` | `/me/erasure` funktioniert unverändert und verlangt **kein** Partner-Credential |
| `test_kernel_erasure_route_still_declared_in_api_terraform` | `/me/erasure`-Route bleibt, je genau eine Route-Ressource |
| `test_there_is_exactly_one_erasure_engine` | genau ein `PrivacyErasure(`, ein `_handle_me_erasure`, zwei Aufrufer |
| `test_partner_route_reads_no_identity_from_the_request` | Dispatch-Zweig liest weder Body noch Query/Path-Parameter |
| `test_erasure_lifecycle_derives_identity_from_jwt_only` | Lifecycle nutzt `_extract_user_context`, keine Body-Identität |
| `test_real_boundary_denies_a_missing_partner_credential` | echte Boundary (kein Mock): 401, Lifecycle nicht aufgerufen |
| `test_real_boundary_denies_a_malformed_partner_credential` | JWT-förmiger Wert im Credential-Header → 401 |
| `test_real_boundary_denies_an_unauthenticated_caller` | kein `sub` → 401 |
| `test_partner_erasure_is_closed_while_the_surface_is_disabled` | `PARTNER_SURFACE_ENABLED=false` → 503 `not activated` |
| `test_partner_erasure_gate_is_prefix_based_not_route_specific` | Gate deckt `/v1/partner/me/` präfixbasiert |

Angepasst:

- `tests/test_p20_api_contract_consistency.py`: Route-Inventar 74 → **75**
  Deklarationen (70 → **71** agent-Routen, 4 orders-reader unverändert); die
  neue Route wird explizit gepinnt.
- `tests/test_partner_surface_gate.py`: `/v1/partner/me/erasure` in der
  Fail-closed-Routenliste.

Ausgeführte Checks (lokal, Python 3.12.3):

```text
python3 -m pytest tests/test_partner_erasure_route.py -q
  -> 15 passed

python3 -m pytest tests/test_partner_erasure_route.py \
  tests/test_p20_api_contract_consistency.py \
  tests/test_platform_openapi_contract.py tests/test_partner_surface_gate.py -q
  -> 63 passed, 322 subtests passed

python3 -m pytest tests/test_privacy_erasure_security.py \
  tests/test_privacy_lifecycle_evidence.py tests/test_privacy_erasure_contract.py \
  tests/test_privacy_erasure_repository.py tests/test_public_application_erasure.py \
  tests/test_application_erasure.py tests/test_r08_c0e_g5_authorization.py \
  tests/test_consent_gate.py tests/test_partner_profile_integration_harness.py \
  tests/test_partner_terraform_wiring.py -q
  -> 139 passed

python3 -m pytest tests/test_partner_security_boundary.py \
  tests/test_partner_privacy_inspection.py tests/test_partner_registry_atomicity.py \
  tests/test_privacy_receipt_contract.py tests/test_r08_c0f_s3_erasure.py \
  tests/test_r08_c1a_profile_only_erasure.py \
  tests/test_r08_c1b_document_erasure_integration.py \
  tests/test_r08_p1_1_canonical_contract.py \
  tests/test_application_privacy_contract.py tests/test_partner_cv_document_api.py -q
  -> 216 passed, 6 subtests passed

python3 -m pytest tests/ -q -p no:randomly
  -> 3206 passed, 129 skipped, 4 failed, 446 subtests passed
```

Die 4 Full-Suite-Fehler sind **umgebungsbedingt und vorbestehend**, nicht durch
diese Änderung verursacht. Gegenprobe mit `git archive origin/main` (identischer
Baum ohne diese Änderungen, `/tmp/opencode/ris-base-check`):

```text
tests/test_composite_lifecycle.py::TestOrchestratorArgOrdering::{test_global_flags_precede_command,
  test_extra_args_after_command, test_full_output_not_truncated}
tests/test_lambda_packaging.py::TestPackage::test_c_exclusions
-> 4 failed, 45 passed, 2 skipped  (identisch auf origin/main)
```

`test_lambda_packaging` benötigt das nicht eingecheckte Build-Artefakt
`terraform/lambda.zip` (`python lambda/build_zip.py --bundle all`);
`test_composite_lifecycle` betrifft die Installer-Orchestrierung und liest
unseren Handler/Terraform-Code nicht.

## 4. Terraform-Prüfungen (ohne AWS/Backend)

```text
terraform fmt -check -recursive            -> PASS (Exit 0)
cd terraform/modules/partner_edge && terraform init -backend=false && terraform validate
                                            -> Success! The configuration is valid.
cd terraform/modules/api && terraform init -backend=false && terraform validate
                                            -> Success! The configuration is valid.
```

Root-Level `terraform init -backend=false` + `terraform validate` wurde
zusätzlich versucht und schlägt **vorbestehend** fehl:
`module.mays_orders[0]` (lokal generiertes, gitignored Modul) besitzt kein
Attribut `iam_handler_role_name`, referenziert in `terraform/main.tf:257`.
Gegenprobe mit `git archive origin/main` (`/tmp/opencode/ris-base-tf`) zeigt
denselben Fehler ohne diese Änderung; die lokale generierte Modulversion
driftet gegen den Root-Vertrag. Die beiden von dieser Änderung berührten
Module validieren sauber. `terraform/.terraform.lock.hcl` wurde nach dem
Init-Versuch auf den getrackten Stand zurückgesetzt.

Kein `plan`, kein `apply`, kein State-Zugriff, keine AWS-CLI/SDK-Aktion.
Sämtliche `.terraform/`-Verzeichnisse und das untracked
`partner_edge/.terraform.lock.hcl` wurden nach der Prüfung entfernt; das
getrackte `terraform/modules/api/.terraform.lock.hcl` ist unverändert.

## 5. Jobsearch-BFF-Kompatibilität

**HTTP-Vertrag auf `main` jetzt kompatibel:** `POST /v1/partner/me/erasure`
existiert auf dem Partner-Gateway (`terraform/modules/partner_edge`), verlangt
JWT + `X-Api-Credential`, ist tenant-/partner-gebunden und liefert die
bestehende `ErasureResult`-Antwort mit `200`/`207`. Der Jobsearch-BFF erhält
damit keine 404/403 aus fehlender Route mehr.

**Semantische Grenze (offen, nicht Teil dieses Auftrags):** Die auf `main`
vorhandene Lifecycle (`agents/ecosystem/privacy_erasure.py`) führt die
G5-Schritte aus (Credentials widerrufen, API-Profile widerrufen, nichtterminale
Work-Items canceln, ApplicationV1, Dokumente, UserProfile-Zeile). Die auf
`ris-dev` deployte Branch-Lineage enthält zusätzlich den
`erase-partner-search-profiles`-Schritt (RIS-ACCOUNT-ERASURE-SEARCH-PROFILES-01)
und das CVDocument-Metadaten-Löschen. Diese Schritte sind **nicht** in `main`
und wurden hier bewusst nicht nachgezogen (kein zweiter Löschmotor, keine
Scope-Ausweitung). Folge: Auf `main` würde der BFF `complete: true` erhalten,
obwohl RIS-Partnerprofile (CV-/Suchprofile) noch existieren. Das ist eine
eigenständige, bereits dokumentierte Privacy-Lücke (P3), die vor einem
Produktions-Rollout separat gemerged/deployt werden muss.

## 6. Offene Punkte / benötigte Freigaben

1. **Terraform-Apply:** Zwei additive API-Gateway-Routen (Partner-Edge und
   Kernel-API) benötigen einen neuen, separat freigegebenen Plan/Apply. Kein
   IAM-/Daten-Change. Kein Plan in diesem Auftrag erstellt.
2. **`PARTNER_SURFACE_ENABLED`:** Die Route bleibt fail-closed (503), solange
   die Partner-Oberfläche nicht explizit aktiviert ist.
3. **Lifecycle-Parität:** siehe §5 – Search-Profile-/CVDocument-Erasure aus der
   Branch-Lineage fehlt auf `main` (separater Auftrag).
4. **Live-E2E:** nicht ausgeführt (kein AWS, keine synthetische Identität, keine
   echten Daten). Nach Apply separat mit synthetischem Testnutzer durchzuführen.
5. **Backups/PITR:** unverändert außerhalb des G5-Scopes.

## 7. Aussagegrenzen

- Keine AWS-, Cognito-, CloudFront-, DNS-, IAM-, DynamoDB-, S3- oder
  API-Gateway-Mutation.
- Kein `terraform plan`/`apply` gegen Live-State, keine State-/Lineage-Prüfung.
- Keine echten personenbezogenen Daten verarbeitet.
- Kein Merge nach `main`, kein Push nach `main`, kein Deploy.
- Die Route ist statisch und per Unit-Test verifiziert, **nicht** live.
