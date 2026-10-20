# Mays-Orders Module Builder Wrapper

## Zweck
Bequemer Wrapper im RIS-Installer, der das Mays-Orders-AWS Terraform-Modul über den offiziellen `module_builder` erzeugt und in `terraform/modules/mays_orders` installiert.

Warum im Installer?
* Der Wrapper muss auf `installer/projects/*`, `terraform/main.tf` und den RIS Installer-Lifecycle zugreifen.
* Component-Naming `${var.project_name}-mays-orders` und Output-Patches für RIS-Verkabelung gehören in den RIS-Build-Prozess.
* Einheitliche Ausführung, Logging und Post-Runs `fmt`/`validate` mit dem RIS-Installer.

## Pfade
* Builder-Clone: `installer/projects/mays_order_builder` → `main` von `maynowak/mays-order-aws`
* Installer-Pin bleibt separat: `installer/projects/mays_orders` → `5cf50a0` per `mays-orders-clone.pinned.json`
* Zielmodul: `terraform/modules/mays_orders`

## Nutzung
```bash
# Bauen / erneuern
python -m installer.build_mays_orders_module --project-name mays-ris --force

# Nur prüfen ob alles da ist
python -m installer.build_mays_orders_module --check

# Aufräumen
python -m installer.build_mays_orders_module --clean
```

## Was der Wrapper macht
1. `installer/projects/mays_order_builder` sicherstellen, `main` checkout
2. `python -m module_builder build --preset orders-service --target terraform/modules/mays_orders --project-name <name> --validate [--force]`
3. Output-Patch: `output "sqs_queue_name"` sicherstellen für Monitoring-Wiring
4. `terraform/main.tf` patchen: `module "mays_orders" { project_name = "${var.project_name}-mays-orders" }`
5. Post-Run: `terraform fmt -check -recursive`, `terraform init -backend=false`, `terraform validate`

## ARN-first Hinweis
Verkabelung erfolgt über ARN wo möglich. `orders_handoff_vars` im Installer leitet Queue ARN deterministisch ab. Modul-Outputs werden auf Vollständigkeit geprüft.

## Dokumentation / Reports
* Ausführungslos: `docs/reports/02-01-WRAPPER-MAYS-ORDERS-MODULE-BUILDER-EXECUTION_LOG.md`
* Audit Log: `docs/AI_AUDITLOG.md`
