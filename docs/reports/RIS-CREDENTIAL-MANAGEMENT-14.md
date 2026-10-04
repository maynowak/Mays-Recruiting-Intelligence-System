# RIS-CREDENTIAL-MANAGEMENT-14 — Credential Management Lifecycle

STATUS: GREEN (implementiert + getestet; CODE + TESTS + REPORTS, KEIN AWS/TF)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, f010c5d (+ uncommitted: P09-Evolution + 1 Test + P09-Test-Refinement + diese Reports)
- Basis (verbindlich): P09-Credential-Contract (Mechanik) + P02-Rollen + P04/P10-Profile + P11-Offers + P12-Introspection (unveraendert genutzt) + Bestand (Audit/Shred-Konventionen).
- Scope: NUR Management Plane (Issue/List/Revoke/Disable/Enable/Rotate + Rollen + Expiry + Idempotency + Audit). NICHT: GW-M2M-Route, REQUEST-Authorizer, OAuth/mTLS, Secrets Manager, neue Permission-Engine, Offer/Entitlement/APIProfile-CRUD, Sandboxing, Cognito-Migration, TF/AWS/Provisionierung.
- Classification: GREEN (61 Tests + Suite ohne Regression).
- AWS/Terraform/Migration: NONE (verifiziert). Secrets: NONE erzeugt/ausgegeben.
- Git: nur P14-Dateien (s. Commit).
- Next: Folge-Gates (Management-Endpoints, GW-Verdrahtung, Offer-Anzeige) -> HARD STOP.

## 1. Repository-Befund ZS2 (gelesen, nicht geaendert — ausser Evolution)

- P09: Issue (admin-only, KEINE Usability-Pruefung, KEINE Idempotency), Revoke/Disable/Enable (admin + Staff-Support; KEIN Owner; KEIN Expiry-Check bei Enable), Rotate (admin-only, KEINE Idempotency), Verify (unangetastet Bestehendes), Stores (put/get-by-digest/get/update/mark_used; KEIN find_by_key/list_*), Audit (eigene Namen).
- P10: Profile-Service (Create/Read/List/Allowlist-Update/Transitions/Renew/Selection; Owner/Admin/Staff-Matrix; Tenant-Regeln) — direkt wiederverwendet, KEIN Code angeruehrt.
- Konfliktanalyse Owner-Issue (explizit, NICHT eigenmaechtig uebergangen): P09-admin-only vs. P14-Owner-Self-Service. ENTSCHEIDUNG (dokumentierte Refinement, kein Bruch): Owner handelt AUSSCHLIESSLICH im eigenen nutzbaren Profil-Kontext (ID-gebunden: actor_id == ownerUserId, sonst DENIED — auch bei gefaelschter 'owner'-Rolle), begrenzt durch eigene Entitlements (KEINE Eskalation: nur diminish/revoke/rotate-eigener Rechte), voll auditiert, Standardpraxis per P01-Vendor-Pattern (OpenAI/OpenRouter: Nutzer verwalten eigene Keys). KEINE Invariante gebrochen (Isolation, Audit, No-Expansion, Secret-Hygiene intakt).

## 2. P09-Evolution (KEINE zweite Domain — alles in agents/ecosystem/credentials.py)

- Owner-Plane: issue/revoke/disable/enable/rotate fuer EIGENE Profile (ID-match; fremd -> DENIED auch mit 'owner'-Rolle).
- Usability-Gates (§8): Issue NUR ACTIVE-effektiv (PENDING/DISABLED/EXPIRED/REVOKED -> ValueError); Rotation ebenso; Enable NIEMALS bei abgelaufen (alle Rollen — rotieren statt reanimieren).
- Profile-Expiry-Cap: Credential-expiresAt DARF Profil-expiresAt NICHT ueberschreiten (MIN-Regel explizit bei Ausstellung; profillos-unbegrenzt -> Credential-Regel allein).
- Idempotency: `idempotency_key` bei Issue + Rotation (gleich -> bestehendes Ergebnis OHNE Secret (duplicate: True); anders -> CredentialConflict). KEINE Zweit-Welt (Key auf Rows).
- Staff: Reissue/Rotation NUR mit Reason (Support-Fall); sonst P02-Umfang (Revoke/Disable + Selbst-Reenable).
- Cross-Tenant: expliziter Reason noetig (sonst DENIED); Owner-Fremdprofile unabhaengig davon DENIED.
- List-/Single-Views (`list_credentials`, `get_credential_metadata`): Owner-eigen / Admin-tenant (cross mit Reason) / Staff-mit-Reason; neutral None/[] statt Orakel; `_public`-Hygiene (nie Digest/Secret); `viewed`-Audit + `expired`-Beobachtung.
- Stores: `find_by_key`/`list_by_owner`/`list_by_profile`/`list_all` BEIDE Impls (DDB: Scan+Filter, dokumentierte Massstabs-Notiz wie Bestand).
- Audit-Taxonomie §20: Management-Events heissen jetzt `credential.created/viewed/disabled/enabled/revoked/rotated/expired/unauthorized_management` (Verify-Plane behaelt `verification/*`; Mapping failed_auth/expired -> Verify-Denials im Report dokumentiert).
- P09-Test-Refinement (5 Tests, Intent erhalten): Issue-vor-Mutation (P09 erlaubte Issue-fuer-Spaeter-Deaktivierte; NEU: nur nutzbare Profile) — als Refinement kommentiert, Verify-Denials unveraendert.
- Verify/Resolve/Digest/Generierung/Stores-Basis: UNBERUEHRT (P09-Verify bleibt einziger Usage-Pruefpfad).

