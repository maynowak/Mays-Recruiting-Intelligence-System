# GATE-3 — Mays-Orders Live-Installation and Verification

STATUS: YELLOW

- Date/Time: 2026-10-01 11:35 UTC
- Branch + HEAD (RIS): main, c32434d (unveraendert, = Gate-2-Ausgangslage)
- MO-Stand: 9c61237185d202e072b2304355ee836154368846 als frischer Git-Clone unter `projects/mays_orders` (clean, ignoriert), gepinnt in `installer/mays-orders-clone.pinned.json`
- Scope: MO live installieren (Freigabe liegt vor) + reale AWS-E2E verifizieren. Kein RIS-Umbau, kein Adapter, kein Destroy, keine manuellen AWS-Ressourcen
- Sections: A–T unten
- Findings: Apply GREEN (37/0/0/0); Kern-E2E PENDING→CONFIRMED live belegt; GET-Read-Bug (Decimal) gefunden, nicht gefixt
- Evidence: Installer-Runs `.mays-installer/runs/20261001-111007` + `-111135` (im Clone, ignoriert); AWS-CLI-Outputs (Account 240571105849 / eu-central-1); Lambda-Logs
- Classification: YELLOW
- Terraform/AWS Checks: validate READY, plan 37+2, deploy Exit 0, state/output OK, kein Destroy
- Git Status (RIS): 0 modified; untracked: 8 Alt-Reports (unberuehrt) + Pin-Datei + dieser Report + Execution-Log
- Files Changed: `installer/mays-orders-clone.pinned.json` (neu), `docs/reports/GATE-3-MO-LIVE-INSTALLATION-AND-VERIFICATION-01.md` (diese Datei), `...-01-EXECUTION_LOG.md` (fortlaufend)
- Open Questions: s. Abschnitt T / offene Punkte
- Risks: s. Abschnitt O + T (GET-Bug, lokaler State, Altlasten)
- Next Actions: Commit (Pin + Reports) → Gate-4-Empfehlung (Decimal-Fix)
- Resume Point: nach Commit HARD STOP (kein RIS-Apply, kein Adapter)

## A. Preflight

| Check | Ergebnis |
|---|---|
| RIS `git status` | 0 modified, 8 untracked Alt-Reports (unberuehrt) |
| RIS HEAD | c32434d = Gate-2-Stand |
| MO working tree (extern `~/projects/Mays-Orders-AWS`) | main 356a1f5, 53 Commits AHEAD von origin/main, nur `?? terraform/tfplan` → NICHT verwendet |
| Remote (`git ls-remote`) | `origin/main` + `HEAD` = 9c61237 = Gate-2-Referenz |
| Frischer Clone `projects/mays_orders` | HEAD 9c61237, `status --short` leer (clean) |
| `.gitignore:52` (`projects/`) | greift (Clone in `git status` unsichtbar — verifiziert) |
| AWS caller identity (mayaws) | `AIDATQAZHYI4SUCNIJNJR`, Account **240571105849**, ARN `arn:aws:iam::240571105849:user/Mayaws` |
| Region | eu-central-1 |
| project_name | mays-orders (Installer-Default; Workspace `mays-orders` existierte + selektiert) |
| Backend (im Clone) | KEIN `terraform/backend.*` im Stand 9c61 (git-ls-files leer) → lokaler State (Gate-2-Aussage bestaetigt) |
| Installer `identity` | Exit 0 (Account/Region/ARN wie oben) |
| Installer `validate` (Clone) | **READY: 10 passed, 0 failed, 0 warned**, Exit 0 |
| Stale S3-Lock (Sep-27-Plan, gleicher Host, kein Prozess aktiv) | via `terraform force-unlock -force 6035dfe2-…` geloest (Unlock bestaetigt, ausfuehrlich im Log) |

## B. AWS Context

- Profil: mayaws · Account: 240571105849 · Region: eu-central-1 · Identity: `arn:aws:iam::240571105849:user/Mayaws`. Keine anderen Profile/Konten verwendet.

## C. Terraform Apply

