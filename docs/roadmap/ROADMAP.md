# Mays-RIS Roadmap (konsolidiert, Stand 2026-10-01)

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
