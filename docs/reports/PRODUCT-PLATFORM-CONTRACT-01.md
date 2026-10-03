# PRODUCT-PLATFORM-CONTRACT-01 — Verbindlicher Product / Platform Contract (Discovery + Entscheidungen)

STATUS: Discovery- und Entscheidungs-Gate (KEINE Implementierung, KEIN AWS, KEIN TF-Apply, KEINE Keys)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, f10dc38
- Scope: Ist-Feststellung + Contract-Entscheidung zum RIS-Produktmodell (Identity/Profile/Offer/API-Profile/Credential/Multi-Client/Frontend/Catalog). Keine Routen, kein Frontend, kein Google-Login-Umbau, keine AWS-Mutation.
- Methode: Repo-Greps (identity/auth/Cognito/profile/entitlement/offer/catalog/client/credential/tenant/userId/Endpunkte) + kanonische Docs (README, SYSTEM-ARCHITECTURE, RUNTIME-PATH, API-STANDARD, PLATFORM_FRONTEND_INTEGRATION, ROADMAP, PROJECT_STATUS) + Gate-Reports 10/11/12/13A/14 + Code-Stichproben (lambda/handler.py, agents/ecosystem/*, agents/runtime/pipeline.py, jobsearch/domain_models.py, terraform/modules/*). Nichts erfunden.
- Classification: siehe Entscheidungs-Matrix (§10). YELLOW gesamt (Kern GREEN, Produktmodell OPEN — ehrlich).
- Terraform/AWS Checks: KEINE (Scope-Verbot; keine TF-Aenderung, keine Mutation).
- Git Status (RIS): nur diese Reports (s. Commit); Bestand unberuehrt.
- Files Changed: docs/reports/PRODUCT-PLATFORM-CONTRACT-01.md (neu) + Execution-Log (neu).
- Open Questions: s. §10/§11 (wichtigste OPEN Decisions im Checkpoint).
- Risks: keine (reines Lese-/Schreib-Gate auf .md).
- Next Actions: Commit -> HARD STOP (KEINE Implementierung).
- Resume Point: nach Commit HARD STOP.

## 0. Status-Legende (fuer diesen Report)

- IMPLEMENTED: im Code/TF vorhanden und (wo angegeben) live belegt.
- DECIDED: durch Gate-Evidenz oder diesen Contract fest entschieden (ohne Code-Aenderung).
- PREPARED: Vertrag/Strategie definiert, NICHT implementiert.
- OPEN: keine belastbare Vorgabe — Entscheidung fehlt, wird NICHT vorweggenommen.
- BLOCKED: von fehlender Voraussetzung abhaengig.
- Historie-Klassen je Quelle: A = verbindlich dokumentiert, B = implementiert/ungenuegend dokumentiert, C = historisch, D = widerspruechlich, E = nicht vorhanden/offen.

## 1. Begriffsklaerung (Kollisionen — DECIDED)

1. "Application Profile" bezeichnet im Repo ZWEI bestehende, VERSCHIEDENE Dinge — beide NICHT das neue API-Profile-Modell:
   - (a) Gate-12/Architektur: UserProfile als Anwendungsdaten (Identity ≠ Application Profile). [A]
   - (b) RIS-APPLICATION-PROFILE-09: fachlich-technisches System-Vollprofil (Dokument, kein Laufzeit-Objekt). [A]
2. "API Profile" (dieses Gate) ist ein NEUER Begriff: API-Zugangs-/Client-Kontext eines Benutzers/Owners (Client/Application + Agent-Entitlements + Credentials). Im Repo 0 Treffer (kein Code, kein TF, keine Tabelle, kein Endpoint). [E]
3. Es gilt strikt: API Profile ≠ API Key (Credential). Ein API Profile KANN spaeter mehrere Credentials tragen (Contract-Prinzip, §8) — aktuell implementiert: nichts. [PREPARED als Prinzip, OPEN als Umsetzung]
4. "Offer / Entitlement": Offer = freischaltbares Funktions-/Leistungsangebot (Produktseite); Entitlement = technische Zugriffsberechtigung (userId x agentId x Gueltigkeit, Tabelle `entitlements`). Offers existieren im Repo NICHT (kein Preis-/Tarif-/Abo-Modell irgendwo belegt — Grep negativ ausser MO-Bestellpositionen unitPrice und DDB billingMode, beide sachfremd). [E]

## 2. Zielmodell-Konsistenz (USER-Baum vs. Architektur)

```
USER
 ├── Identity            -> IMPLEMENTED/DECIDED: Cognito bleibt zentrale Identity-/JWT-Grenze (Pool users, JWT-Authorizer, Claims sub/email/groups/custom:tenant_id). [A: ARCH §4, Gates 10/11/13A]
 ├── UserProfile         -> IMPLEMENTED: v1-Felder, explizit POST-201/409, GET-404, PUT-200/404, Spoof-immun, sub-gebunden. [A: Gate 12, API-STANDARD]
 ├── Offers/Entitlements -> GETEILT: Entitlements IMPLEMENTED (Tabelle Hash entitlementId + GSI userId/agentId; Handler prueft user+agent+validFrom/validUntil, 403 ohne); Offers E (kein Modell, keine Preise, keine Vergabe). [B/A bzw. E]
 ├── API Profiles        -> E: neue Idee, als Produktmodell untersucht, NICHT implementiert. Konsistent moeglich (kein Widerspruch zu Bestand), aber voellig offen. [E/OPEN]
 │      ├── Client/Application -> E (kein Client-Objekt; einziger Client-Begriff = Cognito App-Client + externer mays-jobs-matcher per Vorgabe clientseitig). [E]
 │      ├── Agent Entitlements -> B: Mechanismus vorhanden (s.o.), aber OHNE Profil-/Client-Bindung. [B]
 │      └── API Credentials     -> E (kein Key-/Secret-Modell, keine Speicherung, keine Rotation). [E]
 ├── CV/Documents        -> IMPLEMENTED (Storage only): privater Bucket, Key tenant/{t}/users/{sub}/documents/{uuid}, Presigned-URLs, kein DDB-Metastore, kein Parsing. [A: Gate 14]
 ├── JobSearch Profiles  -> B/IMPLEMENTED-partial: Domaenenmodelle (JobSearch, SearchConfiguration, ATSSearchProfile) + Repository (user/tenant-scoped) + /me/jobsearches-Routen handler-intern; Persistenz/TF-Verdrahtung je nach Stand nach Gate 9/live. [B]
 └── ATS Profiles        -> E als eigenstaendiges Profil: ATSSearchProfile ist JobSearch-Domaenenmodell (KEIN ATS-Aufruf); kein separates ATS-Profil-Objekt, keine ATS-Profiltabelle. [E]
```

Fazit: Das Zielmodell WIDERSPRICHT der Architektur nicht (Identity/Profile/Catalog/Entitlements/Worker-Pfad bleiben unberuehrt), ist aber oberhalb von Entitlements (Offer, API Profile, Client, Credential) VOLLSTAENDIG OFFEN. Keine Stufe wird als implementiert behauptet, die es nicht ist.

## 3. Multi-Client-Modell (Job Matcher A/B — keine Entscheidung erzwungen)

Befund vorab (DECIDED): Entitlements sind (userId, agentId, tenantId-Scope, Zeitfenster) — OHNE Client-/Profil-Dimension. Der Handler kennt keinen Client-Kontext. [A: handler.py _get_entitlements/_get_entitlement_for_agent/_is_entitlement_valid]

1. Kann ein Benutzer mehrere API Profiles besitzen? OPEN — kein Profil-Objekt, keine Ownership-Regel, keine Tabelle. Technisch nichts dagegen, vertraglich nichts dafuer.
2. Kann ein API Profile einem Client/Application-Kontext zugeordnet werden? OPEN — kein Client-Objekt im RIS (Ausnahme: Cognito App-Client = Auth-, kein Produkt-Kontext).
3. Koennen zwei Job Matcher denselben RIS-Benutzer bedienen? BEDINGT MOEGLICH (Technik) / OPEN (Vertrag): Beide Matcher nutzen heute denselben JWT-Pfad; nichts trennt ihre Zugriffe, nichts verbietet Koexistenz (mays-jobs-matcher per Vorgabe clientseitig). Ohne API Profiles keine Trennung, keine Abrechnung, kein Scoping.
4. Bleibt das UserProfile zentral und unabhaengig vom Client? DECIDED JA: Profil ist sub-gebunden (userId=Cognito-sub), ein Profil je Identity, kein Client-Feld, kein clientseitiger Schreibpfad ausser explizitem POST/PUT. [A: Gate 12]
5. Koennen unterschiedliche API Profiles unterschiedliche Agenten verwenden? OPEN (als Profil-Faehigkeit) / IMPLEMENTED (als Mechanismus-Basis): Agent-Filterung je User existiert via Entitlements (GET /agents liefert nur entitled Agents); eine Profil-Ebene darueber fehlt.
6. Wo wird diese Berechtigung fachlich definiert? Nirgends (E): kein Offer-Katalog, keine Vergabestelle, keine Admin-Rolle, kein Produkt-Owner im Repo definiert.
7. Wo wird sie technisch geprueft? DECIDED (Ist-Stand): AUSSCHLIESSLICH im Lambda-Handler (Sync-API-Pfad: _execute_agent 403 ohne gueltiges Entitlement; GET /agents filtert). Die Worker-Pipeline (EligibilityPipeline) prueft NUR Deskriptor-Kompatibilitaet (Status/Capability/Body/Runtime); user_id/tenant_id sind dort als "future checks" markiert — KEINE Entitlement-Pruefung im SQS-Pfad (vertraut dem WorkItem aus dem geprueften Execute-Pfad). [B: pipeline.py/process_record, eligibility.py; bestaetigt durch RUNTIME-PATH "harte Entitlement-Regeln: OPEN"]

## 4. Provisioning / Vergabe (alle Faelle OPEN)

- A) Benutzer erhaelt/kauft Angebot: OPEN — kein Kauf-, kein Zahlungs-, kein Freischalt-Fluss; kein Preis-/Tarifmodell belegt (wird NICHT erfunden).
- B) Plattform/Admin vergibt API-Zugang: OPEN — keine Admin-Rolle, kein Vergabe-Endpoint, kein Admin-UI/CLI-Fluss im Repo.
- C) Organisation/Partner vergibt API-Zugang: OPEN — kein Orga-/Partner-Objekt, keine Delegation.
- D) Anderer Mechanismus: OPEN.
- Festgelegt (DECIDED): NUR die Negativ-Seite — kein Auto-Provision (Profile), kein Auto-Linking, keine impliziten Rechte (Gates 10/12/13A). Alles andere fehlt.
- Benoetigte spaetere Entscheidungen: Offer-Definition + Owner, Vergabestelle + Prozess, Profil-Lebenszyklus (create/suspend/revoke), Credential-Ausgabe + Zustellweg.
- Trennung (PREPARED als Contract-Prinzip): Offer/Entitlement (WAS darf der Benutzer) ≠ API Profile (in WELCHEM Client-Kontext) ≠ API Credential (WOMIT authentifiziert sich der Client). Ein API Key ist NICHT das gekaufte Produkt.

## 5. Frontend-Angebot (Capability Contract — Ist + Luecken)

Heutige Endpunkte (IMPLEMENTED, JWT):
- GET /platform: NUR {name, version, environment} — KEINE Capability-/Feature-Liste. [B: handler.py _handle_platform]
- GET /me: Identitaets-Echo (sub/email/tenant/groups). [A]
- GET /me/profile: Profil ODER 404 (Existenz-Signal, kein Auto-Provision). [A]
- GET /agents: NUR entitled Agents (agentId/name/description/version/capabilities/status) — Backend filtert, Frontend zeigt; KEINE Unterscheidung "freischaltbar vs. gesperrt", KEINE Offer-Sicht. [A: PLATFORM_FRONTEND_INTEGRATION §5 + handler.py]
- JobSearch/ATS/CV/Documents: Routen vorhanden (handler-intern bzw. GW), aber KEIN Feature-Flag-/Capability-Endpoint.

Anzeige-Matrix (Ist):

| Anzeige | Quelle heute | Status |
|---|---|---|
| Profil | GET /me/profile (200/404) | IMPLEMENTED |
| CV Storage | nur via Aufruf (Upload-Presign Erfolg/Fehler), kein Capability-Signal | OPEN (kein Flag-Endpoint) |
| JobSearch | nur via Aufruf, kein Capability-Signal | OPEN |
| ATS | nur via Agent-Ausfuehrung, kein Capability-Signal | OPEN |
| API Access | kein Begriff/Endpoint | OPEN |
| API Profile | existiert nicht | OPEN (E) |
| Agent A | GET /agents (enthalten = entitled) | IMPLEMENTED (Positivliste) |
| Agent B (nicht enthalten) | von Positivliste UNUNTERSCHEIDBAR ob "nicht existent / nicht entitled / inaktiv" | OPEN (kein Grund-Signal; Backend 403/404 bleibt massgeblich) |

Contract-Regel (DECIDED, bestaetigt): Frontend zeigt, Backend entscheidet — jede Ausfuehrung wird serverseitig neu geprueft; Entitlements koennen sich ohne Frontend-Update aendern. [A: PLATFORM_FRONTEND_INTEGRATION §5]

## 6. Agent Catalog / Eligibility (Kette — DECIDED Ist-Stand)

API Profile (kuenftig) -> Agent Entitlement (user x agent x Zeit, DDB `entitlements`) -> Agent Catalog (DDB `agent-catalog`, Hash agentId; RIS-seitig zentral) -> CatalogAdapter (Lazy-Load in Registry) -> Registry (AgentDescriptor: status/capabilities/body/runtime) -> Discovery -> Eligibility (Deskriptor-Kompatibilitaet, KEINE Entitlements) -> Selection (first_match) -> Execution (Body -> Domain-Agent).

DECIDED: Ein Job Matcher besitzt NICHT die Agenten — der Katalog bleibt RIS-seitig zentral (Tabelle + Registry + Handler-Gates). Matcher sind Consumer des JWT-Pfads, keine Catalog-Owner. [A: TF dynamodb-Modul, catalog_adapter, Gate-7/8/9]

## 7. API Credential Security (NUR Contract-Anforderungen, alle future — PREPARED)

Fuer eine spaetere Implementierung gelten muessen (kein Code, keine Auswahl vorweggenommen):
- Credential ≠ Cognito-Passwort; Credential ≠ Cognito-JWT (eigener Auth-Pfad, eigene Pruefstelle).
- API Key/ Secret NIE als Klartext dauerhaft speichern (nur Hash/Referenz + Metadaten).
- Rotation (Ablauf + Ersatz ohne Profil-Neuanlage), Revocation (sofort, pro Credential + pro Profil), Status (active/suspended/revoked), Ablauf/Deaktivierung.
- Auditierbarkeit (wer/wann/welches Profil — CloudTrail-/Log-Anschluss faehig, keine Inhalte in Logs).
- User-/Tenant-Isolation (Credential gilt nur im Profil-Kontext des Owners; kein Cross-Tenant).
- API-Profile-Isolation (Credential aus Profil 1 gilt nie in Profil 2).
- Agent-Authorization: Credential prueft PROFIL-Zugang; Agent-Zugriff bleibt Entitlement-Sache (zwei Stufen, keine Vermischung).

## 8. Abgrenzung — Verantwortungsmatrix (nur Belegtes; Rest OPEN)

| Objekt | Zweck | Owner | Persistenz | Auth-Kontext | Darf Client sehen? |
|---|---|---|---|---|---|
| Identity | Wer ist der Benutzer (sub/tenant/groups) | Cognito (externer IdP-Dienst) | Cognito Pool | JWT (Authorizer) | Ja (eigene Claims via /me) |
| UserProfile | Persoenliche Anwendungsdaten (v1-Felder) | RIS Platform (DDB) | `user-profile` (Hash userId) | JWT + sub-Bindung | Ja (eigenes, via /me/profile) |
| Offer | Freischaltbares Angebot | OPEN (kein Owner definiert) | keine | — | OPEN |
| Entitlement | Techn. Zugriffsrecht user x agent x Zeit | RIS Platform (DDB) | `entitlements` (Hash entitlementId, GSI userId/agentId) | JWT + Handler-Gate (403) | Indirekt (nur entitled Agents via /agents) |
| API Profile | API-Zugangs-/Client-Kontext eines Owners | OPEN | keine | — (kuenftig: Credential + JWT?) | OPEN |
| Client/Application | Produkt-Kontext (z.B. Job Matcher A/B) | Extern (Matcher per Vorgabe clientseitig) / OPEN (RIS-seitig kein Objekt) | keine (RIS) | JWT (heute ungetrennt) | N/A |
| Credential | Techn. Zugangsmittel eines API Profiles | OPEN | keine | — (darf NICHT Cognito-Passwort/JWT sein) | Nein (nur Ausgabezeitpunkt + Metadaten) |
| Agent Catalog | Zentrale Agent-Beschreibungen | RIS Platform (DDB + Registry) | `agent-catalog` (Hash agentId) | JWT (Lesen via /agents + Registry-Lazy) | Ja (gefilterte Liste) |
| JobSearch Profile | JobSearch-Domaene je User (Modelle + CRUD) | RIS Platform (Repository, tenant-scoped) | `jobsearches` (Verdrahtung je Stand) | JWT | Ja (eigene) |
| ATS Profile | Eigenstaendiges ATS-Profil-Objekt | OPEN (nur Domaenenmodell ATSSearchProfile in JobSearch) | keine | — | OPEN |
| CV Document | Private Nutzer-Dokumente (Storage only) | RIS Platform (S3, kein Metastore) | `mays-ris-*-documents` (Key tenant/users/sub/uuid) | JWT + Presign (900s) | Ja (eigene, via Presigned-URLs) |

## 9. Entscheidungs-Matrix

| Entscheidung | Status | Aktuelle Evidenz | Benoetigt fuer |
|---|---|---|---|
| User Identity | DECIDED (Cognito-zentral) | ARCH §4, Gates 10/11/13A, TF cognito-Modul | — (Basis steht) |
| Authentication | DECIDED (USER_PASSWORD_AUTH primaer; Google optional/AUS) | Gate 10/13A, TF-Client | 13B (Test-Account) |
| UserProfile | IMPLEMENTED | Gate 12 (live 201/409/404/PUT), API-STANDARD | — |
| Offers | OPEN | 0 Treffer (kein Modell/Preis/Vergabe) | Offer-Definition + Owner-Entscheid |
| Entitlements | IMPLEMENTED (handler-seitig) | handler.py Gates, DDB-Tabelle, /agents-Filter | Harte Pipeline-Regeln (OPEN, RUNTIME-PATH) |
| API Profile | OPEN (neue Idee, untersucht) | 0 Treffer (dieser Report §1-3) | Objektmodell + Ownership + Lifecycle-Entscheid |
| Client/Application | OPEN (RIS-seitig kein Objekt) | TEAM_COLLABORATION (D: extern) vs. Gate-9-Realitaet | Produktmodell-Entscheid (nicht hier) |
| API Credentials | OPEN | 0 Treffer (kein Modell) | Security-Design (§7) + Ausgabe-/Speicher-Entscheid |
| API Profile Ownership | OPEN | nichts belegt | Owner-Regel (User vs. Orga vs. Admin) |
| API Profile Provisioning | OPEN (A-D alle offen) | Negativ-Seite entschieden (§4) | Vergabestelle + Prozess-Entscheid |
| Agent Entitlements | IMPLEMENTED (Mechanismus) / OPEN (Profil-Bindung) | Tabelle + Handler-Gates | Profil-zu-Entitlement-Mapping (spaeter) |
| Frontend Capability Contract | OPEN (Positivliste existiert) | /agents (A), Rest E | Capability-/Flag-Endpoint-Entscheid (spaeter) |
| Multi-Client | OPEN (Technik bedingt moeglich) | JWT-Pfad ungetrennt (§3) | API-Profile-Entscheid (BLOCKED davon) |
| JobSearch Integration | B (Domaene + Routen; Client-Abgrenzung D/OPEN) | Gate 9, handler /me/jobsearches*, Discovery-Report | Vertragsklaerung (separat) |

## 10. Dokumentations-Folgen (§12 Auftrag — nur Feststellung, KEIN Umbau)

Betroffene Dokumente WENN das Modell spaeter implementiert wuerde (heute NICHT geaendert, da keine belegte Korrektur ansteht):
- SYSTEM-ARCHITECTURE.md (§4 Identity, §6 Status): Offer/API-Profile/Credential-Begriffe + Kette §6 — fehlt ALLES (Entscheid noetig).
- API-STANDARD.md: Capability-/Profil-Routen — fehlen (Entscheid noetig).
- PLATFORM_FRONTEND_INTEGRATION.md: Capability-Vertrag §5ff — nur Positivliste (Entscheid noetig).
- ROADMAP.md / PROJECT_STATUS.md: Produktentscheidungen abbilden (erst nach Entscheid).
- TEAM_COLLABORATION.md: Job-Search-Eigentum D-Widerspruch (separater Klaerungsbedarf, NICHT dieses Gate).
- Neue Begriffe noetig (alle OPEN): API Profile, Client/Application-Kontext (RIS-seitig), API Credential, Offer, Profil-Provisioning.
- Minimal-Update in DIESEM Gate: KEINES an kanonischen Docs (keine belegte Korrektur; Contract ist neu, kein Widerspruch zu heilen). Konvention bestaetigt: README/ARCH/API bleiben gueltig.

## 11. Checkpoint (Bereichs-Ergebnisse)

| Bereich | Ergebnis |
|---|---|
| Discovery | GREEN (Quellen + Greps + Code-Stichproben, nichts erfunden) |
| Identity | DECIDED (Cognito-zentral, JWT-Grenze) |
| UserProfile | IMPLEMENTED (Gate-12-v1, sub-gebunden) |
| Offers / Entitlements | Offers OPEN (0 Treffer) / Entitlements IMPLEMENTED (handler-seitig, DDB) |
| API Profile | OPEN (neue Idee, 0 Treffer, untersucht — NICHT implementiert) |
| Client / Application | OPEN (RIS-seitig kein Objekt; Matcher clientseitig per Vorgabe) |
| Credentials | OPEN (0 Treffer; Anforderungen §7 PREPARED) |
| Multi-Client | OPEN (Technik bedingt moeglich, Vertrag fehlt; Q1/Q2/Q5/Q6 OPEN, Q4 DECIDED-ja, Q7 handler-seitig) |
| Agent Authorization | DECIDED Ist-Stand (Handler-Gates; Pipeline ohne Entitlements — dokumentiert) |
| Frontend Capability Contract | OPEN (nur /agents-Positivliste + Basis-Echo; kein Flag-Endpoint) |
| Provisioning | OPEN (A-D alle offen; nur Negativ-Seite entschieden) |
| Documentation | GREEN (Report + Log; keine kanonische Doku geaendert — keine belegte Korrektur) |
| Tests | Nur Discovery (keine Aenderung, keine Ausfuehrung noetig) |
| AWS Mutation | NONE (verifiziert: kein AWS-Kontakt) |
| Git | Report + Log (Commit folgt); sonst sauber bis auf pre-existing Untracked |

Wichtigste OPEN Decisions (keine Reihenfolge-Wertung):
1. Offer-Modell (Definition + Owner + Vergabestelle) — BLOCKT Provisioning + Monetarisierung.
2. API-Profile-Objektmodell (Ownership User/Orga/Admin + Lifecycle + Client-Bindung) — BLOCKT Multi-Client-Trennung + Credential-Design.
3. Credential-Mechanismus (Typ/Speicherung/Ausgabe/Rotation/Revocation) — BLOCKT jede externe API-Nutzung ausserhalb JWT.
4. Frontend-Capability-Vertrag (Flag-/Capability-Endpoint vs. reine Positivliste) — BLOCKT Angebots-Anzeige (Agent B ✗-Fall).
5. Harte Entitlement-Regeln im Worker-Pfad (Pipeline vs. Handler-only) — sicherheitsrelevant, RUNTIME-PATH-OPEN.
6. JobSearch-Eigentum/Abgrenzung (D-Widerspruch TEAM_COLLABORATION vs. Gate 9) — separater Klaerungsbedarf.

**HARD STOP (keine Implementierung).**
