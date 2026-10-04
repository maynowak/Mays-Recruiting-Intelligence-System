# RIS-PRODUCT-PLATFORM-IMPLEMENTATION-READINESS-06 — Readiness & Interface Contract

STATUS: Contract entschieden (KEINE fachliche Implementierung, KEIN AWS, KEIN TF, KEINE Cognito-/DB-/Gateway-Mutationen, KEINE APIProfile/Offers/Credentials angelegt/erzeugt, KEINE Secrets, KEINE Routen veraendert/implementiert, KEINE neuen AWS-Ressourcen, KEINE finalen API-Routen implementiert)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, 5bac31d
- Basis (verbindlich, NICHT veraendert): P01 (Standards/Rollen) + P02 (APIProfile) + P03 (Credential) + P04 (Offer/Pruefpfad/CRUD/Capability/Worker/Cleanup) + P05 (Groups/Offer-final/Modul/Selection/Introspection/Boundaries) + Bestand (Code, TF-GW/Cognito/SQS/Lambda/DDB, Gates 10-14, kanonische Docs).
- Methode: Bestandsinventar (A-E) + Interface-Entscheidungen R2-R8 + Readiness-Urteil R9; Klassen DECIDED/OPEN/DEFERRED/NOT IN SCOPE. Nicht-Belegbares = OPEN.
- Classification: GREEN (Readiness, R9) mit markierten OPEN-Implementierungsdetails.
- Mutationen: KEINE (verifiziert).
- Git: nur diese beiden Reports (s. Commit).
- Next: erstes Implementierungs-Gate R9 -> HARD STOP.

## P6-R1 — Implementation Readiness Inventory (Bestand -> Klasse)

| Baustein | Befund (EXISTING) | Klasse | Folgerung |
|---|---|---|---|
| Cognito (Pool/Client/Domain/Gruppen) | Pool + App-Client (USER_PASSWORD_AUTH) + Domain + 7 Gruppen-Objekte; Gruppen ohne Checks | A) direkt wiederverwendbar | Identity unveraendert; Gruppen-Semantik kommt mit Rollen-Implementierung |
| UserProfile (Tabelle + POST/GET/PUT + Guards) | v1 live, sub-gebunden, Spoof-immun, 409-Semantik | A) direkt wiederverwendbar | Muster (Conditional Write, 409, Owner-Bindung) als Vorlage fuer Profile-/Offer-CRUD |
| Entitlements (Tabelle + Handler-Gates + Zeitfenster) | Hash entitlementId + GSI userId/agentId; Pruefung NUR Handler; Pipeline ohne | B) erweiterbar | Profil-Bindung braucht zusaetzlichen Zugriffspfad (apiProfileId-Index = C); Worker-Nachpruefung spaeter |
| Catalog/Registry/Discovery/Eligibility | DDB-Tabelle + Adapter + Registry + Discovery + Pipeline (Descriptor-Kompatibilitaet) | A) Kern + B) Eligibility (Status-Norm + Entitlement-Hook spaeter) | Ausfuehrungspfad bleibt; Normierung R6 zuerst |
| GW HTTP API + JWT-Authorizer | Payload-2.0-Proxy; JWT (Audience/Issuer); Routen-Tabelle bekannt; Execute handler-intern | A) direkt wiederverwendbar | JWT-Pfad unangetastet; neuer Namensraum spaeter (C) |
| Agent Lambda (Runtime) | Eine Lambda, Env-Verdrahtung, SQS-Mapping Batch 5 | A) Runtime + B) Auth-Modul-Einschubpunkt | Pruefmodul-Dock exakt bestimmbar (vor Business-Dispatch) |
| SQS / WorkItem | Queue + DLQ/Redrive + KMS; Pflichtfelder workId/type/tenantId/idempotencyKey; workId-Dedup; Attempt-Kette | A) direkt wiederverwendbar | Aktivierungs-Semantik + Idempotenz-Anker stehen; Provenance-Felder = C |
| DynamoDB | 6 Tabellen (work/agent-state/user-profile/catalog/entitlements/jobsearches), PAY_PER_REQUEST, GSIs | A) Muster + C) neue Tabellen (api_profiles, offers, credential-Metadaten + GSIs) | Speicher-Design folgt bestehenden Mustern (Hash + GSI + Conditional) |
| IAM-Strukturen | Least-Privilege pro Funktion/Tabelle (+Logs); Extend-Muster belegt (Gate 12/14) | B) erweiterbar | Neue Tabellen = neue Policen nach gleichem Muster |
| Handler-Gates | 401/403/404-Semantik + Entitlement-Filter + Tenant-Checks (EXISTING-Praxis) | A) direkt wiederverwendbar | Vergabe-/CRUD-/Pruef-Gates kopieren Muster, nicht Logik |
| Audit/Logging | Strukturierte Lambda-Logs + CloudWatch-Gruppen + Trail-Mgmt + Shred-/Maskierungs-Praxis (Gates 10/11/14) | A) Faehigkeit + B) Domaenen-Events (neue Event-Typen nach P03-§15/P04-R3) | Keine neue Pipeline noetig; Event-Katalog erweitern |
| Correlation IDs | requestId (Execute) + workId + processing/execution/attempt-Chain (Envelope) + GW-/Lambda-Request-IDs (Plattform) | B) erweiterbar | IDs EXISTIEREN; Kette durchreichen/verdrahten (kein neues Schema — P05-R3 bestaetigt) |
| Idempotency-Muster | Conditional Writes (Profil-409, workId-Dedup) + Client-idempotencyKey-Transport (Execute/WorkItem) | A) direkt wiederverwendbar | Grant-/CRUD-Idempotency nach gleichem Muster (P04-R3/R5) |
| Agent-Rechte im Worker | Agent-Code laeuft IN-PROCESS mit Worker-Rolle (volle Tabellen/Queue/Logs) | D) technische Luecke | Sandboxing-Gap bleibt sichtbar (R8 Pos. 10); keine Rechteausweitung darueber hinaus |
| Profil-Auswahl-Traeger | KEIN X-Header im Bestand (Kollisions-Check negativ) | E) OPEN -> HIER ENTSCHIEDEN (R3: `X-Api-Profile`) | Namensraum frei, keine Migration |

