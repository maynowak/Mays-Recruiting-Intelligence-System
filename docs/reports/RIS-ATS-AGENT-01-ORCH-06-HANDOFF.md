# RIS-ATS-AGENT-01 — ORCH-06 Abschluss und Handoff

**Datum:** 2026-11-16
**Branch:** `feature/ris-dev2-ats-agent-pinned-core-01` (gepusht)
**Basis:** `main` = `ae08267`
**Status:** **REVIEWFÄHIG** — kein Merge, kein Deploy, keine AWS-Mutation.

---

## 1. Ergebnis in einem Satz

RIS konsumiert die **eine** ATS-Implementierung aus Mays-Jobsearch über einen
gepinnten HTTP-Contract; der RIS-Agent validiert fail-closed und liefert einen
versionierten `ATSAnalysisResultBody V1.1`. Kein Code wurde kopiert, keine
ATS-Logik dupliziert.

---

## 2. Commit-Tabelle

| Commit | Inhalt |
|---|---|
| `70a2994` | ORCH-00 Baseline, Identität des bestehenden `ats-agent`, Konfliktmatrix |
| `2cc1ab5` | ORCH-01 Jobsearch-API-Snapshot (read-only) |
| `955b694` | Konsolidierungsentscheidung: Jobsearch bleibt die Implementierung |
| `c07332d` | Contract-Pin-Werkzeug (`check` / `refresh`) + Manifest |
| `52da8db` | ORCH-03 Contract-Validierung im Agenten, stabile Fehlercodes |
| `000b234` | ORCH-04 `ATSAnalysisResultBody V1` + Fixtures |
| `2f3463d` | ORCH-05 Regression, Fail-closed-Tests, Artefakt-Test |
| `3559494` | Live-Abgleich: Contract 1.2, Body 1.1, Pin `8456910` |
| *(dieser Report)* | ORCH-06 Handoff |

---

## 3. Quell- und Artefakt-Pins

| Element | Wert |
|---|---|
| Jobsearch-Quelle | `maynowak/mays-jobsearch` |
| Contract-Commit | `8456910a9ae64f51ec4a33ea1e9e82068f82bfff` (2026-11-16) |
| Contract-Version | `1.2` |
| Result-Body-Version | `1.1` |
| Endpoint | `POST /api/ats-analysis` |
| Lizenz | AGPL-3.0-only, **kein Code kopiert**, Service-Grenze |

Datei-Hashes im Manifest:

| Datei | SHA-256 |
|---|---|
| `api/ats-analysis.mjs` | `575020e209f3fa73a14e6a7b5bdfba0ec10a55cf27170d07d662131e0c9fc611` |
| `api/_lib/ats.mjs` | `88e06887151ff464aaf9b78cb845468911a916a3dad96f2fb188d96c437fc079` |
| `api/_lib/filter.mjs` | `4599583cf63fdc05edb8028111754c753e7a0e027ce3724e8e5a6476db2eb259` |

Gebaute Artefakte:

| Artefakt | Größe | SHA-256 |
|---|---|---|
| `terraform/lambda.zip` (RIS-Agent, 93 Dateien) | 306.070 B | `b91b74295f1fd1e51b8d47478bda18532dfdd4f18d1c313eb85bdde36c3079d2` |
| `lambda/dist/orders-reader.zip` | 4.357 B | `a26c19025eeafa6f08b499d55ba51a1538d298b4356e2d8efe9b334ecc291a56` |
| Generiertes Orders-Modul-ZIP | 29.417 B | `1801e9fbe0d8d7dd70f8cc46699ff2eae6d44c2c590c5472804e022854ead222` |

---

## 4. Testmatrix

| Bereich | Ergebnis |
|---|---|
| Gesamte gezielte Regression (33 Suiten) | **425 passed**, 8 skipped, 14 subtests |
| ATS-Contract / Body / Agent | PASS |
| Registry / Discovery / Eligibility | PASS |
| AgentBody / WorkItem / Routing | PASS |
| Tenant / Consent / Privacy | PASS |
| Agent-Order A04–A07 | PASS |
| Orders / Transport | PASS |
| Packaging / Pinning / Drift | PASS |
| Generiertes Orders-Artefakt + Bridge | PASS |
| Addition-Regression (`math.add`) | PASS |

Skips: 6 geplante R08-Privacy-Capabilities, 2 Live-Packaging-Tests, die das
Orders-Konto (`mayaws`) bräuchten. **`mayaws` wurde nicht verwendet.**

