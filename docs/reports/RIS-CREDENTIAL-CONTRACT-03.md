# RIS-CREDENTIAL-CONTRACT-03 — Credential Contract (APIProfile-Credentials)

STATUS: Contract entschieden (KEINE Implementierung, KEIN AWS, KEIN TF, KEIN Cognito-/DB-/Lambda-/API-Eingriff, KEINE Credential-Erzeugung, KEINE echten Keys, KEIN Offer-Modell, KEIN Capability-Endpoint, KEINE Worker-Auth-Implementierung)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, 09efe9e
- Basis: PROMPT 01 (Standards/Rollen-Discovery) + PROMPT 02 (APIProfile-Contract) + Bestand (Code, TF-Cognito/API-GW, Gates 10/11/12/13A/14, kanonische Docs). PROMPT-01/02-Feststellungen werden NICHT veraendert, nur die offenen C1-C7 entschieden.
- Methode: Quellenpruefung (§3) + Entscheidung je Credential-Frage mit Begruendung; Klassen DECIDED/EXISTING/STANDARD/VENDOR PATTERN/RECOMMENDED/OPEN/DEFERRED. Nichts erfunden; nichts erzeugt.
- Classification: GREEN (Contract) — alle C1-C7 entschieden oder begruendet vertagt.
- Terraform/AWS/Cognito/DB/API/Credential-Generation: KEINE (Scope-Verbot; verifiziert keine Mutation).
- Git: nur diese beiden Reports (s. Commit).
- Next: PROMPT-04-Empfehlungen (§20) -> HARD STOP.

## 1. Executive Summary

- Credential-Typ (C1, DECIDED als Kombination mit getrennten Boundaries): (a) Browser/Benutzer-Login und authentifizierte Benutzeraufrufe BLEIBEN Cognito-JWT (EXISTING, unveraendert — Identitaets-Boundary); (b) Matcher-/Server-/M2M-/Dritt-API-Zugriff erhaelt EIGENE opake Bearer-Credentials, gebunden an genau EIN APIProfile (RECOMMENDED-Typ, kein JWT, kein Cognito-Ersatz). OAuth-Client-Credentials-Grant als M2M-Fluss ist DEFERRED (kein Authorization Server vorhanden; kein Delegations-Bedarf belegt).
- clientRef (C2, DECIDED): zunaechst NUR Metadaten/Audit — KEINE Sicherheitsbindung, weil kein Mechanismus ohne neue Client-Domaene/PKI beweisbar ist. Durchsetzung erfolgt ueber Credential→Profil-Bindung + Profil-Status + Entitlements; pro Client trennt man ueber EIGENE Credentials (Widerruf pro App ohne Kryptographie-Beweis).
- Storage (C3, DECIDED): DDB-Metadaten + deterministischer Lookup-Digest (SHA-256, domain-separiert); Klartext nach Ausstellung NIE wieder auslesbar; Negativ-Liste absolut (§6). Secrets Manager = DEFERRED-Option (nur bei Compliance-Bedarf).
- Revocation vor Rotation (C4, DECIDED): Profil REVOKED/DISABLED/EXPIRED => alle zugehoerigen Credentials SOFORT unwirksam; Credential-REVOKED => nur dieses. Pruefung pro Request serverseitig, keine langlebigen Positiv-Caches.
- Rotation (§7, DECIDED): B neues Objekt (neue ID), A per Default SOFORT ungueltig; Uebergangsfenster NUR als expliziter Admin-Akt mit Ablauf (auditiert). Profil/Entitlements/clientRef bleiben gleich.
- Ablauf (§8, DECIDED): Credential darf NIEMALS laenger WIRKSAM sein als sein Profil (effektiv = min); Ablauf PFLICHT mit RECOMMENDED-Maximum 366 Tagen; Profil-EXPIRED dominiert immer.
- Scopes (C5, DECIDED): KEINE zweite Berechtigungswelt — Credential traegt hoechstens EINSCHRAENKENDE Scopes (Teilmenge); effektiv = Scope ∩ (Profil-Entitlements ∪ User-Entitlements); ohne Scope-Angabe = volles Profil (nie Erweiterung).
- Pruefreihenfolge (C6, DECIDED): 12-Schritt-Contract (§11); PENDING/DISABLED/EXPIRED/REVOKED = keine Nutzung; 401 (unbekannt/ungueltig) vs. 403 (bekannt, aber unberechtigt/deaktiviert) analog Handler-Konvention.
- Bindung (C7, DECIDED): 1 Credential = genau 1 APIProfile; Transfer VERBOTEN; ownerUserId immutable; Profil-Revoke = alle Credentials unbrauchbar (als widerrufene Saetze erhalten, nicht geloescht).
- Lifecycle (§12, DECIDED): ACTIVE/DISABLED/EXPIRED/REVOKED — KEIN PENDING (Begruendung: Freigabe lebt auf Profil-Ebene; Ausstellung IST der Freigabe-Vollzug).

