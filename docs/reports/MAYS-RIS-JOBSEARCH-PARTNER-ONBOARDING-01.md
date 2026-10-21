# MAYS-RIS-JOBSEARCH-PARTNER-ONBOARDING-01

**Task:** Jobsearch als Partneranwendung im bestehenden RIS-System registrieren und die sichere Ausstellung eines RIS API-Credentials vorbereiten.

**Projekt:** Mays-Recruiting-Intelligence-System · **Environment:** ris-dev
**Account:** 240571105849 · **Region:** eu-central-1
**Datum:** 2026-10-21
**Status:** `GO` (Vorbereitung) mit **STOP-Bedingung** auf der Admin-Voraussetzung — siehe §2 und §10.
**Modus:** ausschließlich read-only. Keine Terraform-Änderung, kein Profil, kein Credential, kein Grant, kein User, kein Secret.

---

## Zusammenfassung

Die Infrastruktur für die Jobsearch-Partnerregistrierung ist vollständig vorhanden und live. Der
Ende-zu-Ende-Pfad (APIProfile → ACTIVE → Credential → Entitlement → Partner-Execute) ist im Code
implementiert, getestet und als Route deployt. Zwei Dinge fehlen für die eigentliche Ausführung —
beide sind **Datenaufbau**, nicht Infrastruktur:

1. **Es gibt keinen Admin.** Der RIS-Pool `eu-central-1_ojbmoiYGM` enthält **null** Benutzer; die
   Gruppen `admins`/`Staff` existieren, haben aber keine Mitglieder. Die kritischen Schritte
   (`PENDING→ACTIVE`, Offer-Grant, ggf. Credential-Ausgabe) sind **admin-only**. Ohne einen Admin
   kann die Kette nicht durchlaufen werden. → **STOP-Voraussetzung**, kein Blocker im Code.
2. **Die Jobsearch-Seite ist nicht verdrahtet.** Im Jobsearch-Repo existiert **keinerlei**
   RIS-Integration (kein `RIS_API_KEY`, kein `X-Api-Credential`, keine serverseitige Proxy-Funktion).
   Das ist laut Aufgabenstellung ausdrücklich „ohne separaten Auftrag nicht ändern".

Ergebnis: **GO** für die Jobsearch-Partnerregistrierung als Vorbereitung; die Ausführung ist durch
das Admin-Gate (§2) und die fehlende Vercel-Verdrahtung (§8) aufgeschoben.

---

## 1. Preflight (verifiziert)

| Prüfpunkt | Befund | Status |
|---|---|---|
| Git HEAD | `3102ad90d749f29fe2192adbb46f986ded355621` | ✅ |
| origin/main | identisch mit HEAD · Branch `main` | ✅ |
| Working Tree | clean (nichts ungetrackt/geändert) | ✅ |
| AWS Identität | `arn:aws:iam::240571105849:user/Mayaws` | ✅ |
| Region | eu-central-1 | ✅ |
| RIS-Installation | Workspace `ris-dev`, RIS-Pool `ris-dev-dev-users` (`eu-central-1_ojbmoiYGM`) | ✅ |
| Kernel API | `ris-dev-dev-api` (`g6901and25`) | ✅ |
| APIProfile-Routen | live, JWT (`3hy7kc`) — s. §4 | ✅ |
| Credential-Lifecycle | implementiert + getestet — s. §5 | ✅ |
| Offer-/Entitlement-System | implementiert + Route live — s. §6 | ✅ |
| Partner-Agentenroute | `POST /v1/partner/agents/{agentId}/execute`, JWT `3hy7kc` — s. §7 | ✅ |

Keine Terraform-Änderung vorgenommen.

---

## 2. Admin-Berechtigungen — **STOP**

### Befunde (read-only)

| Frage | Antwort | Evidenz |
|---|---|---|
| Existiert die Cognito-Gruppe `admins`? | **Ja** | `list-groups` |
| Gibt es einen Benutzer in `admins`? | **Nein** | `list-users-in-group admins` → leer |
| Gibt es überhaupt Benutzer im Pool? | **Nein, 0 Benutzer** | `list-users` → `length(Users) == 0` |
| Gruppen im Pool | `admins`, `Staff`, `Admin`, `recruiters`, `candidates`, `user-requier`, `user-user` | `list-groups` |
| Benutzer in `Staff`? | **Nein** | `list-users-in-group Staff` → leer |

