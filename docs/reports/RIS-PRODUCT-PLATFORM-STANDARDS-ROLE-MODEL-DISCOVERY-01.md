# RIS-PRODUCT-PLATFORM-STANDARDS-ROLE-MODEL-DISCOVERY-01

STATUS: Discovery abgeschlossen (KEINE Implementierung, KEIN AWS, KEIN TF, KEIN Cognito-, DB-, API-Eingriff)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, 15f204d
- Scope: PROMPT 01 — Rollen-/Verantwortungs-Inventar + Standardmuster-Vergleich + Contract-Klaerung (APIProfile/Ownership/Lifecycle/Credentials/Offer-Entitlement/Frontend). Baut auf PRODUCT-PLATFORM-CONTRACT-01 auf, ersetzt ihn nicht.
- Methode: Repo-Greps (Rollenbegriffe, Gruppen-Nutzung, Client-/Credential-/Offer-Treffer) + TF-Cognito-Modul + Handler-/Ecosystem-/Pipeline-Code + kanonische Docs + Gate-Reports 10/11/12/13A/14 + Hersteller-Dokumentation (OpenAI Admin-/API-Referenz, OpenRouter Auth-/Limits-/Management-Key-Docs, Stand 2026). Nichts erfunden; Hersteller-Muster als VENDOR PATTERN (nicht als Standard) gekennzeichnet.
- Classification: je Aussage (EXISTING / IMPLEMENTED / DOCUMENTED / STANDARD / RECOMMENDED / RIS-SPECIFIC / OPEN).
- Terraform/AWS Checks: KEINE (Scope-Verbot).
- Git: nur diese Discovery-Dateien (s. Commit).
- Next: Empfehlungen fuer PROMPT 02 (§16) -> HARD STOP.

## 1. Executive Summary

- RIS besitzt HEUTE: Cognito-Identitaet (User/sub/Tenant/Groups-Claim), UserProfile-v1 (sub-gebunden), handler-seitige Entitlements (user x agent x Zeitfenster), zentralen Agent Catalog + Registry/Discovery/Eligibility-Ausfuehrungspfad, Frontend-Positivliste (/agents). Alles ohne Rollen-Differenzierung ausser Tenant-Isolation.
- RIS besitzt HEUTE NICHT: Administrator-/Staff-/Operator-Berechtigungsrollen (nur Gruppen-Objekte ohne Semantik und ohne einzige Code-Pruefung), Owner ausserhalb "JobSearch-Owner = anlegender User", Client-/Application-Objekte (ausser Cognito App-Client = Auth-Konfiguration), API Profiles, Credentials/Keys, Offers/Vergabe, Lifecycle, Audit.
- mayaws/Operator ist AUSSCHLIESSLICH Deployment-Kontext (AWS-CLI-Profil + Installer-`--profile`), KEINE fachliche Berechtigungsrolle.
- Standard-Seite: OAuth 2.0/OIDC (Rollen + Client-Typen + Scopes + Client-Credentials-Grant) und Cognito/API-Gateway (JWT-Authorizer, API-Keys + Usage-Plans NUR als Metering/Drosselung, KEIN Auth-Ersatz) sind uebernehmbar; IAM ist AWS-Ressourcen-, nicht Endbenutzer-Modell. OpenAI (Org -> Projekte -> Nutzer-Rollen inkl. Owner / Service-Accounts -> projekt-scoped Keys mit Scopes/Expiry, Admin-Keys duerfen KEINE Nutzungs-Endpoints aufrufen, Wert nur bei Erstellung sichtbar) und OpenRouter (pro-Key Limits/Resets, Management-Key verwaltet NUR Keys, keine Inference, pro-Endbenutzer-Key dokumentiert, GET /key Selbst-Introspektion) bestaetigen als VENDOR PATTERN: Profil/Projekt ≠ Key, Management-Plane ≠ Usage-Plane, Key-Wert nie persistent im Klartext.
- Empfehlung: APIProfile als RIS-spezifisches Objekt (Owner = User, spaeter optional Orga/Tenant) mit Credential-Trennung, Status-Lifecycle und Audit — Details und alle Vergabe-Entscheidungen bleiben OPEN fuer PROMPT 02.

