# RIS-APIPROFILE-CONTRACT-02 — Administrator / Staff / Owner / APIProfile Contract

STATUS: Contract entschieden (KEINE Implementierung, KEIN AWS, KEIN TF, KEIN Cognito-/DB-/Lambda-/API-Eingriff, KEINE Credentials, KEIN Offer-Modell, KEINE Capability-API)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, d0020aa
- Basis: PROMPT 01 (RIS-PRODUCT-PLATFORM-STANDARDS-ROLE-MODEL-DISCOVERY-01) + Bestand (RIS-Code, TF-Cognito, Gates 10/11/12/13A/14, kanonische Docs). PROMPT-01-Fakten werden NICHT veraendert, nur entschieden bzw. als OPEN fortgefuehrt.
- Methode: Quellenpruefung (§2) + Entscheidung je Rolle/Objekt mit Begruendung; Klassen DECIDED/EXISTING/STANDARD/RECOMMENDED/OPEN/DEFERRED. Nichts erfunden; nichts implementiert.
- Classification: GREEN (Contract) — alle PROMPT-02-Fragen entschieden oder begruendet offengelassen.
- Terraform/AWS/Cognito/DB/API Checks: KEINE (Scope-Verbot; keine Mutation).
- Git: nur diese beiden Reports (s. Commit).
- Next: PROMPT-03-Empfehlungen (§16) -> HARD STOP.

## 1. Executive Summary

- Administrator: GENAU EINE fachliche Rolle (Fachbegriff "Administrator", technische Gruppe `admins`); `Admin` = dokumentierte Kollisions-Dopplung (deprecated, KEIN TF-Eingriff in diesem Gate). Volle Management-Rechte (Profile-Lifecycle, Credentials spaeter, Entitlements, Offers spaeter, Audit-Leserecht) — aber KEINE automatischen Usage-Rechte.
- Staff: EIGENSTAENDIGE eingeschraenkte Management-Rolle (Support: lesen, auditieren, deaktivieren mit Grund, reaktivieren NUR selbst-gesperrter Profile, Credential-Revoke/Reissue im Support-Fall). VERBOTEN: anlegen, freigeben (PENDING->ACTIVE), Entitlement-/Offer-Aenderungen, Admin-Verwaltung, terminales REVOKED.
- Operator (`mayaws`): AUSSCHLIESSLICH Deployment-Kontext — KEINE fachliche Rolle (bestaetigt).
- Owner: AUSSCHLIESSLICH `ownerUserId` (Ersteller-Prinzip, Analogie JobSearch-Owner). KEIN tenantOwner/organizationOwner/assignedUser/Shared (kein Beleg). Tenant ≠ Owner (bestaetigt).
- APIProfile: eigenstaendiges Objekt (1 User — n Profile, isolierte Kontexte, strikt ≠ API Key); 11-Felder-Object-Contract (§8); Lifecycle PENDING/ACTIVE/DISABLED/EXPIRED/REVOKED mit Actor-Regeln (§9); `clientRef` OPTIONAL-Attribut (max. ein Client je Profil, mehrere Profile je Client moeglich, KEIN Client-Objekt) (§10); Entitlements NUR additiv/Union (Entzug durch Abwesenheit UNMOEGLICH) (§11); Management-Plane ≠ Usage-Plane als Architekturregel (§12).

## 2. Ausgangslage (Quellenpruefung — keine Veraenderung seit PROMPT 01)

- HEAD = d0020aa (PROMPT-01-Commit); tracked tree clean; `git log d0020aa..HEAD` ueber terraform/modules/cognito, lambda/handler.py, agents/ecosystem, jobsearch, docs/architecture, docs/api, installer = LEER. Alle PROMPT-01-Fakten (§1 des Auftrags) gelten unveraendert — explizit festgestellt, nichts stillschweigend uebernommen.
- Einzige zusaetzliche Verifikation: Cognito-Gruppennamen sind case-sensitiv und erscheinen verbatim im `cognito:groups`-Claim (Handler spiegelt nur) — daher ist die `admins`/`Admin`-Kollision sicherheitsrelevant (zwei verschiedene Claims-Werte) und MUSS kanonisch aufgeloest werden (§3C), auch wenn die Bereinigung erst spaeter implementiert wird.

## 3. Administrator Contract (DECIDED)

