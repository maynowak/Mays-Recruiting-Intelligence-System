# RIS-DEV2-RELEASE-READINESS-01 — Freigabeprüfung (schreibgeschützt)

**Datum:** 2026-11-25
**Repository:** `maynowak/Mays-Recruiting-Intelligence-System`
**Branch:** `feature/ris-analysis-integration-07`
**HEAD:** `c2841b81db8af303b75d97e3503fcb50579785d8` (== Remote)
**Verdict: BLOCKED — KEIN APPLY**

> **Status-Update 2026-11-25 (nach diesem Bericht):** Der Blocker wurde mit
> `RIS-ORDER-RESULT-CORRELATION-FIX-01` behoben (`f08dfff`); der Reader hält
> die validierte AgentOrder wieder als internes `agentOrder` vor. Neuer Plan:
> `C:\tmp\ris-dev2-correlation-fix.tfplan`, SHA-256
> `2bbf81424b9761712008ef698f5afe5bb6b5ac1db0eaa74220427e8f09b7facd`
> (0/7/0). Ein Apply bleibt bis zur neuen menschlichen Freigabe gesperrt.

Der Plan ist mechanisch sauber (0 Add / 7 Change / 0 Destroy, nur Lambda-Code),
aber die geplanten Lambda-Bundles brechen den ORDER_RESULT-Rückweg für
Agent-Aufträge, die über den neuen RIS-Reader angelegt werden. Der lokale
Produkt-E2E-Test mit dem gepinnten MO-Consumer (`db4f9e7`) schlägt reproduzierbar
fehl (siehe Abschnitt 7). Ein Apply würde Ergebnisse dauerhaft verwerfen.

---

## 1. Prüfkontext

| Punkt | Wert |
| --- | --- |
| Branch / HEAD | `feature/ris-analysis-integration-07` / `c2841b81db8af303b75d97e3503fcb50579785d8` |
| Remote | identisch (`git ls-remote`) |
| Worktree | sauber (nur fremde, unversionierte `commit_msg.txt`) |
| MO-Pin | `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` |
| Terraform | 1.17.0, Provider AWS `~> 6.0` |
| Workspace | `ris-dev2` |
| Account | `262370457690` (`aws sts get-caller-identity`) |
| Region | `eu-central-1` (Plan-Variable, Provider, Backend) |
| Backend | S3 `ris-dev2-tf-state-dev`, Key `env:/ris-dev2/dev/terraform.tfstate`, DynamoDB-Lock `ris-dev2-tf-lock`, `encrypt=true` |
| State-Lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| State-Serial | **69** (287 Ressourcen: 270 managed + 17 data) |

### State-Identität gegen den Plan

- Der Plan wurde **nach** den Commits erzeugt (Plan-Timestamp
  `2026-11-25T06:24:51Z` = 07:24:51 lokal; letzter Commit 07:23:43 lokal).
- `terraform state pull` (nur lesend): Serial 69, Lineage unverändert.
- S3-Objekt `env:/ris-dev2/dev/terraform.tfstate` (nur `head-object`):
  `LastModified = 2026-11-22T11:52:56Z` — **vor** dem Plan, also keine
  State-Schreibung seit dem Plan.
- Plan-`prior_state` gegen den Live-State abgeglichen: 248 Ressourcen
  byte-identisch; 21 Unterschiede sind ausschließlich
  Provider-Schema-Normalisierung (`evaluation_window`, `recursive_logging`,
  `layers [] -> null`) bei No-op-Ressourcen; die 3 Seed-Items sind
  Index-Instanzen derselben Ressource. Keine Drift, keine fehlende Ressource.
- Lock-Tabelle: 2 historische `-md5`-Einträge, **kein aktiver Lock**.

---

## 2. Plandatei

| Punkt | Wert |
| --- | --- |
| Datei | `C:\tmp\ris-dev2-db4-final.tfplan` |
| Größe | 252 576 Bytes |
| SHA-256 | `cc140152071cd2f0e65a51fea869b007ac639a7859f435a5f6bee0c6e0165089` |
| Format | `1.2`, `applyable=true`, `complete=true`, `errored=false` |
| Summary | **0 to add, 7 to change, 0 to destroy**, 0 Replace |

Die Bytes wurden vor der Auswertung neu gehasht; der geforderte SHA-256 stimmt
exakt. Ein zweiter, unabhängig erzeugter Plan (`b0410b85…`) hat einen
byte-identischen gerenderten Diff.

---

## 3. Ressourcen-Diff

Alle sieben Änderungen sind `update in-place` und enthalten **ausschließlich**
`source_code_hash` und `last_modified`:

| # | Adresse | Code-Hash alt → neu |
| --- | --- | --- |
| 1 | `module.agent_transport[0].aws_lambda_function.dispatch_ingress` | `hXdfaF7a…` → `12ehmEOp…` |
| 2 | `module.analysis_runtime.aws_lambda_function.analysis[0]` | `Qgv4YQkg…` → `4miwKAu5…` |
| 3 | `module.lambda.aws_lambda_function.agent` | `hXdfaF7a…` → `12ehmEOp…` |
| 4 | `module.orders_reader[0].aws_lambda_function.reader` | `RkuZH3hP…` → `2PWEDXGy…` |
| 5 | `module.mays_orders[0].module.lambda.aws_lambda_function.handler` | `SN3V5S0H…` → `qnDqqhy2…` |
| 6 | `module.mays_orders[0].module.sqs_worker.aws_lambda_function.worker` | `SN3V5S0H…` → `qnDqqhy2…` |
| 7 | `module.mays_orders[0].module.agent_transport[0].aws_lambda_function.result_consumer` | `SN3V5S0H…` → `qnDqqhy2…` |

**Keine** Änderung an Environment, IAM, Cognito, CloudFront, DNS, DynamoDB,
SQS, Secrets oder Event-Source-Mappings. Die 265 No-op-Ressourcen umfassen
u. a. 50 IAM-, 15 Cognito-, 23 DynamoDB-, 13 SQS-, 2 Secrets-, 4 ESM-,
2 CloudFront-, 88 API-Gateway- und 27 S3-Ressourcen.

---

## 4. Artefakte

| Bundle | SHA-256 | Terraform `source_code_hash` |
| --- | --- | --- |
| `terraform/lambda.zip` | `d767a19843a98c93fbb776a3b011812653cde7ba84b9406c5157ef0d10f8dd06` | `12ehmEOp…` |
| `terraform/analysis-lambda.zip` | `e268b0280bb96c9573eaf33d4d00ac0cdd21b8a01fddd20839782178c70516db` | `4miwKAu5…` |
| `lambda/dist/orders-reader.zip` | `d8f5840d71b20a20d0d9bd987ce40fb5c36e915358aa5598023b8ec2d7521615` | `2PWEDXGy…` |
| `terraform/modules/mays_orders/lambda/dist/lambda.zip` | `aa70eaaa1cb6e01b972dba05893573559e8aa0d945eb5691ce31e079e2521c89` | `qnDqqhy2…` |

- Alle vier Bundles sind **byte-identisch** mit dem jeweiligen `source_code_hash`
  des Plans.
- ZIP-Inhalte stimmen mit den Quellen überein: Agent 115/115, Analysis 113/113,
  Reader 4/4, MO 13/13 Dateien (MO mit deterministischer CRLF→LF-Normalisierung).
  Keine zusätzlichen/entfernten Einträge, keine `__pycache__`.
- Die sieben **deployed** Funktionen wurden nur lesend geladen
  (`aws lambda get-function`): `CodeSha256` und Environment-Key-Sets stimmen
  exakt mit dem Plan-`before` überein. Damit ist der Plan nachweislich gegen den
  realen Deployment-Stand gerechnet.
- Laufzeiten unverändert `python3.14` (Parser `nodejs22.x`), Handler unverändert,
  keine Layer-/Image-Änderung.

### Code-Delta (deployed → geplant)

| Funktion | Geänderte Dateien |
| --- | --- |
| agent, dispatch_ingress, analysis | `agents/orders/agent_order.py` (+183/−3), `agents/orders/real.py` (+99/−2) |
| orders_reader | `agent_order.py` (+183/−3), `orders_reader.py` (+135/−27) |
| MO handler, worker, result_consumer | `order_service.py` (+13/−3), `validation.py` (+82/−15) |

Keine neuen Dateien, keine entfernten Dateien. Der MO-Delta ist ausschließlich
das `orderDescription`-/`orderType`-Feature.

### Environment-Vertrag

- Statisch ermittelte **required**-Env-Mengen sind zwischen deployed und geplant
  **identisch** (kein neuer Pflicht-Key) — geprüft per AST über den jeweiligen
  Import-Graph.
- `AWS_REGION` ist runtime-provided; `LOG_LEVEL` u. a. haben Defaults.
- **Beobachtung (vorbestehend, nicht durch diesen Plan verursacht):**
  `PRIVACY_INTERNAL_SECRET` wird im Privacy-Pfad von `OrderService` benötigt und
  ist in keiner Lambda-Env gesetzt (fail-closed); `ORDER_RESULT_SERVICE_SECRET`
  wird nur vom nicht deployten `result_handler.handler` gelesen.
- **Beobachtung:** `ORDER_DISPATCH_QUEUE_URL` ist in der Handler-Env gesetzt,
  wird aber vom MO-Code nicht gelesen (identisch vor/nach dem Upgrade).

---

## 5. Tests

