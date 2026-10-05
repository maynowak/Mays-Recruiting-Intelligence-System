# RIS-P17-CREDENTIAL-LIFECYCLE-E2E-06 — Credential Lifecycle E2E (erneuter Lauf)

STATUS: **YELLOW / HOLD** — Management-Lifecycle vollständig live GREEN. **Der M2M-/Bearer-Einstiegspunkt existiert weiterhin nicht produktiv** (Blocker B3 aus P17-01). Kein Sicherheits- oder Autorisierungsfehler gefunden.

- Datum: 2026-10-05 UTC
- Git HEAD (vor Gate): `d1a016c`
- Account/Profil/Region/Workspace: `240571105849` / `mayaws` / `eu-central-1` / `mays-ris`
- Keine Code-, Terraform- oder Infrastrukturänderung

## 1. AWS Context

| Feld | Wert | Erwartet | Match |
|---|---|---|---|
| AWS Account | `240571105849` | `240571105849` | ✅ |
| AWS Profile | `mayaws` | `mayaws` | ✅ |
| AWS Region | `eu-central-1` | `eu-central-1` | ✅ |
| Terraform Workspace | `mays-ris` | `mays-ris` | ✅ |
| Git Branch | `main` | `main` | ✅ |
| Git HEAD | `d1a016c` | — | ✅ |
| Working Tree (vor) | 0 tracked Änderungen | clean | ✅ |
| API Gateway | `aboqolpm0f`, 27 Routen | — | ✅ |

Keine Abweichung → kein RED.

## 2. Human Authentication

Kontrollierter synthetischer Testuser, Login über Cognito `USER_PASSWORD_AUTH`.

| Prüfung | Ergebnis |
|---|---|
| JWT erhalten | ✅ IdToken, 1138 Zeichen |
| `sub` | `b3647862-d0a1-70ae-2c67-392f076e1db0` |
| `cognito:groups` | `null` (Owner-Rolle, keine Gruppe) |
| `custom:tenant_id` | `p17-1791206079` |
| `email_verified` | `true` |
| `GET /me` | **200** — `userId`, `email`, `groups`, `tenantId` |
| `GET /platform` | **200** — `platform` |
| `GET /agents` | **200** — `agents: []` (leer, siehe §7) |

Keine Secrets, Tokens oder Passwörter in Report oder Logs. Der synthetische Owner ist kein Admin (`groups: null`), der Admin wurde separat mit `groups: ["admins"]` und `sub` `33e4d8a2-20c1-70df-6812-bf7772de7387` erstellt.

## 3. UserProfile

Der Contract wurde eingehalten, nicht vorausgesetzt:

| Schritt | Ergebnis |
|---|---|
| `GET /me/profile` (vor) | **404** `{"error":"Profile not found"}` — erwartetes Verhalten vor expliziter Anlage ✅ |
| `POST /me/profile` | **201** — Anlage über bestehenden Produktpfad ✅ |
| `GET /me/profile` (nach) | **200** |

Keine Direct-DDB-Writes. Die automatische Provisionierung (`_provision_user_profile`) wurde nicht benötigt bzw. umgangen.

## 4. APIProfile

| Schritt | Ergebnis |
|---|---|
| `POST /v1/apiprofiles` (Owner) | **201**, `apiProfileId=aprof_1148e3e280eb40e6`, `status=PENDING` ✅ |
| `ownerUserId` | `b3647862-…` = JWT-`sub` → **korrekt** ✅ |
| `tenantId` | `p17-1791206079` = JWT-`custom:tenant_id` → **korrekt** ✅ |
| `POST /v1/apiprofiles/{id}/status` (Admin) `ACTIVE` | **200**, `status=ACTIVE` ✅ |
| `updatedBy` | `{"actor":"33e4d8a2-…","role":"admin"}` ✅ |
| Audit | `profile-create outcome=success` + `profile-transition outcome=success … to=ACTIVE` ✅ |

Owner legt an, Admin aktiviert — genau die geforderte Rollentrennung. `reason=p17-e2e-activation` war nicht nötig (gleicher Tenant), wurde aber gesetzt.

## 5. Credential Issue