- A) GENAU EINE fachliche Administrator-Rolle. Begruendung: Zwei Admin-Begriffe ohne Unterschied erzeugen Claim-Mehrdeutigkeit (case-sensitive Gruppen) und pruefbare Rechte-Luecken; kleinste konsistente Ordnung ist eine Rolle.
- B) Kanonisch: Fachbegriff `Administrator`; technische Cognito-Gruppe `admins` (passt zur bestehenden Kleinschreib-Familie candidates/recruiters/admins).
- C) Gruppe `Admin` (aus dem verbatim-Namenssatz Admin/Staff/user-user/user-requier): wird als DEPRECATED-Alias dokumentiert — bleibt technisch bestehen (KEIN TF-Eingriff in diesem Gate, Scope-Verbot), erhaelt KEINE Semantik, Bereinigung (Entfernen nach Migration) = spaeteres Implementierungs-Gate. [DECIDED-Dokumentation, DEFERRED-Bereinigung]
- D) Administrative Aktionen (alle NUR fachlich definiert, NICHT implementiert):
  - APIProfile: anlegen (fuer sich oder Ziel-User), aendern (alle mutablen Felder §8), aktivieren (PENDING->ACTIVE), deaktivieren (ACTIVE<->DISABLED), revozieren (terminal, §9).
  - Credentials (spaeter): ausstellen, revozieren, Reissue, Ablauf setzen.
  - Entitlements: vergeben und entziehen (user-weit UND profil-gebunden, §11).
  - Offers (spaeter, wenn Modell existiert): verwalten.
  - Audit: lesen (alle fachlichen Aenderungen + Zugiffs-Fehlversuche).
- NICHT enthalten: Usage-Rechte kraft Rolle (§12), Deployments/Infrastruktur (Operator-Domaene), Identitaets-Verwaltung ausserhalb Rollen-Zuweisung (Pool/Client bleiben TF-Domaene).

## 4. Staff Contract (DECIDED — eigenstaendige enge Rolle)

- Staff IST eine eigenstaendige fachliche Rolle (kein "Admin light" ohne Zweck): Begruendung ist der Support-Fall (kompromittiertes Profil SOFORT sperren + Credential ungueltig machen + nach Klaerung entsperren), ohne dafuer volle Admin-Macht (Freigaben, Entitlements, Modell-Politik) zu vergeben — Least Privilege + Trennung Betrieb vs. Politik.
- ERLAUBT: lesen (Profile/Status/Audit), Support (Auskunft zum eigenen Fall), deaktivieren MIT Grund (auditiert), reaktivieren NUR selbst-gesperrter Profile (Fremd-Sperren — auch Admin-Sperren — bleiben dem Sperr-Akteur vorbehalten), Credential-Revoke + Reissue IM Support-Fall (auditiert).
- VERBOTEN: anlegen, PENDING->ACTIVE-Freigabe, Entitlement-Aenderung (Vergabe/Entzug), Offer-Aenderung, Administrator-Verwaltung (Gruppen-Zuweisung), terminales Profil-REVOKED (Admin-exklusiv), EXPIRED-Ueberstimmung ausser via Admin-Verlaengerung.
- Technische Gruppe: `Staff` (bestehend, erhaelt damit erstmals Semantik — Dokumentations-Entscheid, keine TF-Aenderung noetig).

## 5. Operator Boundary (DECIDED — bestaetigt, nichts erfunden)

- `mayaws` = AWS-CLI-Profilname + Installer-`--profile` (Deployment-/Installationskontext: WELCHER Account, WELCHES Profil installiert). Es ist KEINE User-, Administrator-, Staff-Rolle, KEIN APIProfile-Owner, KEIN Application-Owner. Eine fachliche Operator-Rolle wird NICHT eingefuehrt (kein Anwendungsfall im App-Modell; Infrastruktur-Betrieb bleibt ausserhalb des RIS-Berechtigungsmodells).

## 6. Owner Contract (DECIDED)

