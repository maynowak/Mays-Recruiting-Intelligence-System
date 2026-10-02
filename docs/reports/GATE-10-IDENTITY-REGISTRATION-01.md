# GATE-10 — Identity & Registration

STATUS: GREEN (mit 1 OPEN: E-Mail-Verifikation nicht konfiguriert)

- Date/Time: 2026-10-02 UTC
- Branch + HEAD (RIS): main, 1ac5bca + Gate-10-Folgeänderungen (s. Git)
- MO-Stand: 0 Änderungen. Gates 5–9 unangetastet (nur Handler-Import/Dispatch + Katalog-Lazy).
- Scope: Benutzer-Lifecycle (SignUp→Confirm→Login→JWT→Provision→/me→/profile). Keine Jobsuche, keine Jobbörsen, kein neues Runtime-System.
- Sections: Bestand, Contract, E2E, Security, Tests, Docs unten
- Findings: Kette live belegt; 3 echte Befunde behoben (Dispatch-KeyError, Payload-2.0, GSI-NULL); Pool versendet keine Verifikation (OPEN)
- Evidence: API-Responses, Cognito-CLI, DDB-Items, Logs, Suite 327
- Classification: GREEN (Kette) + OPEN (Mail-Verifikation)
- Terraform/AWS Checks: validate GREEN; gezielt Policy (1 changed); 3 Routen per CLI (lambda.zip-Lücke, dokumentiert); 0 destroys
- Git Status (RIS): Commits pro Bereich (s. Git); Clone/States unberührt
- Files Changed: `lambda/handler.py` (Provision/Dispatch/Payload-2.0/Tenant-Fallback/Lazy), `tests/test_identity_registration.py` (neu, 6), TF (Route + PutItem), Docs (API/Architektur), Reports
- Open Questions: E-Mail-Verifikation (Pool-Config-Entscheid); /health ohne Handler (OPEN); Catalog-Scan-Deny (pre-existing); fehlende Plattform-Routen nur bei Bedarf
- Risks: keine neuen (synthetische User, gelöscht; Secrets geschreddert)
- Next Actions: Commits → Folgetor (JobSearch-Backend bleibt clientseitig per Vorgabe)
- Resume Point: nach Commit HARD STOP

## 1. Bestand

Pool `eu-central-1_dgQXgwUbv` (Self-Signup ERLAUBT `AllowAdminCreateUserOnly=false`, MFA OFF, COGNITO_DEFAULT, KEINE AutoVerifiedAttributes); Client USER_PASSWORD_AUTH+Refresh (public); 7 Gruppen; Domain + JWT-Authorizer vorhanden. `/me`+`/me/profile` nur Read (404 ohne Profil); KEIN Provisioning irgendwo (Befund: kein Auto-Provision — Vorgabe erfüllt); Tabelle user-profile (Hash userId + GSI gsi-tenant, leer). JWT PROVEN, Reads PROVEN (Code), Registration/Init OPEN (jetzt geschlossen bis auf Mail).

## 2. Registration Contract (live belegt)

SignUp (Name/Username/E-Mail/Passwort 8+Regeln) → `UserConfirmed:false`, KEIN Code-Versand (OPEN) → Login blockiert (`UserNotConfirmedException` belegt) → Admin-Confirm (Test-Ersatz) → Login → JWT → POST /me/profile (201, Conditional) → GET (200). Keine CV-/Job-/ATS-Daten in Stufe 1.

## 3. Bewusste Registrierung

Reihenfolge wie Contract; GET /me/profile VOR Provision = 404 (belegt — kein Auto-Provision); POST-Duplikat = 409 (kein Überschreiben). Trigger = Registrierungs-Client, nie Read.

## 4. User Profile

`{userId=sub, tenantId=Claim||'default' (GSI braucht String), username, email, displayName?, status ACTIVE, createdAt/updatedAt}`. Tenant-Isolation: sub-gebunden (fremde Profile technisch nicht adressierbar — Zweituser sieht nur 404). Keine Identity-DB neben Cognito (Cognito=IdP, DDB=Profildaten).