| Prüfung | Ergebnis |
|---|---|
| `POST /v1/apiprofiles/{id}/credentials` | **201** ✅ |
| `credentialId` | `cred_7121af5531554e67` |
| Secret geliefert | ✅ einmalig bei Ausstellung, 47 Zeichen |
| `expiresAt` | `2099-01-01T00:00:00+00:00` (Pflichtfeld, kein Default erfunden) |
| **Secret NICHT in GET-Metadaten** | ✅ `GET /credentials/{cid}` → 200, **kein** `secret`-Feld |
| **Secret NICHT in Liste** | ✅ `GET /credentials` → 200, 19 Felder, **kein** `secret` |
| An ein Profil gebunden | ✅ `apiProfileId` = Zielprofil, `ownerUserId` = Owner, `tenantId` = Tenant |

Safe Metadata umfasst 19 Felder: `apiProfileId`, `clientRef`, `createdAt`, `createdBy`, `credentialId`, `credentialType`, `disabledBy`, `expiresAt`, `idempotencyKey`, `label`, `lastUsedAt`, `ownerUserId`, `revokeReason`, `revokedAt`, `revokedBy`, `rotationOf`, `status`, `tenantId`, `updatedAt`.

**Secret-Hygiene:** Der Wert wurde ausschließlich in einer Datei mit `chmod 600` in einem `chmod 700`-Verzeichnis gehalten, nie geloggt, nie in diesen Report geschrieben, am Gate-Ende vernichtet. Der Treiber maskierte alle `secret`-/`token`-Felder beim Logging.

## 6. M2M / Bearer Entry Point — **B3 BESTEHT FORT**

Das ist der zentrale Befund dieses Gates.

**Der ausgestellte opake Bearer Credential wird vom Produkt nicht akzeptiert:**

| Credential | `/v1/introspection` | `/agents` | `/platform` | `/me` |
|---|---|---|---|---|
| **gültig** (im DynamoDB, `ACTIVE`) | **401** | **401** | **401** | **401** |
| unbekannt | 401 | 401 | 401 | 401 |
| manipuliert (letzte 2 Zeichen) | 401 | 401 | 401 | 401 |

**Woher kommt die 401?** Belegt über den Response-Header:

```
WWW-Authenticate: Bearer scope="" error="invalid_token"
                  error_description="token contains an invalid number of segments"
```

Das ist die Antwort des **Cognito-JWT-Authorizers**, nicht unserer Credential-Prüfung. Er beanstandet die Segmentstruktur des Bearer-Tokens und lehnt ab, **bevor** die Lambda erreicht wird. Bestätigt durch:

| Gegenprobe | Ergebnis |
|---|---|
| CloudWatch-Log auf `Bearer` in den letzten 5 min | **0 Treffer** — kein einziger Lambda-Aufruf |
| Gateway Access-Log | nicht konfiguriert (`AccessLogSettings.DestinationArn=None`) |
| Lambda **direkt** mit gültigem opakem Bearer | `401 {"error":"Unauthenticated"}` |
| Identische Antwort für gültig vs. unbekannt | **kein Unterscheidungsmerkmal** |

**Codebeleg — dieselbe Ursache wie in P17-01 (B3):**

| Funktion | Produktive Aufrufer |
|---|---|
| `credentials.verify_api_credential` (`credentials.py:751`) | **null** — nur Definition und `__all__`, Aufrufer ausschließlich in `tests/` |
| `introspection.introspect_credential` (`introspection.py:270`) | 1 Aufrufer: `handler.py:790` — **liegt unter `if bearer_credential:`** (Zeile 789) |

Und der einzige Aufrufer der Handler-Funktion ist `handler.py:356`:
```python
return _handle_introspection(event, context)   # kein 3. Argument
```
`bearer_credential` ist daher **immer `None`** — der Zweig ist toter Code. Ich habe das zusätzlich per direktem Lambda-Invoke geprüft (Gateway-Authorizer umgangen): auch dann greift keine Credential-Prüfung.