- Lifecycle strikt ueber MO-Installer: `validate` → `plan` → `deploy --plan … --yes` (mit `ALLOW_AWS_OPERATIONS=true`; Human approval durch Auftrag).
- Plan-Datei: `mays-orders-development-0.1.0-H2-240571105849-deploy-0001.tfplan` (Run 20261001-111007): **37× (create), 2× (read), 0 Deletes** — exakt Gate-2-Stand (37+2). Alle 39 Adressen unter `module.*`, keine Fremdressourcen.
- Deploy (Run 20261001-111135): `Plan: 37 to add, 0 to change, 0 to destroy, 0 to replace` · Safety **PASS** · Policy gate **PASSED** · `Deployment successful!` · State + Identity post-verifiziert. Exit 0.
- State: `terraform/terraform.tfstate` **lokal** (Lineage `945c0b35-…`, Serial 40, 99 KB), 45 Eintraege = **37 managed + 8 data-Reads**, keine tainted/unerwarteten Eintraege. S3-Workspace-State (`env:/mays-orders/…`, Sep-27-Experimente, andere Lineage) heute NICHT angefasst (LastModified 2026-09-27, read-only verifiziert).

## D. Installed Resources

37 managed (Auszug aus `state list`): API (HTTP API + JWT-Authorizer + Integration + 4 Routen + Stage + Permission), CloudTrail (Trail + S3 + Policy + PAB + SSE + time_sleep), Cognito (Pool/Client/staff-Gruppe), DynamoDB (orders-Tabelle), IAM (Handler-Rolle+Policy), Lambda (Handler + Log-Gruppe), Monitoring (Dashboard + 6 Alarme), SQS (Queue + Policy), SQS-Worker (Rolle/Policy/Function/Mapping/Log). Outputs: s. E–I.

## E. API Verification

- `mays-orders-api` (`246u4m3sqh`), Endpoint `https://246u4m3sqh.execute-api.eu-central-1.amazonaws.com`, HTTP, Stage `$default` (AutoDeploy).
- Routen (alle JWT): `POST /orders`, `GET /orders`, `GET /orders/{orderId}`, `PATCH /orders/{orderId}/status`.

## F. Cognito Verification

- Pool `eu-central-1_8HrAMWpB2` (ARN `…:userpool/eu-central-1_8HrAMWpB2`, Issuer `cognito-idp.eu-central-1.amazonaws.com/eu-central-1_8HrAMWpB2`), Password-Policy (8+upper+lower+Zahl+Symbol), Client `3m2lvs3tan8icjfqtpekt9rpo5` (`ALLOW_USER_PASSWORD_AUTH` + Refresh), Gruppe `staff`. USER_PASSWORD_AUTH-Login live getestet (Token, 1026 Zeichen).

## G. DynamoDB Verification

- Tabelle `mays-orders` (ARN `…:table/mays-orders`), **ACTIVE**, Keys `pk` (HASH) + `sk` (RANGE), GSI `gsi1`, Billing PAY_PER_REQUEST. Zugriff live (Scan/Get). Nebenbefund: `pk` = `ord_ord_…` (Doppelpraefix) — Doku, kein Blocker.

## H. SQS Verification

- URL `https://sqs.eu-central-1.amazonaws.com/240571105849/mays-orders-orders-queue`, ARN `arn:aws:sqs:eu-central-1:240571105849:mays-orders-orders-queue`, Visibility **30s**, SSE SQS-managed (kein CMK), **keine RedrivePolicy (= kein DLQ — Gate-2-Befund live bestaetigt)**.
- Policy live ausgelesen: Sid `AllowAccessFromAccount`, **Principal `*`**, Aktionen Send/Receive/Delete/GetAttributes — Gate-2-Befund live bestaetigt, NICHT umgebaut.

## I. Worker Verification

- `mays-orders-sqs-worker`: Active, python3.14, Rolle `mays-orders-sqs-worker-role`, ENV `ORDERS_TABLE=mays-orders`.
- Handler `mays-orders-handler`: Active, python3.11, Timeout 10s, ENV `SQS_QUEUE_URL` + `ORDERS_TABLE`.

## J. Event Source Mapping

- UUID `b94bc119-…`, **Enabled**, BatchSize **5**, Quelle = Orders-Queue-ARN. Verarbeitung live belegt (s. K).

## K. Live Order E2E

Test-Auftrag (eindeutig markiert): `GATE3-E2E-TEST (automated live test, safe to delete)`, SKU `GATE3-TEST-SKU`, EUR 100 (Integer — Live-Validierung: `unitPrice` muss Integer ≥ 1 sein; Doku-Beispiel 19.99 wird mit 400 abgelehnt).