## 2. Ausgangslage (PROMPT-02-Bindungen — gelten unveraendert)

APIProfile eigenstaendig ≠ Credential; 1 User — n Profile; 1 Profil — n Credentials; Credentials gehoeren fachlich zum Profil; KEIN Credential-Wert im Profil; User-/Tenant-/Profil-Isolation verbindlich; Management ≠ Usage (Admin/Staff erhalten dadurch KEINE Usage-Rechte); clientRef optional; Entitlements = Berechtigungsbasis (handler-seitig, additiv/Union); Profilstatus steuert Nutzbarkeit. Alle C1-C7 waren OPEN — werden hier entschieden (§§4-11).

## 3. Quellenpruefung (keine Veraenderung seit PROMPT 02)

- HEAD = 09efe9e (PROMPT-02-Commit); tracked tree clean; `git log 09efe9e..HEAD` ueber PROMPT-01/02-Reports, TF-Cognito/API-GW, Handler, Ecosystem/Pipeline, JobSearch, Architektur/API-Docs, Installer = LEER. Explizit festgestellt, nichts uebernommen.
- Zusaetzlich verifiziert (technische Randbedingung, EXISTING): API-GW-Authorizer ist JWT-Typ mit `$request.header.Authorization`, Audience = App-Client, Issuer = Pool-Endpoint (terraform/modules/api/main.tf:21-33). KONSEQUENZ (RIS-SPECIFIC): Nicht-JWT-Authorization-Werte werden an der GW-Kante ABGEWIESEN — API-Key-Credentials koennen den bestehenden JWT-Pfad NICHT wiederverwenden (spaeter: eigener Pruefpfad, z.B. REQUEST-Authorizer oder Lambda-interne Pruefung — Design-Entscheid VOR Implementierung, nicht hier).
- Zusaetzlich bestaetigt (EXISTING-Analogie, kein Reuse): Gate-14-Presigns (900s, keine Creds an Browser, documents.py) belegen die Repo-Praxis "kurzlebige Delegation statt Secret-Weitergabe" — dasselbe Prinzip traegt C3/C4.
- Standards/Vendor Patterns: OAuth-2.0-Rollen/Client-Typen/Scopes/Client-Credentials-Grant [STANDARD, RFC 6749]; Bearer-Gebrauch (Header, keine Query) [STANDARD, RFC 6750]; Revocation/Introspection als eigene Mechanismen [STANDARD, RFC 7009/7662]; OIDC-sub [STANDARD]; Cognito-Gruppen + JWT-Authorizer + GW-Keys-nur-Metering [STANDARD, AWS]; IAM = Infra-Modell [STANDARD, nicht Endbenutzer]; OpenAI (projekt-scoped Keys, Scopes/Expiry, Wert-nur-bei-Erstellung, Admin≠Usage, Audit) + OpenRouter (pro-Key-Limits/Resets, Management-Key ohne Inference, pro-Endbenutzer-Key, GET-/key-Introspektion) [VENDOR PATTERN, 2026 verifiziert, NICHT als Standard bezeichnet].

## 4. Credential Type Decision (C1 — DECIDED als Kombination)

