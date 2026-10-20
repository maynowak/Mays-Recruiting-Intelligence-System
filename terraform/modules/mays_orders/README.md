# Mays-Order-AWS — Orders-Service Terraform-Modul

**Vertrag (MAYS-ORDERS-MODULE-CONTRACT-01):** Dieses Verzeichnis ist ein
vollständiges, wiederverwendbares Terraform-Modul, das den **Orders-Service**
bereitstellt. Feste Zusammensetzung (nicht abwählbar):

- Orders-API (HTTP API v2, JWT-Autorisierung) + Orders-Handler-Lambda
- Orders-Worker-Lambda (SQS-Consumer, Status-Verarbeitung)
- Orders-SQS-Queue (asynchrone Verarbeitung)
- Eigene Orders-DynamoDB-Tabelle (GSI1/GSI2)
- Erforderliche Orders-IAM-Rollen/Policies (Least Privilege; SQS-Berechtigung
  nur mit angebundener Queue — count-gated)
- Cognito User Pool/Client/Gruppe `staff` (JWT-Grundlage der Orders-API)

Nicht Bestandteil des Vertrags (Verantwortung des integrierenden Projekts):
Monitoring, CloudTrail, Cognito-Backups, Seed-Daten, Remote-Backend,
Policy-Gate-Ausführung (Root-Ebene), externe Infrastruktur.

## Nutzung (lokales Modul)

```hcl
provider "aws" {
  region = "eu-central-1" # Region liefert der Aufrufer — das Modul setzt keine Region
}

module "orders" {
  source = "../module/Mays-Order-AWS"

  project_name = "test-arn"     # Pflicht (Ressourcen-Namen + Project-Tag)
  # tags                 = { ManagedBy = "terraform" }  # optional
  # monitoring_enabled  = true                              # optional (Default true)
  # log_retention_days   = 7                                 # optional (Default 7)
}

output "orders_api" {
  value = module.orders.api_gateway_endpoint
}
```

## Variablen (vollständiger Input-Vertrag)

| Variable | Typ | Default | Bedeutung |
|---|---|---|---|
| `project_name` | string | `"test-arn"` | Präfix aller Orders-Ressourcen + `Project`-Tag |
| `tags` | map(string) | `{}` | Zusatz-Tags; `Maker`/`Environment` werden intern ergänzt (Tag-Parität zum Stamm-Deploy) |
| `monitoring_enabled` | bool | `true` | Log-Group/Retention-Steuerung in Lambda-/Worker-Modulen |
| `log_retention_days` | number | `7` | CloudWatch-Log-Retention |
| `external_cognito` | object | `null` | **MANAGED (Default/null):** eigener Pool + App Client + Gruppe `staff`. **EXTERNAL (Objekt):** vorhandener Pool des integrierenden Projekts — `user_pool_endpoint` (Format `cognito-idp.<region>.amazonaws.com/<pool-id>`, **ohne** `https://`) + `user_pool_client_id`. Fail-closed bei unvollständigen Referenzen. |

## Cognito-Varianten (MANAGED / EXTERNAL)

**MANAGED (Standard):** Ohne `external_cognito` erstellt das Modul seinen
eigenen Cognito User Pool + App Client + Gruppe `staff` — identisch zum
bisherigen Verhalten; JWT-Authorizer nutzt `https://<pool-endpoint>`.

**EXTERNAL:** Mit gültigem `external_cognito` verwendet das Modul den
vorhandenen Pool/Client; es werden **keine** Cognito-Ressourcen erzeugt und
**keine** fremden Ressourcen verändert. Der JWT-Authorizer bleibt aktiv
(issuer/audience aus den externen Referenzen).

```hcl
module "orders" {
  source = "../module/Mays-Order-AWS"

  project_name = "test-arn"
  external_cognito = {
    user_pool_endpoint = "cognito-idp.eu-central-1.amazonaws.com/eu-central-1_XXXXXXX"
    user_pool_client_id = "1a2b3c4d5e6f7g8h9i0j1k2l3"
  }
}
```

**Outputs im EXTERNAL-Modus:** `cognito_user_pool_endpoint` und
`cognito_user_pool_client_id` geben die tatsächlich verwendeten externen
Referenzen zurück. `cognito_user_pool_id`, `cognito_user_pool_arn` und
`cognito_user_pool_group_name` sind `null` (vom Modul nicht verwaltet —
dokumentierte Inkompatibilität statt stiller Umdeutung; Lösungsvorschlag:
optionale Zusatzfelder im `external_cognito`-Objekt, freizugeben).

**Migration MANAGED → EXTERNAL (NICHT automatisiert):** Ein Wechsel eines
bestehenden Deployments führt zur geplanten Entfernung des verwalteten Pools
(inkl. Nutzer/Gruppen). Kontrollierter Wechsel erfordert: menschliche Freigabe,
Nutzer-/Gruppen-Migration in den Zitpool, bewusstes `terraform state rm` der
Cognito-Adressen oder Destruktion des Modul-Pools, anschließende EXTERNAL-
Konfiguration. Keine automatische Umschaltung/State-Migration durch das Modul.

## Outputs (vollständiger Output-Vertrag)

`dynamodb_table_name`, `dynamodb_table_arn`, `iam_handler_role_name`,
`iam_handler_role_arn`, `lambda_function_name`, `lambda_function_arn`,
`lambda_invoke_arn`, `cognito_user_pool_id`, `cognito_user_pool_arn`,
`cognito_user_pool_endpoint`, `cognito_user_pool_client_id`,
`cognito_user_pool_group_name`, `api_gateway_endpoint`, `api_gateway_id`,
`api_gateway_stage_name`, `api_gateway_authorizer_id`, `sqs_queue_url`,
`sqs_queue_arn`, `sqs_worker_lambda_arn`

## Betriebs- und Vertragsnotizen

- **Artefakte:** `lambda/dist/lambda.zip` liegt im Modul (`${path.module}`),
  Rebuild über `cd lambda && python3 build_zip.py` (Quelle in `lambda/src/`).
- **Keine AWS-Dienste über den Orders-Service hinaus**; keine Provider-Region,
  kein Backend, keine Tags-Dritter im Modul.
- **Upgrades:** Adressen (`module.orders.*`) und Outputs bleiben stabil;
  Ressourcen-Identitäten/Naming-Konventionen unverändert. Nach einem Modul-
  Austausch prüft das integrierende Projekt seinen Plan (keine automatische
  State-Migration).
- **Governance:** Policy-Gate ist Root-Sache des Aufrufers; das MO-Gate liegt
  im Quell-Repo (`terraform/policy/`).
- **Privacy:** interne Privacy-Funktionen sind nicht produktiv aktiviert
  (BLOCKED — Secret-Management fehlt).
