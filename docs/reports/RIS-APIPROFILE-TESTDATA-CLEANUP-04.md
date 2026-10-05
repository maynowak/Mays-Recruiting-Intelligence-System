# RIS-APIPROFILE-TESTDATA-CLEANUP-04 — APIProfile Testdaten-Cleanup

STATUS: **YELLOW / HOLD** — **Kein Delete-Produktpfad vorhanden.** Das Zielprofil konnte über den autorisierten Produktpfad **nicht** entfernt werden. **Keine Mutation durchgeführt.**

- Datum: 2026-10-05 UTC
- Git HEAD: `ca768f9`
- Account/Profil/Region/Workspace: `240571105849` / `mayaws` / `eu-central-1` / `mays-ris`
- **CONTROLLED CLEANUP ONLY** — keine Infrastrukturmutation

## 1. AWS-/Git-Kontext

| Feld | Wert | Erwartung | Match |
|---|---|---|---|
| AWS Profile | `mayaws` | `mayaws` | ✅ |
| Account | `240571105849` | `240571105849` | ✅ |
| Region | `eu-central-1` | `eu-central-1` | ✅ |
| Workspace | `mays-ris` | `mays-ris` | ✅ |
| Branch | `main` | `main` | ✅ |
| HEAD | `ca768f97bee84be5a477c13777bb7bf65bcd5273` | — | ✅ |
| Working Tree | 0 tracked Änderungen | clean | ✅ |

Keine Abweichung.

## 2. Ausgangszustand

| Tabelle | Count | Erwartung Gate 03 | Match |
|---|---|---|---|
| `mays-ris-dev-api-profiles` | **7** | 7 | ✅ |
| `mays-ris-dev-credentials` | **0** | 0 | ✅ |
| `mays-ris-dev-entitlements` | **0** | 0 | ✅ |
| `mays-ris-dev-user-profile` | **0** | — | — |

Vollständige Inventur der 7 Profile (als Vorher-Baseline für spätere Gates festgehalten):

| apiProfileId | status | name | owner (gekürzt) |
|---|---|---|---|
| `aprof_1bbc0fffe66c4f66` | PENDING | `p19-ab-fixture` | `13745802-…` |
| `aprof_31f3fa092e124c89` | ACTIVE | `p19-e2e-renamed` | `d3449862-…` |
| **`aprof_352e41330c42441b`** | **PENDING** | **`p20-staff-should-not-exist`** | `43d44852-…` |
| `aprof_49e8837e4f3e48d7` | PENDING | `p19-audit-probe` | `d3449862-…` |
| `aprof_52223c85442d4182` | ACTIVE | `v3-owner-profile` | `4374d8a2-…` |
| `aprof_a2e238ff71944b88` | PENDING | `v3-admin-for-other` | `v3-nonexistent-target` |
| `aprof_f64dc6401a0d43a2` | PENDING | `p20-sec-owner-profile` | `f3541862-…` |

## 3. Zielprofil-Identifikation — eindeutig

| Feld | Wert |
|---|---|
| `apiProfileId` | `aprof_352e41330c42441b` |
| `name` | `p20-staff-should-not-exist` |
| `status` | `PENDING` |
| `ownerUserId` | `43d44852-70b1-700e-e0ea-eddbc2eb96f1` (= Fixture `p20-sec-staff`) |
| `tenantId` | `p20sec-1791189370` (= synthetischer Tenant aus Gate 01) |
| `createdAt` | `2026-10-05T08:36:56.255401+00:00` |
| `createdBy` | `{"actor": "43d44852-…", "role": "owner"}` |
| `clientRef` / `expiresAt` | `null` / `null` |
| Feldanzahl | 9 |

Identifikation ist eindeutig: Name, synthetischer Tenant, synthetische Owner-ID und der Zeitstempel aus Gate 01 passen zusammen. `createdBy.role = "owner"` ist zugleich die Signatur des in Gate 01 dokumentierten Audit-Defekts (der Staff-Create wurde als Owner-Create protokolliert). **Keine Verwechslungsgefahr.**

## 4. Cleanup-Pfad — nicht vorhanden

Ich habe den Produktpfad **systematisch in vier Ebenen** geprüft. Es gibt **keinen** autorisierten Delete:

| Ebene | Befund |
|---|---|
| **Gateway-Routen** | 5 Routen für `/v1/apiprofiles`: `POST`/`GET` auf der Collection, `GET`/`PATCH` auf `{id}`, `POST` auf `{id}/status`. **Keine `DELETE`-Route.** |
| **Domain** (`agents/ecosystem/api_profiles.py`) | 18 Funktionen, davon **0** mit `delete` im Namen: `_utcnow_iso`, `_parse_time`, `_audit`, `_is_admin`, `_is_staff`, `effective_status`, `_public`, `_check_tenant`, `_actor_label`, `create_profile`, `get_profile`, `list_profiles`, `update_profile`, `set_client_ref`, `set_expires_at`, `transition_status`, `renew_profile`, `resolve_selection`, `credential_profile_match` |
| **Handler** | `DELETE`-Dispatch existiert nur für `/me/documents/*` (`:349`) und `/me/jobsearches/*` (`:376`). `_aprof_ids` akzeptiert ausschließlich die Segmentformen 2, 3 und 4 mit `status` als einziger Aktion — keine Delete-Form. |
| **Tabellen-Contract** (`api_profiles.py:23-24`) | `NO TTL (expired profiles stay EXPIRED records for audit;` **`deletion only via explicit admin cleanup, later gate`)** |

Der Vertrag benennt die Löschung ausdrücklich als **„later gate"** — sie ist damit nicht implementiert, sondern bewusst zurückgestellt. Eine Suche nach einer Cleanup-Schnittstelle (`admin cleanup`, `cleanup profile`, `hard delete`) im Modul, im API-Terraform, im Handler und in `docs/api/API-STANDARD.md` findet **keinen** Treffer außer genau diesem Kommentar.

### Warum REVOKE/DISABLE kein Ersatz sind

Das Gate untersagt ausdrücklich, einen bestehenden REVOKE-/DISABLE-Pfad als Delete zu interpretieren. Semantisch bestätigt:

- `_ALLOWED[REVOKED] = set()` → terminal, **Profil-Datensatz bleibt in DynamoDB**.
- `_ALLOWED[DISABLED] = {ACTIVE, REVOKED}` → reaktivierbar.
- `effective_status()` leitet nur `EXPIRED` ab, kein Löschen.

Ein REVOKE würde das Profil also **nicht entfernen** und das Erfolgskriterium „Count 7 → 6" nicht erfüllen.

## 5. Ergebnis gemäß Gate-Vorgabe

> „Falls kein echter Delete-Produktpfad existiert: YELLOW / HOLD. Dann NICHT direkt löschen."

**YELLOW / HOLD. Keine Mutation.** Es wurde ausdrücklich **nicht**:
- per Direct-DynamoDB gelöscht (verboten),
- `REVOKE`/`DISABLE` als Delete missverstanden,
- eine DELETE-Route oder Löschfunktion implementiert (verboten),
- eine Cognito-Fixture erzeugt (nicht nötig, da keine Mutation stattfindet — vom Gate so gefordert).

## 6. Restrisiko-Abschätzung des verbleibenden Profils

Das Profil ist funktional **inert**. Lokal gegen die echte Domainlogik verifiziert:

| Prüfung | Ergebnis |
|---|---|
| `effective_status()` | `PENDING` |
| `resolve_selection(hint=…)` | `None` (abgelehnt), Audit `action=selection-denied outcome=neutral` |
| `resolve_selection(default)` | `None` (kein ACTIVE-Default), Audit `action=selection-none outcome=neutral` |
| Credential-Ausgabe | setzt `ACTIVE` voraus → mit `PENDING` nicht möglich |
| Credentials / Entitlements | beide Tabelle **0** |

Das Profil gewährt **keinen** Zugriff, ist nicht auswählbar und trägt keine Credentials. Es ist ein reiner Audit-Beleg.

## 7. Nachweis der Nicht-Mutation

