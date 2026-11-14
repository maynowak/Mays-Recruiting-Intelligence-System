# MO-RIS-ORDERS-MODULE-REBUILD-01 — Reproduzierbares Orders-Modul

**Datum:** 2026-11-14
**Modus:** Lokale Implementierung, Tests, Audit, Git-Commits. Keine AWS-Mutation,
kein Apply/Destroy, keine State-Migration, kein RC-Upgrade, kein Merge.
**Ergebnis:** **GENERATED ORDERS MODULE — LOCAL INTEGRATION VERIFIED**

---

## M00 — Ausgangslage und Fehlerursache

| Element | Vorher | Nachher |
|---|---|---|
| Builder-Pin (RIS) | `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d` | `122ec65ac7ab5a044d2b2576ae6b7e4c325246b8` |
| Builder-Pin-Datei | `installer/mays-orders-builder.pinned.json` | dito, aktualisiert |
| Hartkodierter Pin | `installer/build_mays_orders_module.py:107` | dito, aktualisiert |
| `source.commit` im Manifest | `"unknown"` | voller 40-stelliger SHA |
| Lambda-ZIP | 7 Dateien (Basisstand) | 13 Dateien (vollständige Integration) |
| Modul-Zusammensetzung | 7 Module | 8 Module (`agent_transport`) |
| DynamoDB-Indizes | `gsi1`, `gsi2` | + `gsi3` (Ownership) |
| Handler | nur `index.handler` | + `result_consumer.handler` |

### Ursachen (belegt)

1. **Kopiertes statt gebautes Artefakt.** `build_module()` kopierte
   `lambda/dist/lambda.zip` unverändert. Der Pin `1dbb0cb` ist kein Vorfahr der
   Feature-Linie und enthält in `lambda/src/` nur die sieben Basisdateien.
2. **Keine Provenienz.** `git rev-parse --short HEAD` wurde mit
   `except: "unknown"` abgefangen; ein nicht reproduzierbarer Build galt als
   gültig.
3. **Unvollständiges Preset.** `agent_transport` fehlte in Katalog und
   `orders-service`-Preset; damit fehlten Queue, DLQ, Secret und Result-Consumer.
4. **`terraform validate` defekt.** Der Builder ergänzte `count` am
   `cognito`-Modul, ersetzte die direkten Referenzen aber nur im `api`-Block.
   Der `lambda`-Block und die Outputs lasen weiterhin `module.cognito.*` und
   scheiterten an `Can't access attributes on a list of objects`.
5. **Nicht reproduzierbares ZIP.** `ZipFile.write()` stempelte die mtime jedes
   Eintrags; zusätzlich unterschied sich der Inhalt zwischen
   `core.autocrlf=true` (CRLF) und `false` (LF).

---

## M01/M02 — Korrigierter Source-Pin und Manifest

- **Gewählter Source-Commit:** `122ec65ac7ab5a044d2b2576ae6b7e4c325246b8`
  (Branch `feature/mo-agent-order-body-01`, auf Basis `9627eb2`, keine
  RC3-/RC4-Migration).
- Der Commit enthält A04–A07 **und** die Builder-Korrekturen.
- Manifest schreibt `source.repo` + vollen `source.commit`; bei fehlendem Commit
  bricht der Build fail-closed ab (`_fail`), es gibt kein `"unknown"` mehr.

Relevante Orders-Commits:

| Commit | Inhalt |
|---|---|
| `48659cf` | Lambda-ZIP aus der Quelle bauen, voller SHA im Manifest, `agent_transport` im Preset, cognito-Referenzen modus-sicher |
| `4a33f4d` | deterministische ZIP-Einträge (feste Zeitstempel/Modus) |
| `446dbe7` | reproduzierbares ZIP als getracktes Artefakt |
| `122ec65` | Zeilenenden-Normalisierung im ZIP + finales Artefakt |

---

## M03 — Erzeugtes Modul

- Pfad: `…\Temp\opencode\generated\ris-dev2-mays-orders`
- Preset: `orders-service`
- Module (8): `agent_transport`, `api`, `cognito`, `dynamodb`, `iam`,
  `lambda`, `sqs`, `sqs_worker`
- **ZIP-SHA-256:** `1801e9fbe0d8d7dd70f8cc46699ff2eae6d44c2c590c5472804e022854ead222`
- ZIP-Inhalt (13):

