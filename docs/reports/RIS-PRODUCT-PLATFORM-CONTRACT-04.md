# RIS-PRODUCT-PLATFORM-CONTRACT-04 — Offer / Verification Path / CRUD / Capability / Worker-Auth / Group-Cleanup

STATUS: Contract entschieden (KEINE Implementierung, KEIN AWS, KEIN TF, KEINE Cognito-/DB-/Gateway-Mutationen, KEINE neuen Ressourcen, KEINE Credentials erzeugt)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, b52e4a2
- Basis (verbindlich, NICHT veraendert): PROMPT-01-Discovery + PROMPT-02-APIProfile-Contract + PROMPT-03-Credential-Contract + Bestand (Code, TF-GW/Cognito/SQS/Lambda, Gates 10/11/12/13A/14, kanonische Docs). Alle 18 Basisentscheidungen gelten unveraendert (Konfliktpruefung §7: KEIN Widerspruch erzeugt).
- Methode: Repository-/Code-Befunde je Paket + Entscheidung mit Begruendung; Klassen DECIDED/OPEN/DEFERRED/NOT IN SCOPE (+ GREEN/OPEN-Status je Bereich). Nicht-Entscheidbares bleibt OPEN.
- Classification: GREEN (Contract) mit OPEN-Anteilen (ausdruecklich markiert).
- Mutationen: KEINE (verifiziert: kein AWS/TF/Cognito/DB/Gateway-Kontakt, keine Secrets, keine Keys).
- Git: nur diese beiden Reports (s. Commit).
- Next: empfohlene Reihenfolge §8 -> HARD STOP.

## R1 — Minimales Offer-Modell (DECIDED als Contract, GREEN)

Befund: Offer/Product/Plan/Tariff/Package/Subscription als PRODUKT-Modell = 0 Treffer in Code/TF/kanonischen Docs (einzige Treffer sachfremd: Lambda-Deployment-"Package", Python-"Package", MO-Bestellpositionen unitPrice, DDB billingMode, Environment-`product`-Metadaten). Entitlements EXISTIEREN (Tabelle + Handler-Gates). Definitionsluecke wird hier minimal geschlossen — ohne Preis/Billing/Payment (ausdruecklich VERBOTEN in v1: KEINE Preis-/Waehrungs-/Billing-Felder; Monetarisierung = NOT IN SCOPE).

Offer-Contract (minimal, fuer Kette Offer -> Entitlement -> APIProfile -> Credential ausreichend):

| Feld | Pflicht | Bedeutung | Veraenderlich | Actor |
|---|---|---|---|---|
| offerId | Ja | Stabile Offer-Identitaet (systemvergeben; Format = Implementierungsdetail) | NEIN (immutable) | System |
| name | Ja (UNIQUE) | Menschenlesbarer Angebotsname; Eindeutigkeit VERPFLICHTEND (sonst Fehlvergabe durch Verwechslung) | Ja (Admin; Umbenennung auditiert) | Administrator |
| description | Nein | Zweck/Umfang als Freitext | Ja | Administrator |
| status | Ja | ACTIVE (neu vergebbar) / INACTIVE (nicht mehr vergebbar). KEIN PENDING/EXPIRED/REVOKED auf Offer-Ebene (Begruendung: Enzug geschieht an ENTITLEMENTS, nicht am Katalogeintrag; Ablauf lebt am Entitlement-Fenster) | Ja | Administrator |
| agentIds | Ja (min. 1) | Enthaltene Agenten-Referenzen (gegen Katalog pruefbar) | Ja (Admin; Aenderung wirkt NUR auf KUENFTIGE Vergaben, nie rueckwirkend) | Administrator |
| createdAt/updatedAt | Ja | System-Zeiten | System | System |

