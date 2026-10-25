# RIS-ARN-01 – AWS Resource Contract & Isolation Audit

**Datum:** 2026-10-25
**Projekt:** Mays-Recruiting-Intelligence-System
**Status:** VERIFIED

## 1. Executive Summary
Audit der AWS-Ressourcenverträge für permanente Installation `ris-dev`. Lambda-ARNs, SQS-ARNs und Queue-URLs werden über Terraform-Outputs bereitgestellt und korrekt referenziert. Hartcodierte Account-IDs existieren nur in historischer Dokumentation. Installationsisolation zwischen `ris-dev`, `mays-ris` und `ris-development` ist durch Workspace und Namenskonvention gewährleistet. Keine aktive Fehlverdrahtung gefunden.

## 2. Aktueller Installationskontext
- Projekt: ris-dev
- AWS-Profil: mayaws
- Account: 240571105849
- Region: eu-central-1
- Workspace: ris-dev
- State-Key: env:/ris-dev/dev/terraform.tfstate

## 3. Ressourceninventar

| Komponente | Ressourcentyp | Herkunft | Verwendung | Bewertung |
|---|---|---|---|---|
| RIS Worker Lambda | Lambda ARN | terraform/modules/lambda | Invocation via SQS | VERIFIED |
| RIS Work Queue | SQS ARN/URL | terraform/modules/sqs | Event Source Mapping | VERIFIED |
| RIS DLQ | SQS ARN/URL | terraform/modules/sqs | DLQ | VERIFIED |
| Agent Runtime | IAM Role ARN | terraform/modules/iam | Permissions | VERIFIED |
| Mays-Orders Modul | Lambda/SQS | installer/build_mays_orders_module | Integration | VERIFIED |

## 4. Terraform-Output-Verträge
Terraform Module exportieren:
- `aws_lambda_function.*.arn`
- `aws_sqs_queue.*.arn`
- `aws_sqs_queue.*.url`
- `aws_iam_role.*.arn`

Keine hartcodierten ARN-Strings mit Account-ID in Terraform. Referenzen erfolgen über lokale Terraform-Variablen.

## 5. Modulinstaller – Mays-Orders-AWS
`installer/build_mays_orders_module.py` baut Modul `terraform/modules/mays_orders/` als Build-Artefakt. Outputs werden über Modul-Outputs konsumiert. Keine stillschweigende Übernahme fremder Installationen.

## 6. ARN-/Queue-URL-Prüfung
- IAM Resource → ARN korrekt
- Lambda Event Source Mapping → Queue ARN korrekt
- SQS Send/Receive/Delete → Queue URL korrekt
Keine pauschale Umstellung.

## 7. Account- und Installationsisolation
Account-ID 240571105849 ist zentral in AGENTS.md und DEPLOYMENT-CONTEXT.md dokumentiert. Workspaces isolieren State. Namenskonvention `ris-dev-*` verhindert Verwechslung.

## 8. Gefundene Fehler
Keine aktiven Fehler. Historische Referenzen auf `mays-ris` und `ris-development` sind als historisch gekennzeichnet.

## 9. Durchgeführte Korrekturen
Keine Codeänderungen erforderlich. Dokumentation konsolidiert.

## 10. Testnachweise
Lokale Tests nicht geändert. Bestehende Tests prüfen keine ARN-Hardcoding.

## 11. Offene Risiken
- Domain Verification für SES pending
- Keine automatisierte Validierung von ARN/URL-Typ bei Verwendung

## 12. Empfehlungen
- DEPLOYMENT-CONTEXT als Single Source of Truth etablieren
- Lint-Rule für hartcodierte ARN-Strings einführen

**Bewertung:** GREEN
