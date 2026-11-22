# RIS-DEV2 — OWNERSHIP & DYNAMODB FORENSIC-01

**Datum:** 2026-11-16
**Modus:** read-only. Kein Apply, Destroy oder Rollback.
**Konto:** `262370457690` (default/devnemo) · **Region:** `eu-central-1`
**Workspace:** `ris-dev2`

---

## A — Projektgrenzen

### A.1 Governance und Identität

- `AGENTS.md` und `docs/AI_AUDITLOG.md` gelesen.
- `aws sts get-caller-identity`:
  - Account `262370457690`
  - User `arn:aws:iam::262370457690:user/devnemo`

### A.2 Workspace und State

| Element | Wert |
|---|---|
| `TF_WORKSPACE` | `ris-dev2` |
| State-Key | `s3://ris-dev2-tf-state-dev/env:/ris-dev2/dev/terraform.tfstate` |
| Serial | **58** |
| Ressourcen | **243** |
| Lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Terraform | 1.17.0 |

### A.3 Effektiver Orders-Lifecycle

Aus dem **tatsächlich angewendeten** Plan (`ris-dev2-ats-plan-v2.json`):

```json
{"project_name": "ris-dev2", "environment": "dev", "orders_lifecycle": "managed"}
```

Der State enthält **33** Ressourcen unter `module.mays_orders`. RIS betreibt
damit eine **eigene** Orders-Instanz, keine externe.

| Orders-Ressource | Wert |
|---|---|
| Tabelle | `ris-dev2-mays-orders` (Konto `262370457690`) |
| Queue | `ris-dev2-mays-orders-orders-queue` |
| Handler | `ris-dev2-mays-orders-handler` |
| SQS-Worker | `ris-dev2-mays-orders-sqs-worker` |
| Orders-Reader-Env | `ORDERS_TABLE=ris-dev2-mays-orders`, eigene Queue-URL |

### A.4 Fremde Referenzen

| Prüfung | Ergebnis |
|---|---|
| `240571105849` im State | **0** |
| `mays-ris` im State | 65 Vorkommen — **ausschließlich `Maker`-Tags** |
| `mays-orders` im State | 188 Vorkommen — **ausschließlich `ris-dev2-mays-orders`** |
| `mays-ris-dev-*`-Ressourcen | **keine** |
| Lambda-Umgebungsvariablen | keine `mays-ris`-/`240571105849`-Werte |
| IAM `PermissionsBoundary` (alle `ris-dev2`-Rollen) | **None** |
| IAM-Trust-Policies mit Fremd-ARN | keine |
| SQS-Policies `Principal: "*"` | keine (Orders-Queue: `arn:aws:iam::262370457690:root`) |
| SQS-Policies mit `240571105849` | keine |

Die `Maker`-Tags sind Metadaten aus dem Template, keine Projekt- oder
Account-Grenze. Der **Projektname** ist `ris-dev2` (Ressourcen, Tags, State,
Workspace).

### A.5 Modul-Source-Pin vs. AWS-Ownership

| Ebene | Wert |
|---|---|
| Modul-Source-Pin | `maynowak/mays-order-aws` @ `dad69ea28e8b952a8e76e9dfb4fb163f7a979b52` |
| RIS-Pin-Dateien | `installer/mays-orders-builder.pinned.json`, `PINNED_COMMIT` |
| AWS-Ownership | Account `262370457690`, Workspace `ris-dev2` |

Der Git-Pin ist ein **Build-Input**. Er begründet keine Eigentums- oder
Account-Zugehörigkeit der AWS-Ressourcen.

---

## B — DynamoDB-Forensik

### B.1 Tabelle

`ris-dev2-dev-work-items` (Konto `262370457690`):

| Element | Wert |
|---|---|
| KeySchema | `workId` — HASH, Typ **S** |
| GSI `gsi-user` | HASH `userId`, RANGE `status`, **ACTIVE** |
| GSI `gsi-status` | HASH `tenantId`, RANGE `status`, **ACTIVE** |
| Resource-Policy | keine |
| Status | ACTIVE |

### B.2 Tatsächlich verwendete Tabelle und Endpoint der Lambda

Aus dem CloudWatch-Log der fehlerhaften Invocation:

```
table=ris-dev2-dev-work-items
ddb_endpoint=https://262370457690.ddb.eu-central-1.amazonaws.com/
region=eu-central-1
```

Also dieselbe Tabelle und Region wie beim Admin-Call. Der auffällige
**account-based Endpoint** (`262370457690.ddb.…`) zeigt eine neuere
boto3/botocore-Generation der Lambda-Runtime (python3.14).

### B.3 Key unmittelbar vor der Serialisierung

Der Code übergibt:

```python
Key = {"workId": {"S": "probe-key"}}
```

Das ist korrektes DynamoDB-JSON für `workId` (S).

### B.4 Tatsächlich gesendete Requests — der entscheidende Unterschied

**Lambda (fehlerhaft, Resource-Client):**

```json
{"TableName": "ris-dev2-dev-work-items",
 "Key": {"workId": {"M": {"S": {"S": "probe-key"}}}}}
```

**Admin/Plain-Client (erfolgreich):**

```json
{"TableName": "ris-dev2-dev-work-items",
 "Key": {"workId": {"S": "probe-key"}}}
```

Der Lambda-Request ist **doppelt** verpackt: `M` um ein bereits serialisiertes
`{"S": …}`. DynamoDB antwortet deshalb korrekt mit:

```
ValidationException: The provided key element does not match the schema
```

### B.5 Key-Typen und Werte (ohne PII)

