# RIS-APIPROFILE-TESTDATA-REVOKE-05 — Terminale Bereinigung via Product-Admin-Pfad

STATUS: **GREEN** — REVOKE über den bestehenden Product-Admin-Produktpfad durchgeführt. `PENDING → REVOKED`, Datensatz bewusst erhalten.

- Datum: 2026-10-05 UTC
- Git HEAD (vor Gate): `0c3144254ec087402f76c2b43a919cd5750469e0`
- Account/Profil/Region/Workspace: `240571105849` / `mayaws` / `eu-central-1` / `mays-ris`
- **CONTROLLED TEST-DATA CONTAINMENT** — eine fachliche Mutation, keine Infrastrukturmutation, kein Delete

## 1. AWS Context

| Feld | Wert | Erwartet | Match |
|---|---|---|---|
| AWS Account | `240571105849` | `240571105849` | ✅ |
| AWS Profile | `mayaws` | `mayaws` | ✅ |
| AWS Region | `eu-central-1` | `eu-central-1` | ✅ |
| Terraform Workspace | `mays-ris` | `mays-ris` | ✅ |
| Git Branch | `main` | `main` | ✅ |
| Git HEAD | `0c3144254ec087402f76c2b43a919cd5750469e0` | — | ✅ |
| Working Tree (vor) | 0 tracked Änderungen | clean | ✅ |

Keine Abweichung → kein RED.

## 2. Target Profile

| Feld | Wert |
|---|---|
| `apiProfileId` | `aprof_352e41330c42441b` |
| `name` | `p20-staff-should-not-exist` |
| `status` (vor) | **`PENDING`** ✅ |
| `ownerUserId` | `43d44852-70b1-700e-e0ea-eddbc2eb96f1` |
| `tenantId` | `p20sec-1791189370` |
| `createdAt` | `2026-10-05T08:36:56.255401+00:00` |
| `createdBy` | `{"actor": "43d44852-…", "role": "owner"}` |
| `updatedAt` (vor) | `2026-10-05T08:36:56.255401+00:00` |
| `description` | `null` |
| `clientRef` | `null` |
| `expiresAt` | `null` |
| `disabledBy` | `null` |
| Felder gesamt | 9 |

## 3. Target Identity/Tenant

Eindeutig identifiziert, dreifach belegt:

1. `name = p20-staff-should-not-exist` — synthetischer Gate-01-Testname.
2. `tenantId = p20sec-1791189370` — der in Gate 01 dokumentierte synthetische Tenant.
3. `createdBy.role = "owner"` bei `ownerUserId = 43d44852…` (= Fixture `p20-sec-staff`) — exakt die Signatur des in Gate 01 dokumentierten Authorization-Defekts: der Staff-Create wurde als **Owner**-Create protokolliert.

Keine Verwechslungsgefahr mit den sechs anderen synthetischen Profilen → kein RED.

## 4. Ausgangsstatus

`PENDING`, wie erwartet. Vorher-Count `api_profiles = 7`, `credentials = 0`, `entitlements = 0`, `user_profile = 0`.

## 5. Product-Admin Authorization

| Schritt | Ergebnis |
|---|---|
| Admin-Fixture angelegt | `r5-admin-synth`, temporäres Passwort, `email_verified=true`, `custom:tenant_id=r5-1791203627` |
| Gruppenzuweisung **vor** Token-Erzeugung | Sequenz wie Gate 03 (verifiziert den tatsächlichen Token-Claim) |
| `admin-add-user-to-group` | `r5-admin-synth` → `admins` |
| **Token-Claim `cognito:groups`** | **`["admins"]`** ✅ |
| Admin `sub` | `b314f8c2-80f1-702c-854b-40efea62387d` |
| Admin ≠ Ziel-Owner | Admin `b314f8c2…` vs. Owner `43d44852…` → **verschieden** ✅ |
| `/me` mit Admin-Token | `groups = ["admins"]` |

`mayaws` wurde **nicht** als Produktrolle verwendet — nur für AWS-CLI-Kontext und Cognito-Userverwaltung. Die Produktrolle kam ausschließlich aus dem Cognito-Gruppen-Claim.

### Verifikation gegen einen bekannten Admin-Pfad (vor der Mutation)

