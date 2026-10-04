# RIS-PLATFORM-TABLES-IAM-STATE-RECONCILIATION-18B — State Reconciliation

STATUS: GREEN (State = Live für alle 4 P18-Ressourcen; kein Apply, keine AWS-Mutation)

- Datum: 2026-10-04 UTC
- Branch/HEAD: `main`, `7701304` (P18-Commit)
- Account/Region/Workspace: `240571105849` / `eu-central-1` / `mays-ris`
- Scope: ausschließlich State-Reconciliation der 4 P18-Ressourcen. KEIN Create/Delete/Replace/Update, KEIN Lambda-Code-/Env-Deploy, KEIN P16/P13/Cognito/SQS/Worker/Agent.
- Grundlage: P18-Commit `7701304`, B3 `028a24d`, P17-Blocker B.

## 1. Ausgangslage

Die drei P18-Tabellen und die product-Policy existierten bereits live, waren aber nicht (alle) im Terraform-State. In dieser Session wurde **kein Apply** ausgeführt — nur `plan`/`validate`.

## 2. CloudTrail-Provenance

- 3× `CreateTable` am **2026-10-04T12:52:48+02:00**, Actor `Mayaws` (identische Identität wie das Deployment-Profil), ResourceName im Event `null`.
- Bewertung: Out-of-band-Erstellung durch dieselbe Identität; nicht durch dieses Gate. Konformitätsbewertung auf Basis der Live-Werte selbst (siehe §5), nicht auf Basis der Herkunft.

## 3. Korrektur einer Fehldiagnose (wichtig)

Ein erster State-Check wurde **ohne** `AWS_PROFILE` ausgeführt. Terraform griff dadurch auf Default-Credentials eines **anderen Accounts** zurück (`992382612204:user/maymilly`) und erhielt `AccessDeniedException` auf der Backend-Lock-Tabelle `mays-ris-tf-lock`. Der leere Output wurde fälschlich als "nicht im State" interpretiert.

- Konsequenz: **Alle** State-Kommandos in 18B wurden mit `AWS_PROFILE=mayaws` ausgeführt.
- Nebenbefund: Die Backend-Lock-Tabelle liegt in Account `992382612204`; `maymilly` besitzt dort keine Lock-Rechte. `mayaws` hat sie (alle Plan-/State-Operationen erfolgreich).
- Ebenfalls korrigiert: Die IAM-Policy war bereits im State (`create` im P18-Plan war ein Artefakt desselben Credential-Problems). Ein erneuter Import wurde vom Provider korrekt mit `Resource already managed by Terraform` abgelehnt.

## 4. Import (nur State, keine Mutation)

| Ressourcen-Adresse | Import-ID | Ergebnis |
|---|---|---|
| `module.dynamodb.aws_dynamodb_table.api_profiles` | `mays-ris-dev-api-profiles` | importiert |
| `module.dynamodb.aws_dynamodb_table.offers` | `mays-ris-dev-offers` | importiert |
| `module.dynamodb.aws_dynamodb_table.credentials` | `mays-ris-dev-credentials` | importiert |
| `module.lambda.aws_iam_role_policy.lambda_dynamodb_product` | bereits managed | kein Import nötig; Re-Import abgelehnt |

Hinweis: `aws_iam_role_policy` verlangt das ID-Format `<role>:<policy>`, nicht `<role>/<policy>`; der erste Versuch mit `/` wurde vom Provider abgewiesen (ohne Nebenwirkung).

## 5. State-Readback / State = Live Parity

Alle Prüfungen GREEN (state vs. Live verglichen):

**api-profiles** — ACTIVE, PK `apiProfileId`, GSI `gsi-owner` HASH `ownerUserId` Projection ALL, PAY_PER_REQUEST, TTL aus, Tags Project/Environment/Maker, ItemCount 0.

**offers** — ACTIVE, PK `offerId`, **keine** GSI, PAY_PER_REQUEST, TTL aus, Tags Project/Environment/Maker, ItemCount 0.