| Key | Typ | Beispiel |
|---|---|---|
| `workId` (Arbeit) | `S` | `probe-key`, `e2e-ats-…` |
| `workId` (Fence) | `S` | `erasure-fence#<64 hex>` (78 Zeichen) |
| `tenantId` | `S` | synthetisch `tenant-e2e-…` |
| `userId` | `S` | synthetisch `user-e2e-…` |

Keine personenbezogenen Daten in den Key-Attributen.

### B.6 Client und Serializer

| Lauf | Client | Serializer-Verhalten |
|---|---|---|
| Lambda (vor Fix) | `boto3.resource("dynamodb").Table(...).meta.client` | **Document-Transformation** aktiv; DynamoDB-JSON wird als `M` erneut verpackt |
| Lambda (nach Fix) | `_ddb_transaction_client()` → plain `boto3.client("dynamodb")` | korrekt; `{"S": …}` bleibt `{"S": …}` |
| Admin/lokal | plain `boto3.client("dynamodb")`, boto3 1.44.1 | korrekt |

Die Lambda-Runtime ist `python3.14`; die exakte boto3-Version wird von der
Runtime verwaltet und ist ohne Codeausführung nicht abfragbar. Das
serialisierte Body-Log beweist jedoch das Resource-Transformationsverhalten.

### B.7 Vollständiger TransactWriteItems-Aufbau

Der Fence-Pfad baut zwei Operationen:

```json
[
  {"ConditionCheck": {
    "TableName": "ris-dev2-dev-work-items",
    "Key": {"workId": {"S": "erasure-fence#<64 hex>"}},
    "ConditionExpression": "attribute_not_exists(workId)"
  }},
  {"Put": {
    "TableName": "ris-dev2-dev-work-items",
    "Item": {
      "workId": {"S": "e2e-ats-…"},
      "tenantId": {"S": "tenant-e2e-…"},
      "userId": {"S": "user-e2e-…"},
      "requestedBy": {"S": "user-e2e-…"},
      "idempotencyKey": {"S": "key-…"},
      "type": {"S": "ats_process"},
      "capability": {"S": "analyze.job"},
      "agentId": {"S": "ats-agent"},
      "processing_id": {"S": "…"},
      "execution_id": {"S": "…"},
      "attempt_id": {"S": "…#1"},
      "parent_id": {"S": ""},
      "sequence_no": {"N": "1"},
      "attempt_no": {"N": "1"},
      "body_id": {"S": "1.0.0"},
      "body_version": {"S": "1.0.0"},
      "runtime": {"S": "python3.14"},
      "execution_profile": {"S": "LAMBDA"},
      "status": {"S": "RUNNING"},
      "createdAt": {"S": "…"},
      "updatedAt": {"S": "…"}
    },
    "ConditionExpression": "attribute_not_exists(workId)"
  }}
]
```

Beide Keys sind formal korrekt. Der Fehler entsteht **vor** dem Absenden durch
die doppelte Serialisierung des Resource-Clients.

---

## C — Root Cause, Fix und Verifikation

### C.1 Root Cause

**Nicht AWS.** Der Fehler ist ein Client-/Serializer-Defekt:

- `table.meta.client` ist ein **Resource-Client** mit
  `TransformationInjector`.
- Der Fence-Code übergibt bereits DynamoDB-JSON (`{"S": …}`).
- Der Injector verpackt dieses JSON erneut als `M`.
- DynamoDB lehnt den dadurch ungültigen Key ab.

Der Admin-Call nutzt einen **plain low-level client** und ist deshalb
erfolgreich.

### C.2 Minimaler Fix (bereits umgesetzt)

`_ddb_transaction_client()` liefert für echte boto3-Tables einen **plain
`boto3.client("dynamodb")`**; injizierte Fake-Clients in Tests bleiben
unverändert. Zusätzlich:

- `_is_conditional_failed()` erkennt `TransactionCanceledException` mit
  `ConditionalCheckFailed` (Duplikat-Pfad).
- Der SQS-Handler serialisiert `Decimal` über `_application_json_default`.

### C.3 Verifikation

| Prüfung | Ergebnis |
|---|---|
| Regressionstest Resource-Client vs. Plain-Client | Resource: `"M"`; Plain: `"S"` (kein `M`) |
| Deployed CodeSha256 vs. lokales Bundle | **identisch** (`f787b13e…29cc`) |
| Bundle enthält `_ddb_transaction_client` | ja |
| Live ATS-E2E | `COMPLETED`, Body 1.1, Contract 1.2, Score 67 |
| Live Addition-E2E | `17 + 25 = 42` |
| Doppelauslieferung | `duplicate: true`, kein zweiter AgentRun |

Live-WorkItems:

| WorkId | Status | Ergebnis |
|---|---|---|
| `e2e-ats-9fb9228f8558` | `COMPLETED` | `ATSAnalysisResultBody 1.1` |
| `e2e-add-d65103dbae0b` | `COMPLETED` | `sum = 42` |

### C.4 Verbleibende Hypothesen

Keine. Die Request-Bodies, der Client-Unterschied und die erfolgreiche
Live-Verifikation schließen einen AWS-Defekt aus. Die exakte boto3-Version der
Lambda-Runtime ist nicht separat abfragbar; das Verhalten ist jedoch durch den
serialisierten Body belegt.

---

## D — Ergebnis

| Punkt | Status |
|---|---|
| Projektgrenzen | **bestätigt** (`ris-dev2`, `262370457690`) |
| Orders-Lifecycle | **`managed`** (eigene Orders-Instanz) |
| Fremde Referenzen | **keine** (nur `Maker`-Tags) |
| DynamoDB-Root-Cause | **Resource-Client-Doppelserialisierung** |
| Minimaler Fix | **`_ddb_transaction_client`** (umgesetzt und verifiziert) |
| Weitere Änderungen | **keine** |

**HARD STOP.** Kein Apply, Destroy oder Rollback in diesem Gate.