| Credential-Typ | Einsatzfall | Trust Boundary | APIProfile-Zuordnung | Entscheid |
|---|---|---|---|---|
| Cognito User JWT | Browser/User-Login; authentifizierte Benutzeraufrufe (alle heutigen /me-/agents-Pfade) | Identitaet (Mensch -> Cognito -> JWT) | KEINE (user-zentriert, profil-unabhaengig) | BLEIBT (EXISTING, unveraendert) |
| Opaque Bearer-Credential (RECOMMENDED-Typ: zufaelliger, opaker Wert; Server-Lookup) | Job-Matcher-API-Zugriff; Server-to-Server; Dritt-Clients; kuenftige Nutzung ausserhalb eigenen Frontends | Programmatischer Zugriff (Client -> Credential -> Profil-Kontext) | GEBUNDEN an genau EIN APIProfile (§11) | NEU EINFUEHREN (spaeteres Gate; Contract hier) |
| OAuth 2.0 Access Token (JWT, selbsttragend) | — (kein Anwendungsfall ohne Authorization Server) | — | — | ABGELEHNT (kein AS vorhanden; Selbstvalidierung ohne Widerrufs-Kontrolle schwaecher als Server-Lookup) |
| OAuth Client Credentials / M2M-Fluss | Delegations-/Dritt-Szenarien mit eigenem Token-Lebenszyklus | — | — | DEFERRED (kein Delegations-Bedarf belegt; neu bewerten bei Dritt-Delegation) |
| Kombination JWT + opakes Credential | Mensch (JWT) UND Maschine (Key) koexistieren | Zwei Boundaries, strikt getrennt | Key-Seite profil-gebunden | DECIDED (keine Vermischung: Key ersetzt NIEMALS JWT-Login; JWT ersetzt NIEMALS Profil-Credential) |

Begruendung (NICHT "API Key, weil API Key"): Opakes Bearer-Format passt zur bestehenden Architektur (DDB-Lookup + Handler-Gates + sofortige serverseitige Revocation), entspricht OpenRouter-Praxis (Bearer + Management-Plane + Introspektion), vermeidet AS-/PKI-Komplexitaet, und haelt die GW-JWT-Kante unberuehrt (eigener Pruefpfad spaeter). Praesentation spaeter: Authorization-Header (STANDARD RFC 6750), NIEMALS Query-Parameter.

## 5. ClientRef Binding (C2 — DECIDED: zunaechst Metadaten/Audit)

- Fall A (clientRef = NULL): Credential OHNE Client-Bindung verwendbar — Gueltigkeit folgt ALLEIN Profil-Status + Entitlements (§§10-11). [DECIDED]
- Fall B/C ("matcher-a"/"matcher-b"): clientRef wird MITGEPRUEFT, sobald ein Nachweis-Mechanismus existiert — derzeit existiert KEINER (Mechanismen geprueft: OAuth-client_id braucht AS/Registrierung; mTLS braucht PKI; signed assertion braucht Schluessel-Verwaltung; eigenes Client-Secret = neue Client-Domaene = verboten; Key-allein beweist NICHTS ueber den Client). [DECIDED]
- KONSEQUENZ: clientRef ist bis auf Weiteres NUR Metadaten/Audit (wer-gehoert-wozu, Auswertung, Support) — KEINE Sicherheitsbindung. Wer pro Client trennen/widerrufen will, vergibt EIGENE Credentials je Client ( Der Widerruf pro App funktioniert OHNE kryptographischen Client-Beweis). [DECIDED]
- Sicherheitsrelevant wird clientRef ERST mit einem entschiedenen Nachweis (Kandidaten: mTLS/Assertion bei Drittanbieter-Bedarf — DEFERRED; KEINE neue Client-Domaene ohne Bedarfsnachweis).

## 6. Secret Storage Contract (C3 — DECIDED)

