# Mays-Orders Module Builder Wrapper

## Zweck
Bequemer Wrapper im RIS-Installer, der das Mays-Orders-AWS Terraform-Modul über den offiziellen `module_builder` erzeugt und in `terraform/modules/mays_orders` installiert.

Warum im Installer?
* Der Wrapper muss auf `installer/projects/*`, `terraform/main.tf` und den RIS Installer-Lifecycle zugreifen.
* Component-Naming `${var.project_name}-mays-orders` und Output-Patches für RIS-Verkabelung gehören in den RIS-Build-Prozess.
* Einheitliche Ausführung, Logging und Post-Runs `fmt`/`validate` mit dem RIS-Installer.

## Vorzugsweg für die Orders-Integration
Der Modul-Builder ist der **bevorzugte** Integrationsweg (statt der noch
unfertigen phasenweisen `installer.ris install --through`-Sequenz). Vorteile:

* **Parallele Entwicklung:** `mays-order-aws` wird pro Build frisch aus `main`
  gezogen; RIS und MO brauchen keinen gemeinsamen Release-Zeitpunkt.
* **Entkopplung:** RIS verdrahtet nur die generierten Modul-Outputs; interne
  MO-Änderungen bleiben im fremden Stack.
* **Sicherheitsnetz:** der Wrapper patcht nach jedem Build das plan-bekannte
  SQS-Gate und **bricht laut ab**, wenn die Upstream-Quelle das Muster verletzt.
* **Reproduzierbar:** `--check` prüft Modul, Output-Patch, Naming und `validate`.

Kurz: `installer.ris` (Phasen) und Orders-Integration können unabhängig
weiterentwickelt werden; der Modul-Builder hält die Verkabelung stabil.

## Pfade
* Builder-Clone: `installer/projects/mays_order_builder` → `main` von `maynowak/mays-order-aws`
* Installer-Pin bleibt separat: `installer/projects/mays_orders` → `5cf50a0` per `mays-orders-clone.pinned.json`
* Zielmodul: `terraform/modules/mays_orders`

## Nutzung
```bash
# Bauen / erneuern
python -m installer.build_mays_orders_module --project-name ris-dev --force

# Nur prüfen ob alles da ist (Modul, sqs_queue_name, Component-Naming, sqs_enabled-Gate, validate)
python -m installer.build_mays_orders_module --check

# Aufräumen (entfernt das generierte Modul; der nächste Lauf baut es neu)
python -m installer.build_mays_orders_module --clean
```

## Was der Wrapper macht
1. `installer/projects/mays_order_builder` sicherstellen, `main` checkout
2. `python -m module_builder build --preset orders-service --target terraform/modules/mays_orders --project-name <name> --validate [--force]`
3. Output-Patch: `output "sqs_queue_name"` sicherstellen für Monitoring-Wiring
4. `terraform/main.tf` patchen: `module "mays_orders" { project_name = "${var.project_name}-mays-orders" }`
5. `patch_iam_sqs_gate()`: SQS-Gate als plan-bekanntes `count = var.sqs_enabled ? 1 : 0`
   (ARN bleibt Policy-Resource); bricht ab, wenn eine Upstream-Zeile `count` + `sqs_queue_arn` kombiniert
6. Post-Run: `terraform fmt -check -recursive`, `terraform init -backend=false`, `terraform validate`

## ARN-first Hinweis
Verkabelung erfolgt über ARN wo möglich. `orders_handoff_vars` im Installer leitet Queue ARN deterministisch ab. Modul-Outputs werden auf Vollständigkeit geprüft.

## Dokumentation / Reports
* Ausführungslos: `docs/reports/02-01-WRAPPER-MAYS-ORDERS-MODULE-BUILDER-EXECUTION_LOG.md`
* Audit Log: `docs/AI_AUDITLOG.md`
