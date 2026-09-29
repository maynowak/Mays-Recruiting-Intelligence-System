# RIS-APPLICATION-COMPONENTS-06

STATUS: YELLOW

- Date/Time: 2026-09-28 10:30 UTC
- Branch + HEAD: main, aa86adb (Vorgänger b00d0ad intakt)
- Scope: Komponenten-Inventar NUR aus Code (§6ff, Muster aus AI_AUDITLOG.md). Keine Implementierung/IAM-/TF-Änderung/Architekturentscheidung
- Sections: API-/Data-Inventar → Resource-Mapping → IAM-Matrix → Graph → Execution-Chain → ATS/JobSearch → Identity → MO → Profil → Historie
- Findings: s. unten (nur Code-Beweise)
- Evidence: handler.py, agent_body/*, ecosystem/*, ats_agent/*, jobsearch/*, TF-Module, Grep-Leeren
- Classification: YELLOW
- Terraform Checks: KEINE (reine Code-Analyse)
- Git Status: 0 modified, 8 untracked (unberührt); AI_AUDITLOG Template-only
- Files Changed: nur Report + Execution-Log
- Open Questions: s. unten
- Risks: Keine durch Analyse
- Next Actions: Review; KEINE Folgeschritte ohne Review
- Resume Point: Analyse committet (s. Commit)

## Objective

Belegen (nicht raten): welche Komponenten/Lambdas/Events/Ressourcen/IAM-Wege existieren und tatsächlich benutzt werden.

## Application Component Inventory

| Komponente | Ort | Status |
|---|---|---|
| agent-Lambda-Handler | lambda/handler.py (`handler`, REST-Dispatch + SQS-Dispatch) | ACTIVE |
| AgentBody/Executor/Router/Context/Monitor/Result/Invocation | agents/agent_body/* | ACTIVE (Import + `AGENT_BODY.execute` Z.767) |
| Registry/Discovery/Eligibility/Chain/CatalogAdapter | agents/ecosystem/* | ACTIVE (ChainStep + Adapter) |
| ATSAgent + ATSHttpClient | agents/ats_agent/* | DEFINIERT, nur via ChainStep referenziert (kein direkter Runtime-Call belegt) |
| Reference-Agent | agents/reference_agent | ACTIVE (registriert, chain.py:19) |
| JobSearch (Repo/Domain/Spec/Client/Adapter) | jobsearch/* | ARTEFAKT aktiv, Laufzeit teilverdrahtet (s. BOUNDARY-05) |
| SQS-Worker-Pfad | handler `_process_work_item` | ACTIVE |

## Lambda Inventory

| Lambda | Runtime | Handler | Trigger | Zweck |
|---|---|---|---|---|
| `agent` (einzige) | python3.14 | handler.lambda_handler | API-GW (5 Routen) + SQS-Mapping (batch 5) | API + Work-Verarbeitung |

## Event Inventory

API-GW-v2-Events (statisch 404-seitig) + SQS-Records (verarbeitet) + REST-Test-Events (Tests). Kein EventBridge/Scheduler/SNS (Grep-leer PROVEN).

## API Component Matrix (§6)

| Route | Gateway | Handler | Component | Data/Service |
|---|---|---|---|---|
| GET /health | JA | NEIN (404) | — | — |
| GET /platform | JA | static info | — (Konstanten) | — |
| GET /me | JA | user-Echo | JWT-Claims | — |
| GET /me/profile | JA | `_get_user_profile` | user-profile | DynamoDB |
| GET /agents | JA | Entitlements + Katalog | entitlements/agent-catalog | DynamoDB ×2 |
| POST /api/agents/*/execute | NEIN | `_execute_agent` | Work-Erzeugung | DynamoDB + SQS |
| /me/jobsearches* | NEIN | JobSearch-CRUD | JobSearch-Repo | DynamoDB (Env offen) |
| /work* | NEIN | Work-Create/Get | Work-Items | DynamoDB |

## Data Component Matrix (§7)