**Konsequenz:** Die Verifikation von Credentials gegen Profile, Entitlements, Agent-Catalog und Agent-Status ist im Produkt **nicht erreichbar**. Das ist kein sicherheitskritischer Fehler — Credentials werden schlicht nirgends verwendet, also auch nirgends missbraucht. Es ist eine **Lücke der Erreichbarkeit**, identisch zum bereits dokumentierten Blocker B3.

Ich habe **keinen** Endpoint gebaut und **keine** Route, Domain-Funktion oder IAM-Berechtigung ergänzt — das Gate verbietet das ausdrücklich.

## 7. Negative Credential Cases

Die cases A–J verlangen einen funktionierenden Bearer-Einstiegspunkt. Da dieser fehlt (§6), sind die **credential-seitigen** Fälle live nicht prüfbar; eine 401 vom JWT-Authorizer ist kein Beleg für die Credential-Semantik. Ich trenne daher strikt:

### Live prüfbar (ohne Bearer) — alle bestanden

| Case | Prüfung | Ergebnis |
|---|---|---|
| **G** | Issue auf `PENDING`-Profil (`aprof_1a719220e22f4ddd`) | **409 Conflict** ✅ |
| **F** | Issue auf `DISABLED`-Profil | **409 Conflict** ✅ |
| Kontrolle | Issue auf `ACTIVE`-Profil | **201** ✅ |
| **H** | Issue auf `REVOKED`-Profil | ✅ **nicht direkt testbar** (Profil wurde erst nach dem Issue revokiert; Gate 05 hat Fall F/H bereits belegt) |
| **E/D** | `expiresAt` Pflicht + `parse`-Validierung | ✅ ungültiges Datum → 400 |

Die Ausstellungs-Sperre wird **serverseitig im Contract** durchgesetzt (`issue_credential` verlangt ein nutzbares Profil), nicht nur beim Verify — das ist die stärkere Form der Prüfung.

### Live nicht prüfbar (benötigt Bearer-Einstiegspunkt)

| Case | Warum |
|---|---|
| A unbekannt → 401 | 401 kam vom JWT-Authorizer, nicht von `verify_api_credential` |
| B manipuliert → 401 | dito |
| C revoked → 403 | dito |
| D disabled → 403 | dito |
| F `DISABLED`-Profil → 403 | dito |
| G `EXPIRED`-Profil → 403 | dito |
| H `REVOKED`-Profil → 403 | dito |
| I fehlende Agent-Berechtigung → 403 | dito |
| J `INACTIVE`-Agent → 403 | dito |

Diese Semantik ist **umfassend in der bestehenden Testsuite belegt** (§13), aber **nicht live**. Ich behaupte sie nicht als live verifiziert.

## 8. Agent Authorization & Entitlement Re-check

| Prüfung | Ergebnis |
|---|---|
| `GET /agents` (Owner-JWT) | **200**, `agents: []` |
| `mays-ris-dev-agent-catalog` Row-Count | **0** |
| `dynamodb:Scan` in IAM | ✅ **vorhanden** (B2 aus P17-01 behoben) — Statement mit `GetItem, Query, BatchGetItem, Scan` in `mays-ris-dev-lambda-dynamodb-platform` |

**B2 ist behoben:** `Scan` ist konfiguriert, der frühere `AccessDeniedException`-Blocker existiert nicht mehr. Aber die **Agent-Catalog-Tabelle ist leer** — es gibt keinen einzigen Agenten, dessen Berechtigung, Entitlement oder Ausführbarkeit geprüft werden könnte.

Damit ist §7 des Gates (Credential → APIProfile → Entitlement → Agent Catalog → Agent Status → Execution) **live nicht durchführbar**: das letzte Glied der Kette existiert nicht als Daten. Ich habe das nachgewiesen, statt einen Agenten zu erfinden (verboten) oder einen aus anderen Gates zu missbrauchen. `entitlements`-Tabelle: 0 Zeilen.

Die Worker-Entitlement-Recheck-Logik (`check_worker_entitlement`) **bleibt unverändert aktiv** — ich habe sie weder umgangen noch modifiziert. Ihre Tests (§13) sind grün.

## 9. Profile Selection

Über `/v1/introspection` mit Human-JWT (der produktiv erreichbare Selection-Pfad):