## 2. Tatsaechlich vorhandener RIS-Stand (Begriffsinventar)

| Begriff | Existiert? | Wo | Implementiert oder nur dokumentiert? | Aktuelle Bedeutung | Kollisionen |
|---|---|---|---|---|---|
| Administrator | TEILWEISE | TF: Gruppen `admins` + `Admin` (cognito/main.tf:104-114) | IMPLEMENTED als Gruppen-Objekte; KEINE Semantik, KEINE einzige Code-Pruefung (0 Treffer `in groups` ausser /me-Echo) | Leere Gruppenhuelsen ("user decision, verbatim names") | `admins` vs `Admin` sind ZWEI verschiedene Gruppen ohne definierten Unterschied |
| Staff | TEILWEISE | TF: Gruppe `Staff` (cognito/main.tf:116-119); BACKUP_ARCHITECTURE "staff agents" (Backup-Scope, keine Rolle) | Wie Administrator: Objekt ohne Semantik/Pruefung | Undefiniert | Staff = Gruppe vs. umgangssprachlich "Mitarbeiter" — keine Festlegung |
| Operator | NEIN (als Rolle) | Nur: AWS-Profilname `mayaws` + Installer-`--profile`/identity_context (Deployment-/Installationskontext) | Deployment-Kontext, KEINE Berechtigungsrolle | Technischer Betreiber-Kontext (welcher Account/welches Profil installiert) | Darf NICHT als fachliche Rolle gelesen werden |
| Owner | TEILWEISE | jobsearch/repository.py + domain_models.py ("Expected owner's user ID") | IMPLEMENTED als Regel: Owner = anlegender User (user-scoped CRUD) | Besitz = Ersteller-Identitaet (userId) | Kein Orga-/Tenant-Owner; kein APIProfile-Owner (E) |
| User | JA | Cognito User (sub) + user-profile (userId=sub) + Handler user_context | IMPLEMENTED (Gates 10/12) | Natuerliche Person via Identity; Traeger von Profil + Entitlements | — |
| Client | TEILWEISE | (a) Cognito User-Pool App-Client (Auth-Konfiguration, IMPLEMENTED); (b) externer mays-Jobs-matcher (per Vorgabe clientseitig, DOCUMENTED) | Auth-Konfig vs. externer Consumer — KEIN RIS-seitiges Client-Objekt | Je nach Kontext voellig verschieden | App-Client (Cognito) ≠ API-Consumer (Matcher) — strikt trennen |
| Application | NEIN (als Objekt) | Nur Titel-Begriff (RIS-APPLICATION-PROFILE-09 = System-Dokument; TF "application-level" Kommentar) | — | Kein Objekt, keine Persistenz | Darf NICHT mit Cognito App-Client gleichgesetzt werden |
| API Profile | NEIN | 0 Treffer ausser PRODUCT-PLATFORM-CONTRACT-01 (dort als NEUER Begriff eingefuehrt) | — | Neue Zielidee (§4), nicht implementiert | Kollision mit 2 bestehenden "Application Profile"-Bedeutungen (Gate-12-Anwendungsdaten; Report-09-Systemdokument) |
| Credential | NEIN (als Produkt) | Nur Negativ-Regel (Browser erhaelt NIE AWS-Credentials, documents.py) | — | Kein Key-/Secret-Modell | AWS-Credentials ≠ API-Credentials (kuenftig) |
| Offer | NEIN | 0 Treffer (nur sachfremd: MO-Bestellpositionen unitPrice, DDB billingMode) | — | Kein Preis-/Tarif-/Abo-Modell (wird NICHT erfunden) | — |
| Entitlement | JA | DDB `entitlements` (Hash entitlementId, GSI userId/agentId) + Handler-Gates + `validFrom/validUntil` + GET /agents-Filter | IMPLEMENTED (handler-seitig; Pipeline kennt KEINE Entitlements — "future checks") | Techn. Zugriffsrecht user x agent x Zeit | Fachlich (Offer-Folge) vs. technisch (Zeilen) — Vergabestelle fehlt |
| Agent | JA | Registry/Descriptoren, Katalog-Tabelle, 5+ Agents, Pipeline | IMPLEMENTED | RIS-zentrale Ausfuehrungseinheit (Matcher besitzen KEINE) | — |
| UserProfile | JA | `user-profile` (Hash userId), v1-Felder, POST/GET/PUT-Semantik | IMPLEMENTED (Gate 12) | Anwendungsdaten, sub-gebunden, clientfrei | — |
| Tenant | JA | `custom:tenant_id`-Claim + Code-Guards + Isolation live | IMPLEMENTED | Isolations-Dimension (kein Owner, keine Orga-Rolle) | Tenant ≠ Owner ≠ Organisation |