```
agent_order.py  dispatch.py  errors.py  identity.py  index.py
order_service.py  order_types.py  result_consumer.py  result_envelope.py
result_handler.py  sqs_handler.py  state_machine.py  validation.py
```

Vollständige Dateiliste des Moduls (42 Dateien):

```
README.md
lambda/build_zip.py
lambda/dist/lambda.zip
lambda/src/{agent_order,dispatch,errors,identity,index,order_service,
            order_types,result_consumer,result_envelope,result_handler,
            sqs_handler,state_machine,validation}.py
main.tf
module-builder.manifest.json
modules/agent_transport/{lambda.tf,main.tf}
modules/api/{main.tf,outputs.tf,variables.tf}
modules/cognito/{main.tf,outputs.tf,variables.tf}
modules/dynamodb/{main.tf,outputs.tf,variables.tf}
modules/iam/{main.tf,outputs.tf,variables.tf}
modules/lambda/{main.tf,outputs.tf,variables.tf}
modules/sqs-worker/{iam.tf,main.tf,variables.tf}
modules/sqs/main.tf
outputs.tf
variables.tf
versions.tf
```

---

## M04 — Terraform-Vertrag

| Prüfung | Befund |
|---|---|
| `gsi3` (Ownership) | vorhanden: `gsi3`, `gsi3pk`, `gsi3sk` |
| `agent_transport` | `count = var.enable_agent_transport ? 1 : 0` (default-off) |
| Result-Consumer | `handler = "result_consumer.handler"`, ESM auf Ergebnis-Queue |
| SQS/DLQ | `aws_sqs_queue.results` + `results_dlq` + Redrive-Policy |
| Secret | `aws_secretsmanager_secret.result_hmac`, Wert **out-of-band** |
| IAM | Least Privilege: Tabelle, Secret (nur `GetSecretValue`), Queue-Consume; KMS nur bei gesetztem Key |
| Cross-Account | `Principal = { AWS = var.ris_result_producer_role_arns }`, Default `[]` (fail-closed) |
| Retail | unverändert; `index.handler`-Pfad, SQS-Worker, API bleiben bestehen |
| Cognito MANAGED/EXTERNAL | `external_cognito` default `null`; alle Referenzen modus-sicher (`one(splat)`/locals) |
| `terraform fmt -check -recursive` | Exit 0 |
| `terraform validate` | Exit 0 |

`enable_agent_transport` bleibt **default `false`**. Die Integration ist im
Modul vorhanden, aber nicht automatisch aktiv.

---

## M05 — Tests gegen das erzeugte Artefakt

Neuer Test: `tests/test_generated_module_artifact.py` (RIS). Er liest
**ausschließlich** das gebaute Modul, nie `lambda/src` des Quell-Repos.

| Test | Ergebnis |
|---|---|
| Manifest nennt vollen Source-Commit | PASS |
| ZIP-CRC-Integrität (`testzip`) | PASS |
| Exakte 13-Datei-Menge | PASS |
| ZIP-SHA-256 == Manifest == Pin | PASS |
| Import **aller 13 Module** aus dem ZIP (frischer Interpreter, nur ZIP im Pfad) | PASS |
| `handler`-Callable in `index`, `result_consumer`, `result_handler`, `sqs_handler` | PASS |
| `gsi3` im DynamoDB-Modul | PASS |
| `agent_transport` default-off + Result-Consumer + Queue/DLQ/Secret | PASS |
| Cognito MANAGED/EXTERNAL auswertungssicher (keine nackte `module.cognito.*`-Referenz) | PASS |

**Ergebnis: 8 passed.** Geladener Pfad und Hash werden im Testreport ausgegeben:

```
[artifact] …\generated\ris-dev2-mays-orders\lambda\dist\lambda.zip
[artifact] sha256=1801e9fbe0d8d7dd70f8cc46699ff2eae6d44c2c590c5472804e022854ead222
```

### A07-E2E gegen das Artefakt

Das ZIP wurde entpackt und `MO_ORDERS_SRC` auf den **entpackten
Deployment-Inhalt** gesetzt (nicht auf `lambda/src`):

```
Partner A → generiertes Orders-Artefakt → persistierter agentOrder V1
→ A05 Dispatch → RIS Generic Transport V1 → Addition-Agent
→ 17 + 25 = 42 → A06 Result-Consumer → autorisierter Orders-GET = 42
```