Persistieren (Metadaten, DDB — konsistent zu bestehenden Tabellen, abfragbar fuer Management/Introspektion, TTL-faehig):
credentialId (Pflicht, systemvergeben, immutable) · apiProfileId (Pflicht, immutable, §11) · name/label (Pflicht, human-readable) · credentialType (Pflicht, z.B. `opaque-bearer-v1` — Typkennzeichnung fuer spaetere Typen) · status (Pflicht, §12) · createdAt/updatedAt (Pflicht, System) · expiresAt (Pflicht — Ablauf ist Pflicht, §8) · lastUsedAt (System, Introspektion/Betrieb) · revokedAt + revokedBy + revokeReason (bei Revocation Pflicht) · clientRef-Spiegel (aus Profil,Stmtand bei Pruefung) · scopes/entitlementsRef (nur EINSCHRAENKUNG, §9; Default = keine Einschraenkung) · createdBy (Akteur + Typ, immutable) · rotationOf/rotatedBy (Verkettung A->B, §7).

NIEMALS persistieren (absolut): Klartext-Key/-Secret · Passwoerter (Cognito- wie eigene) · fremde IdP-Tokens · vollstaendige Access Tokens · Secrets in Logs/Reports · Secrets in Terraform State · Authorization-Header-Inhalte · sensible Payloads.

Lookup-Prinzip (Modell, als Loesung BESTAETIGT): presented credential -> deterministischer Lookup-Digest (SHA-256, domain-separiert; RECOMMENDED; Pepper/HSM = Implementierungsdetail) -> Metadaten -> APIProfile -> Profil-Status -> Entitlements -> Authorization. Reversible Verschluesselung als PRIMAER-Ablage ist VERBOTEN (Hash, nicht Encrypt — Encrypt waere wieder auslesbar). Secrets-Manager-Ablage = DEFERRED-Option (nur bei Compliance-Bedarf; kein Architektur-Zwang heute).

## 7. Revocation Contract (C4 — DECIDED, Revocation vor Rotation)

Bestaetigt (fachlich, Prioritaet absteigend):
1. Profil REVOKED -> ALLE zugehoerigen Credentials SOFORT unwirksam (terminal, §9 PROMPT 02).
2. Profil DISABLED -> ALLE zugehoerigen Credentials SOFORT unwirksam (reversibel via Entsperrung).
3. Profil EXPIRED -> ALLE zugehoerigen Credentials SOFORT unwirksam (abgeleitet).
4. Credential REVOKED -> NUR dieses Credential unwirksam (Profil + Geschwister unberuehrt).
- Wirksamkeit: naechste Pruefung (pro-Request serverseitig); langlebige Positiv-Caches VERBOTEN (negativ-cachen ebenfalls nicht noetig — Pruefung ist billig: Digest-Lookup + Status). Widerrufene Saetze BLEIBEN als Datensaetze erhalten (Status REVOKED + revokedAt/By/Reason) — Loeschen wuerde Audit zerstoeren.
- Actor-Regeln: Profil-Ebene s. PROMPT 02 (REVOKED nur Admin); Credential-Revoke: Admin + Staff-im-Supportfall (PROMPT-02-Staff-Umfang, auditiert).

## 8. Rotation Contract (§7 Auftrag — DECIDED ohne Profil-Neuanlage)

- Rotation A->B: B = NEUES Credential-Objekt (NEUE credentialId; rotationOf=A, rotatedBy=Akteur); A per DEFAULT SOFORT REVOKED (sicherer Default).
- Uebergangsfenster: NUR als expliziter Admin-Akt MIT Ablaufdatum (auditiert, befristet, RECOMMENDED kurz); ohne diesen Akt gibt es KEINE Ueberlappung.
- Wer: Administrator; Staff NUR im Support-Fall (Analogie Reissue, PROMPT 02 §4). Rotation IMMER auditiert (alte + neue ID verkettet).
- Unveraendert: APIProfile (gleich), Entitlements (gleich), clientRef (gleich), Owner (gleich). Aendert sich: credentialId (neu), Secret-Wert (neu, einmalige Ausgabe), createdAt/expiresAt (neu).
- KEINE automatische Rotation (kein Scheduler, kein Ablauf-Automatismus ausser EXPIRED-Ableitung).

## 9. Expiration Contract (§8 Auftrag — DECIDED)

