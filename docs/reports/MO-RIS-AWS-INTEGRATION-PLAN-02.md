# MO-RIS-AWS-INTEGRATION-PLAN-02 — Account Reconciliation & Contract Freeze

**Datum:** 2026-11-13
**Typ:** Read-only Discovery + Plan-Konkretisierung. **Keine AWS-Mutation.**
**Ergebnis:** Konten aus Datei-Evidenz abgeglichen. Live-Verifikation des
Zielkontos **BLOCKED** (kein zugelassenes Profil). Vertrag eingefroren.

## 1. R01 — Account Discovery

### 1.1 Datei-Evidenz (belastbar)

| Nachweis | Quelle | Wert |
|---|---|---|
| Orders-State-Bucket | `terraform/backend.tf` | `mays-orders-tfstate-central-240571105849` |
| Orders-Region | ebd. | `eu-central-1` |
| Orders-Workspace | ebd. | `workspace_key_prefix = "env:"` |
| Orders-Lock | ebd. | `mays-orders-terraform-locks` |
| Orders-Deployments | `docs/reports/00-AI_AUDITLOG-MIGRATED-EXECUTION_LOG.md` | `mayaws`, Account `240571105849` |
| RIS dauerhafte Dev-Installation | RIS `AGENTS.md` | `ris-dev` in `240571105849`, `eu-central-1` |
| RIS-Backend-Schema | `installer/ris.py` | `env:/<workspace>/<env>/terraform.tfstate` |

**Ergebnis: beide Systeme gehören im Zielbild demselben Konto `240571105849`,
Region `eu-central-1`.**

### 1.2 Live-Prüfung (read-only, bekannte Default-Credentials)

| Prüfung | Ergebnis |
|---|---|
| `sts get-caller-identity` | `arn:aws:iam::262370457690:user/devnemo` |
| `s3api head-bucket` auf Orders-State | **403 Forbidden** (Bucket existiert, kein Zugriff) |
| SQS `ris-agent*` in 262370457690 | 5 Queues (Testinstallation `ris-agent`) |
| SQS `mays-orders*` in 262370457690 | keine |

**Befund:** Die vorhandenen Credentials gehören dem Entwickler-Testkonto
`262370457690`. Das Zielkonto `240571105849` ist damit **nicht lesbar**.

> **Status: `BLOCKED — ACCOUNT CONTEXT UNVERIFIED` für Live-Fakten des
> Zielkontos.** Die Datei-Evidenz ist eindeutig, aber ein `terraform plan`
> gegen `240571105849` darf ohne freigegebenes Profil nicht erzeugt werden.

### 1.3 Entscheidung B3

**Same-Account** (`240571105849`), weil beide State-Backends und die
RIS-Dokumentation dasselbe Konto nennen. **Keine Migration**, kein
Konto-Wechsel, keine neuen Cross-Account-Verträge. Die Testinstallation
`ris-agent` (262370457690) bleibt davon unberührt und ist **nicht** Ziel.

## 2. R02 — Queue- und Service-Vertrag

Vorhandene Queues im Zielbild (Datei-Evidenz): nur die Retail-Queue
`mays-orders-orders-queue`. **Keine** Agent-Transport-Queue vorhanden →
beide neu.

| Verantwortung | Komponente | Rechte |
|---|---|---|
| Orders Dispatch-Producer | Orders-Lambda (A05) | `sqs:SendMessage` → dispatch |
| RIS Dispatch-Ingress | **neue** Lambda (Envelope → WorkItem) | `ReceiveMessage`/`DeleteMessage` auf dispatch |
| RIS Agent Runtime | bestehende Worker-Lambda | unverändert (liest `work-queue`) |
| RIS Result-Producer | bestehende RIS-Runtime | `sqs:SendMessage` → results |
| Orders Result-Consumer | **neue** Lambda (`result_handler.handler`) | `ReceiveMessage`/`DeleteMessage` auf results |

Event-Source-Mappings: Dispatch-Batch 5 / Visibility 300 s; Result-Batch 10 /
Visibility 60 s. Beide mit DLQ nach 3 Empfängen. Eine Queue pro Richtung,
nicht pro Agent.

## 3. R03 — Secret-Vertrag (B4)

**Entscheidung: Secrets Manager**, ein Secret pro Installation.

