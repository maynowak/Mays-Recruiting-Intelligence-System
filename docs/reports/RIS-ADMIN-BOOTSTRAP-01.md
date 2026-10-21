# RIS-ADMIN-BOOTSTRAP-01

**Task:** Ersten RIS-Administrator sicher vorbereiten, damit die bestehende Partner-Onboarding-Kette für Mays-Jobsearch genutzt werden kann.

**Projekt:** Mays-Recruiting-Intelligence-System · **Target:** ris-dev · **Region:** eu-central-1
**Account:** 240571105849 · **Datum:** 2026-10-21
**Typ:** **PREPARE** — keine AWS-Mutation. Vorlage zur Freigabe.
**Status:** `GO` (Vorbereitung) — Ausführung noch nicht freigegeben.

---

## Zusammenfassung

Der Bootstrap-Pfad ist vollständig aus vorhandenen AWS-Mitteln ableitbar. Es gibt **keine**
dedizierte RIS-Bootstrap-Tooling-Landschaft; das ist konsistent mit `AUTHENTICATION.md`, wo
„Tenant provisioning workflow" ausdrücklich als **Open Decision** geführt wird. Es ist daher
**keine neue Benutzerverwaltung** zu bauen: AWS-Cognito-Admin-APIs (`admin-create-user`,
`admin-add-user-to-group`, `admin-set-user-password`, `admin-update-user-attributes`) plus die
bereits existierende Gruppe `admins` genügen.

Drei Kernaussagen:

1. **Admin-Rechte entstehen im API-/JWT-Pfad ausschließlich aus `cognito:groups`.** Self-Signup
   kann niemals `admins` erhalten (kein Lambda-Trigger gesetzt, Gruppen nur per Admin-API
   zuweisbar). Self-Registration ist damit **kein** Admin-Vektor.
2. **Tenant kommt ausschließlich aus dem Claim `custom:tenant_id`.** Schreibbar nur per
   Admin-API; das Feld ist nicht Teil des Self-Serve-Signup-Formulars in der Anwendung (API hat
   keine Signup-Route; Profil-`tenantId` wird im Handler serverseitig gesetzt, Body-Werte werden
   ignoriert — `handler.py:521-525`).
3. **Der Admin-Bootstrap ist ein reiner AWS-Vorgang** (Cognito Admin-API). Er ist bewusst **nicht**
   über das `ris_admin`-CLI abbildbar: das CLI ist für Partner/APIProfile/Credential gedacht und
   autorisiert sich über eine **lokale** `RIS_ADMIN_AUTHORIZATION_FILE` (Trust-Anchor für den
   Operator-Platz, `tools/ris_admin/credentials.py:64-122`) — nicht über Cognito-Gruppen.

---

## 1. Bestehende Implementierung (verifiziert)

### Cognito User-Pool-Schema
- Pool `ris-dev-dev-users` (`eu-central-1_ojbmoiYGM`).
- Custom-Attribut `custom:tenant_id`: Typ `String`, `Mutable=true`, `Required=false`
  (`terraform/modules/cognito/main.tf:49-55`; live via `describe-user-pool` bestätigt).
- Standard-Attribute (`email` u. a.) werden live geführt; das Schema wird per
  `lifecycle { ignore_changes = [schema] }` bewusst out-of-band gehalten (RIS-COGNITO-SCHEMA-19).
- Passwort-Policy: min 8, Upper/Lower/Number, kein Symbol.
- `AutoVerifiedAttributes=["email"]`, `MfaConfiguration=OFF`.
- `AdminCreateUserConfig.AllowAdminCreateUserOnly=false` → Self-Signup ist **erlaubt**.

### custom:tenant_id
- Autoritative Tenant-Quelle: Claim `custom:tenant_id` (`docs/architecture/AUTHENTICATION.md:32`,
  `docs/api/API-STANDARD.md:304-306`).
- Handler liest ihn in `_extract_user_context` (`lambda/handler.py:311-313`).
- Kein Pre-Token-Generation-Trigger gesetzt (`LambdaConfig` leer) → der Claim wird unverändert aus
  den User-Attributen in das Token übernommen.

