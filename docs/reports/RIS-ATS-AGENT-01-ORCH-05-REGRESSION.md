# RIS-ATS-AGENT-01 — ORCH-05 Integration und Regression

**Datum:** 2026-11-16
**Branch:** `feature/ris-dev2-ats-agent-pinned-core-01` (HEAD vor diesem Report: `000b234`)
**Modus:** lokal. Keine Cloud-Tests, keine AWS-Aktion, keine Jobsearch-Mutation.

---

## 1. Ergebnis

| Metrik | Wert |
|---|---|
| **Passed** | **425** |
| **Subtests** | **14** |
| **Skipped** | **8** (bewusst, siehe unten) |
| **Failed** | **0** (mit den dokumentierten Umgebungsvariablen) |

Ohne `ORDERS_TABLE` / `ORDERS_SQS_QUEUE_URL` schlagen 3 Reader-Importtests fehl.
Das ist **vorbestehend** und auf `main` mit einem separaten Worktree
reproduziert:

| Lauf | Ergebnis |
|---|---|
| `main`, ohne Env | 3 failed, 1 passed |
| `main`, mit Env | 4 passed |
| Feature-Branch, mit Env | **425 passed** |

Die Ursache ist `lambda/orders_reader.py`, das beim Import
`ORDERS_TABLE` verlangt — unabhängig von ATS.

---

## 2. Abgedeckte Bereiche

| Bereich | Testdateien |
|---|---|
| ATS-Contract / Body | `test_ats_contract_client.py`, `test_ats_result_body.py`, `test_ats_built_bundle.py` |
| ATS-Agent / Registry / Discovery | `test_ats_domain_agent.py`, `test_jobsearch_agent.py`, `test_multi_agent_ecosystem.py` |
| Addition-Regression | `test_addition_agent.py` |
| AgentBody / Invocation / Status | `test_agent_body.py`, `test_agent_invocation.py`, `test_agent_status_normalization.py`, `test_reference_agent.py` |
| Tenant / Consent / Privacy | `test_tenant_resolution_l03.py`, `test_consent_gate.py`, `test_application_privacy_contract.py`, `test_privacy_capability_planned.py`, `test_p22_agent_capability_contract.py` |
| Agent-Order A04–A07 | `test_agent_order_body.py`, `test_mo_contract_compat.py`, `test_mo_dispatch_handoff.py` |
| Orders / Transport | `test_order_transport_contract.py`, `test_orders_adapter.py`, `test_real_orders_adapter.py`, `test_orders_reader.py`, `test_terraform_agent_transport.py` |
| Runtime / Pipeline | `test_processing_chain.py`, `test_routing.py`, `test_full_pipeline.py` |
| Packaging / Pinning / Drift | `test_lambda_packaging.py`, `test_project_pinning.py`, `test_jobsearch_api_contract.py` |
| Generiertes Orders-Artefakt | `test_generated_module_artifact.py`, `test_lambda_bridge_e2e.py` |

---

## 3. Fail-closed-Matrix

| Anforderung | Nachweis | Ergebnis |
|---|---|---|
| Ungültige Inputs | `FailClosedTest::test_validate_work_rejects_missing_required_field`, `…_missing_job` | PASS |
| Unerlaubte Capability | `…_unknown_capability`, `test_process_work_rejects_unknown_capability`, Routing-Tests | PASS |
| Fremder Tenant | `test_tenant_resolution_l03.py`, Consent-/Privacy-Suiten | PASS |
| Consent / PII | `test_consent_gate.py`, `test_application_privacy_contract.py` | PASS |
| Doppelauslieferung | `TestATSInvocation::test_duplicate_no_second_run` | PASS |
| Stale WorkId | `test_lambda_bridge_e2e.py` (`expectedWorkId`-Bedingungen), `test_order_transport_contract.py` | PASS |
| Hash-Drift | `test_jobsearch_api_contract.py` (Mismatch/Drift/Fail-closed) | PASS |
| Kein CV-Rohtext/Secret im Log | `test_profile_and_description_never_reach_the_log` | PASS |

Der ATS-Agent selbst hält keine Tenant-Daten; die Tenant-Grenze liegt im
bestehenden Runtime-/Eligibility-Pfad und bleibt unverändert.

---

## 4. Echte Artefakte

### RIS-Agent-Bundle

```
python lambda/build_zip.py --bundle all
```

