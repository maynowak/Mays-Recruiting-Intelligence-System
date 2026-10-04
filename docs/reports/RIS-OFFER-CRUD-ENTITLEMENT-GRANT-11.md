# RIS-OFFER-CRUD-ENTITLEMENT-GRANT-11 — Offer CRUD + Offer → Entitlement Grant

STATUS: GREEN (implementiert + getestet; CODE + TESTS only, KEIN AWS, KEIN TF)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, d85afc9 (+ uncommitted: 1 Modul + 1 Test + P8-Minimal-Extension + diese Reports)
- Basis (verbindlich): P04-R1 (Minimal-Offer) + P05-R2 (final) + P06-R5 (Grant-Sequenz) + P08-Re-check + P10-Profile + P7-Status (alle unveraendert ausser dokumentierter P8-Optional-Param).
- Scope: NUR Offer-Domaene (Vertrag/Store/CRUD/Lifecycle/Admin), Grant (user-wide + profile-bound, Fenster, all-or-nothing, Idempotency, Overlap, Withdraw), Audit, Tests. NICHT: Credential-Issuance/CRUD, Gateway-Authorizer, OAuth/M2M, APIProfile-CRUD/Selection (P10 steht), Capability/Introspection, Worker-Neubau, Sandboxing, Cognito-Cleanup, Billing/Pricing/Subscription.
- Classification: GREEN (44 Tests + Suite ohne Regression).
- AWS/TF/Cognito/DB/Gateway: KEINE Mutation (verifiziert). Migration: NONE.
- Git: nur P11-Dateien + P8-Minimal-Extension (s. Commit).
- Next: Folge-Gates (Introspection, Pruefpfad-Verdrahtung, Offer-Anzeige, Sandboxing) -> HARD STOP.

## 1. Ausgangsbefunde ZS1/ZS2 (B1-B8, ohne Eingriff)

- B1: Entitlement-Tabelle provisioniert (PK entitlementId S; Attr userId/agentId; TTL expiresAt EPOCH; GSIs gsi-user/gsi-agent ALL; PAY_PER_REQUEST).
- B2: Zeilen-Vertrag (Code-gelesen): userId/tenantId(agent-global wenn fehlend)/agentId/validFrom-validUntil-ISO; KEIN status, KEIN apiProfileId, KEIN offerId/grantId (alle drei = P11-additiv, schemalos ohne TF-Aenderung).
- B3: Handler-Queries (`_get_entitlement*`) + P8-Resolver fragen OHNE IndexName (gegen PK-Tabelle zur Laufzeit ValidationException -> still None/[]). PRE-EXISTING Befund (ausserhalb P11-Scope; Fix = separates Mini-Gate; P11-Neucode nutzt IndexName korrekt).
- B4: entitlementId-Format nirgends festgelegt (nur Test-Fakes) -> `ent_`+16hex (Konvention cred_/aprof_/off_).
- B5: TTL expiresAt (epoch) vs. Fenster validFrom/Until (ISO) sind ZWEI Mechaniken (Infra-Cleanup vs. Fach-Fenster); P11 setzt expiresAt = validUntil-Epoche (Alignment, keine Erfindung).
- B6: P8-Check kennt KEINEN Profil-Kontext (Signatur ohne apiProfileId) -> minimale Optional-Param-Extension (default None = exakt altes Verhalten; P8-Tests unveraendert gruen).
- B7: Katalog-Status zentral via P7 (`is_executable_status`); Handler-Gates + Eligibility wiederverwendet, unangetastet.
- B8: P10-Profil-Service (get/effective_status/Owner/Tenant) direkt wiederverwendbar (keine Duplikation, kein P10-Code angeruehrt).

## 2. Offer Contract (NEU: agents/ecosystem/offers.py)

- Felder: offerId (`off_`+16hex, server, immutable) / name (Pflicht, GLOBAL-UNIQUE case-insensitiv) / description (optional) / status (ACTIVE/INACTIVE) / agentIds (min. 1, katalog-validiert) / createdAt/updatedAt/createdBy/updatedBy (server). KEINE Preis-/Billing-/Subscription-Felder (Test belegt Abwesenheit).
- Owner: RIS-Plattform (KEIN per-Offer-Owner). Verwaltung NUR Admin (Staff/User: Unauthorized + Audit). Reads: Admin voll; andere NUR ACTIVE-Anzeige (Name/Beschreibung/Agenten — Introspection-fundiert spaeter).
- Lifecycle: ACTIVE<->INACTIVE (Admin + Reason-Pflicht). INACTIVE blockiert NUR Neues (keine Rueckwirkung — P04-Vertrag; bestehende Rows unberuehrt belegt).
- Agent-Aenderungen: nur kuenftig (Test: alte Rows behalten alte Agents).

## 3. Grant (Herzstueck — 10-Schritt-Sequenz P06-R5 implementiert)

