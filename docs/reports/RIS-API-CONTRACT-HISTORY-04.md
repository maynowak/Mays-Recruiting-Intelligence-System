# RIS-API-CONTRACT-HISTORY-04

STATUS: YELLOW

- Date/Time: 2026-09-28 09:55 UTC
- Branch + HEAD: main, 5b8338a (Vorgänger 5397d90 intakt)
- Scope: Historische Vertragsabsicht read-only (Muster aus AI_AUDITLOG.md). Keine Auswahl A/B/C, keine Änderung
- Sections: OpenAPI-Genese → Absicht → OpenAPI↔Handler → GW-Historie → Handler-Historie → Routen-Matrix → JobSearch-Kapsel → Gegenüberstellung → Kapsel-Urteil
- Findings: s. unten (nur Belegtes; Hypothese als PARTIAL bewertet, nicht entschieden)
- Evidence: `git log --follow/-S/show` (Commits + Diffs, keine Messages-Deutung allein); Boundary-Doku; Test-Greps
- Classification: YELLOW
- Terraform Checks: KEINE (reine Historien-Analyse)
- Git Status: 0 modified, 8 untracked (unberührt); AI_AUDITLOG Template-only (Eintrag als separate Datei)
- Files Changed: nur Report + Execution-Log
- Open Questions: s. unten
- Risks: Keine durch Analyse
- Next Actions: Review; Varianten-Entscheid (A/B/C) erst danach
- Resume Point: Analyse committet (s. Commit)

## 1. OpenAPI-Genese (PROVEN)

Geboren d6ccd09 (11.09., "feat: add JobSearch API contract and reference implementation") MIT Domänen-Paket (models, source_interface, schemas, reference_actor, client, apify_adapter) — von Anfang an Domänen-Vertrag + eigene Laufzeit (localhost:8000, eigene Client-Lib). Einzige Änderung: 29bf860 (Struktur-Fix). NIE: x-amazon-Extensions, Lambda-ARNs, Platform-Routen (`-S`-Suchen leer).

## 2. Absicht (Doku + Commits)

"Contract"-Sprache ab Geburt (Commit-Text: "API contract"). KEINE "spec first/contract first"-Belege, KEINE Kapsel-Terminologie (encapsulation/public-vs-internal nirgends), KEINE OpenAPI-Contract-Tests (Test-"contract" = Agent-Invocation, intern). Boundary-Doku (INTEGRATION_BOUNDARIES B): GW=Routing vs Handler=Logik, "MaysJobsearchApi"-Vertrag — Schichten-Denken ohne OpenAPI-Kapsel-Aussage. Urteil: A (Vertrag) PARTIAL (Wortlaut ja, Kapsel-Architektur nein belegt).

## 3. OpenAPI ↔ Handler

KEINE gemeinsamen Commits (Schnittmenge leer PROVEN). KEINE Ableitung je Richtung belegt (Spec aus Domänen-Paket, Handler aus G0.x-Runtime-Linie). KEINE Contract-Tests Spec↔Handler. Getrennte Entwicklung PROVEN (verschiedene Commits/Zwecke).

## 4. GW-Historie

Payload 2.0 seit G0.1 (d87a48f) — IMMER HTTP-API-v2, KEIN REST→HTTP-Wechsel, KEIN 1.0→2.0-Wechsel. 5 Routen: teils G0.1, teils 5073d84. KEIN Commit stellte Handler auf v2 um (kein Beleg).

## 5. Handler-Historie

`httpMethod`-REST-Modell seit G0.1 (mit GW-v2 koexistent von Beginn an — KEIN Nacheinander, KEIN Umbauversuch). Routen gestaffelt: /me/profile G0.3.1 (748ddf7), /api/agents G0.4 (d0c8abe), /me/jobsearches JobSearch-CRUD (849ae1a). NIE v2-kompatibel, NIE Adapter (`-S routeKey` leer).

## 6. Routen-Matrix

| Route | Handler seit | Gateway seit | OpenAPI seit | Historische Beziehung |
|---|---|---|---|---|
| /health | NIE (404) | G0.1/5073d84 | NIE | Entkoppelt (Grund UNKNOWN) |
| /platform, /me | G0.1-Linie | G0.1-Linie | NIE | Parallel entstanden, nie verbunden |
| /me/profile | G0.3.1 | 5073d84/G0.1 (FRÜHER) | NIE | GW VOR Handler |
| /agents | G0.x-Linie | G0.x-Linie | NIE | Parallel |
| /api/agents/* | G0.4 | NIE | NIE | Handler-only |
| /me/jobsearches* | 849ae1a | NIE | NIE (Spec hat /v1/*) | Domänen-CRUD ohne GW/Spec-Anbindung |
| /v1/jobs/* | — (JobSearch-Repo) | NIE | d6ccd09 | Eigene Kapsel |

## 7. JobSearch-Kapsel (PROVEN separat)

Eigene Domäne (Modelle/Interfaces/Schemas/Adapter/Client), eigene Spec, eigener Server-Port, eigene Tests — KEIN Platform-Anteil außer späterem Handler-CRUD (849ae1a) via JobSearch-Repo. Trennung EXPLIZIT belegt (Verzeichnis-, Commit-, Zweck-Evidenz). Warum unter `jobsearch/`: dort gehört sie hin (Domänen-Paket). Betrieben: via Handler-CRUD lesend/schreibend + eigene Client-Lib; KEINE separate Lambda (PROVEN: nur `agent`).

## 8. Gegenüberstellung

| Ebene | Historische Evidenz | Ergebnis |
|---|---|---|
| OpenAPI Contract | Domänen-Vertrag seit Geburt, 2 Commits, nie AWS/Platform | Eigene Kapsel (PROVEN) |
| Platform API | G0.x-Routen + Doku-Verträge, KEINE Spec | Spec-los (PROVEN) |
| API Gateway | v2 seit G0.1, 5 Routen | Technisch, unverändert |
| Lambda Handler | REST seit G0.1, gestaffelte Routen | Technisch, unverändert |
| SQS Worker | Gleiche Lambda, Mapping | Technisch |

Frage "OpenAPI = eigenständiger Vertrag, GW/Lambda = separate Schicht?": PARTIAL — Kapsel-Realität PROVEN (getrennte Genese/Null-Kopplung/Domänen-Paket), Kapsel-ABSICHT als solche NOT PROVEN (kein Beleg für bewussten Entwurfsakt; House-Style spricht für Evolution, nicht Dekret — als Deutung markiert, nicht Fakt).

## 9. Kapsel-Urteil (Hypothese, NICHT entschieden)

Diagramm-Trennung (Contract vs. Implementation vs. GW/Lambda) beschreibt den IST-Zustand ZUTREFFEND (PROVEN entkoppelt). Ob BEWUSST entworfen: NOT PROVEN. Keine Variante gewählt.

---

*Analyse: RIS-API-CONTRACT-HISTORY-04 · Muster aus AI_AUDITLOG.md · nur Belegtes ·
keine Auswahl · keine Änderung · keine AWS-Mutation.*