- Zwei Ebenen, eine Regel: wirksam = min(Credential-Status/-Ablauf, Profil-Status/-Ablauf). Credential darf NIEMALS laenger WIRKSAM sein als sein Profil — auch bei kuenstlich fernerem eigenem expiresAt. Profil-EXPIRED dominiert IMMER (unabhaengig vom Credential-Datum).
- Credential DARF frueher ablaufen (kuerzere Laufzeit = engerer Schadenradius, RECOMMENDED fuer sensible Kontexte).
- Ablauf ist PFLICHT (jedes Credential hat expiresAt; NULL-Verlaengerung verboten). RECOMMENDED-Maximum: 366 Tage (deckt Jahres-Rotation inkl. Schaltjahr; Vorbild OpenAI-Maximum 31536000s = 365d als VENDOR PATTERN). Exakter Default (z.B. 90/180/365) = Policy-Parameter der Implementierung, NICHT dieses Contracts.
- Credential-Expiry umgeht NIEMALS Profil-Semantik (§10 Schritt 5+7 pruefen Profil UNABHAENGIG vom Credential-Datum).

## 10. Scopes / Entitlements (C5 — DECIDED: keine zweite Welt)

- Basismodell A (DECIDED): Credential -> APIProfile -> Entitlements (+ User-Entitlements via Union, PROMPT 02 §11). Credential besitzt KEINE eigenen Berechtigungen.
- Option C als ZUSATZ (DECIDED, nur einschraenkend): optionale Credential-Scopes muessen TEILMENGE der Profil-/User-Rechte sein. Formel (GEPRUEFT UEBERNOMMEN):
  effective = credentialScope ∩ (profilEntitlements ∪ userEntitlements),
  wobei fehlende credentialScope-Angabe = KEINE Einschraenkung (volle Profil-Rechte), NIEMALS Erweiterung.
- VERBOTEN: Credential erweitert Rechte, die Profil/User nicht besitzen (No-Expansion-Regel — serverseitig durchzusetzen, nicht nur zu dokumentieren).
- Modell B (eigene Scope-Welt) ABGELEHNT ohne Begruendung — keine Begruendung vorhanden (keine zwei Berechtigungswelten erfinden).

## 11. Credential Validation Order (C6 — DECIDED, 12 Schritte)

1. Credential vorhanden? (sonst 401 — analog Handler-Unauth).
2. Credential bekannt? (Digest-Lookup, konstanter Zeitvergleich; unbekannt -> 401, KEIN Grund-Signal nach aussen).
3. Credential aktiv? (Status ACTIVE; DISABLED/REVOKED -> 403).
4. APIProfile vorhanden? (Referenz intakt; sonst 403 + Alarm-Signal: Dateninkonsistenz).
5. APIProfile ACTIVE? (PENDING/DISABLED/EXPIRED/REVOKED -> 403; PENDING/DISABLED/EXPIRED/REVOKED erlauben NIEMALS Nutzung).
6. Credential nicht abgelaufen? (expiresAt; abgelaufen -> 403).
7. APIProfile nicht abgelaufen? (Profil-expiresAt/EXPIRED dominiert; -> 403).
8. Clientbindung erfuellt? (Derzeit: Metadaten-Konsistenz clientRef-Spiegel vs. Profil; echte Bindungspruefung erst mit C2-Nachweis — bis dahin KEIN harter Block aus clientRef allein.)
9. User-/Tenant-Isolation erfuellt? (Owner-/Tenant-Kontext des Profils vs. Ziel-Ressource).
10. Entitlement erfuellt? (Union user ∪ profil, No-Expansion; sonst 403).
11. Agent Catalog erlaubt Agent? (Status ACTIVE + Capability — EXISTING-Pruefung).
12. Execution darf stattfinden (alle Pruefungen bestanden -> WorkItem-Pfad wie heute).
- Schrittreihenfolge-Begruendung: billige deterministische Auth-Pruefungen (1-3) -> Kontext/Bindung (4-9) -> Berechtigung (10-11) -> Vollzug (12); Fehlerantworten unterscheiden NUR 401 (unbekannt/ungueltig) vs. 403 (bekannt, aber unberechtigt/deaktiviert) — analog bestehender Handler-Semantik, kein Schritt-Leak.

