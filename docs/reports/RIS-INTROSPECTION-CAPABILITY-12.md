# RIS-INTROSPECTION-CAPABILITY-12 — Read-only Introspection / Capability Endpoint

STATUS: GREEN (implementiert + getestet; KEIN GW, KEIN TF, KEIN AWS, KEINE Migration)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, 6ade188 (+ uncommitted: 1 Service + Handler-Adapter + P9-Refactor + 1 Test + diese Reports)
- Basis (verbindlich): P05-R4/R5 + P06-R4 (einheitlicher Contract, 3 Aufloesungen) + P07 (Status) + P08 (Entitlement-Reads) + P09 (Verify-Boundary) + P10 (Profile/Selection) + P11 (Offers) + Bestand (Handler-401/403/404, Audit, Shred-Praxis).
- Scope: NUR Introspection (Service 3 Kontexte + Response-Contract + Handler-Adapter ohne GW-Verdrahtung + Tests). NICHT: GW-Routen/TF, neue Permission-Engine/-Tabellen, zweite Verify-Logik, Frontend-Flags als Rechte, WorkItem/SQS-Schreiben, Credential-Rotation, Provisionierung.
- Classification: GREEN (39 Tests + Suite ohne Regression).
- AWS/TF/Gateway/Cognito/DB: KEINE Mutation (verifiziert). Migration: NONE.
- Git: nur P12-Dateien (s. Commit).
- Next: Gateway-Verdrahtung + Credential-Management-Endpoints + Offer-Anzeige-Ausbau (Folge-Gates) -> HARD STOP.

## 1. Ausgangsbefund (ZS1 — gelesen, nicht geaendert)

- Handler: Pfad+Methoden-Dispatch, JWT-Claims-Extrakt (401/403/404-Konventionen), KEIN Auth-Header-Parsing (Kante), KEINE Introspection-Route.
- Resolver bereit: P10 (Profile + Selection/Default + effective_status), P8 (Entitlement-Reads + Zeitfenster + Tenant-Regel), P9 (Verify-Entscheidung + Reason-Kategorien), P7 (`is_executable_status`), P11 (Offer-Store ACTIVE/Inactive).
- Quellen: user-profile/DDB-Reads, Entitlement-Tabelle, Katalog-Tabelle, JWT-Claims; Response-Hygiene + Audit + Correlation bestehen; 401/403/404 + Tenant-Suiten bestehen.
- Fehlende Bausteine (gebaut): Introspection-Service, Credential-Kontext ueber HTTP (GW-Route fehlt — Adapter vorbereitet), Profil-Auswahl-Traeger ueber HTTP (Header-Read). NICHTS sonst fehlte.

## 2. Verwendete Komponenten / Architekturgrenze (§2 — strikt)

Request (JWT / X-Api-Profile / Credential-Param) -> Introspection -> {UserProfile/Identity, APIProfile, Entitlements, Offers, Katalog} -> positive Response. KEINE neue Permission Engine/Tabelle/Authorization, KEINE zweite Credential-Verifikation (P09-Boundary SHARED via `resolve_credential_profile` — dafuer P09-interner Refactor: Schritte 1-11 extrahiert, alle 39 P09-Tests weiter GRUEN), KEINE Frontend-Flag-Rechte.

## 3. Context-Modell (§3 — drei Kontexte, ein Vertrag)

- HUMAN (JWT sub/tenant): allowedProfiles (eigene ACTIVE, minimal) + user-weite Positiv-Capabilities + ACTIVE-Offers. KEINE fremden Profile/Tenants.
- PROFILE (X-Api-Profile, UNTRUSTED): P10-Resolution (Default bei 1/keins-bei-0/Pflicht-bei-n; explizit verifiziert oder neutral 404); danach Profil-Capabilities (Union user-weit + profil-gebunden) + Offers + Ablauf-Hinweise.
- CREDENTIAL (Bearer-Param): P09-Shared-Boundary (Status/Expiry/Owner-Tenant wie Verify); Mismatch Header-vs-Bindung -> 403; Response NUR sichere Metadaten (credentialId/expiresAt/apiProfileId — KEIN Secret/Digest/JWT/Header).

## 4. Response Contract (§4 — Pflichtschluessel immer)

context/subject/capabilities/validity{checkedAt}/resolution in JEDEM Kontext; dazu kontextabhaengig allowedProfiles/profile/credential/offers/validity-Details. Capability-Eintraege: agentId/name/capabilities/scopeRestricted/expiresHint (Minimum relevanter Ablaeufe). Offer-Eintraege: offerId/name/description (KEINE Preise — existieren nicht).

## 5. Positive-only / Security Boundary (§5 — kein Orakel)

Abwesend statt begruendet: unbekannte/fremde/deaktivierte Profile (404-neutral), nicht-entitlede/nicht-ausfuehrbare Agents (nicht in Liste), keine Reason-/Policy-/IAM-/DDB-/Rollen-/Digest-/Secret-/JWT-/Header-/Payload-Details, keine Negativlisten, keine Schwellen-Offenlegung. Tests 24-30 belegen Abwesenheit (inkl. Audit-Logs).

## 6. Capability Resolution (§6 — UNION + INTERSECT-only)

