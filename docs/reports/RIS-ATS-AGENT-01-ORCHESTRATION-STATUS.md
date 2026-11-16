# RIS-ATS-AGENT-01 — Orchestrierungsstatus (vollständig)

**Datum:** 2026-11-16
**Branch:** `feature/ris-dev2-ats-agent-pinned-core-01`
**Umgebung:** `ris-dev2`, Konto `262370457690`, Region `eu-central-1`
**Status:** **AGENT ORCHESTRATION — RIS-DEV2 DIRECT PATH COMPLETE / PRODUCT E2E OPEN**

---

## 1. Direkte Antwort

**Ja, für den Agenten-Direktpfad in `ris-dev2`:**

```
SQS/WorkItem → Agent-Lambda → Registry/Discovery/Eligibility/Routing
→ ATS-Agent → Jobsearch /api/ats-analysis → ATSAnalysisResultBody 1.1
→ DynamoDB → Duplikat-/Idempotenzpfad
```

Dieser Pfad ist **deployed und live verifiziert**.

**Nein, für den vollständigen Produkt-End-to-End-Pfad:**

```
Partner A → Mays-Order (nested agentOrder) → Orders-Dispatch
→ RIS Generic Transport → ATS-Agent → Result → autorisierter Orders-GET
```

Dieser Pfad ist lokal mit dem **generierten Orders-Artefakt** getestet, aber
**nicht live** über die öffentliche Partner-API und **nicht** gegen das
externe Orders-Konto `240571105849` (403).

---

## 2. Agent und Architektur

| Element | Wert |
|---|---|
| Agent-ID | `ats-agent` |
| Capability | `analyze.job` |
| Work Type | `ats_process` |
| Version | `1.0.0` |
| Runtime | `python3.14`, `LAMBDA` |
| Contract | `MAYS-JOBSEARCH-ATS-ANALYSIS-V1`, Version **1.2** |
| Result Body | `ATSAnalysisResultBody`, Version **1.1** |
| Quelle | `maynowak/mays-jobsearch` @ `8456910` |
| Lizenz | AGPL-3.0-only, **kein Code kopiert** (Service-Grenze) |

Wiederverwendet, nicht neu gebaut:

- Agent Registry, Discovery, Eligibility, Routing
- AgentBody, WorkItem, Runtime-Pipeline
- Generic Order Transport V1
- OrdersPort und Orders-Modul
- `addition_agent` als Regressionsfall
- `agentOrder` V1 / Ownership / Result

---

## 3. ORCH-Gates

| Gate | Inhalt | Commit | Status |
|---|---|---|---|
| ORCH-00 | Baseline, Agent-Identität, Konfliktmatrix | `70a2994` | COMPLETE |
| ORCH-01 | Jobsearch-API-Snapshot (read-only) | `2cc1ab5` | COMPLETE |
| ORCH-02 | Contract-Pin statt Vendor | `c07332d` | COMPLETE |
| ORCH-03 | Contract-Validierung im Agenten | `52da8db` | COMPLETE |
| ORCH-04 | `ATSAnalysisResultBody V1` | `000b234` | COMPLETE |
| ORCH-05 | Regression, Fail-closed, Artefakt | `2f3463d` | COMPLETE |
| ORCH-06 | Handoff-Bericht | `6f6b1a9` | COMPLETE |
| Live-Fix | Contract 1.2 / Body 1.1 | `3559494` | COMPLETE |
| ris-dev2 | Plan, Apply, Live-E2E | `05c12b3` | COMPLETE |
| Ownership | Queue-Policy, Projektgrenzen | `a9ec193` | COMPLETE |
| Live-E2E-Fix | DynamoDB-Client, Duplikat, Decimal | `22786fc` | COMPLETE |
| Forensic | Ownership & DynamoDB | `dc61c17` | COMPLETE |

---

## 4. Live-Evidenz

### 4.1 Umgebung

| Element | Wert |
|---|---|
| State | serial **58**, **243** Ressourcen, Lineage unverändert |
| Agent-Lambda | `ris-dev2-dev-agent`, `Active` |
| CodeSha256 | `94exPsBrUKodt2hkj4qeiPKroyiAdiTWYe/6o1SEKcw=` |
| Agent-Rolle | `ris-dev2-dev-agent`, kein Permissions-Boundary |
| Work-Table | `ris-dev2-dev-work-items`, Key `workId` (S) |

### 4.2 ATS

| Feld | Wert |
|---|---|
| WorkId | `e2e-ats-9fb9228f8558` |
| Status | `COMPLETED` |
| BodyType / Version | `ATSAnalysisResultBody` / `1.1` |
| Score | `67` |
| AnalysisStatus | `complete` |
| Metadata | Titel, Tokens, Sprache, WorkMode, JobTypes, ContractType |
| Matches | `MATCHED`, `MATCHED`, `UNKNOWN` |
| Source | Contract 1.2, Commit `8456910` |

