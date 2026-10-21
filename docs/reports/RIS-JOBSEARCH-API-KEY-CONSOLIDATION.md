# RIS-JOBSEARCH API-Key / Credential Konsolidation — Mays-Jobs-Matcher / jobsearch

**Zweck:** Zentrale Übersicht aller Reports, Artefakte und Schritte rund um die RIS-API-Key-Erzeugung für die Partneranwendung `mays-jobsearch` / Mays-Jobs-Matcher. Enthält den aktuellen Live-Stand, die Report-Kette und die Wiederholungs-Anleitung zur Key-Erzeugung.

**Stand:** 2026-10-21
**Klassifikation:** GREEN

## 1. Aktueller Live-Stand

- Partner Application: `mays-jobsearch`
  - Cognito Client: `7ldhihlpdgsgcl3puvu4oi7ksv` (human pool `eu-central-1_ojbmoiYGM`)
  - APIProfile: `aprof_6dcfd2a3097b460d` — `ACTIVE`
  - Letztes Credential: `cred_a3bfb5c470ec416f` — `ACTIVE`, `expiresAt` 2027-12-31
  - Secret Pfad: `~/.secrets/mays-jobsearch-ris-api.key` (0600, nie im Repo)
  - Label: `jobsearch-prod`
- Agent Catalog:
  - `reference_agent` ACTIVE
  - `jobsearch-agent` ACTIVE (Terraform Seed, `terraform/modules/dynamodb/main.tf`)
- Offer / Grant
  - Offer `off_fa8a120b80fd4dd2` „Mays-Jobsearch-Partnerpaket“ ACTIVE — Agents `jobsearch-agent`, `reference_agent`
  - Grant `grt_0ac9893f568a4017` USER-Scope, Tenant `mays-ris-dev`, 2026-10-21 → 2027-12-31
  - Entitlements: `ent_962a0e279d0549a6`, `ent_8765562679494f3f`
- L03 Tenant-Resolution live in Lambda `ris-dev-dev-agent` (LastModified 2026-10-21T13:28:20Z)

## 2. Report-Kette

| Report | Thema | Status |
|---|---|---|
| `MAYS-RIS-JOBSEARCH-PARTNER-ONBOARDING-01.md` | Read-only Vorprüfung, STOP wegen fehlender Admin-User | abgeschlossen |
| `RIS-JOBSEARCH-APIPROFILE-CREATE-02.md` | APIProfile + Partner Registry + Credential Erzeugung für mays-jobsearch | GREEN, Credential ausgestellt |
| `RIS-JOBSEARCH-CONSUMER-OFFER-03.md` | Consumer Offer/Grant, Katalog-Seed jobsearch-agent, L03 Tenant | GREEN |
| `RIS-JOBSEARCH-CONSUMER-OFFER-03-EXECUTION_LOG.md` | Checkpoint-Log nach Template | GREEN |
| `RIS-JOBSEARCH-APIPROFILE-CREATE-02.md` | APIProfile-Provisionierung & Credential Lifecycle | GREEN |
| `PARTNER_USER_DUAL_AUTH_IMPLEMENTATION_ROADMAP.md` | Dual-Auth Konzept | Referenz |

Querverweise:
- `docs/api/API-STANDARD.md` — Partner Route `POST /v1/partner/agents/{agentId}/execute`, Header `X-Api-Credential`
- `docs/architecture/PARTNER_USER_DUAL_AUTH_ADR.md` — ADR ACCEPTED, L03 dokumentiert
- `docs/MAYS_RIS_PARTNER_AGENT_INTEGRATION.md` — Integrationsanleitung

## 3. Wie ein RIS-API-Key erzeugt wird

API-Key = Credential-Secret für ein APIProfile. Erzeugung ist **admin-only**, Trust-Anchor gesteuert, keine Flag-Overrides.

