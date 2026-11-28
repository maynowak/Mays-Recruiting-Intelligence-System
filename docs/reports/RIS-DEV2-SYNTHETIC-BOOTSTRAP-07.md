# RIS-DEV2-SYNTHETIC-BOOTSTRAP-07

**Datum:** 2026-11-25
**Branch / Baseline:** `feature/ris-analysis-integration-07` / `c7944689acd19d4e175577a63b7c7579e7b7e534`
**AWS-Konto / Region / Installation:** `262370457690` / `eu-central-1` / `ris-dev2`
**MO-Pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`
**Status:** **SYNTHETIC BOOTSTRAP — LIVE VERIFIED (Phase B only)**

## 1. Preflight

| Prüfung | Ergebnis |
| --- | --- |
| STS-Konto / Region | `262370457690` / `eu-central-1` |
| Base-Apply-06 live | `analysis-agent` ACTIVE; Binding-Route vorhanden (JWT, Authorizer `0iqec5`); IAM nur `dynamodb:GetItem` |
| Synthetic-Modus | `ANALYSIS_SYNTHETIC_MODE=false` |
| Baseline-Zähler | 0 User, 2 Clients, 4 API-Profile, 0 Offers, 2 Entitlements, 0 Partner-Apps |

## 2. Provisionierung (genau die freigegebenen Schritte)

| Schritt | Ergebnis |
| --- | --- |
| 1. Cognito-User | `ris-dev2-canary-07`, Pool `eu-central-1_OYN9QiHc5`, Status `CONFIRMED`, `Enabled=true`; `custom:tenant_id=ris-dev2-canary-07`; Einladungsmail unterdrückt (`SUPPRESS`); E-Mail `…@example.invalid`, `email_verified=true` |
| — `sub` | `a39458b2-7001-701a-c509-47c424d653e5` |
| 2. API-Profil | `aprof_cdbd3b6f803744bf`, `ACTIVE`, Owner = `sub`, Tenant = `ris-dev2-canary-07`, Name `ris-dev2-canary-07` |
| 3. App-Client | `5ianq5p5ahofqnej6dpu3no7ip`, Name `ris-dev2-canary-07-partner`, kein Secret, keine OAuth-/Auth-Flows (inerte Registry-Identität) |
| 4. Partner-Anwendung | `ris-dev2-canary-07`, `ACTIVE`, Client `5ian…`, Profil `aprof_cdbd…`, Tenant `ris-dev2-canary-07` (plus erwartete `CLIENT#…`-Reservierung) |
| 5. Profilbindung | `partnerApplicationId=ris-dev2-canary-07`, `issuer=https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_OYN9QiHc5`, admin-auditiert |
| 6. Offer | `off_4b4f0843057c4a91`, `ACTIVE`, `agentIds=["analysis-agent"]` |
| — Entitlement | `ent_bf0c8123844e47bb`, USER-Scope (kein `apiProfileId`), Agent `analysis-agent`, User `sub`, Tenant `ris-dev2-canary-07`, Ablauf `1795714828` = **2026-11-26T17:40:28Z** |

## 3. Read-only Abnahme

| Prüfung | Ergebnis |
| --- | --- |
| User/Tenant/Issuer | `CONFIRMED`, `sub` und Tenant stimmen mit Profil und Bindung überein; Issuer = Pool-Issuer |
| Reguläre JWT-Authentifizierung | `initiate-auth` (USER_PASSWORD_AUTH) mit dem Human-Client `5jg…`: ID-Token mit `token_use=id`, `aud=5jg…`, korrekter `iss`, `sub`, Tenant. **Token/Passwort nicht gespeichert, nicht geloggt.** |
| Profil | `ACTIVE`, Owner = tatsächliche `sub`, Tenant korrekt, Bindung gesetzt |
| Partner-Anwendung | `ACTIVE`, richtiger Client, Tenant und Profil |
| Entitlement | vorhanden, gültig, zeitlich begrenzt (24 h), kein Profil-Scope |
| Zähler nachher | 1 User, 3 Clients, 5 API-Profile (1 ACTIVE neu), 1 Offer, 3 Entitlements, 1 Partner-Application (+Reservierung) |
| Bestehende Clients | Human- und M2M-Client unverändert; neue Clients nur der dedizierte Partner-Client |
| Pool/Gruppen | Pool-Konfiguration und 7 Gruppen unverändert |
| Synthetic-Modus | weiterhin **false**, alle Identitäts-Env-Werte leer |
| Base-Apply-Ressourcen | Katalog ACTIVE, Route JWT, IAM `GetItem` only; State-Serial 71 und S3-Version unverändert |

## 4. Notwendige Abweichung (lokal, kein AWS-Scope)

Die autorisierte CLI verweigerte unter Windows jede Authorization-Datei, weil
`st_mode` dort immer `0666` meldet (ACLs sind nicht abbildbar). Behoben in
`tools/ris_admin/credentials.py` analog zur bereits vorhandenen
Parent-Directory-Regel: POSIX prüft weiterhin streng, Windows überspringt die
POSIX-Modusbits. Als kompensierende Kontrolle ist die Authorization-Datei per
`icacls /inheritance:r` ausschließlich für den ausführenden Benutzer lesbar.
Der POSIX-Test für world-writable Dateien ist unter Windows begründet
geskippt. **Keine Änderung an AWS-Berechtigungen oder am Write-Umfang.**
Commit: `e8c3da8`.

## 5. Sichere Ablage (Phase C)

- Verzeichnis `C:\tmp\ris-dev2-canary-07\` (ACL: nur ausführender Benutzer).
- `user-credentials.json` enthält das generierte Passwort; **nie** in Git,
  Bericht, Auditlog oder Kommandozeilen ausgegeben.
- `identity.json`, `profile.json`, `offer.json`, `grant.json` enthalten die
  obigen IDs für Phase C.
- Entitlement läuft am **2026-11-26T17:40:28Z** ab. Phase C muss davor
  stattfinden; sonst ist ein neuer Grant (eigene Freigabe) nötig.

## 6. Grenzen eingehalten

Kein Terraform-Apply, keine Synthetic-Aktivierung, kein Order-Create, kein
Analysis-Canary, keine Änderung bestehender Cognito-Clients oder der
Pool-Konfiguration, kein Rollback/Cleanup mit weiteren Writes, kein Main-Merge.

## 7. Nächster Schritt

Phase C benötigt eine **eigene** Freigabe: `mode=true`-Plan mit den obigen
echten Identitäten, kurzem Ablauf, exaktem Diff/Hash und anschließendem
Order→Dispatch→WorkItem→Analysis→ORDER_RESULT→Owner-GET-Canary.
