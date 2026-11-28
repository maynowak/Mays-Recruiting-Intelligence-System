# RIS-DEV2-CANARY-INGRESS-IAM-FIX-10

**Datum:** 2026-11-26
**Branch:** `feature/ris-analysis-integration-07`
**AWS:** `262370457690` / `eu-central-1` / `ris-dev2`
**Status:** **READY FOR INGRESS IAM APPLY APPROVAL**
**Modus:** Codefix + Tests + Plan; kein Apply, kein Redrive, keine Order, kein Cleanup

## 1. Read-only Verifikation

| Prüfung | Ergebnis |
| --- | --- |
| CloudWatch-Ingress-Fehler | `AccessDeniedException` für `dynamodb:ConditionCheckItem` auf `ris-dev2-dev-work-items` |
| Live-Policy `…-dispatch-ingress-policy` / `WorkItems` | `GetItem`, `PutItem`, `UpdateItem`, `Query` — `ConditionCheckItem` fehlt |
| Worker-Rolle | besitzt `TransactWriteItems` und `ConditionCheckItem` bereits |
| Order | `ord_676668fe5ab468284ed7fcf2` weiterhin `PENDING` |
| Dispatch-DLQ | 1 Nachricht (Retries erschöpft), nicht redriven |
| Synthetic-Modus | `true`, Ablauf `2026-11-26T17:40:28Z` |

## 2. Änderung

`terraform/modules/agent_transport/lambda.tf`, Statement `WorkItems` der
Ingress-Rolle:

```diff
- Action = ["dynamodb:GetItem", "dynamodb:PutItem",
-           "dynamodb:UpdateItem", "dynamodb:Query"]
+ Action = ["dynamodb:GetItem", "dynamodb:PutItem",
+           "dynamodb:UpdateItem", "dynamodb:Query",
+           "dynamodb:ConditionCheckItem"]
```

Unverändert: `Effect`, beide Resource-ARNs (Tabelle + `index/*`),
`GetItem`/`PutItem`/`UpdateItem`/`Query`. **Kein**
`dynamodb:TransactWriteItems` (DynamoDB autorisiert bei Transaktionen die
Item-Aktionen; der Fehler nannte ausschließlich `ConditionCheckItem`).

## 3. Tests

| Lauf | Ergebnis |
| --- | --- |
| `test_terraform_agent_transport.py` (inkl. neuer exakter Action-Pin) | PASS |
| `test_work_queue.py` (inkl. neuer `TransactionCanceledException`-Duplikate) | PASS |
| `test_dispatch_ingress_lambda.py` | PASS |
| Fokussiert gesamt | **38 passed** |
| `terraform fmt -check` / `validate` | PASS |

Die beiden neuen Queue-Tests belegen: Bei `TransactionCanceledException` mit
gesetztem `enqueuedAt` bzw. terminalem Status wird **nicht** erneut gesendet.
Ein zusätzlicher Runtime-Fehler wurde nicht bestätigt; keine Runtime-Änderung.

## 4. Plan

| Feld | Wert |
| --- | --- |
| Datei | `C:\tmp\ris-dev2-ingress-iam-fix-10.tfplan` |
| Größe | 250 859 Bytes |
| SHA-256 | `41d4fdd7929ab3f7b7ff6fcac8787c78c225d7403a92e2cf57877f3ca3f846b0` |
| Terraform | 1.17.0; `applyable/complete` |
| Diff | **0 Add / 1 Change / 0 Destroy / 0 Replace** |
| Ressource | ausschließlich `module.agent_transport[0].aws_iam_role_policy.dispatch_ingress` |
| Attribut | `policy` (nur die neue Aktion) |
| Drift | **keine** |
| State | Serial **72**, Lineage unverändert; S3-Version `21AxFw…` unverändert |
| Synthetic-Modus | unverändert `true` (Plan mit Basis- und Canary-Var-Datei) |

## 5. Rollback

Konfigurationsänderung zurücknehmen und einen neuen Plan (0/1/0) mit eigener
Freigabe anwenden. Danach schlägt Dispatch wieder mit `AccessDeniedException`
fehl; es entstehen keine Datenverluste.

## 6. Nach dem Apply (separate Freigabe)

1. Read-only prüfen, dass die Live-Policy die fünf Aktionen enthält.
2. DLQ-Redrive der einen Nachricht **oder** neue synthetische Order — jeweils
   gesondert freigeben.
3. E2E nur vor **2026-11-26T17:40:28Z**; danach sind neuer Grant und neuer
   Plan nötig.

## 7. Grenzen eingehalten

Kein Terraform-Apply, kein DLQ-Redrive, keine neue Order, kein Cleanup, keine
weiteren AWS-Writes. Der Plan wurde read-only erzeugt; State blieb Serial 72.