Kernsatz (DOCUMENTED/IMPLEMENTED): Gruppen-Claims werden gelesen und in /me gespiegelt, aber NIRGENDS als Zugriffsentscheidung verwendet; einzige funktionale Autorisierung heute = Entitlement (user x agent x Zeit) + Tenant-Bindung.

## 3. Rollenmodell Ist-Zustand

- Funktionale Rollen: EXISTIEREN NICHT. Weder Admin (anlegen/aendern/deaktivieren/revozieren) noch Staff-Vorgaenge noch Operator-Rechte sind irgendwo definiert oder geprueft. [OPEN]
- Staff: weder als technische Rolle noch als fachliche Gruppe definiert (nur Gruppen-Objekt `Staff`). [OPEN]
- Operator (= mayaws): NUR Deployment-Kontext. Wer `--profile mayaws` + `--yes` aufruft, kann TF-Apply ausfuehren — das ist Arbeitsplatz-/Credential-Fakt, KEIN im System modelliertes Recht. [DOCUMENTED als Kontext, OPEN als Rolle]
- Owner: NUR "JobSearch-Owner = Ersteller" (userId). Kein APIProfile-Owner, keine Orga, kein Tenant-als-Owner. [IMPLEMENTED (eng), sonst OPEN]
- User: einzige tragende Identitaet (sub); darf heute KEIN APIProfile verwenden/besitzen (existiert nicht); mehrere Matcher ueber EINEN JWT-Pfad technisch moeglich, aber ungetrennt/unbelegt. [IMPLEMENTED/OPEN]
- Client/Application: Matcher IST faktisch ein Client (ruft JWT-geschuetzte API), aber RIS fuehrt KEIN Objekt — Zuordnung heute nur implizit (derselbe JWT-Pfad fuer alle). Ob ein Objekt noetig ist, entscheidet PROMPT 02 (Empfehlung §16: ja, minimal als APIProfile-Attribut, nicht als eigene Lifecycle-Domaene). [OPEN]

## 4. Standards / etablierte Patterns (A = Standard, V = einzelnes Hersteller-Muster)

