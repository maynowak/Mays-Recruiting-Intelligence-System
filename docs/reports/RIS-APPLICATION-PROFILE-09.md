# RIS-APPLICATION-PROFILE-09 — Mays-RIS Application Profile v1 (voll)

STATUS: YELLOW

- Date/Time: 2026-09-28 11:35 UTC
- Branch + HEAD: main, 307db8a (Kurz-Profil) — VOLLSTÄNDIGE Fassung (ersetzt Kurz-Profil inhaltlich)
- Scope: Fachlich-technisches Voll-Profil (Muster aus AI_AUDITLOG.md). Herkunft: GATE-PROVEN vs. DECISION-INPUT (vorgegeben, gekennzeichnet). Kein Umbau, keine AWS-Mutation
- Sections: Identity → Purpose → Boundary(+Consumer) → UserProfile → AgentRuns → JobSearch → CV → ATS → AgentPlatform → APIPlatform → Identity&Access → DataDomains → Consumers → Extension → AWS-Mapping → IAM-Requirements → Core/Extension → Non-Goals → OpenDecisions
- Findings: s. Profil (Provenienz je Eintrag)
- Evidence: Gates 01–08 + Handler/TF/JobSearch/ATS-Code + Commits (d6ccd09/849ae1a/818d774/13e4d84) + Frontend-Vertrag
- Classification: YELLOW
- Terraform Checks: KEINE (Profil-Dokument)
- Git Status: 0 modified, 8 untracked (unberührt); AI_AUDITLOG Template-only
- Files Changed: Report (Voll-Fassung) + Execution-Log
- Open Questions: s. §20
- Risks: Keine durch Dokument; Vorgaben ≠ Code-Stand (gekennzeichnet)
- Next Actions: Review; KEINE Folgeschritte ohne Review
- Resume Point: Voll-Profil committet (s. Commit)

## 1. Identity

Mays-Recruiting-Intelligence-System / Mays-RIS — API Platform / Recruiting Intelligence Platform (GATE-PROVEN: Handler/GW/Runtime durchgängig).

## 2. Purpose (belegt, keine Marketing-Sprache)

Authentifizieren (Cognito/JWT) · Profil bereitstellen · benutzerbezogene Daten verwalten (Profil/Katalog/Entitlements) · Agent Runs im Benutzerkontext (Entitlement-Gates + tenant-scoped Work) · Agent Runtime · JobSearch (PARTIAL) · CV (Vorgabe, Code-LEER) · ATS via Agenten (PREPARED).

## 3. Product Boundary (+ Consumer, AKTUELL vs. SPÄTER)

```text
                  Mays-RIS API / Application
                    │ (PROVEN: Handler/GW/Runtime)
       ┌────────────┼────────────┐
       ▼            ▼            ▼
 User Profile   Agent Runs   JobSearch (PARTIAL)
```

Consumer AKTUELL: Mays Job Matcher Web Application (DECISION-INPUT, gestützt Frontend-Binding-Vertrag) + authentifizierte API-Nutzer (PROVEN: JWT-Gates). SPÄTER (Vorgabe, nichts implementiert): externe Consumer/Offerer, Apply-Agents, Actors.

## 4. User Profile (PROVEN)

Identity: sub→userId, email, custom:tenant_id→tenantId, cognito:groups (generisch). Storage: user-profile-Tabelle (Get by userId + Tenant-Check). Zugriff: GET /me (Echo, 401) + GET /me/profile (404 o. Profil). Tenant-Isolation: im Code (Warnung bei Mismatch). KEINE erfundenen Felder (Response = Claims bzw. Item-Passthrough).

## 5. Agent Runs (PROVEN Ablauf, PARTIAL Dedup)

User → Execute (401/403/404-Gates) → Entitlement → WorkItem (uuid, type agent_<id>, tenant/user/request-IDs, capability, idempotencyKey, payloadVersion, status QUEUED, attempt 0, TTL+30d) → SQS (+Attribute) → Worker → Runtime → Agent. Status: QUEUED→COMPLETED/FAILED (Rückschreibung). Semantik aus Code (keine Erfindung).

## 6. JobSearch (PRODUCT COMPONENT; Persistence PARTIAL/UNWIRED)

Rolle: Produkt-Domäne (Modelle/Repo/Spec/Client). Benutzerbezug: userId/tenantId-scoped CRUD. API-Grenze: NUR `/me/jobsearches*` (handler-intern, KEIN GW). Repository: boto3-DynamoDB (Tabelle aus Env/None). Persistenz: UNVERDRAHTET (keine TF-Tabelle/Env/IAM) — NICHT als produktiv dargestellt. CV-Verhältnis: keins belegt. ATS-Verhältnis: keins belegt (ATSSearchProfile = JobSearch-Domänenmodell, KEIN ATS-Aufruf).

## 7. CV (Vorgabe; Code-LEER)