- A) JA: `ownerUserId` ist der ALLEINIGE Owner (Ersteller-Prinzip — direkte Analogie zum EXISTING JobSearch-Owner "Expected owner's user ID" = anlegender User; konsistent mit sub-gebundenem UserProfile und Tenant-Isolation).
- B) NEIN zu allem Weiteren: KEIN tenantOwner (Tenant = Isolation, kein Akteur), KEINE organizationOwner (kein Orga-Begriff im Repo — spaetere separate Erweiterung, NICHT dieser Contract), KEIN assignedUser (kein Sharing-Begriff; Teilen = neues Profil + eigene Entitlements), KEIN Shared Ownership (kein Beleg, wuerde Audit-Zuordnung verwischen).
- Admin-Anlage FUER Ziel-User: erlaubt (createdBy=Admin-Akteur, ownerUserId=Ziel-User) — Ownership bleibt beim Ziel-User, nicht beim Anlegenden (Ausnahme vom reinen Ersteller-Prinzip, explizit entschieden und auditiert).

## 7. APIProfile — Fachliche Definition (DECIDED)

- APIProfile = fachlicher API-Nutzungskontext eines Owners (Buendel aus: Identitaet des Profils + Owner + optionaler Client-Bezug + Entitlements + spaeteren Credentials). STRIKT NICHT: API Key, Passwort-Ersatz, JWT-Ersatz, Agent (Ausfuehrung bleibt RIS-zentral).
- Struktur (Zielbild, bestaetigt): User 1—n APIProfile (A, B, ...); jedes Profil mit eigenen Entitlements + eigenem clientRef + spaeter eigenen Credentials; Profile bilden VONEINANDER GETRENNTE Nutzungskontexte (Profil-Isolation, §13).
- Ein User DARF mehrere APIProfiles besitzen (DECIDED — sonst kein Multi-Client-Modell); mehrere Matcher ueber getrennte Profile (DECIDED — Trennung ueber Profile, nicht ueber Identitaeten).

## 8. APIProfile Object Contract (DECIDED — Minimalfelder)

| Feld | Pflicht | Bedeutung | Veraenderlich | Wer darf aendern | Audit |
|---|---|---|---|---|---|
| apiProfileId | Ja | Stabile Profil-Identitaet (systemvergeben; exaktes Format = Implementierungsdetail) | NEIN (immutable) | Niemand (System bei Anlage) | Ja (Objekt-Identitaet) |
| name | Ja | Menschenlesbarer Name (eindeutig je Owner: ownerUserId+name — RECOMMENDED, verhindert Verwechslung) | Ja | Owner + Administrator | Ja |
| description | Nein | Freitext-Zweckbeschreibung | Ja | Owner + Administrator | Nein (niedrig; Aenderungszeit via updatedBy/updatedAt) |
| ownerUserId | Ja | Fachlicher Eigentuemer (Cognito-sub; §6) | NEIN (kein Transfer — Transfer = Neuanlage) | Niemand (System bei Anlage; Admin-Anlage fuer Ziel-User erlaubt) | Ja |
| clientRef | Nein (NULL = ungebunden) | Optionale Client-Zuordnung, opaker stabiler Identifier (§10) | Ja | NUR Administrator | Ja |
| status | Ja | Lifecycle-Zustand (§9) | Ja (nur erlaubte Uebergaenge) | Administrator (+ Staff eng, §9) | Ja (jede Aenderung mit von/nach/Grund) |
| createdAt | Ja | Anlagezeitpunkt | NEIN | System | Ja |
| updatedAt | Ja | Letzte Mutation | System (jede Mutation) | System | Ja |
| expiresAt | Nein (NULL = kein Ablauf) | Gueltigkeitsende (treibt EXPIRED) | Ja | NUR Administrator | Ja |
| createdBy | Ja | Anlegender Akteur (User- oder Admin-Identitaet + Akteur-Typ) | NEIN | System bei Anlage | Ja |
| updatedBy | Ja | Letzt-aendernder Akteur | System (jede Mutation) | System | Ja |

- VERBOTEN im APIProfile (DECIDED): Credential-/Key-Werte, Secrets, Passwoerter, Klartext-Tokens, JWT-Ablagen. Profil speichert NUR Referenzen + Metadaten (spaeteres Credential-Objekt haengt AM Profil, liegt NICHT darin).

## 9. Lifecycle Contract (DECIDED — PENDING bleibt)

- PENDING BLEIBT (gegen die Streich-Option entschieden): Begruendung ist der Freigabe-Vorbehalt — ohne PENDING waere jedes angelegte Profil SOFORT nutzbar und widerspraeche expliziter Vergabe (Anfrage/Freigabe- und Admin-Vorab-Anlage-Faelle). PENDING = angelegt, NICHT nutzbar (keine Credential-Pruefung erfolgreich, keine Entitlements wirksam).