- Ownership/Administration (DECIDED): Owner = RIS-Plattform (KEIN per-Offer-Owner — Offers sind Katalog, kein Besitzobjekt); verwalten NUR Administrator; Staff KEINE Offer-Aktionen (PROMPT-02-Verbotsliste gilt); Lesbarkeit: Offer-Katalog fuer Anzeige lesbar (vgl. R4), Vergabe nur Admin.
- Vergabe-Semantik (DECIDED): Offer-Vergabe = Admin-Akt erzeugt Entitlements (user-weit ODER profil-gebunden, mit Zeitfenster); Offer-INACTIVE blockiert NUR neue Vergaben; bereits erteilte Entitlements laufen UNVERAENDERT weiter (separater Entzug noetig — kein implizites Entziehen durch Katalog-Aenderung).
- Negationen (DECIDED): Offer ≠ APIProfile (Katalog vs. Kontext) ≠ Credential (Recht vs. Nachweis) ≠ UserProfile (Angebot vs. Personendaten) ≠ Tenant (Angebot vs. Isolation). Kein Kauf-/Subscription-Fluss (NOT IN SCOPE).

## R2 — Credential Verification Path (DECIDED: Einfuehrungspfad B, A DEFERRED, GREEN)

Befund (EXISTING): HTTP API (Payload 2.0, AWS_PROXY -> Agent-Lambda); JWT-Authorizer (Authorization-Header, Audience = App-Client, Issuer = Pool); Routen: /health (NONE) + /platform, /me, /me/profile x3, /agents (alle JWT); Orders-Routen (JWT, eigenes Modul); Agent-Execute NUR handler-intern (KEINE GW-Route); 401 (unauth) / 403 (Entitlement fehlt) / 404-Semantik im Handler etabliert.

| Kriterium | A) REQUEST-Authorizer (Custom, GW-Kante) | B) Lambda-interne Pruefung (nach GW) |
|---|---|---|
| JWT-Grenze | Unberuehrt (eigene Routen/Authorizer) | Unberuehrt (eigene Routen, JWT-Routen unangetastet) |
| Bestehende Human-JWT-Aufrufe | Keine Auswirkung | Keine Auswirkung |
| 401/403 | GW-nativ (Authorizer-Policy) | Handler-Semantik (EXISTING 401/403, PROMPT-03-C6) |
| Credential-Lookup / Profil-State / Entitlements | Eigene Lambda + IAM + DDB-Anbindung noetig | Direkte Wiederverwendung (Handler-Gates, EXISTING-Muster) |
| Revocation-Wirksamkeit | NUR mit Cache-TTL 0 sicher (sonst Fenster!) — Pflicht-Parameter | Sofort (pro-Request, kein Cache — PROMPT-03-C4) |
| Audit | GW-Logs + Authorizer-Logs (zwei Stellen) | Handler-/App-Logs (eine Stelle, EXISTING-Praxis) |
| Performance | -1 Hop bei Ablehnung (Edge), +1 Hop (Authorizer-Lambda, Cold Starts) bei Erfolg | Keine Extra-Hops; Ablehnung kostet Lambda-Laufzeit |
| Secret-Handling | Gleich (Digest-Vergleich, nie Klartext) | Gleich (Digest-Verglich, nie Klartext) |
| Least Privilege | Neue IAM-Rolle (Authorizer braucht DDB-Read) | Keine neue Rolle (EXISTING Lambda-Rolle, ggf. eng begrenzte Lese-Erweiterung spaeter) |
| Komplexitaet | NEU: Authorizer-Lambda + Policy-Modell + TTL-Disziplin + separater Deploy-Pfad | MINIMAL: dediziertes Auth-Modul im Handler (kein Inline in Business-Logik) |

ENTSCHEIDUNG (begruendet): Einfuehrungspfad = B (Lambda-intern, dediziertes Auth-Modul, pro-Request, TTL-frei) — kleinste Aenderung, EXISTING-Gate-Muster, Revocation sofort wirksam, keine neue Infrastruktur (passt zur Gate-Regel "keine neuen Build-Services ohne Beleg"). A = DEFERRED mit expliziten Triggern (Missbrauchs-Traffic-Kosten an der Kante; GW-seitiges Throttling pro Credential; Mehrfach-Nutzung durch kuenftige Services). KEIN Hybrid zum Start (kein Grund, BEIDE Pfade zu betreiben; Hybrid waere doppelte Prueflogik = doppelte Fehlerflaeche).
- Routen-Prinzip (DECIDED): Credential-autorisierte Zugaenge erhalten EIGENEN Routen-Namensraum (Contract-Vorschlag, keine Implementierung — z.B. spaeteres `/v1/...` vs. bestehende Human-Pfade); bestehende JWT-Routen werden NICHT auf Key-Auth umgestellt/aufgeweicht. Dispatch Mensch-vs-Maschine NIEMALS per "probier JWT, sonst Key" auf derselben Route (sonst Orakel-/Downgrade-Risiko) — Trennung per Route, nicht per Rate-Versuch.

