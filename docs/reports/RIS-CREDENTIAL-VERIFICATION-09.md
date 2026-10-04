# RIS-CREDENTIAL-VERIFICATION-09 — Opaque Bearer Credential (Verification)

STATUS: GREEN (implementiert + getestet; KEIN AWS, KEIN TF, KEINE Migration, KEINE echten Secrets)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, 31c4ff4 (+ uncommitted: 1 Modul + 1 Test + diese Reports)
- Basis (verbindlich): P03-C1-C7 + P05-R3 + P06-R2/R3/R7 + P08-Worker-Re-check (unveraendert) + Bestand (GW-JWT-Kante, Handler-401/403, Entitlement-Vertrag, Shred-/Maskierungs-Praxis).
- Scope: NUR Credential-Grenze (Modell/Erzeugung/Once-Only/Digest/Verify-Interface/401-403/Bindung/Expiry/Revocation/Rotation/Audit/Negativ-Tests). NICHT: APIProfile-CRUD/Selection, Offer-CRUD/Grant, Capability/Introspection, Worker-Re-check (P8 steht), Sandboxing, OAuth/M2M, mTLS, Secrets Manager, Cognito-Cleanup. P7/P8 UNVERAENDERT.
- Classification: GREEN (39 Tests + Suite ohne Regression).
- Terraform/AWS/Cognito/DB/Gateway: KEINE Mutation (verifiziert). Migration: NONE.
- Git: nur P9-Dateien (s. Commit).
- Next: Folge-Gates per P6-R8 (Offer/APIProfile-CRUD, Introspection, Pruefpfad-Verdrahtung, Sandboxing) -> HARD STOP.

## 1. Ausgangsbefund ZS1 (gelesen, nicht geaendert)

- GW: JWT-Authorizer (Authorization-Header, Audience/Issuer); Routen-Tabelle bekannt (JWT ausser /health-NONE; Execute handler-intern). Handler parst KEINEN Authorization-Header selbst (Kante prueft JWT).
- 401/403-Tests bestehen (identity/platform/documents-Suiten); Shred-/Maskierungs-Praxis belegt (Gates 10/11/14: keine Secrets/Token in Logs/Reports).
- Entitlement-Vertrag + P8-Re-check + P7-Statusgrenze: wiederverwendet, unangetastet.

## 2. Route-Grenze ZS2 (DECIDED, dokumentiert — KEIN TF-Eingriff)

- Human-JWT und Machine-Credential NIEMALS konkurrierend auf derselben Route (kein "erst JWT, sonst Key" — Orakel-/Downgrade-Risiko); Human-Pfad UNVERAENDERT.
- Namespace-Vertrag (minimal, Vorschlag fuer spaeteres Gate — NICHT implementiert, KEINE TF-Routen angelegt): Machine-Zugaenge unter `/v1/m2m/`-Prefix (folgt P04-`/v1/`-Prinzip); bestehende Human-Pfade bleiben JWT-only.
- P09-Verifikation ist routen-unabhaengig getestet (Harness-Pfad: Modul direkt; GW-Anbindung = spaeteres Verdrahtungs-Gate).

## 3. Credential Contract (Modell ZS3 + Typ-Entscheid)

- Typ: OPAQUE BEARER (`opaque-bearer-v1`) — kein JWT/Passwort/Profil/Entitlement/AWS-Secret; genau EIN APIProfile (Transfer verboten); widerrufbar; pro Verwendung geprueft; nie rekonstruierbar.
- Metadaten (persistiert, camelCase Repo-Konvention): credentialId / apiProfileId / ownerUserId / tenantId (PFLICHT — P09-Klaerung des P02-Objektvertrags: Isolation verlangt persistierten Tenant; fehlend = 403) / label / credentialType / status(ACTIVE/DISABLED/REVOKED — KEIN PENDING) / digest(Lookup, intern) / clientRef (Profil-Spiegel) / createdAt/updatedAt/expiresAt(PFLICHT)/lastUsedAt / revokedAt/revokedBy/revokeReason / disabledBy / rotationOf / createdBy{actor,role}.
- NIE persistiert: Roh-Credential/Secret, Header, Passwort, JWT, Session-Token (absolut; Tests belegen Abwesenheit in Stores/Logs/Responses).

## 4. Digest + Generierung (ZS4/ZS5 — NEU: agents/ecosystem/credentials.py)

- Secret: `ris_` + base64url(32 Zufalls-Bytes, `secrets`-Modul) = 47 Zeichen; nicht-deterministisch, entropiestark, inhaltsleer (keine IDs/Daten/Zeit — Test belegt Abwesenheit von userId/profileId/tenant).
- Digest: SHA-256 ueber Domain-Trennung `ris-cred-v1:` + Secret (deterministischer Lookup; keine reversible Verschluesselung; Digest ist KEIN Credential, wird NIEMALS zurueckgegeben/geloggt).
- Ausgabe: GENAU EINMAL bei Ausstellung (Rückgabe-Objekt {metadata-ohne-digest, secret}); danach unrekonstruierbar (nur Digest-Vergleich).

## 5. Verification Interface (Schritt 6 — `verify_api_credential`, P06-Signatur)

