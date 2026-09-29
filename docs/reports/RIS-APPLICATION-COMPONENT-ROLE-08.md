# RIS-APPLICATION-COMPONENT-ROLE-08

STATUS: YELLOW

- Date/Time: 2026-09-28 11:00 UTC
- Branch + HEAD: main, 08dae39 (Vorgänger 749764f intakt)
- Scope: Rollen NUR aus Evidenz (Muster aus AI_AUDITLOG.md). Kein Umbau/Repair, keine TF-/IAM-/API-Änderung
- Sections: Runtime-Nutzung → Queues → ATS/CV/Match → JobSearch/Profile/Lambda/GW/Cognito/Dynamo/S3/MO → Historie → Graphen → Matrix
- Findings: s. Tabellen (keine Rolle aus Namen/Dateinamen)
- Evidence: Caller-Greps (Router/Registry/Adapter/Tests), Chain-/Executor-/Invoker-Code, Registry-Funktionen, TF-Queues/Policies/Env, Handler-Reads, Tests, Commits (818d774/13e4d84/deb2954/d6ccd09/849ae1a)
- Classification: YELLOW
- Terraform Checks: KEINE (reine Code-Analyse)
- Git Status: 0 modified, 8 untracked (unberührt); AI_AUDITLOG Template-only
- Files Changed: nur Report + Execution-Log
- Open Questions: s. Entscheidungs-Fragen
- Risks: Keine durch Analyse
- Next Actions: Review; KEINE Folgeschritte ohne Review
- Resume Point: Analyse committet (s. Commit)

## Objective

Rollen (CORE/OPTIONAL/PREPARED/UNUSED/INCOMPLETE/EXTERNAL_BOUNDARY/UNKNOWN) NUR aus Code/Tests/Doku/Historie — nie aus Namen.

## Role Definitions

Per Ticket §2 ( Framework ≠ auto-CORE; "nicht benutzt ≠ optional"; UNKNOWN bei Dünn-Beleg).

## Agent Runtime Roles

| Component | Role | Runtime used | Evidence |
|---|---|---|---|
| AgentBody/Executor/Router/Context | CORE | JA (`AGENT_BODY.execute`, Router.route) | handler.py:767, body/__init__, executor.py |
| AgentRegistry | CORE | JA (CatalogAdapter-Population + Router-Lookup) | handler.py:36-72 |
| AgentDescriptor | CORE | JA (Registry-Einträge) | registry/descriptor |
| AgentDiscovery/EligibilityCheck | PREPARED | NEIN (Prod nutzt Router direkt; nur Framework + Tests) | Caller-Grep (nur `__init__`/Tests); test_event_hook_pipeline |
| AgentInvoker/InvocationContract | PREPARED | NEIN (nur Chain/intern + Tests) | invoker→Body (ungenutzter Pfad); test_agent_invocation |
| ProcessingChain/ChainExecutor | PREPARED | NEIN (Prod-Pfad ohne Chain) | nur chain.py + Tests |
| Reference Agent | CORE | JA (registriert, chain.py:19 + Router) | Registrierungs-Call |

## Queue Roles

| Queue | Exists | Producer | Consumer | Mapping | Runtime Use | Role |
|---|---|---|---|---|---|---|
| work | JA | Execute-Handler | agent (Mapping) | JA (batch 5) | JA | CORE (trotz v2-Diskussion: Pfad aktiv) |
| cv/ats/match | JA (je +DLQ) | KEINER | KEINER | NEIN | NEIN | PREPARED (Infra bereit, ungenutzt — NICHT "optional") |
| DLQ | JA (shared) | Redrive (TF-Ebene) | KEINER (Code) | — | PASSIV (bei Failures) | PREPARED |

## ATS Role

1. Ausführbar? NUR wenn registriert + URL gesetzt (beides offen). 2. Descriptor? JA (Funktion `get_ats_descriptor`, unaufgerufen im Prod-Pfad). 3. Registry-Eintrag? Mechanismus JA (`register_ats_agent`, Tests), Prod-Aufruf NEIN. 4. Capability? JA (`ats.analyze` + `analyze.job`). 5. Invocation-Pfad? NUR via Router/Chain (Template), kein direkter. 6. Tests? JA (unit/ats_agent). 7. Queue? NEIN. 8. API? NEIN (GW). 9. Historisch vorgesehen? JA, bewusst (818d774 "integrate via HTTP API", 13e4d84 "register ... connecting"). 10. Rolle: PREPARED (nicht CORE trotz viel Code — kein Prod-Pfad).

## CV Role / Match Role

| Component | Code | Runtime | Queue | Tests | Role |
|---|---|---|---|---|---|
| CV-Agent | NICHT GEFUNDEN (nur Template-Name) | NEIN | PREPARED-Queue | KEINE | UNKNOWN |
| Match-Agent | dto. | NEIN | dto. | KEINE | UNKNOWN |
| cv/match-Queues | JA | NEIN | — | KEINE | PREPARED |

## JobSearch Role