### Voraussetzungen
- AWS Profile mit Zugriff auf Account 240571105849
- Trust-Anchor Datei `~/.config/ris/ris-admin-auth.json` existiert, 0600, owned by invoking user
- Eintrag für den eigenen AWS Principal mit `role: admin` und `tenantId: mays-ris-dev`
- `API_PROFILES_TABLE` und `CREDENTIALS_TABLE` Env gesetzt oder DynamoDB Stores verfügbar
- Output-Pfad existiert nicht vorher, Parent-Verzeichnis 0600/0700, kein Symlink

### CLI Pfad
```bash
# 1. APIProfile prüfen / anlegen
ris-admin apiprofile show --apiProfileId aprof_6dcfd2a3097b460d

# 2. Credential ausstellen
export CREDENTIALS_TABLE=ris-dev-dev-credentials
export API_PROFILES_TABLE=ris-dev-dev-api-profiles

ris-admin credential create \
  --apiProfileId aprof_6dcfd2a3097b460d \
  --expiresAt 2027-12-31 \
  --label jobsearch-prod-v2 \
  --output /home/$USER/.secrets/mays-jobsearch-ris-api-v2.key \
  --reason "Rotation für Mays-Jobs-Matcher"
```

Domain-Modul: `agents/ecosystem/credentials.issue_credential`
- Secret wird einmalig zurückgegeben und sofort in die Output-Datei geschrieben, 0600
- Idempotency-Key optional, Duplicate → kein neues Secret
- Bei Schreibfehler → Credential existiert trotzdem, `CredentialOutputFailed` mit `credentialId` für manuelles Revoke

### Manueller API Pfad
`POST /v1/apiprofiles/{apiProfileId}/credentials`
- Auth: Admin JWT mit `custom:tenant_id`
- Body: `expiresAt`, `label`, `reason`
- Response enthält `credentialId`, Secret wird **nicht** zurückgegeben — nur einmalig bei Erzeugung

## 4. Diagnose bei „Key-Erzeugung hängt 8h“

Häufigste Ursachen:
1. **Token ohne `custom:tenant_id`** → L03 deny 403, Request hängt im Client
2. **Trust-Anchor fehlt / falsche Berechtigung** → `AdminAuthorizationError`
3. **Output-Pfad unsicher / existiert schon** → `OutputDestinationError` vor Issuance
4. **APIProfile nicht ACTIVE** → `ValueError apiProfileId does not exist`

Checks:
- JWT decodieren, `custom:tenant_id`, `cognito:groups` prüfen
- `ls -l ~/.config/ris/ris-admin-auth.json` — 0600, owner korrekt
- CloudWatch Logs `/aws/lambda/ris-dev-dev-agent` nach `issue_credential` / Fehler
- API Gateway Execution Logs nach 401/403

## 5. Frontend-Nutzung

- **Nie** `RIS_API_KEY` als `VITE_` Variable. Serverseitig im Vercel-Proxy halten.
- Partner-Request:
  ```
  POST https://ris-dev-dev-api.execute-api.eu-central-1.amazonaws.com/v1/partner/agents/{agentId}/execute
  Authorization: Bearer <Access-Token des Users>
  X-Api-Credential: <Secret aus ~/.secrets/mays-jobsearch-ris-api.key>
  ```
- Login gegen RIS-Pool `eu-central-1_ojbmoiYGM`, Client `7ldhihlpdgsgcl3puvu4oi7ksv`
- Tenant wird serverseitig aus Claim / Registry aufgelöst, kein Default

## 6. Offene Punkte

- Automatisierter Grant bei Self-Signup noch manuell
- `POST /work`-Stub enthält noch `or 'default'` Fallback — nicht deployed, dokumentiert als OPEN
- Rotation-Prozess dokumentiert, aber kein Cron

## 7. Evidenz

- `tools/ris_admin/credentials.py` — Admin-Auth, sichere Secret-Ausgabe
- `tools/ris_admin/cli.py` — Wiring `credential create|revoke|list|show`
- `agents/ecosystem/credentials.py` — Domain `issue_credential`, `revoke_credential`
- `docs/reports/RIS-JOBSEARCH-APIPROFILE-CREATE-02.md`
- `docs/reports/RIS-JOBSEARCH-CONSUMER-OFFER-03.md`

---
*Konsolidiert am 2026-10-21*