| Zustand | Bedeutung | Eintritt | Erlaubte Uebergaenge | Actor | Reversibel/Terminal |
|---|---|---|---|---|---|
| PENDING | Angelegt, Freigabe ausstehend | Anlage (Request oder Admin-Vorab) | -> ACTIVE (Freigabe/Aktivierung); -> REVOKED (Rueckzug) | NUR Administrator | Reversibel (via REVOKED-Ausstieg, keine Nutzung dazwischen) |
| ACTIVE | Nutzbar | Freigabe; Entsperrung; Verlaengerung | -> DISABLED; -> REVOKED; -> EXPIRED (automatisch) | Admin (alle); Staff (nur DISABLED mit Grund) | Reversibel |
| DISABLED | Administrativ gesperrt | Sperr-Akt (mit GRUND-Pflicht) | -> ACTIVE (Entsperrung: Admin immer; Staff NUR selbst-gesperrte); -> REVOKED | Admin + Staff (Sperre); Entsperrung s. Regel | Reversibel |
| EXPIRED | Zeitablauf (aus expiresAt ABGELEITET, kein manueller Akt) | System bei Fristueberschreitung | -> ACTIVE (NUR via Verlaengerung = neues expiresAt); -> REVOKED | System (Eintritt); Administrator (Verlaengerung/Cleanup) | Abgeleitet, kein Akteur-Uebergang |
| REVOKED | Endgueltig entzogen | Admin-Akt (Missbrauch/Vertragsende) | KEINE (terminal; Neuanlage noetig) | NUR Administrator | TERMINAL |

- Credentials folgen dem Profil-Status SOFORT (DISABLED/EXPIRED/REVOKED = keine erfolgreiche Pruefung; Details = Credential-Gate). Staff darf KEIN terminales REVOKED ausloesen und KEIN EXPIRED ueberstimmen.

## 10. ClientRef Contract (DECIDED — Attribut, kein Objekt)

- `clientRef` = OPTIONALER, opaker, stabiler Identifier (KEIN Lifecycle-Objekt, KEINE eigene Domaene — bestaetigt PROMPT-01-Empfehlung; ein Client-Objekt ist derzeit NICHT benoetigt, explizit dokumentiert).
- NULL ERLAUBT (ungebundenes/client-unabhaengiges Profil — z.B. vor Client-Zuordnung oder bewusst clientfrei).
- Identifiziert den Produkt-Client (z.B. Job Matcher A/B) als Zeichenkette; RIS interpretiert sie NICHT (keine Validierung gegen Register — sonst Schein-Architektur). Empfohlenes Format (RECOMMENDED, nicht normativ): stabiler, display-unabhaengiger Bezeichner.
- Veraenderlich NUR durch Administrator (auditiert). Bindungsregeln: EIN Profil max. EIN clientRef (scharfe Isolation); MEHRERE Profile duerfen DENSELBEN clientRef tragen (z.B. zwei Profile mit unterschiedlichem Entitlement-Umfang fuerselbe App — exakt der Matcher-A/B-Fall mit A/F/G vs. B/C/Z).

## 11. Entitlement Relationship (DECIDED — nur additiv/Union)

- A) JA: Ein APIProfile KANN eigene (profil-gebundene) Entitlements besitzen.
- B) JA: User-weite Entitlements gelten ZUSAETZLICH (bestehende Tabelle/Mechanik bleibt gueltig).
- C) NEIN: Ein APIProfile DARF KEINE Rechte entziehen — Abwesenheit im Profil schaltet user-weite Rechte NICHT ab.
- D) Profil wirkt AUSSCHLIESSLICH hinzu (Union-Semantik): wirksame Rechte = user-weite ∪ profil-gebundene.
- Sicherheitsbegruendung: Entzug durch Abwesenheit waere implizit, unpruefbar und audit-feindlich; expliziter Entzug bleibt Admin-Akt an der Entitlement-Quelle (Vergabe/Entzug D. in §3). Fail-closed bleibt erhalten (Abwesenheit UEBERALL = kein Zugriff).
- Worker-Pfad: UNVERAENDERT spaeteres Gate (keine Implementierung hier).