Nachgewiesene CV-Funktion: KEINE (kein Code/Daten/Queue-Nutzung/Tests — nur Queue-/Template-Namen). PRODUCT COMPONENT = ja (Vorgabe). RUNTIME STATUS = PREPARED (Infra: cv-Queue definiert). NICHT aus Queue-Namen auf Funktion geschlossen.

## 8. ATS (PRODUCT COMPONENT; Runtime PARTIAL)

Job → ATSAgent.process_work (validate → _analyze_job via HTTP-Client) → Recommendation/Analysis. Bausteine: Client/validate/status/descriptor/Registrierungs-Fn/Tests (PROVEN). Offen: Registry-Population im Prod-Pfad, HTTP-URL-Verdrahtung. KEIN Extraktions-/Empfehlungs-Modul über agent.py hinaus (nicht erfunden).

## 9. Agent Platform (ACTIVE CORE vs. PREPARED FRAMEWORK)

ACTIVE CORE: Registry (populiert), Descriptor, Router, Executor, Body, Reference-Agent. PREPARED FRAMEWORK: Discovery/Eligibility/Invoker/Contract/Chain (+Tests, kein Prod-Pfad). EINE `agent`-Lambda bleibt Runtime-Einheit (keine Aufteilung).

## 10. API Platform (Gateway/Handler/intern getrennt)

GW: 5 Routen (JWT außer health). Handler-Super-Set (Execute/JobSearch/Work NUR intern). Intern: ohne GW/ohne Spec. v2/REST-Mismatch = IMPLEMENTATION GAP (nicht repariert).

## 11. Identity & Access (getrennt)

Authentication (Cognito→JWT→Authorizer) ≠ Authorization (Entitlement-Gates 403) ≠ Tenant-Isolation (Repo-Checks). Claims: sub/email/tenant/groups.

## 12. Data Model Boundary

| Domain | Storage | Runtime | Status |
|---|---|---|---|
| User Profile | user-profile | Reads | PROVEN |
| Agent Catalog | agent-catalog | Reads + Registry | PROVEN |
| Entitlements | entitlements | Gates | PROVEN |
| Work Items | work-items | Write + Worker-Reads | PROVEN |
| JobSearch | KEINE (Doku-Dict) | CRUD ohne Tabelle | NOT WIRED |
| CV | KEINE | — | NOT WIRED |
| ATS/Run Data | Work-Items (Result-Rückschreibung) | via Body | PROVEN (als Work-Result) |

## 13. API Consumers (CURRENT vs. FUTURE)

CURRENT: Web-App (Vorgabe + Vertrag), authentifizierte Nutzer (Gates). FUTURE/EXTENSIBLE (nur Strategie, nichts implementiert): externe Consumer, Offerer, Apply-Agents, Actors.

## 14. External Offerers / Actors (nur Strategie)

Web App + API Client + externe Offerer (Apply/Actor) als zukünftige Plattformfähigkeit. KEINE API/IAM-Regel erfunden.

## 15. AWS Runtime Mapping (nur belegt)

Profile→Lambda→user-profile; Runs→Lambda→work-items→SQS→Lambda; JobSearch→Lambda→Repo→(Tabelle offen); ATS→(Runtime offen). KEINE S3-/MO-Pfade.

## 16. IAM Communication Requirements (REQUIREMENTS, keine Implementierung)

DynamoDB Get/Query (3 Tabellen) + Put/Get/Update/Query/Delete (work) + SQS-Send + SQS-Consume (FEHLT: Receive/Delete — benötigt, nicht vorhanden) + Logs. S3-Regel OHNE Pfad (nicht aufnehmen). JobSearch-Tabellen-Zugriff: benötigt SOFERN Tabelle (derzeit gegenstandslos).

## 17. CORE vs EXTENSION

CORE: Identity, Profile, Runs, Platform, JobSearch(-Domäne), CV(Vorgabe), ATS(Vorgabe), API. EXTENSION (Strategie, NICHT implementiert): Apply-Agents, Actors, Offerer, externe Consumer, Monetarisierung/Job-Boards.

## 18. Application Profile v1 (Konsolidierung obiger §§1–17)

## 19. Explicit Non-Goals

Keine TF-/IAM-Implementierung, keine API-Reparatur, keine Lambda-Aufteilung, keine JobSearch-Persistenz-Implementierung, keine ATS-Vervollständigung, keine Monetarisierung, keine MO-Anbindung.

## 20. Open Architecture Decisions (echt)

User-/Run-Datenmodelle (implizit vs. explizit); JobSearch-/CV-Persistenz; ATS-Run/Result-Persistenz; Registrierungs-/Entitlement-Modell; Consumer-/Offerer-Modell; GW-v2-Vertrag; SQS-Receive-IAM; MO-Grenze (falls je benötigt). NICHTS erfunden.

---

*Profil: RIS-APPLICATION-PROFILE-09 v1 (voll) · Muster aus AI_AUDITLOG.md ·
Vorgaben als DECISION-INPUT gekennzeichnet · keine Architekturänderung.*