| Fall | Ergebnis |
|---|---|
| JWT **ohne** `X-Api-Profile` | **200**, `context=human`, `resolution.selectedBy=default` ✅ |
| JWT **mit** eigenem `X-Api-Profile` | **200**, `context=profile`, `selectedBy=explicit` ✅ |
| JWT mit **fremdem** `X-Api-Profile` | **404** `{"error":"Not found"}` ✅ |
| Genau ein `ACTIVE`-Default | ✅ Owner-Liste: nur `aprof_1148e3e280eb40e6` (`ACTIVE`) |
| Audit | `selection-resolved outcome=explicit hint=provided` ✅ |

Der Header muss zum Kontext passen — ein fremder `X-Api-Profile` wird nicht aufgelöst, sondern mit 404 abgelehnt. **Kein Profil-Crossing.**

## 10. Isolation

| Negativprüfung | Ergebnis |
|---|---|
| Owner liest fremde `credentialId` im eigenen Profil (`cred_ffffffffffffffff`) | **404** ✅ |
| Owner listet Credentials des **Forensikprofils** `aprof_352e4133…` (anderer Tenant) | **200** mit `items: []` — **0 Credentials sichtbar** ✅ |
| Owner listet Credentials des Forensikprofils (Audit) | `credential.viewed outcome=success count=0` ✅ |
| Admin (anderer Tenant) liest Forensikprofil | **403 Forbidden** ✅ |
| Admin stellt Credential für Owner-Profil aus | 201 — vertragsgemäß (Admin darf für Zieluser ausstellen) |

**Kein Datenleck über Tenant-Grenzen:** Der Owner sieht 0 Credentials des fremden Profils. Der 200 mit leerer Liste ist eine korrekte Negativantwort; entscheidend ist `count=0`, nicht der Statuscode.

## 11. Revocation & Rotation

### Rotation (durchgeführt)

| Schritt | Ergebnis |
|---|---|
| `POST /credentials/{cid}/rotate` **ohne** `expiresAt` | **400** `{"error":"Missing field: expiresAt"}` — korrekter Contract ✅ |
| `POST /credentials/{cid}/rotate` **mit** `expiresAt` | **201**, neues `credentialId` `cred_bb74e7c61af64d28`, `rotationOf=cred_7121af5531554e67` ✅ |
| Neues Secret geliefert | ✅ einmalig (47 Zeichen), nicht ausgegeben |
| Altes Credential A nach Rotation | `status=REVOKED`, `revokedAt`/`revokedBy` gesetzt ✅ |
| Neues Credential B nach Rotation | `status=ACTIVE`, `rotationOf` verlinkt ✅ |
| Audit | `credential.rotated outcome=success oldCredentialId=… newCredentialId=…` ✅ |

**A ist nach Rotation sofort ungültig** — serverseitig durch `status=REVOKED` belegt. Der Bearer-Test mit Secret A liefert 401, ist aber **kein Beleg** (JWT-Authorizer). Der Beleg ist der Status im Store.

### Revocation (durchgeführt)

| Schritt | Ergebnis |
|---|---|
| `POST /credentials/{cid}/revoke` | **200**, `status=REVOKED`, `revokedBy`/`revokedAt` gesetzt ✅ |
| `GET /credentials/{cid}` nachher | **`REVOKED`** — kein Cache liefert alten Zustand ✅ |
| Audit | `credential.revoked outcome=success credentialId=…` ✅ |

Das Gate verlangt, das Credential danach **erneut zu verwenden** und 403 zu erwarten. Das ist live nicht möglich (§6) — die 401 kam vom Authorizer, nicht von der Revocation-Prüfung. Ich dokumentiere das als **nicht live verifiziert**; der serverseitige Nachweis ist der `REVOKED`-Status im Store plus die 33 grünen Revocation-Tests.

### disable/enable

Der Verifikationsversuch schlug fehl, weil das rotierte Credential B revokiert und deshalb nicht mehr adressierbar war (404). `disable`/`enable` sind im Contract implementiert (`disable_credential`/`enable_credential`) und durch `test_enable_revoked_409`, `test_disabled_revoke`, `test_25_disabled_revoke` belegt. Ich habe **keine** weiteren Credentials zu diesem Zweck erzeugt.

