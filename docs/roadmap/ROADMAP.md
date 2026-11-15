# Mays-RIS Roadmap (konsolidiert, Stand 2026-10-01)

## Strategische Roadmap 2026 (Referenzdokument)

| Dokument | Stand | Inhalt | SHA-256 |
|---|---|---|---|
| [`RIS_Agent_Ecosystem_Entwicklungsroadmap_2026.pdf`](RIS_Agent_Ecosystem_Entwicklungsroadmap_2026.pdf) | 2026-11-15 | Vom Auftraggeber bereitgestellte Entwicklungsroadmap (PDF) | `0212667decc460963498669c0be00faffa5eece76b821d69605658f252ed904a` |

Das PDF ist ein **Planungsdokument**, kein Evidenznachweis. Technische Aussagen
gelten nur, wenn sie durch Code, Tests, Pläne oder Reports gedeckt sind
(`docs/reports/`, `docs/AI_AUDITLOG.md`).

Aktueller Deployment-Stand der Mays-Orders-Anbindung:
[`docs/deployment/MAYS-ORDERS-VERSION-RIS-DEV2.md`](../deployment/MAYS-ORDERS-VERSION-RIS-DEV2.md).

## R08 Security-05 status (2026-11-04)

FIX-01 is verified locally with a durable subject fence and DynamoDB atomic
create/erasure admission. Gate B remains NO-GO; live queue, restore, retention,
legal, deployment, and production activation gates remain open.

Keine Termine, keine Priorisierung als „beste Wahl" — technischer
Abhängigkeitsstand. Abgeschlossene Gates werden nicht als offen dargestellt.

## DONE (belegt)

- G0–G0.5: Repository, AWS/TF-Foundation, Testing-Strategie, Agent-API/MO-Boundary, Reference/Runtime
- G2.5–G2.9 + Agent-Reg/Hook: Body/Harness, Worker-Wiring, Invocation, Ecosystem, Registry/Katalog, Event/Envelope, Discovery/Eligibility
- Gate 3: MO live (37/0/0/0) + Kern-E2E
- Gate 4: eigene Orders-Fassade (Decimal-sicher) auf eigener API
- Gate 5: Worker→Body-Runtime (Idempotency/Retry/DLQ-Nutzung, Result)
- Gate 6: OrdersPort + Real-Adapter (Transport-agnostisch, Fehlerklassen)
- Gate 7: ATS Domain Agent (live)
- Gate 8: Multi-Agent (5 Agents, shared Queue) + Installer-Pinning (2 Projekte, SHA-verifiziert)
- Gate 9: JobSearch-Domain (Tabelle + Agent + Tenant-isoliert, live)
- Gates 10–12: Identity-Lifecycle, E-Mail-Verifikation, Profile-v1 (live)
- Gate 13A: Google-Federation-Foundation (YELLOW — konfiguriert, nicht live verifiziert)
- OBS-Foundation: Trail/Dashboard/Alarme live (GREEN)
- Lifecycle-01: Install→Verify→NoOp→Partial→Destroy am Isolationsprojekt (GREEN)
- Documentation Consolidation (dieses Gate)

## CURRENT

- Dokumentations-Konsolidierung (Architektur/Runtime/API/Roadmap/README, Konsistenz-Check).

## NEXT (technisch möglich, keine Reihenfolge-Wertung)

- Gate 13B: sichtbarer Google-Linking-Flow (NICHT begonnen — braucht Test-Account + Redirect-URI)

- JobSearch update/delete als Agent-Caps (Repository kann es bereits)
- ATS-Vertiefung (mehr Capabilities gegen bestehende API)
- Plattform-OpenAPI (Lücke zu /me-/orders-Routen schliessen)
- Installer-Härtung (deterministische Bundles + `package`-Befehl: DONE; CI erstellt weiter keins — OPEN)
- Observability-Ausbau (Dashboards/Alarme über Bestand hinaus)

## OPEN (verstanden, ungelöst)

- POST-Reconciliation nach Timeout; MO-Idempotency-Key fehlt
- nextToken-Roundtrip live; Tenant-Entitlement-Regeln (hart)
- 5 pre-existing Test-Defekte; `api.test.ts`-nahe Frontend-Fragen (fremd)

## DEFERRED (bewusst später)

- MicroVM, API-Keys, Production Rollout, CI/CD-Grossumbau, CV-Vollsystem,
  Matching-Agent, Frontend-Ausbau, Multi-Region.

## NOT PROVEN

- Performance-/Last-Aussagen; Kosten über Leerlauf hinaus; ATS-API-Betrieb
  (Dritt-Deployment) jenseits des getesteten Calls.
