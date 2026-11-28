# RIS-DEV2-CANARY-CONTRACT-FIX-03

**Datum:** 2026-11-25
**Branch / Baseline:** `feature/ris-analysis-integration-07` / `c17d1264486c65bd6718467cc623756dde52b453`
**MO-Pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`
**Modus:** Vertragsfix + Tests; **kein AWS-Write, kein Apply, kein State-Write, kein Main-Merge**

## Ergebnis

**READY FOR SYNTHETIC BOOTSTRAP** — die beiden Gate-C-Lücken B2 und B3 sind
geschlossen:

- **B3 (Katalog):** `analysis-agent` ist im Terraform-Katalog-Seed, mit den
  Werten der echten Runtime (v1.0.0, `analysis.run`, Body 1.0.0, python3.14,
  ACTIVE). Offer/Grant gegen den erweiterten Katalog sind getestet; ohne den
  Eintrag bleibt der Agent weiterhin abgelehnt.
- **B2 (Profilbindung):** `partnerApplicationId` und `issuer` sind jetzt
  admin-only am API-Profil bindbar. Der Issuer kommt aus dem verifizierten
  JWT-Claim `iss` (HTTP) bzw. der Operator-Konfiguration (CLI), nie aus dem
  Body. Die Partner-Anwendung wird gegen die autoritative Registry geprüft.
  `resolve_context()` übernimmt beide Werte in den Dispatch-Kontext.

Es bleiben ausschließlich **Provisionierungs**schritte (Cognito-User,
dedizierter App-Client, Profil, Offer/Grant) — keine weiteren Vertragslücken.

## 1. Schritt 1 — Katalog (Commit `dd17574`)

`terraform/modules/dynamodb/main.tf`, `locals.agent_catalog_seed`:

| Feld | Wert |
| --- | --- |
| agentId / name | `analysis-agent` |
| version | `1.0.0` |
| status | `ACTIVE` |
| capabilities | `["analysis.run"]` |
| supported_bodies | `["1.0.0"]` |
| supported_runtimes | `["python3.14"]` |
| risk_level | `low` |

Bestehende Einträge (`reference_agent`, `ats-agent`, `jobsearch-agent`) sind
unverändert. Kein Entitlement-Bypass, keine Test-Sonderfreigabe.

Tests:

- Seed == Runtime-Descriptor (`test_declared_analysis_agent_matches_the_runtime`).
- Seeded catalog → `analysis-agent` ist offerable und grantbar
  (`test_seeded_analysis_agent_can_be_offered_and_granted`).
- Unseeded catalog → weiterhin `GrantDenied`.

## 2. Schritt 2 — Profil-Vertrag (Commit `f06cdfe`)

### Domain

`agents/ecosystem/api_profiles.py::set_identity_binding`:

- **admin-only** (`_is_admin`), `reason` Pflicht, auditiert als
  `profile-identity-binding`.
- Issuer: nicht-leer, `https://`, max. 512 Zeichen.
- Partner-Anwendung: vorhanden, `status=ACTIVE`, gleicher Tenant wie das
  Profil, `apiProfileId` leer oder identisch.
- Setzt beide Felder atomar am Profil; Owner/Staff erhalten
  `UnauthorizedProfileAction`. `update_profile` akzeptiert die Felder weiterhin
  **nicht** (kein Selbstzuweisungsweg).

### HTTP

`POST /v1/apiprofiles/{apiProfileId}/binding` (JWT, admin):

- Body nur `partnerApplicationId`, `reason`; ein `issuer` im Body ⇒ 400.
- Issuer = verifizierter `iss`-Claim; fehlt er ⇒ 400.
- Abweichender `custom:partner_application_id`-Claim ⇒ 400.
- Partner-Anwendung wird per `get_partner_application` (ConsistentRead) aus
  `RIS_PARTNER_APPLICATIONS_TABLE` gelesen; fehlend/inaktiv/fremd ⇒ 403/404.
- Route im Terraform-Modul `api` ergänzt; bestehender JWT-Authorizer, keine
  neue Integration, keine IAM-Änderung.

### CLI

`ris_admin apiprofile bind --apiProfileId … --partner-application-id … --reason …`

- Issuer ausschließlich aus `RIS_COGNITO_ISSUER` (kein Flag).
- Partner-Anwendung über die Registry geprüft.
- Kein Tenant-Flag; Tenant/Owner bleiben aus der Authorization-Datei.

### Weitergabe

