# GATE-2 — Mays-Orders Installation + RIS Handoff-Vertrag

STATUS: YELLOW

- Date/Time: 2026-09-30 14:10 UTC
- Branch + HEAD (RIS): main, 51c0513 · MO-Stand: 9c61237 = Remote-main (Match, clean, KEIN Push)
- Scope: MO-Installation prüfen (read-only, kein Apply) + Handoff-Vertrag (Muster aus AI_AUDITLOG.md). Kein RIS-Umbau, keine AWS-Mutation
- Sections: Baseline → Installer/Checks → Ressourcen/Outputs → Order/Status/SQS/Auth-Verträge → Agent-Pfad → Tests → Security → Handoff
- Findings: s. unten (nur Belegtes)
- Evidence: MO-CLI (Args/Validierung/Plan @ 9c61237), Plan-JSON (37+2), api/endpoints.md, state-machine.md, sqs_handler.py, Tests (81+51), Queue-Policy, Grep-Leeren
- Classification: YELLOW
- Terraform/AWS Checks: KEINE Mutation (validate/plan lesend; KEIN Apply — keine Freigabe)
- Git Status (RIS): 0 modified, 8 untracked (unberührt); AI_AUDITLOG Template-only; MO-Clone ~/.mays-Artefakte NUR /tmp (Repo sauber)
- Files Changed: nur Report + Execution-Log (RIS)
- Open Questions: s. unten
- Risks: Keine durch Gate
- Next Actions: Review; Gate-3-Entscheid SEPARAT (Apply-Freigabe + SQS-Policy-Befund)
- Resume Point: Handoff committet (s. Commit); MO NICHT installiert (bewusst)

## A. Installation Context

MO-Installer: `installer.cli.main` (argparse: --profile/--region/--project-name[u.a.], Commands validate/plan(+destroy)/deploy/destroy/state/output/identity/gui). project_name→Workspace→Isolation (09-Tests). AWS: Profil mayaws / 240571105849 / eu-central-1 (validiert, IDs only).

## B. AWS Context · C. Terraform Context

Validate GREEN (alle Checks, Exit 0). Plan GREEN (37 create + 2 read, Datei in /tmp-Clone). KEIN Apply (keine Freigabe → HARD STOP eingehalten).

## D. Mays-Orders Resources (aus Plan)

API (HTTP API + JWT-Authorizer + Integration + 4 Routen + Stage + Permission), CloudTrail (Trail+S3+Policy+PAB+SSE), Cognito (Pool/Client/staff-Group), DynamoDB (orders-Tabelle), IAM (handler-Rolle+Policy), Lambda (handler + Log-Gruppe), Monitoring (Dashboard + 6 Alarme), SQS (orders-Queue + Policy), SQS-Worker (Rolle/Policy/Function/Mapping/Log).

## E. API Contract

`POST /orders` (201 + `orderId` `ord_*`), `GET /orders/{orderId}`, `PATCH /orders/{orderId}/status`, (Liste). JWT (Cognito-Issuer + Client-Audience). KEIN generischer Agent-Execution-Vertrag.

## F. Order Contract

Erzeugung → `orderId` + PENDING; Status-Lifecycle PENDING→CONFIRMED→PROCESSING→SHIPPED→DELIVERED, CANCELLED aus PENDING/CONFIRMED; Conditional Writes (`attribute_exists` + Status-Guard, 409 bei Konflikt); KEIN Result-Packet/Response-Queue (nur Roadmap-Notiz).

## G. Status Contract

Werte s. oben (6, dokumentiert). Abfrage: GET (Polling); Änderung: PATCH (validiert); Worker: DynamoDB-Update nach Verarbeitung.

## H. SQS / Worker Contract

Queue `mays-orders-orders-queue` (30s Visibility, SSE) → Mapping → Worker-Lambda → DynamoDB-Update. KEIN DLQ (nicht gefunden — Befund).

## I. Authentication Contract

Cognito-Pool + JWT-Authorizer (alle Routen außer ggf. Health-Analog); `staff`-Gruppe; Admin-Create (kein Self-Signup laut Doku).

## J. RIS Integration Handoff

RIS braucht später: API-Endpoint (aus MO-Outputs), orderId-Erzeugung (POST), Status-Abfrage (GET), Status-Änderung (PATCH), Queue/Mapping-Namen, JWT-Felder (Issuer/Audience/staff-Claim). Agent-Pfad: RIS-WorkItem → (HTTP/Call NOCH NICHT VERDRAHTET) → POST /orders → Polling GET → PATCH bei Bedarf. KEIN Push/Callback/Queue-Vertrag vorhanden — Polling als einziger belegter Weg.

## K. Offene Abhängigkeiten

MO NICHT installiert (keine Live-Ressourcen verifiziert); SQS-Policy Principal `*` (Befund, keine Änderung); KEIN DLQ; KEIN Result-Vertrag; KEIN Live-Test.

## L. Entscheidung für nächstes Gate

Gate 3 (bei Freigabe): MO-Apply → Live-Verifikation → RIS-Adapter (OrdersPort→HTTP-Client) als SEPARATER Implementierungs-Gate. KEIN Auto-Start.

## Tests

MO-Installer 81/81 PASS; Lambda-Unit (state/validation/order/index) 51/51 PASS (mit PYTHONPATH=src; ohne = Collection-Error, Doku-Problem, kein Code-Fehler). E2E-Async NICHT ausgeführt (braucht Live-AWS).

## Security / Cost

Befunde (KEINE Änderung): SQS-Policy Principal `*` (Sid suggeriert Account-Scope — Auseinanderfallen dokumentiert); KEINE Secrets im Code (nur Redaktions-Muster); KEINE unnötigen Ressourcen im Plan; State lokal (kein Remote-Backend → kein State-Leak-Risiko, aber auch keine Team-Fähigkeit).

---

*Gate-2: MO-Installation geprüft (NICHT installiert) + Handoff-Vertrag · Muster aus
AI_AUDITLOG.md · keine AWS-Mutation · keine RIS-Änderung.*
