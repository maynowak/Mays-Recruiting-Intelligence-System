# GATE-12 — User Profile & Persistence Foundation

STATUS: GREEN

- Date/Time: 2026-10-02 UTC
- Branch + HEAD (RIS): main + Gate-12-Commits (s. Git)
- MO-Stand: 0 Änderungen. Gates 5–11 unangetastet (nur Handler/TF-Config im Scope).
- Scope: Profile-v1 (Modell, Persistenz, POST/GET/PUT, Isolation, Security). Kein CV-Storage, keine Adresse/Payment, keine Aggregation, kein Auth-Neubau.
- Sections: Bestand, Modell, API, Security, Tests, E2E, Docs unten
- Findings: v1 live belegt (201/200/409/404-Semantik); Spoof-Versuche ignoriert; keine neue Tabelle nötig
- Evidence: 11 Unit-Tests, API-Responses, DDB-Items, Suite 334
- Classification: GREEN (alle Bereiche; CV-Storage explizit später)
- Terraform/AWS Checks: validate GREEN; gezielt Policy (1 changed); PUT-Route per CLI (lambda.zip-Lücke); 0 destroys
- Git Status (RIS): Commits pro Bereich (s. Git); Clone/States unberührt
- Files Changed: `lambda/handler.py` (v1 + PUT), `tests/test_identity_registration.py` (11), TF (Route + UpdateItem), Docs (API/Architektur), Reports
- Open Questions: keine neuen (Gate-10/11-OPENs bestehen: Mail-Inbox, /health, Catalog-Scan, Plattform-Routen)
- Risks: keine neuen (synthetische User, gelöscht; Secrets geschreddert)
- Next Actions: Commit → Folgetor (Secure CV Storage separat)
- Resume Point: nach Commit HARD STOP

## Bestand

Tabelle `mays-ris-dev-user-profile` (Hash userId, GSI gsi-tenant, TTL expiresAt, PAY_PER_REQUEST, SSE-Default) — geeignet, keine neue Tabelle. Gate-10-Provision speicherte username/displayName (jetzt v1-konform ersetzt; Tabelle war leer — keine Migration). GET nur Read (404 ohne Auto-Provision — Vorgabe erfüllt).

## Modell (v1, live)

`{userId=sub, tenantId=Claim||default, nickname?, firstName?, lastName?, email=Claim, status ACTIVE, createdAt, updatedAt}`. NUR diese Felder; kein username/displayName mehr; keine Adresse/Payment/CV/Dokumente (bewusst nicht).

## API (live belegt)

- POST /me/profile: 201 (Conditional) / 409 (Duplikat, kein Overwrite) / 401 / 400.
- GET /me/profile: 200 eigenes / 404 fehlend-fremd / 401.
- PUT /me/profile: 200 (nur nickname/firstName/lastName) / 400 (leer) / 404 (kein Upsert) / 401.
- Identität: userId/tenantId/createdAt/email/status immun (Body-Spoof live ignoriert); updatedAt serverseitig.

## Security

Unauth/invalid kontrolliert; A→B DENIED (404, sub-gebunden, kein fremder Zugriffspfad existent); Tenant via Claim + Code-Guards; keine Passwörter/Tokens in DDB (nur Cognito); keine PII in Logs (nur IDs); IAM +UpdateItem nur user-profile-Tabelle; HTTPS via API-GW; SSE-Default (AWS-verwaltet, Projektkonvention).

## Tests (11, alle Gate-Punkte)

Create, Read (Handler-GET + live), Duplicate, Missing (GET+PUT 404), User-Isolation (live Zweituser), Tenant-Isolation (live + Unit), Unauth (401), userId-Spoof, tenantId-Spoof, Update, createdAt-immun, updatedAt-server. Suite **334 passed** (4 pre-existing deselected + 1 Collection klassifiziert).

## Live E2E (synthetisch)

User A: POST 201 (Spoof ignoriert) → GET 200 → PUT 200 (immutable belegt) → POST 409. User B: PUT 404 + GET 404 (Isolation). Cleanup: beide User + Profil gelöscht (Pool leer, Tabelle 0), Secrets geschreddert.

## Docs

API-STANDARD (PUT-Zeile), SYSTEM-ARCHITECTURE (v1-Absatz), diese Reports. CV STORAGE = späteres separates Gate (hier dokumentiert, nicht implementiert).

## Checkpoint

| Bereich | Ergebnis |
|---|---|
| Profile Model | GREEN |
| Persistence | GREEN |
| API | GREEN |
| Identity Binding | GREEN |
| Tenant Isolation | GREEN |
| IAM/Security | GREEN |
| Tests | GREEN (11 + 334) |
| AWS E2E | GREEN |
| Documentation | GREEN |
| Git | GREEN (folgt) |

**GREEN.** Reports: `GATE-12-USER-PROFILE-PERSISTENCE-01.md` (+ Log). Commits: s. Git. Offen: nur Gate-10/11-OPENs. Nächstes: Secure CV Storage (separat).

**DANN HARD STOP.**