## R3 — APIProfile CRUD Contract (DECIDED, GREEN; Routen nur Contract-Vorschlag)

Operationen x Rollen (PROMPT-02-Rollen spiegeln sich exakt):

| Operation | Owner (eigenes Profil) | Admin | Staff | User (fremd/kein Profil) |
|---|---|---|---|---|
| Create (fuer sich) | ERLAUBT (PENDING-Start) — KEIN Self-Provisioning durch blossen Login (DECIDED: Anlage = expliziter Akt, nie Login-Nebenwirkung) | ERLAUBT (fuer sich + fuer Ziel-User, createdBy=Admin, owner=Ziel) | VERBOTEN (kein allgemeines Erstellen) | VERBOTEN |
| Read (eigen / alle) | Eigene (Metadaten; Secrets nie) | Alle (default tenant-gefiltert; tenant-uebergreifend NUR mit Grund + Audit) | Lesen im Support-Fall (auditiert) | Nur eigene Kontexte (keine Fremd-Profile) |
| Update name/description | ERLAUBT (auditiert) | ERLAUBT | VERBOTEN | VERBOTEN |
| clientRef/expiresAt/owner-nahe Felder | VERBOTEN | ERLAUBT (admin-only, auditiert) | VERBOTEN | VERBOTEN |
| Deactivate (ACTIVE->DISABLED) | ERLAUBT (eigene, reversibel, auditiert — Selbst-Sperrung) | ERLAUBT | ERLAUBT (mit Grund, auditiert) | VERBOTEN |
| Reactivate | ERLAUBT (eigene; NICHT nach Admin-Sperre ohne Admin — Sperr-Akteur-Regel PROMPT 02) | ERLAUBT | NUR selbst-gesperrte (PROMPT 02) | VERBOTEN |
| Revoke (terminal) | VERBOTEN (Endgueltigkeit = Admin-Akt) | ERLAUBT | VERBOTEN | VERBOTEN |
| Expiration | System-Ableitung (+ Admin-Verlaengerung) | Verlaengerung | — | — |
| Entitlements/Offer am Profil | VERBOTEN | ERLAUBT (Vergabe/Entzug) | VERBOTEN | VERBOTEN |

- Feldklassen (DECIDED, aus PROMPT-02-Objektvertrag): immutable = apiProfileId/ownerUserId/createdAt/createdBy (+ apiProfileId-Format System); owner-mutable = name/description (+ Deactivate/Reactivate-eigen); admin-only = clientRef/status (ausser Owner-Selbstsperre)/expiresAt/Entitlement-Bindung; system-managed = createdAt/updatedAt/updatedBy/Status-Ableitungen (EXPIRED).
- Idempotency (DECIDED): Duplikat-Schutz ZWEISTUFIG — (1) name UNIQUE je Owner => 409 bei Doppel-Anlage (Analogie POST /me/profile 409, EXISTING-Semantik); (2) clientseitiger Idempotency-Key (RECOMMENDED, Analogie WorkItem-idempotencyKey + Conditional Writes) fuer sichere Retries (Antwort: 201 neu vs. bestehendes Objekt referenzieren — exakte Statuswahl = Implementierungsdetail innert dieser Regel).
- Tenant Isolation (DECIDED): Owner-Operationen strikt im eigenen Tenant-Kontext (JWT/sub+tenant); Admin-Cross-Tenant NUR begruendet + auditiert; Staff-Cross-Tenant NIE ohne Support-Fall + Audit.
- Routen (NUR Contract-Vorschlag, KEINE Implementierung): `POST /v1/apiprofiles`, `GET /v1/apiprofiles[/{id}]`, `PATCH /v1/apiprofiles/{id}`, `POST /v1/apiprofiles/{id}/{disable,reenable,revoke,renew}` — Namensraum `/v1` folgt R2-Routen-Prinzip; finale Pfade/Methoden = Implementierungs-Gate.