| Suite | Ergebnis |
|---|---|
| `test_agent_order_body.py` (43) | PASS |
| `test_mo_contract_compat.py` (9) | PASS |
| `test_partner_e2e_real.py` (16) | PASS |
| `test_lambda_bridge_e2e.py` (5) | PASS |
| **Summe** | **73 passed** |
| `test_addition_agent.py` + `test_order_transport_contract.py` + `test_terraform_agent_transport.py` | **93 passed** |

Fakes ausschließlich an Infrastrukturgrenzen (SQS/DynamoDB/AWS-Clients).

---

## M06 — Reproduzierbarkeit

| Nachweis | Ergebnis |
|---|---|
| Zwei Builds aus demselben Arbeitsbaum | identische ZIP-SHA (`1801e9fb…`) |
| Frischer Clone mit `core.autocrlf=true` (CRLF-Quellen) | ZIP-SHA `1801e9fb…` |
| Frischer Clone mit `core.autocrlf=false` (LF-Quellen) | ZIP-SHA `1801e9fb…` |
| Pinned-Installer-Pfad (Clone auf `122ec65`) | ZIP-SHA `1801e9fb…`, 13 Dateien, `validate` OK |
| Manifest-Commit == Pin | PASS |
| Imports nur aus dem Paket auflösbar | PASS |
| Keine Datei aus einem fremden Checkout | PASS (Build liest `source_root`) |
| Terraform-Syntax | PASS (`fmt`/`validate`) |

Damit ist das ZIP **über Checkout-Konfigurationen hinweg byte-identisch**. Die
einzige variable Manifest-Angabe ist `generated_at` (Build-Zeitpunkt); sie
geht nicht in das ZIP ein.

---

## M07 — Retail und Cross-Repo

- Orders-Lambda-Suite: **217 Tests OK** (`python -m unittest discover -s tests`).
- Modul-Builder-Suite: **77 passed, 13 failed** — die 13 Fehler sind
  vorbestehende Windows-Pfadtrennungs-Erwartungen (`modules/dynamodb/main.tf`
  vs. `modules\dynamodb\main.tf`) und traten bereits vor dieser Änderung auf.
  Der `OrdersService`/`ExternalCognito`-Block: 24 passed, 1 derselben
  bekannten Layout-Fehler.
- Retail-Orders funktionieren weiter (217 Tests, keine Löschungen im
  Feature-Diff).
- Agent-Orders gehen nicht an den Retail-Worker; Owner-Isolation fail-closed;
  `expectedWorkId` serverseitig gebunden; Result idempotent (A04–A07-Tests).

---

## Grenzen

1. **Das Modul wird lokal generiert**, nicht als Git-Modul veröffentlicht.
   Reproduzierbar ist es über den gepinnten Builder-Commit.
2. **Orders-AWS-Konto `240571105849` ist nicht zugreifbar** (403 auf
   `mays-orders-tfstate-central-240571105849`). Orders-Plan/Apply bleibt
   unverifiziert.
3. **Cross-Account-Rollen-ARNs fehlen**; Queue-/Secret-Policies bleiben
   `Principal = []` (fail-closed).
4. **Secret-Wert** ist nicht provisioniert (`result_hmac` ist nur der Container).
5. **Live-E2E** wurde nicht ausgeführt.
6. ZIP-Reproduzierbarkeit gilt für dieselbe Python/zlib-Version; andere
   Kompressorversionen können abweichende Bytes erzeugen (nicht getestet).

---

## Vier Stufen — getrennt

| Stufe | Status |
|---|---|
| 1. Lokale Integration vollständig | **JA** |
| 2. Generiertes Modul integrationsgetestet | **JA** (lokal, gegen das ZIP) |
| 3. AWS-Infrastruktur planverifiziert | RIS ja / Orders **nein** (403) |
| 4. Live E2E | **NEIN** |

Stufe 2 ist ausdrücklich **kein** Nachweis für Stufe 3 oder 4. Aus diesem
Ergebnis folgt **keine AWS-Freigabe**.

---

## Status

**`GENERATED ORDERS MODULE — LOCAL INTEGRATION VERIFIED`**

Nicht erfüllt und daher ausdrücklich offen: Orders-Konto-Zugriff,
Cross-Account-Rollen-ARNs, Secret-Provisionierung, Live-E2E.