### Gruppen- und Rollenauflösung
- `lambda/handler.py:200-224` `_normalize_groups`: Akzeptiert native Liste **und** die vom
  API-Gateway-JWT-Authorizer stringifizierte Form (`"[admins]"`), drop nicht-erlaubte Zeichen.
  Kann eine Gruppe **niemals hinzufügen**, nur normalisieren.
- `lambda/handler.py:322` → `context['groups']`.
- `_cred_actor` (`handler.py` Z. 1492+): `"admins"`→admin · `"Staff"`→staff · sonst owner.
- Domain-Rollenprüfungen: `agents/ecosystem/api_profiles.py:38,104-109` und
  `agents/ecosystem/offers.py:29,99-100` (`ADMIN_GROUP="admins"`, `STAFF_GROUP="Staff"`).

### Admin-Autorisierung
- API-/JWT-Pfad: `_is_admin(actor) = "admins" in actor["groups"]` — aus Cognito-Claim.
- CLI-Pfad: `resolve_admin_authorization` liest eine **lokale, nicht world-writable, vom Nutzer
  eigene** JSON-Mapping-Datei (`RIS_ADMIN_AUTHORIZATION_FILE`), prüft `principal_arn` → `{role,
  tenantId}`. Fail-closed, kein Flag-Override (`tools/ris_admin/credentials.py:64-122`).
  → **Getrennte Autorisierungswelt** — hier **nicht** für den Cognito-Admin-Bootstrap zuständig.

### Tenant-Isolation
- Filter über `tenantId` in `api_profiles.py:142,352,362,588`; Cross-Tenant nur mit explizitem
  `reason` (`_check_cross_tenant`, `credentials.py:166-172`).
- Partner-Execute: JWT-Tenant **muss** Credential-Tenant **und** Registry-Tenant entsprechen
  (`handler.py:1080-1093`).
- `user-profile` Tabelle: PK `userId`, GSI `gsi-tenant` (tenant-scoped Reads).

### Benutzerregistrierung
- Keine Signup-/Login-Route im Repo (`docs/api/API-STANDARD.md:313`).
- Ablauf: SignUp → Confirm (E-Mail-Code) → Login (`USER_PASSWORD_AUTH`) → JWT →
  `POST /me/profile` (Conditional Write, 409 bei Duplikat). **Niemals** Auto-Provisioning durch Reads.

### Token-Claims
- `sub`, `email`, `preferred_username`/`cognito:username`, `cognito:groups`, `custom:tenant_id`
  (`SYSTEM-ARCHITECTURE.md:54`, `API-STANDARD.md:304-306`).
- Access-Token = API-Autorisierung; Authorizer prüft `issuer` + `audience` (kein Scope-Check).

### Bestehende Bootstrap-/Admin-Werkzeuge
- **Kein** RIS-spezifisches Bootstrap-Tool.
- `tools/ris_admin` — Partner/APIProfile/Credential/Entitlement-OPs (dry-run-fähig), **nicht**
  Benutzeranlage.
- Nächstliegende Referenz: `installer/projects/mays_orders/scripts/tests/setup_test_user.py`
  (fremdes Repo) nutzt exakt das Muster `admin_create_user` + `admin_set_user_password` +
  `admin_add_user_to_group`. Es ist **kein** Referenzbaustein für ris-dev, sondern belegt nur, dass
  die AWS-Admin-API der vorgesehene Weg ist.

---

## 2. Admin-Bootstrap — empfohlener Weg

**Weg:** AWS-Cognito-Admin-API, manuell/skriptbasiert, **ohne** Terraform, **ohne** neue IAM-Rolle,
**ohne** öffentlichen Endpunkt.

Anforderungen und Erfüllung:

| Anforderung | Umsetzung |
|---|---|
| Dedizierter Administrator | Eigene Identität (E-Mail), ausschließlich in `admins` |
| Gruppe `admins` | `admin_add_user_to_group` (Gruppe existiert bereits) |
| Eindeutige Tenant-Zuordnung | `custom:tenant_id` = vorgeschlagene ID (§3) per `admin_update_user_attributes` |
| Keine fest codierten Zugangsdaten | Passwort nur aus Env-Variable zur Laufzeit; nie im Repo/Log |
| Keine öffentlichen Admin-Endpunkte | Reine AWS-Admin-API, nicht über API Gateway exponiert |
| Keine Umgehung der Rollenprüfungen | Nutzt dieselbe `admins`-Gruppe + denselben `custom:tenant_id`-Claim wie der Handler |