### 4.3 Addition

| WorkId | Status | Ergebnis |
|---|---|---|
| `e2e-add-d65103dbae0b` | `COMPLETED` | `17 + 25 = 42` |

### 4.4 Doppelauslieferung

`e2e-ats-9fb9228f8558` erneut zugestellt:

```json
{"status": "COMPLETED", "duplicate": true, "attempt_no": 1}
```

CloudWatch: „Duplikat erkannt … kein neuer AgentRun". Kein zweiter Lauf.

### 4.5 Root-Cause des früheren Blockers

Der Fence-Code nutzte `table.meta.client` (Resource-Client mit
Document-Transformation) und übergab bereits DynamoDB-JSON. Der Request wurde
doppelt verpackt:

```json
{"workId": {"M": {"S": {"S": "probe-key"}}}}
```

Der Admin-Call mit plain `boto3.client("dynamodb")` sendet korrekt
`{"workId": {"S": "probe-key"}}`. **Kein AWS-Defekt.** Fix:
`_ddb_transaction_client()` (plain Low-Level-Client); zusätzlich
`_is_conditional_failed()` und `Decimal`-Serialisierung im SQS-Handler.

---

## 5. Vollständigkeitsmatrix

| Ebene | Status | Evidenz |
|---|---|---|
| Lokale Integration (Unit/Contract/Body) | **COMPLETE** | 425 Regression, Fixtures, Contract-Tests |
| Generiertes Orders-Modul | **COMPLETE** | 8 Module, 13 Lambda-Dateien, Artefakt-Tests |
| ris-dev2-Infrastruktur | **COMPLETE** | 227 Creates, State 58/243 |
| Direkter Agentenpfad (SQS → ATS → Result) | **COMPLETE / LIVE** | ATS COMPLETED, Addition 42, Duplikat |
| Öffentliche Partner-API (Cognito JWT) → Agent | **LOKAL GETESTET, NICHT LIVE** | API-/Auth-Tests, kein Live-JWT-Call |
| Orders-External (Konto `240571105849`) | **BLOCKED** | 403 auf Orders-State |
| Autorisierter Orders-GET live | **NICHT LIVE** | lokaler Bridge-/A07-Test |
| Jobsearch-UI-Parität | **FELD-PARITÄT LOKAL** | Body-Felder, keine Live-UI-Prüfung |
| xrepo-Handoff (`MAYS-XR-ATS-001`) | **OFFEN** | anderer Agent aktiv, kein Task angelegt |
| Merge nach `main` | **OFFEN** | Branch reviewfähig |
| Drift-Monitor Jobsearch-Contract | **MANUELL** | `check --fetch` |
| Produktions-Secret / Cross-Account-ARNs | **OFFEN** | nicht provisioniert |

---

## 6. Tests und Security

| Bereich | Ergebnis |
|---|---|
| Fokussierte ATS/Orders/Handler-Suite | **223 passed**, 1 vorbestehender Platform-Handler-Fehler |
| Gezielte Gesamtregression | **425 passed**, 8 skipped |
| Volle Suite vs. `main` | **2627 / 29 / 79 / 4** vs. **2533 / 31 / 126 / 4** — **kein neuer Fehler** |
| E2E lokal (Partner, Bridge, generiertes Orders-Artefakt) | **149 passed** |
| Security (Auth, Consent, Privacy, Tenant, M2M, Policy) | **302 passed**, 6 skipped |
| Secret-Scan | sauber |
| Queue-Policies | keine Wildcards, keine Fremdkonten |
| IAM | `TransactWriteItems` + `ConditionCheckItem`, kein Boundary |
| Fremde Account-Referenzen im State | **0** |

---

## 7. Was fehlt für „komplett"

1. **Live-Test über die öffentliche Partner-API** mit gültigem Cognito-JWT
   (nicht nur direkter Lambda-Invoke).
2. **Orders-External-Pfad** gegen `240571105849` (403) inklusive echter
   Rollen-ARNs und autorisiertem Orders-GET.
3. **xrepo-Handoff** `MAYS-XR-ATS-001` (sequenziell, anderer Agent aktiv).
4. **Merge nach `main`** nach Review.
5. **Drift-Monitor** für den Jobsearch-Contract (CI/Schedule).
6. **Produktions-Secret** und Cross-Account-Freigaben.

---

## 8. Fazit

Die **Agenten-Orchestrierung im ris-dev2-Direktpfad ist vollständig und live
verifiziert**. Die **Produkt-End-to-End-Orchestrierung** (Partner-API →
Orders-External → autorisierter Abruf) ist **noch nicht geschlossen**.

**Keine AWS-Änderung in diesem Bericht.**
