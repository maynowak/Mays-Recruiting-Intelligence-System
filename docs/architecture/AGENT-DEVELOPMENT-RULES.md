# RIS Agenten-Entwicklungsregeln – Correction-14 Baseline

**Stand:** 2026-11-21 · Code/Test auf RIS Feature-Branch nach `f639611` / `6440e53` · **kein Apply**.

**Verbindliche Referenz:** `RIS-MAYS-ORDERS-MODULES.md` / `reference/RIS_Mays_Orders_Modulregister_Correction14.odt` und `../reports/RIS-ANALYSIS-ECOSYSTEM-CORRECTION-14.md`.

## Grundsatz: erst Owner bestimmen

| Thema | Owner | Nicht implementieren in |
|---|---|---|
| ATS, CV/Jobparser, LLM/Matching, Fachresultate | **RIS Domain-Agent** (`ats_agent`, `analysis_agent`, Parser) | Mays-Orders, Ingress |
| Catalog, Registry, Eligibility, Routing, AgentBody | **RIS Ecosystem** | Agent-Sonderlogik / Mays-Orders |
| SQS, Persist+Enqueue, WorkItem, Retry, DLQ, Replay | **RIS Runtime/Ingress/Worker** | ATS/Analysis-Agent |
| ORDER_DISPATCH, ORDER_RESULT, ORDER_FAILED, Signatur | **RIS Transport V1 + Mays Consumer-Contract** | Eigener Agent-Sender |
| Generische Order, Owner, Preise, Billing, Lifecycle, Abruf | **Mays-Orders** | RIS-Agent/Runtime |
| Identity, RIS-Key, APIProfile, Consent, Entitlement | **RIS Partner/Security** | Browser-Metadaten / Agent-Payload |
| Lambda/IAM/SQS Mapping/Deploy | **Infra/Terraform** mit neuer Operator-Freigabe | Nebenwirkung eines Agent-Features |

## Workflow für Modi / Coding-Agenten

1. `AGENTS.md` und `docs/AI_AUDITLOG.md` **vor jedem Schritt** lesen. Das gilt auch für Review-/Explore-Unteragenten.
2. Baseline prüfen: `agentOrder V1`, `Transport V1`, `WorkItem/ProcessingEnvelope`, `AgentBody.process_work`, Result Contracts, Identity/Consent/Entitlement.
3. Den **tatsächlichen Modul-Owner** und Eingangsweg bestimmen: (A) kostenpflichtige Mays-Order mit `agentOrder`, oder (B) autorisierter RIS API Execute. **Beide verwenden die vorhandene Work-SQS/Worker-Runtime** (nach freigegebenem Correction-14-Apply).
4. Nur Domain-Logik im Domain-Agent implementieren. Für generische Infrastrukturfehler ein **eigenes kleines Ecosystem-Arbeitspaket**; für Preis/Lifecycle ein **getrenntes Mays-Orders-Arbeitspaket**.
5. Keine neue Queue, keine zweite Order-State-Machine, keine neue Result-Transportfamilie, keine agenteneigene Retry-/DLQ-Logik.
6. Tests: Addition-Agent als Baseline, neuer Domain-Agent, ORDER_RESULT/FAILED, Queue-Redelivery/Replay, Entitlement-Revoke, Tenant/Fence und Mays-Consumer-Contract. Keine verteilte Exactly-once-Garantie behaupten.
7. Tests → Auditlog → Commit → Push **nach jedem abgeschlossenen Schritt**, Feature-Branch. Kein Main-Merge/Production-Deploy ohne Auftrag.
8. Terraform: ausschließlich read-only Plan, manifestierte Ressourcen und Hashes, State Serial/Lineage, `NO_SHARED_DESTROY`. **Keine AWS-Mutation ohne ausdrückliche exakte Operator-Freigabe.**

## Wichtiges Release-Gate

**Correction-14 ist vorbereitet, nicht deployed:** Plan **4 add / 3 change / 0 destroy**, SHA256 `4a0a02f5a9bd7f16a1295d046798c314a9faac8425e2864d02ec442ed304d033` ist **nicht freigegeben**. Separate synthetische Env-/Consent-Freigabe fehlt. SQS-DLQ-Erschöpfung sendet **noch kein** `ORDER_FAILED` (kein Consumer). Kein realer Nutzerbetrieb.

## Prompt-Baustein für neue ATS-Agenten

> Entwickle ausschließlich die fachliche ATS-Logik innerhalb des bestehenden RIS Domain-Agent-Contracts. Vorher Owner/Contracts, `AGENTS.md`, Auditlog und das Modulregister Correction-14 lesen. Nutze bestehende Registry/Eligibility/AgentBody, gemeinsame Work-SQS/Worker, Result-Transport V1 und Partner-Security unverändert. Identifiziere Querschnittsprobleme als **separate RIS Ecosystem-Aufgabe**, Order-/Preisprobleme als **separate Mays-Orders-Aufgabe**. Kein Terraform Apply, keine neue Queue, kein paralleler Lifecycle, keine echten Daten. Nach jedem Schritt Tests → Auditlog → Commit → Push.