| Tabelle | Zweck | Consumer | Producer | Tenant Scope |
|---|---|---|---|---|
| user-profile | Nutzerprofile | Handler (+Lambda-Env/Policy) | — (kein Write-Pfad belegt) | userId/tenantId-Parameter |
| agent-catalog | Agent-Metadaten | Handler + CatalogAdapter→Registry | — | — |
| entitlements | Zugriffsrechte | Handler-Gates (401/403 via 403) | — | userId/tenantId |
| work-items | Work-Queue-State | Worker + Handler-Reads | `_execute_agent` (put) | tenantId/userId-Felder |
| jobsearch | JobSearch-Objekte | Handler-CRUD (Env UNGESETZT) | dto. | Parameter (laufzeit-unwirksam ohne Tabelle) |

S3 (Data-Bucket, versioniert): KEIN Code-Zugriff gefunden (Policy vorhanden, Nutzung fehlt). Secrets/Parameter: KEINE. SQS: work-queue (1).

## Resource → Component (§8, nur echte Pfade)

agent ──READ→ user-profile/agent-catalog/entitlements (Get/Query) ──WRITE→ work-items (put) ──SEND→ work-queue (SendMessage+Attrs) ──READ→ SQS-Records (Mapping) ──EXEC→ AgentBody. KEIN S3-Zugriff, KEIN Lambda-Invoke, KEIN JobSearch-Tabellen-Zugriff mit gesetzter Tabelle.

## IAM Communication Matrix (§9: Regel vs. Nutzung getrennt)

