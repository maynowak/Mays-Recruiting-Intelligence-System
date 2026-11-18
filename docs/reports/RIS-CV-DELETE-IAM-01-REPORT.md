# RIS-CV-DELETE-IAM-01 — IAM FIX & SYNTHETIC DELETE READINESS

**Status:** `READY FOR CONTROLLED IAM APPLY`  
**Frontend dependency:** Jobsearch `feature/jm-cv-ux-07-persistence-delete-editor-return` (`0d1a17f`)  
**No Apply, no Jobsearch change, no real CV deletion.**

## 1. Betroffene Umgebung

```text
Profil:       mayaws
Account:      240571105849
Region:       eu-central-1
Workspace:    ris-dev
State-Bucket: mays-ris-tf-state-dev
State-Key:    env:/ris-dev/dev/terraform.tfstate
Serial:       82
Lineage:      9cec61e5-c036-1ad5-6ae4-8b48a50122a4
Ressourcen:   271 Blöcke / 312 Instanzen
State-ETag:   "eea44cc0a985d5ff2a54a234fb7630a7"
```

`ris-dev2` ist nicht die Zielumgebung. Im State-Backend existiert nur der
`ris-dev`-State; es wurde keine andere Umgebung oder ein Production-RIS
angenommen.

## 2. Root Cause

Der CV-Delete nutzt die bestehende Partner-Profile-Transaktion:

```text
role:  ris-dev-dev-agent
table: ris-dev-dev-partner-profiles
path:  reserve_parent_delete / finalize_parent_delete
```

Die Transaktion verwendet `ConditionCheck` innerhalb von
`TransactWriteItems`. Die bestehende IAM-Policy
`ris-dev-dev-lambda-dynamodb-partner-profiles` enthielt:

```text
dynamodb:PutItem
dynamodb:GetItem
dynamodb:Query
dynamodb:DeleteItem
dynamodb:UpdateItem
dynamodb:TransactWriteItems
```

aber nicht:

```text
dynamodb:ConditionCheckItem
```

Live-Simulation:

```text
dynamodb:ConditionCheckItem
auf ris-dev-dev-partner-profiles
= implicitDeny
```

Damit ist der 500er `cv delete reservation failed` erklärt.

## 3. IAM-Diff

Geändert wird ausschließlich:

```text
module.lambda.aws_iam_role_policy.lambda_dynamodb_partner_profiles
```

hinzugefügt:

```text
"dynamodb:ConditionCheckItem"
```

Unverändert:

- Rolle `ris-dev-dev-agent`
- Effect `Allow`
- Resource:
  - `arn:aws:dynamodb:eu-central-1:240571105849:table/ris-dev-dev-partner-profiles`
  - `arn:aws:dynamodb:eu-central-1:240571105849:table/ris-dev-dev-partner-profiles/index/*`
- alle bisherigen Aktionen
- keine Wildcard-Berechtigung
- keine neue Tabelle, Rolle, Lambda oder Resource
- keine Cognito-/CloudFront-/DNS-Änderung

## 4. Aktueller Terraform-Plan

```text
Plan:        /tmp/opencode/ris-cv-delete-iam-01.tfplan
SHA-256:     754770b44e4f63d386f962a12e6701e04e3b1c94a53cbc3d2858b9e871afbf5d
State:       Serial 82
Changes:     0 Add / 1 Change / 0 Destroy / 0 Replace
```

Der alte Plan `c30d9c1928e60332be040d2a2453b5b357c9c14e699404238dddc623077be4e8`
ist nur Referenz und **SUPERSEDED**; der neue Plan ist der aktuelle
Freigabegegenstand.

Es wurde **kein Apply** ausgeführt; State und ETag wurden nicht geschrieben.

## 5. Tests / Gates

```text
Fokussiert IAM/Consent/Profile: 46 PASS
Vollständige RIS-Suite:         2829 PASS / 104 skipped / 18 bekannte Baseline-Fehler
terraform fmt -check:           PASS
terraform validate:             PASS
```

Die 18 Restfehler sind die bekannten Wrapper-/Terraform-/Composite-/Health-/
Platform-Baseline-Fehler; keine neuen durch den IAM-Fix.

## 6. Synthetische Delete-E2E — vorbereitet, nicht ausgeführt

Nach separater Apply- und Testfreigabe:

1. Autorisierte synthetische Identität verwenden.
2. Einen neuen synthetischen CV anlegen.
3. Über den bestehenden BFF dauerhaft speichern.
4. In der persistenten Liste finden.
5. Löschen bestätigen.
6. Serverantwort prüfen.
7. Liste neu laden.
8. Sicherstellen, dass der gelöschte CV fehlt.
9. Sicherstellen, dass andere CVs unverändert bleiben.
10. Keine echten Benutzer-CVs anfassen.

Der Test wird erst nach Apply des exakten Plans und separater Freigabe
ausgeführt. Keine produktiven Benutzerdaten, keine Tokens in Reports.

## 7. Empfehlung

```text
READY FOR CONTROLLED IAM APPLY
```

Für den Apply ist eine separate ausdrückliche Freigabe erforderlich:

```text
GO APPLY 754770b44e4f63d386f962a12e6701e04e3b1c94a53cbc3d2858b9e871afbf5d
```

Der Apply muss aus dem vorbereiteten Worktree mit generiertem
`terraform/modules/mays_orders` erfolgen; kein neuer Plan, kein `-target`,
keine State-Manipulation, kein Jobsearch-Change.

## 8. Offene Risiken

- IAM-Fix ist noch nicht angewendet.
- Der echte CV-Delete ist bis dahin nicht als funktionsfähig verifiziert.
- Jobsearch-Frontend-Fix ist im separaten Branch `0d1a17f`; keine
  Jobsearch-Änderung in diesem Auftrag.
- Kein Main-Merge und kein Deployment in diesem Schritt.
