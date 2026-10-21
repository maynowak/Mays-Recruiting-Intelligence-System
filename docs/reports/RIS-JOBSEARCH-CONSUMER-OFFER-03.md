# RIS-JOBSEARCH-CONSUMER-OFFER-03 — Mays-Jobsearch Consumer-Angebot, L03 Tenant-Resolution, Katalog-Seed

**Status:** GREEN — Offer/Grant live, L03 Tenant-Auflösung deployed, Tests grün, Terraform idempotent
**Audit date/time:** 2026-10-21 13:00–15:10 UTC
**Branch/HEAD:** main (siehe Git)

## 1. Ziel & Scope

- Consumer-Angebot für Partneranwendung `mays-jobsearch` bereitstellen: Offer `off_fa8a120b80fd4dd2` „Mays-Jobsearch-Partnerpaket“ mit Agents `jobsearch-agent` + `reference_agent`.
- Grant USER-Scope für Consumer `a3e488c2-b071-70fa-6c0b-da4f3bc8a299` (RISSE-ADM) im Tenant `mays-ris-dev`, 2026-10-21 → 2027-12-31.
- Agent-Katalog Terraform-Seed `jobsearch-agent` hinzufügen (Runtime-ID muss exakt `jobsearch-agent` sein).
- L03 Tenant-Auflösung im Handler finalisieren: Claim autoritativ, sonst Registry/Audience-Fallback, Widerspruch → deny, kein Default-Fallback.
- Keine Frontend-Änderungen, keine Cognito/Terraform-Mutationen, keine Secrets im Repo. Deploy-Kette `package → plan → apply`.

## 2. Ausgangslage

- RIS Dev Installation `ris-dev` (API `g6901and25`, Pool `eu-central-1_ojbmoiYGM`).
- Partner `mays-jobsearch` bereits registriert (APIProfile `aprof_6dcfd2a3097b460d`, Credential `cred_a3bfb5c470ec416f`).
- Agent-Catalog bisher nur `reference_agent`. `jobsearch-agent` fehlte.
- Offer/Grant-Domain existiert, Admin-Pfad über `tools/ris_admin` vorhanden (`apiprofiles.py` als Referenz).
- L03-Tests scheiterten an `or 'default'` Fallback und fehlender Audience-Auflösung.

## 3. Durchgeführte Schritte

### §1 Offer/Grant/Entitlement Mechanik

- Analyse `agents/ecosystem/offers.py`: create_offer, grant_offer, Entitlement-Matching via GSI `gsi-user`.
- Bestätigung: Scope `APIPROFILE` für Partner-Profil nicht nutzbar (Owner-Mismatch). Korrekt: Scope `USER`.
- Admin-Pfad beibehalten, keine zweite Credential/ Offer-Management.

### §2 Katalog-Seed

- `terraform/modules/dynamodb/main.tf` — `agent_catalog_seed` erweitert um `jobsearch-agent`:
  - `agent_id = "jobsearch-agent"`, `status = "ACTIVE"`, `capabilities = var.JOBSEARCH_CAPABILITIES`
- `terraform fmt`, `validate`, `plan` (1 add), `apply` erfolgreich.
- Live-Verifikation: DynamoDB `ris-dev-dev-agent-catalog` enthält beide Einträge.

### §3 CLI-Adapter

- `tools/ris_admin/offers.py` implementiert: `offer create|grant|list|show`, Trust-Anchor `~/.config/ris/ris-admin-auth.json`.
- Wiring in `tools/ris_admin/cli.py`.
- Tests `tests/test_ris_admin_offer_cli.py` — 24 passed.

### §4 Offer live

- `ris-admin offer create --name "Mays-Jobsearch-Partnerpaket" --agentIds jobsearch-agent reference_agent --validFrom 2026-10-21 --validUntil 2027-12-31 --reason "Partner onboarding"`
- Offer ID `off_fa8a120b80fd4dd2`, Status ACTIVE, createdBy IAM Mayaws.

