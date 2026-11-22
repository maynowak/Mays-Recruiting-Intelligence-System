# RIS-ATS-AGENT-01 — ris-dev2-Plan und Verifikation

**Datum:** 2026-11-16
**Branch:** `feature/ris-dev2-ats-agent-pinned-core-01`
**Profil:** `default` (devnemo) · **Projekt:** `ris-dev2` · **Region:** `eu-central-1`
**Modus:** Plan + lokale Tests. **Kein Apply, kein Deploy, keine AWS-Mutation.**

---

## 1. Plan-Ergebnis

| Element | Wert |
|---|---|
| Workspace | `ris-dev2` |
| Backend | `s3://ris-dev2-tf-state-dev`, Key `dev/terraform.tfstate`, Prefix `env:` |
| Lock | `ris-dev2-tf-lock` |
| Projektname | `ris-dev2` |
| Plan | **227 to add, 0 to change, 0 to destroy** |
| Data-Reads | 6 |
| Plan-Datei | `ris-dev2-ats-plan-2026-11-16.tfplan` |
| Plan SHA-256 | `73953f06a25f63488d1a04b40f7b31782165c1235fe3e8798dff0bd9c8ce10ee` |
| Plan-JSON SHA-256 | `8f79f9a2028fd5a996686b18b25823253b6a22361502aa6d206e3c38f3ad5d10` |

Der State ist leer (ris-dev2 am 2026-11-09 abgebaut). 227 Creates sind daher
eine **vollständige Neuinstallation der RIS-Plattform**, nicht ein Delta.

### Kein zerstörerischer Diff

| Aktion | Anzahl |
|---|---|
| create | 227 |
| update | 0 |
| delete | 0 |
| replace | 0 |
| read (data) | 6 |

### Ressourcen-Schwerpunkte

| Typ | Anzahl |
|---|---|
| `aws_apigatewayv2_route` | 78 |
| `aws_iam_role_policy` | 24 |
| `aws_dynamodb_table` | 20 |
| `aws_cloudwatch_metric_alarm` | 13 |
| `aws_cognito_user_group` | 8 |
| `aws_lambda_function` | 6 |
| `aws_sqs_queue` | 6 |
| `aws_s3_bucket` | 5 |

Modul-Sichten:

| Modul | Creates |
|---|---|
| `module.mays_orders` | 25 |
| `module.orders_reader` | 10 |
| `module.agent_transport` | **0** (`enable_agent_transport = false`, default-off) |

Das ATS-Feature selbst ist **code-only**; es erzeugt keine zusätzliche
Infrastruktur. Die ATS-Routen der Plattform sind bereits Teil des API-Moduls.

---

## 2. Vorgehen

1. Branch ausgecheckt, Worktree sauber.
2. `terraform fmt -check -recursive` → Exit 0.
3. `terraform init -backend=false` + `terraform validate` → Exit 0.
4. Orders-Modul aus dem gepinnten Builder gebaut
   (`module-builder.manifest.json` → `source.commit = 122ec65…`, 8 Module).
5. Root erneut `init -backend=false` + `validate` → Exit 0.
6. `terraform init -reconfigure` mit dem ris-dev2-Backend.
7. `terraform plan -var="project_name=ris-dev2"` + die drei ZIP-Pfade.
8. Plan als JSON ausgewertet (Aktionen, Typen, Module).
9. Worktree restauriert: Lockfile zurückgesetzt, generiertes Orders-Modul
   entfernt, Platzhalter-`variables.tf` wiederhergestellt.

Kein Apply. Die Plan-Datei liegt außerhalb des Repositories.

---

## 3. Volle Regression

Vergleich Feature-Branch gegen `main` mit identischer Umgebung:

| Lauf | passed | failed | skipped | errors | subtests |
|---|---|---|---|---|---|
| **Feature** | **2627** | **29** | 79 | 4 | 434 |
| `main` (Baseline) | 2533 | 31 | 126 | 4 | 425 |