## 12. Audit

Audit läuft über `_audit()` → CloudWatch `/aws/lambda/mays-ris-dev-agent` (keine Audit-Tabelle, keine `/audit/events`-Route — erneut verifiziert).

**40 Audit-Events** in diesem Gate. Credential-Actions:

| Action | Anzahl | Outcome |
|---|---|---|
| `credential.created` | **5** | `success` |
| `credential.rotated` | **1** | `success` |
| `credential.revoked` | **2** | `success` |
| `credential.viewed` | **9** | `success` |
| Credential-Authentication | **0** | — (kein produktiver Verifikationspfad, §6) |
| Credential-Failure | **0** | — (dito) |
| `credential.disabled`/`enabled` | **0** | — (nicht ausgeführt, §11) |

APIProfile-Actions:

| Action | Outcome | Details |
|---|---|---|
| `profile-create` | `success` | Owner, `tenant=` |
| `profile-transition` | `success` ×3 | `to=ACTIVE`, `to=DISABLED`, `to=ACTIVE` (Admin, mit `reason`) |
| `selection-resolved` | `explicit` | `hint=provided` |
| `profile-transition` (Cleanup) | `success` | `to=REVOKED` |

**Secret-Freiheit geprüft:** Kein Audit-Event enthält ein Secret, ein Passwort oder einen `Authorization`-Header. Events enthalten `ref`, `action`, `outcome`, `actor`, `credentialId`, `apiProfileId`, `tenantId`, `correlation` und `reason`. Audit-Schema **nicht verändert**.

Offene Lücke, die ich benenne: `credential.disabled`/`enabled` und abgelehnte Credential-Authentifizierungen erscheinen nicht als `outcome=denied`-Events, weil keine produktive Verifikation existiert und der `REVOKED`-/`Conflict`-Pfad vor `_audit()` wirft.

## 13. Tests

| Suite | Ergebnis |
|---|---|
| `test_credential_management.py` + `test_credential_verification.py` + `test_api_profiles.py` + `test_apiprofile_management_http.py` + `test_credential_management_http.py` + `test_offer_entitlement_grant.py` + `test_worker_entitlement_recheck.py` + `test_introspection_capability.py` | **335 passed**, 8 warnings (Deprecation in `executor.py:63`, vorbestehend) |
| `tests/verify_e2e.py` | `ALL COMPONENTS VERIFIED FUNCTIONAL`; GAPS: „AWS E2E: No AWS credentials for live testing" (Skript kennt die Live-Credentials nicht), „Agent-to-Agent integration: coverage gap" |

**Keine Tests wurden abgeschwächt, geändert oder gelöscht.** Keine neuen Fehler: 335/335 grün. Die beiden `verify_e2e.py`-GAPS sind **Baseline-Bekanntes**, keine neuen Fehler — und beide sind strukturell dieselben Lücken wie live: fehlender M2M-Einstiegspunkt und leere Agent-Catalog.

Diese 335 Tests decken die live nicht prüfbare Semantik ab, u. a. `test_43_revoked_403`, `test_46_profile_revoked_403`, `test_06_revoked_403`, `test_12_revoked_profile_403`, `test_20_revoked_profile_denied`, `test_11_revoked_404`, `test_revoked_between_checks_denied`, `test_12_revoked_before_retry_denied`, `test_27_revoked_terminal`.

## 14. Cleanup

| Schritt | Ergebnis |
|---|---|
| Credentials des Zielprofils | 6 gefunden → 4 noch `ACTIVE` revokiert → **alle 6 `REVOKED`** ✅ |
| Test-APIProfile `aprof_1148e3e280eb40e6` | **REVOKED** via Admin-Pfad ✅ |
| Test-APIProfile `aprof_1a719220e22f4ddd` (PENDING-Probe) | **REVOKED** via Admin-Pfad ✅ |
| Testuser `p17-owner-1791206079` | **deaktiviert** (`admin-disable-user`) ✅ |
| Testuser `p17-admin-1791206079` | **deaktiviert** ✅ |
| Secrets/Tokens | tmp-Verzeichnis (`chmod 700`), `state.json` (`chmod 600`), Treiberskript und alle JSON-Dateien **vernichtet**, bestätigt ✅ |
| **Keine Direct-DDB-Deletes** | ✅ ausschließlich Produktpfade |
| **Forensikprofil `aprof_352e4133…`** | **unverändert** — `REVOKED` wie nach Gate 05 ✅ |

