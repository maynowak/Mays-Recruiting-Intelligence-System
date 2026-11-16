# RIS-ATS-AGENT-01 — ris-dev2 Apply, Live-E2E, Security, Regression

**Datum:** 2026-11-16
**Branch:** `feature/ris-dev2-ats-agent-pinned-core-01`
**Konto:** `262370457690` (devnemo) · **Region:** `eu-central-1` · **Workspace:** `ris-dev2`
**Status:** **DEPLOYED / LOCAL VERIFIED / LIVE-E2E BLOCKED WITH EVIDENCE**

---

## 1. Ergebnis in einem Satz

Die RIS-Plattform ist in `ris-dev2` neu aufgebaut (State 242 Ressourcen, serial 53).
Plan, Apply, lokale E2E-, Security- und Regressionsläufe sind belegt. Der
**Live-E2E des ATS-Agenten** ist an einer DynamoDB-Anomalie blockiert: Selbst
ein einfaches `GetItem` der Lambda wird mit „key element does not match the
schema" abgelehnt, obwohl Identität, Tabelle, Schlüssel und Endpoint korrekt
sind und dieselben Aufrufe mit Adminrechten funktionieren.

**Kein Destroy, kein Rollback.** Die Umgebung bleibt aufgebaut.

---

## 2. Plan und Apply

### 2.1 Plan

| Element | Wert |
|---|---|
| Ursprünglicher Plan | `73953f06a25f63488d1a04b40f7b31782165c1235fe3e8798dff0bd9c8ce10ee` |
| Aktionen | **227 to add, 0 to change, 0 to destroy**, 6 data reads |
| Ersatzplan (lock-identisch) | `e28246507a0b505d17d318017c1c35e600d378bf51e93203b9429b5130e6dffa` |
| Adressvergleich | **identisch** (233 Adressen, gleiche Aktionen) |

Der ursprüngliche Plan war wegen einer Lockfile-Inkonsistenz nicht anwendbar.
Der Ersatzplan war adress- und aktionsidentisch und wurde verwendet.

### 2.2 Apply-Verlauf

| Schritt | Plan-SHA | Ergebnis |
|---|---|---|
| Erst-Apply | `e2824650…` | 227 Creates gestartet; Abbruch am Orders-`sqs_worker`-Role: Account-Boundary `240571105849` existiert nicht in `262370457690` |
| Fix Orders-Boundary | — | Orders-Commit `95f8921` (portabel), RIS-Pin nachgezogen |
| Delta-Apply | `b392e5e2…` | **5 Creates, 222 No-Ops, 0 Destroys**; Plattform vollständig |
| IAM-Fix `ConditionCheckItem` | `6db49d0f…` | **1 Update** |
| Diagnose-/Cleanup-Builds | v7–v12 | nur Lambda-Code-Updates |

### 2.3 Endzustand

| Element | Wert |
|---|---|
| State | `serial 53`, **242 Ressourcen**, Lineage unverändert (`a0bd361d-…`) |
| Agent-Lambda | `ris-dev2-dev-agent`, `Active` |
| CodeSha256 | `v84GzeWEAuHRehbbLlVTAqd9icPFKLfx6icILZp/rik=` (`bfce06cd…ae29`) |
| Orders-Modul | aus Pin `95f8921`, Lambda-ZIP `1801e9fb…ad222` |
| IAM (Work-Table) | `TransactWriteItems` **und** `ConditionCheckItem` |

Wichtige Outputs:

```
lambda_function_name       = ris-dev2-dev-agent
dynamodb_work_items_table  = ris-dev2-dev-work-items
dynamodb_agent_catalog     = ris-dev2-dev-agent-catalog
cognito_user_pool_id       = eu-central-1_OYN9QiHc5
sqs_queues                 = ats / cv / match / work
```

---

## 3. Live-E2E — was passiert ist

Ein synthetischer SQS-Record (`ats_process`, `analyze.job`, synthetische
Job-/Profil-Daten, keine PII) wurde direkt an `ris-dev2-dev-agent` invokes.

| Phase | Ergebnis |
|---|---|
| Handler, Envelope, Kandidaten | PASS |
| Eligibility | 1 eligible, 0 rejected |
| Agent-Auswahl | `ats-agent` |
| **Subject-Fence-Admission** | **BLOCKIERT** |
| ATS-Aufruf / Result | nicht erreicht |

### Fehler

```
TransactionCanceledException
[ValidationError: The provided key element does not match the schema, None]
```

### Was bereits ausgeschlossen ist

