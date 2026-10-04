# RIS-P17-CREDENTIAL-LIFECYCLE-E2E-01 — Credential Lifecycle E2E

STATUS: **RED** — E2E **nicht ausführbar**; zwei unabhängige, belegte Blocker. Kein CredentialLifecycle live verifiziert.

- Datum: 2026-10-04 UTC
- Branch/HEAD: `main`, `a447c8a`
- Account/Region/Workspace: `240571105849` (`user/Mayaws`) / `eu-central-1` / `mays-ris`
- AWS-Mutation: 1 Cognito-Testuser (synthetisch, deaktiviert), **keine** Terraform-/Lambda-/IAM-/Gateway-/DynamoDB-Mutation

## 1. Zusammenfassung

Der Credential-Lifecycle konnte **nicht** getestet werden. Zwei unabhängige Blocker, beide im Produktivcode belegt:

| # | Blocker | Klasse | Folge |
|---|---|---|---|
| **B1** | **Keine Management-Schnittstelle für APIProfile.** Alle Schreib-/Transitionsfunktionen (`create_profile`, `update_profile`, `transition_status`, `renew_profile`, `set_client_ref`, `set_expires_at`) haben **null** produktive Aufrufer; nur `get_profile`/`resolve_selection` (Read) sind verdrahtet. `mays-ris-dev-api-profiles` ist leer (Count 0). Keine Gateway-Route für APIProfile in `terraform/modules/api/main.tf`. | **D** | B, C, G, H, REVOKE, Teile von F nicht ausführbar |
| **B2** | **`dynamodb:Scan` fehlt auf `mays-ris-dev-agent-catalog`.** Code braucht `scan` (`agents/ecosystem/catalog_adapter.py:76,121`), IAM-Policy `…-dynamodb-platform` gewährt nur `BatchGetItem, GetItem, Query`. Live-Log belegt `AccessDeniedException … Scan`. | **C/F** | `GET /agents` liefert **leere Liste**, Introspection liefert leere Capabilities; D „Agent ACTIVE/executable" und F6 nicht aussagekräftig prüfbar |
| **B3** | **Kein M2M-Einstiegspunkt.** `verify_api_credential` hat **null** produktive Aufrufer (nur Tests). `introspect_credential` ist im Handler unerreichbar: `handler.py:698` liegt in `if bearer_credential:`, aber der einzige Aufrufer `handler.py:269` übergibt nur `(event, context)`. | **C** | D, F1–F5, F7, F8 nicht ausführbar |

B1 und B3 betreffen die Kernfrage von P17 (Credential-Ausstellung + M2M-Autorisierung). Damit ist kein aussagekräftiger Lifecycle-Test möglich → **RED**, nicht GREEN.

## 2. AWS / Git Context

| Prüfung | Ergebnis |
|---|---|
| Branch / HEAD | `main` / `a447c8a` |
| `git status --short` | tracked clean; 9 vorbestehende untracked unberührt |
| `AWS_PROFILE` | `mayaws` (keine Default-Credentials) |
| Account | `240571105849` ✔ |
| Region | `eu-central-1` ✔ |
| Workspace | `mays-ris` ✔ |
| Terraform-Mutation | **keine**; Plan unverändert: nur `module.iam.lambda_policy` (Fremd-Drift) + `sqs_mapping` (ESM-Tags) |

## 3. Preconditions

| # | Prüfung | Ergebnis |
|---|---|---|
| 5 | API Gateway ID + Routen | `aboqolpm0f`, **22** Routen |
| 6 | 7 Credential-Routen + Introspection | 7/7 + `GET /v1/introspection` vorhanden |
| 7 | Cognito `AutoVerifiedAttributes` | `["email"]` ✔ unverändert |
| 8 | Keine Terraform-Mutation | bestätigt, Plan unverändert |
| 9 | Testuser | Pool war **leer** (`list-users` → `[]`) → synthetischen Testuser angelegt |

## 4. Testuser-Kontext (synthetisch, anonymisiert)

