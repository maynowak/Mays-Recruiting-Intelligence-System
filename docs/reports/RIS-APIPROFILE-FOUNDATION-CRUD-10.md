# RIS-APIPROFILE-FOUNDATION-CRUD-10 — APIProfile Foundation, CRUD & Selection

STATUS: GREEN (implementiert + getestet; CODE + TESTS only, KEIN AWS, KEIN TF)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, e1bdcf5 (+ uncommitted: 1 Modul + 1 Test + diese Reports)
- Basis (verbindlich): P02 (Objekt/Lifecycle/Rollen) + P03/P09 (Credential-Bindung) + P04-R3 (CRUD/Idempotency) + P05-R4 (Selection) + P06 (Interfaces) + Bestand (UserProfile-CRUD, DDB-Konventionen, Handler-401/403/404, Conditional-Write/409, Shred-Praxis).
- Scope: NUR APIProfile-Domaene (Persistence-Vertrag, Repository, Service CRUD/Lifecycle/Rollen, Tenant, Selection/Default, Audit, Tests). NICHT: Offer-CRUD/Grant, Credential-Issuance/CRUD, Gateway-Authorizer, OAuth/M2M, Capability/Introspection, Worker-Re-check (P8 steht), Sandboxing, Cognito-Cleanup. P7/P8/P9 UNVERAENDERT (Regression belegt).
- Classification: GREEN (53 Tests + Suite ohne Regression).
- AWS/TF/Cognito/DB/Gateway: KEINE Mutation (Scope-Entscheid §8: CODE + TESTS only). Migration: NONE.
- Git: nur P10-Dateien (s. Commit).
- Next: Folge-Gates (Offer-CRUD/Grant, Introspection, Pruefpfad-Verdrahtung) -> HARD STOP.

## 1. Ausgangsbefunde ZS1 (B1-B10, ohne Eingriff)

- B1: UserProfile = Tabelle (PK userId, GSI tenant, TTL) + Handler-CRUD (POST-Conditional-409, GET, PUT-Allowlist nickname/firstName/lastName; immun: userId/tenantId/createdAt/email/status).
- B2: Entitlements = Tabelle only (PK entitlementId, GSIs userId/agentId); KEIN Service-Layer; Reads via Handler-Helper + P8-Resolver.
- B3: Katalog = Tabelle + P7-normierter Adapter/Registry-Pfad.
- B4: Cognito-Gruppen: 7 TF-Objekte; Code echoet Claims; KEINE Enforcement-Stelle — P10 fuehrt erste `admins`/`Staff`-Pruefungen im Service ein (gruppenbasiert, kein neues Rollenobjekt).
- B5: Handler-Routing (Pfad+Methode, JWT-Kontext sub/email/tenant/groups, 401/403/404).
- B6: Auth-Helfer (Zeitfenster, Tenant-Guards, Spoof-Ignoranz als Konvention).
- B7: Audit (Logger, secrets-frei) + Correlation (workId/requestId-Ketten).
- B8: Idempotency (Conditional Writes, 409, idempotencyKey-Transport, workId-Dedup).
- B9: P9-Resolver-Protokoll `get_profile(id)` (In-Memory + lazy-DDB; Credential-Service erwartet apiProfileId/ownerUserId/tenantId/status/expiresAt/clientRef).
- B10: APIProfile-Domaene = 0 Treffer ausser P09-Fremdschluessel (apiProfileId) — neu zu bauen, nichts zu uebernehmen.

## 2. Object Boundary ZS2 (im Code durchgesetzt)

UserProfile (Personendaten, fremde Domaene, unberuehrt) vs. APIProfile (Nutzungskontext, DIESES Modul) vs. Credential (Nachweis, P09 referenziert Profile) vs. Entitlement (Recht, Tabelle, Grant spaeter) vs. Offer (Paket, spaeter) vs. Tenant (Isolation, nie Owner) vs. Owner (nur ownerUserId). Keine Vermischung: strikte Feld-Allowlisten, kein generisches Merge, keine Fremdschluessel-Logik ausser apiProfileId-Referenzen.

## 3. Schema ZS3/ZS4 (Vertrag, NICHT provisioniert — CODE + TESTS only)