## 12. Management vs Usage (DECIDED — Architekturregel)

- MANAGEMENT PLANE: Profile administrieren, Lifecycle aendern, Credentials verwalten (spaeter), Entitlements verwalten, Audit lesen. Traeger: Administrator (+ Staff eng).
- USAGE PLANE: API benutzen, Agents ausfuehren, JobSearch-/Agent-Funktionen verwenden. Traeger: authentifizierter User IM Profil-Kontext (spaeter Credential) — NIEMALS die Admin-Rolle als solche.
- REGEL (verbindlich): Administrator-/Staff-Rechte ersetzen KEINE Usage-Rechte. Ein Admin ohne gueltiges (profil-gebundenes oder user-weites) Entitlement erhaelt an Usage-Gates 403 wie jeder andere User. Umgekehrt verleiht Usage KEINE Management-Rechte. Beide Ebenen werden GETRENNT geprueft und GETRENNT auditiert (Vorbild: OpenAI Admin-Keys duerfen keine Nutzungs-Endpoints aufrufen — VENDOR PATTERN, PROMPT 01 §4).

## 13. Security Contract (DECIDED — nur Contract-Regeln)

- User-Isolation (EXISTING: sub-Bindung) + Tenant-Isolation (EXISTING: Claim + Guards) bleiben gueltig und gelten fuer Profile/Entitlements/Credentials gleichermassen.
- Profile-Isolation (NEU, verbindlich): Credential aus Profil 1 gilt NIE in Profil 2; Entitlements wirken nur im passenden Kontext (Union §11, kein Cross-Profil).
- Owner-Bindung (NEU): jede Profil-Mutation prueft Owner- ODER Admin/Staff-Kompetenz (§§3/4/8); Fremd-Profile sind ohne Management-Rolle nicht adressierbar.
- Kein Secret im APIProfile; kein Credential-Wert im APIProfile (§8-Verbot).
- Audit fuer JEDE fachliche Aenderung (Actor/Zeit/von-nach/Grund; secrets-frei).
- Backend entscheidet IMMER (Handler-/spaeter Pipeline-Gates); Frontend ersetzt NIEMALS Authorization (bestaetigt PROMPT-01-§11/PLATFORM_FRONTEND_INTEGRATION §5).

## 14. Decision Matrix

| Thema | Entscheidung | Begruendung | Klasse |
|---|---|---|---|
| Eine Administrator-Rolle | Genau eine; Fachbegriff Administrator; Gruppe `admins` | Claim-Eindeutigkeit (case-sensitiv), kleinste Ordnung | DECIDED |
| `Admin`-Doppelgruppe | Deprecated-Alias, keine Semantik, Bereinigung spaeter (kein TF-Eingriff hier) | Kollision dokumentiert statt synonymiert; Scope-Verbot | DECIDED (+ DEFERRED-Bereinigung) |
| Admin-Aktionen (Profile/Credentials/Entitlements/Offers/Audit) | Fachlich definiert, nicht implementiert | Spec-Katalog §3D + Plane-Trennung | DECIDED |
| Staff als Rolle | Eigenstaendig, eng (Support: lesen/sperren-mit-Grund/entsperren-selbst-gesperrter/Revoke-Reissue-im-Supportfall) | Support-Lockout-Bedarf + Least Privilege | DECIDED |
| Staff-Verbote | Kein Anlegen/Freigeben/Entitlement/Offer/Admin-Verwaltung/REVOKED | Trennung Betrieb vs. Politik | DECIDED |
| Operator | Nur Deployment-Kontext, keine Rolle | Ist-Stand + Infra/App-Trennung | DECIDED |
| Owner | Nur ownerUserId (Ersteller; Admin-Anlage fuer Ziel-User erlaubt) | Analogie JobSearch-Owner; kein Beleg fuer mehr | DECIDED |
| Kein tenant/org/assigned/shared Owner | Nicht eingefuehrt | Kein Bedarf belegt; Orga = separate Erweiterung | DECIDED (Negativ-Entscheid) |
| Tenant ≠ Owner | Bestaetigt | Tenant = Isolation, kein Akteur | DECIDED |
| APIProfile-Objekt + 11 Felder | Wie §8 (Pflicht/Immutabilitaet/Actor/Audit) | Minimalcontract aus Zielbild + JobSearch-/Profil-Analogien | DECIDED |
| Secret-Verbot im Profil | Absolut | Credential-Hygiene (Standard) | DECIDED |
| PENDING bleibt | Freigabe-Vorbehalt braucht nicht-nutzbaren Startzustand | Funktional begruendet, kein Produkt-Kopie | DECIDED |
| Lifecycle-Uebergaenge/Actoren | Wie §9-Tabelle (inkl. Staff-nur-selbst-gesperrt + terminales REVOKED nur Admin) | Auditierbarkeit + Least Privilege | DECIDED |
| clientRef optional/Attribut/kein Objekt | NULL ok; max. eins je Profil; mehrere Profile je Client; Admin-only-Mutation | Isolation schaerfen ohne Schein-Domaene | DECIDED |
| Entitlement-Union (nur additiv) | Profil entzieht nie; wirksam = user ∪ profil | Impliziter Entzug waere unpruefbar (Security) | DECIDED |
| Management ≠ Usage | Getrennte Pruefung/Audit; Admin erhaelt keine Usage-Rechte kraft Rolle | OpenAI-Plane-Trennung (Pattern) + Fail-closed | DECIDED (+ STANDARD-Einfluss) |
| Gruppen-Semantik Altbestand | Unveraendert (nur Admin/Staff erhalten Semantik) | Kein Anlass, intakt lassen | EXISTING |
| Gruppen-Bereinigung (`Admin` entfernen) | Spaeteres Implementierungs-Gate | Scope-Verbot (kein TF hier) | DEFERRED |
| Offer-Modell | Nicht in diesem Contract | Scope-Verbot (§: kein Offer-Modell) | OPEN (Prompt 01) |
| Credential-Mechanik | Nicht in diesem Contract | Scope (§15/PROMPT 03) | OPEN |