## R4 — Capability / Introspection Contract (DECIDED: separater Read-Only-Contract, GREEN)

Befund: /platform = statisch {name,version,environment} (KEINE Capabilities); /me = Identitaets-Echo; /me/profile = Existenz-Signal (200/404); /agents = user-kontext Positivliste (OHNE Profil-/Scope-/Begruendungs-Dimension). KEINE Route kann Profil-/Credential-Kontext + effektive Entitlements + Offer-Darstellung abbilden, ohne ihre Human-JWT-Semantik zu verwischen.
ENTSCHEIDUNG: SEPARATER read-only Introspection-Contract (kein Ausbau bestehender Routen — /agents bleibt user-kontext Positivliste):
- Kontexte (DECIDED): Human-JWT (user-weite Sicht) + APIProfile-Kontext (Profil-Sicht; Auswahl-Mechanismus fuer Menschen = OPEN — Default-Profil vs. explizite Wahl ist VOR Implementierung zu entscheiden) + Credential-Kontext (Key -> Profil automatisch, inkl. Scope-Einschraenkungs-Hinweis).
- Inhalt (DECIDED): effektive Entitlements (Union + Scope-Schnitt, PROMPT-03-C5) + verfuegbare Agents (aus zentralem Katalog gefiltert) + Offer-Anzeige (Name/Beschreibung VERGEBBARER Offers — KEINE Preise, existieren nicht) + Gueltigkeits-Hinweise (Ablauf, NICHT Secrets). NUR Positives (erlaubt + demnaechst-ablaufend); NEGATIVES WIRD NICHT BEGRUENDET (kein Orakel: "Agent B ✗" ohne Warum — Fortschreibung der /agents-Regel; Backend-403/404 bleiben massgeblich).
- Isolation (DECIDED): tenant/user/profile-gefiltert serverseitig; credential-gebundene Sicht zeigt NUR eigenes Profil; Caching clientseitig zulaessig NUR mit Gueltigkeits-Hinweis (autoritativ bleibt jede Ausfuehrungs-Pruefung).
- Musterwahl (DECIDED): Positive-Liste (EXISTING /agents) + Scopes-/Entitlements-Selbstauskunft (OpenRouter-GET-/key-Analogie, VENDOR PATTERN) + UI-Flags NUR als Anzeige-Schalter (niemals Sicherheitsentscheidung). KEINE neue Permission-Welt (Entitlements bleiben einzige Quelle).

## R5 — Worker-Path Authorization (DECIDED: A + auditiver Provenance-Ansatz, GREEN als Boundary)

Befund (EXISTING, agents/runtime/pipeline.py + base.py + TF): SQS = Aktivierung (Batch 5, DLQ via redrive/maxReceiveCount, KMS, 14d-Retention); WorkItem-Pflicht = workId/type/tenantId/idempotencyKey (fehlend -> ValueError -> Retry -> DLQ); Dedup-Anker = workId-Conditional-Write (idempotencyKey wird GESPEICHERT, aber NICHT als Dedup-Schluessel verwendet — gleiche Keys bei verschiedenen workIds werden NICHT erkannt); KEINE Signatur/Provenienz/Auth-Felder (tenantId/agentId wortwoertlich aus Queue-Nachricht); Eligibility = Deskriptor-Kompatibilitaet OHNE Entitlements ("future checks"); Agent-Code laeuft IN-PROCESS mit der vollen Worker-Lambda-Rolle (KEINE separaten Agent-Rechte — CURRENT GAP, s.u.).
ENTSCHEIDUNG (Hybrid aus Architektur folgend — A erzwingt, B belegt, KEIN blosses Vertrauen):
- A) Entitlement-NACHPRUEFUNG am Worker VOR Ausfuehrung (DECIDED Produktionsregel): userId+agentId+Zeitfenster frisch aus Entitlement-Quelle lesen (nicht aus Nachricht uebernehmen); CLOSED-TOCTOU so weit wie moeglich (Pruefung am Attempt, nicht nur am Execute); Kosten (DDB-Read pro Record) sind Sicherheitskosten, kein Gegenargument.
- B) Provenance-Snapshot (DECIDED auditiv, NICHT als Ersatz): Sync-Pfad legt Authorisierungs-Herkunft ins WorkItem (welches Entitlement/welcher Profil-Kontext/welcher Entscheid-Zeitpunkt — FELDER spaeteres Design, kein Format hier); Worker vergleicht + protokolliert Mismatch (Abweichung = Alarm, nicht stilles Weiter). Signierte Provenance = DEFERRED (Schluessel-Verwaltung erst bei Bedarf; unsigned Snapshot + A-Nachpruefung genuegt vorerst).
- C) verworfen (kein drittes Modell aus Architektur begruendbar).
- Grenzsaetze (DECIDED): SQS-Event = Aktivierung, KEINE Autorisierung; Queue-Schreibrecht = IAM-Grenze (nur Worker-Rolle + Admins — EXISTING redrive/DLQ-Setup); WorkItem-Felder (tenantId/agentId/capability) = UNVERTRAUT bis Nachpruefung; Duplikat (gleiche workId) = KEIN neuer fachlicher Run (EXISTING Conditional Write bleibt); Retry = weiterer Attempt DERSELBEN Verarbeitung (EXISTING attempt_no-Kette).
- CURRENT GAP (ausdruecklich, DEFERRED an Implementierung): Agent-Code teilt heute die Worker-Infra-Rechte (in-process). Produktions-Boundary verlangt spaeter Agent-Sandboxing/Least-Privilege (Daten-Kontext statt Rollen-Kontext) — Design VOR Produktiv-Credentials (vgl. PROMPT-03-C6/P4-R5-Verknuepfung).

