# RIS-JOBSEARCH-APIPROFILE-CREATE-02 — Mays-Jobsearch Partner-Provisionierung

**Status:** GREEN
**Datum:** 2026-10-21
**Umgebung:** `ris-dev` (Workspace `ris-dev`, Account `240571105849`, Region `eu-central-1`)
**Tenant:** `mays-ris-dev`
**Anwendung:** Mays-Jobsearch — https://www.mays-job-matcher.app

---

## 1. Ergebnis in Kürze

Der komplette Partner-Bootstrap ist durchgelaufen. Es existiert jetzt:

| Objekt | ID | Status |
|---|---|---|
| APIProfile | `aprof_6dcfd2a3097b460d` | `ACTIVE` |
| Partner Application | `mays-jobsearch` | `ACTIVE` |
| API Credential | `cred_a3bfb5c470ec416f` | `ACTIVE`, exp. `2027-12-31T23:59:59Z` |

Das Secret liegt ausschließlich in `~/.secrets/mays-jobsearch-ris-api.key` (`0600`, owner `dci-student`).
Es wurde **nie** ausgegeben, geloggt, committet oder in einen Report geschrieben.

---

## 2. Ursachenanalyse des vorherigen `403 Forbidden` / `401 Unauthorized`

Zwei verschiedene Fehlerbilder, zwei verschiedene Ursachen:

### 2.1 `{"error": "Forbidden"}` (Lambda, HTTP 403)

Quelle: `lambda/handler.py::_handle_apiprofile_routes` (Zeile 2307-2310)

```python
if not user_context.get("tenantId"):
    return {"statusCode": 403, "body": json.dumps({"error": "Forbidden"})}
```

`_extract_user_context()` liest den Tenant **ausschließlich** aus dem JWT-Claim
`custom:tenant_id` (Handler-Zeile 311). Der Claim war im IdToken **nicht** vorhanden.

**Root Cause (live verifiziert):** Der Human-Client `7ldhihlpdgsgcl3puvu4oi7ksv`
hat `ReadAttributes = null`. Bei Cognito bedeutet das: der App-Client darf alle
**Standard**-Attribute lesen, aber **keine Custom**-Attribute. `custom:tenant_id`
ist im User zwar gepflegt (`admin-get-user` zeigt `mays-ris-dev`), wird aber
deshalb nicht in das IdToken gemappt.

Live-Beleg:

```
ReadAttributes = null
Schema: custom:tenant_id (Mutable=True, im User gesetzt)
```

Der Admin-Status war zu keinem Zeitpunkt das Problem (`RISSE-ADM` war `CONFIRMED`,
in `admins`, `custom:tenant_id=mays-ris-dev`).

### 2.2 `{"message": "Unauthorized"}` (API Gateway, HTTP 401)

Das ist das Format von **API Gateway**, nicht des Lambdas. Der JWT-Authorizer
hat den Token abgelehnt: `aud` passte nicht oder die Variable war leer.
Live-Konfiguration:

| Authorizer | Audience | Issuer |
|---|---|---|
| `ris-dev-dev-jwt-human` (`3hy7kc`) | `7ldhihlpdgsgcl3puvu4oi7ksv` | `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ojbmoiYGM` |
| `ris-dev-dev-jwt-m2m` (`p14vbj`) | `82ji073smu1b3fsvj96sonso` | dito |

Nur der **IdToken** (`aud` = Client-ID) wird vom Human-Authorizer akzeptiert;
der AccessToken (`aud` = Pool-ID) nicht.

---

## 3. Gewählter Lösungsweg (ohne Terraform, ohne Cognito-Mutation)

Der HTTP-Weg über den IdToken ist blockiert, solange der App-Client das
Custom-Attribut nicht lesen darf — und die Cognito-Clients durften laut
Vorgabe nicht verändert werden.

Umgesetzt wurde deshalb der in `RIS-JOBSEARCH-KEY-BOOTSTRAP-01` ausdrücklich
freigegebene Weg: *"If CLI commands are missing, implement the minimal CLI
integration using the existing authorization and lifecycle mechanisms."*

### 3.1 Neue Datei `tools/ris_admin/apiprofiles.py`

Dünne Verdrahtung über die **bestehende** Domain (`agents/ecosystem/api_profiles.py`):

* `create_profile` (Startzustand immer `PENDING`)
* `transition_status` (`PENDING -> ACTIVE`, admin-only in der Domain)
* `get_profile`, `list_profiles`

Es gibt **keine** zweite Credential-/Profil-Lifecycle. Die Rollen-Autorisierung
kommt aus demselben Trust-Anchor wie bei `credential issue`
(`resolve_admin_authorization` → STS `GetCallerIdentity`).

Mapping Authorization-Contract → Domain-Actor:

```
actor_role   admin|staff|owner  ->  Cognito-Gruppe (admins|Staff)
actor_id     <Principal-ARN>     ->  Domain actor userId (owner)
actor_tenant <tenantId>         ->  Domain actor tenantId
```

**Es gibt bewusst kein `--tenantId`-Flag:** Der Tenant kommt immer aus dem
Authorization-File. Damit kann die CLI kein Profil in einen fremden Tenant
schreiben — Tenant-Isolation bleibt intakt.

### 3.2 CLI-Erweiterung `tools/ris_admin/cli.py`

```
ris-admin apiprofile create   --name [--description] [--target-owner] [--idempotency-key]
ris-admin apiprofile activate --apiProfileId [--reason]
ris-admin apiprofile show     --apiProfileId [--reason]
ris-admin apiprofile list     [--reason]
```

`--dry-run` verändert nichts. Fehlende/ungültige Authorization ⇒ Fail-Closed.

### 3.3 Trust-Anchor (Operator-Autorisierung)

`~/.config/ris/ris-admin-auth.json` (`0600`, owner `dci-student`):

```json
{
  "principals": {
    "arn:aws:iam::240571105849:user/Mayaws": {
      "role": "admin",
      "tenantId": "mays-ris-dev"
    }
  }
}
```

Das ist der dokumentierte lokale Trust-Anchor des RIS-Admin-CLIs. Er bindet
**nur den eigenen IAM-Principal** (den, mit dem ohnehin gearbeitet wird) und
wird fail-closed geprüft (Datei vorhanden, nicht group/other-writable, owned by
invoking user, Rolle und tenantId vorhanden).

### 3.4 Ausführungs-Skript

`/tmp/opencode/ris_jobsearch_bootstrap.sh` (lokal, nicht im Repo):
Anchor anlegen → APIProfile → aktivieren → Partner → Credential → Verification.
Alle Schritte sind **idempotent** (kein Duplicate, wenn etwas schon existiert).

---

## 4. Ausgeführte Befehle (vollständig)

```bash
cd /home/dci-student/projects/Mays-Recruiting-Intelligent-System
export AWS_PROFILE=mayaws AWS_REGION=eu-central-1
export RIS_PROJECT_NAME=ris-dev
export API_PROFILES_TABLE=ris-dev-dev-api-profiles
export CREDENTIALS_TABLE=ris-dev-dev-credentials
export RIS_ADMIN_AUTHORIZATION_FILE=$HOME/.config/ris/ris-admin-auth.json
export PYTHONPATH=tools:.

RIS="python3 tools/ris_admin/cli.py --profile mayaws --region eu-central-1 --environment dev"

# 1) APIProfile (PENDING)
$RIS apiprofile create --name "Mays-Jobs-Matcher" \
  --description "Mays-Jobsearch partner site https://www.mays-job-matcher.app" \
  --authorization-file $RIS_ADMIN_AUTHORIZATION_FILE

# 2) Aktivieren (admin-only, Domain-Enforcement)
$RIS apiprofile activate --apiProfileId aprof_6dcfd2a3097b460d \
  --reason "partner integration: Mays-Jobsearch onboarding" \
  --authorization-file $RIS_ADMIN_AUTHORIZATION_FILE

# 3) Partner Registry
$RIS partner create mays-jobsearch \
  --cognitoClientId 7ldhihlpdgsgcl3puvu4oi7ksv \
  --apiProfileId aprof_6dcfd2a3097b460d \
  --tenantId mays-ris-dev

# 4) Credential (Secret nur in die Datei, nie auf stdout)
mkdir -p ~/.secrets && chmod 700 ~/.secrets
$RIS credential issue --apiProfileId aprof_6dcfd2a3097b460d \
  --expiresAt 2027-12-31T23:59:59Z \
  --label jobsearch-prod \
  --reason "partner integration" \
  --output-file ~/.secrets/mays-jobsearch-ris-api.key \
  --authorization-file $RIS_ADMIN_AUTHORIZATION_FILE
```

---

## 5. Verifikation (live)

### 5.1 APIProfile

```json
{
  "apiProfileId": "aprof_6dcfd2a3097b460d",
  "name": "Mays-Jobs-Matcher",
  "tenantId": "mays-ris-dev",
  "status": "ACTIVE",
  "ownerUserId": "arn:aws:iam::240571105849:user/Mayaws",
  "createdBy": { "actor": "arn:aws:iam::240571105849:user/Mayaws", "role": "admin" }
}
```

### 5.2 Partner Registry (`ris-admin partner validate`)

