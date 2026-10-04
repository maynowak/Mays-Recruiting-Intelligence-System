# RIS-PRODUCT-PLATFORM-OPEN-DECISIONS-05 — Offene Contract-Entscheidungen schließen (P5)

STATUS: Contract entschieden (KEINE Implementierung, KEIN AWS, KEIN TF, KEINE Cognito-/DB-/Gateway-Mutationen, KEINE Credentials erzeugt, KEINE APIProfile angelegt, KEINE neue Architektur)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, 8caa4d9
- Basis (verbindlich, NICHT veraendert): PROMPT 01 (Standards/Rollen) + PROMPT 02 (APIProfile) + PROMPT 03 (Credential) + PROMPT 04 (Offer/Pruefpfad/CRUD/Capability/Worker/Cleanup, Commit 8caa4d9) + Bestand (Code, TF-GW/Cognito/SQS/Lambda, Gates 10/11/12/13A/14, kanonische Docs). Alle 18 Basis- + P04-Entscheidungen gelten (Konfliktpruefung §7: KEIN Widerspruch).
- Methode: Repository-/Code-Befunde je Paket (R1-R6) + Entscheidung mit Begruendung; Klassen DECIDED/OPEN/DEFERRED/NOT IN SCOPE (+ GREEN/OPEN-Status). Nicht-Entscheidbares bleibt OPEN — keine Annahme als DECIDED.
- Classification: GREEN (Contract) mit OPEN-Resten (markiert).
- Mutationen: KEINE (verifiziert: kein AWS/TF/Cognito/DB/Gateway-Kontakt, keine Secrets, keine Keys).
- Git: nur diese beiden Reports (s. Commit).
- Next: Implementierungsreihenfolge §8 -> HARD STOP.

## P5-R1 — Cognito Group Needs Clarification (DECIDED je Gruppe, GREEN als Klaerung)

Befund (verifiziert, TF + Code + Docs): 7 Gruppen in terraform/modules/cognito/main.tf:94-129. Code-Nutzung: NULL (einzige Beruehrung = /me-Echo des `cognito:groups`-Claims, lambda/handler.py:222-225/327 — KEINE Zugriffsentscheidung). "candidates"-Treffer in Ecosystem-Dateien = Discovery-Variablen (Agenten-Kandidaten), NICHT die Gruppe (Wortgleichheit, kein Bezug). Doku-Treffer zu candidates/recruiters/user-user/user-requier als GRUPPEN: NULL (nur Gate-11-"7 Gruppen"-Erwaehnung als Anzahl). mayaws = Installer-`--profile`/AWS-CLI-Kontext, KEINE Gruppe, KEINE Rolle (bestaetigt P01/P02).

| Gruppe | Nutzung | Dokumentierte Bedeutung | Entscheid |
|---|---|---|---|
| `admins` | TF-Objekt, kein Code-Check | Administrator (PROMPT 02 DECIDED) | A) PRODUKTIV ERFORDERLICH (kanonisch; Semantik-Belegung = Implementierung) |
| `Staff` | TF-Objekt, kein Code-Check | Support-Rolle (PROMPT 02 DECIDED) | A) PRODUKTIV ERFORDERLICH (wie oben) |
| `Admin` | TF-Objekt, kein Code-Check | Deprecated-Alias (PROMPT 02/04 DECIDED) | B) HISTORISCH/DEPRECATED (Freeze -> Migration -> Entfernung per R6-Plan; KEINE Mutation hier) |
| `candidates` | KEINE (weder Code noch Doku als Gruppe) | KEINE belastbar (Name allein = KEIN Beleg) | C) UNKLAR -> Produktentscheidung erforderlich (Vermutung Domaene, NICHT als Fakt) |
| `recruiters` | KEINE | KEINE belastbar | C) UNKLAR -> Produktentscheidung erforderlich |
| `user-user` | KEINE | KEINE belastbar | C) UNKLAR -> Produktentscheidung erforderlich |
| `user-requier` | KEINE | KEINE belastbar (Schreibweise zusaetzlich auffallend — als VERMUTUNG markiert) | C) UNKLAR -> Produktentscheidung erforderlich |