| Lauf | Ergebnis |
| --- | --- |
| Fokussiert ohne `MO_ORDERS_SRC` (Reader, Gate, Transport, Handoff, Modul, Builder) | **134 passed, 25 skipped, 7 subtests** |
| Cross-Repo-Vertrag mit echtem MO-Validator `db4f9e7` | **5 passed, 4 subtests** |
| Reader→Consumer-E2E mit `MO_ORDERS_SRC=db4f9e7` | **2 failed, 4 passed** (siehe 7) |
| MO-Lambda-Suite `db4f9e7` | **240 Tests OK** |

---

## 6. Vorhandene Live-/E2E-Nachweise

- Live verifiziert sind der aktuelle Deployment-Stand vom 18./22.11.2026
  (ESMs, Result-Queue/DLQ, Consumer-/Reader-Env) — nicht der geplante Code.
- Der letzte dokumentierte lokale Produkt-E2E (Reader → Dispatch → Agent →
  Result → Read-back) ist `tests/test_agent_order_dispatch_e2e.py`; er wurde in
  früheren Läufen ohne `MO_ORDERS_SRC` übersprungen und ist mit dem Pin
  **erstmals ausgeführt und fehlgeschlagen**.
- **Offen (fehlende Live-Nachweise):**
  - keine Live-Invocation der vier neuen RIS-Bundles,
  - kein Live-Roundtrip `orderDescription` (Create → Dispatch → Result),
  - kein Live-Nachweis des Result-Consumers nach dem Upgrade,
  - kein Live-Nachweis für `orderType: generic` im Reader.

---

## 7. BLOCKER — Result-Rückweg bricht

**Symptom** (`tests/test_agent_order_dispatch_e2e.py`, mit `MO_ORDERS_SRC`):

```
result rejected: missing_correlation
AssertionError: {'processed': 1, 'rejected': 0} != {'processed': 0, 'rejected': 1}
```

**Ursache:**

- Der geplante Reader speichert die Agent-Order-Zeile **ohne** Root-Attribut
  `agentOrder` (`lambda/orders_reader.py`, `stored_item`, Zeile 627–654:
  `orderDescription` + `agentOrderFingerprint`, kein `agentOrder`).
- Der deployte **und** der geplante MO-Consumer lesen die Korrelation aber aus
  genau diesem Attribut:
  - `lambda/src/order_service.py:467` → `agent_order = item.get("agentOrder") or {}`
  - `lambda/src/order_service.py:470-473` → `missing_correlation`
  - ebenso `lambda/src/dispatch.py:47` für den MO-eigenen Dispatch-Builder.
- Die deployte Reader-Version (`RkuZH3hP…`) schrieb noch
  `"agentOrder": agent_order`; der geplante Reader (`2PWEDXGy…`) entfernt es.
  Damit ist die Regression eindeutig dem geplanten Reader zuzuordnen.

**Wirkung bei Apply:** ORDER_RESULT-Nachrichten für über den RIS-Reader
angelegte Agent-Aufträge werden als `rejected` konsumiert (kein Retry, kein DLQ),
der Auftrag bleibt ohne Ergebnis; die Read-back-/Status-Kette ist unterbrochen.

**Mögliche Wege (Entscheidung durch Menschen, nicht in diesem Gate umgesetzt):**

1. RIS-Reader persistiert wieder eine MO-kompatible Korrelationsreferenz
   (z. B. Root-`agentOrder` oder ein vom Consumer gelesenes Feld) → RIS-Fix,
   neue Bundles, neuer Plan.
2. MO-Consumer leitet die Korrelation aus `orderDescription` ab → neuer
   MO-Commit, neuer Pin, Modul-Neubau, neuer Plan.
3. Bewusste Scope-Entscheidung, den Result-Rückweg für diesen Rollout
   abzuschalten (nicht empfohlen; widerspricht dem dokumentierten Produkt-E2E).

---

## 8. Weitere Risiken (nicht blockierend, aber Freigabe-relevant)

- **Breaking API-Change:** Der Reader akzeptiert kein Root-`agentOrder` mehr;
  bestehende Clients mit diesem Format erhalten 400. Koordination mit
  API-Konsumenten erforderlich (im RC4-Design beabsichtigt).
- **OrderDescription-Serialisierung:** `serialize_agent_order` begrenzt die
  gesamte serialisierte AgentOrder auf 1024 Zeichen (nicht nur die
  Beschreibung). Große Inputs werden kontrolliert abgelehnt, nicht abgeschnitten.
- **Vorbestehende Privacy-Env-Lücke** (`PRIVACY_INTERNAL_SECRET`) bleibt
  unverändert; Privacy-Operationen bleiben fail-closed.

---

## 9. Nicht ausgeführt

Kein `terraform apply`, keine AWS-Mutation, kein State-Write, kein Main-Merge,
keine Änderung an MO oder am Pin. Der gespeicherte Plan bleibt unverändert
liegen; nach einem Fix ist ein **neuer** Plan und eine neue Freigabe nötig.