| Feld | Wert |
|---|---|
| Username | `p17-e2e-synthetic-01` |
| E-Mail | `p17-e2e-synthetic@example.invalid` (`.invalid` ist reserviert, nicht zustellbar) |
| Tenant | `custom:tenant_id` = synthetischer Wert |
| Status final | `CONFIRMED`, **Enabled: false** (deaktiviert, s. Cleanup) |

Keine realen personenbezogenen Daten. Passwort und Tokens wurden ausschließlich in einer tmp-Datei mit Mode 700 gehalten, nie ausgegeben und nach dem Lauf mit `shred -u` vernichtet.

## 5. Ausgeführte Testschritte

### A) Human Identity — 🟢 BESTANDEN

| Request | Ergebnis |
|---|---|
| `admin_create_user` + `admin_set_user_password` (permanent) | ok, `CONFIRMED` |
| `initiate_auth` `USER_PASSWORD_AUTH` | IdToken + AccessToken, kein Challenge |
| `GET /me` | **200** — `{userId, email, groups, tenantId}` |
| `GET /platform` | **200** — `{name, version, environment}` |
| `GET /agents` | **200** — aber `agents: []` (leer, siehe B2) |
| `GET /me/profile` | **404** `{"error":"Profile not found"}` |

`GET /me/profile` → 404 ist **korrekt**: `docs/api/API-STANDARD.md:25-26` schreibt explizite Provisionierung vor („NIEMALS Auto-Provisioning durch Reads"). Kein Defekt.

### B) APIProfile — 🔴 NICHT AUSFÜHRBAR (B1)

Beleg:

- `mays-ris-dev-api-profiles` Count = **0**
- Keine Gateway-Route mit `apiProfileId` außer den 7 Credential-Routen (`grep` in `terraform/modules/api/main.tf`)
- Produktive Aufrufer der Schreibfunktionen in `agents/ecosystem/api_profiles.py`:

| Funktion | produktive Aufrufer | Test-Aufrufer |
|---|---|---|
| `create_profile` | **0** | 28 |
| `transition_status` | **0** | 52 |
| `update_profile` | **0** | 9 |
| `renew_profile` | **0** | 1 |
| `set_client_ref` | **0** | 1 |
| `set_expires_at` | **0** | 4 |
| `get_profile` | 6 | 19 |
| `resolve_selection` | 1 | 10 |

Das vom Gate geforderte Vorgehen „über die tatsächlich implementierte Management-Schnittstelle einen Test-APIProfile-Zustand herstellen" ist damit **nicht möglich** — die Schnittstelle existiert nicht. Der einzige verbleibende Weg wäre ein direkter DynamoDB-Write, der im Gate ausdrücklich verboten ist („Keine DynamoDB Update").

### C) Credential Issue — 🔴 NICHT AUSFÜHRBAR (Folge von B1)

| Request | Ergebnis | Interpretation |
|---|---|---|
| `POST /v1/apiprofiles/{pid}/credentials` | **404** `{"error":"Not found"}` | Profil existiert nicht — korrekt |
| `GET /v1/apiprofiles/{pid}/credentials` | **200** `{"items":[]}` | Liste funktioniert, leer |

Ohne existierenden APIProfile kein `credentialId`, kein Secret, kein Lifecycle. Es wurde **kein** Credential erzeugt (Tabellen-Count weiterhin 0).

### D) M2M Authentication — 🔴 NICHT AUSFÜHRBAR (B3)

`verify_api_credential` (`agents/ecosystem/credentials.py:751`) hat null produktive Aufrufer. Der einzige Produktions-Einstieg, `introspect_credential` (`handler.py:698`), ist unerreichbar, weil `bearer_credential` am einzigen Aufrufer (`handler.py:269`) nie übergeben wird. Ein gültiges Bearer-Credential kann live nirgends eingereicht werden.

### E) Introspection — 🟡 TEILWEISE BESTANDEN (Human-Modus)

Erster Versuch **401** — klassifiziert als **A) Fixture-Problem**: `introspect_human` (`introspection.py:176-179`) gibt 401, wenn `user_id` oder `tenant_id` leer ist; `custom:tenant_id` fehlte am Testuser. Nach Setzen des synthetischen Tenant-Attributs:

| Feld | Wert |
|---|---|
| Status | **200** |
| `context` | `human` |
| `subject` | `{userId, tenantId}` (synthetisch) |
| `allowedProfiles` | `[]` |
| `capabilities` | `[]` |
| `offers` | `[]` |
| `validity.checkedAt` | vorhanden |

Keine Secrets in der Response. Die **leeren** `capabilities` sind partly B1 (keine Profile) und partly **B2** (Katalog nicht lesbar) geschuldet — der Erfolgsfall „Agent ist ACTIVE/executable" ist damit **nicht** nachweisbar. Der Credential-Kontext (`introspect_credential`) ist wegen B3 nicht testbar.

### F) Negative Auth — 🔴 NICHT AUSFÜHRBAR (B3)

Alle acht Negativfälle (401 für unbekannt/formatungsgültig-falsch, 403 für revoked/disabled/expired, 403 für nicht erlaubtes Agent-Ziel, Ablehnung fremder Profil-/Tenant-Bindungen) setzen einen funktionierenden M2M-Einstiegspunkt voraus. Der existiert nicht. F6 wäre zusätzlich durch B2 (Katalog nicht lesbar) nicht aussagekräftig.

### G/H/REVOKE — 🔴 NICHT AUSFÜHRBAR (Folge von C)

Rotation, Profil Disable/Enable und Revoke setzen ein existierendes Credential voraus. Keines erzeugt.

## 6. Blocker B2 im Detail (unabhängiger Runtime-Defekt)

| Beleg | Wert |
|---|---|
| IAM live (`…-dynamodb-platform`, agent-catalog-Statement) | `BatchGetItem`, `GetItem`, `Query` |
| Code (`agents/ecosystem/catalog_adapter.py`) | `scan` (`:76`, `:121`), `get_item` (`:99`) |
| Fehlend | **`dynamodb:Scan`** auf Tabellen-ARN |
| CloudWatch | `AccessDeniedException … not authorized to perform: dynamodb:Scan on resource: arn:aws:dynamodb:eu-central-1:240571105849:table/mays-ris-dev-agent-catalog` |
| Lebt-Auswirkung | `GET /agents` → `agents: []`; Introspection → `capabilities: []` |

Der Fehler wird im Handler gefangen und degradiert still (200 mit leerer Liste) — er ist nur im Log sichtbar. Das ist dieselbe Fehlerklasse wie der in `RIS-ENTITLEMENTS-IAM-ANALYSIS.md` dokumentierte Entitlement-Gap, betrifft aber die **andere** Policy (`platform`) und war dort nicht in Scope. Das bestehende Analyse-Gate hat diese Lücke deshalb nicht abgedeckt.

## 7. I) Audit — 🟢 BESTANDEN (soweit ausführbar)

Audit-Einträge im Log `/aws/lambda/mays-ris-dev-agent`, ohne Secrets:

```
introspection-audit ref=… action=introspect outcome=denied  context=human
introspection-audit ref=… action=introspect outcome=denied  context=profile
API request: GET /v1/introspection
API request: POST /v1/apiprofiles/…/credentials
```

- Audit-Trail für Introspection (erfolglos **und** verweigert) vorhanden
- Lifecycle-Audit (Issue/Rotate/Disable/Revoke) **nicht prüfbar**, da kein Credential erzeugt wurde
- Geprüfte Einträge enthalten weder Secret, Token, Authorization-Header noch Passwort

## 8. J) Cleanup

| Schritt | Ergebnis |
|---|---|
| Test-APIProfile deaktiviert/revoked | entfällt — keiner erzeugt |
| Test-Credential REVOKED | entfällt — keiner erzeugt |
| Passwort/Token vernichtet | `shred -u` auf Passwort- und Token-Dateien; JSON-Payloads mit Zugangsdaten gelöscht |
| Testuser | **deaktiviert** (`Enabled: false`), nicht gelöscht — Reversibel via `admin-enable-user`. Kein etabliertes sicheres Löschverfahren für Testuser vorhanden |
| Fremde Ressourcen | keine verändert |
| `mays-ris-dev-api-profiles` / `-credentials` | beide Count **0** — keine Testartefakte |
| Gateway | 22 Routen, unverändert |
| Lambda | `yaKXvStx/o/M/XHUiA01d18cFDoi35PMcAibequbZHc=`, `LastModified 2026-10-04T11:44:08Z` — unverändert |
| ESM | UUID `7cc946b9…`, `Enabled`, Batch 5 — unverändert |