Entscheidungsbedarf (belastbar, fuer Produkt-Owner): Pro C-Gruppe genau EINE der Antworten — (i) fachliche Rolle mit Semantik + Checks definieren, (ii) als historisch zur Entfernung freigeben (dann R6-Regeln: Mitglieder-Export, Claim-Check, Migration, eigenes Gate), (iii) bewusst behalten-ungenutzt mit Begruendung. DEFAULT bis zur Entscheidung: (iii) mit Freeze (keine neuen Mitglieder, keine neue Semantik-Behauptung). KEINE Bedeutung aus Namen abgeleitet (Verbot eingehalten). KEINE Migration/Freeze-Technik/Cognito-Mutation in diesem Gate.

## P5-R2 — Offer Contract Finalization (DECIDED: GREEN / implementierungsreif)

P04-Contract geprueft (offerId / name-UNIQUE / description / ACTIVE-INACTIVE / agentIds / Zeiten / Plattform-Owner / Admin-only / Vergabe-erzeugt-Entitlements / INACTIVE-nur-kuenftig / Bestand-bleibt / keine Preise) — VOLLSTAENDIG fuer ein Implementierungs-Gate. Verbleibende Detailfragen ENTSCHIEDEN (keine echte Luecke uebrig):
- Agent-Referenzen GEGEN KATALOG: Vergabe PRUEFT jedes agentId auf Katalog-Existenz (sonst Vergabe abgelehnt — keine baumelnden Referenzen; Katalog bleibt einzige Agent-Wahrheit, P04-R6/P01-§6).
- Deaktivierter Agent: DEAKTIVIERT (INACTIVE/RETIRED/...) DARF NICHT ausgefuehrt werden — Contract-Regel (unabhaengig von heutiger Durchsetzungstiefe). BEFUND dazu (kein Code-Eingriff): Handler-Gates vergleichen heute Kleinbuchstaben-`'active'` (handler.py:606/779) gegen Katalog-Werte in GROSSBUCHSTABEN (Adapter-Map ACTIVE/INACTIVE/...; Unbekannt -> ACTIVE-Default), und Pipeline-Eligibility blockiert hart NUR RETIRED/DEPRECATED (eligibility.py:74-83; INACTIVE erzeugt nur Grund ohne Block). KONSEQUENZ (Implementierungs-Auftrag, nicht hier): Status-Normalisierung (kanonisch GROSS, case-insensitiver Vergleich) + harter INACTIVE-Ausschluss auch im Pipeline-Pfad — dokumentiert, NICHT implementiert.
- Offer-Aenderung: wirkt NUR auf KUENFTIGE Vergaben (keine Rueckwirkung — bestaetigt P04; begruendet: erteilte Rechte sind eigenstaendige Entitlement-Objekte mit eigenem Lifecycle).
- Vergabe-Ziel: User (user-weit) ODER APIProfile (profil-gebunden) — BEIDE erlaubt (Union-Semantik PROMPT 02 §11); Vergabe-Akt enthaelt: offerId + Ziel (userId [+ apiProfileId]) + Zeitfenster (Pflicht ab Vergabe — Default-Fenster = Policy-Parameter der Implementierung innert PROMPT-03-366-Tage-Rahmen) + Actor + Grund.
- Audit (DECIDED-Mindestumfang): offer-created/updated/deactivated + grant (offerId, Ziel-User/Profil, Fenster, Actor, Grund) + grant-denied (unbekanntes agentId/inaktives Offer) + entitlement-withdrawn — secrets-frei (keine Secrets im Offer-Kontext vorhanden).
- Offer-Identitaet: offerId EINDEUTIG (PK), name UNIQUE (Fehlvergabe-Schutz) — beide DECIDED (P04 bestaetigt, hier final).
- KEINE Preis-/Tarif-/Billing-/Subscription-Felder (Verbot bestaetigt; Monetarisierung = NOT IN SCOPE).
ERGEBNIS: GREEN / DECIDED — keine OPEN-Luecke; naechster Schritt waere Implementierungs-Gate (nicht hier).

