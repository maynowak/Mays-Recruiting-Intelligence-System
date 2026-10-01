# GATE-8 — Multi-Agent Ecosystem + Installer Project Version Pinning

STATUS: GREEN

- Date/Time: 2026-10-01 19:40 UTC
- Branch + HEAD (RIS): main, 0626ff2 + Gate-8-Aenderungen (s. R)
- MO-Stand: 0 Aenderungen. Gates 5–7 unangetastet (nur Pipeline-Bootstrap + Return-Feld).
- Scope: Multi-Agent (Reference/ATS/Dummy-A/Dummy-B, shared Queue) + Installer-Projektmodell mit Git-SHA-Pinning (mays_jobsearch etabliert). Keine neuen Queues/DLQs/Retry-Systeme, kein Foundation-Apply.
- Sections: A–S unten
- Findings: 4 Agents gleichzeitig registriert/entdeckt/selektiert (live je korrekt); Pinning pro Projekt mit verifiziertem SHA; Duplikat/Isolation live belegt
- Evidence: 14 Unit-Tests (5 Pinning + 9 Multi), DDB-Items, Worker-Logs, Pin-Dateien, TF-State
- Classification: GREEN
- Terraform/AWS Checks: keine TF-Aenderung (nur Lambda-Code-Update per Mechanismus); 0 destroys
- Git Status (RIS): nur Gate-8-Dateien (s. R); Clones ignoriert, Pins getrackt
- Files Changed: `installer/orchestrator.py` (Projekte + Pinning), `installer/mays-jobsearch-clone.pinned.json` (neu), `agents/dummy/` (neu), `agents/runtime/pipeline.py` (Bootstrap + result_reference), `tests/test_project_pinning.py` + `test_multi_agent_ecosystem.py` (neu), Reports
- Open Questions: Jobsearch-Remote-HEAD driftet ggf. (Pin+Verify dafuer da); ATS-Live diesmal optional genutzt (1 Run ok)
- Risks: keine neuen (Dummy DEV-markiert, synthetische Daten, keine Secrets)
- Next Actions: Commit → Folgestufen
- Resume Point: nach Commit HARD STOP

## A. Ausgangslage

Gate 7 GREEN. `installer/projects/` enthielt nur `mays_orders`-Clone; `mays_jobsearch` existierte NICHT (Auftrag-Annahme korrigiert: etabliert statt vorgefunden). Ecosystem kannte 3 Agents (reference/orders/ats).

## B. Mays-Orders Installer Referenz

MO-Installer (read-only gelesen, fremder Code unberuehrt): `DeploymentId` (account:project:environment) + `PlanMetadata.git_commit` als JSON neben Plan-Artefakten + Run-Verzeichnisse mit Context. Referenzverhalten: beweglicher Branch ≠ Nachweis; aufgeloester SHA wird persistiert. Uebernommen: Pin-Datensatz + Verifikation, eigene Feldnamen laut bestehendem RIS-Pin-Schema.

## C. mays_jobsearch Projektmodell

Remote `git@github.com:maynowak/mays-jobsearch.git` (HEAD `3cd58b8`), frisch geklont nach `installer/projects/mays_jobsearch` (clean, ignoriert). Befund: Frontend-Projekt (Vite/Node) — KEIN installer/, KEIN terraform/ → `kind: reference` (reine Versionsreferenz, kein TF-/Workspace-Kontext). Isolation: eigenes Verzeichnis, eigene Pin-Datei, keine Vermischung mit mays-orders/RIS.

## D. Git Pinning

`installer/orchestrator.py`: PROJECTS (+`local_dir`, `kind`, `.get()`-Sicherung Bestand), `pin_filename/pin_path/project_local_dir`, `resolve_remote_sha` (ls-remote), `local_head_sha`, `build_pin_record` (RIS-Pin-Schema), `write_pin`, `verify_pin` (Drift-Erkennung). Kein zweites Parallelsystem (bestehende Modelle erweitert).

## E. Installer Version Evidence

- `installer/mays-jobsearch-clone.pinned.json`: 3cd58b8 (= Remote-HEAD, verifiziert).
- `installer/mays-orders-clone.pinned.json`: 9c61… (re-verifiziert True).
- Pin-Dateien getrackt (ausserhalb ignorierter Pfade — check-ignore belegt), Clones ignoriert.

## F.–I. Registry/Discovery/Eligibility/Selection

5 Agents registriert (reference, orders_function, ats-agent, dummy-a, dummy-b). Discovery liefert Mehrheiten (alle ACTIVE); Eligibility filtert (RETiRED→0/1 belegt); Selection first_match pro Capability (A–E Unit + live belegt). Discovery≠Selection dokumentiert/belegt.