## 9. Erwartet vs. tatsächlich

| Erwartung (Gate) | Tatsächlich |
|---|---|
| A) Human JWT → `GET /me` 200 | ✅ 200 |
| B) Test-APIProfile über Management-API anlegen | ❌ Schnittstelle existiert nicht (B1) |
| C) Credential ausstellen, ACTIVE, Secret einmalig | ❌ nicht ausführbar (B1) |
| D) M2M mit Bearer → positiver Authorization-Pfad | ❌ kein M2M-Einstiegspunkt (B3) |
| E) Introspection positiv | ⚠️ 200, aber leere Capabilities (B1/B2); Credential-Kontext nicht testbar (B3) |
| F) 8 Negativfälle 401/403 | ❌ nicht ausführbar (B3) |
| G) Rotation A→B, A=403 | ❌ nicht ausführbar |
| H) Profil DISABLED → 403 → ACTIVE → ok | ❌ nicht ausführbar |
| REVOKE → 403, terminal | ❌ nicht ausführbar |
| I) Audit ohne Secrets | ✅ für Introspection belegt |
| J) Cleanup | ✅ vollständig, Testuser deaktiviert |

## 10. AWS-Mutationen

| Art | Umfang |
|---|---|
| Cognito | 1× `admin_create_user`, 1× `admin_set_user_password`, 2× `initiate_auth`, 1× `admin_update_user-attributes`, 1× `admin_disable_user` — **alle** auf dem synthetischen Testuser |
| Terraform / Lambda / IAM / Gateway / DynamoDB / SQS | **keine** |

## 11. Offene Punkte / Abweichungen

1. **B1 — APIProfile ohne Management-API.** Blocker für den gesamten Credential-Lifecycle. Erforderlich ist ein eigenes Gate: Gateway-Route + Handler-Dispatch für `create_profile` / `transition_status` (die Logik existiert und ist getestet, nur nicht verdrahtet).
2. **B2 — `dynamodb:Scan` fehlt auf `mays-ris-dev-agent-catalog`.** Eigenständiges IAM-Gate. Solange es fehlt, liefern `/agents` und `/v1/introspection` still degradierte Antworten — ein Befund, der ohne Log-Lesen nicht auffällt.
3. **B3 — kein M2M-Einstiegspunkt.** `verify_api_credential` ist unverdrahtet; der Introspection-Credential-Branch ist durch den nicht übergebenen `bearer_credential` tot. Erforderlich: Handler-Übergabe plus eine M2M-Route (bewusst nicht Teil von P16/P17C).
4. **Entitlement-Grant weiterhin offen** (`grant_offer`/`withdraw_entitlement` ohne produktive Aufrufer, siehe `RIS-ENTITLEMENTS-IAM-ANALYSIS.md`). Für F6 „Agent-Ziel nicht erlaubt" wird ein Entitlement-Grant benötigt.
5. **`GET /health` weiterhin 404** (live, ohne Handler-Pfad) — vorbestehend.
6. Der Testuser kann für einen späteren Lauf reaktiviert werden (`admin-enable-user`); Passwort ist vernichtet, also ist eine Neuanmeldung nötig.
7. **Methodischer Hinweis:** Die Entitlement-IAM-Analyse hat die Plattform-Policy geprüft, aber nur auf den Entitlements-ARN. Eine vollständige Least-Privilege-Analyse müsste **alle** Statements der `platform`-Policy gegen den Codebedarf je Tabelle prüfen — B2 wäre dabei aufgefallen.

## 12. P17-Einstufung

**RED.** Der reale Credential-Lifecycle ist über die live Gateway-Schicht nicht nachweisbar, und die negativen Sicherheitsfälle zeigen keine 401/403-Grenzen. P17 wird **nicht** als GREEN geführt.