| Muster | Kernaussagen (fuer RIS relevant) | Klasse |
|---|---|---|
| OAuth 2.0 (RFC 6749/6750/7662/7009) | Rollen: Resource Owner / Client / Authorization Server / Resource Server. Oeffentliche vs. vertrauliche Clients. Scopes = delegierte Berechtigungen. Client-Credentials-Grant = M2M ohne Benutzer. Introspection + Revocation als eigene Endpunkte. | STANDARD |
| OpenID Connect | Identitaets-Schicht auf OAuth 2.0: ID-Token mit `sub`-Claim; UserInfo; Cognito User Pool IST ein OIDC-Provider (RIS nutzt genau das: sub/email/groups/tenant als Claims). | STANDARD |
| AWS Cognito + API Gateway | User-Pool-Gruppen als grobe Rollen (Claim `cognito:groups`); JWT-Authorizer als Policy-Enforcement-Point; API-Keys + Usage-Plans NUR fuer Drosselung/Metering — explizit KEIN Auth-Ersatz (ohne Authorizer/Lambda-Check keine Sicherheit). | STANDARD (AWS-Plattformmuster) |
| AWS IAM | Nutzer/Gruppen/Rollen/Richtlinien + STS-Annahme + ABAC fuer AWS-RESSOURCEN. Endbenutzer-Auth gehoert NICHT in IAM (dafuer Cognito Identity Pools als Bruecke). | STANDARD (fuer Infrastruktur; NICHT als Endbenutzer-Rollenmodell uebernehmbar) |
| OpenAI (API-Plattform) | Org -> Projekte -> Rollen (u.a. Owner) + Service-Accounts; Keys sind projektgebunden, optional mit Scopes/Expiry, Wert nur bei Erstellung sichtbar (danach redacted + last_used_at); Admin-Keys verwalten NUR, duerfen KEINE Nutzungs-Endpoints aufrufen; Audit-Logs. | VENDOR PATTERN (belegt: developers.openai.com Admin-/API-Referenz 2026) |
| OpenRouter | Pro-Key Kredit-Limits + Reset-Zyklen; Management-Key verwaltet NUR Keys (keine Inference); dokumentierter Fall "ein Key pro Endbenutzer"; GET /key Selbst-Introspektion (limit_remaining/usage); disabled- + expires_at-Felder. | VENDOR PATTERN (belegt: openrouter.ai Auth-/Limits-/Management-Key-Docs 2026) |
| AWS Amplify | App-zentriertes Deployment-/Backend-Modell (App -> Umgebungen -> Auth/API/Storage-Kategorien, darunter Cognito-Pools); AppSync-"API-Keys" nur fuer oeffentlichen Lesezugriff, KEIN Benutzer-Auth. | VENDOR PATTERN mit GERINGER Uebertragbarkeit (Deployment-, kein API-Produkt-Modell) |

## 5. Standards -> RIS Mapping (B = uebernehmbar, C = RIS muss selbst definieren, D = NICHT kopieren)

| Standard-/Pattern-Aussage | RIS-Uebernahme |
|---|---|
| B: OAuth-Rollen (Owner/Client/AS/RS) + vertraulicher Client + Client-Credentials-Grant (M2M) | M2M-Zugang spaeter als Client-Credentials-analoger Fluss (eigener Token-/Key-Pfad, NICHT Cognito-Benutzer-Impersonation) |
| B: Scopes als delegierte Berechtigungen | Entitlements als RIS-Scopes lesen (user x agent x Zeit); kuenftige Profil-Scopes daran anlehnen |
| B: Introspection + Revocation als eigene Mechanismen | Credential-Pruefung + sofortige Revocation als Pflicht-Mechanismus (§9 C4) |
| B: Cognito-Gruppen als grobe Rollen + JWT-Authorizer als PEP | Admin/Staff spaeter als Gruppen-ROLLEN mit Semantik + Handler-Gates (heute: Huelsen) |
| B: OpenAI/OpenRouter Management-Plane ≠ Usage-Plane | Admin-/Ausstellungs-Funktionen strikt von Nutzungs-Pruefung trennen (eigene Rechte, eigene Audit-Spur) |
| B: Key-Wert nur bei Erstellung sichtbar; Metadaten (redacted/last_used/expires/disabled) abfragbar | Direkt uebernehmen (§9 C6) |
| B: OpenRouter GET-/key-Selbst-Introspektion + pro-Key-Limits | Capability-Selbstauskunft spaeter nach diesem Vorbild (liest, veraendert nichts) |
| C: Wer Owner ist (User vs. Orga/Tenant); wer vergeben darf; Offer-Definition; Profil-Lifecycle-Details; Frontend-Flag-Semantik | Muss RIS fachlich selbst definieren (PROMPT 02) — kein Standard regelt das |
| D: OpenAI Org/Projekt-Hierarchie 1:1 kopieren | NICHT kopieren: RIS hat Tenant-Isolation + sub-zentrierte Profile; keine fremde Hierarchie ueberstuelpen |
| D: AWS-IAM als Endbenutzer-Rollenmodell | NICHT kopieren: IAM sichert AWS-Ressourcen, nicht App-Benutzer |
| D: API-Gateway-Keys als Auth | NICHT kopieren: Metering-Keys sind KEINE Sicherheit (ohne Authorizer wertlos) |
| D: Amplify-App-Modell als Produktmodell | NICHT kopieren: Deployment-Sicht, keine Offer/Profile/Credential-Semantik |

