# RIS-ATS-AGENT-01 — ORCH-00 Baseline und Konfliktmatrix

**Datum:** 2026-11-15
**Gate:** ORCH-00 (Baseline / Audit)
**Branch:** `feature/ris-dev2-ats-agent-pinned-core-01`
**Basis:** `main` = `ae08267c3871d7bb85b7aa7ed2aed07a75385584`
**Modus:** read-only Untersuchung; keine AWS-/Jobsearch-Mutation, kein Merge, kein Push.

---

## 1. Git-Baseline

| Element | Wert |
|---|---|
| Ausgangsbranch | `feature/ris-mo-addition-agent-e2e-01` (sauber, gepusht) |
| `main` (lokal + `origin/main`) | `ae08267` — Merge A04–A07 |
| Neuer Branch | `feature/ris-dev2-ats-agent-pinned-core-01` von `main` |
| Working Tree | sauber |
| Planungsdokument | `docs/roadmap/RIS_ATS_AGENT_ORCHESTRIERTER_PROMPTPLAN_2026-11-15.md` (SHA-256 `770f5135…1bdf0`) |

Der Plan nennt als RIS-Baseline `ae08267c3871d7bb85b7aa7ed2aed07a75385584`.
Das stimmt mit dem tatsächlichen `main` überein.

---

## 2. Bestehender ATS-Agent (wird wiederverwendet, nicht neu gebaut)

| Eigenschaft | Ist-Wert | Quelle |
|---|---|---|
| Registry-Identifier | `ats-agent` | `agents/ats_agent/registry.py` |
| Anzeigename | `ATS Agent` | dito |
| Version | `1.0.0` | dito |
| Capability | `analyze.job` | dito |
| Work Type | `ats_process` | dito |
| Supported Bodies | `1.0.0` | dito |
| Runtime | `python3.14` | dito |
| Execution Profile | `LAMBDA` | dito |
| Risk Level | `low` | dito |
| Implementierung | `ATSAgent(AgentBase)` | `agents/ats_agent/agent.py` |
| Aktueller Datenpfad | HTTP POST `/api/ats-analysis` gegen `ATS_API_BASE_URL` (Default `https://mays-jobsearch.vercel.app`) | `ATSHttpClient` |
| Transport-Fallback | `httpx` → `requests` → stdlib `urllib` | dito |
| Lambda-Factory | `create_ats_handler()` / `lambda_handler` | dito |

**Wichtige Einschränkung:** Der Agent enthält heute **keine ATS-Fachlogik**. Er
delegiert an einen veränderlichen HTTP-Dienst. Genau das ist der Gegenstand von
ORCH-02/ORCH-03.

### Runtime-Wiring

`agents/runtime/pipeline.py` registriert den Agenten bereits:

```python
if not registry.is_registered("ats-agent"):
    registry.register("ats-agent", get_ats_descriptor())
body.register_agent(work_type=ATS_WORK_TYPE, handler=ats.process_work)
body.register_agent(capability=ATS_ANALYZE_CAPABILITY, handler=ats.process_work)
body.register_agent(agent_id="ats-agent", handler=ats.process_work)
```

Es gibt **keinen zweiten Registrierungspfad** und keinen eigenen SQS-Transport
für ATS. Das bleibt so.

---

## 3. Wiederverwendete, bereits verifizierte Bausteine

| Baustein | Status | Vorgabe für dieses Gate |
|---|---|---|
| Agent Registry / Discovery / Eligibility | vorhanden | nicht neu bauen |
| AgentBody / WorkItem / Routing | vorhanden | unverändert nutzen |
| Generic Order Transport V1 | vorhanden (A05) | unverändert |
| OrdersPort / Real-Adapter | vorhanden (Gate 6) | unverändert |
| `agentOrder` V1 (A04, Ownership, A06) | vorhanden | unverändert |
| `addition_agent` (`math.add`) | vorhanden | Regressionsfall, **nicht ändern** |
| `ats_agent` | vorhanden | erweitern, **nicht duplizieren** |

A04–A07 und Gate 7 gelten ausdrücklich als **bereits verifiziert** und werden
nicht erneut entworfen.

---

## 4. Konfliktmatrix

| Datei / Bereich | Risiko | Regel |
|---|---|---|
| `agents/ats_agent/agent.py` | HTTP-Aufruf muss durch lokalen Core-Adapter ersetzt/ergänzt werden | bestehende Klasse und Vertrag behalten; kein Parallel-Agent |
| `agents/ats_agent/registry.py` | Descriptor-Änderung könnte Clients brechen | `ats-agent` + `analyze.job` bleiben; Capability-Erweiterung nur nach Kompatibilitätsprüfung |
| `agents/runtime/pipeline.py` | doppelte Registrierung | bestehende Zeilen nutzen; keine zweite Registrierung |
| `agents/orders/*` | versehentliche Änderung | **nicht anfassen** |
| `agents/addition_agent/*` | Regression | **nicht ändern** |
| `installer/mays-jobsearch-clone.pinned.json` | Verwechslung mit ATS-Paket-Pin | historischer Referenzpin `29d8b730…`; **nicht umdeuten oder überschreiben** |
| `tests/test_ats_domain_agent.py` | Bruch des HTTP-Vertragstests | bei Adapterwechsel bewusst anpassen, nicht löschen |
| `tests/test_jobsearch_agent.py` | dito | dito |
| Jobsearch-Repository | Mutation | **read-only**; keine Branches/Tags/Commits/Patches |

---

## 5. Testbaseline (vor jeder Änderung)

```text
python -m pytest tests/test_ats_domain_agent.py tests/test_jobsearch_agent.py -q
13 passed
```

Reproduzierbar auf `main` = `ae08267` und auf dem neuen Branch (identischer
Stand, noch keine Änderung).

---

## 6. Harte Grenzen dieses Auftrags

- Keine AWS-/Terraform-Apply-, Deploy-, Cognito-, CloudFront- oder DNS-Aktion.
- `ris-dev2` ist eine Projektkonfiguration, **keine** als live anzunehmende
  Installation.
- Jobsearch ist vollständig read-only.
- Kein Merge und kein Push ohne gesonderten Auftrag.
- Keine erfundenen Testergebnisse; jede Aussage braucht ein Kommando oder einen
  Dateiverweis.
- KI-Funktion bleibt standardmäßig deaktiviert.

---

## 7. Offene Entscheidungen (Default aus dem Plan)

| Thema | Default |
|---|---|
| Tag im Jobsearch-Repo | keiner; RIS-eigener voller Source-SHA + Artefakt-SHA |
| PDF-/DOCX-Eingang | nur mit nachgewiesenem separaten Parser; nicht als vorhanden ausgeben |
| KI | deaktiviert, externer Provider nur unter eigenem Consent-/Security-Gate |
| Release | lokale Integration; kein AWS Apply/Deploy, kein Merge |

---

## 8. Nächster Schritt

**ORCH-01** — aktuellen Jobsearch-ATS-Stand read-only abholen:

- frischer `fetch` (der Plan-SHA `a5640d12…` ist nur Planungsbaseline),
- `api/ats-analysis.mjs`, `api/_lib/ats.mjs`, `api/_lib/filter.mjs` und
  transitive Imports,
- Tests, Fixtures, UI-Felder,
- Import-/Field-Matrix und Abweichungen zum historischen Pin `29d8b730…`.

**Status: ORCH-00 COMPLETE.** Kein Push.