## 5. Login

Bestehender Client-Flow, kein Passwort-Code bei uns. JWT→Authorizer→Claims→/me (200 mit sub/email/tenant/groups) belegt.

## 6. E-Mail-Prüfung

Cognito-Modell verwendet, aber: Pool verlangt Confirmation, versendet NICHTS (kein Code, kein Auto-Verify). Verhalten belegt: unconfirmed→Login-Fehler; nach Confirm→Login-OK. Lücke = OPEN (Pool-Config `auto_verified_attributes=[email]` + Absender = separater Entscheid, kein Code nötig).

## 7. Profilabruf

/me 200; /me/profile 200 nach Provision (vollständiges Profil); Zweituser 404 (Isolation); kein Token→401; Fake-Token→401; Duplikat-Signup→UsernameExists; Falsch-Passwort→NotAuthorized.

## 8. Security

Unauth/invalid/duplicate/wrong-pw kontrolliert; confirmed→Zugriff; Tenant→eigen ok/fremd 404; keine Passwörter in DDB (nur Cognito-Hash dort); keine Secrets/Token in Logs/Reports (Shred); PII nur synthetisch.

## 9. API

 Routen: POST /me/profile (neu, JWT, Conditional) + fehlende GET /me, GET /me/profile live ergänzt (deklariert, nie applied — wie Authorizer Gate 4). Befunde: Agent-Dispatch-KeyError (alle Agent-Routen waren 500 — behoben), Payload-2.0-Pfad (behoben), `/health` ohne Handler (OPEN, ausser Scope).

## 10. Tests

Neu 6 (Provision 201/Felder, 409, Username-Extraktion, 401, Tenant-Fallback, Dispatch-KeyError). Suite **327 passed** (321 + 6), 4 pre-existing deselected + 1 Collection (klassifiziert). Lazy-boto-Fix heilte zusätzlich den order-abhängigen Source-Connectivity-Test (jetzt grün in Suite).

## 11. Live E2E

Synthetische User (echtes SignUp + Admin-Confirm als Mail-Ersatz), Login, /me, 404-vorher, 201-Provision, 200, 409, Isolation, Negativs — alle belegt. Cleanup: beide User + Profil gelöscht (Pool leer, Tabelle 0), Secrets geschreddert.

## 12. JobSearch-Abgrenzung

`mays-jobs-matcher` bleibt clientseitig (keine Änderung). Kein Crawling/Aggregation/zentrale Suche/Backend-Suche in diesem Gate. RIS liefert Identity + Profile.

## 13. Doku-Änderungen

API-STANDARD (Route + Registrierungs-Contract), SYSTEM-ARCHITECTURE (Identity-Absatz), diese Reports. Keine alten Reports angerührt.

## 16. Abschluss

| Bereich | Ergebnis |
|---|---|
| Registration | GREEN |
| Email Verification | YELLOW (OPEN: kein Versand konfiguriert) |
| Login / JWT | GREEN |
| Profile Provisioning | GREEN (nur explizit) |
| /me / /me/profile | GREEN |
| Tenant Isolation | GREEN |
| Security | GREEN |
| Tests | GREEN (327) |
| Live E2E | GREEN |
| Documentation / Git | GREEN |

**GREEN** (Gesamt; 1 OPEN dokumentiert). Reports: `GATE-10-IDENTITY-REGISTRATION-01.md` (+ Log). Commits: s. Git. Offen: Mail-Config-Entscheid, /health-Handler, Catalog-Scan-Deny, fehlende Plattform-Routen bei Bedarf. Nächstes Gate: JobSearch-Backend bleibt clientseitig — Vorschlag: Mail-Verifikation schliessen oder Domain-Vertiefung.

**DANN HARD STOP.**
