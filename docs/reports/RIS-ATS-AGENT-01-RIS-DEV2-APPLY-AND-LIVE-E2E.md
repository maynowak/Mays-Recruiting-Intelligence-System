# RIS-ATS-AGENT-01 — ris-dev2 Apply, Live-E2E, Security, Regression

**Datum:** 2026-11-16
**Branch:** `feature/ris-dev2-ats-agent-pinned-core-01`
**Konto:** `262370457690` (devnemo) · **Region:** `eu-central-1` · **Workspace:** `ris-dev2`
**Status:** **DEPLOYED / LIVE E2E VERIFIED / LOCAL VERIFIED**

---

## 1. Ergebnis

Die RIS-Plattform ist in `ris-dev2` neu aufgebaut. Der vollständige ATS-Pfad
läuft live:

```
SQS/WorkItem → Agent-Lambda → ATS-Agent → Jobsearch /api/ats-analysis
→ ATSAnalysisResultBody 1.1 → DynamoDB → autorisierter Abruf
```

Zusätzlich live verifiziert:

| Test | Ergebnis |
|---|---|
| ATS `analyze.job` | `COMPLETED`, Score 67, Body 1.1, Contract 1.2 |
| Addition `math.add` | `17 + 25 = 42`, `COMPLETED` |
| Doppelauslieferung | `duplicate: true`, **kein** zweiter Lauf |

---

## 2. Plan und Apply

| Element | Wert |
|---|---|
| Plan | **227 to add, 0 to change, 0 to destroy** |
| Ursprünglicher Plan | `73953f06…10ee` (Lockfile-Inkonsistenz) |
| Ersatzplan (adress-/aktionsidentisch) | `e2824650…ffa` |
| State | **serial 58, 243 Ressourcen**, Lineage unverändert |
| Agent-Lambda | `ris-dev2-dev-agent`, `Active` |
| CodeSha256 | `94exPsBrUKodt2hkj4qeiPKroyiAdiTWYe/6o1SEKcw=` |
| Destroy/Rollback | **keiner** |

Delta-Appläufe: Orders-Boundary (`v3`, 5 Creates), `ConditionCheckItem`
(`v6`, 1 Update), Queue-Policy (`v13`, 1 Update), Lambda-Fixes (`v14`–`v17`).

---

## 3. Live-E2E-Nachweise

### 3.1 ATS

Synthetischer WorkItem (`ats_process`, `analyze.job`, keine PII):

| Feld | Wert |
|---|---|
| Status | `COMPLETED` |
| `data.bodyType` | `ATSAnalysisResultBody` |
| `data.bodyVersion` | `1.1` |
| `analysis.score` | `67` |
| `analysis.analysisStatus` | `complete` |
| `analysis.metadata` | Titel, Tokens, Sprache, WorkMode, JobTypes, ContractType |
| `matches` | `MATCHED`, `MATCHED`, `UNKNOWN` |
| `source` | `mays-jobsearch`, Contract 1.2, Commit `8456910` |

### 3.2 Addition

WorkItem `agent_addition_agent` / `math.add`:

```json
{"left": 17, "right": 25, "sum": 42}
```

Status `COMPLETED`.

### 3.3 Doppelauslieferung

Derselbe ATS-WorkItem erneut zugestellt:

```json
{"status": "COMPLETED", "duplicate": true, "attempt_no": 1,
 "result_reference": "work:…:attempt:1"}
```

Kein zweiter Agentenlauf.

### 3.4 Test-Entitlement

Die Entitlement-Tabelle war leer; der Worker lehnt korrekt ab. Für den E2E
wurde eine **synthetische Testzeile** angelegt:

| Feld | Wert |
|---|---|
| User | `user-e2e-15` |
| Tenant | `tenant-e2e-15` |
| Agenten | `ats-agent`, `addition_agent` |
| Zweck | ausschließlich Live-E2E |

Das ist Testdatum, keine Infrastrukturänderung. Die IDs sind im Auditlog
dokumentiert.

---

## 4. Gefundene und behobene Defekte