| Frage | Festlegung |
|---|---|
| Erzeugt/verwaltet | Orders-Seite (Consumer/Verifier) als Container `<project>-agent-result-hmac` |
| Wert | **out-of-band** gesetzt; niemals in Terraform-State, Git, Report, Log oder Test |
| Lesen darf | Orders-Consumer-Rolle + explizit gelistete RIS-Producer-Rollen (Resource-Policy) |
| Laufzeitbezug | `GetSecretValue` beim Cold Start, im Prozess gecacht; **keine** Env-Variable mit Wert |
| Rotation | Secret-Wert als JSON `{"current": "...", "previous": "..."}`; Verifier akzeptiert beide, bis die Rotation abgeschlossen ist |
| Fehlerfall | Secret fehlt/unlesbar → Consumer verwirft (fail-closed), Producer kann nicht signieren → kein Result + Alarm |
| Versionen | nur `current` + `previous`, keine unbegrenzte Historie |

Lokale Tests verwenden ausschließlich synthetische Werte (bereits so umgesetzt).

## 4. R04 — Terraform-Inventar

Neu, hinter `enable_agent_transport = true` (Default **false** → 0 Änderungen):

| Repo | Ressource | Typ |
|---|---|---|
| RIS | `agent-dispatch` Queue | create |
| RIS | `agent-dispatch-dlq` | create |
| RIS | Dispatch-Queue-Policy | create |
| Orders | `agent-results` Queue | create |
| Orders | `agent-results-dlq` | create |
| Orders | Result-Queue-Policy | create |
| Orders | `agent-result-hmac` Secret | create |
| Orders | Secret-Resource-Policy | create |

**8 Creates, 0 Updates, 0 Deletes.** Keine bestehende Ressource wird geändert.
Zusätzlich später (nicht in diesem Code): 2 Lambdas + 2 IAM-Rollen.

Validierung:

| Prüfung | Ergebnis |
|---|---|
| `terraform fmt -check` (beide Repos) | 0 |
| `terraform validate` (beide Repos) | **Success** |
| Contract-Compat (RIS) | 9 passed |
| Orders Suite | 193 OK |

**Kein `terraform plan`** gegen `240571105849` erzeugt — kein freigegebenes
Profil. Kein Plan gegen `262370457690`, weil das nicht das Ziel ist.

## 5. R05 — Entscheidungstabelle

| Punkt | Nachweis |
|---|---|
| AWS-Konten | **Identisch** `240571105849` (Datei-Evidenz); live unbestätigt |
| AWS-Regionen | `eu-central-1` (beide) |
| Dispatch-Queue | **neu erforderlich** (keine vorhandene passend) |
| Result-Queue | **neu erforderlich** |
| Lambdas | RIS-Ingress neu; Orders-Result-Consumer nutzt vorhandenen `result_handler` (eigenes Deployable) |
| IAM | 4 Richtungen, Least Privilege, keine Owner-Rechte, keine DB-übergreifenden Zugriffe |
| Secrets | Secrets Manager, Container in Orders, Lesen für RIS-Producer |
| Terraform | 8 Creates bei Flag an, 0 bei Flag aus |
| Betrieb | DLQ 3 Versuche, Retention 4 d, SSE-SQS, Alarme auf DLQ-Tiefe |
| Deployment | Voraussetzungen: Profil für 240571105849, B1/B2-Lambdas, Secret-Wert, Plan-Review; Rollback per Flag |

## 6. Risiken und Blocker

| # | Blocker | Wirkung |
|---|---|---|
| B-a | **Kein Zugriff auf 240571105849** | kein echter Plan; Live-Fakten unbestätigt |
| B-b | Dispatch-Ingress-Lambda fehlt | Queue ohne Consumer |
| B-c | Result-Consumer-Lambda fehlt | Ergebnisse werden nicht übernommen |
| B-d | Secret-Wert muss out-of-band gesetzt werden | sonst fail-closed, kein Betrieb |
| B-e | Rotation noch nicht implementiert | Verifier kennt nur einen Schlüssel |

**Rollback:** `enable_agent_transport = false` → Plan entfernt die 8 Ressourcen;
alternativ gezielter Destroy nach Freigabe. Bestehende Ressourcen unberührt.

## 7. STOP

Kein Apply, kein Destroy, kein Deployment, kein State-Wechsel. Ein späteres
Apply erfordert einen Plan gegen `240571105849` mit eindeutiger Ressourcenliste
und ausdrücklicher Freigabe.