## P5-R3 — Credential Verification Module Contract (DECIDED, GREEN)

Modulvertrag (PROMPT-03-C6 als Basis, unveraendert - 12 Schritte gelten):
- INPUT: Bearer-Credential (Rohwert, NUR im Speicher des Aufrufs) + angeforderte Capability/Operation + Request-Kontext (Route, Zeit, Request-/Correlation-ID) + Kontext-Hinweis (Profil-Selektion NACH P5-R4 ODER Credential-Selbstauflösung; KEIN User-/Tenant-/Profil-Vertrauen aus Client-Feldern).
- OUTPUT (genau drei Klassen): AUTHORIZED + Autorisierungs-Kontext (userId/tenantId/apiProfileId/credentialId/entitlementRefs/Scope-Schnitt — KEIN Secret, KEIN Digest, KEIN Rohwert) · UNAUTHORIZED/401 (unbekannt/ungueltig/formatfremd) · FORBIDDEN/403 (bekannt, aber Status/Ablauf/Bindung/Entitlement/Katalog negativ).
- Lage (DECIDED): NACH Gateway (P04-R2-Pfad B), VOR JEDER Business-Logik (inkl. Read-Pfade — auch Lese-Routen mit Credential-Kontext passieren das Modul; keine Abkuerzung fuer "nur lesend").
- Pfad-Trennung (DECIDED): Human-JWT-Pfad und Credential-Pfad dispatchen per ROUTE (P04-R2), NIEMALS per Header-Schnueffeln auf derselben Route (kein Orakel-/Downgrade-Risiko); JWT-Pfad bleibt exakt wie heute (Authorizer + Handler-Claims).
- Weitergabe ERLAUBT (an Business-Logic): Autorisierungs-Kontext (§-Liste oben) + Entscheidungs-Referenz (Audit-ID) + Auflösungs-Protokoll (Selection/Resolution/Authorization nach R4).
- Weitergabe VERBOTEN: Roh-Credential, Digest-Werte, Secrets, fremde Kontexte (andere Tenants/Profile), Ablehnungs-Begruendungen mit Orakel-Wirkung (nur 401/403-Codes + neutrale Audit-Events).
- Audit-Daten: Auth-Event je Pruefung (Erfolg/Misserfolg RL-begrenzt protokolliert — kein Secret, kein Digest, kein Header-Inhalt) + Felder per PROMPT-03-§15 (actor=System-bei-M2M? — Actor = credentialId/apiProfileId + aufrufender Client-Hinweis + tenant context + correlation/request id).
- Correlation ID (DECIDED): KEIN neues ID-Schema — GW-Request-ID + Lambda-Request-ID + (bei Ausfuehrung) workId/execution_id-Kette werden durchgereicht (EXISTING-IDs wiederverwenden).
- Revocation: pro-Request frisch (kein Positiv-Cache; PROMPT-03-C4 gilt im Modul wortwoertlich).
- Noch KEIN Code, KEINE Route, KEIN Credential (Scope-Verbot eingehalten).

## P5-R4 — APIProfile Selection Contract (DECIDED: Variante D, GREEN; zentraler Punkt geschlossen)

