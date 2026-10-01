# GATE-7 — ATS Domain Agent (erster echter Domain Agent)

STATUS: GREEN

- Date/Time: 2026-10-01 18:55 UTC
- Branch + HEAD (RIS): main, 8cf454a + Gate-7-Aenderungen (s. P)
- MO-Stand: 0 Aenderungen. Gate 5/6 unangetastet (nur Pipeline-Bootstrap + 1 Agent-Zeile).
- Scope: ATS als Domain Agent registrieren + live nachweisen. Kein Runtime-Umbau, kein Domain-Ausbau, keine OrdersPort-Nutzung (Use-Case braucht keinen Order-Aufruf → NOT USED).
- Sections: A–Q unten
- Findings: ATS live COMPLETED (Attempt 1) mit echter API-Analysis; Duplikat/Negativ/Retry-Mechanik intakt; 2 minimale Befunde live behoben (urllib-Fallback, Payload-Wrap)
- Evidence: 9 Unit-Tests + 20 ATS-Bestand, DDB-Items, Worker-Logs, Bundle-SHA
- Classification: GREEN
- Terraform/AWS Checks: keine TF-Aenderung (nur Lambda-Code-Update per bestehendem Mechanismus); 0 destroys
- Git Status (RIS): nur Gate-7-Dateien (s. P)
- Files Changed: `agents/ats_agent/agent.py` (Fallback + Wrap-Norm), `agents/runtime/pipeline.py` (ATS-Registrierung), `tests/test_ats_domain_agent.py` (neu), Reports
- Open Questions: mjs-Referenzen existieren nicht (Code massgeblich); externer API-Betrieb (Dritt-Deployment)
- Risks: keine neuen (synthetische Daten, keine PII, keine Secrets)
- Next Actions: Commit → Folgetore
- Resume Point: nach Commit HARD STOP

## A. ATS-Bestand

- KEIN `api/_lib/ats.mjs`, KEINE `extractRequirements*`/`matchRequirement`/`analyzeJobForAts`/`generateCVRecommendations` (grep-leer — Auftrag-Referenzen veraltet, Code massgeblich).
- Real: `agents/ats_agent/agent.py` (ATSAgent/AgentBase + ATSHttpClient httpx→requests, Capability `analyze.job`, Validierung job-Pflicht), `registry.py` (Descriptor `ats-agent`/ACTIVE + register-Funktionen), 20 Tests gruen.
- A: Delegations-Integration an externe ATS-API. B: produktionsfaehig (Contract/Validierung/Fehler). C: kein toter Code. D: Input `payload.job` (+optional `profile`). E: Output `{success, data:{analysis, jobTitle, candidateSkills}, metrics}`. F: via Descriptor + Body-Route. G: fehlte Bootstrap-Registrierung + Lambda-Transport + Wrap-Norm.

## B. Domain-Agent Contract

AgentBase (process_work/validate/get_status) + Ecosystem-Descriptor. ATS uebernimmt KEINE Runtime-Verantwortung (kein SQS/Retry/DLQ/Auswahl/Infra im Agent).

## C. Registration

Bestehende `get_ats_descriptor()`/`register_ats_agent()` wiederverwendet + Body-Routen (work_type/capability/agent_id) im Pipeline-Bootstrap. Kein zweites Registry-Modell. Felder: ats-agent/1.0.0/ACTIVE/analyze.job/low/LAMBDA/python3.14 — alle im Modell vorhanden, keine Erweiterung noetig.

## D. Discovery

`analyze.job` → [`ats-agent`] (ACTIVE); `reference.echo` → [`reference_agent`] (live + Unit belegt). Kein implizites Ueberschreiben (get_routes enthaelt beide).

## E. Eligibility

ACTIVE + Capability + Body/Runtime via bestehende Pipeline. Negativ: RETIRED-Deskriptor → 0 eligible/1 rejected (Unit). Tenant/Entitlement: keine harten Regeln im Modell (zukuenftig).