**credentials** — ACTIVE, PK `credentialId`, GSI `gsi-digest` HASH `digest` Projection ALL, PAY_PER_REQUEST, TTL aus, Tags Project/Environment/Maker, ItemCount 0. Attribut-Definitionen ausschließlich `credentialId` + `digest` — **kein** Secret-Feld; Credentials werden schemalos gehalten, Secrets existieren nicht in der Tabelle.

**IAM `mays-ris-dev-lambda-dynamodb-product`** — Policy-Dokument state-identisch zu live:
- api-profiles: GetItem, Query, PutItem, UpdateItem → Tabellen-ARN + `/index/*`
- offers: GetItem, Scan, PutItem, UpdateItem → Tabellen-ARN
- credentials: GetItem, Query, Scan, PutItem, UpdateItem → Tabellen-ARN + `/index/*`

Nicht enthalten und bestätigt abwesend: `dynamodb:*`, DeleteItem, Batch*, Transact*, fremde Tabellen-ARNs, Cognito, S3, Terraform-/IAM-Admin.

## 6. Fresh Plan — `Plan: 16 to add, 2 to change, 0 to destroy.`

- **Die vier P18-Ziele: 0 add, 0 change, 0 destroy (alle `no-op`).**
- Maschineller Delta-Vergleich gegen den P18-Plan (`/tmp/p18.json` vs `/tmp/p18b.json`, 90 Ressourcen): **einzige** Aktionsänderungen sind `create → no-op` bei genau den 4 P18-Adressen. Keine Adresse hinzugefügt oder entfernt, keine unerwartete Drift-Bewegung.
- Verbleibender Plan exakt der in P18 klassifizierte Fremd-Drift, unangetastet:
  - 14× API-Gateway-Routen (P16=7, P13=1, CLI-Drift=6)
  - 1× `module.iam.aws_iam_role_policy.lambda_policy` (IAM-Drift)
  - 1× `module.lambda.aws_lambda_event_source_mapping.sqs_mapping` (SQS-Drift)
  - 2 Updates: `aws_cognito_user_pool.users`, `aws_lambda_function.agent`
  - 72 no-op, 0 destroy

## 7. Tests

- `terraform validate`: Success (nur bekannte `range_key`-Deprecation-Warnungen).
- Domain-Suiten (P10/P11/P09/P14-HTTP/Introspection): **281 passed**.
- Gesamtsuite: `15 failed, 709 passed, 8 skipped, 231 warnings, 1 error` — **identisch zur P18-Baseline**; Fehlerliste-MD5 `d0efae4dba6d8af196593535a46c3e57` (unverändert). Keine Python-Änderung in 18B.
- Keine Credential-E2E, kein P17-Re-Run.

## 8. Lambda

NICHT deployt und unverändert belegt: `LastModified 2026-10-03T10:38:23Z`, `CodeSha256 zSt29/mH4DADAJz8yXvETWOH8Yvnbpy0P02k+SQM16I=`, und `API_PROFILES_TABLE`/`OFFERS_TABLE`/`CREDENTIALS_TABLE` sind **nicht** in der Lambda-Environment enthalten.

## 9. AWS Mutation

- **Keine.** Import ist state-only; kein Create/Update/Delete/Tag-Write an AWS-Ressourcen ausgeführt.
- Reads: `sts`, `dynamodb describe-table`/`list-tags-of-resource`, `iam get-role`/`get-role-policy`/`list-role-policies`, `cloudtrail lookup-events`, `lambda get-function-configuration`.

## 10. Git

- Nur die beiden 18B-Reports committed. TF-Code unverändert gegenüber `7701304`.
- Terraform-State ist remote/backend-verwaltet und wurde **nicht** committed.

## 11. Follow-ups (unverändert, nicht in diesem Gate)

- Lambda Environment/Code-Deployment (env-Variablen) — separates Gate.
- `TransactWriteItems`/`DeleteItem` für die bestehende Entitlements-Tabelle — separates Mini-Gate vor Grant-E2E.
- P16/P13-Routen, Cognito-, SQS-, Lambda-Drift — nicht angefasst.