**Warum kein neues Tooling:** Die vier Admin-API-Aufrufe sind idempotent ausführbar und
minimal. Ein Skript ist optionaler Komfort, keine neue Architektur (§9 zeigt die exakten Aufrufe).
Die Pflicht-Reihenfolge ist zwingend: **User → Passwort/Confirm → Gruppe → Tenant-Attribut**.

---

## 3. Tenant-Festlegung (Vorschlag)

**Befund:** Es existiert **keine** hart kodierte Tenant-Konvention und **kein** infra-Default.
Der einzige Code-Fallback ist `'default'` und gilt **nur** für die `user-profile`-Provisionierung
(`handler.py:525`), nicht als Tenant-Architektur. Die Terraform-`foundation_entitlements`-Map
(`terraform/variables.tf:288-299`) nimmt `tenantId` als freien String.

**Vorschlag:** `mays-ris-dev`

Begründung:
- Folgt der bestehenden Benennungslogik (`mays-orders`, `mays-ris`, `ris-dev`) und bleibt von
  fremden Familien (Orders) unterscheidbar.
- Explizit nicht `default`: der stille Fallback würde Jobsearch und potenzielle andere Nutzer im
  selben Namensraum vermischen — Isolation wäre nur scheinbar.
- Derselbe Tenant gilt für **Admin-User, Jobsearch-APIProfile, Credential und Entitlement** — die
  Partner-Bindungsregel (`registry.tenantId == credential.tenantId == jwt.tenantId`) verlangt
  Einheitlichkeit auf der ganzen Kette.

Keine neue Tenant-Architektur — nur ein konsistenter Wert im bestehenden Claim.

---

## 4. Cognito Client-Bindung

**Human App Client (verifiziert live):**

| Feld | Wert |
|---|---|
| Client-ID | `7ldhihlpdgsgcl3puvu4oi7ksv` |
| Name | `ris-dev-dev-client` |
| ClientSecret | **null** (public client, PKCE) |
| ExplicitAuthFlows | `ALLOW_USER_PASSWORD_AUTH`, `ALLOW_REFRESH_TOKEN_AUTH` |
| AllowedOAuthFlows | `code` (Authorization Code + PKCE) |
| Scopes | `openid`, `email`, `profile` |
| CallbackURLs | `http://localhost:5173/auth/callback`, `https://mays-job-matcher.vercel.app/auth/callback` |
| LogoutURLs | `http://localhost:5173/`, `https://mays-job-matcher.vercel.app/` |
| IdentityProvider | `COGNITO` |
| RefreshTokenValidity | 30 (Tage) · `EnableTokenRevocation=true` |

**M2M Client:** `ris-dev-m2m-client` (`82ji073smu1b3fsvj96sonso`), `client_credentials`, Scope
`ris-api/m2m:execute` — bleibt unangetastet.

**Für den Admin-Bootstrap relevant:** Der Admin-User muss sich über `7ldhih…` (bzw. Managed Login)
anmelden; der Access-Token trägt `cognito:groups` und `custom:tenant_id`. Für den späteren
**Partner-User-Execute** bindet die Registry den JWT-`client_id` an `apiProfileId` + `tenantId`.

**Keine neuen App Clients / User Pools** — es wird ausschließlich der bestehende Human Client genutzt.

---

## 5. Sicherheitsprüfungen

