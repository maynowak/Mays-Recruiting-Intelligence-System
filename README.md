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
  (eigener Pfad, live über den Modul-Builder), ATS/JobSearch/Reference-Auswahl
  (live), Installer-Pinning (mays-orders@9c61237, mays_jobsearch@3cd58b81),
  Tabellen/Queues/Mapping.
- dauerhafte Dev-Installation: `ris-dev` (Workspace `ris-dev`,
  Komponenten `ris-dev-mays-orders*`); Verifikation
  `./scripts/parallel_tests.sh ris-dev` = 64 PASS / 0 FAIL.
- prepared: JobSearch update/delete, ATS-Vertiefung, ats/cv/match-Queues,
  Jobsearch-Login E2E (Phase 2/3 offen: OAuth-Callback/PKCE, DNS
  `auth.mays-job-matcher.app`, CORS).
- open: POST-Reconciliation, MO-Idempotency-Key, Full-Plan-`lambda.zip`,
  Plattform-OpenAPI, `installer.ris`-Phasen (`--through`), 5 pre-existing
  Test-Defekte.
- Suite: pytest 1593 passed, 2 failed (dokumentierte Baseline-Defekte), 3 skipped.

## Installer / AWS / Security

- `python -m installer.ris --project-name <p> --environment dev --profile mayaws {validate,plan,apply,preflight,install,state}`
- Profil = Installationskontext (kein fester Account); Workspace = project_name;
  Backend S3 + Lock; Pins je Projekt (s. `installer/*-clone.pinned.json`).
  Für lokale Läufe gegen `ris-dev`: `TF_DATA_DIR=/tmp/tfris-dev`.
- JWT (Cognito — zentraler Identity Provider), Tenant-Isolation im Code,
  Least-Privilege-Rollen, keine Secrets im Repo. E-Mail/Passwort ist der
  Hauptweg; Google Federation ist optional vorbereitet (Standard AUS, kein
  separates Backend-Auth-System, Backend nutzt weiter Cognito JWTs).
  UserProfile ist eigene Persistence (Google-Login erzeugt keins);
  Account Linking vorbereitet, aber nicht aktiviert; Live-Google-E2E offen.
  Bekannte Fremd-OPENs: SQS-`*`, MO ohne DLQ (dokumentiert).

## Mays-Orders: Modul-Builder statt Installer-Phasen (Parallel-Entwicklung)

Der Mays-Orders-Terraform-Baustein wird nicht mehr über den (noch unfertigen)
phasenweisen `installer.ris install --through`-Weg integriert, sondern über den
**Modul-Builder-Wrapper**. Damit sind RIS und Mays-Orders entkoppelt und können
parallel entwickelt werden — der fremde Stack wird pro Build frisch aus
`mays-order-aws` gezogen, das RIS verdrahtet nur die generierten Outputs.

```bash
# Modul bauen/erneuern (zieht mays-order-aws, erzeugt terraform/modules/mays_orders)
python -m installer.build_mays_orders_module --project-name ris-dev --force

# Nur prüfen (Modul da, sqs_queue_name, Component-Naming, plan-bekanntes SQS-Gate, validate)
python -m installer.build_mays_orders_module --check

# Generiertes Modul entfernen (Build-Artefakt, nicht versioniert)
python -m installer.build_mays_orders_module --clean
```

- Der Wrapper läuft nach **jedem** Build `patch_iam_sqs_gate()`: das SQS-Gate ist
  ein **plan-bekanntes** `count = var.sqs_enabled ? 1 : 0`, die Queue-ARN bleibt
  das Policy-Resource. Bricht die Upstream-Quelle das Muster, schlägt der Build
  laut fehl statt ein unplanbares Modul zu schreiben.
- `terraform/modules/mays_orders/` ist ein **Build-Artefakt** (gitignored); die
  versionierten Teile sind Wrapper, README und Ausführungsreport.
- Details: `installer/README_MODULE_BUILDER.md`,
  `docs/reports/02-01-WRAPPER-MAYS-ORDERS-MODULE-BUILDER-EXECUTION-LOG.md`.

> Hinweis: `installer.ris` ist in Arbeit (phasenweises `--through` noch nicht
> aktiv). Das blockiert die Orders-Integration **nicht** — der Modul-Builder ist
> der abgesicherte Weg und erlaubt parallele Entwicklung.

## Doku-Struktur / Reports

`docs/architecture/`, `docs/api/`, `docs/ecosystem/`, `docs/roadmap/ROADMAP.md`,
`docs/reports/` (Gate-Nachweise G0–G9 + Execution-Logs, bleiben erhalten).
Ältere Architektur-Docs sind Historie — im Zweifel gelten Code + die drei
kanonischen Dateien oben.