INCOMPLETE (nicht UNUSED — Handler greift zu; nicht CORE — Persistenz fehlt: Tabelle/Env/IAM unbelegt, table None). Spec/Client/Domain: Artefakt-belegt.

## Profile / Catalog / Entitlement Roles

Alle CORE: gelesen in Live-Pfaden (me/profile, agents, execute-Gates), tenant-scoped, graceful-degradation bei fehlendem Env. KEINE Writes (nur work-items-put). IAM + Env vorhanden.

## Agent Lambda Role

CORE mit DREI kombinierten Anwendungs-Rollen in EINER Lambda (explizit, KEIN Aufteilungs-Vorschlag): (a) API-Handler, (b) SQS-Worker, (c) JobSearch-CRUD-Träger. Auslöser: GW + Mapping + (Tests).

## API Gateway Role

CORE (5 Routen + JWT-Integration verdrahtet). v2-Diskrepanz = Wiring-Qualität (INCOMPLETE als Verdrahtung), ändert Architektur-Rolle NICHT.

## Cognito Role

CORE (einziger Auth-Pfad: Pool → Authorizer → Claims → userId/tenantId).

## DynamoDB Roles

4 Tabellen CORE (Reads + work-Writes, IAM + Env); jobsearch-Tabelle INCOMPLETE (Definition ohne Ressource); NICHT vermischt (getrennte Zeilen).

## S3 Role

UNUSED (Policy vorhanden, 0 Nutzung PROVEN per Exhaustiv-Grep; KEINE Zukunfts-Annahme).

## Mays-Orders Role

NOT FOUND (keine technische Boundary vorhanden → KEIN EXTERNAL_BOUNDARY; keine Zukunfts-Aussage).

## Core Application Graph (nur CORE)

```text
User → Cognito → API-GW → agent Lambda ──READ→ Profile/Katalog/Entitlements
                                  ├──WRITE→ work-items ──SEND→ work-queue ──► agent Lambda ──► AgentBody/Router/Registry ──► Reference-Agent
                                  └── JobSearch-CRUD (INCOMPLETE markiert, kein CORE-Pfeil zur Tabelle)
```

## Prepared / Incomplete Graph

```text
PREPARED: Discovery/Eligibility/Invoker/Chain · ATS (Code+Tests+Registrierungs-Fn) · cv/ats/match-Queues · DLQ
INCOMPLETE: JobSearch-Persistenz (Tabelle/Env/IAM) · ATS-Laufzeit (Population/URL) · GW-v2-Verdrahtung
```

## Application Profile Role Matrix

| Component | Role | Runtime | AWS | IAM | Evidence |
|---|---|---|---|---|---|
| Handler/agent/Body/Router/Registry | CORE | JA | Lambda/SQS/Dynamo | Allow+genutzt | Pfade oben |
| GW/Cognito/4 Tabellen/work-Queue | CORE | JA | API/Cognito/Dynamo/SQS | Allow+genutzt | Verträge |
| Discovery/Eligibility/Invoker/Chain | PREPARED | NEIN | — | — | Framework+Tests |
| ATS (Code/Tests/Reg-Fn) | PREPARED | NEIN | — | — | 818d774/13e4d84/Tests |
| cv/ats/match-Queues, DLQ | PREPARED | NEIN/passiv | SQS-Res. | — | TF (ungenutzt) |
| JobSearch-Persistenz | INCOMPLETE | NEIN | — | FEHLT | table-None |
| S3-Zugriff | UNUSED | NEIN | Bucket | Allow-ohne-Pfad | Exhaustiv-Grep |
| MO | NOT FOUND | — | — | — | Grep-Leere |
| CV/Match-Agenten | UNKNOWN | — | — | — | Nur Template-Namen |

## Decision-Relevant Open Questions

Ungenutzte Queues: Warum existent (Reserve vs. Rest)? ATS: Produkt-Bestandteil oder vorbereitet (Owner)? JobSearch-Persistenz ins aktive Profil (Owner)? IAM-Receive-Regel zum Core (fehlend!)?

## Conclusion

CORE: Handler/agent-Lambda/Body-Router-Registry/GW/Cognito/4 Tabellen/work-Queue+Mapping/Reference/Profile-Katalog-Entitlements-Reads. PREPARED: Runtime-Framework, ATS-Paket, 4 Queues. INCOMPLETE: JobSearch-Persistenz, ATS-Laufzeit, GW-Verdrahtung. UNUSED: S3-Zugriff. UNKNOWN: CV/Match-Agenten. NOT FOUND: MO. Queues aktiv: NUR work (+DLQ passiv). Domain-Core: Profile/Katalog/Entitlements/Work (+ JobSearch INCOMPLETE). Vorbereitet zu dokumentieren: Framework/ATS/Queues/DLQ. Entscheidungsrelevant: s. Fragen.

---

*Analyse: RIS-APPLICATION-COMPONENT-ROLE-08 · Muster aus AI_AUDITLOG.md · Rollen
NUR aus Evidenz (kein Name→Rolle-Schluss) · keine Architekturentscheidung.*