## 12. Credential → APIProfile Binding (C7 — DECIDED)

- EIN Credential gehoert GENAU EINEM APIProfile (1:1 auf Credential-Seite; n:1 auf Profil-Seite: ein Profil DARF mehrere Credentials haben — bestaetigt PROMPT-02-Zielbild).
- Transfer VERBOTEN (kein Umhaengen auf anderes Profil; anderer Kontext = neues Credential oder neues Profil).
- ownerUserId unveraenderlich (PROMPT 02 §8 — Transfer-Verbot schliesst Owner-Wechsel implizit ein).
- Profil-Revoke: alle Credentials unbrauchbar, Saetze als REVOKED erhalten (Audit, §6). Credential-Revoke: nur dieses (Profil + Geschwister unberuehrt).

## 13. Credential Lifecycle (DECIDED — KEIN PENDING)

| Zustand | Bedeutung | Eintritt | Uebergaenge | Actor | Art |
|---|---|---|---|---|---|
| ACTIVE | Pruefbar/nutzbar (Profil-Status vorbehalten) | Ausstellung (= Aktivierung) | -> DISABLED; -> REVOKED; -> EXPIRED (automatisch) | Admin (Ausstellung); Admin/Staff-support (Sperre) | Fachlich |
| DISABLED | Temporar gesperrt (Grund-Pflicht) | Sperr-Akt | -> ACTIVE (Admin; Staff NUR selbst-gesperrte); -> REVOKED (Admin; Staff-support) | Admin + Staff-support | Fachlich, reversibel |
| EXPIRED | Frist ueberschritten (aus expiresAt ABGELEITET) | System | -> ACTIVE NUR via Rotation/Neuausstellung (kein "Entsperren" abgelaufener Secrets); -> REVOKED (Cleanup) | System (Eintritt) | Abgeleitet |
| REVOKED | Endgueltig entzogen | Admin-/Support-Akt | KEINE (terminal; Neuausstellung noetig) | Admin (+ Staff-support) | TERMINAL |

- KEIN PENDING (gegen Option entschieden): Begruendung — Freigabe lebt auf PROFIL-Ebene (PENDING dort); Ausstellungsakt IST der Freigabe-Vollzug; ein "angelegtes-aber-inaktives Secret" haette keinen Beobachter-Nutzen und wuerde Secret-Lebenszeit unnoetig verlaengern.
- disabled ≠ expired ≠ revoked (Analogie Profil-Lifecycle PROMPT 02 §9); kein Widerspruch zum Profil-Lifecycle (Profil-Status dominiert immer, §7/§10).

## 14. Management Plane (bestaetigt + praezisiert — DECIDED)

- Administrator: ausstellen (Wert GENAU EINMAL bei Erstellung anzeigen, danach nie wieder) · anzeigen = NUR sichere Metadaten (§6) · revozieren · rotieren · deaktivieren/reaktivieren (§13-Tabelle) · Audit lesen.
- Staff: NUR PROMPT-02-Supportfaelle (Support-Revoke/Reissue/Sperre, auditiert) — KEIN freies Credential-Management, KEINE Ausstellung ausserhalb Support-Fall mit Grund.
- User: EIGENE Credential-Metadaten sehen (soweit spaeterer Endpoint erlaubt — Entscheid VOR Implementierung, nicht hier); NIEMALS fremde; NIEMALS Secret-Werte nachtraeglich (technisch UNMOEGLICH machen, nicht nur verbieten — C3-Hash statt Encrypt).
- Management ≠ Usage (§12 PROMPT 02 gilt unveraendert; Management-Akte brauchen Admin/Staff-Kompetenz UND Audit-Pflicht).

## 15. Audit Contract (DECIDED-Mindestumfang)