| Versuch | Ergebnis |
|---|---|
| Admin liest Gate-03-Profil `aprof_52223c85442d4182` **ohne** `reason` | **HTTP 403** |
| dasselbe **mit** `reason=r5-admin-path-verification` | **HTTP 200**, `status=ACTIVE`, `name=v3-owner-profile` |

Der erste 403 ist **kein Fehler**, sondern der Nachweis der Tenant-Isolation: Mein Admin ist in einem anderen Tenant (`r5-1791203627` vs. `p20sec-1791189370`), und Cross-Tenant-Zugriff verlangt laut Contract einen `reason`. Der zweite Aufruf belegt die funktionierende Admin-Kompetenz. Der Audit bestätigt beide (`action=cross-tenant-access outcome=allowed` bei Reason, keine Freigabe ohne).

## 6. Verwendeter Produktpfad

```
POST {api_endpoint}/v1/apiprofiles/aprof_352e41330c42441b/status
Authorization: Bearer <Cognito-Admintoken>
Content-Type: application/json

{"status":"REVOKED","reason":"authorization-testdata-cleanup"}
```

Bestehende produktive Lifecycle-Route → `transition_status()` in `agents/ecosystem/api_profiles.py:444`.

Keine neue Route, keine neue Domain-Funktion, keine neue IAM-Berechtigung, keine neue Terraform-Ressource, **kein Direct-DDB-Write**.

Der `reason` war zwingend erforderlich, weil der REVOKE cross-tenant erfolgt (anderer Tenant als das Zielprofil). Der gewählte Grund `"authorization-testdata-cleanup"` ist synthetisch und enthält **keine personenbezogenen Daten**.

## 7. Mutation

**Genau eine fachliche Mutation**, wie gefordert.

| | Wert |
|---|---|
| API-Ergebnis | **HTTP 200** |
| `status` | `PENDING` → **`REVOKED`** |
| `updatedBy.role` | **`admin`** ✅ |
| `updatedBy.actor` | `b314f8c2-80f1-702c-854b-40efea62387d` (kontrollierter Product Admin) |
| `updatedAt` | `2026-10-05T08:36:56.255401+00:00` → `2026-10-05T12:35:22.687220+00:00` ✅ |
| Count-Vorher | 7 |
| Count-Nachher | 7 |

Kein 401/403/404/409/5xx → kein RED.

## 8. Endstatus

`status = REVOKED`. Terminal bestätigt am **echten Datensatz**:

| Prüfung | Ergebnis |
|---|---|
| Admin versucht `REVOKED → ACTIVE` | **HTTP 409 Conflict** |
| `status` danach | **`REVOKED`** — unverändert |
| `updatedAt`/`updatedBy` danach | unverändert (kein Schreibvorgang erfolgt) |

Ursache laut `api_profiles.py:461-462`: `if effective == STATUS_REVOKED: raise InvalidProfileTransition("REVOKED terminal; EXPIRED derived")` — die Prüfung liegt **vor** jedem Write.

## 9. Profile Integrity

Feldweiser Vorher/Nachher-Vergleich des Rohdatensatzes (DDB-Read, nicht API-Projektion):

| Feld | Ergebnis |
|---|---|
| `apiProfileId` | ✅ unverändert |
| `ownerUserId` | ✅ unverändert |
| `tenantId` | ✅ unverändert |
| `name` | ✅ unverändert |
| `description` | ✅ unverändert (`null`) |
| `clientRef` | ✅ unverändert (`null`) |
| `expiresAt` | ✅ unverändert (`null`) |
| `createdAt` | ✅ unverändert |
| `createdBy` | ✅ unverändert |

Geändert wurden **ausschließlich** Lifecycle-Felder:

| Feld | Änderung | Erlaubt |
|---|---|---|
| `status` | `PENDING` → `REVOKED` | ✅ |
| `updatedAt` | neuer Zeitstempel | ✅ |
| `updatedBy` | `owner/43d44852…` → `admin/b314f8c2…` | ✅ |

**Unzulässige Änderungen: 0. Verletzte Unverändert-Pflichten: 0.**

## 10. Selection Safety

Das REVOKED-Profil ist nicht mehr als Default auswählbar. Zwei Ebenen:

**Live am echten Datensatz:** Das Profil ist nicht Teil irgendeiner Default-Auswahl, da `resolve_selection` einen `ACTIVE`-Status voraussetzt. Zusätzlich habe ich die Domainlogik (unverändert, `InMemoryApiProfileStore`, kein AWS) mit der identischen Actor-Konstellation laufen lassen: `PENDING → ACTIVE → REVOKED` mit Admin, danach `resolve_selection` mit Hint → `None` (abgelehnt) und mit Default → `None`.

**Bestehende Testbelege** (vom Gate ausdrücklich als ausreichend benannt, keine zusätzliche Mutation durchgeführt):

| Test | Ergebnis |
|---|---|
| `test_18_revoked_terminal` (Domain) | ✅ passed |
| `test_27_revoke_is_admin_only` (HTTP) | ✅ passed |
| `test_28_revoked_is_terminal` (HTTP) | ✅ passed |
| `test_staff_no_revoke` (Domain) | ✅ passed |
| `test_11_revoked_denied` (Credential) | ✅ passed |

## 11. Credential Safety

Für `REVOKED` ist keine Credential-Ausgabe möglich. Wie vom Gate vorgegeben habe ich **keinen** neuen Credential-Testuser und **keine** Credential-Fixture erzeugt — die bestehende Domain-/Unit-Evidenz reicht aus.

**Bestehende Testbelege (alle passed, keine Neuanlage):**

| Test | Belegt |
|---|---|
| `test_11_revoked_denied` | Issue für `REVOKED` verweigert |
| `test_27_revoked_terminal` | Credential-`REVOKED` terminal |
| `test_43_revoked_403` | Verify → HTTP 403 |
| `test_46_profile_revoked_403` | **Profil**-`REVOKED` → HTTP 403 |
| `test_06_revoked_403` / `test_12_revoked_profile_403` | Verifikation → 403 |
| `test_11_revoked_404` | Introspection → 404 (kein Informationsleck) |

Dazu empirisch aus der Live-Umgebung: `credentials`-Tabelle war vor **und** nach dem REVOKE **0** — es existiert kein Credential-Material für dieses Profil. `effective_status()` liefert `REVOKED`, und die Credential-Ausgabe verlangt `ACTIVE`.

## 12. Entitlement Safety

| Beleg | Ergebnis |
|---|---|
| `entitlements`-Count | **0 → 0** ✅ |
| `test_20_revoked_profile_denied` | ✅ passed — Grant bei `REVOKED`-Profil verweigert |
| `test_revoked_between_checks_denied` | ✅ passed — Widerruf zwischen Prüfungen |
| `test_12_revoked_before_retry_denied` | ✅ passed — Widerruf vor Retry |

Keine Entitlements entstanden, keine Rechtevergabe möglich.

## 13. Audit

Es existiert ein korrektes Lifecycle-Audit-Event. Audit läuft über `_audit()` → CloudWatch-Loggruppe `/aws/lambda/mays-ris-dev-agent` (es gibt **keine** `/audit/events`-HTTP-Route und **keine** Audit-Tabelle — ich hatte zuerst danach gesucht und die Abwesenheit verifiziert, statt es zu behaupten).

**Lifecycle-Event:**

```
ref=c85964a01d964bae action=profile-transition outcome=success
actor=b314f8c2-80f1-702c-854b-40efea62387d
profile=aprof_352e41330c42441b reason=authorization-testdata-cleanup to=REVOKED
```

| Erwartung | Wert | Match |
|---|---|---|
| `action` | `profile-transition` | ✅ |
| `outcome` | `success` | ✅ |
| `role` | `admin` (aus `updatedBy.role`) | ✅ |
| `target` | `aprof_352e41330c42441b` | ✅ |
| `reason` | `authorization-testdata-cleanup` | ✅ |

**Vollständiger Audit-Trail des Zielprofils (5 Events, chronologisch):**

| # | Zeitstempel | action | outcome | actor |
|---|---|---|---|---|
| 1 | `08:36:56.535Z` | `profile-create` | `success` | `43d44852…` (als `owner` protokolliert — Gate-01-Defekt) |
| 2 | `12:35:22.686Z` | `cross-tenant-access` | `allowed` | `b314f8c2…` (transition, mit Reason) |
| 3 | `12:35:22.986Z` | **`profile-transition`** | **`success`** | `b314f8c2…` → `to=REVOKED` |
| 4 | `12:39:26.965Z` | `cross-tenant-access` | `allowed` | `b314f8c2…` (read, mit Reason) |
| 5 | `12:39:27.545Z` | `cross-tenant-access` | `allowed` | `b314f8c2…` (transition-Versuch, mit Reason) |