## 6. Rollenmodell Vorschlag (RECOMMENDED — Entscheidung PROMPT 02, keine Implementierung)

| Rolle | Verantwortung (Vorschlag) | Begruendung |
|---|---|---|
| Administrator | APIProfiles anlegen/aendern/deaktivieren; Credentials ausstellen/revozieren; Offers/Entitlements vergeben; Audit einsehen. Technisch: Cognito-Gruppe(n) mit Semantik + Handler-/Admin-Pfad-Gates. | Existierende Gruppen-Huelsen (`admins`/`Admin` — VEREINHEITLICHEN, Dopplung aufloesen) + OpenAI-Admin-Trennung (Management ≠ Usage) |
| Staff | Operative Support-Vorgaenge (z.B. lesen, revozieren bei Missbrauch, re-ausstellen) — KEINE Offer-/Modell-Politik. Ob technisch eigene Rolle oder fachliche Gruppe mit engeren Rechten, entscheidet PROMPT 02. | Trennung Policy (Admin) vs. Betrieb (Staff) ist Standardpraxis; heute beides undefiniert |
| Operator | KEINE fachliche Rolle. Bleibt Deployment-Kontext (Profil/Account/Workspace). Wer installiert, folgt aus Arbeitsplatz-Credentials, nicht aus App-Rechten. | Ist-Stand + IAM-Trennung (Infra vs. App) |
| Owner | Vorschlag: APIProfile-Owner = anlegender User (Analogie JobSearch-Owner, EXISTING-Regel). Orga-/Tenant-Ownership erst, wenn ein Orga-Begriff eingefuehrt wird (derzeit E). Owner ≠ Tenant (Tenant = Isolation, kein Akteur). | Kleinste konsistente Erweiterung des einzigen existierenden Owner-Begriffs |
| User | Verwendet Profile (authentifiziert, JWT); darf mehrere APIProfiles besitzen (RECOMMENDED: ja — sonst kein Multi-Client-Modell); mehrere Matcher ueber getrennte Profile (RECOMMENDED: ja, Trennung ueber Profile, nicht ueber Identitaeten). | Multi-Client-Zielbild PROMPT-01-§4 |
| Client/Application | Matcher IST Client; RIS fuehrt dafuer (RECOMMENDED) KEIN eigenes Lifecycle-Objekt, sondern ein Profil-Attribut (client_id/Name + Nachweis), an das Bindung/Audit haengen. Eigene Client-Domaene nur bei Bedarf (z.B. Drittanbieter-Secrets). | C: RIS-Definition; vermeidet Over-Engineering, haelt Bindungsoption offen |

Offen gelassen (PROMPT 02): Admin vs. `admins`-Bereinigung, Staff-Umfang, Orga-Begriff, Vergabeprozess.

## 7. APIProfile Ownership-Modell (RECOMMENDED-Geruest, alles OPEN ausser Markiertem)