- Eigene Tabelle (NICHT UserProfile wiederverwendet): Namensmuster `{project}-{env}-api-profiles` (Repo-Konvention), PK apiProfileId (S), GSI-1 `gsi-owner` HASH ownerUserId (ALL) — KEINE Tenant-GSI (Tenant wird pro Item verifiziert, nie als Listenschluessel; KEINE unnoetigen GSIs), PAY_PER_REQUEST + SSE-Default (Konvention), KEIN TTL (abgelaufene Profile bleiben EXPIRED-Saetze fuers Audit; Loeschung nur explizit-admin, spaeter).
- Felder/Pflichten: apiProfileId (server, `aprof_`+16hex, immutable), name (Pflicht, getrimmt, UNIQUE je Owner case-insensitiv), description (optional), ownerUserId (Pflicht, immutable), tenantId (Pflicht, server-/claim-derived, immutable, nie Payload), clientRef (optional/NULL, admin-only), status (nur PENDING/ACTIVE/DISABLED/REVOKED gespeichert; EXPIRED abgeleitet), createdAt/updatedAt/createdBy/updatedBy (server), expiresAt (optional/NULL, admin-only, muss parsen), disabledBy (Sperr-Akteur/Rolle/Grund), idempotencyKey (intern, nie extern).
- TF-Entscheid (§8/Schritt 26): KEINE Tabellen-/IAM-Anlage in P10 (Sicherheits-/Umfangs-Grund wie P8/P9: lazy Adapter + Vertrags-Doku; Provisionierung = separates Deployment-Gate mit Plan/Apply/Verifikation).

## 4. Owner/Admin/Staff (Schritte 5-7 — P02 exakt)

- Owner: eigene erstellen (PENDING-Start, tenant=Claim, clientRef/expiresAt-Input IGNORIERT per Spoof-Konvention)/lesen/listen/name+description-aendern/selbst-sperren (mit Grund)/selbst-entsperren (NUR eigene Sperre). VERBOTEN: Admin-Lock-Umgehung, Fremdprofile, immutable Felder, REVOKED-Reaktivierung, clientRef/expiresAt.
- Admin (`admins`): fuer sich + Ziel-User erstellen, fremd lesen (tenant-default, cross-tenant NUR mit Grund + Audit), clientRef/expiresAt setzen, alle zulässigen Transitionen, revoke, renew. VERBOTEN: owner-Umschreibung, tenant-Ueberschreibung, created-Manipulation. KEINE neue Admin-Rolle (Gruppen-Claim wie Bestand).
- Staff (`Staff`, KEIN Admin): Support-Lesen/Audit NUR mit Reason, deaktivieren mit Reason, NUR-selbst-gesperrt-reaktivieren. VERBOTEN: erstellen, PENDING->ACTIVE, Offers/Entitlements/Admin-Verwaltung, terminal-REVOKE. Credential-Grenze nur dokumentiert (P9 unvermischt).

## 5. Create/Idempotency/Read/Update (Schritte 8-11)

- Create: Owner ohne ownerUserId-Einschleusung (Claim gewinnt); Admin mit target_owner; Start IMMER PENDING (nie ACTIVE, nie Login-Nebenwirkung).
- Idempotency: owner+name-UNIQUE -> Duplikat = ProfileConflict (409-Analogie); optionaler idempotency_key: Match -> bestehendes Objekt (sicherer Retry), Mismatch -> 409. KEINE zweite Idempotency-Welt (Conditional-Put + Key-Transport wie Bestand).
- Read: neutral None (fremd/fehlend/geloescht ununterscheidbar); Response-Hygiene (`_public`: KEINE DDB-Keys/Audit-Details/Secrets/Digests/Policies — idempotencyKey intern).
- Update: Allowlist name/description (+reason-Param fuer Admin-Cross-Tenant); unbekannte Felder = ValueError (kein Merge); immutable nie passierbar.

## 6. Lifecycle/Expiry (Schritte 12/13)