**Es gibt keinen neuen Fehler.** Die 29 Feature-Fehler sind eine Teilmenge der
31 Main-Fehler. Zwei Fehler existieren nur auf `main`:

- `test_lambda_packaging::test_c_exclusions` (auf dem Branch behoben),
- `test_ats_agent::test_analyze_job_calls_api` (auf dem Branch sauber
  übersprungen, weil `requests` lokal fehlt).

Die verbleibenden 29 sind vorbestehend: Composite-Lifecycle-Argv,
Health-Plane, Platform-Handler-Importpfad, Windows-Symlink-Guards in
`test_ris_admin_credentials`, Dependency-Check. Die 4 Collection-Errors sind
identisch auf `main` (`ConsentContext`, `mock_aws`, fehlendes `requests`).

### ATS-Unit-Tests

Die drei alten ATS-Unit-Tests wurden auf den neuen Contract/Body angepasst:

```text
tests/unit/ats_agent: 19 passed, 1 skipped
```

---

## 4. E2E

| Suite | Ergebnis |
|---|---|
| Partner-Addition-Demo, Partner-E2E, Lambda-Bridge, Agent-Order, generiertes Orders-Artefakt, MO-Contract, Transport | **149 passed, 4 subtests** |
| Live-ATS (`POST /api/ats-analysis`, synthetisch) | HTTP 200, Contract 1.2, Body 1.1 |
| Addition-Pfad | `17 + 25 = 42` durch beide Lambda-Entrypoints |
| Orders-Artefakt | ZIP `1801e9fb…ad222`, 13 Dateien |

---

## 5. Security

| Suite | Ergebnis |
|---|---|
| Auth-Boundary, Authorization-Context, Partner-Security, Browser-Fail-closed, Consent, Privacy, Credential-Management, Tenant, M2M, API-Security, Policy-Gate, Addition-Authorization | **302 passed, 6 skipped, 13 subtests** |

Secret-Scan (getrackte Dateien):

| Befund | Bewertung |
|---|---|
| `tests/integration/dynamodb_local_support.py`: lokales Test-Secret | bewusst, kein Produktions-Secret |
| `jobsearch/partner_profile_repository.py`: `getattr(creds, "secret_key")` | Laufzeit-Credential, kein literaler Key |
| AKIA-/Private-Key-Muster | **keine** |

Bundle-Prüfung: keine `.env`, `.pem`, `.key` oder `.p12`-Einträge.
`compileall agents installer lambda` → OK.

Zusätzlich belegt: `test_profile_and_description_never_reach_the_log` (kein
CV-Rohtext im Log) und die Contract-Fail-closed-Fälle.

---

## 6. Was das bedeutet

| Stufe | Status |
|---|---|
| Lokale Integration | **JA** |
| Generiertes Modul getestet | **JA** |
| AWS-Infrastruktur planverifiziert | **JA** (227/0/0) |
| Live-E2E in AWS | **NEIN** |

Der Plan ist **nicht freigegeben**. 227 Creates bedeuten einen vollständigen
Neuaufbau; das braucht eine eigene, ausdrückliche Entscheidung.

---

## 7. Offene Gates

1. **Apply-Freigabe** für ris-dev2 (227 Creates) — nicht erteilt.
2. **Live-E2E** nach Apply (Agent-Invoke, Jobsearch-Call aus Lambda).
3. **Orders-Konto `240571105849`** — 403, nicht zugreifbar.
4. **Cross-Account-Rollen-ARNs** — unbekannt.
5. **Secret-Provisionierung** (`result_hmac`) — nicht erfolgt.
6. **Drift-Monitor** für den Jobsearch-Contract — derzeit manuell.

---

**Status: RIS-DEV2 PLAN VERIFIED / FULL REGRESSION NO NEW FAILURES /**
**E2E AND SECURITY GREEN (LOCAL) / NO APPLY.**