### 4.1 Orders-Boundary nicht portabel
Upstream-Modul setzte die Boundary aus Konto `240571105849` fest.
**Fix:** Orders `95f8921` — Boundary optional, Orders-Root setzt sie explizit,
Builder neutralisiert den Default. RIS-Pin nachgezogen.

### 4.2 Orders-Queue für fremde Prinzipale offen
Queue-Policy `Principal: "*"` erlaubte jedem AWS-Prinzipal Send/Receive/Delete.
**Fix:** Orders `dad69ea` — Policy auf `arn:aws:iam::262370457690:root`
beschränkt. Angewendet und verifiziert.

### 4.3 DynamoDB-JSON doppelt verpackt (Live-E2E-Blocker)
`boto3.resource('dynamodb').Table(...).meta.client` trägt die
Document-Transformation. Der Fence-Code übergab bereits DynamoDB-JSON; auf der
Leitung kam:

```json
{"Key": {"workId": {"M": {"S": {"S": "…"}}}}}
```

**Fix:** `_ddb_transaction_client()` liefert einen echten Low-Level-Client
(keine Resource-Marshalling); Fake-Clients in Tests bleiben unverändert.
Regressionstest prüft den serialisierten Body (kein `"M"`).

### 4.4 Transaktions-Conditional nicht erkannt
`TransactionCanceledException` mit `ConditionalCheckFailed` wurde nicht als
Duplikat erkannt.
**Fix:** `_is_conditional_failed()` wertet `CancellationReasons` aus.

### 4.5 Decimal-Serialisierung im Duplikat-Response
Der SQS-Handler serialisierte DynamoDB-`Decimal` nicht.
**Fix:** `json.dumps(..., default=_application_json_default)` im SQS-Pfad.

### 4.6 Fehlende IAM-Aktion
DynamoDB-Transaktionen brauchen `dynamodb:ConditionCheckItem`.
**Fix:** Agent-Rolle `ris-dev2-dev-lambda-dynamodb-work` ergänzt.

---

## 5. Lokale Verifikation

| Bereich | Ergebnis |
|---|---|
| Fokussierte ATS/Orders/Handler-Suite nach den Fixes | **223 passed**, 1 vorbestehender Platform-Handler-Fehler |
| Gezielte Gesamtregression | **425 passed**, 8 skipped |
| Volle Suite vs. `main` | **2627 passed / 29 failed / 79 skipped / 4 errors**; `main`: 2533 / 31 / 126 / 4 — **kein neuer Fehler** |
| E2E lokal (Partner, Bridge, generiertes Orders-Artefakt) | **149 passed** |
| Security (Auth, Consent, Privacy, Tenant, M2M, Policy) | **302 passed**, 6 skipped |
| Secret-Scan | sauber |

---

## 6. Security

- Queue-Policy auf das eigene Konto beschränkt.
- Keine fremden Account-Referenzen im State (`240571105849`: **0**).
- Kein Code-Copy aus Jobsearch (AGPL-Service-Grenze).
- Kein CV-Rohtext/Secret im Log; Testdaten synthetisch.
- IAM: `TransactWriteItems` + `ConditionCheckItem`, kein Wildcard-Prinzipal.

---

## 7. Offene Punkte

| # | Punkt | Status |
|---|---|---|
| 1 | Orders-Konto `240571105849` | 403, nicht zugreifbar |
| 2 | Cross-Account-Rollen-ARNs | unbekannt |
| 3 | Secret-Provisionierung (`result_hmac`) | nicht erfolgt |
| 4 | Jobsearch-Drift-Monitor | manuell (`check --fetch`) |
| 5 | Test-Entitlements | nach E2E bewusst belassen, dokumentiert |

---

## 8. Commits

| Repo | Commit | Inhalt |
|---|---|---|
| Orders | `95f8921` | Boundary portabel |
| Orders | `dad69ea` | Queue-Policy auf eigenes Konto |
| RIS | `05c12b3` | Apply, Diagnose, IAM |
| RIS | `a9ec193` | Queue-Policy-Pin/Report |
| RIS | *(dieser Commit)* | Live-E2E-Fixes + Erfolgsbericht |

**Status: DEPLOYED / LIVE E2E VERIFIED / LOCAL VERIFIED.**