## P6-R2 — Credential Verification Interface (DECIDED, Contract ohne Code)

- Interface-Name (DECIDED): `verify_api_credential` (Modul-Funktion, Python-Laufzeit; Signatur illustrativ-verbindlich: `verify(request) -> Decision`; exakte Typen = Implementierung innert dieser Felder).
- INPUT (alle Pflicht ausser markiert): bearerCredential (Rohwert, Speicher-nur-Aufruf) · requestedCapability/operation · routeContext (Route + Methode) · requestTime · request/correlationId (durchgereicht, P05-R3) · selectionHint OPTIONAL (nach R3; UNTRUSTED).
- OUTPUT A — AUTHORIZED (ausschliesslich): { userId, tenantId, apiProfileId, credentialId, entitlementRefs[], effectiveScope (Schnitt-Ergebnis), resolution {selectedBy, resolvedAt, default?}, auditRef } — KEIN Rohwert, KEIN Digest, KEINE Secrets, KEINE JWT-Inhalte, KEINE fremden Profile/Tenants, KEINE Ablehnungs-Details ueber Code hinaus.
- OUTPUT B — 401 UNAUTHORIZED: unbekannt / ungueltig / Format-falsch / nicht-authentifizierbar (kein Unterschied nach aussen — ein Code, kein Grund).
- OUTPUT C — 403 FORBIDDEN: bekannt-aber-disabled/revoked · Profil-nicht-ACTIVE · Credential/Profil-abgelaufen · Entitlement-fehlt · Capability-nicht-erlaubt · Agent-nicht-ausfuehrbar (Codes je Klasse erlaubt, KEINE Orakel-Begruendungen).
- Idempotenz des Pruefens (DECIDED): Entscheidung rein lesend, wiederholbar gleich (bei gleichem Zustand); Nebenwirkung AUSGELAGERT: lastUsedAt-Fortschreibung als Fire-and-Forget, darf Request NIEMALS scheitern lassen.
- Cache-Verbot (DECIDED): KEIN Positiv-Cache (TTL>0 verboten — Revocation-Bruch); KEIN Negativ-Cache noetig (Lookup billig).
- Audit-Verantwortung (DECIDED): Modul emittiert je Pruefung ein Audit-Event (Erfolg + Misserfolg, Misserfolg ratenbegrenzt; Felder PROMPT-03-§15; secrets-frei).
- Fehlersemantik (DECIDED): 401 vs. 403-Trennung analog Handler + PROMPT-03-C6; Transport-Fehler (DDB-unerreichbar) = 503-neutral + Alarm (kein Fail-open, kein Fail-als-403).

