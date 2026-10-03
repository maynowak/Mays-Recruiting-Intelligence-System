# GATE — JOBSEARCH / RIS IDENTITY & PRODUCT CONTRACT DISCOVERY

STATUS: Discovery abgeschlossen (keine Implementierung, keine Architekturänderung)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD: main, 2fb346e (s. Git)
- Scope: NUR Ist-Feststellung (12 Themen). Keine Routen, kein Google-13B, kein Frontend, keine AWS-Mutation.
- Methode: Repo-Greps + kanonische Docs gelesen (SYSTEM-ARCHITECTURE, API-STANDARD, README, TEAM_COLLABORATION, PROJECT_STATUS, ROADMAP) + Gate-10/11/12/13A-Reports als Nachweis, NICHT als Vertrag. Code stichprobenhaft (TF-Cognito, Handler-Claims) zur Einordnung B vs A.
- Classification: siehe Tabelle (GREEN = belastbar+aktuell dokumentiert; YELLOW = teilweise/implizit; OPEN = keine belastbare Vorgabe)

## Konflikttabelle (§6)

| Thema | Repository-Befund | Status | Quelle |
|---|---|---|---|
| IdP | Cognito User Pool `users` = zentrale Identity-/Token-Grenze | GREEN | SYSTEM-ARCHITECTURE §4, README, TF-Modul |
| Login | E-Mail+Passwort (USER_PASSWORD_AUTH) Hauptweg; keine Signup-/Login-Routen im Repo | GREEN | API-STANDARD, Gate-10-Report, TF-Client |
| Auth | API-GW JWT-Authorizer entscheidet (live 401-Belege in Gates) | GREEN | TF api-Modul, API-STANDARD, Gate-E2E |
| JWT | Issuer=Cognito-Endpoint, Audience=Client; Claims sub/email/preferred_username/cognito:groups/custom:tenant_id | GREEN | ARCH §4, API-STD §2, Handler-Code |
| userId | Cognito `sub`; keine separate RIS-Identity | GREEN | ARCH, Profile-v1, Code |
| tenantId | Claim `custom:tenant_id` + Code-Guards + Isolation live belegt | GREEN | ARCH §5, Tests, Gate-E2E |
| UserProfile | v1-Felder, explizit POST→201/409, GET→404, nie via Read | GREEN | ARCH, API-STD, Code+Tests |
| JobSearch ↔ RIS | mays-jobs-matcher clientseitig + RIS-JobSearch-Domain-Agent koexistieren; Abgrenzung NUR in Gate-Reports, nicht kanonisch | OPEN | Gate-10/9-Reports (kein kanonischer Doc-Absatz) |
| Produktmodell | Wort kommt im Repo NICHT vor (0 Treffer) | OPEN | Grep-Befund |
| Google | optional via Cognito-Federation, Standard AUS, kein separates Backend-Auth | GREEN (als Absicht+YELLOW live) | ARCH, README, Gate-13A, TF-Vars |
| Account Linking | kein Auto-Link (weder E-Mail noch sonst); nur später explizit | GREEN (als Negativ-Vertrag) | ARCH, Gate-13A, Guard-Tests |

## Klassifizierung A–E (Auszug)

- A (verbindlich): IdP/Login/Auth/JWT/Claims/userId/Tenant/Profile-Regeln/Google-Optional/Linking-Negativ (s. Tabelle).
- B (implementiert, nicht als Vertrag dok.): E-Mail-Template-Details, 7 Gruppen-Rollen, Password-Policy-Werte, Confirm-Verhalten ohne Inbox.
- C (historisch): CURRENT-ARCHITECTURE (Sep-28, überholt), alte Roadmap/G0.3-Einträge.
- D (widersprüchlich): TEAM_COLLABORATION ("Job search API beim EXTERNEN Team") vs. RIS-eigene jobsearch/-Domain + JobSearch-Agent + /me/jobsearches (Gate 9 live) — Eigentum der Job-Such-API ungeklärt.
- E (nicht vorhanden): Produktmodell-Dokument; Zukunftsvertrag Frontend↔RIS; produktiver Google-Login; expliziter Linking-Flow; konsolidierte Verantwortungsmatrix (verteilt vorhanden).

## Gap-Report (§7)

1. **Hat das Team Recht? TEILWEISE.** Identity-Kern (IdP/Login/JWT/Profile) IST belastbar dokumentiert — der Befund trifft dafür NICHT zu. Richtig ist: Produktmodell, JobSearch↔RIS-Abgrenzung und Zukunft (Google produktiv, Linking-Flow) haben KEINE belastbare Vorgabe.
2. **Vorhanden:** s. GREEN-Zeilen (11 von 12 Themen haben belastbaren Kern).
3. **Fehlt:** Produktmodell-Dokument; kanonische Frontend/Domain-Abgrenzung; produktiver Google-Nachweis; Linking-Flow-Spezifikation.
4. **Nur implizit:** Gruppen-Rollen, Password-Policy-Werte, Template-Details, Confirm-ohne-Inbox (aus Code/TF ableitbar, nicht als Vertrag formuliert).
5. **Widersprüche:** Job-Such-API-Eigentum (TEAM_COLLABORATION vs. Gate-9-Realität); veraltete Status-Docs (gekennzeichnet, nicht maßgeblich).
6. **Richtige Orte:** `docs/architecture/SYSTEM-ARCHITECTURE.md` (kanonisch) + `docs/api/API-STANDARD.md` + NEU: Produkt-Contract-Dokument (nur Ort vorgeschlagen, kein Inhalt vorweggenommen).

Keine Implementierung gestartet. Keine Folge-Gates gestartet.

**HARD STOP.**
