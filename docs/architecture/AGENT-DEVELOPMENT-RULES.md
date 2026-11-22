# RIS Agenten-Entwicklungsregeln – Correction-14 Baseline

**Stand:** Correction-14 Architektur vom 2026-11-21; aktualisierter Infrastruktur-/QA-Verifikationsstand 2026-11-22 (`550090e`). Das historische Baseline-Dokument entstand vor 16C2 Apply A.

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

**16C2 Apply A AWS INFRA VERIFIED:** Der spätere, gesondert genehmigte Plan SHA-256 `7393445789d92bdb15ebcc9ea3ae85a9e98cb068c27ad84bc6fd982d3ba0f64a` wurde am 2026-11-22 angewendet: **4 add / 3 change / 0 destroy**, State **67 → 69**. Der ältere Correction-14-Plan `4a0a02f5...` blieb ein historischer Preflight, nicht der ausgeführte Apply. Analysis-/Parser-Lambda und Worker-/Ingress-Bindungen sind installiert, deny-by-default. Gate **B** (synthetische Identität/Entitlement/Consent), **C** (Mays-Orders `apiProfileRef`-Owner-/Partner-Bindung), Legal/Catalog/Produktaktivierung bleiben gesperrt. SQS-DLQ-Erschöpfung sendet noch kein terminales `ORDER_FAILED`. **Keine Analysis Live-E2E-Abnahme oder Freigabe echter Nutzer**. Belege: `docs/reports/RIS-ANALYSIS-16C2-APPLY-REGRESSION.md`, `docs/reports/RIS-ANALYSIS-16C2-QA2-MODULE-CONTRACT.md`.

## Prompt-Baustein für neue ATS-Agenten

> Entwickle ausschließlich die fachliche ATS-Logik innerhalb des bestehenden RIS Domain-Agent-Contracts. Vorher Owner/Contracts, `AGENTS.md`, Auditlog und das Modulregister Correction-14 lesen. Nutze bestehende Registry/Eligibility/AgentBody, gemeinsame Work-SQS/Worker, Result-Transport V1 und Partner-Security unverändert. Identifiziere Querschnittsprobleme als **separate RIS Ecosystem-Aufgabe**, Order-/Preisprobleme als **separate Mays-Orders-Aufgabe**. Kein Terraform Apply, keine neue Queue, kein paralleler Lifecycle, keine echten Daten. Nach jedem Schritt Tests → Auditlog → Commit → Push.