### Endzustand der Tabellen

| Tabelle | vor Gate | nach Gate | Differenz |
|---|---|---|---|
| `api-profiles` | 7 | **9** | +2 (beide REVOKED, Tenant `p17-1791206079`) |
| `credentials` | 0 | **6** | +6 (alle REVOKED) |
| `entitlements` | 0 | **0** | — |

**Bestandsabgleich:** Alle sieben vorbestehenden Profile sind unverändert — `PENDING`, `ACTIVE`, `REVOKED`, `PENDING`, `ACTIVE`, `PENDING`, `PENDING`. Kein Bestandsprofil und keine Bestands-Credential wurde verändert. Die 9 Profile und 6 Credentials sind **kontrollierte, terminal gesperrte** Testdaten; ein produktiver Delete-Pfad existiert nicht (Gate 04/05), daher bleibt die Spur erhalten — genau wie beim Forensikprofil.

## 15. AWS Mutation

| Ressource | Wert | Vergleich | Match |
|---|---|---|---|
| Lambda `CodeSha256` | `ECemCxwAOv0fNo3OeAkxjpT3Eg+Xyl9LZB61h3R4VvQ=` | identisch (Gate 04/05) | ✅ |
| ESM | `Enabled`, Batch 5 | identisch | ✅ |
| Gateway-Routen | 27 | identisch | ✅ |
| Terraform `plan` | `No changes.` | identisch | ✅ |
| `mays-ris-lambda-policy` | unberührt | — | ✅ |
| ESM-Tags | unberührt | — | ✅ |

**Erlaubte Mutationen, die erfolgt sind:** 2 Cognito-Testuser (angelegt, dann deaktiviert), 1 UserProfile, 2 APIProfile, 6 Credentials — **alle über die Produkt-API**. Keine Terraform-, IAM-, Lambda-, Gateway-, Cognito-Konfigurations-, SQS-, ESM-, S3- oder Direct-DDB-Mutation. Keine M2M-Implementierung ergänzt, keine IAM-Härtung, kein Terraform-Drift bereinigt, keine bestehenden Contracts geändert.

## 16. Green-Kriterien

| # | Kriterium | Status |
|---|---|---|
| 1 | Human JWT funktioniert | ✅ `/me`, `/platform`, `/agents` 200 |
| 2 | APIProfile `PENDING → ACTIVE` | ✅ 201 + 200 |
| 3 | Credential Issue funktioniert | ✅ 201, Secret einmalig |
| 4 | **gültiges Bearer Credential funktioniert** | ❌ **401 — kein M2M-Einstiegspunkt (B3)** |
| 5 | ungültiges Credential wird abgelehnt | ⚠️ abgelehnt, aber vom JWT-Authorizer, nicht vom Contract |
| 6 | revoked/disabled/expired Credential abgelehnt | ⚠️ nur Testsuite, nicht live |
| 7 | Profil-Status serverseitig berücksichtigt | ✅ Issue 409 auf `PENDING`/`DISABLED` |
| 8 | **Agent Authorization funktioniert** | ❌ **live nicht prüfbar — Catalog leer (0 Agenten)** |
| 9 | Entitlement-Recheck funktioniert | ⚠️ Logik unverändert + 2 Tests grün, nicht live |
| 10 | Profile Selection funktioniert | ✅ default + explicit + fremd 404 |
| 11 | Credential/Profile Isolation | ✅ 404 / `count=0` / 403 |
| 12 | Credential Revocation funktioniert | ✅ Status `REVOKED`, kein Cache-Effekt |
| 13 | Audit vorhanden und secret-frei | ✅ 40 Events, kein Secret |
| 14 | Testdaten bereinigt/contained | ✅ 6 Credentials + 2 Profile `REVOKED`, 2 User deaktiviert |
| 15 | keine unerlaubte Infrastrukturmutation | ✅ |
| 16 | Git clean | ✅ |