Es wurden **keine** Benutzer erstellt und **keine** Gruppenmitgliedschaften verändert.

### Gruppen → RIS-Rollen-Mapping

Actor-Rolle wird in `lambda/handler.py::_cred_actor` aus den Cognito-Gruppen abgeleitet:

```
groups enthält "admins"  → role = "admin"
sonst "Staff"            → role = "staff"
sonst                    → role = "owner"
```

Konstanten: `agents/ecosystem/api_profiles.py:38-39` → `ADMIN_GROUP = "admins"`, `STAFF_GROUP = "Staff"`.

### Tenant-Bestimmung (serverseitig)

`lambda/handler.py:311-313`: `tenantId` stammt ausschließlich aus dem JWT-Claim `custom:tenant_id`.
Kein Request-Body/Header kann den Tenant wählen.

### Rollenmatrix (aus dem Code, nicht aus Prosa)

| Aktion | Admin (`admins`) | Staff (`Staff`) | Owner (self, ID-gebunden) |
|---|---|---|---|
| Profil erstellen (`create_profile`) | ✅ (auch für andere) | ❌ `staff may not create profiles` | ✅ nur eigenes |
| `PENDING→ACTIVE` (`transition_status`) | ✅ admin-only | ❌ | ❌ |
| `ACTIVE↔DISABLED` | ✅ | ✅ mit `reason` | ✅ eigenes |
| `REVOKED` | ✅ | ❌ | ❌ |
| Credential ausgeben (`issue_credential`) | ✅ | ❌ | ✅ eigenes, usable |
| Credential rotieren | ✅ | ✅ mit `reason` | ✅ eigenes |
| Credential disable/enable/revoke | ✅ | ✅ Support | ✅ eigenes |
| Offer erstellen (`create_offer`) | ✅ admin-only | ❌ | ❌ |
| Offer granten (`grant_offer`) | ✅ admin-only | ❌ | ❌ |

`_owner_self` (`credentials.py:152-163`) ist **ID-gebunden** (`actor_id == ownerUserId`), nicht nur
Rollenstring — ein gefälschtes „owner" im Token genügt nicht.

### STOP-Voraussetzung

> **Es existiert kein Admin-Benutzer.** Damit können `PENDING→ACTIVE`, Offer-Erstellung,
> Offer-Grant und (falls admin- statt owner-ausgestellt) die Credential-Ausgabe **nicht** ausgeführt
> werden. Der erste konkrete Schritt vor der Registrierung ist daher:
>
> 1. Einen RIS-Benutzer anlegen (nur nach separater Freigabe; hier NICHT getan),
> 2. diesen der Gruppe `admins` zuordnen (nur nach separater Freigabe),
> 3. dessen `custom:tenant_id` auf den Ziel-Tenant setzen (Annahme: `default`, siehe §3).

Ohne diese drei Schritte bleibt die Partnerregistrierung bei `PENDING` stehen.

---

## 3. Partnerregistrierung (Vorprüfung, read-only)

**Partner:** Mays-Jobsearch · **Website:** https://mays-job-matcher.app ·
**Frontend:** https://mays-job-matcher.vercel.app

| Frage | Befund |
|---|---|
| Existiert ein Jobsearch-APIProfile? | **Nein** — `ris-dev-dev-api-profiles` = 0 Items |
| Existiert ein passendes Credential? | **Nein** — `ris-dev-dev-credentials` = 0 Items |
| Existiert eine Partnerregistrierung? | **Nein** — `ris-dev-dev-partner-applications` = 0 Items |
| Welche `applicationId` / `clientRef`? | Noch nicht vergeben. `clientRef` ist **admin-only Metadata** (nicht sicherheitsrelevant, `api_profiles.py:407-414`). |
| Welchem Tenant gehört die Anwendung? | Noch nicht zugewiesen. Tenant kommt aus `custom:tenant_id` des Owner-Users. Der Pool hat keinen Default — Annahme `default` ist nicht bestätigt. |

**Fazit:** Es existiert **keine** Doppelung. Es ist noch nichts vorhanden — die Registrierung startet
bei null. **Wichtig:** Es existiert bereits ein Registrierungs-Mechanismus
(`agents/ecosystem/partner_registry.py` + Tabelle `ris-dev-dev-partner-applications`, PK
`applicationId`, GSI `gsi-client`), der genutzt werden muss — keine neue Architektur.