ENTSCHEIDUNG: D) Kombination aus Default + expliziter Auswahl — mit strikter Drei-Teilung (sonst waere D beliebig):
- SELECTION (Client-Hinweis, UNVERTRAUT): explizite Profil-ID als Request-Parameter (RECOMMENDED-Traeger: Header — GET-faehig, log-sparsam; exakter Name = Implementierungsdetail) ODER Leere (= Default-Wunsch). Mehrere Profile + keine Angabe = KEIN Raten (kein "erstes", kein "letztes", kein Alphabet) — sonst Profil-Verwechslung.
- RESOLUTION (server-seitig, VERTRAUENSWUERDIG): Hinweis -> verifiziertes Profil-Objekt NUR bei: Existenz + Owner-Bindung (oder Admin/Staff-Kompetenz) + Status-Pruefung (PENDING/DISABLED/EXPIRED/REVOKED = KEIN Kontext; PENDING/DISABLED/EXPIRED/REVOKED erlauben NIEMALS Nutzung) + Tenant-Match. Misserfolg -> 404/403 OHNE Orakel (kein Unterschied ob "existiert-nicht" vs. "fremd" vs. "deaktiviert").
- AUTHORIZATION (server-seitig, MASSGEBLICH): Entitlements/Scope-Schnitt/Katalog NACH Resolution (PROMPT-03-C5/C6 + P04-R5). Auswahl ALLEIN autorisiert NICHTS (Profil-Auswahl ≠ Berechtigung — Contract-Satz).
- DEFAULT-Regel (DECIDED): genau EIN ACTIVE-Profil des Users -> automatisch (UX + Audit-Vermerk "default-resolved"); NULL Profile -> KEIN Kontext + Hinweis auf Anlage/Beantragung (KEIN Auto-Provision — Basisentscheid 11 aus P01-P04 gilt); MEHRERE -> explizite Angabe PFLICHT (sonst 400/403-neutral mit Auswahl-Hinweis via Introspection-HUMAN-Sicht).
- Credential-Kontext braucht KEINE Selection (Key -> Profil 1:1 automatisch; explizite Profil-ID dazu MUSS matchen oder wird abgelehnt — kein Override).
- Multi-Client-Sicherung: Matcher A kann NUR Profile mit clientRef=A (oder NULL, solange NULL-Kontexte noch zugelassen sind — NULL-Zulassung = spaetere Policy, DEFAULT restriktiv: NULL-Profile nur ohne clientRef-Bindungszwang) — Verwechslung A/B damit strukturell ausgeschlossen; Audit protokolliert Selection+Resolution+Authorization als Triple.
- Warum D (statt A/B/C): A allein laesst Multi-Profil-Nutzer stranden + verschleiert Kontext; B allein belastet Single-Profil-UX + jeden M2M-Aufruf; C allein ist nur Transport ohne Semantik. D verbindet explizit (auditierbar/automatisierbar) mit Default (nur wo eindeutig) — direkt aus Mehrere-Profile-pro-User + Multi-Client-Ziel abgeleitet (Repository-/Contract-Realitaet, keine Erfindung).

## P5-R5 — Introspection Contract Finalization (DECIDED: EINHEITLICH, GREEN)

ENTSCHEIDUNG: EIN einheitlicher Introspection-Contract (eine Huellform, drei Aufloesungswege) — statt dreier Modelle (ein mentales Modell, eine Implementierung, keine Triple-Pflege; Unterschiede NUR in Subjekt-Aufloesung + Feld-Sichtbarkeit):
- HUMAN: aktueller User (sub/tenant) + ERLAUBTE Profil-Kontexte (IDs+Namen+Status — Auswahl-UX nach R4) + user-weite effektive Positiv-Capabilities.
- PROFILE (nach R4-Resolution): DIESES Profil (ID/Name/Status/clientRef-Label) + dessen effektive Positiv-Capabilities + Offer-Anzeige (Name/Beschreibung VERGEBBARER Offers, KEINE Preise) + Ablauf-Hinweise (Profil + beteiligte Entitlements).
- CREDENTIAL (Key -> Profil automatisch): wie PROFILE + Credential-Label/ID + Scope-Einschraenkungs-Hinweis (soweit sicher darstellbar) + Credential-Ablauf.
- ZURUECKGEGEBEN (DECIDED): nur Positive (erlaubt + demnaechst-ablaufend mit Datum) + Gueltigkeits-Hinweise + Auflösungs-Nachweis (welcher Kontext, wann geprueft — KEINE Gültigkeits-Dauer-Behauptung ueber Request hinaus).
- NIEMALS (DECIDED): Secrets/Digests/Rohwerte · Ablehnungs-Begruendungen je Agent (kein Permission-Orakel) · fremde Tenants/Users/Profile · interne IAM-/DDB-Details · JWTs/Token-Inhalte · exakte Schwellen/Regeln der Pruefung (kein Reverse-Engineering-Futter).
- Isolation: tenant/user/profile-gefiltert serverseitig; credential-gebunden NUR eigenes Profil; KEINE finalen URLs in diesem Gate (Implementierung waehlt Namensraum nach P04-R2-Prinzip — keine voreilige API-Festlegung).