| Prüfung | Wert | Erwartung |
|---|---|---|
| Zielprofil | weiterhin vorhanden, `status=PENDING` | unverändert |
| `api_profiles` Count | **7** | 7 (nicht 6 — Cleanup nicht möglich) |
| `credentials` | 0 | 0 |
| `entitlements` | 0 | 0 |
| `user_profile` | 0 | 0 |
| Lambda `CodeSha256` | `ECemCxwAOv0fNo3OeAkxjpT3Eg+Xyl9LZB61h3R4VvQ=` | unverändert |
| Agent Role-Policies | 8 | unverändert |
| ESM | `7cc946b9…`, `Enabled`, Batch 5 | unverändert |
| Terraform `plan -lock=false` | `No changes.` | kein Drift |
| Cognito-Fixtures | **keine erzeugt** | Gate-Vorgabe |

Es wurde **kein** Audit-Eintrag für einen Cleanup erzeugt — es gab keine Aktion.

## 8. Empfehlung

Ich habe **nicht** eigenmächtig eine Löschung implementiert. Zwei Optionen, beide erfordern ein eigenes Gate:

**Option 1 — REVOKE als bewusste Bereinigung (kein Löschen).**
Der Admin-Pfad funktioniert. `POST /v1/apiprofiles/{id}/status {"status":"REVOKED"}` setzt das Profil terminal auf `REVOKED`, erzeugt einen korrekten `profile-transition`-Audit-Eintrag mit `role=admin` und macht das Profil explizit unbrauchbar. Der Datensatz bleibt als Audit-Beleg erhalten — genau das, was der Tabellen-Contract fordert. **Das erfüllt das Sicherheitsziel, aber nicht „Count 7 → 6".**

**Option 2 — Löschpfad als eigenes Feature-Gate.**
Fachlich sauberer, weil der Contract die Löschung explizit vorsieht: Store-Methode, Domain-Funktion mit Admin-Autorisierung + Audit, HTTP-Route, Tests, Terraform-DynamoDB-Permission (`DeleteItem`) prüfen. Das ist **neue Funktionalität** und in diesem Gate ausdrücklich ausgeschlossen.

Ich empfehle **Option 1** als Sofortmaßnahme (ein einziger Audit-gerechter API-Aufruf, kein Code), und Option 2 als späteres Gate — **entschieden wird das nicht von mir.**

## 9. Erfolgskriterien

| # | Kriterium | Status |
|---|---|---|
| 1 | Exakt `aprof_352e4133…` entfernt | ❌ **nicht möglich** (kein Delete-Pfad) |
| 2 | Count 7 → 6 | ❌ bleibt 7 |
| 3 | Credentials 0 → 0 | ✅ |
| 4 | Entitlements 0 → 0 | ✅ |
| 5 | Keine anderen Profile verändert | ✅ |
| 6 | Kein UserProfile verändert | ✅ |
| 7 | Keine Produktivdaten verändert | ✅ |
| 8 | Keine Infrastruktur verändert | ✅ |
| 9 | Keine Secrets im Report | ✅ |
| 10 | Working Tree clean | ✅ |

2 von 10 Kriterien nicht erfüllt — **ausschließlich** weil der autorisierte Produktpfad die Löschung nicht unterstützt. Das ist exakt der in der Gate-Vorgabe beschriebene **YELLOW**-Fall.

## 10. Offene Punkte

1. **`aprof_352e4133…` bleibt stehen** (inert, kein Zugriffsrisiko). Entscheidung Option 1 vs. Option 2 liegt beim Auftraggeber.
2. **Weitere 6 synthetische Profile** derselben Testwellen (`p19-*`, `p20-*`, `v3-*`) — in diesem Gate ausdrücklich nicht im Scope. Ein späteres Gate kann sie gesammelt behandeln; `aprof_a2e238ff71944b88` hat mit `v3-nonexistent-target` einen Nicht-UUID-Owner.
3. **`aprof_a2e238ff71944b88`** entstand aus dem Gate-03-`targetOwner`-Test mit einem erfundenen Ziel-User — der Admin-Pfad hat einen Profil-Satz für einen nicht existierenden User angelegt. Vertragsgemäß (Admin darf für Zieluser anlegen), aber ein Hinweis für spätere Cleanup-Logik.
4. **403/404-Frage** und **Audit-Schema** bleiben unberührt, wie angewiesen.
5. `mays-ris-lambda-policy` und ESM-Tags wurden **nicht** angefasst.