- APIProfile ist eigenstaendiges Objekt (RECOMMENDED, bestaetigt Zielidee §4): `{profileId, ownerUserId (DECIDED-Vorschlag: Ersteller, Analogie JobSearch), status, clientRef (Attribut, kein Fremdschluessel auf Lifecycle-Objekt), entitlementsRef[], credentialsRef[], timestamps}`.
- Owner vs. Assigned User: Vorschlag genau EIN Owner (Ersteller-User); "assigned user" wird NICHT eingefuehrt (kein Sharing-Begriff im Repo; Teilen = neues Profil + eigene Entitlements). [RECOMMENDED, OPEN-Entscheid]
- Bindung an Client/Application: RECOMMENDED locker (Attribut + optionale strikte Bindung spaeter: Credential gilt nur mit passendem clientRef-Nachweis), NICHT hart als Fremdschluessel-Lifecycle — haelt beide Wege offen und verhindert Schein-Architektur ohne Client-Domaene.
- Beziehung: User 1—n APIProfile; APIProfile 1—n Credentials; APIProfile 1—n Entitlements (Schnittmenge mit user-weiten Entitlements: Union, nie Intersection — sonst wuerde ein Profil Rechte ENTZIEHEN, die der User direkt hat; RECOMMENDED, zu bestaetigen).

## 8. Client/Application Boundary (RECOMMENDED)

- Matcher = OAuth-sinniger "vertraulicher Client" (M2M-Anteil) + Browser-Anteil (Benutzer-JWT). RIS braucht HEUTE kein Client-Objekt; sobald Credentials existieren, braucht jedes Credential einen `clientRef`-Anker (sonst keine Zuordnung, kein Widerruf pro App, keine Audit-Aussage "welche App").
- Cognito App-Client bleibt AUTH-Konfiguration (welche Flows/IdPs), sagt NICHTS ueber Produkt-Clients — beide Ebenen strikt getrennt dokumentieren (Kollisions-Schutz §2).

## 9. Credential Boundary (RECOMMENDED — kein Typ vorweggenommen)

- Fuer Browser/User-Login: Cognito-JWT (EXISTING, bleibt). Fuer API-Zugriff (App/M2M): EIGENER Credential-Typ (OPEN ob Key- oder Token-Format — PROMPT 02 entscheidet anhand M2M-Anteil vs. Verwaltbarkeit; NICHT automatisch "API Key").
- Gehoert zum APIProfile (Ausstellung/Scope/Status), referenziert Client (clientRef), gehoert NICHT zum User (kein Benutzer-Passwort-Ersatz) und NICHT zum Cognito-Pool.
- NIEMALS persistieren: Klartext-Secrets/Key-Werte, Cognito-Passwoerter, fremde IdP-Tokens, JWTs als "gespeicherte Sessions".
- Persistierbar: Hash/Referenz + Metadaten (Name, Scopes/EntitlementsRef, created/last_used/expires/status, clientRef, auditRef) — Vorbild OpenAI-redacted/last_used_at + OpenRouter-disabled/expires_at/usage (VENDOR PATTERN).

## 10. Offer / Entitlement Boundary (Kette — RECOMMENDED)

Offer (Produkt, Owner OPEN) -> Entitlement (techn. Recht, RIS-seitig, user- ODER profil-gebunden — BEIDE Anker RECOMMENDED: user-weite Basis + profil-spezifische Zusaetze, Union-Semantik) -> APIProfile (Kontext-Buendel) -> Credential (Nachweis) -> API-/Agent-Zugriff (Handler-Gate + kuenftig Pipeline-Regeln).

- Kette ist SINNVOLL (trennt Kauf/Vertrag, Recht, Kontext, Nachweis, Durchsetzung — entspricht OAuth-Trennung + OpenAI/OpenRouter-Praxis). Standard-Anteil: Rollen-/Scope-/Introspection-/Revocation-Denken + Plane-Trennung. RIS-Anteil: Entitlement-Zeilenformat, Agent-Katalog-Bindung, Tenant-Scope, Frontend-Positivliste.
- Owner eines Offers: OPEN (kein Produkt-Owner im Repo). Vergabe: OPEN (keine Stelle). User MULTIPLE Entitlements: IMPLEMENTED-moeglich (Query liefert Liste; kein Exklusivitaets-Constraint). Profil MULTIPLE Entitlements: RECOMMENDED-ja (Union). Agent Access: ueber Entitlement (user x agent x Zeit) + Katalog-Status + kuenftige Pipeline-Regeln; Matcher besitzen KEINE Agenten (DECIDED).

