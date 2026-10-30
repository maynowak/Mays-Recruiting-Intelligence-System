# DEPLOYMENT-CONTEXT

**Stand:** 2026-10-25
**Gültig für:** Permanente RIS Entwicklungsinstallation

## Aktuelle permanente Entwicklungsinstallation

| Eigenschaft | Wert |
|---|---|
| Projektname | ris-dev |
| AWS-Profil | mayaws |
| AWS-Account | 240571105849 |
| Region | eu-central-1 |
| Terraform-Workspace | ris-dev |
| State-Key | env:/ris-dev/dev/terraform.tfstate |
| Ressourcenfamilien | ris-dev-*, ris-dev-dev-* |
| Cognito User Pool | eu-central-1_ojbmoiYGM |
| Custom Domain | auth.mays-job-matcher.app |

## Namenskonventionen

Terraform: `prefix = "${var.project_name}-${var.environment}"`
Beispiel: `ris-dev-dev-users`, `ris-dev-dev-api`, `ris-dev-mays-orders`

## Historische Vorgängerinstallationen

| Name | Status | Zeitraum |
|---|---|---|
| mays-ris | zerstört | Legacy, nicht mehr aktiv |
| ris-development | zerstört | Vorheriger Dev-Stack, durch ris-dev ersetzt |

Gründe für Umbenennung:
* Namenslängenlimit für CloudTrail Bucket und Cognito Backup
* Konsistente 7 Zeichen Projektname für `ris-dev-mays-orders` ≤ 39 Zeichen

## Abgrenzung temporäre Testinstallationen

Temporäre Testinstallationen wie `ris-a`, `ris-b` sind nicht Teil der permanenten Dev-Installation. Sie werden für Paralleltests genutzt und nach Tests zerstört.

## Referenzen

* SYSTEM-ARCHITECTURE.md
* RUNTIME-PATH.md
* API-STANDARD.md
* README.md

Änderungen an diesem Dokument nur nach Freigabe.
