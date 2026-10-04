# RIS-P18-AGENT-CATALOG-IAM-FIX-01 — Agent Catalog IAM Fix

STATUS: GREEN (IAM-Defekt behoben und live belegt; `/agents`-Inhalt bleibt leer wegen leerer Katalog-Tabelle — separater Punkt)

- Datum: 2026-10-04 UTC
- Branch/HEAD: `main`, `e501a37`
- Account/Region/Workspace: `240571105849` (`user/Mayaws`) / `eu-central-1` / `mays-ris`
- AWS-Mutation: **1** IAM-Update (`PutRolePolicy` auf `mays-ris-dev-lambda-dynamodb-platform`) + Testuser-Attribut/Passwort auf dem synthetischen P17-Testuser

## 1. Root Cause

Der Produktivcode liest den Agent Catalog per **`dynamodb:Scan`**, die IAM-Policy erlaubte auf dieser Tabelle nur `GetItem`, `Query`, `BatchGetItem`. Jeder Scan-Zugriff lief therefore in `AccessDeniedException`.

Der Handler fängt die Exception in `except Exception` und degradiert **still**: HTTP 200 mit leerer Liste. Der Defekt war deshalb im Response nicht sichtbar, nur im CloudWatch-Log.

Live-Beleg aus dem P17-Lauf:

```
AccessDeniedException: not authorized to perform: dynamodb:Scan on resource:
arn:aws:dynamodb:eu-central-1:240571105849:table/mays-ris-dev-agent-catalog
```

## 2. Codepfad — vollständige Analyse

Es gibt **drei** produktive Scan-Stellen auf dem Agent Catalog, nicht eine:

| # | Stelle | Methode | Produktive Aufrufer |
|---|---|---|---|
| 1 | `agents/ecosystem/catalog_adapter.py:121` (`get_all_agents`) | `table.scan()` | `lambda/handler.py:52` (`_init_catalog`), `lambda/handler.py:655` (`_build_introspection_sources`) |
| 2 | `lambda/handler.py:1362` (`_get_agent_catalog`) | `table.scan()` (direkt, ohne Adapter) | `handler.py:601` (`_handle_agents`), `:1113`, `:1166`, `:1209` |
| 3 | `agents/ecosystem/catalog_adapter.py:76` (`scan_all_agent_ids`) | `table.scan(ProjectionExpression=…)` | nur Docstring — kein produktiver Aufrufer, gleiche Permission |

Dazu **eine** GetItem-Stelle: `catalog_adapter.py:99` (`get_agent`) — kein produktiver Aufrufer, `GetItem` war bereits gewährt.

`Query` und `BatchGetItem` auf dem Catalog werden im Code **nirgends** verwendet. Sie sind Bestand der bestehenden Policy und wurden **nicht** angetastet (Entfernen von Rechten liegt außerhalb dieses Gates).

**Index-Nutzung: keine.** Weder `scan_all_agent_ids` noch `get_all_agents` noch `_get_agent_catalog` referenzieren den GSI `gsi-status`. Alle drei lesen den Basis-Tabellen-ARN.

## 3. Bisherige vs. erforderliche Policy

| Resource | vorher | nachher |
|---|---|---|
| `…/table/mays-ris-dev-agent-catalog` | `BatchGetItem`, `GetItem`, `Query` | `BatchGetItem`, `GetItem`, `Query`, **`Scan`** |
| `…/table/mays-ris-dev-agent-catalog/index/*` | dito | dito + `Scan` |

Alles andere in der Policy unverändert (siehe Negativprüfung §7).

## 4. Least-Privilege-Begründung

- **Nur `Scan` ergänzt**, keine bestehende Aktion entfernt, keine neue Aktion auf andere Tabellen.
- **Kein Wildcard** — verifiziert: keine `dynamodb:*`, keine Action mit `*`.
- **Keine Resource-Erweiterung.** Das Statement enthielt bereits `var.agent_catalog_table_arn` **und** `…/index/*`; ich habe die Action-Liste ergänzt, die Resource-Liste nicht. Scan gilt damit formal auch für die Index-ARNs — Scan operiert nie auf einem GSI, es entsteht also **keine zusätzlich erreichbare Fähigkeit**.
- **Bewusste Abweichung von der Idealform:** eine strikt tabellen-only-Variante erforderte einen Statement-Split in zwei Statements. Das hätte auch die bestehenden Actions umstrukturiert und ist größer als der minimale Fix. Vor der Freigabe als Option vorgelegt und verworfen.