| Prüfung | Ergebnis |
|---|---|
| Lambda-Identität | `262370457690`, Rolle `ris-dev2-dev-agent` |
| DynamoDB-Endpoint | `https://dynamodb.eu-central-1.amazonaws.com` |
| Tabelle | `ris-dev2-dev-work-items` |
| Key-Schema (Admin-Sicht) | `workId` (HASH, String) |
| Key-Typ/Länge | `str`, 78 Zeichen |
| IAM `TransactWriteItems` | vorhanden |
| IAM `ConditionCheckItem` | ergänzt und deployed |
| **Identische Calls mit Adminrechten** | **erfolgreich** (GetItem, TransactWriteItems, auch mit dem exakten Item) |
| **GetItem mit einfachem Key `probe-key` in der Lambda** | **scheitert mit demselben Fehler** |

Damit ist der Fehler **nicht** auf Contract, Agent-Code, Item-Form, IAM oder
den Fence-Key zurückzuführen. Die Lambda erhält für einen trivialen
`GetItem`-Aufruf eine Schema-Ablehnung, obwohl Tabelle und Schlüssel korrekt
sind. Das ist ein **Plattform-/Runtime-Befund**, der AWS-seitig untersucht
werden muss (z. B. Tabellen-/GSI-Zustand, Endpoint-/Client-Anomalie).

---

## 4. Dabei gefundene und behobene Defekte

### 4.1 Orders-Boundary nicht portabel

Das generierte Orders-Modul setzte die IAM-Boundary
`arn:aws:iam::240571105849:policy/...` fest. Im RIS-Konto existiert sie nicht.

**Fix:** Orders-Commit `95f8921` — Submodul-Default leer, `permissions_boundary`
nur bei gesetztem Wert, Orders-Root setzt die Boundary explizit; der Builder
neutralisiert den Default im generierten Modul. RIS-Pin auf `95f8921`.

### 4.2 Fehlende IAM-Aktion für DynamoDB-Transaktionen

`TransactWriteItems` allein genügt nicht; die `ConditionCheck`-Operation
braucht `dynamodb:ConditionCheckItem`.

**Fix:** `terraform/modules/lambda/main.tf`, Agent-Rolle
`ris-dev2-dev-lambda-dynamodb-work`, deployed.

### 4.3 Diagnose

Die Fehlermeldung des Fence-Pfads wurde um Tabelle, Fence-Key, WorkId und
Cancellation-Reasons ergänzt. Das bleibt als dauerhafte Diagnosehilfe.

---

## 5. Lokale Verifikation (nach dem Apply)

| Bereich | Ergebnis |
|---|---|
| ATS/Contract/Body/Agent + Orders/Transport | **185 passed**, 9 subtests |
| Gezielte Gesamtregression (33 Suiten) | **425 passed**, 8 skipped |
| Volle Suite vs. `main` | **2627 passed / 29 failed / 79 skipped / 4 errors**; `main`: 2533 / 31 / 126 / 4 — **kein neuer Fehler** |
| E2E (Partner, Bridge, Agent-Order, generiertes Orders-Artefakt) | **149 passed**, 4 subtests |
| Security (Auth, Consent, Privacy, Tenant, M2M, Policy) | **302 passed**, 6 skipped |
| Secret-Scan | keine AKIA-/Private-Key-Muster; nur lokales Test-Secret |
| `compileall` | OK |

Die 29 Suite-Fehler sind vorbestehend (Composite-Lifecycle-Argv, Health-Plane,
Windows-Symlinks, Dependency-Check). Die 4 Collection-Errors sind identisch
auf `main`.

---

## 6. Lizenz und Datenminimierung

- ATS bleibt in Jobsearch (AGPL-3.0-only). **Kein Code kopiert.**
- RIS speichert nur Interface-Metadaten, Contract-Fixtures und Analyseergebnisse.
- Kein Profil-Input, kein `candidateSkills`, keine Roh-CVs im Result-Body.
- Der Live-Call war synthetisch und read-only.

---

## 7. Offene Punkte

| # | Punkt | Status |
|---|---|---|
| 1 | Live-ATS-E2E | **BLOCKIERT** (DynamoDB-Schema-Anomalie in der Lambda) |
| 2 | AWS-seitige Ursache | offen; Tabelle/GSI/Endpoint prüfen; ggf. Support |
| 3 | Orders-Konto `240571105849` | 403, nicht zugreifbar |
| 4 | Cross-Account-Rollen-ARNs | unbekannt |
| 5 | Secret-Provisionierung | nicht erfolgt |
| 6 | Jobsearch-Drift-Monitor | manuell (`check --fetch`) |

**Kein Destroy.** Die Umgebung bleibt für die Untersuchung stehen.

---

## 8. Nächste Entscheidung

1. AWS-seitige Untersuchung der `work-items`-Tabelle (Key-Schema/GSI/Endpoint).
2. Danach denselben Live-E2E wiederholen — ohne Codeänderung.
3. Erst dann Cross-Account- und Secret-Gates.

**Status: DEPLOYED / LOCAL VERIFIED / LIVE-E2E BLOCKED WITH EVIDENCE.**