Die autoritative Kette (ADR `M2M_CLIENT_APIPROFILE_BINDING_ADR.md`) ist:

```
Cognito Client (client_id) → Partner Registry (applicationId, clientId, apiProfileId, tenantId, status)
   → APIProfile (ownerUserId, tenantId, status)
      → Credentials (credentialId → apiProfileId)
         → Entitlements (userId/tenantId → agentId)
            → Agent Catalog
```

---

## 4. APIProfile-Lifecycle (vorhandene API)

- **Erstellen:** `POST /v1/apiprofiles` → `agents/ecosystem/api_profiles.py::create_profile` (Z. 255).
  Startet **immer PENDING**, nie ACTIVE, nie beim Login. `tenantId` serverseitig aus dem Token.
  `clientRef`/`expiresAt` sind admin-only; vom Owner mitgeschickte Werte werden **ignoriert**.
- **Aktivieren:** `POST /v1/apiprofiles/{apiProfileId}/status` → `transition_status` (Z. 474):
  `PENDING→ACTIVE` ist **admin-only**; `EXPIRED` ist abgeleitet, nie Ziel.
- **Nutzbarkeit:** `effective_status == "ACTIVE"` (`_profile_usable`).
- **Statusübergänge** (`api_profiles.py:52-55`): PENDING→{ACTIVE,DISABLED,EXPIRED}; ACTIVE→{DISABLED,REVOKED};
  DISABLED→{ACTIVE,REVOKED}; REVOKED terminal.
- **Eindeutigkeit:** Name eindeutig pro Owner; `applicationId`/`cognitoClientId` atomar eindeutig per
  DynamoDB-Transaktion (`partner_registry.py:12-40`).
- **Tenant-Isolation:** `_check_tenant` auf jeder Aktion; Cross-Tenant nur mit explizitem `reason`.
- **Owner-Zuordnung:** `ownerUserId = actor` (außer Admin mit explizitem `targetOwner`).

---

## 5. Credential-Ausstellung (Voraussetzungen — NICHT ausgeführt)

**Route:** `POST /v1/apiprofiles/{apiProfileId}/credentials` → `lambda/handler.py:1612` →
`creds.issue_credential` (`credentials.py:239`).

Voraussetzungen laut Code:

- Profil muss **ACTIVE-usable** sein (PENDING/DISABLED/EXPIRED/REVOKED → keine Ausgabe).
- `expiresAt` ist **Pflicht** (kein erfundener Default).
- Credential darf das Profil **nicht überleben** (MIN-Regel).
- **Admin** jederzeit; **Owner** nur fürs **eigene** Profil; **Staff nie** (Ausgabe).
- Secret wird **genau einmal** ausgegeben (once-only); mit `Idempotency-Key` identischer Aufruf →
  bestehende Zeile `duplicate: true`, Original-Secret wird **nie** erneut geliefert.

Beispiel-Metadaten (für den späteren freigegebenen Aufruf): `label: jobsearch-prod`,
`reason: partner integration`.

> **Kein Secret ausgegeben oder gespeichert.** Dieser Report, `AI_AUDITLOG.md` und alle
> Terminal-Transkripte enthalten **keine** Secrets.

---

## 6. Entitlements (Bestandsaufnahme)

- **Angebotssystem:** `agents/ecosystem/offers.py` — `create_offer` (admin-only, Z. 364) +
  `grant_offer` (admin-only, Z. 486). Grant erzeugt **eine Entitlement-Zeile pro Offer-Agent**.
- **Scope:** `USER` (kein `apiProfileId`) **XOR** `APIPROFILE` (Profil muss existieren, dem Ziel-User
  gehören, zum Tenant passen und ACTIVE-usable sein).
- **Live-Bestand:** Offers = **0**, Entitlements = **0**, Partner Applications = **0**.
- **Agent-Catalog live:** ausschließlich `reference_agent` (ACTIVE). Weitere Agenten sind **nicht**
  deployt; `dummy-a/b` sind DEV-only und nicht als Produktions-Agenten zu behandeln.

**Für Jobsearch benötigte Grants (Vorschlag, NICHT vergeben):** minimaler Scope — zunächst nur der
Agent, den Jobsearch tatsächlich braucht (aktuell faktisch nur `reference_agent` verfügbar). Keine
pauschale Freigabe aller Agenten. Grant ist admin-only; Vergabe **erst nach separater Freigabe**.