## R6 — Cognito Group Cleanup Plan (DECIDED als Plan, GREEN; KEINE Mutation)

Ist-Stand vs. P01/P02 (verifiziert identisch — terraform/modules/cognito/main.tf:94-129; Code-Nutzung: NULL ausser /me-Echo):

| Gruppe | TF | Code-Nutzung | Semantik-Stand | Plan-Entscheid |
|---|---|---|---|---|
| `admins` | Z.104-107 | Keine (Claim nur Echo) | Administrator (PROMPT 02 DECIDED) | BEHALTEN (kanonisch); mit Semantik + Gates belegen (Implementierung) |
| `Staff` | Z.116-119 | Keine | Support-Rolle (PROMPT 02 DECIDED) | BEHALTEN; mit Semantik belegen (Implementierung) |
| `Admin` | Z.111-114 | Keine | Deprecated-Alias (PROMPT 02 DECIDED) | P1-Freeze (keine neuen Mitglieder) -> P2-Migration (Mitglieder -> `admins`, Claim-Impact pruefen) -> P3-Entfernung (separates Gate, Backup-vorher) |
| `candidates` | Z.94-97 | Keine | UNKLAR/historisch (Domaenen-Vermutung, KEIN Beleg) | P1-Freeze + Bedarfs-Klaerung (OPEN: Produktentscheid noetig); LOESCHEN VERBOTEN ohne Member-Migration + Claim-Check |
| `recruiters` | Z.99-102 | Keine | UNKLAR/historisch (wie candidates) | Wie candidates |
| `user-user` | Z.121-124 | Keine | UNKLAR (verbatim-Satz, KEIN Beleg) | Wie candidates (zusaetzlich: Namens-Sinn klaeren) |
| `user-requier` | Z.126-129 | Keine | UNKLAR (verbatim-Satz, moegl. Tippfehler-Artefakt — als VERMUTUNG markiert, nicht als Fakt) | Wie candidates (Schreibweise im Zuge Klaerung entscheiden) |

- Harte Regeln (DECIDED): KEINE Gruppe loeschen/umbenennen/zusammenlegen IN DIESEM GATE (Scope-Verbot erfuellt); NIEMALS nicht-leere Gruppen ohne Member-Migration entfernen (sonst JWT-Claim-Bruch bei Mitgliedern); jede Entfernung NUR mit vorherigem Mitglieder-Export + Claim-Verwendungs-Check + TF-Aenderung + Apply im Wartungsfenster + Nach-Verifikation (separates Implementierungs-Gate).
- Phasen (RECOMMENDED-Reihenfolge): P0 Inventar (HIERMIT ERLEDIGT) -> P1 Freeze + Bedarfs-Klaerung (parallel zu Offer-Entscheid) -> P2 `Admin`-Migration (nach Admin-Semantik-Implementierung) -> P3 Entfernung NUR leerer/deprecated Gruppen (eigenes Gate).

