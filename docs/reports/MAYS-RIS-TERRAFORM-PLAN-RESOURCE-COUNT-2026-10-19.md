# Mays-RIS – Terraform-Plan Ressourcen-Zählung (2026-10-19)

**Datum:** 2026-10-19
**Status:** COMPLETED (GREEN)
**Methode:** `terraform plan` lokal (Backend-Override), `AWS_PROFILE=mayaws`,
`-lock=false -input=false`, Vars: `filename`/`health_writer_zip_path`/`health_publisher_zip_path`
**Ergebnis:** `Plan: 159 to add, 0 to change, 0 to destroy`

## 1. Aufschlüsselung (159 Ressourcen „to add")

| Modul | Ressourcen | Anmerkung |
|---|---:|---|
| `module.api` | 37 | RIS-Kern HTTP API (Routen/Integration/Authorizer/Permissions) |
| `module.health_plane` | 15 | Health-Plane |
| `module.lambda` | 14 | RIS Agent-Lambda |
| `module.cognito` | 12 | RIS Cognito |
| `module.dynamodb` | 11 | RIS-Tabellen (work-items, user-profile, agent-catalog, …) |
| `module.orders_reader` | 10 | Orders-Facade (verdrahtet auf `module.mays_orders`) |
| **`module.mays_orders`** | **24** | **Orders-Service-Modul (Child-Modul)** |
| `module.monitoring` | 8 | RIS-Monitoring (nur RIS-Kern) |
| `module.health_public` | 7 | Health public |
| `module.cloudtrail` | 6 | RIS-Trail (account-weit) |
| `module.sqs` | 5 | RIS-Queues (work/ats/cv/match + DLQ) |
| `module.documents` | 4 | Dokumenten-Bucket |
| `module.iam` | 2 | RIS Lambda-Role |
| Root (`aws_s3_bucket.data` + 3 Helfer) | 4 | Data-Bucket |
| **Summe** | **159** | |

## 2. `module.mays_orders` im Detail (24)

| Untermodul | Ressourcen |
|---|---:|
| `api` | 9 |
| `sqs_worker` | 5 |
| `cognito[0]` | 3 |
| `sqs` | 2 |
| `lambda` | 2 |
| `iam` | 2 |
| `dynamodb` | 1 |
| **Summe** | **24** |

Enthalten: API+Handler, Worker, Queue, Orders-Tabelle, IAM, Cognito (MANAGED).
**Nicht** enthalten (Vertrag `MAYS-ORDERS-MODULE-CONTRACT-01`): Monitoring,
CloudTrail, Cognito-Backups.

## 2a. Detail: Cognito (nicht nur der Pool)

**RIS `module.cognito` = 12 Ressourcen**

| Ressource | Anzahl | Details |
|---|---:|---|
| `aws_cognito_user_pool` | 1 | `users` |
| `aws_cognito_user_pool_client` | 2 | `client`, `m2m` (Machine-to-Machine) |
| `aws_cognito_resource_server` | 1 | `ris_api` (Scope-Server für M2M-Routen) |
| `aws_cognito_user_pool_domain` | 1 | `domain` |
| `aws_cognito_user_group` | 7 | `admins`, `candidates`, `recruiters`, `standard_admin`, `standard_staff`, `standard_user_user`, `standard_user_requier` |
| **Summe (Plan)** | **12** | |

Deklariert, aber **nicht im Plan** (count-gated, Default aus):
`aws_cognito_identity_provider.google` (Gate 13A, `google_client_id = ""` → `count = 0`)
→ Bei aktivierter Google-Federation wäre es **13**.

**RIS `module.mays_orders` Cognito = 3 Ressourcen:** `user_pool.users`,
`user_pool_client.app`, `user_group.staff` (MANAGED-Modus; EXTERNAL → 0).

Ergänzend außerhalb des Cognito-Moduls: `module.dynamodb.user_profile`-Tabelle
und die JWT-Wirksamkeit über `module.api` (Authorizer) gehören nicht zu Cognito.

## 3. Abgleich mays-order-aws ↔ RIS

| Sicht | to add | Differenz-Begründung |
|---|---:|---|
| mays-order-aws root (Default, Backups an) | 56 | core 37 + Backups 19 |
| mays-order-aws root (`enable_cognito_backup=false`) | **37** | dokumentierte Baseline |
| RIS `module.mays_orders` | **24** | = 37 − monitoring 7 − cloudtrail 6 |
| RIS root gesamt | **159** | RIS-Kern 135 + mays_orders 24 |

- 24 + 13 (monitoring 7 + cloudtrail 6) = 37 ✓
- 37 + 19 (cognito_backup 5 + automation 14) = 56 ✓
- 159 − 24 = 135 (übrige RIS-Ressourcen)

## 4. Befund

- Kein Zähler-/Wiring-Defekt: Plan valide, 0 change/destroy, keine Duplikate,
  keine Ressourcen doppelt gezählt.
- **Coverage-Lücke:** `module.mays_orders` besitzt weder Monitoring- noch
  CloudTrail-Ressourcen (bewusst), und die RIS-Module `monitoring` (8) und
  `cloudtrail` (6) sind **nur am RIS-Kern** verkabelt
  (`module.api`, `module.lambda`, `module.dynamodb.work_items`, `module.sqs`).
- Abdeckung trotzdem vorhanden: account-weiter RIS-CloudTrail (Audit) und
  Log-Retention im Orders-Modul (`monitoring_enabled`, `log_retention_days`).
  Orders-spezifische CloudWatch-Alarme fehlen.

## 5. Optionen

- **A** `module.mays_orders` an RIS-Monitoring anbinden (2. Instanz bzw.
  Modul-Erweiterung für api/lambda/table/queue) → +7 Ressourcen auf 166.
- **B** Vertrag akzeptieren: Gap dokumentieren (Trail + Log-Retention).
- **C** builder-Preset in mays-order-aws opt-in erweitern.

## 6. Reproduktion

```bash
cd terraform
# lokaler Backend-Override (nur lokal, nicht committen)
cat > backend_local_override.tf <<'EOF'
terraform { backend "local" { path = "terraform.tfstate.local" } }
EOF
AWS_PROFILE=mayaws terraform init -reconfigure
AWS_PROFILE=mayaws terraform plan -lock=false -input=false \
  -var="filename=lambda.zip" \
  -var="health_writer_zip_path=lambda.zip" \
  -var="health_publisher_zip_path=lambda.zip"
rm backend_local_override.tf
```