Umgebungsbefund: Ohne `ORDERS_TABLE`/`ORDERS_SQS_QUEUE_URL` scheitern 3
Reader-Importtests; auf `main` reproduziert und daher vorbestehend.

---

## 5. Schema- und UI-Parität

| Jobsearch/UI-Feld | RIS-Body |
|---|---|
| `analysis.score` | `analysis.score` |
| `analysis.keywordCoverage.overall` | `analysis.keywordCoverage.overall` |
| `requirementCoverage`, `profileEvidenceCoverage` | übernommen |
| `roleMatch`, `analysisStatus`, `basis` | übernommen |
| `metadata` (Titel, Tokens, Sprache, WorkMode, JobTypes, ContractType) | `analysis.metadata` |
| `requirements[].source` | `requirements[].source` |
| `matches` (`MATCHED`/`PARTIAL`/`UNKNOWN`) | übernommen |
| `recommendations[].evidence` (String/null) | übernommen |
| `ai` (Default aus, Consent-Gate) | übernommen |

Nicht enthalten: Profil-Input, `candidateSkills`, Tokenizer-Interna
(`normalized`, `explicitness`), Roh-CVs, Secrets. PDF-/DOCX-Extraktion ist
nicht Teil des Contracts und wurde nicht erfunden.

---

## 6. Live-Verifikation

Ein read-only `POST` mit synthetischen Daten gegen
`https://mays-jobsearch.vercel.app/api/ats-analysis` lieferte HTTP 200.
Dabei wurden drei Abweichungen gefunden und korrigiert:

1. `analysis.metadata` war vorhanden.
2. `requirements[].source` war vorhanden.
3. `recommendations[].evidence` ist String/`null`, kein Array.

Der Pin wurde nach Review von `464783b9` auf `8456910` gehoben. Keine Aussage
über Last, SLA oder Produktionsverfügbarkeit.

---

## 7. Änderungen im RIS-Branch

| Datei / Bereich | Änderung |
|---|---|
| `agents/ats_agent/contract.py` | Validator für Contract 1.2 |
| `agents/ats_agent/result_body.py` | `ATSAnalysisResultBody` 1.1 |
| `agents/ats_agent/agent.py` | Fehlercodes, Body, Metriken, Log-Hygiene |
| `installer/jobsearch_api_contract.py` | `check` / `refresh`, fail-closed |
| `docs/contracts/*` | API-Contract, Result-Body, Manifest |
| `tests/*` + `tests/fixtures/ats_result_body/*` | 10+ neue Fälle, 5 Fixtures |
| `docs/reports/RIS-ATS-AGENT-01-*` | Baseline, Snapshot, Konsolidierung, Regression |

Unverändert: `agents/orders/*`, `agents/addition_agent/*`, `agentOrder` V1,
Transport V1, OrdersPort.

---

## 8. Offene Punkte

| # | Punkt | Status |
|---|---|---|
| 1 | **ris-dev2-Deployment** | nicht erfolgt; State 0 Ressourcen; kein Plan/Apply |
| 2 | Live-Aufruf des RIS-Agenten in AWS | nicht erfolgt |
| 3 | Jobsearch-Last/SLA | nicht bewertet |
| 4 | Drift-Überwachung | manuell (`check --fetch`); kein CI-Job |
| 5 | xrepo-Task `MAYS-XR-ATS-001` | nicht angelegt; anderer Agent aktiv |
| 6 | Orders-Konto `240571105849` | 403, nicht zugreifbar |
| 7 | Cross-Account-Rollen-ARNs | unbekannt |
| 8 | Secret-Provisionierung | nicht erfolgt |

---

## 9. Getrennte AWS-Gates (nicht Teil dieses Auftrags)

1. **ris-dev2-Plan** mit dem ATS-Branch — nur Plan, keine Freigabe.
2. **Apply** — 191 Creates wären ein vollständiger RIS-Neuaufbau; separat
   freizugeben.
3. **Orders-Konto** — Zugang und echte Rollen-ARNs klären.
4. **Live-E2E** — erst nach 1–3 und mit echtem Secret.

Aus diesem Report folgt **keine AWS-Freigabe**.

---

## 10. Empfohlener nächster Schritt

Ein separater Auftrag **„RIS-ATS-AGENT-01 ris-dev2 Plan"**:

- Branch auschecken, `terraform init -backend=false`, `validate`,
- Plan gegen `ris-dev2` mit Default-Profil (`devnemo`) und Projektname
  `ris-dev2`,
- Plan-Diff prüfen (keine Deletes/Ersetzungen),
- **kein Apply**.

**Status: ORCH-06 COMPLETE. Branch reviewfähig, kein Merge.**