## P6-R3 — APIProfile Selection Interface (DECIDED, inkl. Headername)

- Selection-Header (DECIDED): `X-Api-Profile` (Kollisions-Check negativ — kein X-Header im Bestand; GET-faehig, log-sparsam; Body-Profil-ID wird NIEMALS als vertrauenswuerdig behandelt).
- Erlaubte Werte: exakte apiProfileId ODER leer (Default-Wunsch). Alles andere (Namen, Prefixe, Wildcards) UNGUELTIG (-> wie unbekannt).
- Fehlender Header -> Default-Regel (P05-R4: genau-1 -> auto (+Audit-Vermerk); 0 -> KEIN Kontext + Anlage-Hinweis (KEIN Auto-Provision); n -> explizit PFLICHT (400/neutral + Introspection-Hinweis)).
- Mehrere ACTIVE -> explizit PFLICHT (kein Raten — entschieden P05, hier technisch verankert).
- Unbekanntes Profil -> 404-neutral. FREMDES Profil (existiert, nicht-eigen, keine Kompetenz) -> IDENTISCH 404-neutral (kein Orakel — entschieden). DEAKTIVIERTES (eigenes, nicht-ACTIVE) -> 404-neutral am Use-Time (Status erfährt Owner via HUMAN-Introspection — P05-R5; kein Use-Time-Leak).
- Credential-Kontext: KEINE Selection noetig (Key->Profil automatisch); mitgegebene Profil-ID MUSS matchen, sonst 403-neutral (kein Override).
- clientRef-Regel (DECIDED technisch): Profil OHNE clientRef = in jedem Client-Kontext verwendbar (solange NULL-Policy das zulaesst — DEFAULT restriktiv spaeter entscheidbar, OPEN); Profil MIT clientRef = NUR dort (Mismatch -> 403-neutral + Audit).
- Audit-Triple (DECIDED): selectionHint (roh-UNTRUSTED, gekuerzt) + resolutionErgebnis (Profil-ID/Status/Owner-Check/Tenant-Check) + authorizationErgebnis (Codes) — immer gemeinsam, secrets-frei.

## P6-R4 — Introspection Response Contract (DECIDED, logische Struktur ohne URL)

```
{ context: human|profile|credential,
  subject: { userId, tenantId },                                  # immer
  allowedProfiles?: [{ apiProfileId, name, status }]              # NUR human (Auswahl-UX)
  profile?: { apiProfileId, name, status, clientRef?,             # NUR profile/credential
              expiresAt?, offerRefs? },
  capabilities: [{ agentId, name, capabilities[],                  # immer (positiv-only)
                   scopeRestricted: bool, expiresHint? }],
  offers?: [{ offerId, name, description }],                       # vergebbar/angezeigt, KEINE Preise
  validity: { checkedAt, credentialExpiresAt?, profileExpiresAt? },# immer (Hinweise, keine Policy-Details)
  resolution: { selectedBy: default|explicit|credential,           # immer (Kontext-Nachweis)
                resolvedAt } }
```

- HUMAN: subject + allowedProfiles + user-weite capabilities (KEIN fremdes Profil-Detail).
- PROFILE: genau EIN aufgeloestes Profil (+ dessen capabilities/offers/validity).
- CREDENTIAL: wie PROFILE + Credential-Label/ID + Scope-Hinweis (Wert nie).
- Optional: description/clientRef-Label/offers/scopeRestricted/expiresHints (kontextabhaengig); Pflicht: context/subject/capabilities-array (ggf. leer)/validity.checkedAt/resolution.
- Immutable (Stamm): IDs/Namen/Owner/clientRef-Zuordnung. Dynamisch (pro Request berechnet): capabilities/validity/resolution/allowedProfiles-Status.
- Serverseitig berechnet: ALLES ausser selectionHint. Client DARF NICHT liefern (und wird ignoriert/ablehnt bei Versuch): Entitlements, Scopes, Status, Owner, Tenant, Ablaufdaten, Capability-Listen.
- Verbote (DECIDED): negative Agentenlisten · Orakel-Begruendungen · Secrets/Digests/JWTs · interne AWS-Details (Tabellen/Rollen/ARNs) · exakte Pruef-Schwellen/Regeln.
- URL: KEINE festgelegt (P04-R2-Namensraum-Prinzip gilt; Pfadwahl = Implementierung).

