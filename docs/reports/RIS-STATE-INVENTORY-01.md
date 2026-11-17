# RIS-STATE-INVENTORY-01

**Status:** `RESOURCE LOSS CONFIRMED`  
**Scope:** Read-only reconciliation of `ris-dev` Terraform state, S3 state
versions and live AWS resources  
**No Terraform Apply, State-Push, Import, Remove, Refresh-only-Apply or
deployment.**

## 1. Ergebnis

Es wurde **genau ein tatsächlicher AWS-Ressourcenverlust** festgestellt:

```text
API Gateway Route
POST /v1/partner/me/erasure
API:       c7e9pdwe78
Route-ID:  san8y6o
Target:    integrations/anl98ns
```

Die Route war von State-Serial 56 bis 61 vorhanden, wurde am
`2026-11-16T17:16:33Z` per CloudTrail `DeleteRoute` gelöscht und fehlt ab
State-Serial 62. Sie fehlt auch im aktuellen State und in der Live-API.

Es wurden **keine weiteren verwalteten AWS-Ressourcen** als verloren
festgestellt. Die übrigen State-Differenzen sind leere Blöcke, Data-Sources
oder eine Adress-Move-Operation.

## 2. Kanonischer Kontext

Verwendet wurde ausschließlich:

```text
/home/dci-student/projects/mays-xrepo-orchestration/repos/Mays-Recruiting-Intelligence-System
bzw. der isolierte Plan-Worktree ris-consent-recovery-03-main
```

AWS-/Backend-Kontext:

```text
Profil:       mayaws
Account:      240571105849
Region:       eu-central-1
Workspace:    ris-dev
Bucket:       mays-ris-tf-state-dev
Key:          env:/ris-dev/dev/terraform.tfstate
Lock:         mays-ris-tf-lock
Serial:       80
Lineage:      9cec61e5-c036-1ad5-6ae4-8b48a50122a4
Ressourcen:   271 Blöcke / 311 Instanzen
Managed/Data: 255 / 16
```

Der `default`-Workspace enthält 0 Ressourcen; im Bucket liegt nur der
`ris-dev`-State. Keine parallele Terraform-Operation.

## 3. S3-Versionierung

```text
Bucket-Versioning: Enabled
State-Versionen:   80
Delete-Marker:     keine
```

Die relevanten Versionen wurden read-only geladen und ausschließlich auf
Adressen, Typen, Serial und Lineage ausgewertet. Keine State-Werte wurden in
diesen Report übernommen.

## 4. Versionsvergleich

| Vergleich | Ergebnis |
|---|---|
| Serial 80 ↔ 79 | 5 leere Ressourcenblöcke entfernt, **0 Instanzen** verloren |
| Serial 80 ↔ 78 | 1 Data-Source entfernt, 1 Policy-Adresse verschoben; **kein verwalteter AWS-Verlust** |
| Serial 80 ↔ 61 | **1 verwaltete API-Gateway-Route fehlt** |
| Serial 61 ↔ 62 | Route `POST /v1/partner/me/erasure` verschwindet; alle übrigen Instanzen bleiben |

Die 5 Blöcke zwischen Serial 79 und 80 hatten **0 Instanzen**:

- `module.cognito[0].aws_cognito_identity_provider.google`
- `module.cognito[0].aws_cognito_user_pool_domain.custom`
- `module.dynamodb.aws_dynamodb_table_item.foundation_entitlement`
- `module.mays_orders[0].module.agent_transport[0].aws_iam_role_policy.result_consumer_kms`
- `module.monitoring_orders[0].aws_cloudwatch_metric_alarm.dlq_messages` (leerer Zusatzblock; der reale Alarm bleibt separat erhalten)

Bei Serial 78 → 80 wurde lediglich
`module.mays_orders[0].module.iam.aws_iam_role_policy.agent_dispatch`
nach `aws_iam_role_policy.orders_agent_dispatch` verschoben; die Data-Source
`aws_caller_identity.current` entfiel. Das ist kein AWS-Ressourcenverlust.

## 5. Bestätigter Verlust

Historischer State:

```text
Serial 61
VersionId: xjIgGOxUqG1NIc2Kws_Jd0woZ1oaPjHm
Ressource: module.jobsearch_edge[0].aws_apigatewayv2_route.partner
Index:     POST /v1/partner/me/erasure
API:       c7e9pdwe78
Route-ID:  san8y6o
```

CloudTrail:

```text
Event:      DeleteRoute
Zeit:       2026-11-16T17:16:33Z
API:        c7e9pdwe78
Route-ID:   san8y6o
Principal:  arn:aws:iam::240571105849:user/Mayaws
```

State-Folgeversion:

```text
Serial 62
VersionId: dGaUJHZMOovO5vUXysl5Lt0f9CSxOKRE
Zeit:      2026-11-16T17:17:01Z
Route:     nicht mehr enthalten
```

Aktueller AWS-Gegencheck:

```text
API c7e9pdwe78: 40 Routen
POST /v1/partner/me/erasure: nicht vorhanden
```

Damit ist es **keine reine State-Bereinigung**, sondern eine tatsächliche
AWS-Löschung. Die Ursache ist eine Konfiguration/ein Apply ohne diese
Partner-Route; der genaue Checkout lässt sich aus dem State allein nicht
feststellen. Der Zeitpunkt und die State-Transition sind eindeutig.

## 6. AWS- und Planprüfung

Read-only-Prüfung:

- Terraform-Plan-Refresh meldet **0 Add / 0 Destroy** für alle aktuell
  verwalteten Ressourcen; die 255 managed Instanzen sind im aktuellen
  Kontext vorhanden.
- Die Live-API hat 40 Routen; der State hat ebenfalls 40 Routen.
- Die fehlende Erasure-Route ist in der aktuellen Konfiguration nicht
  enthalten; deshalb erzeugt der Plan auch **keine Wiedherstellung**.
- Keine weiteren fehlenden verwalteten Instanzen im Vergleich zu Serial 61
  gefunden.

Vorhandener Plan:

```text
/tmp/opencode/ris-consent-recovery-03.tfplan
SHA-256: 153d121260bf5340a63b4d091abe5541732e853891db2f00f6d8b1694baf312c
State-Serial: 80
0 Add / 5 Change / 0 Destroy / 0 Replace
```

Der Plan ist mechanisch zum State 80 passend, aber **kein Recovery-Plan für
die verlorene Route**. Er darf nicht als vollständiger Recovery-Apply
verwendet werden.

## 7. Bewertung

- **Tatsächlicher AWS-Verlust:** 1 API-Gateway-Route.
- **State-only:** leere Blöcke und Data-Source-Abbau.
- **Adress-Move:** Orders-Dispatch-Policy, gleiche Ressource.
- **Keine weiteren** Lambda-, DynamoDB-, SQS-, Cognito-, IAM-, S3-, Secret-,
  CloudWatch- oder API-Gateway-Ressourcen als verloren nachgewiesen.

**Kein Apply, kein State-Push, kein Import, kein Deployment.** Eine
Wiederherstellung der Route erfordert eine separate Quellcode-/Terraform-
Änderung und einen neuen Plan mit eigener Freigabe; State-Manipulation ist
nicht zulässig.