## F. Input Contract

`payload.job{title, description}` (+optional `profile{}`), WorkItem-Pflichtfelder via Gate-5-Validierung. Engine-Wrap (`payload.payload`) wird eine Ebene entpackt (Muster Gate 6, live belegt).

## G. ATS Processing

Agent → ( Stub/Real-Client ) → externe Analyse → Result. Transport erg.: urllib-Fallback (Lambda hat httpx/requests nicht sicher). Fachlogik unveraendert.

## H. Result Contract

Body-kompatibel (success/data/metrics, Fehler `ATSAPIError`-typisiert). Live persistiert: jobTitle/candidateSkills/analysis (matches/confidence) + result_reference. Kein zweiter Result-Typ.

## I. OrdersPort-Verwendung

NOT USED — Use-Case braucht keinen Order-Aufruf (Auftrag: nicht kuenstlich einbauen).

## J. Idempotency

Gate-5-Mechanik (Conditional Write). Live-Duplikat: kein neuer Run (Log + attempt konstant).

## K. Retry

Neuer Attempt bei Redelivery (Unit fail-once + Gate-5-Live 1→2→3 als Beleg der Mechanik). ATS ohne eigene Schleife.

## L. Negative Tests

Unit: Non-ATS→Reference, Invalid→ValueError/keine Registrierung, No-Agent→ValueError, Duplicate, Retired-Eligibility. Live: Non-ATS→reference_agent COMPLETED; Duplikat→kein Run.

## M. Live E2E

Bundle `SvyMjR…` (agents+jobsearch+handler). SQS `gate7-e2e-001` (synthetisch, kein PII) → Worker → `Selected agent ats-agent` → externe API (200) → COMPLETED attempt 1 + Referenz. Tabelle danach leer (Items geloescht). Keine Cognito-/Secrets-Artefakte (Pfad braucht keine Auth).

## N. Security / PII

Synthetische Jobdaten (erfundener Titel, leeres Profil); Logs: nur workId/capability/Titel (synthetisch); keine Secrets/Credentials/Tokens im Pfad; keine PII-Persistenz ausser Test-Item (geloescht).

## O. Regression

Suite **302 passed** (293 + 9 neu); 4 pre-existing Deselected + 1 Collection (klassifiziert Gate 5, unveraendert). Gate 5/6: Pipeline-/Adapter-/Reader-Tests alle gruen; Diffs minimal.

## P. Git

M: `agents/ats_agent/agent.py`, `agents/runtime/pipeline.py`. Neu: `tests/test_ats_domain_agent.py`, Reports. Secret-Scan sauber; Bundle in /tmp (entfernt); Clone unberuehrt.

## Q. Gate Decision

| Bereich | Ergebnis |
|---|---|
| ATS Existing Logic | GREEN |
| ATS Agent | GREEN |
| Agent Registration | GREEN |
| Discovery | GREEN |
| Eligibility | GREEN |
| Input Contract | GREEN |
| ATS Processing | GREEN |
| Result Contract | GREEN |
| OrdersPort | NOT USED |
| Idempotency | GREEN |
| Retry | GREEN |
| Negative Tests | GREEN |
| Live E2E | GREEN |
| Security / PII | GREEN |
| Gate-5 Regression | GREEN |
| Gate-6 Regression | GREEN |
| Test Suite | GREEN |
| Mays-Orders unchanged | GREEN |
| Git | GREEN |

**Entscheidung: GREEN** — erster echter Domain Agent live integriert; Ecosystem unterscheidet Reference/ATS; Mechanik intakt; MO unverändert.

- Report: `docs/reports/GATE-7-ATS-DOMAIN-AGENT-01.md` (+ Log folgt)
- Commit: folgt
- Offen: mjs-Diskrepanz (Doku); Fremd-API-Betrieb; pre-existing Defekte
- Nächstes Gate: Domain-Ausbau nach Bedarf (Empfehlung)

**DANN HARD STOP.**