- INPUT: bearer + agent_id (PFLICHT — Ziel wird NIE geraten; Capability-Mapping = Routing-Sache) + optionale operation/route/method/requestTime/requestId/selectionHint (UNTRUSTED).
- OUTPUT AUTHORIZED (ausschliesslich): userId/tenantId/apiProfileId/credentialId/entitlementRefs/effectiveScope/resolution/auditRef — KEIN Rohwert/Digest/Secret/JWT/Header/fremde Kontexte.
- Reihenfolge Schritt 7 implementiert (1-15): Format -> Digest-Lookup -> Status -> Profil-Existenz -> Profil-Status -> Expiry-MIN(Credential,Profil) -> Owner/Tenant-Konsistenz (+ Tenant-Pflicht) -> Client-Note (Metadaten-only, blockiert NIE) -> Entitlement (P08-Reuse, Scope v1 = keine Einschraenkung) -> Katalog-Ausfuehrbarkeit (P7-zentral) -> AUTHORIZED.
- 401 (unbekannt/ungueltig/Format/fehlendes Ziel) vs. 403 (bekannt-aber-deaktiviert/revoked/abgelaufen/Profil-negativ/Mismatch/Entitlement/Katalog) — KEINE Orakel-Begruendungen aussen (Reason-Kategorie nur Audit-intern).
- Store-Fehler -> `CredentialStoreUnavailable` (Aufrufer mappt 503; NIEMALS 401/403 — Fail-Closed ohne Fehldeutung).

## 6. Bindungen (Schritte 8/9 — KEINE zweite Welt)

- APIProfile-Abhaengigkeit: Resolver-entkoppelt (`get_profile`-Protokoll; In-Memory + lazy-DynamoDB-Adapter, KEINE Tabellenerstellung); KEIN CRUD/UI/Selection/Offer hier.
- Entitlement: P08-`check_worker_entitlement` wiederverwendet (Owner als user_id + Profil-Tenant + Agent); Credential erweitert NICHTS (v1 scopelos = volle Profil-Union; Schnittformel greift bei kuenftigen Scopes).
- Katalog: `is_executable_status` (P7-zentral); unbekannter Agent -> 403.

## 7. Revocation/Expiry/Rotation (Schritte 10-12)

- Kaskade: Credential-REVOKED -> sofort tot; Profil REVOKED/DISABLED/EXPIRED -> alle Credentials sofort tot (Status wird JE Verification frisch gelesen — KEIN positiver Cache; Tests 18/19/23 belegen Sofortwirkung).
- Expiry: PFLICHT beidseitig; effektiv MIN; Profil dominiert (Test 13). KEINE Produkt-Default-Dauer festgelegt (Aufrufer MUSS expiresAt liefern — ValueError sonst; kein OPEN-Dauer-Problem, da kein Default existiert).
- Rotation: B neu (ID + Secret), A SOFORT revoked (Standard); Overlap nur spaeter explizit+befristet (Daten-Grenze bereit: rotationOf-Kette). Admin-only (Staff: KEIN issue/rotate; revoke/disable + Selbst-Reenable per P02).

## 8. Audit (Schritt 13 — P03-Felder, secrets-frei)

- Events: issued/secret-issued (Metadaten-only), verification success/unknown/denied, revoked/expired/disabled/enabled, rotated (A->B-verlinkt), unauthorized-management-attempt.
- Felder: actor/timestamp/credentialId/apiProfileId/clientRef/action/outcome/reason-Kategorie/tenant/correlation(audit_ref+requestId). NIEMALS Secret/Digest/JWT/Header/Passwort/Payload (Tests 20-22 belegen Abwesenheit in Logs/Stores/Responses).

## 9. Tests (Schritt 14: 25 Faelle + Schritt 15 Fail-Closed — 39 Tests, ALLE GRUEN)

- Matrix 1-19 (inkl. 14b Tenant-Pflicht), 24/25 Rotation, Management (Admin/Staff-Regeln, Expiry-Pflicht, Profil-Pflicht, lastUsedAt), Hygiene 20-23, Fail-Closed (Credential-/Profil-/Entitlement-Store-Ausfall -> CredentialStoreUnavailable, KEIN 401/403, KEIN AUTHORIZED).
- Datei: tests/test_credential_verification.py (39 Tests).

## 10. Regression (Schritt 18) / IAM (Schritt 17)

- Gesamt-Suite: 457 passed (418 + 39), 8 skipped; 15 failed + 1 ERROR = IDENTISCHE Menge wie P8-Baseline (pre-existing, unberuehrt).
- IAM: KEINE TF-Aenderung (Scope-Verbot erfuellt). Bedarfs-Vertrag fuer spaeteres TF-Gate (dokumentiert, nicht angelegt): DDB Least-Privilege NUR auf Credential-/Profil-/Entitlement-Tabellen (Read: Metadaten + Digest-GSI + Profil + Entitlements; Write: Issuance-/Revocation-Metadaten + Audit-Pfad); KEIN dynamodb:*, KEIN S3, KEIN Cognito-Admin, KEINE TF-Rechte. Tabellen-Design (PK credentialId + GSI digest; PK apiProfileId) als Vorschlag, NICHT erstellt.

## 11. Offene Policy-Punkte (explizit, keine als entschieden dargestellt)

- Operator-Default-Ablaufdauer (Code verlangt explizites expiresAt; UX-Default = Produkt-Policy, spaeter).
- User-sichtbarer Metadaten-Umfang (Endpoint-Entscheid, spaeter).
- Scope-Vokabular (falls je eingefuehrt; v1 = keine Einschraenkung).
- Routen-Pfad-Finalisierung (`/v1/m2m/`-Vorschlag) + Pruefpfad-Verdrahtung (REQUEST-Authorizer vs. Lambda-intern ist fuer JWT-fremde Keys weiter Design-Entscheid VOR Verdrahtung — P04-R2 galt fuer Einfuehrungspfad B der Prueflogik, nicht fuer GW-Anbindung).
- Secrets-Manager-Ablage (DEFERRED-Option bei Compliance-Bedarf).

**HARD STOP (keine Implementierung ueber diesen Contract hinaus, keine Mutation).**