---

## 7. Dual-Auth-Vertrag

**Route:** `POST /v1/partner/agents/{agentId}/execute` — live, Authorizer `3hy7kc`
(`ris-dev-dev-jwt-human`). Erwartete Header:

```
Authorization: Bearer <COGNITO_ACCESS_JWT>
X-Api-Credential: <RIS_API_KEY>
```

Validierung im Handler (`lambda/handler.py::_partner_execute_agent`, Z. 1009-1165):

1. `token_use == "access"` (ID-Token wird abgelehnt) — Z. 1031.
2. Credential wird mit dem **zentralen** Verifier `resolve_credential_profile` geprüft — Z. 1055.
3. **Partner-Registry-Bindung** (Z. 1070-1087): JWT `client_id` → Registry-Lookup (Basis-Tabelle,
   strongly consistent) → Registry muss `ACTIVE` sein; `registry.apiProfileId` **muss** gleich
   `credential.apiProfileId` sein; `registry.tenantId` **muss** gleich `credential.tenantId` sein.
4. **Tenant-Isolation** (Z. 1089-1093): JWT-Tenant **muss** Credential-Tenant entsprechen.
5. **Entitlement** (Z. 1095-1114): geprüft wird der **JWT-User**, nicht der Credential-Owner.
6. **Agent-Catalog** (Z. 1116-1125): Agent muss executable Status haben.

Keine neuen Auth-Mechanismen — bestehende wiederverwendet.

### L01 / L03 (Architekturkonzept)

Im Repo existieren **keine** Zeichenketten `L01`/`L03`. Die Layer-Definitionen stehen in
`docs/ARCHITECTURE.md:195-224`:

- **Layer 1 — Authentication Boundary** (L01): Cognito user/tenant auth, JWT identity propagation,
  IAM. → Abgedeckt durch §7 Punkte 1-2 + Tenant-Claim (§2).
- **Layer 3 — Work System** (L03): SQS, Lambda Worker, DynamoDB Work Items. → Der Partner-Execute
  enqueued authorisiert ein WorkItem (`_enqueue_agent_work`, Z. 1146-1156), ohne selbst auszuführen.

> **Offene Klärung:** Die Bezeichnungen „L01/L03" sind im Repo nicht auffindbar. Sollte ein
> separates Sicherheits-/Architekturkonzept existieren, ist dessen Fundstelle nachzuliefern, damit
> die Prüfung gegen die exakt gemeinten Punkte erfolgt. Die hier getroffene Zuordnung folgt
> `docs/ARCHITECTURE.md`.

---

## 8. Vercel-Integration — fehlende Verdrahtung

**Vorgesehen:** `RIS_API_KEY=<ONCE_ONLY_SECRET>`, **ausschließlich serverseitig** über
`process.env.RIS_API_KEY` in einer Vercel Function. **Nicht** `VITE_RIS_API_KEY` (Browser-Bundle).

**Befund (read-only, Jobsearch-Repo `installer/projects/mays_jobsearch/`):**

- Es existiert **kein** `RIS_API_KEY`, **kein** `X-Api-Credential`, **keine** RIS-Client-Referenz
  in `src/` oder `api/`.
- `.env.example` enthält **keinen** RIS-Abschnitt (nur OpenRouter/EdenAI/Apify).
- `api/` besteht aus Vercel-Serverless-Funktionen (`.mjs`), u. a. `api/_lib/identity.mjs` — es gibt
  also ein **serverseitiges** Muster, aber **keine** RIS-Proxy-Funktion.

**Ergebnis:** Keine geeignete serverseitige Integrationsfunktion vorhanden. Die Verdrahtung ist
**vollständig offen** und wird hier **nicht** geändert (kein Auftrag). Für die spätere Umsetzung:
Vercel-Serverless-Route, die eine Human-JWT (Access) des Endnutzers weiterleitet und serverseitig
`X-Api-Credential` ergänzt (Muster analog `PARTNER_USER_DUAL_AUTH_ADR.md`).

---

## 9. Tests

Ausgeführt (read-only):

```
python3 -m pytest tests/test_partner_security_boundary.py \
                 tests/test_credential_verification.py \
                 tests/test_introspection_capability.py \
                 tests/test_entitlement_provisioning.py -q
→ 166 passed, 1 failed
```