## P6-R5 — Offer -> Entitlement -> APIProfile Boundary (DECIDED Vergabe-Sequenz)

Fachliche Reihenfolge (verbindlich, je Vergabe-Akt):
1. Actor authentifizieren (JWT/Admin-Session — KEIN Credential als Management-Auth). 2. Actor autorisieren (NUR Administrator — P04-R1/R3). 3. Offer pruefen (Existenz + ACTIVE — INACTIVE = Abbruch). 4. Offer-ACTIVE bestaetigt (sonst Abbruch, Audit grant-denied). 5. ALLE agentIds gegen Katalog pruefen (Existenz). 6. Agent-Status pruefen (nur ACTIVE faehig — R6-Regel; unfähige = Abbruch). 7. Ziel bestimmen (User-weit ODER APIProfile — exklusiv je Akt; Profil muss ACTIVE + tenant-konsistent sein). 8. Zeitfenster bestimmen (Pflicht; Default-Policy innert 366-Tage-Rahmen = Implementierungs-Parameter). 9. Entitlement(s) erzeugen (je agentId EINES; TransactWrite-bündig wo noetig). 10. Audit schreiben (grantId als Anker: offerId + Ziel + Fenster + Actor + Grund verlinkt alle erzeugten Entitlements).
- Offer-Aenderung NICHT rueckwirkend (P04 bestaetigt — hier technisch: kein Sync-Job, keine Kaskaden-Updates). INACTIVE blockiert nur Neues. Bestand bis Ablauf/Entzug.
- Transaktion/Idempotency (DECIDED): Validierung VOLLSTAENDIG VOR jeder Schreiboperation (all-or-nothing — KEINE Teilvergabe bei teilweise ungueltigen agentIds; Begruendung: keine halb-bestueckten Offers, klare Audit-Aussage); Grant-Akt idempotent via Client-grant-Key (Duplikat = bestehende Entitlements referenzieren, KEINE Doppel-Zeilen); Doppeleinreichung gleichen Fensters+Umfangs = idempotente Rueckgabe (KEINE stille Verlaengerung — Verlaengerung = eigener expliziter Akt).
- Bereits vorhandenes Entitlement (identisch): zurueckgeben + referenzieren (kein Duplikat). Ueberlappend-abweichend: NEUES Entitlement nur bei expliziter Teilung (sonst Ablehnung mit Hinweis — kein Ratespiel).

## P6-R6 — Status Normalization Interface (DECIDED, kanonisch)

Befund (EXISTING, verifiziert): Katalog-Status in GROSSBUCHSTABEN (Adapter-Map: ACTIVE/INACTIVE/DEPRECATED/RETIRED/FAILED/REGISTERED/AVAILABLE; Test-/Seed-Praxis kleinbuchstaben `active`) vs. Handler-Vergleich klein (`'active'`, handler.py:606/779) vs. Adapter-Default Unbekannt->ACTIVE (fail-open, catalog_adapter.py:186) vs. Pipeline-Hartblock NUR RETIRED/DEPRECATED (eligibility.py:74-83).
- Kanonische Mengen (DECIDED — nur Belegtes uebernommen): AUSFUEHRBAR = {ACTIVE}. NICHT ausfuehrbar = {INACTIVE, DEPRECATED, RETIRED, REGISTERED, AVAILABLE, FAILED} (pre-ACTIVE/failed = nicht-ausfuehrbar — entschieden statt offen). UNBEKANNT = BLOCKIERT (fail-closed — BEWUSSTE Abweichung vom heutigen Default-ACTIVE; als Verhaltens-Aenderung fuer das Implementierungs-Gate markiert).
- Normalisierungsgrenze (DECIDED): GENAU EINE zentrale Normalisierung (upper/strip/trim -> kanonisch; unbekannt -> BLOCKED) am Katalog-Eingang (Adapter + Handler-Gate + Pipeline/Worker + Discovery + Introspection nutzen DIESELBE Funktion — keine lokalen Vergleiche mehr). Persistierte Werte werden NICHT stillschweigend umbenannt (DDB-Bestands-Scan VOR Migration im Implementierungs-Gate).
- Fail-closed (DECIDED): Unbekannt/leer/verstümmelt = nicht-ausfuehrbar + Audit-Alarm (Datenqualitaets-Signal, kein stilles Weiter).
- Auswirkungen (DECIDED): Discovery surft NUR ACTIVE fuer Ausfuehrungs-Pfade (Introspection zeigt Nicht-Aktive GAR NICHT — Positiv-only R4); Eligibility: nicht-ACTIVE -> INELIGIBLE mit Grund (heutiger INACTIVE-Quirk wird damit GEHEILT — als Aenderung markiert); Pipeline/Worker: gleiche Regel (kein Sonderweg); Introspection: Abwesenheit = Unverfuegbarkeit (kein Status-Leak).