- NUR Admin (Staff/User: Unauthorized). Cross-Tenant NUR mit Reason. USER-XOR-PROFILE (beides/gemischtes = DENIED).
- Offer laden (fehlend/inaktiv = DENIED) + ALLE Agents JETZT katalog-validiert (P7-zentral; ein Fehler = Gesamt-DENIED, null Rows).
- Ziel: USER (kein Profil) ODER PROFILE (existiert + owner==target + tenant-match + effective-ACTIVE — PENDING/DISABLED/EXPIRED/REVOKED denied per Spec-Test 19; Renew/Aktivierung zuerst).
- Fenster: beide PFLICHT, parsbar, from<until (kein Default erfunden).
- All-or-Nothing: VOLLSTAENDIGE Validierung VOR Writes; DDB-Adapter transaktional (transact_write_items), Fake atomar (Validate-first). Partial-Write-Simulation belegt Null-Rows.
- Idempotency: identischer Grant (Offer+Ziel+Scope+Agent+Fenster) -> bestehende IDs (kein Duplikat); Key-Match -> Ergebnis; Key-Mismatch -> Conflict. KEINE Zweit-Welt (Key auf Rows, Abfrage via Store).
- Overlap: abweichendes Fenster bei gleichem (User,Agent,Kontext) -> GrantConflict (KEIN Merge/Extend/Split-Automatismus; Weg: explizit withdraw + re-grant). Dokumentiert als kleinste sichere Variante.
- Rows: entitlementId + user/tenant/agent + apiProfileId-NUR-bei-Scope (sonst ABSENT = user-wide) + Fenster + expiresAt-Epoche (TTL) + offerId/grantId (`grt_`) + createdAt/By + idempotencyKey?.
- Withdraw (admin-only, Reason-Pflicht, Hard-Delete + Audit) als expliziter Gegenakt (kein impliziter Entzug irgendwo).

## 4. P8/P10/P7-Integration (minimal, kompatibel)

- P8: `check_worker_entitlement(..., api_profile_id=None)` — user-wide Rows wie bisher; profil-gebundene NUR bei Context-Gleichheit (sonst `profile-mismatch`-DENIED); Pipeline reicht `work.get('apiProfileId')` durch (heute None = exakt altes Verhalten; alle 20 P8-Tests unveraendert gruen).
- P10: Grant nutzt `get_profile` + `effective_status` + Owner/Tenant-Vergleiche (KEIN P10-Code angeruehrt; Owner unveraendert belegt).
- P7: Katalog-Validierung + Handler/Eligibility unberuehrt; Grant-fuer-inaktive/unknown-Agents DENIED (Tests 34/35 auf Grant-Ebene + P7-Suite gruen).

## 5. Tests (Schritte 27/28 — 44 Tests, ALLE GRUEN)

- Offer 1-13 (inkl. 7 Status-Faelle + Reaktivierung + Preis-Abwesenheit).
- Grant 14-29 (Formen, Fremd/Tenant/PENDING/REVOKED, Fenster-Fehler, No-Partial, Duplikat/Idem/Overlap, Edit-/INACTIVE-Unberuehrtheit, Scope-Trennung, Staff-Verbot, Cross-Tenant, Withdraw).
- P8 30-33 (user-wide + profile-bound +/ohne Kontext, Fenster abgelaufen/zukuenftig).
- P7/P10 34-37 (Grant-Denials inaktiv/unknown; Owner-unveraendert; Cross-Tenant).
- Integrity (28er): Tamper-Tenant, Credential/Offer- und Offer/Entitlement-Verwechslung (Typ-Fehler), Scope-Mix, Key-Mismatch, Partial-Simulation, Doppel-Grant.
- KEINE echten Secrets (Zufalls-nur-Test/keine Keys im Scope).

## 6. Regression/IAM/Provisionierung (Schritte 26/29/31)

- Gesamt-Suite: 554 passed (510 + 44), 8 skipped; 15 failed + 1 ERROR IDENTISCH zur P10-Baseline (pre-existing).
- IAM: KEINE TF-Aenderung. Bedarf spaeter (Deployment-Gate): DDB Least-Privilege NUR offers-Tabelle (neu) + entitlements (bestehend, +Transact-Recht wo noetig); KEIN dynamodb:*, KEIN Cognito/S3/TF/fremde Tabellen.
- Provisionierung: NICHT erfolgt (Scope-Entscheid CODE+TESTS wie P8-P10): Offer-Tabellen-Vertrag (PK offerId; PAY_PER_REQUEST+SSE; KEIN TTL-Bedarf — Offers leben bis Admin-Akt) + Entitlement-Attribute (schemalos, KEIN TF noetig) als Doku; Entitlement-DDB-Reads mit KORREKTEM IndexName (B3-Fix NICHT noetig fuer Neucode).

## 7. Offene Folge-Punkte (explizit, nichts als entschieden dargestellt)

Offer-Anzeige/Introspection · Pruefpfad-Verdrahtung (P9-Modul -> Route) · Credential-Management-Endpoints · B3-IndexName-Fix (Handler + P8-Resolver, separates Mini-Gate) · Worker-Sandboxing · `Admin`-Migration · Tabellen/IAM-Provisionierung (Deployment-Gate) · Default-Ablauf-Policy.

**HARD STOP (keine Implementierung ueber diesen Contract hinaus, keine Mutation).**