## 11. Frontend Capability Boundary (RECOMMENDED)

- Grundsatz "Frontend shows, backend decides" bleibt (DOCUMENTED, PLATFORM_FRONTEND_INTEGRATION §5).
- Musterwahl: RECOMMENDED Kombination — (a) POSITIVE LIST (heute /agents: was geht SOFORT), (b) SCOPES/ENTITLEMENTS-Selbstauskunft (kuenftig: was darf ICH, analog OpenRouter GET /key — lesend, cachebar), (c) FEATURE FLAGS nur fuer reine UI-Schalter (niemals als Sicherheitsentscheidung). Scopes-fuer-Ausfuehrung + Flags-fuer-Anzeige strikt trennen.
- Kein Muster erfindet Rechte: Anzeige-Liste ist Abbild serverseitiger Pruefung mit Timestamp/Gueltigkeit, keine eigene Autorisierung.

## 12. Lifecycle (RECOMMENDED — fachlich vs. abgeleitet)

| Zustand | Art | Bedeutung | Uebergaenge (Vorschlag) |
|---|---|---|---|
| PENDING | FACHLICH | Angelegt, noch nicht nutzbar (z.B. Freigabe ausstehend) | -> ACTIVE (Admin-Freigabe) / -> REVOKED (Rueckzug) |
| ACTIVE | FACHLICH | Nutzbar (Credentials pruefbar, Entitlements wirksam) | -> DISABLED (Admin/Staff, reversibel) / -> REVOKED (endgueltig) / -> EXPIRED (automatisch) |
| DISABLED | FACHLICH | Temporar gesperrt (reversibel), Grund + Actor + Zeit Pflicht | -> ACTIVE (Entsperrung) / -> REVOKED |
| EXPIRED | ABGELEITET | Guel­tigkeits­ende ueberschritten (berechnet, kein manueller Akt) | -> ACTIVE nur via Verlaengerung (neuer Ablauf, auditiert) |
| REVOKED | FACHLICH | Endgueltig entzogen (Missbrauch/Vertragsende); Credentials SOFORT ungueltig | terminal (kein Rueckweg; Neuanlage noetig) |

- disabled (administrativ, reversibel, mit Grund) ≠ expired (Zeitablauf, berechnet) ≠ revoked (endgueltig, sofort wirksam, kein Rueckweg).
- Status aendern duerfen: PENDING->ACTIVE / DISABLED<->ACTIVE / REVOKED = Administrator; DISABLED (mit Missbrauchs-Begruendung) zusaetzlich Staff (RECOMMENDED, zu bestaetigen); EXPIRED = System (abgeleitet, kein Akteur).
- Auditierbar: JEDE fachliche Statusaenderung (wer/wann/von-nach/Grund) + jede Credential-Ausstellung/Rotation/Revocation + jede Entitlement-Vergabe (RECOMMENDED; technische Basis: CloudTrail-Mgmt + strukturierte App-Logs ohne Secrets — EXISTING-Faehigkeit, Gate 14).

## 13. Security Considerations (RECOMMENDED-Prinzipien)

- Zwei Ebenen, zwei Pruefungen: Profil-/Credential-Pruefung (WER ruft in WELCHEM Kontext an) VOR Agent-Entitlement-Pruefung (DARF der Kontext DIESEN Agenten nutzen). Keine Vermischung.
- Credential-Hygiene: nur Hash/Referenz speichern; Wert genau EINMAL bei Ausstellung zeigen; Rotation ohne Profil-Neuanlage; sofortige Revocation (Profil- + Credential-Ebene); Ablauf default-maessig befristen (Max-Laufzeit OPEN).
- Isolation: User-/Tenant-Isolation (EXISTING) + Profil-Isolation (Credential aus Profil 1 gilt nie in Profil 2) + Least-Privilege pro Funktion (EXISTING IAM-Muster).
- Kein Secret in Logs/Reports/State-lesbaren Feldern (EXISTING-Praxis: Shred + maskierte Destinations, Gates 10/11/14).
- Pipeline-Luecke schliessen (PROMPT 02): Entitlement-Nachpruefung im Worker-Pfad oder signierte, faelschungssichere WorkItem-Herkunft — heute vertraut der SQS-Pfad dem Execute-Pfad (DOCUMENTED Ist-Stand, RUNTIME-PATH-OPEN).