## P5-R6 — Profile / Offer / Credential Boundary (DECIDED-Matrix, GREEN)

| Objekt | Zweck | Besitzer | Berechtigung | Secret? | Lebenszyklus |
|---|---|---|---|---|---|
| UserProfile | Persoenliche Anwendungsdaten (v1) | User (sub-gebunden; Plattform persistiert) | JWT-eigen (lesen/schreiben-eigen); Admin/Staff-Supportfaelle | NEIN | Implizit (kein Status; existiert-oder-404) |
| Offer | Vergabefaehiger Katalogeintrag (agentIds-Buendel) | RIS-Plattform (KEIN per-Offer-Owner) | Admin (verwalten/vergeben); Staff KEINE | NEIN | ACTIVE/INACTIVE (nur Neu-Vergabe-Steuerung) |
| Entitlement | Techn. Zugriffsrecht (user-x-agent-x-Zeit ODER profil-x-agent-x-Zeit) | RIS-Plattform (Vergabe-Akt gehoert Admin) | Admin (Vergabe/Entzug); Pruefung serverseitig (Handler + spaeter Worker) | NEIN | Zeitfenster (validFrom/validUntil) + Entzug |
| APIProfile | API-Nutzungskontext (Owner + clientRef + Entitlements + spaeter Credentials) | ownerUserId (alleinig) | Owner-eigen (eng) / Admin (voll) / Staff (Support) | NEIN (Referenzen nur) | PENDING/ACTIVE/DISABLED/EXPIRED/REVOKED (terminal) |
| Credential | Nachweis fure EINEN Profil-Kontext (opak, Bearer) | Profil-Kontext (Ausstellung: Admin; Nutzung: Profil) | Pruefung serverseitig pro Request; Management Admin/Staff-support | JA (genau EINMAL bei Ausstellung; danach NUR Digest) | ACTIVE/DISABLED/EXPIRED/REVOKED (terminal; KEIN PENDING) |
| Agent Catalog Entry | Zentrale Agent-Beschreibung (Faehigkeiten/Status/Runtime) | RIS-Plattform (zentral; Matcher besitzen KEINE) | Lesend gefiltert (/agents, Introspection); schreibend Plattform-seitig | NEIN | ACTIVE/INACTIVE/DEPRECATED/RETIRED/... (Ausfuehrungs-Sperre per Contract R2-Regel) |

Grenzsaetze (alle DECIDED, Rest-OPEN: KEINE — Matrix geschlossen): Offer ≠ Entitlement (Katalog vs. erteiltes Recht) · Entitlement ≠ APIProfile (Recht vs. Kontext, Union-Semantik) · APIProfile ≠ Credential (Kontext vs. Nachweis) · Credential ≠ Identity (Nachweis vs. Person/sub) · UserProfile ≠ APIProfile (Personendaten vs. Nutzungskontext; ein User — ein Profil, aber n APIProfile) · Tenant ≠ Owner (Isolation vs. Akteur).

## P5-R7 — Product Platform Decision Matrix (Gesamtauswertung)

