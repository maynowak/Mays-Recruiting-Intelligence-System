# RIS-APPLICATION-COMPONENTS-07

STATUS: YELLOW

- Date/Time: 2026-09-28 10:55 UTC
- Branch + HEAD: main, 749764f (Vorgänger aa86adb intakt)
- Scope: 7 offene Punkte aus 06 vertiefen (Muster aus AI_AUDITLOG.md). Kein Umbau/Repair, keine TF-/IAM-/API-Änderung
- Sections: SQS-Kette → S3 → JobSearch-Persistenz → ATS-Pfad → Idempotency → GW-Runtime → Handler-only/Health → Profil v0.2 → Matrizen → MO → Historie
- Findings: s. unten (nur Code-Beweise)
- Evidence: sqs/main.tf, lambda-Policies, handler.py, jobsearch/*, ats_agent/*, chain.py/executor.py/invocation.py, api/main.tf, Tests, Grep-Leeren
- Classification: YELLOW
- Terraform Checks: KEINE (reine Code-Analyse)
- Git Status: 0 modified, 8 untracked (unberührt); AI_AUDITLOG Template-only
- Files Changed: nur Report + Execution-Log
- Open Questions: s. unten
- Risks: Keine durch Analyse
- Next Actions: Review; KEINE Folgeschritte ohne Review
- Resume Point: Analyse committet (s. Commit)

## Objective

Offene 06-Punkte schließen (SQS/S3/JobSearch/ATS/Idempotency/GW-Lücken/Laufzeit) — Analyse only.

## SQS Receive Analysis

| Element | Vorhanden | Code-Verwendung | Status |
|---|---|---|---|
| work_queue (+DLQ, SSE, redrive maxReceive 3) | JA (sqs/main.tf:3-28) | Send (Execute) + Mapping-Consume | WIRED |
| cv/ats/match-Queues (+DLQ-Anbindung) | JA (Z.30-75) | KEINE (Grep leer überall) | UNWIRED (definiert, ungenutzt) |
| Mapping (work_queue→agent, batch 5) | JA | Records-Consume | WIRED |
| function_response/batch-window/Filter | NEIN | — | NOT FOUND |
| Visibility 300s / Retention 14d | JA (Defaults) | operativ | WIRED (Config) |
| IAM Receive/Delete (execution-Rolle) | NEIN (nur Send/GetAttributes; Receive NUR im Orphan-Doc) | Mapping braucht sie IMPLIZIT | LÜCKE (Regel fehlt, Pfad existiert) |
| Handler-Verwendung | Records-Parse + Work-Laden + Body-Execute | — | WIRED |

SQS-Receive-Kette: VOLLSTÄNDIG verdrahtet bis auf fehlende Receive/Delete-Regel (Mapping läuft ohne sie NICHT — Befund, kein Fix hier).

## S3 Runtime Analysis

Actions/ARNs/Env/Imports/Clients/Objekt-Ops/TF-Resourcen/Runtime/ATS/CV/JobSearch: ALLE Greps LEER. Ergebnis: S3 Runtime Usage NOT FOUND — IAM PRESENT / RUNTIME USAGE NOT FOUND (Policy ohne Pfad). Keine Berechtigungsänderung.

## JobSearch Persistence

Tabelle: NUR als Doku-Dict (`jobsearch-job_searches`, repository.py:200) — KEINE TF-Ressource, KEIN Env (einzige Quelle: ctor-arg/env, nie gesetzt), KEIN Installer-Provisioning. Tests: env `env-table` (Mock, keine reale Tabelle). Doku beschreibt Tabelle als geplant (JOBSEARCH-PROFILE-01). Ergebnis: PARTIAL (Code bereit, nichts verdrahtet/deployt). Kein Tabellen-Bau hier.

## ATS Execution Path (belegt)

API-execute → WorkItem(`type: agent_<id>`) → SQS → Worker → Body → Executor (Context-Validate) → Router.route → Handler. ATS-spezifisch: `ChainStep(ats_agent/ats.analyze)` (Templates + Doku-Beispiel) + `ATSAgent.process_work` (Code) + Registry (CatalogAdapter/DynamoDB-Inhalt = live UNKNOWN) + Invoker/Contract (In-Prozess-Pipeline, KEIN Lambda-Invoke). ATSHttpClient (HTTP, URL-parametriert): CODE vorhanden, KEIN Aufrufer im Laufzeitpfad. Graph s. Conclusion (nur vorhandene Pfade; Mock-/Duplicate-Pfade NICHT hineininterpretiert).

## Idempotency / Deduplication

1. Erzeugt: Execute (Key aus Body/uuid), Invoker (`inv-uuid`), Context-Default. 2. Gespeichert: im WorkItem (+ DynamoDB-put). 3. Geprüft: NIRGENDS (kein Lookup, kein ConditionExpression, kein Dedup-Check — Greps leer; `dedup_key()`-Accessor ungenutzt). 4. Duplicate: Neuanlage + Neuversand (kein Schutz). 5. SQS-Retry: Re-Execution (Mapping redelivert; kein Filter). 6. Dokumentiert: NEIN (als Semantik). Ergebnis: PARTIAL (Erzeugung+Speicherung JA, Prüfung NEIN).

## API Gateway Runtime Analysis

| Route | Gateway Event | Handler erwartet | Dispatch | Ergebnis |
|---|---|---|---|---|
| GET /health (NONE) | v2 | KEIN Branch | `/`+GET → 404 | 404 (statisch) |
| GET /platform|/me|/me/profile|/agents (JWT) | v2 (+Claims) | httpMethod/path | `/`+GET → 404 | 404 (statisch; GW-401/403 VOR Lambda ohne Token) |
| (alle) | — | — | — | live UNVERIFIED |

## Handler-only Routes

`/api/agents/*`: INTERNAL (Handler + Tests, KEIN GW, KEIN OpenAPI-Eintrag). `/me/jobsearches*`: INTERNAL (dto.). `/work*`: INTERNAL (dto.). KEINE als GATEWAY/TEST-ONLY/UNUSED klassifizierbar (alle mit Handler + teils Tests) — Extern-Status: UNKNOWN (kein GW).

## Health Route

GW JA (NONE, seit G0.1, KEINE Doku/Tests/Begründung gefunden). Handler NEIN → statisch 404. INTENT UNKNOWN (keine Spekulation, kein Fix).

## Runtime Wiring Matrix

/me/profile: WIRED (Code) / UNREACHABLE (GW-v2-Dispatch, statisch). /agents: dto. Execute: PARTIALLY WIRED (Handler-Kette JA, GW-Anbindung NEIN). SQS Worker: WIRED (minus Receive-Regel). JobSearch: PARTIALLY WIRED (Code JA, Persistenz NEIN). ATS: PARTIALLY WIRED (Code/Template JA, Registry-Population + HTTP-Pfad offen).

## Application Profile Candidate v0.2

Identity PROVEN · Compute PROVEN (1 Lambda) · API PROVEN (5 GW + Handler-Super-Set) · Events PROVEN (GW-v2/SQS; kein EB/SNS) · Messaging PROVEN (5 Queues definiert, 1 verdrahtet + DLQ; Mapping batch 5) · Data PROVEN (4 Tabellen + JobSearch-offen; KEIN S3-Pfad) · Internal PROVEN (Body/Ecosystem/ATS-Artefakt/JobSearch-Paket) · External PARTIAL (ATS-Client-Code ungenutzt; MO NOT FOUND) · IAM PROVEN (Regeln s. Matrix; Receive-Lücke + S3-ohne-Pfad + JobSearch-ohne-Abdeckung) · Runtime PARTIAL (s. Matrix).

## Communication Matrix v0.2

| Source | Event/Action | Target | Resource | Code Path | IAM | Runtime |
|---|---|---|---|---|---|---|
| GW | v2-Event | agent-Lambda | — | 5 Routen → Integration | Allow (api-Modul) | statisch 404-seitig |
| agent | Put/Get/Query | DynamoDB | 4 Tabellen | Handler + Worker | Allow (Rollen) | WIRED |
| agent | SendMessage | SQS | work-queue | `_execute_agent` | Allow | WIRED |
| SQS | Records | agent-Lambda | work-queue | Mapping batch 5 | FEHLT (Receive/Delete) | WIRED (Regel-Lücke) |
| agent | Execute | AgentBody | In-Prozess | `_process_work_item` | n/a | WIRED |
| Body | Route/Exec | Agents | Registry/DynamoDB-Katalog | Executor/Invoker/Chain | n/a | WIRED (ATS-Population offen) |
| Handler | CRUD | JobSearchRepo | (Tabelle UNGESETZT) | lazy Import | FEHLT | UNWIRED |
| — | — | S3 | Data-Bucket | KEINER | Allow (ungenutzt) | UNWIRED |
| — | — | MO | — | KEINER | — | NOT FOUND |

## Mays-Orders Boundary

Letzte gezielte Suche (Endpoints/URLs/ARNs/Invoke/IAM/Env/Secrets/TF/SDK/HTTP): HTTP-Client-CODE (ATSHttpClient, RealMaysOrdersAdapter als "Later Production"-Doku-Muster mit Platzhalter-Endpoint) VORHANDEN, aber KEIN Laufzeit-Aufrufer (Grep-leer) → RIS → Mays-Orders = NOT FOUND (verfeinert: Muster-Code existent, unverdrahtet; KEINE zukünftige Architektur behauptet).

## Remaining Open Questions

Receive-Regel; S3-Pfad; JobSearch-Verdrahtung (Tabelle/Env/IAM, Owner); ATS-Population/HTTP-Pfad; Dedup-Semantik; v2-/GW-Lücken; cv/ats/match-Queues-Schicksal; Laufzeit-Stände.

## Conclusion (13 Antworten)

1. SQS: JA (bis auf Receive-Regel). 2. NEIN (IAM ohne Pfad). 3. NEIN (PARTIAL: Code ohne Verdrahtung). 4. Template-Pfad + Registry (Population offen) + ungenutzter HTTP-Client. 5. PARTIAL (Erzeugung+Speicherung, keine Prüfung). 6. Alle GW-Routen statisch 404-seitig (v2-Bruch). 7. Execute/JobSearch/Work = INTERNAL. 8. GW JA / Handler NEIN → 404 (Intent UNKNOWN, seit G0.1). 9. Matrix oben. 10. Profil v0.2 oben. 11. Matrix oben (Regel vs. Nutzung getrennt). 12. Profil-Lücken: Receive-Regel, JobSearch-Verdrahtung, ATS-Vollständigkeit, Dedup, v2/GW, cv/ats/match-Schicksal. 13. NEIN (Muster-Code ja, Anbindung nein).

---

*Analyse: RIS-APPLICATION-COMPONENTS-07 · Muster aus AI_AUDITLOG.md · nur
Code-Beweise · keine Architekturentscheidung · keine AWS-Mutation.*