## 14. Audit Requirements (RECOMMENDED-Mindestumfang)

- Ereignisse: Profil-Lifecycle (alle Uebergaenge), Credential-Ausstellung/Rotation/Revocation/Fehlgebrauch (Rate), Entitlement-Vergabe/Entzug, Admin-/Staff-Aktionen (wer/was), anonyme/fehlgeschlagene Zugriffsversuche (ohne Secrets).
- Eigenschaften: Actor + Zeit + Vorher/Nachher + Grund; unveraenderbar ablegbar (CloudTrail-Mgmt EXISTING + append-only App-Spur spaeter); Secrets/PII-frei; Tenant-zuordenbar.
- Auswertung: letzter Gebrauch (last_used_at-Analogie), ruhende Credentials, abgelaufene Profile — als spaetere Betriebs-Sichten, nicht als Gate-01-Umfang.

## 15. OFFENE ENTSCHEIDUNGEN (keine als entschieden behandeln)

1. Admin-Begriff bereinigen (`admins` vs `Admin`) + Admin-Rechteumfang (PROMPT 02).
2. Staff-Umfang (eigene Rolle vs. enge Admin-Untermenge) + Missbrauchs-Sperrrecht.
3. Owner-Modell (nur Ersteller-User vs. zusaetzlich Orga/Tenant als Owner-Typ).
4. Offer-Definition + Owner + Vergabestelle + Kauf-/Freischalt-Fluss (blockt Monetarisierung).
5. Client-Objekt (Attribut reicht vs. eigene Domaene mit Secrets/Rotation).
6. Credential-Typ (Key vs. Token/M2M-Fluss) + Max-Laufzeit + Rotation-Pflicht.
7. Profil↔Entitlement-Schnitt (Union bestaetigen; user-weite vs. profil-gebundene Anker).
8. Capability-Endpoint (Format/Umfang/Caching) + Flag-Disziplin.
9. Worker-Pfad-Entitlements (Nachpruefung vs. signierte Herkunft).
10. Gruppen-Semantik Altbestand (candidates/recruiters/user-user/user-requier — behalten mit Semantik oder bereinigen).

## 16. Empfehlungen fuer PROMPT 02 (Contract-Entscheidungen, dann Design — KEIN Code)

1. R1: Admin/Staff-Semantik + `admins`/`Admin`-Bereinigung entscheiden (kleinste Rollen-Luecke, blockt alles Administrative).
2. R2: Owner = Ersteller-User bestaetigen; Orga-Typ vertagen (kein Begriff ohne belegten Bedarf).
3. R3: APIProfile-Objekt + clientRef-Attribut + Union-Entitlements + Lifecycle-Tabelle (§12) als Contract beschliessen.
4. R4: Credential-Typ entscheiden (M2M-Anteil klaeren: reiner Server-zu-Server-Anteil spricht fuer Token/Credentials-Grant-Analogie; einfache Matcher-Integration fuer Key-Format) + Ausgabe-/Speicher-/Rotations-Regeln.
5. R5: Capability-Selbstauskunft (OpenRouter-GET-/key-Analogie) als naechsten sichtbaren Baustein vorziehen (kein Schreib-Eingriff, sofortiger Frontend-Nutzen).
6. R6: Worker-Pfad-Sicherheitsentscheidung (Nachpruefung vs. signierte Herkunft) VOR jeder Credential-Einfuehrung (sonst Umgehungs-Pfad).
7. R7: Offer-Minimalmodell (nur Name/Beschreibung/EntitlementsRef, KEINE Preise) als Vergabe-Voraussetzung — Monetarisierung explizit spaeter.

**HARD STOP (Discovery only — keine Implementierung).**