effective = user-weit UNION profil-gebunden (Tenant-gefiltert, Fenster-geprueft) INTERSECT optionalem Scope-Filter (v1: kein Taxonomie-Scope — Filter = Agenten-Menge, nur einschraenkend, `scopeRestricted`-Flag; Erweiterung NIEMALS). KEINE zweite Welt (P08-Zeit + P07-Status wiederverwendet).

## 7. Agent Catalog / P7 (§7 — zentral, keine Zweit-Logik)

NUR normalized-ACTIVE sichtbar (Dict- ODER Roh-String-Eintraege via `_catalog_entry`); INACTIVE/DEPRECATED/RETIRED/REGISTERED/AVAILABLE/FAILED/UNKNOWN abwesend (Tests 19-21 + Ghost-Agent).

## 8. Offer Resolution (§8 — Anzeige, keine Wirkung)

ACTIVE-Anzeige (derzeit alle ACTIVE — KEIN Targeting-Modell vorhanden, dokumentiert); INACTIVE verborgen; KEINE Preis/Billing/Subscription-Daten (Test 24); Aenderungen ohne Rueckwirkung (P11-Vertrag unberuehrt).

## 9. Profile Resolution (§9 — P10, keine Duplikation)

Default 0/1/n + explizit-verifiziert-oder-neutral-404 + Credential-Match-Regel (Mismatch 403, kein Override). Unbekannt/fremd/deaktiviert NIEMALS als eigen behandelt.

## 10. Human/Credential-Kontexte (§10/§11 — bestehende Vertraege)

- Human: sub/tenant aus JWT (validierter Identity-Kontext); UserProfile bleibt User-Datenbasis (unberuehrt, nur referenziert); AllowedProfiles fuehren zur Auswahl-UX.
- Credential: P09-`resolve_credential_profile` SHARED (kein Re-Hash/Store/Log/Return — Tests belegen Abwesenheit); Metadaten-Minimum in Response.

## 11. Admin-Sicht (§12 — NICHT erweitert, dokumentiert)

P10-Admin-Kompetenz (fremde Profile mit Reason) wird in Resolution respektiert, ABER Introspection wird NICHT zur Export-Schnittstelle: keine Bulk-Aufzaehlung (P10-`list_profiles` gibt Admins nur eigene; volle Tenant-Listen existieren nicht). Als Grenze dokumentiert statt erweitert.

## 12. Credential Scope (§13 — optional/restriktiv, getestet)

Ohne Filter: volle Profil-Union (`scopeRestricted: false`). Mit Filter: Schnittmenge (`scopeRestricted: true`); Filter ⊄ Entitlements -> LEER (200, kein Fehler — Test 16 beweist Nicht-Erweiterung).

## 13. Endpoint + HTTP (§14/§15 — vorbereitet, NICHT verdrahtet)

- KEIN GW-Pfad angelegt (TF-Verbot), KEINE Dispatch-Route (keine toten Pfade), KEINE Live-Claims: `_handle_introspection(event, context, bearer_credential=None)` + `_build_introspection_sources()` (lazy; fehlende unprovisionierte Tabellen -> neutral 503 "Temporarily unavailable" — KEIN falscher Live-Betrieb).
- Header-Read: `x-api-profile` (GW-v2-Kleinschreibung beachtet). JWT via `_extract_user_context`.
- Semantik: 200 (gueltig), 401 (kein JWT + kein Bearer / unbekannt/Format), 403 (bekannt-aber-nicht-nutzbar/Mismatch), 404 (explizit-unaufloesbar, neutral), 503 (Infra, neutral), 500 (unerwartet, neutral "Internal error" — KEINE Details).

## 14. Audit (§16 — Konvention, secrets-frei)

Je Introspection: actor/user, tenant, context, apiProfileId?, credentialId?, timestamp, correlation/requestId, resolution-mode, outcome. NIEMALS Secret/Digest/JWT/Header/Payload-Secrets. KEINE Response-Persistierung (nur Events).

## 15. Tests (§17 — 39 Tests, ALLE GRUEN)

Human 1/2 · Profile 3-11 (inkl. PENDING/DISABLED/EXPIRED/REVOKED-404) · Capabilities 12-21 (Union/Scope±/Tenant/Ghost/Status/Expiry) · Offers 22-24 · Credential-View/Mismatch/Unknown · Hygiene 25-30 (Secrets/JWTs/Digests/Positiv-only/Orakel/Audit-Logs) · Handler (200/401/404/503/Header/Bearer-Param). KEIN Test mit fremden Secrets.

## 16. Regression (§20) / IAM+AWS (§19)

- Gesamt-Suite: 593 passed (554 + 39), 8 skipped; 15 failed + 1 ERROR IDENTISCH zur P11-Baseline (Hash-gleich, pre-existing).
- AWS Mutation: NONE. Terraform: NONE. Migration: NONE. (Falls Provisionierung je noetig: Deployment Gate required — dokumentiert, nicht ausgefuehrt.)

## 17. Offene Punkte / naechstes Gate (explizit)

GW-Routen + TF-Verdrahtung (Human/JWT + Machine-Pfad nach P04-Namensraum) · Credential-Management-Endpoints · Offer-Targeting (falls Produkt es verlangt) · Scope-Vokabular (falls je eingefuehrt) · Tabellen/IAM-Provisionierung (Deployment-Gate) · B3-IndexName-Fix (Mini-Gate, unabhaengig) · Sandboxing/`Admin`-Migration (sichtbar).

**HARD STOP (keine Implementierung ueber diesen Contract hinaus, keine Mutation).**
