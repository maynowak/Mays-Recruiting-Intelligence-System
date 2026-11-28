# RIS-DEV2-CANARY-BASE-PLAN-04

**Datum:** 2026-11-25
**Branch / Baseline:** `feature/ris-analysis-integration-07` / `d0678113d053f174ff0808b32ddbe73342dd5d66`
**MO-Pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`
**Modus:** Planvorbereitung; **kein Apply, keine Cognito-/AWS-Mutation, kein State-Write**

## Ergebnis

**READY FOR BASE APPLY APPROVAL**

Der Basis-Plan ist erzeugt und vollständig geprüft: **2 Add / 8 Change /
0 Destroy / 0 Replace** — exakt der erwartete Umfang, ohne erzwungene Zahlen.
`ANALYSIS_SYNTHETIC_MODE=false`, keine Platzhalter-Identitäten, keine
Consent-Lockerung.

## 1. Plan

| Feld | Wert |
| --- | --- |
| Datei | `C:\tmp\ris-dev2-base-04.tfplan` |
| Größe | 252 768 Bytes |
| SHA-256 | `9b1e5a66384b593885d4f10061f7d55cbbcb91af04aa60e4f3091fc52a1f613c` |
| Terraform | 1.17.0; `applyable=true`, `complete=true`, `errored=false` |
| Provider | AWS `6.67.0`, time `0.14.2` (Lockfile) |
| Summary | **2 Add / 8 Change / 0 Destroy / 0 Replace** (264 No-op) |

### Adds (2)

1. `module.dynamodb.aws_dynamodb_table_item.agent_catalog_seed["analysis-agent"]`
   — `agentId=analysis-agent`, `version=1.0.0`, `status=ACTIVE`,
   `capabilities=["analysis.run"]`, Body `1.0.0`, Runtime `python3.14`,
   Risk `low`, kein `expiresAt`.
2. `module.api.aws_apigatewayv2_route.apiprofiles_binding` —
   `POST /v1/apiprofiles/{apiProfileId}/binding`, `authorization_type=JWT`,
   vorhandener Authorizer `0iqec5`, vorhandene Lambda-Integration.

### Changes (8)

| # | Adresse | Änderung |
| --- | --- | --- |
| 1 | `module.analysis_runtime.aws_iam_role_policy.analysis_runtime_data[0]` | `policy` → nur `dynamodb:GetItem` (PartnerProfiles-Tabelle, WorkItems-Tabelle) |
| 2 | `module.analysis_runtime.aws_lambda_function.analysis[0]` | `environment` + `source_code_hash` + `last_modified` |
| 3 | `module.lambda.aws_lambda_function.agent` | `source_code_hash` + `last_modified` |
| 4 | `module.agent_transport[0].aws_lambda_function.dispatch_ingress` | dito |
| 5 | `module.orders_reader[0].aws_lambda_function.reader` | dito |
| 6 | `module.mays_orders[0].module.lambda.aws_lambda_function.handler` | dito |
| 7 | `module.mays_orders[0].module.sqs_worker.aws_lambda_function.worker` | dito |
| 8 | `module.mays_orders[0].module.agent_transport[0].aws_lambda_function.result_consumer` | dito |

**Analysis-Environment:** sieben neue Keys
`ANALYSIS_SYNTHETIC_{INSTALLATION,TENANT_ID,USER_ID,PARTNER_APPLICATION_ID,ISSUER,ENTITLEMENTS,EXPIRES_AT}`
mit `INSTALLATION=ris-dev2` und sonst leer; `ANALYSIS_SYNTHETIC_MODE=false`.
Keine bestehenden Env-Werte geändert. `ANALYSIS_CONSENT=false`,
`ANALYSIS_NOTICE_APPROVED=false`.

**Code-Hashes (neu):**

| Funktion | nach |
| --- | --- |
| agent / dispatch_ingress | `mcRPFOT8J8p02UQmYHT6iaAaMTJUELg0x2bNEAEmbUo=` |
| analysis | `WDBpUPbeAUyUIFHCX3kHdMPGRVoqgqtmZqk1fOSbBSg=` |
| reader | `YQAE9urjUx5MhyNkOeSRvL8MEC6ikWH+8kfCcTyBrms=` |
| MO handler/worker/consumer | `qnDqqhy24BuXLboFiTVzVZ6KoNlF61aRzjHgeeJSHIk=` |

Bundles auf Platte: agent `99c44f14…`, analysis `58306950…`, reader
`610004f6…`, MO `aa70eaaa…`. Die Agent-/Analysis-Bundles enthalten jetzt den
Profil-Bindungs-Code aus `f06cdfe`; Reader und MO sind unverändert.

## 2. Identität, State, Drift

| Prüfung | Wert |
| --- | --- |
| Branch / HEAD / Remote | erwartet und identisch (`d067811…`) |
| AWS-Konto / Region | `262370457690` / `eu-central-1` |
| Workspace / Backend | `ris-dev2` / S3 `ris-dev2-tf-state-dev`, Key `dev/terraform.tfstate`, Prefix `env:` |
| State | Lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, Serial **69** |
| S3-State | Version `21V4lPFLRfZO7YLrgBcxlVtFOZb5y8dW`, LastModified `2026-11-22T11:52:56Z` (vor dem Plan) |
| Lock | kein aktiver Lock |

`resource_drift` enthält erneut die drei bekannten Refresh-Beobachtungen
(`aws_iam_role.inline_policy` für dispatch_ingress und analysis, `layers`
`null`/`[]`). Beide Rollen sind in `resource_changes` **No-op**; die
beabsichtigte IAM-Änderung betrifft die separate Policy-Ressource. Keine
weiteren Abweichungen.

## 3. Regression

| Lauf | Ergebnis |
| --- | --- |
| MO-Lambda-Suite `db4f9e7` | **240 OK** |
| RIS-Cross-Repo mit `MO_ORDERS_SRC` | **148 passed, 7 subtests**, 0 skipped |
| API-/Profil-/Katalog-/Offer-/Synthetic-Set | **250 passed, 322 subtests** |
| `terraform fmt -check -recursive` / `validate` | PASS |

Die vollständige `tests/`-Sammlung bleibt **BLOCKED_ENV** (fehlendes
`requests`, Ledger-Collection-Fehler) und wird **nicht** als PASS gewertet.
Fremde Produktänderungen wurden dafür nicht vorgenommen.

## 4. Bootstrap-Reihenfolge (verifiziert)

| # | Schritt | Technische Prüfung |
| --- | --- | --- |
| 1 | Cognito-User mit Tenant | Pool `eu-central-1_OYN9QiHc5` hat `custom:tenant_id` (mutable), MFA off, E-Mail auto-verified. `AdminCreateUser` + `AdminSetUserPassword` sind für `devnemo` erlaubt. Der Human-Client `5jgjivk9k9rrjos62so1qhq8o3` erlaubt `ALLOW_USER_PASSWORD_AUTH` → JWT per `initiate-auth` (USER_PASSWORD_AUTH) möglich. |
| 2 | Profil für `sub` | `ris_admin apiprofile create --target-owner <sub>` + `activate`; Admin-Mapping aus `RIS_ADMIN_AUTHORIZATION_FILE` (0600, Principal → role=admin, tenant=<synthetischer Tenant>). |
| 3 | Dedizierter App-Client | `CreateUserPoolClient` erlaubt. Vorhandene Clients: Human (`5jg…`) und M2M (`3mrg…`) — **nicht wiederverwenden**. Ein dedizierter Client ohne Callback/Flows genügt als Registry-Identität; kein Secret nötig. |
| 4 | `partner create` | `applicationId`, `--cognitoClientId`, `--apiProfileId`; Tenant kommt aus der Authorization-Datei. |
| 5 | `apiprofile bind` | Issuer aus `RIS_COGNITO_ISSUER` = `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_OYN9QiHc5`; Partner-Anwendung ACTIVE, gleicher Tenant, gleiches Profil. |
| 6 | Offer + Grant | Katalog enthält nach dem Basis-Apply `analysis-agent`; Offer create + user-wide Grant (`--user-id <sub>`, Fenster). |
| 7 | Kontext + Canary-Plan | `apiprofile show` liefert `partnerApplicationId`/`issuer`; daraus Var-Datei mit **echten** Werten, `mode=true`, Plan erzeugen und gesondert freigeben. |

**Berechtigungen:** Der Operator `devnemo` hat aktuell `AdministratorAccess`
(Read-only geprüft). Für die Provisionierung sind mindestens
`cognito-idp:AdminCreateUser`, `AdminSetUserPassword`,
`AdminUpdateUserAttributes`, `AdminGetUser`, `AdminDeleteUser`,
`CreateUserPoolClient`, `DeleteUserPoolClient` sowie
`dynamodb:GetItem/PutItem/UpdateItem/DeleteItem` auf API-Profiles, Offers,
Entitlements und PartnerApplications nötig. Eine engere Provisioning-Rolle ist
empfohlen; die Simulation bestätigt die Aktionen als `allowed`.

## 5. Rollback-Risiken

| Änderung | Rückweg | Risiko |
| --- | --- | --- |
| Katalog-Item | Reverse-Plan (`destroy`) | Danach keine neuen Offers/Grants für `analysis-agent`; bestehende Entitlements bleiben, Offer-Validierung schlägt bei künftigen Grants fehl. |
| Binding-Route | Reverse-Plan (`destroy`) | Bindungs-Endpunkt entfällt; bestehende gebundene Profile behalten die Felder, neue Bindungen sind nicht möglich. |
| IAM-Policy | Reverse-Plan | Query/Index werden wieder erlaubt (breiter); funktional nicht erforderlich. |
| 7 Lambda-Updates | Reverse-Plan + **alte Bundles** | Die vorherigen Agent-/Analysis-Artefakte (`d767a198…`, `e268b028…`) liegen nicht mehr auf Platte; ein Rollback braucht einen Checkout vor `f06cdfe` + Rebuild, nicht nur Terraform. |
| Env-Keys | Reverse-Plan entfernt sie | Der Code liest fehlende Keys als leer → Synthetic bleibt aus (fail-closed). |

Ein Apply muss exakt den gespeicherten Plan verwenden; jede Drift davor ist ein
Stop. Der Plan ersetzt weder P1 noch P2; beide bleiben unangetastet.

## 6. Entscheidung

**READY FOR BASE APPLY APPROVAL** — für genau
`9b1e5a66384b593885d4f10061f7d55cbbcb91af04aa60e4f3091fc52a1f613c`
(2/8/0/0), Workspace `ris-dev2`, Serial 69.

Nach dem Basis-Apply folgt die separate Provisionierung (Schritte 1–7) und ein
neuer `mode=true`-Plan mit den echten Identitätswerten.

## 7. Nicht ausgeführt

Kein Apply, keine Cognito-/DynamoDB-Mutation, keine Provisionierung, kein
State-Write, kein Main-Merge. Die Zählungen/Reads in §4 sind read-only
(`describe`, `list`, `simulate-principal-policy`).