| Source | Action | Resource | Code-Pfad | Status |
|---|---|---|---|---|
| execution-Rolle | dynamodb Get/Query/BatchGet | Plattform-Tabellen (+Index) | Handler-Reads | REGEL+GENUTZT |
| dto. | dynamodb Put/Get/Update/Query/Delete | work-items | put + Worker-Reads | REGEL+GENUTZT |
| dto. | sqs SendMessage/GetQueueAttributes | Queue (+URL-or-*) | `_execute_agent`-Send | REGEL+GENUTZT |
| dto. | logs Create*/Put* | `arn:aws:logs:*:*:*` | Logging | REGEL+GENUTZT (angenommen) |
| dto. | s3 Put/Get/Delete | Data-Bucket/* | KEINER gefunden | REGEL OHNE NUTZUNG |
| dto. | sqs Receive/Delete | — | Mapping braucht sie IMPLIZIT | LÜCKE (nur iam-Orphan-Doc hat sie) |
| api-Modul | lambda:InvokeFunction | Funktion (Allow) | GW→Lambda-Erlaubnis | REGEL (Allow, kein Aufruf) |

## Communication Graph (§10, nur Nachweisbares)

```text
User ─JWT→ API-GW (5 Routen) ──► agent Lambda ──READ→ Profile/Katalog/Entitlements (DynamoDB)
                                              ├──WRITE→ work-items ──SEND→ work-queue (SQS)
                                              └──SQS-Records──► agent Lambda ──EXEC→ AgentBody ──► Agent (reference registriert; ATS nur ChainStep)
JobSearch-Zweig: Handler-CRUD ──► JobSearchRepo ──► (Tabelle UNGESETZT)
```

## Agent Execution Chain (§11, belegt)

POST-execute → user_context (401) → Entitlement-403 → Katalog-404 →
uuid-WorkItem (QUEUED, idempotencyKey, payloadVersion, attempt 0) →
DynamoDB-put + SQS-send (Attribute workType/agentId) → 202 →
Mapping (batch 5) → Records-Parse → `_process_work_item` → AgentBody
(Router→Executor→Agent) → COMPLETED/FAILED + workId-Rückschreibung.
Idempotency: Key erzeugt+gespeichert, KEINE Deduplizierungs-Prüfung im Code
gefunden (Befund). Registry: CatalogAdapter (DynamoDB) + Code-Registrierung
(reference); Invoker/ProcessingChain-Klassen existent, ChainStep mit ATS
referenziert (ATS-Ausführungspfad PARTIAL).

## Identity Chain (§13)

User → Cognito → JWT → GW-Authorizer (Issuer/Audience) → Lambda →
`sub/email/custom:tenant_id/cognito:groups` → userId-Pflicht, Tenant-Scoping
in Repo-Calls. KEINE Weitergabe an AWS-Ressourcen (keine Assume/Tagging).
Gruppen: gelesen, KEINE gruppenbasierte Verzweigung gefunden (nur Durchleitung).

## JobSearch / ATS Placement (§12, aus Gate 05 + verifiziert)

JobSearch: NUR `/me/jobsearches*` (intern, KEIN GW); ATS: NUR ChainStep-Referenz
+ Domänen-Modell (ATSSearchProfile in JobSearch-CRUD); KEIN direkter ATS-Pfad
belegt (kein separater Aufruf/Invoke). JobSearch NICHT von Agent Runtime
verwendet (kein Import dort); ATS via Runtime NUR per ChainStep-Routing
(PARTIAL belegt).

## Mays-Orders Boundary (§14)

NOT FOUND (keine URLs/ARNs/Invokes/HTTP-Clients/Env/Secrets/TF-Refs im
Ausführungspfad; Greps leer). Keine zukünftige Verbindung behauptet.

## Profile Candidate (§15)

Identity PROVEN (Cognito/JWT/Claims/Tenant) · App/Domain PROVEN (Platform +
JobSearch-Paket) · Compute PROVEN (1 Lambda, python3.14, Handler) · API
PROVEN (5 GW-Routen + Handler-Super-Set) · Auth PROVEN (JWT/Authorizer/Gates) ·
Events PROVEN (GW-v2 + SQS; KEIN EventBridge/SNS) · Data PROVEN (4 Tabellen +
JobSearch-offen) · Messaging PROVEN (1 Queue + Mapping batch 5, Receive-Lücke
notiert) · IAM PROVEN (Rollen/Policies s. Matrix, S3 ungenutzt) · Internal
PROVEN (Body/Ecosystem/Repo/Domain) · External: MO NOT FOUND, externe APIs
PARTIAL (ATSHttpClient existent, ungenutzter Pfad).

## Historical Consistency (§16, entscheidungsrelevant)

Runtime-Kern stabil seit G0.x (Body/Ecosystem), JobSearch-Paket d6ccd09 +
CRUD 849ae1a, Repairs b5a2703/21cc04a (Lambda/IAM) ohne Verhaltensänderung.
Keine Struktur-Brüche belegt.

## Open Questions

SQS-Receive-Abdeckung (Mapping braucht sie — nur Orphan-Doc hat sie); S3-
Policy ohne Nutzung; JobSearch-Persistenz (Tabelle/Env/IAM); ATS-Ausführungs-
pfad-Vollständigkeit; Idempotency-Dedup (nicht gefunden); v2-/GW-Lücken
(fremde Gates); Laufzeit-Stände.

## Conclusion (9 Antworten)

1. Handler(+Body/Ecosystem/JobSearch-Paket/ATS-Artefakt) + 1 Lambda. 2. EINE
Lambda (`agent`). 3. GW-v2 + SQS-Records (+ REST nur Tests). 4. 4 Tabellen +
JobSearch-offen (Namen/ARNs s. Matrix); S3-Bucket ohne Code-Nutzung. 5. s.
IAM-Matrix (Regel vs. Nutzung getrennt; Receive-Lücke). 6. Genutzte Wege s.
Graph; S3-Policy ungenutzt; JobSearch-Tabelle ungesetzt. 7. NUR Definiertes
ohne Verdrahtung: S3-Zugriff, JobSearch-Tabelle, ATS-Direktpfad, GW-lose
Routen. 8. JA — zentrale Runtime (`AGENT_BODY.execute`, einziger
Verarbeitungspfad). 9. Execute→Validierung→Entitlement→Work→DynamoDB→SQS→
Mapping→Worker→Body→Agent (s. §11). 10. NEIN (NOT FOUND). 11. s. Profil:
Identität/Compute/API/Events/Data/Messaging/IAM/Internal PROVEN; JobSearch-
Persistenz + ATS-Vollständigkeit + MO = offen/nicht vorhanden.

---

*Inventar: RIS-APPLICATION-COMPONENTS-06 · Muster aus AI_AUDITLOG.md · nur
Code-Beweise · keine Architekturentscheidung · keine AWS-Mutation.*