## P6-R7 — Implementation Boundary / Security Check (DECIDED-Matrix)

| Grenze | Vertrauenswuerdig | Nicht vertrauenswuerdig | Pruefung (wo/wie spaeter) |
|---|---|---|---|
| Human Request (JWT) | Cognito-Signatur + Authorizer (Audience/Issuer) | Claims jenseits sub/tenant/groups; Body-Identitaeten | Authorizer (Kante) + Handler-Claims-Extrakt (Spoof-Ignoranz EXISTING) |
| Profile Selection (`X-Api-Profile`) | NICHTS (reiner Hinweis) | Gesamter Header-Inhalt | Resolution (Existenz/Owner/Status/Tenant) VOR Authorization |
| Credential (Bearer) | NUR nach Digest-Lookup + Status + Ablauf | Rohwert VOR Pruefung; mitgegebene Kontext-Behauptungen | Verify-Modul R2 (pro-Request, kein Cache) |
| APIProfile (Objekt) | NUR nach Resolution (Owner/Status/Tenant verifiziert) | IDs/Felder aus Client-Hand | Resolution R3; Status-Dominanz R4/P03 |
| Entitlement (Zeilen) | NUR frisch gelesene (Handler/Worker) | Mitgegebene/erratene Rechte; Offer-Name als Rechtsbeweis | Server-Read + Union/No-Expansion (P02/P03) |
| SQS Event | NUR Queue-Herkunft (IAM-geschrieben) | JEGLICHER Inhalt (tenant/agent/capability wortwoertlich) | Worker-Nachpruefung (P04-R5-A) + Provenance-Vergleich |
| WorkItem (Felder) | NUR nach Validierung + NUR workId als Dedup-Anker | tenantId/agentId/capability/payload als Auth-Beweis | Pflichtfeld-Check (EXISTING) + Entitlement-Re-Check (spaeter) |
| Agent Catalog | Katalog-Tabelle + normalisierter Status (R6) | Client-behauptete Agent-Faehigkeit | Zentrale Wahrheit; Deaktiv-Sperre |
| Agent Runtime | Pipeline-Entscheidung (nach A-Nachpruefung) | Agent-Code als Sicherheits-Prinzipal (GAP: teilt heute Worker-Rolle) | spaeter Sandboxing (R8-10); bis dahin KEINE Rechteausweitung ueber Worker hinaus dokumentieren |

Explizit bestaetigt (DECIDED): Selection verleiht KEINE Rechte · Queue-Nachricht verleiht KEINE Rechte · WorkItem-Felder ersetzen KEINE Autorisierung · Credential repraesentiert NUR sein gebundenes Profil · Katalog = zentrale Agent-Wahrheit · Entitlements = einzige Berechtigungsquelle · Worker prueft spaeter erneut (A-Regel) · Agent-Worker-Rechte-Gap BLEIBT SICHTBAR (D-Luecke R1) · KEINE Rechteausweitung via Scope/Offer/Profil (No-Expansion ueberall).

## P6-R8 — Implementation Order (bestaetigt + begruendet)

| # | Schritt | Abhaengigkeit | Warum hier (Security/klein/testbar/rollbackfaehig) |
|---|---|---|---|
| 1 | Status Normalization / fail-closed | Keine (reine Lese-Regel + Tests) | Kleinster Change; heilt aktive Fehlstelle (INACTIVE-Quirk, Default-ACTIVE); da
...[truncated 2085 chars]