| Bereich | Entscheidung | Status | Begruendung |
|---|---|---|---|
| Cognito Groups | admins/Staff = erforderlich (Semantik-Belegung = Implementierung); Admin = deprecated (R6-Plan); 4x UNKLAR (C) mit Entscheidungsbedarf (i/ii/iii) + Freeze-Default | GREEN (Klaerung) | Vollinventar (TF-Zeilen + NULL-Nutzung ausser Echo); keine Bedeutung aus Namen; keine Mutation hier |
| Offer Contract | P04-Contract final: Katalog-Check, Deaktiv-Sperre, keine Rueckwirkung, User-/Profil-Vergabe mit Fenster, Audit-Umfang, Doppel-Identitaet — implementierungsreif | GREEN / DECIDED | Keine echte Luecke uebrig; Preise explizit ausgeschlossen |
| Credential Verification Module | 12-Schritt-C6 als Modulvertrag (Input/Output/Audit/Correlation/kein Cache); Lage nach GW vor Business; Routen-Dispatch; Weitergabe-Positiv-/Negativ-Listen | GREEN / DECIDED | PROMPT-03-C6 + P04-R2 direkt fortgefuehrt; noch kein Code (Scope) |
| APIProfile Selection | D (Default + explizit) mit Selection/Resolution/Authorization-Trennung; Default-Regel 1/0/n; Credential ohne Selection; Multi-Client-Sicherung; Audit-Triple | GREEN / DECIDED | Zentraler P04-OPEN-Punkt geschlossen; aus Multi-Profil-/Multi-Client-Realitaet abgeleitet |
| Introspection | EINHEITLICHER Read-Only-Contract (3 Aufloesungen, Positiv-only, kein Orakel, Isolations-Regeln, keine finalen URLs) | GREEN / DECIDED | Ein mentales Modell; bestehende Routen unzureichend (R4-Befund P04) |
| Object Boundaries | 6-Objekt-Matrix geschlossen (alle 6 Grenzsaetze DECIDED) | GREEN / DECIDED | Kein OPEN-Rest in den Grenzen |

Konfliktpruefung P01-P04: GEPRUEFT, KEIN Widerspruch (R1-Gruppenstatus folgt P02/R6-Plan; R2-Status-Regel verschaerft Durchsetzung, aendert KEIN entschiedenes Modell; R3-Modul folgt P03-C6 + P04-R2; R4-Default folgt P02-Union + Basis-11-kein-Self-Provisioning; R5-einheitlich folgt P03-C6-Empfehlung; R6-Matrix folgt allen Object-Contracts). — Kein Konflikt zu dokumentieren (Regel waere: OPEN + Doku; nicht eingetreten).

## Kanonische Dokumentation (P5-Folgen — KEINE Aenderung)

Geprueft (SYSTEM-ARCHITECTURE, RUNTIME-PATH, API-STANDARD, PLATFORM_FRONTEND_INTEGRATION, README, ROADMAP, PROJECT_STATUS): KEINE Aussage durch P5 veraltet/widerspruechlich (Offer/Modul/Selection/Introspection/Boundaries sind NEU bzw. verschaerfen Durchsetzung, ohne belegte Bestand-Aussage zu brechen — die Status-Quirks §R2 sind Code-Befunde, keine Doku-Widersprueche). Konvention: KEINE kosmetischen Aenderungen; kanonische Docs bleiben gueltig.

## Naechste empfohlene Implementierungsreihenfolge (fuer Folge-Gates, kein Umfang hier)

1. Gruppen-Bedarfs-Klaerung (R1-C) + Status-Normalisierung (R2-Befund: kanonisch GROSS, case-insensitiver Vergleich, INACTIVE-Ausschluss Pipeline) — kleinste Code-nahe Schritte zuerst.
2. Pruefmodul-Schnitt (R3) + Selection-Traeger (R4-Header-Name) + Introspection-Antwortform (R5) — Contract-zu-Schnittstelle, noch kein Verhalten.
3. Offer-CRUD + Vergabe (R2) + APIProfile-CRUD (P04-R3) — schreibende Management-Pfade mit Audit.
4. Credential-Einfuehrung (P03-C1) + Worker-Nachpruefung (P04-R5-A) + Agent-Sandboxing-Gap — gemeinsam (kein Umgehungs-Pfad).
5. `Admin`-Migration/Entfernung (R6-Plan P2/P3) + Capability-Ausbau — zuletzt.

**HARD STOP (keine Implementierung, keine Mutation).**
