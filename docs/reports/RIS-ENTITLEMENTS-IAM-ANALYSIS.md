# RIS-ENTITLEMENTS-IAM-ANALYSIS — Entitlements-IAM Mini-Gate (Analyse, kein Apply)

STATUS: YELLOW — **kein IAM-Change erforderlich**; die im Gate-Auftrag angenommene Lücke existiert im produktiven Code nicht

- Datum: 2026-10-04 UTC
- Branch/HEAD: `main`, `d1cb28b`
- Account/Region/Workspace: `240571105849` (`user/Mayaws`) / `eu-central-1` / `mays-ris`
- Rolle: `mays-ris-dev-agent`
- Policy: `mays-ris-dev-lambda-dynamodb-platform`
- **Keine AWS-Mutation.** Kein Terraform-Code geändert.

## 1. Ausgangslage

Die in P18B/P19 dokumentierte Lücke lautete: „`TransactWriteItems`/`DeleteItem` für die bestehende Entitlements-Tabelle — separates Mini-Gate vor Grant-E2E". Ziel dieses Gates war, die Rechte aus dem produktiven Code abzuleiten und minimal zu ergänzen.

## 2. Live-Policy (Read-only)

`mays-ris-dev-lambda-dynamodb-platform`, Statement 3:

| Aktion | Ressource |
|---|---|
| `dynamodb:GetItem`, `dynamodb:Query`, `dynamodb:BatchGetItem` | `…/table/mays-ris-dev-entitlements` + `…/index/*` |

Terraform-Quelle: `terraform/modules/lambda/main.tf:59-70`. State = Live (`No changes.`).

## 3. Code-Analyse: welche Entitlements-Operationen sind erreichbar?

Vollständige Router-Durchsicht `lambda/handler.py:244-297` (23 Dispatch-Zweige) plus AST-Scan über alle 54 produktiven Python-Dateien.

**Erreichbar — genau eine Operation, `Query`:**

| Call-Site | Index | Trigger |
|---|---|---|
| `lambda/handler.py:1395` `_get_entitlement_for_agent` | `gsi-user` | `GET/POST /api/agents/{agentId}` (403-Gate) |
| `lambda/handler.py:1429` `_get_entitlements` | `gsi-user` | `GET /agents` (live GW-Route) |
| `agents/ecosystem/worker_authorization.py:189` `find_entitlements` | `gsi-user` | SQS-Worker-Autorisierung + `GET /v1/introspection` (live GW-Route) |

Alle drei decken sich mit B3 (`028a24d`), das genau diesen Index-Zwang herstellte. `Query` ist in der Live-Policy enthalten — **der Bedarf ist gedeckt**.

**Nicht erreichbar — die Grant/Withdraw-Operationen:**

`agents/ecosystem/offers.py:286-326` (`DynamoDBEntitlementStore`) enthält `transact_write_items` (`:296`), `delete_item` (`:325`), `get_item` (`:319`), `scan` (`:312`), `query` (`:303`). Diese Klasse wird **im Produktivcode nirgends instanziiert**:

- `lambda/handler.py:645` importiert ausschließlich `DynamoDBOfferStore`, nicht `DynamoDBEntitlementStore`.
- AST-Scan über 54 produktive Dateien: **keine** Referenz auf `grant_offer`, `withdraw_entitlement` oder `DynamoDBEntitlementStore` außerhalb von `agents/ecosystem/offers.py` selbst.
- Es existiert **keine** Grant/Withdraw-Route: weder im Handler-Router noch in `terraform/modules/api/main.tf` (P16-Routen decken nur Credentials ab).
- `agents/runtime/pipeline.py` (SQS-Worker-Pfad) enthält keinen Grant/Withdraw-Aufruf.

Die Klasse ist im Lambda-Bundle enthalten und wird von `tests/test_offer_entitlement_grant.py` gegen In-Memory-Stores getestet — aber **kein Live-Pfad erreicht sie**.

## 4. Transaktions-Scope

`put_entitlements_batch` (`offers.py:286-298`) baut `TransactItems` ausschließlich aus `table.table_name` — **nur** die Entitlements-Tabelle, keine weiteren. Die Items sind reine `Put` mit `ConditionExpression: attribute_not_exists(entitlementId)` (Create-only-Semantik, `ClientError` → `GrantConflict`). Ein späterer Grant-Pfad bräuchte daher genau `TransactWriteItems` auf dem Entitlements-ARN — keinen weiteren Tabellen-ARN.

## 5. Zusätzlich erkannte Über-Gewährung

`dynamodb:BatchGetItem` ist auf der Entitlements-Tabelle gewährt, wird aber **nirgends im Repo** aufgerufen (`grep -rn "batch_get_item" lambda/ agents/ jobsearch/` → leer). Ebenso ist `GetItem` auf Entitlements nicht erreichbar (der einzige `get_item` auf Entitlements sitzt im toten `get_entitlement`). Das ist eine bestehende Über-Gewährung, **kein** Mangel — ich habe sie bewusst nicht angetastet, weil das Entfernen von Rechten außerhalb des Auftrags liegt und die Live-Funktionalität nicht gefährdet werden darf.

## 6. Bewertung

| Frage | Antwort |
|---|---|
| Fehlt der Lambda heute ein Recht? | **Nein.** Alle drei erreichbaren Call-Sites nutzen `Query`, das gewährt ist. |
| Ist `TransactWriteItems` für Live nötig? | **Nein.** Der Grant-Pfad ist nicht erreichbar. |
| Sollte ich es trotzdem ergänzen? | **Nein.** Es wäre eine unbegründete Rechteausweitung auf einen Codepfad ohne Live-Einstiegspunkt. |
| Wird es später gebraucht? | Ja, sobald ein Grant/Withdraw-Route ergänzt wird. Dann als **gemeinsames** Gate mit der Route, nicht vorab. |

Die Gates P18B und P19 haben die Lücke korrekt als offen markiert; die Prämisse „vor Grant-E2E" traf jedoch auf einen Codepfad, dessen E2E es noch nicht gibt. Ein Grant-E2E ist derzeit nicht durchführbar — unabhängig von IAM, weil die Route fehlt.

## 7. Terraform-Checks

- `plan -target=module.lambda.aws_iam_role_policy.lambda_dynamodb_platform` → **`No changes.`** (State = Live, kein Drift)
- `validate` Success, `fmt -check modules/lambda/main.tf` clean

## 8. AWS Mutation

**Keine.** Nur `sts get-caller-identity`, `iam get-role-policy`, `dynamodb describe-table` (read-only) sowie Terraform `plan`/`validate`.

## 9. Git

Commit: nur diese beiden Reports. Kein Terraform-Code geändert.

## 10. Offene Punkte

1. **Empfehlung:** Entitlements-IAM als geschlossen betrachten. Der nächste Schritt für Grant/Withdraw ist ein **kombinatorisches** Gate: Gateway-Route + Handler-Dispatch + IAM (`TransactWriteItems`, `DeleteItem`, `Scan`, `GetItem` auf Entitlements) — alles zusammen, damit Berechtigung und Einstiegspunkt synchron entstehen.
2. `BatchGetItem`/`GetItem` auf Entitlements sind übergewährt und ungenutzt — Kandidat für eine spätere Least-Privilege-Bereinigung, nicht in diesem Gate.
3. Alle P18/P19-Gates empfahlen „Entitlements-IAM-Gate vor Grant-E2E". Diese Empfehlung ist mit diesem Befund überholt und sollte in den Folgedokumenten nicht mehr als Blocker für einen P17-Re-Run geführt werden.