| Prüfung | Ergebnis | Evidenz |
|---|---|---|
| Admin-Rolle aus vertrauenswürdigem Claim | ✅ Nur `cognito:groups`; keine Header/Body-Einflussnahme | `handler.py:322`, `api_profiles.py:104-109` |
| Tenant nicht benutzer-setzbar | ✅ `custom:tenant_id` nur im Token/Admin-API; Profil setzt serverseitig; Body ignoriert | `handler.py:311-313`, `521-525` |
| Keine Admin-Rechte durch Self-Registration | ✅ Kein Lambda-Trigger; Self-Signup kann keine Gruppen setzen | `LambdaConfig{}`, `AllowAdminCreateUserOnly=false` |
| Keine Secrets in Git/Logs/Reports | ✅ Passwort nur Env-Var; kein Secret ausgegeben | dieses Dokument |
| Kein Zugriff auf andere Tenants | ✅ `_check_cross_tenant`, JWT-/Credential-/Registry-Tenant-Gleichheit | `credentials.py:166-172`, `handler.py:1080-1093` |
| Keine Umgehung der Rollenprüfungen | ✅ Bootstrap nutzt dieselbe `admins`-Gruppe | §2 |
| `_normalize_groups` fügt nie Gruppen hinzu | ✅ nur Normalisierung, Allowlist | `handler.py:200-224` |

**Restrisiko (dokumentiert, kein Blocker):** Self-Signup ist pool-seitig erlaubt. Ein
selbstregistrierter Nutzer erhält **keine** Sonderrolle (owner), kann aber ein eigenes
`APIProfile` (PENDING) anlegen. Aktivierung, Grant und Credential-Ausgabe bleiben admin-only.
Optional könnte langfristig `AllowAdminCreateUserOnly=true` gesetzt werden — das wäre eine
Terraform-Änderung und ist **nicht** Teil dieses Auftrags.

---

## 6. Tests

Ausgeführt (read-only, kein AWS):

```
python3 -m pytest tests/test_ris_admin_credentials.py tests/test_partner_security_boundary.py -q
→ 96 passed

python3 -m pytest tests/test_authorization_context.py tests/test_api_profiles.py \
     tests/test_apiprofile_management_http.py tests/test_credential_verification.py \
     tests/test_entitlement_provisioning.py tests/test_introspection_capability.py \
     tests/test_machine_entrypoint.py -q
→ 261 passed

python3 -m pytest tests/ -q
→ 1608 passed, 2 failed (bekannte Baseline), 11 skipped
```

Abgedeckt: Admin-Rollenauflösung, Tenant-Isolation, Cognito-Claim-Verarbeitung
(`_normalize_groups`), Unauthorized/Forbidden, Partner-Security-Boundaries (T01-T14).
Die 2 Baseline-Fehler (`test_install_dry_run_performs_no_mutation`,
`test_validate_skips_workspace_without_backend`) sind dokumentiert und unverändert.

**Klassifikation:** `GREEN`.

---

## 7. Ergebnis / Offene Voraussetzungen

### Offene Voraussetzungen (vor Ausführung)

1. **Freigabe** dieses Bootstrap-Plans (PREPARE-Auftrag).
2. **Admin-Identität festlegen** — konkrete E-Mail, die als erster Admin dient (read-only geprüft:
   Pool hat 0 Benutzer).
3. **Passwort** über sicheren Kanal (Env-Var zur Laufzeit; nie im Repo). Der Admin muss es nach
   dem ersten Login wechseln, wenn ein temporäres Passwort verwendet wird.
4. **`RIS_ADMIN_AUTHORIZATION_FILE`** (optional, nur wenn das `ris_admin`-CLI für Partner/APIProfile
   genutzt werden soll) — liegt außerhalb des Repos, `0600`, vom Operator-User owned.
5. **DNS/Jobsearch-Verdrahtung** bleibt eine separate Voraussetzung (aus
   MAYS-RIS-JOBSEARCH-PARTNER-ONBOARDING-01, §8).

### GO / NO-GO

> **GO** für den in §9 vorgelegten Bootstrap (nach Freigabe).
> **NO-GO** für jede Ausführung in diesem Auftrag — es wurde **nichts** geschrieben.

---

## 8. Freigabegate (dieser Auftrag)

Erlaubt und ausgeführt: read-only AWS-Prüfungen, Code-/Contract-Audit, Tests, Dokumentation,
Git-Commit/Push.

**Nicht ausgeführt:** kein Benutzer erstellt, keine Gruppenmitgliedschaft verändert, keine
Tenant-Daten geschrieben, keine Credentials ausgestellt, keine Terraform-Änderung, keine Secrets.

---