Terraform-Änderung: genau eine Action-Zeile in `terraform/modules/lambda/main.tf:47-64`.

## 5. Terraform Plan

`fmt -check modules/lambda/main.tf` clean, `validate` Success.

**`Plan: 0 to add, 1 to change, 0 to destroy`**, `replace_paths: KEINE`. Einzige non-noop-Ressource: `module.lambda.aws_iam_role_policy.lambda_dynamodb_platform`. Policy-Diff im Plan verifiziert: genau eine Action ergänzt, alle 6 Resource-ARNs unverändert.

## 6. Apply + Live Readback

Identität vor Apply verifiziert (Account `240571105849`, Workspace `mays-ris`). Gezielter Apply auf `…lambda_dynamodb_platform`:

```
Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

IAM-Readback live bestätigt:

| Resource | Actions |
|---|---|
| `…/table/mays-ris-dev-user-profile` (+ `/index/*`) | `BatchGetItem, GetItem, PutItem, Query, UpdateItem` |
| `…/table/mays-ris-dev-agent-catalog` (+ `/index/*`) | `BatchGetItem, GetItem, Query,` **`Scan`** |
| `…/table/mays-ris-dev-entitlements` (+ `/index/*`) | `BatchGetItem, GetItem, Query` |

## 7. Negativprüfung

| Tabelle | Ergebnis |
|---|---|
| `mays-ris-dev-user-profile` | 🟢 unverändert |
| `mays-ris-dev-entitlements` | 🟢 unverändert |
| `mays-ris-dev-api-profiles` | 🟢 nicht betroffen (eigene Policy, unverändert) |
| `mays-ris-dev-offers` | 🟢 nicht betroffen |
| `mays-ris-dev-credentials` | 🟢 nicht betroffen |
| `mays-ris-dev-jobsearches` | 🟢 nicht betroffen |
| `mays-ris-dev-work-items` | 🟢 nicht betroffen |
| Wildcards | 🟢 keine |
| `Scan` nur im agent-catalog-Statement | 🟢 verifiziert |

## 8. Live-Validierung

**Erwartungskorrektur:** Das Gate erwartete, `/agents` zeige nach dem Fix „tatsächliche aktive Agenten". Die Tabelle `mays-ris-dev-agent-catalog` hat jedoch **Count 0** — es existieren keine Zeilen. `/agents` liefert daher auch nach dem Fix 200 mit leerer Liste. Der belastbare Nachweis ist deshalb das **Verschwinden** des `AccessDeniedException`, nicht eine befüllte Liste.

| Messung | vorher | nachher |
|---|---|---|
| `GET /agents` | 200, `agents: []` | 200, `agents: []` |
| `GET /v1/introspection` | 200, `capabilities: []` | 200, `capabilities: []`, Audit `outcome=success` |
| `GET /platform` | 200 | 200 |
| **CloudWatch agent-catalog `AccessDenied`** | **3 Events** | **0 Events** |
| Sonstige `AccessDenied` | 0 | 0 |
| Scan-Fehler-Events | — | 0 |
| ERROR-Logzeilen im Messfenster | 3 | **0** |

Nachher-Logfenster enthält nur noch `START/END/REPORT`, `Processing request`, `API request: GET /agents`, `API request: GET /v1/introspection` und `introspection-audit … outcome=success capabilities=0` — **keine einzige ERROR-Zeile**.

**Einschränkung der Beweiskette:** CloudTrail wurde als zusätzlicher Belastungstest versucht, liefert aber `0 ScanTable-Events`. DynamoDB-Data-Events werden nur mit aktiviertem „Enable data events" aufgezeichnet; das ist hier nicht aktiv. Die CloudWatch-Evidenz ist daher die maßgebliche Quelle.

## 9. Fresh Plan

| Ressource | Aktion |
|---|---|
| `module.lambda.aws_iam_role_policy.lambda_dynamodb_platform` | `no-op` 🟢 |
| `module.iam.aws_iam_role_policy.lambda_policy` | `create` (Fremd-Drift, unberührt) |
| `module.lambda.aws_lambda_event_source_mapping.sqs_mapping` | `update` (ESM-Tags, unberührt) |

Unverhältnismäßigkeitsprüfung: Lambda `CodeSha256 yaKXvStx/o/M/XHUiA01d18cFDoi35PMcAibequbZHc=`, `LastModified 2026-10-04T11:44:08Z`; Gateway 22 Routen; ESM `7cc946b9…`, `Enabled`, Batch 5; 8 Role-Policies — alle unverändert.

## 10. Tests

| Lauf | Ergebnis |
|---|---|
| Gesamtsuite (ohne `AWS_PROFILE`) | 15 failed / 709 passed / 8 skipped / 231 warnings / 1 error |
| Fehler-MD5 | `d0efae4dba6d8af196593535a46c3e57` — **identisch zur Baseline seit P18** |
| Agent-/Catalog-Subset | 92 passed, 2 failed |

Die 2 Subset-Fehler (`test_agent_invocation.py::test_contract_validation`, `::test_contract_mode_validation`) sind **präexistend** — beide erscheinen mit identischem Namen auch im Gesamtlauf, dessen MD5 unverändert ist. Keine Regression; keine Baseline-Frage als neue Regression markiert.

## 11. AWS-Mutationen

| Art | Umfang |
|---|---|
| IAM | 1× `PutRolePolicy` auf `mays-ris-dev-lambda-dynamodb-platform` |
| Cognito | am synthetischen Testuser `p17-e2e-synthetic-01`: Passwort neu gesetzt, Tenant-Attribut, `admin-enable-user`, `admin-disable-user` |
| Terraform-Ressourcen | **keine** außer der genannten IAM-Policy |
| Lambda / Gateway / DynamoDB / SQS / ESM | **keine** |

Testuser nach Cleanup: `CONFIRMED`, `Enabled: false`. Passwort und Token mit `shred -u` vernichtet, tmp-Verzeichnis gelöscht. Keine Katalog-Zeile geschrieben (Tabelle unverändert leer).

## 12. Offene Punkte

1. **`mays-ris-dev-agent-catalog` ist leer (Count 0).** Der IAM-Defekt ist behoben, aber es gibt keine Agenten zu lesen. `/agents` und die Introspection-Capabilities bleiben deshalb inhaltlich leer. Das Befüllen des Katalogs ist eine eigene fachliche Aufgabe (Seed/Migration) und war in diesem Gate nicht zulässig.
2. **`Query` und `BatchGetItem` auf dem Catalog sind ungenutzt** (kein Code-Aufrufer) — Über-Gewährung, analog zu `BatchGetItem` auf Entitlements. Entfernen wäre Least-Privilege, ist aber kein Add und liegt außerhalb des Auftrags.
3. **`GetItem` auf dem Catalog** wird nur von `get_agent()` benötigt, das keine produktive Caller hat — ebenfalls Über-Gewährung.
4. **`gsi-status`** existiert, wird vom Produktivcode nicht genutzt.
5. **Aus P17 weiter offen und unverändert:** APIProfile-Management-API fehlt, kein M2M-Einstiegspunkt (`verify_api_credential` unverdrahtet), `bearer_credential` wird nicht übergeben, Entitlements-Grant ohne Route.
6. **Methodischer Punkt:** Die Entitlement-IAM-Analyse hat dieselbe Policy geprüft, aber nur auf den Entitlements-ARN. Eine vollständige Least-Privilege-Analyse müsste **alle** Statements je Tabelle gegen den Codebedarf prüfen — dann wäre dieser Defekt aufgefallen. Empfehlung: vor dem nächsten Live-Gate eine solche Gesamtanalyse über alle Rollen-Policies.