- Matrix implementiert (PENDING->{ACTIVE(admin),DISABLED,REVOKED(admin)}; ACTIVE->{DISABLED,REVOKED(admin)}; DISABLED->{ACTIVE(admin/eigen-nur-eigen/Staff-nur-selbst),REVOKED(admin)}; EXPIRED->{REVOKED}; REVOKED terminal; EXPIRED nie Ziel; abgelaufen-nur-renew(admin)).
- DISABLED braucht Grund (Pflicht); disabledBy{Akteur,Rolle,Grund} steuert Reaktivierungs-Recht (Admin-Lock unumgehbar).
- EXPIRED rein abgeleitet (`effective_status`: REVOKED dominiert, sonst Ablaufpruefung) — KEIN Scheduler/EventBridge (autoritativ an jeder Pruefstelle erkannt); P9-MIN-Regel unberuehrt (keine Credential-Logik-Duplikation).

## 7. Selection/Default/Audit (Schritte 14-17 — P05/P06 exakt)

- Header `X-Api-Profile` (P06-Name, kollisionsfrei verifiziert): exakte ID oder leer; UNTRUSTED (verleiht NICHTS).
- Resolution: explizit (Existenz + Owner-oder-Admin-Kompetenz + Tenant + ACTIVE-effektiv, sonst neutral None) vs. Default (0->kein Kontext, 1->auto+Audit, n->explizit-PFLICHT); PENDING/DISABLED/EXPIRED/REVOKED nie Default.
- Credential-Match: Header-Profil MUSS Credential-Profil gleichen (sonst DENIED; kein Override/Raten; Credential autoritativ).
- Audit: requested/resolved/denied/default/explicit/mismatch (Actor/Zeit/Profil/Typ/Outcome/Reason/Correlation; KEINE Secrets).

## 8. P9-Integration/Entitlement/IAM/Routen (Schritte 18-21)

- P9: KEINE Code-Aenderung noetig (Resolver-Protokoll `get_profile` kompatibel — Test `test_credential_bound_to_service_profile` beweist AUTHORIZED gegen P10-erstelltes Profil via P9-Verify). Produktions-Adapter beider Module zeigen auf dasselbe spaetere Tabellendesign (Konvergenz am TF-Gate).
- Entitlement (Schritt 19): KEINE Grant-Mechanik (Scope-Verbot eingehalten); spaetere Bindung via Profil-Referenz vorbereitet (apiProfileId als Anker), keine Struktur vorweggenommen.
- Routen (Schritt 20): KEINE GW-/Handler-Routen angelegt (TF-Verbot + keine toten Pfade); logischer Contract dokumentiert (POST/GET/GET/PATCH `/v1/apiprofiles[...]` im P04-Namensraum; KEINE Live-Claims).
- IAM (Schritt 21): KEINE TF-Aenderung; Bedarfs-Vertrag ( spaeteres Gate): DDB Least-Privilege NUR api-profiles-Tabelle (+gsi-owner implizit): Read (Get/Query) + Write (Put/Update); KEIN dynamodb:*, KEIN Cognito-Admin, KEIN S3, KEIN Terraform, KEINE fremden Tabellen.

## 9. Tests/Regression (Schritte 22-24 — 53 Tests, ALLE GRUEN)

- Spec 1-36 abgedeckt (Owner 1-11, Admin 12-18 + Lock/Expiry/Renew, Staff 19/20 + Support-Regeln, Idem/Tenant 21/22, Selection 23-34, P9/P8/P7-Green via Suite 35/36) + Integrity (Tamper-Felder, unbekannter Status, REVOKED/EXPIRED-Pfade, Enumeration-Neutralitaet, Header-Eskalation, Cross-Tenant, Mismatch).
- Gesamt-Suite: 510 passed (457 + 53), 8 skipped; 15 failed + 1 ERROR IDENTISCH zur P9-Baseline (pre-existing). KEIN Test braucht fremde Credentials/Secrets.

## 10. Folge-Entscheidungen (OPEN, nichts als entschieden dargestellt)

Offer-CRUD/Grant (P11-Kandidat) · Introspection-Endpoint · Pruefpfad-Verdrahtung (P9-Modul -> Route) · Credential-Management-Endpoints · Worker-Sandboxing · `Admin`-Migration · Tabellen/IAM-Provisionierung (Deployment-Gate) · Default-Ablauf-Policy.

**HARD STOP (keine Implementierung ueber diesen Contract hinaus, keine Mutation).**
