# Schritt 2 – terraform apply (Option A) mit Profil mayaws (2026-10-19)

**Datum:** 2026-10-19
**Status:** COMPLETED (GREEN)
**Ausführung:** direkt in `<RIS-Root>/terraform` (kein Installer)
**Profil:** `AWS_PROFILE=mayaws` → Account `240571105849`, User `Mayaws`, Region `eu-central-1`

## 1. Backend-Bootstrap (notwendig, vor apply)

| Aktion | Ergebnis |
|---|---|
| Lock-Tabelle `mays-ris-tf-lock` angelegt (PAY_PER_REQUEST, `LockID` S, Tags Project/Maker/Environment) | OK (vorher `list-tables` = leer) |
| Lokaler Backend-Override entfernt (`*_override.tf`, gitignored) | OK |
| `terraform init -reconfigure -backend-config="bucket=mays-ris-tf-state-dev" -backend-config="region=eu-central-1"` | OK (partieller S3-Backend aus `main.tf`: key `terraform.tfstate`, `encrypt=true`, Lock-Tabelle `mays-ris-tf-lock`) |
| State-Lage | `s3://mays-ris-tf-state-dev/terraform.tfstate` (Default-Workspace, vorher kein Objekt am Bucket-Root → frische Anlage) |

## 2. Plan (mit Lock gegen S3)

```
terraform plan -out=ris_option_a.tfplan -input=false
→ Plan: 167 to add, 0 to change, 0 to destroy   (Exit 0, 0 Fehler)
```

## 3. Apply

```
terraform apply -input=false -auto-approve ris_option_a.tfplan
→ Apply complete! Resources: 167 added, 0 changed, 0 destroyed.   (Exit 0)
```

Keine Fehler, keine Destroy-/Replace-Aktionen.

## 4. Wesentliche Outputs nach Apply

- RIS API (JWT) + Orders-API (HTTP API v2, JWT-Authorizer)
- Lambdas: `mays-ris-dev-agent`, `mays-ris-dev-orders-reader`,
  `mays-ris-dev-health-writer`, `mays-ris-dev-health-publisher`,
  Orders-Handler + Orders-Worker
- DynamoDB: work-items, user-profile, agent-catalog, entitlements,
  agent-state, jobsearches, orders (+ weitere)
- SQS: work/ats/cv/match (+ Orders-Queue)
- Rollen/ARN, Dashboard `mays-ris-overview` + `mays-ris-orders-overview`

## 5. Hinweise

- Variablen: `filename`/`health_writer_zip_path`/`health_publisher_zip_path`
  zeigen auf `lambda/dist/*.zip` (Repo-Artefakte).
- Defaults: `project_name = mays-ris`, `environment = dev` → Namen `mays-ris-dev-*`.
- Nicht Teil dieses Apply: Installer-Phasen, Policy-Gate, Workspaces des Installers.