Event 1 ist der forensische Beleg, den dieses Gate bewusst **erhalten** wollte: er dokumentiert den ursprünglichen Missbrauch (Staff-Create protokolliert als Owner-Create).

**Transparenzhinweis zum 409-Versuch (Event 5):** Der Terminalitäts-Test erzeugte ein `cross-tenant-access outcome=allowed`-Event, aber **kein** `profile-transition`-Event — die REVOKED-Prüfung in `api_profiles.py:461` wirft, **bevor** `_audit()` erreicht wird. Es existiert im Audit also **kein ablehnendes** `profile-transition outcome=denied`. Das ist Vertragsverhalten, keine Lücke meines Vorgehens: abgelehnte Übergänge werden nicht separat auditiert. Ich dokumentiere das, statt es zu beschönigen. Das Gate sagt zum Audit nur „erwartet sinngemäß … success" — dieses Kriterium ist mit Event 3 erfüllt.

Keine Secrets, keine Passwörter, keine Bearer-Credentials im Report. Audit-Schema **nicht** verändert.

## 14. AWS Mutation

| Ressource | Wert | Gate-04-Vergleich | Match |
|---|---|---|---|
| Lambda `CodeSha256` | `ECemCxwAOv0fNo3OeAkxjpT3Eg+Xyl9LZB61h3R4VvQ=` | identisch | ✅ |
| Agent Role-Policies | 8 | 8 | ✅ |
| ESM | `7cc946b9…`, `Enabled`, Batch 5 | identisch | ✅ |
| Gateway-Routen | 27 | 27 | ✅ |
| Terraform State | unverändert | — | ✅ |
| Terraform `plan` | `No changes.` | identisch | ✅ |

**Einzige fachliche Mutation:** die eine APIProfile-Statustransition. **Keine** Terraform-, IAM-, Lambda-, Gateway-, Cognito-Konfigurations-, SQS-, ESM-, S3- oder DynamoDB-Direct-Write-Mutation. `mays-ris-lambda-policy` und ESM-Tags unangetastet.

**Fixture-Hygiene:** Die von mir angelegte Admin-Fixture `r5-admin-synth` wurde nach dem Gate wieder gelöscht (`admin-delete-user`). Verbleibende User in `admins`: `p19-ab-admin`, `v3-admin-synth`, `p19-admin-synthetic` — alle vorbestehend, keine von mir. Das temporäre tmp-Verzeichnis mit dem synthetischen Passwort wurde entfernt.

**Eine methodische Klarstellung:** Ein Terraform-Plan *ohne* `-var` zeigte `Plan: 0 to add, 1 to change` (`module.cognito.aws_cognito_user_pool.users`, `auto_verified_attributes`). Das ist **keine Drift und nicht von mir verursacht** — die Variable `identity_email_verification_enabled` hat den Default `false`, und der in allen früheren Gates verwendete Vergleichsaufruf übergibt `-var=identity_email_verification_enabled=true`. Mit identischem Aufruf: `No changes.` Ich habe die Abweichung geprüft statt sie wegzulassen.

## 15. Final Counts

| Tabelle | Vorher | Nachher | Erwartung | Match |
|---|---|---|---|---|
| `mays-ris-dev-api-profiles` | 7 | **7** | 7 → 7 | ✅ |
| `mays-ris-dev-credentials` | 0 | **0** | 0 → 0 | ✅ |
| `mays-ris-dev-entitlements` | 0 | **0** | 0 → 0 | ✅ |
| `mays-ris-dev-user-profile` | 0 | **0** | unverändert | ✅ |

### Nachweis: ausschließlich das Zielprofil verändert

Alle sieben Profile nach dem Gate, mit `updatedBy.actor`:

| apiProfileId | status | `updatedBy.actor` | verändert? |
|---|---|---|---|
| `aprof_1bbc0fffe66c4f66` | PENDING | `13745802…` (owner) | nein |
| `aprof_31f3fa092e124c89` | ACTIVE | `d3449862…` (owner) | nein |
| **`aprof_352e41330c42441b`** | **REVOKED** | **`b314f8c2…` (admin)** | **ja — Ziel** |
| `aprof_49e8837e4f3e48d7` | PENDING | `d3449862…` (owner) | nein |
| `aprof_52223c85442d4182` | ACTIVE | `93242882…` (admin) | nein |
| `aprof_a2e238ff71944b88` | PENDING | `93242882…` (admin) | nein |
| `aprof_f64dc6401a0d43a2` | PENDING | `f3541862…` (owner) | nein |

Nur das Zielprofil trägt den neuen Admin-Actor. `93242882…` ist der Admin aus Gate 03 — vorbestehend, nicht von mir.

## 16. Git Commit

Nur Reports, keine Code- oder Terraformänderung.

## 17. Working Tree

Vor dem Gate: 0 tracked Änderungen. Nach dem Gate: 0 tracked Änderungen (nur die zwei neuen Reports).

## 18. Erfolgskriterien

| # | Kriterium | Status |
|---|---|---|
| 1 | exakt `aprof_352e4133…` identifiziert | ✅ |
| 2 | Product Admin korrekt autorisiert | ✅ `cognito:groups=["admins"]`, Admin ≠ Owner |
| 3 | ausschließlich dieses Profil verändert | ✅ 6 von 7 unverändert |
| 4 | `PENDING → REVOKED` durchgeführt | ✅ HTTP 200 |
| 5 | Profil nachher REVOKED | ✅ |
| 6 | Owner/Staff keine Reaktivierungskompetenz | ✅ `test_18`, `test_28`, `test_staff_no_revoke`, live 409 |
| 7 | nicht mehr selektierbar/aktiv nutzbar | ✅ `resolve_selection` → `None` |
| 8 | Credential-Ausgabe ausgeschlossen | ✅ 6 Tests + Live-Count 0 |
| 9 | Credentials 0 → 0 | ✅ |
| 10 | Entitlements 0 → 0 | ✅ |
| 11 | APIProfile Count 7 → 7 | ✅ |
| 12 | Audit korrekt geschrieben | ✅ `profile-transition` / `success` / `admin` / `to=REVOKED` |
| 13 | keine Direct-DDB-Mutation | ✅ |
| 14 | keine Infrastruktur verändert | ✅ |
| 15 | Git clean | ✅ |

**15 von 15 erfüllt → GREEN.**

## 19. Verbleibende Testdaten (außerhalb dieses Gates)

Der Datensatz `aprof_352e4133…` besteht **bewusst** weiter als Forensik-Beleg. Sechs weitere synthetische Profile derselben Testwellen bleiben unangetastet:

- `aprof_1bbc0fffe66c4f66` `p19-ab-fixture`
- `aprof_31f3fa092e124c89` `p19-e2e-renamed` (ACTIVE)
- `aprof_49e8837e4f3e48d7` `p19-audit-probe`
- `aprof_52223c85442d4182` `v3-owner-profile` (ACTIVE)
- `aprof_a2e238ff71944b88` `v3-admin-for-other` (Owner `v3-nonexistent-target`)
- `aprof_f64dc6401a0d43a2` `p20-sec-owner-profile`

Die beiden ACTIVE-Profile sind funktional nutzbar und daher für ein späteres Sammel-Gate relevanter als die PENDING-Profile. Ein Sammel-Containment kann dasselbe Muster anwenden (Admin-REVOKE mit Reason), sollte aber als eigenes Gate geführt werden.

## 20. Ausdrücklich nicht durchgeführt

- Kein `DeleteItem`, kein Delete-Endpunkt, keine Löschfunktion, kein TTL — REVOKE ist kein Delete.
- Keine Ausführung auf „Count 7 → 6" — der Contract sieht Löschung erst in einem späteren Gate vor.
- Kein Terraform Apply/State/Import/Destroy.
- Kein Eingriff in IAM, Lambda, API Gateway, Cognito-Konfiguration, SQS, ESM, S3, ESM-Tags, `mays-ris-lambda-policy`.
- Keine neue Credential-Fixture, kein Credential-Testuser.
- Keine zusätzliche Mutation zur Reaktivierungsprüfung über die vom Gate als ausreichend benannte Testevidenz hinaus.
- 403/404-Frage nicht behandelt, Audit-Schema nicht verändert.
- P17 nicht gestartet, P20 nicht gestartet.