`lambda/dispatch_ingress.resolve_context` liest die Felder bereits; ein neuer
Test beweist, dass ein gebundenes Profil `partnerApplicationId` und `issuer`
in das persistierte WorkItem überträgt. Fehlende Bindung ⇒ weiterhin leere
Werte und fail-closed im Synthetic-Verifier.

Rückwärtskompatibilität: bestehende Profile ohne die Felder funktionieren
unverändert; Create/Update/Status-Verträge sind unverändert.

## 3. Schritt 3 — Cross-Repo-Regression (tatsächlich ausgeführt)

| Lauf | Ergebnis |
| --- | --- |
| MO-Lambda-Suite `db4f9e7` | **240 Tests OK** |
| RIS-Cross-Repo mit `MO_ORDERS_SRC` (Handoff, Agent-Order-E2E, WorkQueue, Transport, Dispatch, Reader) | **148 passed, 7 subtests**, 0 skipped |
| API-Profil-/Katalog-/Entitlement-/Offer-Set (11 Dateien) | **289 passed** |
| Offer-Product-Admin (`test_p23`) isoliert | **55 passed, 86 subtests** |
| API-Vertrag (`test_p20`) inkl. neuer Route | **21 passed, 322 subtests** |
| P21/P22/Security/Consent/Transport | **85 passed, 12 subtests** |
| `terraform fmt -check -recursive` | PASS |
| `terraform validate` | PASS (nur vorbestehende `hash_key`-Warnungen) |

**Bekannte Harness-Interferenz:** `test_p23` setzt beim Import
`API_PROFILES_TABLE`; im kombinierten Lauf greift dadurch ein Live-Store und
die Route-Inventur liefert 500 statt 503. Das ist vorbestehend und
reihenfolgeabhängig; isoliert läuft die Datei grün. Die Sets wurden daher in
getrennten Prozessen ausgeführt.

**Nicht gezählt:** die vollständige `tests/`-Sammlung ist
`BLOCKED_ENV` (fehlendes `requests`-Modul, Ledger-Collection-Fehler) und wird
nicht als PASS behauptet.

## 4. Erwarteter Terraform-Plan (nicht erzeugt)

Kein Canary-Plan mit Platzhaltern wurde erstellt. Nach der Provisionierung ist
mit folgendem Diff zu rechnen:

| Aktion | Ressource |
| --- | --- |
| **add** | `aws_dynamodb_table_item.agent_catalog_seed["analysis-agent"]` |
| **add** | `aws_apigatewayv2_route.apiprofiles_binding` |
| change | 7 Lambda-Funktionen (`source_code_hash`, `last_modified`) |
| change | `module.analysis_runtime.aws_iam_role_policy.analysis_runtime_data[0]` (GetItem-only) |

Erwartung: **2 Add / 8 Change / 0 Destroy / 0 Replace**, sofern keine weitere
Provisionierung über Terraform läuft. Der Plan wird erst mit den **echten**
Synthetic-Werten erzeugt und gesondert freigegeben.

## 5. Verbleibende Bootstrap-Anforderungen

1. **Cognito-User** im Pool `eu-central-1_OYN9QiHc5` (Issuer des Orders-Readers)
   anlegen, `custom:tenant_id` setzen, bestätigen.
2. **Dedizierter App-Client** für die Partner-Anwendung (kein Human-Client
   wiederverwenden; die Registry bindet einen Client eindeutig).
3. **Partner-Anwendung** über `ris_admin partner create` mit
   `--cognitoClientId`, `--apiProfileId`, Tenant aus der Authorization-Datei.
4. **API-Profil** mit `--target-owner <sub>` anlegen, aktivieren, dann
   `apiprofile bind` mit der Partner-Anwendung (Issuer aus
   `RIS_COGNITO_ISSUER`).
5. **Offer** `analysis-agent` anlegen und user-wide an `<sub>`/Tenant granten
   (kurzes Fenster).
6. Erfasste Werte (`sub`, `tenant`, `partnerApplicationId`, `issuer`,
   `apiProfileId`) in die Canary-Var-Datei; Plan erzeugen, freigeben, anwenden.
7. Canary-Stufen und Rückweg (`ANALYSIS_SYNTHETIC_MODE=false`) wie in
   `RIS-DEV2-SYNTHETIC-LIVE-CANARY-01` beschrieben.

## 6. Nicht ausgeführt

Kein AWS-Write, kein Cognito-User, kein Terraform-Plan/Apply, kein
State-Write, kein Main-Merge.