Ereignisse: created · issued (Erstausgabe) · viewed/displayed (Metadaten-Abruf) · revoked · rotated (A->B-verlinkt) · expired (System-Eintritt) · disabled/enabled · failed authentication (r limitiert: kein Secret, kein Digest-Raten-Schluss) · client binding failure · profile binding failure · unauthorized management attempt.
NIE loggen: Secret/Key-Wert · Passwort · fremde/fuehrende Tokens · vollstaendige Access Tokens · Authorization-Header · sensible Payloads (EXISTING-Praxis Gates 10/11/14: Shred + Maskierung).
Pflichtfelder: actor (+ Typ) · timestamp · credentialId · apiProfileId · clientRef (falls vorhanden) · action · outcome · reason (bei Sperre/Entzug) · tenant context · correlation/request id.

## 16. Security Contract (verbindlich — DECIDED)

1. Credentials sind KEINE Identitaet (kein sub-Ersatz, kein Profil-Ersatz).
2. Credentials ersetzen Cognito NICHT (andere Boundary, §4).
3. Credentials gehoeren genau einem APIProfile (§12).
4. Credential-Werte werden nach Ausstellung NICHT wieder ausgelesen (technisch unmoeglich, §6/§14).
5. Profilstatus ist VOR jeder Credential-Nutzung zu pruefen (§11 Schritte 4-5/7).
6. Revocation MUSS wirksam sein (sofort, kaskadierend, ohne Positiv-Cache — §7).
7. Entitlements werden SERVERSSEITIG geprueft (No-Expansion, §10; Frontend nie massgeblich).
8. Frontend entscheidet NIEMALS ueber Berechtigung (bestaetigt).
9. Credentials duerfen KEINE Rechte erweitern (§10).
10. KEIN Secret in Logs/Reports/Terraform-State (§6-Negativliste).

## 17. Decision Matrix

| Thema | Entscheidung | Begruendung | Klasse |
|---|---|---|---|
| C1 Kombination JWT (Mensch) + opakes Bearer-Credential (Maschine/Profil) | Zwei Boundaries, strikt getrennt | Architektur-Fit (DDB+Handler+Revocation) + OpenRouter-Praxis; kein AS vorhanden | DECIDED (+ VENDOR-PATTERN-Einfluss) |
| Kein JWT-Access-Token als API-Credential | Abgelehnt | Kein AS; Selbstvalidierung schwaecher als Server-Lookup | DECIDED |
| OAuth Client-Credentials-Fluss | Vertagt | Kein Delegations-Bedarf belegt | DEFERRED |
| GW-JWT-Kante unberuehrt; eigener Pruefpfad spaeter | Key nutzt NICHT den JWT-Authorizer | Technische Verifikation (api/main.tf:21-33) | DECIDED (EXISTING-Fakt + Folgerung) |
| C2 clientRef vorerst Metadaten/Audit | Kein beweisbarer Mechanismus ohne neue Domaene/PKI | Ehrlichkeit statt Schein-Bindung | DECIDED |
| Trennung pro Client via eigene Credentials | Widerruf ohne Kryptographie-Beweis | Praktikabel sofort, sobald Credentials existieren | RECOMMENDED |
| mTLS/Assertion-Bindung | Vertagt | PKI-Overkill ohne Dritt-Bedarf | DEFERRED |
| C3 DDB-Metadaten + SHA-256-Lookup-Digest | Architektur-Konsistenz + Abfragbarkeit; Hash statt Encrypt | Kein neuer Service; Auslese-Unmoeglichkeit | DECIDED |
| Secrets Manager | Option bei Compliance-Bedarf | Kein Zwang heute | DEFERRED |
| C4 Kaskade Profil->Credentials + Einzel-Revoke | Sofort-Wirksamkeit, kein Positiv-Cache | Sicherheitskern | DECIDED |
| Rotation B-neu/A-sofort-tot; Fenster nur explizit+befristet | Sicherer Default; Migration als Ausnahme mit Ablauf | Audit + kleinster Schaden | DECIDED |
| Ablauf Pflicht, max. 366 Tage, Profil dominiert | Schaden begrenzen; Profil-Semantik nie umgehbar | Vendor-Praxis + Logik | DECIDED (Max = RECOMMENDED-Rahmen) |
| C5 Keine zweite Welt; Scope nur Teilmenge (Schnittformel) | Keine Berechtigungswelt erfinden; No-Expansion | Formel geprueft uebernommen | DECIDED |
| C6 12-Schritt-Pruefung + 401/403-Trennung | Billig-vor-teuer; kein Schritt-Leak; Handler-Konvention | Nachvollziehbar + konsistent | DECIDED |
| C7 1:1-Bindung, Transfer-Verbot | Kontextschaerfe + Audit | Analogie Owner-Immutabilitaet | DECIDED |
| Lifecycle ohne PENDING | Freigabe lebt auf Profil-Ebene | Kein Secret ohne Beobachter altern lassen | DECIDED |
| Management-Regeln (§14) + Audit (§15) + Security (§16) | Wie dort (Rollen aus PROMPT 02) | Fortfuehrung entschiedener Kompetenzen | DECIDED |
| Offer-Modell / Capability-Endpoint / Worker-Auth-Implementierung | Nicht in diesem Gate | Scope-Verbote | OPEN (fuer Folge-Gates) |