## J. Dummy Agents

`agents/dummy/agents.py` (DEV/TEST ONLY): DummyAgentA/B (AgentBase, Marker+Echo, keine API/AWS/MO). Registrierung via `register_dummy_agents` im Pipeline-Bootstrap.

## K. Multi-Agent Tests

`tests/test_multi_agent_ecosystem.py` (9): 5-fach-Registrierung, Discovery-Mehrheit, Routing A–E (unbekannt→ValueError ohne Registrierung), Shared-Queue-Simulation (3 Items→je richtiger Agent), Duplikat. `tests/test_project_pinning.py` (5): Definition/Pfade, Resolve+Write, Verify+Drift, Repeatability+Isolation, Unknown-Reject. **14/14 PASS**.

## L. Idempotency

Gate-5-Mechanik unveraendert; pro Agent belegt (Unit + live gate8-a-Duplikat: attempt konstant, Log "kein neuer AgentRun"). Auswahl fuehrt bei Duplikat zu keinem Processing.

## M. Result Isolation

Referenzen `work:<id>:attempt:1` je Agent disjunkt; Processing-IDs disjunkt; Results agent-markiert (`processed_by`, Order-/Echo-/ATS-Daten) — keine Vermischung (live ausgelesen).

## N. Live E2E

Bundle `BhSS9b8f…` (Active). 4 Nachrichten, shared Queue: gate8-a→dummy-a, gate8-b→dummy-b, gate8-r→reference_agent, gate8-c→ats-agent (mit echter Analysis) — alle COMPLETED attempt 1, Queue 0. ≥2 Agenten (4) nachgewiesen. Sequenziell (Batch 5 erlaubt Parallelitaet; dokumentiert ausreichend, keine neue Infra).

## O. Security

Keine Secrets/Credentials/Tokens/PII (synthetische Proben, Shred n/a — nichts erzeugt ausser DDB-Test-Items, geloescht). Repository-URLs/SHAs oeffentlich dokumentierbar. Installer-Metadaten ohne Credentials.

## P. Regression

Suite **316 passed** (302 + 14 neu); 4 pre-existing Deselected + 1 Collection (klassifiziert, unveraendert). Gate-5/6/7-Tests alle gruen (Pipeline/Adapter/Reader/ATS).

## Q. Mays-Orders unchanged

Keine Beruehrung (kein TF/State/Lambda/SQS-Kontakt; Clone read-only + clean).

## R. Git

M: `installer/orchestrator.py`, `agents/runtime/pipeline.py`. Neu: `installer/mays-jobsearch-clone.pinned.json`, `agents/dummy/`, `tests/test_project_pinning.py`, `tests/test_multi_agent_ecosystem.py`, Reports. Secret-Scan sauber; Zips /tmp (entfernt).

## S. Gate Decision

| Bereich | Ergebnis |
|---|---|
| Mays-Orders Installer Reference | GREEN |
| mays_jobsearch Project Model | GREEN |
| Git Repository Resolution | GREEN |
| Git SHA Pinning | GREEN |
| Version Persistence | GREEN |
| Project Isolation | GREEN |
| Agent Registry | GREEN |
| Multi-Agent Registration | GREEN |
| Discovery | GREEN |
| Eligibility | GREEN |
| Selection | GREEN |
| Dummy Agent A / B | GREEN / GREEN |
| Reference Agent | GREEN |
| ATS Agent | GREEN |
| Shared Work Queue | GREEN |
| Parallel / Multi-WorkItem | GREEN (sequenziell dokumentiert) |
| Idempotency / Retry | GREEN / GREEN |
| Result Isolation | GREEN |
| Live E2E | GREEN |
| Security | GREEN |
| Gate-5/6/7 Regression | GREEN / GREEN / GREEN |
| Mays-Orders unchanged | GREEN |
| Git | GREEN |

**Entscheidung: GREEN** — Multi-Agent live mit 4 Agents auf shared Queue; Pinning mit verifiziertem SHA je Projekt; Isolation/Idempotency belegt.

- Report: `docs/reports/GATE-8-MULTI-AGENT-ECOSYSTEM-INSTALLER-PINNING-01.md` (+ Log folgt)
- Commit: folgt
- Offen: Remote-HEAD-Drift (Verify deckt ab); ATS-Live optional
- Nächste Stufe: Domain-Ausbau/Production-Vorbereitung (Empfehlung)

**DANN HARD STOP.**