| Schritt | Beleg |
|---|---|
| Auth (staff-User `gate3-e2e-test`, danach geloescht) | JWT erhalten |
| `POST /orders` | **201**, `orderId` `ord_9d0eb8a5786b82bb8652d09c`, Status **PENDING** (09:24:42) |
| SQS-Zustellung | Handler-Log 09:24:43 `Sent order ord_… to SQS` |
| Worker-Verarbeitung | Worker-Log 09:24:44/46 `Worker processing … status=CONFIRMED` → `transitioned PENDING -> CONFIRMED` |
| DDB-Status | `status=CONFIRMED`, `updated 09:24:46`, `version=1` |
| Queue danach | `ApproximateNumberOfMessages=0`, `NotVisible=0` (entleert) |
| `GET /orders/{id}` | **500** (s. L — Bug, kein E2E-Fehlschlag der Kette) |

## L. Status Transition

- **PENDING → CONFIRMED via SQS/Worker live nachgewiesen** (Logs + DDB + Queue-Leere). Tatsaechlich erreichter Zwischen-Status: CONFIRMED (09:24:46).
- Einschraenkung: API-Reads (`GET /orders`, `GET /orders/{id}`) und `PATCH`-Responses geben **500 `INTERNAL_ERROR`**, Handler-Log: `Unexpected error: Object of type Decimal is not JSON serializable` (RequestId `e4c9f8fa`, 09:25:18). Ursache: DDB-Numerics (Decimal) werden im GET/PATCH-Response-Pfad nicht konvertiert. POST-201 funktioniert (frische Dicts ohne Decimal). **Nicht gefixt** (separates Gate noetig).

## M. Cancellation Check

- `PATCH …/status {"status":"CANCELLED"}` aus CONFIRMED: Response 500 (Decimal-Bug, s. L), **Wirkung belegt**: DDB `status=CANCELLED`, `updated 09:26:56` → zulaessiger Uebergang funktioniert fachlich.
- `PATCH CANCELLED→CONFIRMED`: **409 `INVALID_TRANSITION`** (`Transition from CANCELLED to CONFIRMED is not allowed`) — korrekt.
- `PATCH CANCELLED→SHIPPED`: **409** — korrekt. Finaler DDB-Status: **CANCELLED** (Endzustand).
- Kein Worker-Abbruch behauptet (Implementierung nicht vorhanden — nur Guards via Conditional Writes laut Gate 2).

## N. Agent/Result Contract Finding

- Grep in `lambda/`, `api/`, `order-lifecycle/` nach result.packet/callback/webhook/push/response-queue: **kein Treffer**. Kein Result Packet, kein Execution Contract, kein Callback/Push, keine Response Queue. **Polling (`GET`) einziger belegter Handoff — Gate-2-Erwartung live bestaetigt** (mit L-Einschraenkung: Reads aktuell 500).

## O. Security Findings

- SQS-Policy Principal `*` live bestaetigt (Sid suggeriert Account-Scope — Auseinanderfallen wie Gate 2). Auswirkung: Queue-Aktionen formal fuer `*` erlaubt (AWS-seitig durch Account-Kontext begrenzt, dennoch unsauber). E2E-relevant: nein. **Nicht umgebaut** (separates Haertungs-Gate).
- Kein DLQ (keine RedrivePolicy) — Poison-Message-Risiko, separates Gate.
- Secrets: keine im Code/Repo (Test-Passwort nur in RAM/`/tmp`, danach `shred`; Token ebenso). Cognito-Test-User geloescht (Pool leer verifiziert).
- Oeffentliche Endpunkte: nur API-Gateway-Endpoint (alle Routen JWT). IAM: Least-Privilege live verifiziert (Handler: DDB Put/Get/Query/Update nur eigene Tabelle+GSI, SQS nur Send an eigene Queue; Worker: DDB Get/Update, SQS Receive/Delete/GetAttributes).

## P. Cost/Resource Summary