Die eine Fehlschlag (`test_secret_opaque_random`) ist **flaky**, kein Regressionsfehler: der Zufalls-
Secret wurde zufällig mit der Teilkette `u1` erzeugt, die der Test über `assertNotIn("u1", ...)`
ausschließt. Isoliert 5× hintereinander → **5× passed**. Vollständige
`test_partner_security_boundary.py` (T01-T14, Dual-Auth) → **47 passed**, 3× stabil.

Abgedeckte Prüfbereiche: Profil-Lifecycle (`test_entitlement_provisioning`), Credential-Lifecycle
(`test_credential_verification`, `test_introspection_capability`), Admin/Owner/Staff-Rollen,
Tenant-Isolation, Duplicate Prevention, Credential Expiration, Partner Dual Auth (T01-T14, inkl.
Cross-Client-Reuse, Tenant-Mismatch, revoked Credential, inaktives Profil, Registry-Mismatches,
`RIS_TEST_MODE`-Bypass entfernt).

**Klassifikation:** `GREEN` (mit dokumentiertem flaky Baseline-Test).

---

## 10. Freigabegate / Ergebnis

### Erlaubt (ausgeführt)

- Read-only AWS-Prüfungen ✅
- Read-only RIS-Prüfungen ✅
- Code- und Contract-Audit ✅
- Tests ✅
- Dokumentation ✅
- Git-Commit/Push der Dokumentation ✅ (dieser Report + `AI_AUDITLOG.md`)

### Nicht ausgeführt (wie verlangt)

- Kein APIProfile erstellt/aktiviert
- Kein Credential ausgestellt
- Keine Entitlements vergeben
- Keine Benutzer/Gruppen verändert
- Kein Terraform Apply · keine DNS-Änderung
- Keine Secrets ausgegeben/gespeichert

### Ergebnis: **GO** (Vorbereitung) mit zwei aufgeschobenen Voraussetzungen

| Gate | Zustand |
|---|---|
| Infrastruktur vollständig | ✅ |
| Code/Contract vorhanden | ✅ |
| Tests grün | ✅ |
| **Admin-Benutzer vorhanden** | ❌ **STOP** — Pool hat 0 Benutzer |
| **Jobsearch verdrahtet** | ❌ offen — keine RIS-Integration vorhanden |

**GO**, sobald die beiden Voraussetzungen geschaffen sind (jeweils nur nach separater Freigabe).

---

## 11. Konkrete nächste API-Aufrufe (nach Freigabe)

Reihenfolge mit exakten Aufrufen und benötigten Berechtigungen. `$API` = Kernel-Endpoint,
`$JWT_ADMIN` = Access-Token eines `admins`-Users, `$JWT_OWNER` = Access-Token des Profil-Owners.

**Schritt 0 — Voraussetzungen schaffen (separate Freigabe nötig)**
Admin-User anlegen + Gruppe `admins` + `custom:tenant_id` setzen. (Hier NICHT ausgeführt.)

**Schritt 1 — APIProfile erstellen** *(owner-self oder admin)*
```http
POST $API/v1/apiprofiles
Authorization: Bearer $JWT_OWNER
Content-Type: application/json

{ "name": "mays-jobsearch",
  "description": "Mays-Jobsearch Partner Application" }
```
→ `201`, Status **PENDING**. Antwort enthält `apiProfileId` (`$PID`).

**Schritt 2 — APIProfile aktivieren** *(admin-only)*
```http
POST $API/v1/apiprofiles/$PID/status
Authorization: Bearer $JWT_ADMIN
Content-Type: application/json

{ "status": "ACTIVE", "reason": "jobsearch partner onboarding" }
```

**Schritt 3 — Credential ausstellen** *(admin oder owner-self; NUR nach separater Freigabe,
once-only Secret)*
```http
POST $API/v1/apiprofiles/$PID/credentials
Authorization: Bearer $JWT_ADMIN
Content-Type: application/json
Idempotency-Key: jobsearch-prod-<date>

{ "expiresAt": "<YYYY-MM-DDTHH:MM:SSZ>",
  "label": "jobsearch-prod",
  "reason": "partner integration" }
```
→ `201`, `secret` **genau einmal**. `expiresAt` ≤ Profil-`expiresAt`. Danach Secret **ausschließlich**
als Vercel-Server-Secret `RIS_API_KEY` setzen — nie in Git/Logs/Chat.