## 15. Open Decisions (fuer PROMPT 03 — nichts vorweggenommen)

1. Credential-Typ (Key vs. Token/M2M-Fluss) — inkl. M2M-Anteils-Klaerung.
2. Client-Bindungs-Durchsetzung (Nachweis-Mechanismus fuer clientRef bei Credential-Gebrauch).
3. Secret Storage (Hash/Referenz-Format, Ablageort, Zugriffsrechte).
4. Rotation (Pflicht/Frissen, Ablauf ohne Profil-Neuanlage) + Ablauf-Maximalwerte.
5. Revocation-Mechanik (sofortige Wirksamkeit ueber Handler + Pipeline).
6. Credential Scopes (Anlehnung Entitlements vs. eigene Scope-Semantik).
7. Credential→APIProfile-Bindung (Ausstellungs-/Pruef-/Audit-Fluss).
8. Offer-Modell (Definition/Owner/Vergabe — blockt Monetarisierung, NICHT PROMPT 03).
9. Capability-Endpoint (Format/Umfang — NICHT PROMPT 03, Vormerkung).
10. Worker-Pfad-Entitlements (Nachpruefung vs. signierte Herkunft — sicherheitsrelevant, eigenes Gate).

## 16. PROMPT-03 Recommendations (Credential-Gate — KEIN Code)

1. C1: Credential-Typ entscheiden (M2M-Anteil vs. Matcher-Integrationsaufwand abwaegen; KEIN Automatismus "API Key").
2. C2: clientRef-Nachweis definieren (wie belegt ein Aufrufer die Client-Bindung — sonst bleibt Bindung Dekoration).
3. C3: Storage-Contract (Hash + Metadaten; Wert genau EINMAL bei Ausstellung; redacted/last_used/disabled/expires-Metadaten nach OpenAI-/OpenRouter-Vorbild).
4. C4: Revocation-vor-Rotation priorisieren (sofortige Sperrung ist der Sicherheitskern; Rotation ist Betriebskomfort).
5. C5: Scopes an Entitlements anlehnen (keine zweite Berechtigungswelt erfinden).
6. C6: Profil-Status als Pruefungs-Eingang verankern (DISABLED/EXPIRED/REVOKED = sofort unwirksam — §9-Bindung vorausgesetzt).
7. C7: Management-Aufrufe (Ausstellung/Revocation) ueber Admin-/Staff-Kompetenz + Audit-Pflicht an §12/§14 binden.

**HARD STOP (keine Implementierung, keine Mutation).**