## 18. Open / Deferred Decisions (fuer Folge-Gates — nichts vorweggenommen)

- OPEN: exakter Credential-Default-Ablauf (Policy-Zahl innert 366-Tage-Rahmen); User-sichtbare Metadaten-Endpoints (Ob/Umfang); Scope-Vokabular (falls Scopes je eingefuehrt); clientRef-Nachweis-Mechanismus (bei Bedarf); Pepper-/HSM-Details (Implementierung).
- DEFERRED: OAuth-Client-Credentials-Fluss; mTLS/Assertion-Bindung; Secrets-Manager-Ablage; `Admin`-Gruppen-Bereinigung (PROMPT 02); Offer-Modell; Capability-Endpoint; Worker-Auth-Implementierung; APIProfile-CRUD-Implementierung; Cognito-Group-Cleanup; jegliches TF/AWS-Deployment.

## 19. Implementation Boundary (spaeter — NICHT dieses Gate)

A) Spaeter zu implementieren (ausserhalb): Credential-Tabellen/TF, Pruefpfad (REQUEST-Authorizer vs. Lambda-intern — Design-Entscheid offen), Management-Endpoints, Introspektions-Endpoint (GET-/key-Analogie), Rotation-/Revocation-Ops, Audit-Pipeline-Anschluss, Worker-Nachpruefung.
B) NICHT Bestandteil des Credential-Gates: Offer-Modell, Capability-Endpoint, Monetarisierung, Worker-Auth-Implementierung, APIProfile-CRUD, Cognito-Group-Cleanup, TF/AWS-Deployment.
C) VOR Implementierung noch zu entscheiden: Pruefpfad-Design (§3 GW-Konsequenz), exakte Ablauf-Defaults, User-Metadaten-Umfang, Scope-Vokabular, Pepper-/HSM-Frage.

## 20. PROMPT-04 Recommendations (Reihenfolge-Vorschlag — KEIN Code)

1. P4-R1: Offer-Minimalmodell (Name/Beschreibung/EntitlementsRef, KEINE Preise) als Vergabe-Voraussetzung — blockt Provisioning-Entscheidungen.
2. P4-R2: Pruefpfad-Design (REQUEST-Authorizer vs. Lambda-intern) VOR jeder Credential-Tabellen-Arbeit — sonst Design-Bruch an der GW-Kante.
3. P4-R3: APIProfile-CRUD-Contract (Anlage-/Mutations-Endpoints, Validierung, unique-je-Owner) als naechsten sichtbaren Baustein.
4. P4-R4: Capability-/Introspektions-Endpoint (lesend, OpenRouter-GET-/key-Analogie) VOR schreibenden Management-Endpoints (sofortiger Frontend-Nutzen, kein Schreib-Risiko).
5. P4-R5: Worker-Pfad-Entscheidung (Nachpruefung vs. signierte Herkunft) VOR Produktiv-Credentials (sonst Umgehungs-Pfad).
6. P4-R6: Cognito-Group-Cleanup (`Admin`-Entfernung nach Migration) ins Implementierungs-Fenster einplanen.

**HARD STOP (keine Implementierung, keine Mutation, keine Credential-Erzeugung).**