**Schritt 3b — Partnerregistrierung binden** *(admin; bestehende Registry, kein Neubau)*
Cognito-M2M-Client für Jobsearch + Registry-Record (`applicationId`, `cognitoClientId`,
`apiProfileId`, `tenantId`, `status=ACTIVE`) — via `tools/ris_admin/cli.py partner create ...`
bzw. `partner_registry.create_partner_application(...)`. Für den **Partner-User-Execute-Pfad** (§7)
ist der gebundene Cognito-`client_id` der **Human**-Login-Client des Endnutzers bzw. der Partner-Client
je nach Fluss — vor Ausführung anhand des gewählten Flows festlegen.

**Schritt 4 — Offer erstellen** *(admin-only)*
```http
POST $API/v1/offers
Authorization: Bearer $JWT_ADMIN
Content-Type: application/json

{ "name": "mays-jobsearch-offer",
  "description": "Agents for Mays-Jobsearch",
  "agentIds": ["reference_agent"] }
```
→ `offerId` (`$OFFER`). Minimaler Agenten-Scope, keine Pauschalfreigabe.

**Schritt 5 — Offer granten** *(admin-only)*
```http
POST $API/v1/offers/$OFFER/grant
Authorization: Bearer $JWT_ADMIN
Content-Type: application/json

{ "targetUserId": "<userId>",
  "tenantId": "<tenant>",
  "scope": "APIPROFILE",
  "apiProfileId": "$PID",
  "reason": "jobsearch partner grant" }
```
→ eine Entitlement-Zeile pro Offer-Agent.

**Schritt 6 — Partner-Execute (Jobsearch → RIS)** *(JWT + Credential)*
```http
POST $API/v1/partner/agents/reference_agent/execute
Authorization: Bearer $JWT_ENDUSER
X-Api-Credential: $RIS_API_KEY
Content-Type: application/json

{ "capability": "reference.echo", "payload": {}, "idempotencyKey": "..." }
```
→ `202` mit `workId` (autorisiert, kein direkter Execute).

---

## Offene Sicherheitsprüfungen

1. **Tenant-Ziel unbestätigt** — welcher `custom:tenant_id` soll Jobsearch zugeordnet sein? Der Pool
   hat keinen Default.
2. **Cognito-Client-Bindung** — welcher `client_id` (Human vs. M2M) wird der Partnerregistrierung
   zugeordnet, je nach gewähltem Jobsearch-Fluss?
3. **„L01/L03"** — Fundstelle des gemeinten Architekturkonzepts klären (§7).
4. **Vercel-Verdrahtung** — serverseitige Proxy-Funktion fehlt; `RIS_API_KEY` darf nie ins
   Browser-Bundle (`VITE_*`).
5. **Entitlement-Minimalprinzip** — nur benötigte Agenten granten (aktuell nur `reference_agent`
   verfügbar).
6. **Credential-TTL** — `expiresAt` des Credentials muss ≤ Profil-`expiresAt` sein.

---

## Evidenz-Referenzen

- Code: `lambda/handler.py` (Z. 300-324 Tenant, 1009-1165 Partner-Execute, 1612 Credential),
  `agents/ecosystem/api_profiles.py` (Z. 38-55, 104-134, 255-330, 444-509),
  `agents/ecosystem/credentials.py` (Z. 152-163, 239+), `agents/ecosystem/offers.py` (Z. 364-400, 486-545),
  `agents/ecosystem/partner_registry.py` (Z. 12-40, 99-178), `tools/ris_admin/cli.py` (Z. 120-230).
- ADRs: `docs/architecture/M2M_CLIENT_APIPROFILE_BINDING_ADR.md`,
  `docs/architecture/PARTNER_USER_DUAL_AUTH_ADR.md`, `docs/architecture/RIS_AUTH_CONTRACT.md`.
- Layer: `docs/ARCHITECTURE.md:195-224`.
- Tests: `tests/test_partner_security_boundary.py` (T01-T14), `tests/test_credential_verification.py`,
  `tests/test_entitlement_provisioning.py`, `tests/test_introspection_capability.py`.
- AWS (read-only): Cognito `list-users`/`list-groups`/`list-users-in-group`, DynamoDB `scan`/`describe-table`
  (`api-profiles`=0, `credentials`=0, `entitlements`=0, `offers`=0, `partner-applications`=0,
  `agent-catalog`=`reference_agent`), API GW `get-routes`/`get-authorizers`.
