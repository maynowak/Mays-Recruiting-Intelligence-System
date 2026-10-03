# RIS-OBSERVABILITY-FOUNDATION-01 — CloudTrail + CloudWatch

STATUS: GREEN

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, 02f1584 + OBS-Änderungen (s. Git)
- MO-Stand: 0 Änderungen (nur gelesen: Module/Pattern/States als Referenz).
- Scope: CloudTrail-Audit + CloudWatch-Runtime als TF-verwaltete Foundation (Dashboard/Alarme/Trail/S3). Keine Agent-Metriken, kein SNS, kein Versioning/Lifecycle (nicht in Referenz), kein State-Umbau.
- Classification: GREEN (alle Green-Kriterien belegt)
- Terraform/AWS Checks: validate GREEN; gezielte Pläne/Applies (14 created, 1 Policy-Update, 2 Waisen entfernt); No-Op-Plan leer; Update-Delta = 1 Change; 0 destroys ausser Waisen-Ersatz
- Git Status (RIS): nur OBS-Dateien (s. Git); Clone/States unberührt
- Files Changed: TF (monitoring/main+vars+outputs, sqs/outputs, main, variables), `tests/test_observability_foundation.py` (neu), Docs (Architektur), Reports
- Open Questions: LatestDelivery null (erste Trail-Zustellung läuft, normal); Full-Plan-lambda.zip (bekannt); 5 pre-existing Defekte
- Risks: Fremd-Mutation live gefunden (falsches Bundle, per CloudTrail belegt) → forensisch gesichert + bit-identisch restauriert (Gate-12-SHA)
- Next Actions: Commit → Folgetore (Agent-Metriken mit Vertrag)
- Resume Point: nach Commit HARD STOP

## Phase 1 — MO-Referenz (read-only, verifiziert)

- CloudWatch: Dashboard (`${project}-overview`, 10 System- + 3 Error-Widgets, echte Namespaces ApiGateway/Lambda/DynamoDB, PLANNED-Text statt Fake) + 6 Alarme (4xx/5xx/errors/duration/throttles/dynamodb, notBreaching, kein SNS) + Outputs; live laufend (6× OK).
- CloudTrail: Trail (multi-region, global, validiert, RW) + S3 (PAB alle true, SSE AES256) + 3-Statement-Policy + time_sleep; live laufend. KEIN Versioning/Lifecycle (auch dort nicht — nicht erfunden).
- Prinzipien übernommen: project_name-Namen, echte Metriken nur, kein SNS, strikte Trail/Watch-Trennung.

## Phase 2 — RIS-Ist (klassifiziert)

- Dashboard: NOT FOUND (kein Modulblock, keine Ressource).
- Alarme: PARTIAL (nur 2 Inline: lambda_errors/api_5xx mit *-dev*-Namen, ohne notBreaching).
- Log Groups: PROVEN (agent/reader, 7/14d).
- Trail/S3/Policy: NOT FOUND (Modul vorhanden, unverdrahtet).
- Metriken: PROVEN (Namespaces nativ verfügbar).
- project_name/environment: PARTIAL (Inline-Namen mit env-Suffix vs Referenz ohne).
- IAM/Outputs: PARTIAL (Policy-Dokument im Modul, keine Live-Rolle nötig).

## Phase 3 — Differenzmatrix (Kurz)

| Capability | MO | RIS (vorher) | Status | Aktion |
|---|---|---|---|---|
| Dashboard | PROVEN (10+3 Widgets) | NOT FOUND | → PROVEN | Modul verdrahtet, RIS-Rebrand + SQS/Extensions |
| Alarme (6+DLQ) | PROVEN | PARTIAL (2 Inline) | → PROVEN (7) | Modul verdrahtet, Inline-Waisen ersetzt |
| Trail/S3/Policy/PAB/SSE | PROVEN | NOT FOUND | → PROVEN | Modul verdrahtet (Policy auf Referenzmuster) |
| Versioning/Lifecycle | NOT FOUND | NOT FOUND | NOT FOUND | nicht erfunden |
| project_name | PROVEN | PARTIAL | → PROVEN | Referenz-Namen, Isolation verifiziert |
| Outputs | PROVEN | PARTIAL | → PROVEN | Dashboard/DLQ-Outputs ergänzt |
| Log Groups | — | PROVEN | PROVEN | unverändert |

## Phasen 4–8 — Regeln/Einbindung

- Trail = Audit (eigener S3, getrennt vom TF-State-Bucket — verifiziert ungleich); Watch = Runtime (erweiterbar via Extensions-Platzhalter, keine Agent-Metriken erfunden).
- Namen: `${project_name}-overview/-trail/-cloudtrail-<account>` (Isolation live verifiziert: kein MO-Overlap).
- Update: Threshold-Änderung → exakt 1 Change (Plan-only, live unangetastet).

## Phase 9 — AWS E2E (mit Zwischenfall)

- Verlauf: Apply 1 (10 Creates: Bucket/PAB/SSE/Policy/Alarme/Dashboard) → Trail-Fehler (Policy-Muster zu eng → auf Referenzmuster) → Apply 2 (Trail + Policy) complete.
- Live: Trail aktiv (Logging true), Bucket AES256 + PAB 4×true, Dashboard 20 Widgets (System/Queues/Extensions/Error), 7 Alarme OK, Log-Gruppen da.
- ZWISCHENFALL (06:47 UTC): fremdes `UpdateFunctionCode` (Mayaws-Credentials, NICHT aus meinen Plänen — Pläne belegt ohne Funktions-Update) spielte `orders_reader.py`-Bundle auf Agent-Funktion → ImportModuleError. Forensik: Bundle gesichert (4164 B, 1 Datei), CloudTrail-Evidence, Restore aus Repo (bit-identisch Gate-12-SHA `A9fC8T5d…`), Re-Verifikation (Handler-404 = Code aktiv, Queues/DLQ leer). MO unberührt.
- Waisen: 2 Inline-Alarme ersetzt (CLI-Delete + state rm, dokumentiert).

## Phasen 10–11 — Tests

- Neu 6 Contract-Tests (Dashboard-Widgets echt/kein Fake, 7 Alarme, Trail-Logging, Bucket-Schutz+Trennung, Isolation, Log-Gruppen) → live PASS; ohne Creds Skip (CI-sicher); boto-Cleanup für Suite-Verträglichkeit.
- Suite: 338 passed + 6 live (bzw. Skip), 4 pre-existing + 1 Collection klassifiziert. 2 Installer-Tests sind Env-sensitiv (kein Code-Problem, belegt).
- No-Op-Plan leer; Update-Delta = 1 Change (nur Plan).

## Phase 12 — Dokumentation

- SYSTEM-ARCHITECTURE (Observability-Absatz + Status); dieser Report + Execution-Log (Template). Keine alten Reports angerührt.

## Checkpoint

- CloudTrail: GREEN (aktiv, getrennt, geschützt) · CloudWatch: GREEN (Logs/Metriken/Alarme) · Dashboard: GREEN (20 Widgets, echte Daten) · S3-Trennung: GREEN · project_name: GREEN · Updateability: GREEN (No-Op + 1-Delta) · AWS E2E: GREEN · Tests: GREEN · Docs/Audit: GREEN · Commit: folgt · Gaps: LatestDelivery-läuft, lambda.zip, 5 Defekte.

**GREEN. HARD STOP.**