## 3. Issue/Metadata/Revoke/Disable/Enable/Rotation/Expiry/Idempotency/ClientRef (§§10-17, implementiert wie spezifiziert)

- Issue-12-Schritte (AuthN/AuthZ/Profile/Owner-Tenant/Status/Expiry/Cap/ID/Secret/Digest/Persist/Audit/Once-Only); KEINE Default-Expiration (expiresAt Pflicht).
- Metadata-Sicht exakt §12-Felder (digest-frei); lastUsedAt = safe metadata; KEIN Secret-Recovery (technisch unmoeglich + Test).
- Revoke terminal (alle Status -> REVOKED; revokedAt/By/Reason; Verify lehnt sofort ab). Disable<->Enable mit Selbst-Sperr-Regel + Ablauf-Sperre. Rotation B-neu/A-sofort-tot + rotationOf-Kette + Profil-Bindung (kein Umbiegen).
- ClientRef: Profil-Spiegel only (Metadata/Audit, KEIN Proof — P04/P05/P09 Gueltigkeit).

## 4. P09/P12-Integration (§§18/19 — KEINE Duplikation, KEINE P12-Aenderung)

- Verify-Pfad: EIN Pfad (`verify_api_credential`, unveraendert aufgerufen); Tests 41-46 (AUTHORIZED/403-Matrix) GRUEN.
- P12: unveraendert (nutzt Metadaten-Sicht + Verify; KEINE Secret-Ausgabe — Tests 20-22 decken Abwesenheit aus P14-Sicht mit ab).

## 5. Tests (§23 — 61 Tests, ALLE GRUEN)

Issue 1-14 (Owner/Admin/Staff/Rollen/Tenant/Status/Expiry/Cap) · Secret 15-21 (Once-Only/Abwesenheit/Digest) · Lifecycle 22-28 (+ Staff-Support/Admin-Lock) · Rotation 29-35 (+ Owner/Staff-Regeln) · Idempotency 36-40 (inkl. No-Recovery) · P09 41-46 · List-Views (Scoping/Neutralitaet) · Audit 47-53 (Cross-Tenant/Unauthorized/Secrets-frei/JWT/Header/Digest/Exception-Hygiene). KEINE echten Secrets (Zufalls-Testwerte; Secret-Scan negativ).

## 6. Regression (§24) / IAM+AWS (§22) / TF (§22)

- Gesamt-Suite: 657 passed (596 + 61), 8 skipped; 15 failed + 1 ERROR Hash-IDENTISCH zur P13-Baseline (pre-existing).
- IAM/TF/AWS/Migration: NONE (keine Tabellen angelegt, keine Rollen geaendert, keine Routen/Deploys; Bedarfs-Doku aus P09/P11 gilt unveraendert).

## 7. Offene Punkte / naechstes Gate (explizit)

Management-Endpoints (HTTP-Schicht ueber diesem Service) · GW-M2M-Verdrahtung · Offer-Anzeige/Targeting · Scope-Vokabular · Tabellen/IAM-Provisionierung (Deployment-Gate) · Default-Ablauf-Policy (UX) · B3-IndexName-Fix (Mini-Gate) · Sandboxing · `Admin`-Migration.

**HARD STOP (keine Implementierung ueber diesen Contract hinaus, keine Mutation).**
