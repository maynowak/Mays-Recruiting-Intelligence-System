# Fix: Health-Lambda-Log-Groups überlebten jeden Destroy (2026-10-19)

**Befund** aus `PARALLEL-TESTABDECKUNG-ANALYSE-2026-10-19.md` §4 (GELB),
entdeckt durch den ausgebauten Volltest (`destroy-check` prüft `Log-Groups == 0`).

## Symptom

Nach erfolgreichem `terraform destroy` (State 0) verblieben je Installation:

```
/aws/lambda/ris-a-dev-health-writer        /aws/lambda/ris-a-dev-health-publisher
/aws/lambda/ris-b-dev-health-writer        /aws/lambda/ris-b-dev-health-publisher
/aws/lambda/mays-ris-b-dev-health-writer   (Rest der falsch etikettierten Ausführung)
```

## Ursache

`modules/health_plane/main.tf` deklarierte `aws_lambda_function.health_writer` und
`.health_publisher` **ohne** `aws_cloudwatch_log_group`. Der Lambda-Dienst legt die
Gruppe beim ersten Invoke automatisch an; Terraform kennt sie nicht → `destroy` kann
sie nicht entfernen. Alle übrigen Log-Groups (core-Modul, `orders_reader`, `mays_orders`)
sind verwaltet und wurden sauber gelöscht.

## Änderung

| Datei | Änderung |
|---|---|
| `terraform/modules/health_plane/main.tf` | `aws_cloudwatch_log_group.health_writer` + `.health_publisher`, `retention_in_days = var.log_retention_days` |
| `terraform/modules/health_plane/variables.tf` | neues `log_retention_days` (default 14, kern-konsistent) |
| `terraform/main.tf` | `module.health_plane` erhält `log_retention_days = var.lambda_config.log_retention_days` |

**Effekt:** Ressourcenzahl 167 → **169**; Destroy vollständig; Retention kostenbewusst
statt „never expire" (Lambda-Default).

## Aufräumen

Die 5 verwaisten Gruppen wurden gelöscht (alle gehörten früheren Ausführungen dieses
Projekts, `ris-a-*` / `ris-b-*` / `mays-ris-b-*`; fremde Ressourcen blieben unberührt).

## Verifikation

```
Plan A nach Fix: 169 to add, 0 to change, 0 to destroy; 0 × mays-ris-dev im Plan
destroy-check nach dem nächsten Destroy muss: LogGroups ris-a → 0, ris-b → 0
```

## Hinweis Bestandsinstallation

Für `mays-ris` (falls noch installiert) erzeugt der nächste Apply `already exists`-Fehler,
solange die unverwalteten Gruppen existieren. Vorbereitung:
`terraform import module.health_plane.aws_cloudwatch_log_group.health_writer /aws/lambda/mays-ris-dev-health-writer`
(analog publisher).