- 37 managed Ressourcen, serverless/pay-per-use: DDB PAY_PER_REQUEST, Lambdas 128 MB (Timeout 10s), Log-Retention 7 Tage, keine NAT/EC2/SNS. Erwartete laufende Kosten ~0 im Leerlauf (Test-Order = 1 Item).
- Vorgefunden, NICHT Gate-3 (nicht angefasst, nicht gezaehlt): `mays-orders-cognito-backup-lambda` (Sep 27) + 2 Backup-Alarme (1× INSUFFICIENT_DATA) + 3 CodeBuild-Log-Groups + 6 CodeBuild-Projekte (`mays-orders-development-ci-*`) + Lock-Tabelle `mays-orders-terraform-locks` (fuer externe Bestaende noetig).

## Q. Cleanup

- Infrastruktur bleibt bestehen (Auftrag — **kein Destroy**).
- Test-User geloescht, Secrets vernichtet. Test-Order `ord_9d0e…` (CANCELLED) bleibt in DDB — kein DELETE-Endpunkt im Modell (1 Item, vernachlaessigbar).

## R. Test Results

| Test | Anzahl | Ergebnis | Exit |
|---|---|---|---|
| MO Installer (`installer/tests/`) | 81 | PASS | 0 |
| Lambda-Unit (`lambda/tests/`, `PYTHONPATH=lambda/src`) | 51 | PASS | 0 |
| Lambda-Unit ohne korrekten PYTHONPATH | — | Collection-Error (Doku-Problem, wie Gate 2) | — |
| Live-E2E | 1 Order, 5 Schritte | Kette belegt (s. K–M) | — |

## S. Git State

- RIS: `git status` 0 modified; untracked: 8 Alt-Reports (unberuehrt, nicht Gate-3) + `installer/mays-orders-clone.pinned.json` + 2 Gate-3-Dateien. Vor Commit geprueft: keine Secrets/Credentials/State-Dateien (Clone + `*.tfstate` + `*.tfplan` ignoriert).
- MO-Clone: clean auf 9c61237. Externer Checkout unberuehrt (nur Shared-State-Unlock, keine Datei-Aenderung).
- Commit (vorgesehen): `docs(install): verify live mays-orders foundation` — nur Pin-Datei + Reports.

## T. Gate Decision

| Bereich | Ergebnis |
|---|---|
| Preflight | GREEN |
| AWS Identity | GREEN |
| Terraform Apply | GREEN |
| State / Workspace | GREEN (lokal, wie Gate-2-Stand; Isolation via Prefix + separates File) |
| API Gateway | GREEN |
| Cognito | GREEN |
| DynamoDB | GREEN |
| SQS | GREEN |
| Worker | GREEN |
| Event Source Mapping | GREEN |
| Order E2E | GREEN (Kette PENDING→CONFIRMED belegt) |
| Status Transition | YELLOW (CONFIRMED belegt; Reads per API 500) |
| Cancellation | GREEN (fachlich + 409-Guards) |
| RIS Handoff | YELLOW (nur Polling belegt; Reads aktuell fehlerhaft) |
| Security | YELLOW (Policy-`*`, kein DLQ — bekannt, separates Gate) |
| Tests | GREEN (81+51) |
| Git | GREEN |

**Entscheidung: YELLOW** — Mays-Orders ist live installiert (37/0/0/0) und die Kern-E2E-Kette (POST→DDB→SQS→Worker→CONFIRMED→CANCELLED) ist mit AWS-Evidence nachgewiesen. Offen: GET/PATCH-Response-Serialisierung (Decimal-Bug) — kein Datenverlust, aber API-Reads betroffen.

- Report: `docs/reports/GATE-3-MO-LIVE-INSTALLATION-AND-VERIFICATION-01.md` (+ `-EXECUTION_LOG.md`)
- Commit: folgt (nur Pin-Datei + Reports)
- Offene Punkte: (1) Decimal-Fix + Re-E2E der Reads; (2) SQS-Policy-Haertung + DLQ (separates Security-Gate); (3) Sep-27-Altlasten (Backup-Lambda/CodeBuild) klaeren/entfernen; (4) Remote-State-Migration (lokaler State ist Team-Single-Point)
- Naechste Gate-Empfehlung: **Gate 4 = MO Decimal-Fix (minimaler Response-Encoder) + Re-Apply + Read-Re-E2E**, danach RIS-Adapter-Gate (Polling-Client). KEIN RIS-Foundation-Apply, KEIN Adapter in diesem Gate.

**DANN HARD STOP.**