## P4-Gesamtauswertung

| Bereich | Entscheidung | Status | Begruendung |
|---|---|---|---|
| Offer | Minimal-Contract (6 Felder, ACTIVE/INACTIVE, agentIds, Plattform-Owner, Admin-only, keine Preise) | GREEN | Kette schliessen ohne Preis-Erfindung; Enzug an Entitlements (nicht Katalog) |
| Credential Verification | Einfuehrungspfad B (Lambda-intern, dediziertes Modul, eigener Routen-Namensraum); A deferred mit Triggern | GREEN | Kleinste Aenderung + sofortige Revocation + keine neue Infra; JWT-Routen unberuehrt |
| APIProfile CRUD | Operations-Rollen-Matrix + Feldklassen + 409/Idempotency + Tenant-Regeln (Routen nur Vorschlag) | GREEN | PROMPT-02-Rollen exakt gespiegelt; Owner-Selbstsperre reversibel; kein Self-Provisioning per Login |
| Capability Contract | Separater Read-Only-Introspection-Contract (3 Kontexte, nur Positives, kein Orakel) | GREEN | Bestehende Routen koennen Profil-/Scope-Kontext nicht abbilden; Profil-Auswahl-Mechanismus OPEN |
| Worker Authorization | A-Nachpruefung (Produktionsregel) + B-Provenance (auditiv, unsigned; signiert deferred) + Gap Agent-Sandboxing | GREEN (Boundary) | Schliedert Revoke-then-Retry-Luecke; kein Vertrauen in Nachrichten-Felder; In-Process-Rollen-Teilung als Gap benannt |
| Cognito Cleanup | 7-Gruppen-Plan (behalten/deprecated/unklar) + harte Loesch-Regeln + Phasen | GREEN (Plan) | Keine Mutation hier; kein stilles Loeschen; Claim-Bruch ausgeschlossen |

Konfliktpruefung P01-P03: KEIN Widerspruch erzeugt (R2-Namensraum folgt P03-eigenem-Pruefpfad; R4-Introspektion folgt P03-C6-Empfehlung; R5-A+B folgt P03-pro-Request + P02-Union; R6-`Admin`-deprecated folgt P02; R1/R3 ohne Preis/Capability-Anmassung innert Scopes).

## Dokumentation (P4-Folgen — KEINE kanonische Aenderung)

Geprueft: SYSTEM-ARCHITECTURE/RUNTIME-PATH/API-STANDARD/PLATFORM_FRONTEND_INTEGRATION/README/ROADMAP/PROJECT_STATUS enthalten KEINE Aussage, die durch P4 veraltet/widerspruechlich wuerde (Offer/CRUD/Introspektion/Worker-Nachpruefung/Cleanup sind NEU, kein Widerspruch zu heilen). Konvention bestaetigt: KEINE kosmetischen Aenderungen; kanonische Docs bleiben gueltig. spaetere Implementierungs-Gates aktualisieren docs gezielt (Offer-Katalog, Routen-Namensraum, Introspection-Endpoint, Worker-Regel, Gruppen-Semantik).

## Naechste empfohlene Reihenfolge (fuer Folge-Gates, kein Umfang hier)

1. Gruppen-Bedarfs-Klaerung (R6-unklar) parallel zu Offer-Freigabe (R1) — kleinste offene Produktfragen zuerst.
2. Pruefpfad-Detail (R2-B-Modul-Schnitt) + Profil-Auswahl-Mechanismus (R4-OPEN) — beide VOR CRUD-Implementierung.
3. APIProfile-CRUD (R3) + Introspection lesend (R4) — sichtbarer Nutzen ohne Schreib-Risiko an Credentials.
4. Credential-Einfuehrung (PROMPT-03-C1-Typ) + Worker-Nachpruefung (R5-A) + Agent-Sandboxing-Gap — gemeinsam (sonst Umgehungs-Pfad).
5. `Admin`-Migration/Entfernung (R6-P2/P3) + Capability-Ausbau (Offer-Anzeige) — zuletzt.

**HARD STOP (keine Implementierung, keine Mutation).**