## 9. Konkrete AWS-Kommandos (zur Freigabe — noch NICHT ausgeführt)

Variablen:
```
POOL=eu-central-1_ojbmoiYGM
ADMIN_EMAIL=<erste Admin-E-Mail>
TENANT=mays-ris-dev
AWS_PROFILE=mayaws AWS_REGION=eu-central-1
```

**Schritt 1 — Admin-User anlegen** (temporäres Passwort, kein Versand; Passwort nur interaktiv):
```bash
aws cognito-idp admin-create-user \
  --user-pool-id "$POOL" \
  --username "$ADMIN_EMAIL" \
  --user-attributes Name=email,Value="$ADMIN_EMAIL" \
                   Name=email_verified,Value=true \
                   Name=custom:tenant_id,Value="$TENANT" \
  --desired-delivery-mediums EMAIL \
  --message-action SUPPRESS
```

**Schritt 2 — Passwort setzen** (permanent; Wert NICHT im Shell-Verlauf/Log):
```bash
read -rs ADMIN_PW          # interaktiv, ohne Echo
aws cognito-idp admin-set-user-password \
  --user-pool-id "$POOL" \
  --username "$ADMIN_EMAIL" \
  --password "$ADMIN_PW" \
  --permanent
unset ADMIN_PW
```

**Schritt 3 — Gruppe `admins` zuweisen:**
```bash
aws cognito-idp admin-add-user-to-group \
  --user-pool-id "$POOL" \
  --username "$ADMIN_EMAIL" \
  --group-name admins
```

**Schritt 4 — Tenant-Attribut sicherstellen** (falls in Schritt 1 nicht gesetzt/zu ändern):
```bash
aws cognito-idp admin-update-user-attributes \
  --user-pool-id "$POOL" \
  --username "$ADMIN_EMAIL" \
  --user-attributes Name=custom:tenant_id,Value="$TENANT"
```

**Schritt 5 — Verifikation (read-only):**
```bash
aws cognito-idp admin-get-user --user-pool-id "$POOL" --username "$ADMIN_EMAIL" \
  --query 'UserAttributes[?Name==`custom:tenant_id`]'
aws cognito-idp admin-list-groups-for-user --user-pool-id "$POOL" --username "$ADMIN_EMAIL" \
  --query 'Groups[].GroupName'
```

**Schritt 6 — Login/Token (optional, zur Verifikation der Claims):**
USER_PASSWORD_AUTH gegen Client `7ldhihlpdgsgcl3puvu4oi7ksv`, dann im Access-Token prüfen:
`cognito:groups` enthält `admins` und `custom:tenant_id == mays-ris-dev`.

**Danach:** Partner-Onboarding-Kette aus
`docs/reports/MAYS-RIS-JOBSEARCH-PARTNER-ONBOARDING-01.md` §11 kann starten.

---

## Evidenz-Referenzen

- Code: `lambda/handler.py` (Z. 200-224 Gruppen, 300-324 Context, 510-541 Profil, 1009-1165
  Partner-Execute), `agents/ecosystem/api_profiles.py:38-55,104-142`,
  `agents/ecosystem/credentials.py:64-172`, `agents/ecosystem/offers.py:29,99-100`,
  `tools/ris_admin/credentials.py:64-122`, `tools/ris_admin/cli.py:80-116,230-349`.
- Terraform: `terraform/modules/cognito/main.tf:15-75`, `terraform/variables.tf:288-299`,
  `terraform/modules/dynamodb/main.tf` (tenantId-Keys).
- Docs: `docs/architecture/AUTHENTICATION.md`, `docs/architecture/RIS_AUTH_CONTRACT.md`,
  `docs/api/API-STANDARD.md:302-318`, `docs/architecture/SYSTEM-ARCHITECTURE.md:54`.
- AWS (read-only): `describe-user-pool` (Schema, Policies, LambdaConfig, AdminCreateUserConfig),
  `describe-user-pool-client` (7ldhihlpdgsgcl3puvu4oi7ksv), `list-groups`, `list-users`,
  `list-users-in-group`, `list-user-pool-clients`.
- Referenz (fremd): `installer/projects/mays_orders/scripts/tests/setup_test_user.py`.