```json
{
  "valid": true,
  "problems": [],
  "record": {
    "applicationId": "mays-jobsearch",
    "apiProfileId": "aprof_6dcfd2a3097b460d",
    "status": "ACTIVE",
    "cognitoClientId": "7ldhihlpdgsgcl3puvu4oi7ksv",
    "tenantId": "mays-ris-dev"
  }
}
```

### 5.3 Credential-Metadaten (ohne Secret)

```json
{
  "credentialId": "cred_a3bfb5c470ec416f",
  "apiProfileId": "aprof_6dcfd2a3097b460d",
  "tenantId": "mays-ris-dev",
  "status": "ACTIVE",
  "label": "jobsearch-prod",
  "expiresAt": "2027-12-31T23:59:59Z",
  "credentialType": "opaque-bearer-v1"
}
```

### 5.4 Secret-Ablage

| Prüfung | Ergebnis |
|---|---|
| Pfad | `~/.secrets/mays-jobsearch-ris-api.key` |
| Rechte | `0600` (owner `dci-student`) |
| Format | Präfix `ris_`, 47 Zeichen, kein Trailing-Whitespace |
| Im Repo? | nein |
| In Logs/Reports? | nein |
| In der Konsole ausgegeben? | nein |

### 5.5 Duplikat-/Fremd-Tenant-Check

| Tabelle | Items | Bewertung |
|---|---|---|
| `ris-dev-dev-api-profiles` | 1 | 1 Profil, Tenant `mays-ris-dev`, Status `ACTIVE` |
| `ris-dev-dev-credentials` | 1 | 1 Credential |
| `ris-dev-dev-partner-applications` | 2 | 1 Application + 1 Client-Reservierung (`CLIENT#…`, Status `RESERVED`) — das ist der Unique-Guard der Registry, kein Duplicate |

Es existiert **kein** APIProfile/Credential in einem anderen Tenant.

---

## 6. Was NICHT verändert wurde

* kein Terraform (`terraform plan/apply` wurde nicht ausgeführt)
* kein Cognito: kein neuer User, kein neuer Pool, **keine Client-Änderung**
  (`7ldhihlpdgsgcl3puvu4oi7ksv` und `82ji073smu1b3fsvj96sonso` unverändert)
* keine neue Infrastruktur, keine neue Tabelle
* keine Roh-DynamoDB-Schreibzugriffe — alle Mutationen liefen über die
  bestehende Domain (`create_profile`, `transition_status`,
  `issue_credential`, `create_partner_application`)
* keine bestehenden Tenant-Daten berührt

---

## 7. Offen / nächste Schritte (Frontend)

1. **Vercel**: Secret als serverseitige Env-Variable `RIS_API_KEY` eintragen
   (Production + Preview). **Niemals** `VITE_RIS_API_KEY` / `NEXT_PUBLIC_*`.
2. **Serverless Proxy** in der Jobsearch-App bauen:
   `POST https://g6901and25.execute-api.eu-central-1.amazonaws.com/v1/partner/agents/{agentId}/execute`
   mit `Authorization: Bearer <User-Access-Token>` **und**
   `X-Api-Credential: $RIS_API_KEY`.
3. **Login**: Cognito Authorization Code + PKCE gegen den RIS-Pool
   (`eu-central-1_ojbmoiYGM`), Client `7ldhihlpdgsgcl3puvu4oi7ksv`.
   Callback ist bereits konfiguriert:
   `https://www.mays-job-matcher.app/auth/callback`.
4. **Entitlements**: Für den genutzten Agenten muss noch ein Offer/Grant
   angelegt werden (admin-only, Domain `agents/ecosystem/offers.py`).
   Der Partner-Pfad prüft die Berechtigung des humanen Users.
5. **Optional, für später**: Der Human-Client kann `custom:tenant_id` in
   `ReadAttributes` erhalten — dann trägt der IdToken den Tenant und der
   HTTP-Verwaltungsweg (`POST /v1/apiprofiles`) funktioniert direkt.
   Das ist eine **bewusste Entscheidung** und wurde hier nicht ausgeführt
   (Vorgabe: bestehende Cognito-Clients nicht verändern).

---

## 8. Tests

```
python3 -m pytest tests/test_ris_admin_apiprofile_cli.py -q                     => 15 passed
python3 -m pytest tests/test_ris_admin_cli.py tests/test_ris_admin_credentials.py \
                 tests/test_ris_admin_apiprofile_cli.py \
                 tests/test_apiprofile_management_http.py \
                 tests/test_partner_registry_atomicity.py \
                 tests/test_partner_security_boundary.py -q                       => 173 passed
```

Neue Testdatei: `tests/test_ris_admin_apiprofile_cli.py` (Deckung: kein
Tenant-Flag, Fail-Closed ohne Anchor, admin-only Aktivierung, keine
Tenant-Überschreitung, Domain-Lifecycle statt Direktzugriff).
