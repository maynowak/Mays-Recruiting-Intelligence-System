# Mays Recruiting Intelligence System (Mays-RIS)

Agent-Runtime-Plattform (AWS, eu-central-1): SQS → Worker → Ecosystem
(Registry/Discovery/Eligibility/Selection) → Agent Body → Domain Agents →
Result. Mays-Orders ist eine externe Systemgrenze (eigener Stack, eigenes
Team), angebunden über OrdersPort → RealMaysOrdersAdapter → HTTP.

## Architektur (Kurz)

```text
User → Cognito/JWT → API-GW (9 Routen: /health /platform /me /me/profile
/agents + GET/POST /orders, GET/PATCH /orders/{id}) → Lambdas
API → WorkItem → Shared Work Queue (+DLQ, 3 Empfänge) → Worker-Lambda
→ Ecosystem → Body → Agents (reference, ats, jobsearch, orders-function,
dummy-a/b DEV) → DynamoDB (work-items, jobsearches, profile, catalog,
entitlements, agent-state)
```

Details: `docs/architecture/SYSTEM-ARCHITECTURE.md` (maßgeblich),
`docs/architecture/RUNTIME-PATH.md`, `docs/api/API-STANDARD.md`.

## Stand (ehrlich)

- implemented + verified: Runtime-Pfad, Idempotency/Retry/DLQ, Orders-Integration
  (eigener Pfad, live), ATS/JobSearch/Reference-Auswahl (live), Installer-Pinning
  (mays-orders@9c61237, mays_jobsearch@3cd58b81), Tabellen/Queues/Mapping.
- prepared: JobSearch update/delete, ATS-Vertiefung, ats/cv/match-Queues.
- open: POST-Reconciliation, MO-Idempotency-Key, Full-Plan-`lambda.zip`,
  Plattform-OpenAPI, 5 pre-existing Test-Defekte.
- Suite: 321 passed (4 deselected, 1 Collection — klassifiziert).

## Installer / AWS / Security

- `python -m installer.ris --project-name mays-ris --environment dev --profile mayaws {validate,plan,apply,preflight,install,state}`
- Profil = Installationskontext (kein fester Account); Workspace = project_name;
  Backend S3 + Lock; Pins je Projekt (s. `installer/*-clone.pinned.json`).
- JWT (Cognito), Tenant-Isolation im Code, Least-Privilege-Rollen, keine
  Secrets im Repo. Bekannte Fremd-OPENs: SQS-`*`, MO ohne DLQ (dokumentiert).

## Doku-Struktur / Reports

`docs/architecture/`, `docs/api/`, `docs/ecosystem/`, `docs/roadmap/ROADMAP.md`,
`docs/reports/` (Gate-Nachweise G0–G9 + Execution-Logs, bleiben erhalten).
Ältere Architektur-Docs sind Historie — im Zweifel gelten Code + die drei
kanonischen Dateien oben.
