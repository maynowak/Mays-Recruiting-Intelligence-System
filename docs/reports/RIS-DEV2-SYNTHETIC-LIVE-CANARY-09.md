# RIS-DEV2-SYNTHETIC-LIVE-CANARY-09

**Datum:** 2026-11-25
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `547c3952b46f069e673f2e598d9acdfc351c3fcf`
**AWS:** `262370457690` / `eu-central-1` / `ris-dev2`
**Status:** **BLOCKED — PARTIALLY VERIFIED**
(Canary-Apply und Konfiguration verifiziert; E2E scheitert am Dispatch-Ingress-IAM.)

## 1. Preflight (PASS)

| Prüfung | Ergebnis |
| --- | --- |
| HEAD / STS / Region / Workspace | `547c395…`, `262370457690`, `eu-central-1`, `ris-dev2` |
| State | Lineage `a0bd361d…`, Serial **71**, kein Lock |
| Plan | `C:\tmp\ris-dev2-canary-08.tfplan` |
| SHA-256 | `996864c10b77ed8ced23c5f01e55036caab6676752a38f0c4b0e7f904bb94096` |
| Diff | 0 Add / 1 Change / 0 Destroy; nur Analysis-Environment |
| Identität | User/Profil/Partner/Bindung/Entitlement gültig, Ablauf 2026-11-26T17:40:28Z |
| Env/Consent/Code | Mode true, exakte vier Felder, Entitlements korrekt, Consent/Notice false, Code-Hash unverändert |

## 2. Apply (erfolgreich)

```text
terraform apply -auto-approve -no-color C:\tmp\ris-dev2-canary-08.tfplan
→ exit 0
Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

| Ergebnis | Wert |
| --- | --- |
| State | **71 → 72**, Lineage unverändert |
| S3-State | Version `21AxFwPWYyKaobrw_DDdE231zgOU9_pr`, `2026-11-25T19:08:55Z` |
| Live-Env | `ANALYSIS_SYNTHETIC_MODE=true`; Tenant/User/Partner/Issuer exakt; Entitlements `parse.cv,parse.job,analyze.job,compare.tags`; Ablauf `2026-11-26T17:40:28Z`; Consent/Notice false |
| Code/IAM | Analysis-Code `WDBpUPbe…` unverändert; IAM nur `dynamodb:GetItem` |

## 3. E2E-Ergebnis

| Schritt | Ergebnis |
| --- | --- |
| JWT | regulär via `USER_PASSWORD_AUTH` (Human-Client), korrekter `iss`/`aud`/`sub`/Tenant; Token nicht gespeichert/geloggt |
| Order-Create | **HTTP 201**, `ord_676668fe5ab468284ed7fcf2`, Status `PENDING`; Dispatch vermerkt (`msg_work-eb1185ecc14c889a_order_dispatch`, `workId=work-eb1185ecc14c889a`) |
| Dispatch-Ingress | **AccessDeniedException**: `dynamodb:ConditionCheckItem` auf `ris-dev2-dev-work-items` fehlt der Ingress-Rolle |
| WorkItem | **keines** angelegt (`0` Zeilen für die Order) |
| Analysis/Worker | **nicht aufgerufen** (keine Log-Streams/Invocation nach dem Apply) |
| ORDER_RESULT / Owner-GET | nicht erreicht; Order bleibt `PENDING`, `processing=null` |
| Queues | Dispatch: 1 in-flight (Retry), DLQ 0; Work-Queue 0; DLQ 0 |
| Negativfälle | kein Token → **401**; unbekannte Order → **404**; fremder Owner (kontrollierter Direkt-Invoke des Readers) → **404** |
| Signatur/Replay/Korrelation | durch die gepinnten lokalen Cross-Repo-Tests abgedeckt (8 passed); **nicht** live injiziert (kein Secret-Handling, keine Queue-Writes) |

### Fehlerbeleg (CloudWatch)

```text
dispatch processing failed; requesting retry
botocore.exceptions.ClientError: AccessDeniedException ... not authorized to
perform: dynamodb:ConditionCheckItem on resource:
arn:aws:dynamodb:eu-central-1:262370457690:table/ris-dev2-dev-work-items
because no identity-based policy allows the dynamodb:ConditionCheckItem action
```

## 4. Ursache und kleinster Fix

`enqueue_work_item` persistiert das WorkItem mit `TransactWriteItems`
(`ConditionCheck` + `Put`). Die Ingress-Rolle hat im WorkItems-Statement nur
`GetItem/PutItem/UpdateItem/Query`; es fehlen **`dynamodb:TransactWriteItems`**
und **`dynamodb:ConditionCheckItem`**. Die Worker-Rolle besitzt beide bereits.

Kleinster Fix (separate Freigabe nötig):

- `terraform/modules/agent_transport/lambda.tf`, Statement `WorkItems` der
  Ingress-Rolle: `dynamodb:TransactWriteItems` und
  `dynamodb:ConditionCheckItem` ergänzen (keine Runtime-Änderung, keine neuen
  Ressourcen).
- Neuer Plan danach: erwartet **0 Add / 1 Change / 0 Destroy** (nur die
  IAM-Policy).
- Danach neuer E2E-Lauf. Die aktuelle Dispatch-Nachricht wird voraussichtlich
  nach `maxReceiveCount` in die Dispatch-DLQ wandern; kein Redrive ohne
  Freigabe.

## 5. Aktueller AWS-Zustand (nicht verändert)

- `ANALYSIS_SYNTHETIC_MODE=true` bleibt aktiv; Entitlement gültig bis
  **2026-11-26T17:40:28Z**.
- Order `ord_676668fe5ab468284ed7fcf2` bleibt `PENDING` mit
  `dispatch.status=SENT`.
- Dispatch-Queue: 1 Nachricht in-flight; DLQ 0; Work-Queue/DLQ 0.
- Kein Cleanup, kein Rollback, kein neuer Grant, keine IAM-/Cognito-Änderung.

## 6. Grenzen eingehalten

Kein Rollback-Apply, kein Cleanup, kein neuer Grant, keine weiteren
Infrastruktur-/Cognito-/IAM-Änderungen, kein Main-Merge. Nach dem Fehler
wurden nur read-only Prüfungen ausgeführt.

## 7. Entscheidung

**BLOCKED — PARTIALLY VERIFIED.** Apply und Synthetic-Konfiguration sind live
verifiziert; der E2E ist am fehlenden `dynamodb:ConditionCheckItem` /
`dynamodb:TransactWriteItems` der Ingress-Rolle gescheitert. Ohne diesen IAM-Fix
kann kein ORDER_DISPATCH ein WorkItem erzeugen.