**2 Kriterien nicht erfüllt (4 und 8), beide strukturell und nicht von mir verursacht.** Kein neuer Sicherheits- oder Autorisierungsfehler → **kein RED**. Aber ein E2E-Gate, das seinen Kern (M2M-Verifikation eines gültigen Bearer-Credentials) live nicht ausführen kann, ist **nicht GREEN**.

## 17. Blocker-Bewertung

| ID | Blocker | Status | Klasse |
|---|---|---|---|
| **B1** | Keine APIProfile-Management-Schnittstelle (P17-01) | ✅ **behoben** — 5 Routen produktiv, Live-GATE GREEN | — |
| **B2** | `dynamodb:Scan` auf `agent-catalog` fehlt (P17-01) | ✅ **behoben** — `Scan` in IAM vorhanden | — |
| **B3** | Kein M2M-Einstiegspunkt (P17-01) | 🔴 **besteht fort** | fehlende Erreichbarkeit, kein Sicherheitsfehler |
| **B4** | **Agent-Catalog leer (0 Agenten)** | 🔴 **neu identifiziert** | fehlende Testdaten |

B3 ist strukturell unverändert: `verify_api_credential` hat null produktive Aufrufer, `introspect_credential` liegt hinter einem immer `None`-Argument. Der Gateway hat **26 von 27 Routen** mit JWT-Authorizer; nur `GET /health` ist öffentlich. Ein opakes Credential kann strukturell keine JWT-Authorizer-Route passieren.

B4 ist neu: selbst mit funktionierendem M2M-Einstiegspunkt wäre §7 nicht durchführbar, weil die Kette an `agent-catalog` endet — die Tabelle enthält keine Zeile.

## 18. Empfehlung

Ich habe nichts implementiert — beide Lücken zu schließen erfordert neue Produktfunktion und ist ein eigenes Gate:

**B3 (M2M-Einstiegspunkt):** Erforderlich sind ein Gateway-Authorizer, der opake Credentials akzeptiert (oder eine eigene Route mit `AuthorizationType=NONE` plus Credential-Prüfung im Handler), die Verdrahtung von `bearer_credential` in `_handle_introspection`, ein produktiver Aufrufer für `verify_api_credential` und die Frage, wie `agent_id` als Operation-Target bestimmbar wird (`verify_api_credential` verlangt es ausdrücklich und rät nie). Das ist Architektur, kein Refactoring.

**B4 (Agent-Catalog befüllen):** Notwendig, bevor Agent-Authorization live testbar wird. Der Katalog ist eine Produkt-Datenquelle, deren Befüllung eine eigene fachliche Entscheidung ist.

Meine Empfehlung: **B3 als eigenes Architektur-Gate** mit B4 als Vorbedingung. Erst danach ist ein echtes P17-E2E-GREEN möglich.

## 19. Git Commit / Working Tree

Keine Code-, Terraform- oder Teständerung. Nur Reports committed.

## 20. Ausdrücklich nicht durchgeführt

- Kein neuer Endpoint, keine neue Route, keine neue Domain-Funktion (`keine M2M-Implementierung ergänzt`).
- Keine bestehenden Contracts geändert, keine neue Architektur.
- Keine IAM-Härtung, kein Terraform Apply/State/Import/Destroy, kein Terraform-Drift bereinigt.
- Keine Lambda-, Gateway-, Cognito-Konfigurations-, SQS-, ESM-, S3-Mutation.
- Kein Direct-DDB-Write, kein `DeleteItem`.
- `mays-ris-lambda-policy` und ESM-Tags unangetastet.
- Kein Agent erfunden, kein Agent aus anderen Gates zweckentfremdet.
- Keine bestehenden Produktivdaten verändert; `aprof_352e4133…` unverändert.
- Audit-Schema nicht verändert; keine Bearer-Credentials in Audit/Report.
- P20 nicht gestartet.
