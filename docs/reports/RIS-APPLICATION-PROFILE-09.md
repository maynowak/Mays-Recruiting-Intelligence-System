# RIS-APPLICATION-PROFILE-09 — Mays-RIS Application Profile v1

STATUS: YELLOW

- Date/Time: 2026-09-28 11:20 UTC
- Branch + HEAD: main, 57fc27f (Gates 01–08 + 12 Vorgaben als Basis)
- Scope: Fachlich-technisches Profil v1 (Muster aus AI_AUDITLOG.md). Kein Umbau, keine AWS-Mutation. Herkunft je Punkt: GATE-PROVEN vs. DECISION-INPUT (vorgegeben)
- Sections: Identity → Purpose → Boundary → Funktionen → Runtime → Data → IAM-Ableitung → Offen
- Findings: s. Profil (Provenienz je Eintrag)
- Evidence: Gates 01–08 (referenziert), PLATFORM_FRONTEND_INTEGRATION (Frontend-Vertrag), CV-Grep-Leere, Vor-Reports
- Classification: YELLOW
- Terraform Checks: KEINE (Profil-Dokument)
- Git Status: 0 modified, 8 untracked (unberührt); AI_AUDITLOG Template-only
- Files Changed: nur Report + Execution-Log
- Open Questions: s. unten
- Risks: Keine durch Dokument; Vorgaben ≠ Code-Stand (gekennzeichnet)
- Next Actions: Review; KEINE Folgeschritte ohne Review
- Resume Point: Profil v1 committet (s. Commit)

## 1. Application Identity

| Feld | Wert | Herkunft |
|---|---|---|
| Name | Mays-Recruiting-Intelligence-System / Mays-RIS | GATE-PROVEN (Repo/Docs durchgängig) |
| Typ | API Platform / Recruiting Intelligence Platform | GATE-PROVEN (Handler/GW/Runtime) + DECISION-INPUT |
| Primary Consumer | Mays Job Matcher Web Application | DECISION-INPUT (gestützt: Frontend-Vertrag PLATFORM_FRONTEND_INTEGRATION als Binding Contract Platform↔JobSearch-Frontend) |
| Additional Consumers | User/API-Clients, spätere externe Consumer/Offerer | DECISION-INPUT (keine aktiven belegt — NICHT als aktiv dargestellt) |

## 2. Application Purpose (belegt, keine Marketing-Sprache)

Authentifizieren (Cognito/JWT PROVEN) · Profil bereitstellen (PROVEN) · benutzerbezogene Daten verwalten (PROVEN: Profil/Katalog/Entitlements) · Agent Runs im Benutzerkontext (PROVEN: Entitlement-Gates + tenant-scoped Work) · Agent Runtime (PROVEN) · JobSearch integrieren (DECISION-INPUT; Code PARTIAL) · CV-Daten (DECISION-INPUT; Code-LEER — nur Queue-/Template-Namen) · ATS via Agenten (DECISION-INPUT; Code PREPARED).

## 3. Product Boundary

```text
                  Mays-RIS API / Application
                    │ (GATE-PROVEN: Handler/GW/Runtime)
       ┌────────────┼────────────┐
       ▼            ▼            ▼
 User Profile   Agent Runs   JobSearch (PARTIAL: CRUD ohne Persistenz)
       │            │            │
       └────────────┼────────────┘
                    ▼
         CV / ATS Data (DECISION-INPUT: Code-LEER/PREPARED)
```

## 4. Funktionen → Technik (Auszug, Provenienz markiert)

Auth/Profile/Agent-Runs/Runtime: GATE-PROVEN. JobSearch-CRUD: Code JA/Persistenz NEIN. ATS-Ausführung: PREPARED (Registrierungs-Fn + Tests, kein Prod-Caller). CV-Verarbeitung: NUR Vorgabe (kein Code). Apply-Agents/Actors/externe Offerer/Consumer: VORGESEHEN (DECISION-INPUT, nichts implementiert). Monetarisierung/Programmatic Job Boards: AUSGESCHLOSSEN aus diesem Gate (Vorgabe).

## 5. IAM-Ableitung (Regel; Härtung später)

Kommunikation aus Codepfaden (PROVEN): DynamoDB-Reads (3 Tabellen), Work-Put, SQS-Send, SQS-Consume (Regel-LÜCKE notiert), Logs. NICHT aus Policies übernommen (S3-Regel ohne Pfad; JobSearch ohne Abdeckung). Härtung = späterer Schritt (Vorgabe).

## 6. AWS-Ableitung (aus Funktionen, nicht umgekehrt)

1 Lambda (API+Worker), 5 GW-Routen (JWT), 4 Tabellen (+ JobSearch-offen), 1 verdrahtete Queue (+DLQ), Cognito-Pool/Client. NICHT abgeleitet: S3-Nutzung, CV-/Match-Infra, MO-Anbindung.

## Open Questions

JobSearch-Persistenz (Owner); ATS-Produktivierung; CV-Realisierung (ganz offen); GW-Anbindung/Execute/v2 (Review-Entscheide); Receive-Regel; S3-Schicksal; Laufzeit-Belege.

---

*Profil: RIS-APPLICATION-PROFILE-09 v1 · Muster aus AI_AUDITLOG.md · Vorgaben als
DECISION-INPUT gekennzeichnet (nicht als Code-Fakt) · keine Architekturänderung.*