| Artefakt | Größe | SHA-256 |
|---|---|---|
| `terraform/lambda.zip` | 306.070 B, 93 Dateien | `b91b74295f1fd1e51b8d47478bda18532dfdd4f18d1c313eb85bdde36c3079d2` |
| `lambda/dist/orders-reader.zip` | 4.357 B, 1 Datei | `a26c19025eeafa6f08b499d55ba51a1538d298b4356e2d8efe9b334ecc291a56` |

`terraform/lambda.zip` enthält `agents/ats_agent/{agent,contract,result_body,registry}.py`
sowie `agents/__init__.py` und `agents/ats_agent/__init__.py`.

**Beweis am Artefakt, nicht am Quellbaum:** Ein frischer Interpreter bekommt
**nur** das ZIP in `sys.path` und führt Contract-Validierung plus
Body-Projektion aus:

| Prüfung | Ergebnis |
|---|---|
| Import aus dem ZIP | OK |
| `validate_analysis_response` | OK |
| `build_ats_analysis_result_body` | OK |
| Contract-Version | `1.2` |
| Body-Version | `1.1` |
| Score/Match-Status | `50` / `MATCHED, UNKNOWN` |

Test: `tests/test_ats_built_bundle.py` (3 Tests, inkl. Hash-Report).

### Generiertes Orders-Modul

| Artefakt | Wert |
|---|---|
| ZIP | 13 Dateien, `1801e9fbe0d8d7dd70f8cc46699ff2eae6d44c2c590c5472804e022854ead222` |
| Manifest-Commit | `122ec65ac7ab5a044d2b2576ae6b7e4c325246b8` |
| Tests | `test_generated_module_artifact.py` + `test_lambda_bridge_e2e.py` |

---

## 5. Live-Verifikation (read-only, synthetisch)

Ein echter `POST https://mays-jobsearch.vercel.app/api/ats-analysis` mit
synthetischen Job-/Profil-Daten (keine PII) lieferte **HTTP 200** und deckte
drei Abweichungen zum bisherigen Pin auf:

| Befund | Korrektur |
|---|---|
| `analysis.metadata` vorhanden | in Contract 1.2 und Body 1.1 aufgenommen |
| `requirements[].source` vorhanden | in Contract und Body aufgenommen |
| `recommendations[].evidence` ist **String oder `null`**, kein Array | Validator und Contract korrigiert |

Der Live-Dienst war gegenüber `464783b9` weitergelaufen; `main` stand auf
`8456910` (PR #21). Der Pin wurde nach Review auf `8456910` gesetzt.

Ergebnis: **Contract 1.2 / Body 1.1**, Live-Validierung und Projektion laufen
durch. Keine Aussage über Last, SLA oder Produktionsverfügbarkeit.

## 6. Skips (bewusst)

| Anzahl | Grund |
|---|---|
| 6 | `test_privacy_capability_planned.py`: R08-A/B/C sind geplante, nicht implementierte Capabilities |
| 2 | `test_lambda_packaging.py`: Live-Tests brauchen `mayaws`-Credentials |

Keine Cloud-Tests werden als lokal bestanden ausgegeben.

---

## 7. Reproduzierbare Kommandos

```powershell
python lambda/build_zip.py --bundle all

$env:PYTHONPATH='.'
$env:ORDERS_TABLE='orders-baseline'
$env:ORDERS_SQS_QUEUE_URL='https://sqs.eu-central-1.amazonaws.com/262370457690/q'
$env:MO_ORDERS_MODULE='…\generated\ris-dev2-mays-orders'
$env:MO_ORDERS_MODULE_ZIP_SHA256='1801e9fb…'
$env:MO_ORDERS_SOURCE_COMMIT='122ec65a…'
$env:MO_ORDERS_SRC='…\generated\zip-extracted'

python -m pytest <die 33 Testdateien aus Abschnitt 2> -q
# 425 passed, 8 skipped, 14 subtests passed
```

---

## 8. Grenzen

- **Live-Call** gegen `mays-jobsearch` war lesend und synthetisch; keine
  Aussage ?ber Last, SLA oder Produktionsverf?gbarkeit.
- **Kein AWS/ris-dev2**: kein Plan, kein Apply, kein Deployment.
- **Kein vollständiger RIS-Suite-Lauf**: die bekannten, unabhängigen
  Alt-Fehler anderer Suiten bleiben außerhalb dieses Gates.
- Der Bundle-Hash ist umgebungsabhängig (Python/zlib), aber innerhalb
  desselben Builders reproduzierbar.

**Status: ORCH-05 COMPLETE.**