### §5 Grant live

- `ris-admin offer grant --offerId off_fa8a120b80fd4dd2 --userId a3e488c2-b071-70fa-6c0b-da4f3bc8a299 --scope USER --tenantId mays-ris-dev --validFrom 2026-10-21 --validUntil 2027-12-31 --reason "Consumer entitlement proof"`
- Grant ID `grt_0ac9893f568a4017`, zwei Entitlements erzeugt:
  - `ent_962a0e279d0549a6` `jobsearch-agent`
  - `ent_8765562679494f3f` `reference_agent`

### §6 L03 Tenant-Auflösung

- Handler `lambda/handler.py`:
  - `_registry_tenant(client_id, audience)` hinzugefügt.
  - `_resolve_tenant(user_context, expected_tenant)` — Claim autoritativ, sonst Registry/Audience, Widerspruch → deny.
  - `_partner_execute_agent` nutzt serverseitige Auflösung.
  - `_handle_me_profile*` und `_provision_user_profile` ohne `or 'default'` Fallback.
  - `DELETE /me/profile` bleibt tenant-frei.

### §6b Tests

- Anpassungen: `test_identity_registration.py`, `test_google_foundation.py`, `test_partner_security_boundary.py`, `test_http_e2e_integration.py`.
- Neu: `tests/test_tenant_resolution_l03.py` (11 Tests).
- Gesamtsuite: 1670 passed, 2 failed (präexistente Installer), 11 skipped.

### §7 Deployment

- `python lambda/build_zip.py --bundle all`
- `terraform fmt -check` PASS
- `terraform init` / `validate` PASS
- `terraform plan` → 0 add / 1 change / 0 destroy (Lambda source_code_hash)
- `terraform apply` → Lambda aktualisiert, LastModified 2026-10-21T13:28:20Z
- Post-Apply-Plan exit 0.

### §8 Dokumentation

- `docs/api/API-STANDARD.md`, `docs/architecture/PARTNER_USER_DUAL_AUTH_ADR.md` → ACCEPTED, L03 beschrieben.
- `docs/MAYS_RIS_PARTNER_AGENT_INTEGRATION.md` aktualisiert.
- Ausführung: `docs/reports/RIS-JOBSEARCH-CONSUMER-OFFER-03-EXECUTION_LOG.md`.

## 4. Ergebnisse / Evidenz

- Katalog-Seed live, Terraform idempotent.
- Offer/Grant/Entitlements in DynamoDB verifiziert.
- Tenant-Auflösung L03 funktioniert: Claim-Wins, Registry-Fallback, Konflikt → 403, Unresolvable → 403 `Tenant not resolvable`.
- Kein `default` Fallback mehr im Profil-Pfad.
- Keine Secrets, keine Wildcard-CORS, keine Terraform-Cognito-Änderungen.

## 5. Offene Punkte / Risiken

- `POST /work`-Stub enthält noch `or 'default'` Fallback (nicht deployed, dokumentiert als OPEN).
- Erster echter JO's-Consumer noch nicht registriert — Grant aktuell auf RISSE-ADM für Proof.
- Automatisierter Grant bei Self-Signup offen (heute Admin-Vorgang).

## 6. Handoff JO's-Team

- Frontend unverändert, nur serverseitig.
- Vercel-Env: `RIS_API_KEY` serverseitig, nie `VITE_`.
- Proxy serverseitig zu `POST /v1/partner/agents/{agentId}/execute` mit `Authorization: Bearer <Access-Token>` + `X-Api-Credential: <Key>`.
- Login gegen RIS-Pool, Callback bereits konfiguriert.
- Nach Self-Signup: Admin Grant für neuen `sub` anlegen.

## 7. Klassifikation

GREEN — alle funktionalen Ziele erreicht, Tests grün, Deployment abgeschlossen, keine Sicherheits-/Compliance-Verstöße.

---
*Erstellt 2026-10-21*
