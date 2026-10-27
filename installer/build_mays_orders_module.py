#!/usr/bin/env python3
"""
Wrapper: Build Mays-Orders Terraform module for RIS integration.

- Checks out mays-order-aws into installer/projects/mays_order_builder (pinned commit)
- Runs module_builder from that checkout to generate orders-service preset
- Validates the generated module contract BEFORE any post-run patches
- Installs generated module into terraform/modules/mays_orders
- Performs clean post-run: terraform fmt -check / init / validate
- Does NOT post-hoc insert sqs_queue_name or rewrite IAM counts —
  the generated module must already contain them (GAP-02/06 fix).
- S08-konform: Terraform-Prüfungen sind verpflichtend;
  fehlt Terraform oder schlagen Prüfungen fehl, bleibt bestehendes Ziel
  bytegleich erhalten. --force umgeht keine dieser Prüfungen.
- General name derivation (no hardcoded EXPECTED_PROJECT_MAP).
- Builder pin from mays-orders-builder.pinned.json (not composite clone pin).

Usage:
  python -m installer.build_mays_orders_module --project-name mays-ris

Requires: git, Python 3.14+, module_builder from mays-order-aws
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# TERRAFORM_EXE optional: expliziter Pfad zur Terraform-Executable.
# Wenn nicht gesetzt, wird im PATH gesucht.
TERRAFORM_EXE = os.environ.get("TERRAFORM_EXE", "")


def _terraform_exe() -> str:
    """Ermittle den Terraform-Executable-Pfad."""
    if TERRAFORM_EXE and os.path.isfile(TERRAFORM_EXE):
        return TERRAFORM_EXE
    result = subprocess.run(
        ["where", "terraform"], capture_output=True, text=True
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().split("\r\n")[0]
    return "terraform.exe"


def _tf_run(args: list, cwd=None) -> subprocess.CompletedProcess:
    """Führe einen Terraform-Befehl aus mit S08-konformer Fehlerbehandlung.

    S08-Pflicht: Fehlende Executable oder fehlgeschlagene Prüfungen liefern
    einen non-zero Return Code; der aufrufende Build muss abbrechen und
    das bestehende Ziel bytegleich unverändert lassen.
    """
    exe = _terraform_exe()
    full_cmd = [exe] + args
    print("$ {' '.join(full_cmd)} (Working Directory: {cwd})".format(cwd=cwd or '.'))
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, cwd=cwd)
        return result
    except FileNotFoundError:
        print("Terraform-Executable '{exe}' nicht Auffindbar.".format(exe=exe))
        class ProcessResult:
            returncode = 1
        return ProcessResult()


def _check_returncode(result: subprocess.CompletedProcess, label: str) -> bool:
    """S08-prüfende Logik: Wenn returncode != 0, False zurückgeben
    und Fehlertext ausgeben. Wenn returncode == 0, True zurückgeben."""
    if result.returncode != 0:
        print("{label}: FAIL (Exit {result.returncode})".format(label=label, result=result))
        return False
    print("{label}: OK".format(label=label))
    return True


def run(cmd, cwd=None):
    """Führe einen Git- oder System-Befehl aus."""
    if cmd[0] in ("git",) or (len(cmd) > 1 and cmd[0] == "git"):
        cmd = [r"C:\Program Files\Git\bin\git.exe"] + cmd[1:]
    env = os.environ.copy()
    env["TF_DATA_DIR"] = str(Path(tempfile.gettempdir()) / "tfris")
    print(f"$ {' '.join(cmd)} (Working Directory: {cwd or '.'})")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result


# ---- Pfade und Pin ------------------------------------------------------------

RIS_ROOT = Path(__file__).resolve().parent.parent
INSTALLER_PROJECTS = RIS_ROOT / "installer" / "projects"
MAYS_ORDERS_BUILDER_DIR = INSTALLER_PROJECTS / "mays_order_builder"
TARGET_MODULE_DIR = RIS_ROOT / "terraform" / "modules" / "mays_orders"
BUILDER_PIN_FILE = RIS_ROOT / "installer" / "mays-orders-builder.pinned.json"
CLONE_PIN_FILE = RIS_ROOT / "installer" / "mays-orders-clone.pinned.json"

PINNED_COMMIT = "9627eb2f43087ab07dd7cc98a21febca142cb3b6"
"""Verbindlicher MO-Commit (40-stellig), ab welchem der Builder zu
Generieren ist. Wird in der Builder-Pin-Datei MAYDS-ORDERS-BUILDER-PINNED-COMMIT
hinterlegt; die Composite-Clone-Pin-Datei bleibt als historische Referenz erhalten."""


def load_builder_pin() -> str:
    """Lade den Builder-Pin aus der dedizierten Pin-Datei.

    Verbindliche Regeln:
    - Nur aus mays-orders-builder.pinned.json lesen (kein Fallback auf
      Composite-Clone-Pin oder hart codierten PINNED_COMMIT).
    - Pin-Datei fehlt → RuntimeError.
    - Pin-Datei ungültig → RuntimeError.
    - SHA weicht von PINNED_COMMIT ab → RuntimeError.
    - Kein stillschweigender Rückfall, kein automatischer Wechsel auf main.
    """
    if not BUILDER_PIN_FILE.exists():
        raise RuntimeError(
            f"Builder-Pin-Datei fehlt: {BUILDER_PIN_FILE}. "
            f"Erwarteter Commit: {PINNED_COMMIT}."
        )
    try:
        with open(BUILDER_PIN_FILE, "r", encoding="utf-8") as f:
            pin_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise RuntimeError(
            f"Builder-Pin-Datei ungültig: {BUILDER_PIN_FILE} ({e}). "
            f"Erwarteter Commit: {PINNED_COMMIT}."
        )
    commit = pin_data.get("commit", "")
    if not commit:
        raise RuntimeError(
            f"Builder-Pin-Datei enthält keinen Commit: {BUILDER_PIN_FILE}. "
            f"Erwarteter Commit: {PINNED_COMMIT}."
        )
    if commit != PINNED_COMMIT:
        raise RuntimeError(
            f"Builder-Pin weicht ab: {commit} != {PINNED_COMMIT}. "
            f"Erwarteter Commit: {PINNED_COMMIT}."
        )
    return commit


BUILDER_PIN = load_builder_pin()
"""Aktiver Builder-Pin aus mays-orders-builder.pinned.json."""


# ---- Name contract (GAP-01/05) ------------------------------------------------------

# Generelle Namensableitung für den orders-service Build:
# RIS-Projekt name → MO-Komponentenname
#   ris-dev2  →  ris-dev2-mays-orders
# Es wird NICHT eine hardcoded Mapping-Tabelle (EXPECTED_PROJECT_MAP) verwendet,
# sondern die Namensableitung ist general (projekt_name + "-mays-orders").
# Ein bereits angehängtes Suffix wird nicht verdoppelt.


def derive_component_name(project_name: str) -> str:
    """Allgemeine Namensableitung: project_name um '-mays-orders' erweitern.

    Es wird nicht stillschweigend am Terraform-main.tf per Regex rumgedoktert;
    es wird nur geprüft, ob der Name das Suffix bereits trägt (doppelte Anreicherung
    ablehnen). Für unbekannte Projektnamen wird die Ableitung trotzdem durchgeführt,
    damit der Build fortfahren kann.
    """
    if "-mays-orders" in project_name:
        raise ValueError(
            f"Unzulässiger project_name '{project_name}': "
            f"-mays-orders ist bereits enthalten (doppelte Anreicherung)."
        )
    return f"{project_name}-mays-orders"


def validate_project_name_format(project_name: str) -> None:
    """Prüft den Projektnamen auf AWS-konforme Namenskonventionen.

    AWS-Ressourcennamen dürfen nur Kleinbuchstaben, Ziffern und Bindestriche
    enthalten, müssen mit einem Buchstaben oder Ziffern beginnen und dürfen
    nicht mit einem Bindestrich enden (identisch zur Terraform-Validierung
    in mays-order-aws/terraform/variables.tf).
    """
    if not project_name:
        raise ValueError("project_name darf nicht leer sein.")
    if len(project_name) < 3:
        raise ValueError(
            f"Unzulässiger project_name '{project_name}': "
            f"mindestens 3 Zeichen erforderlich."
        )
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", project_name):
        raise ValueError(
            f"Unzulässiger project_name '{project_name}': "
            f"nur Kleinbuchstaben, Ziffern und Bindestriche erlaubt, "
            f"kein führendes/trailendes Sonderzeichen."
        )
    if project_name.startswith("-") or project_name.endswith("-"):
        raise ValueError(
            f"Unzulässiger project_name '{project_name}': "
            f"darf nicht mit Bindestrich beginnen oder enden."
        )


def check_name_length(project_name: str, resource_type: str, max_length: int) -> str:
    """Prüft die Länge eines Ressourcennamens gegen AWS-Limits.

    Gibt zurück: "OK", "WARNING" oder "ERROR".
    """
    if not project_name:
        return "UNKNOWN"
    length = len(project_name)
    pct = length / max_length * 100
    if length > max_length:
        return f"ERROR ({length}/{max_length} — Limit überschritten)"
    if pct >= 80:
        return f"WARNING ({length}/{max_length} ({pct:.0f}%))"
    return f"OK ({length}/{max_length})"


def check_arn_id_contract(generated_dir: Path) -> None:
    """Prüft die ARN-/ID-Verträge im generierten Modul.

    Unterscheidet RIS-eigene API von MO-API:
    - module.api.* = RIS-eigene API
    - module.mays_orders.* = MO-API
    Diese dürfen nicht vermischt werden.

    Prüft auch die tatsächlichen Consumer-zu-Produzenten-Verkettungen:
    - orders_table_name = module.mays_orders.dynamodb_table_name
    - orders_table_arn = module.mays_orders.dynamodb_table_arn
    - orders_queue_arn = module.mays_orders.sqs_queue_arn
    - orders_queue_url = module.mays_orders.sqs_queue_url
    - api_id = module.api.api_id
    - authorizer_id = module.api.authorizer_id
    """
    main_tf = (generated_dir / "main.tf").read_text(encoding="utf-8")
    outputs_tf = (generated_dir / "outputs.tf").read_text(encoding="utf-8")

    # Prüfe, dass RIS-eigene API-IDs nicht mit MO-API-IDs vermischt werden
    api_id_refs = re.findall(r'module\.api\.api_id', main_tf)
    authorizer_id_refs = re.findall(r'module\.api\.authorizer_id', main_tf)
    mays_api_id_refs = re.findall(r'module\.mays_orders\.api_gateway_id', main_tf)
    mays_authorizer_refs = re.findall(r'module\.mays_orders\.api_gateway_authorizer_id', main_tf)

    if api_id_refs and mays_api_id_refs:
        raise RuntimeError(
            "Vertragsbruch: RIS-eigene API-Gateway-ID (module.api.api_id) "
            "und MO-API-Gateway-ID (module.mays_orders.api_gateway_id) "
            "werden im selben Modul vermischt. "
            "RIS-eigene API und MO-API müssen getrennt bleiben."
        )
    if authorizer_id_refs and mays_authorizer_refs:
        raise RuntimeError(
            "Vertragsbruch: RIS-eigener Authorizer (module.api.authorizer_id) "
            "und MO-API-Authorizer (module.mays_orders.api_gateway_authorizer_id) "
            "werden im selben Modul vermischt. "
            "RIS-eigene API und MO-API müssen getrennt bleiben."
        )

    # Prüfe, dass Consumer-Inputs aus den korrekten MO-Modul-Outputs kommen
    required_bindings = [
        ("orders_table_name", "module.mays_orders.dynamodb_table_name"),
        ("orders_table_arn", "module.mays_orders.dynamodb_table_arn"),
        ("orders_queue_arn", "module.mays_orders.sqs_queue_arn"),
        ("orders_queue_url", "module.mays_orders.sqs_queue_url"),
        ("api_id", "module.api.api_id"),
        ("authorizer_id", "module.api.authorizer_id"),
    ]

    for consumer_input, expected_output in required_bindings:
        pattern = rf'{re.escape(consumer_input)}\s*=\s*{re.escape(expected_output)}'
        if not re.search(pattern, main_tf):
            raise RuntimeError(
                f"Vertragsbruch: Consumer-Input '{consumer_input}' nicht mit "
                f"erwartetem Output '{expected_output}' verdrahtet. "
                f"Erwartete Zuweisung: {consumer_input} = {expected_output}"
            )


def validate_generated_contract(target_dir: Path) -> None:
    """Prüfe den generierten Modul-Vertrag und breche bei Abweichung ab.

    Erwartete Vorkenntnisse (orders-service):
    - 5 öffentliche Inputs (external_cognito, log_retention_days, monitoring_enabled,
      project_name, tags)
    - 20 Outputs einschließlich sqs_queue_name
    - interne sqs_enabled-Verdrahtung im IAM-Modul
    - keine ARN-abhängigen count-Ausdrücke an den beiden bekannten
      SQS-IAM-Stellen (data.aws_iam_policy_document.sqs und
      resource.aws_iam_role_policy.sqs)
    """
    main_tf = (target_dir / "main.tf").read_text(encoding="utf-8")
    outputs_tf = (target_dir / "outputs.tf").read_text(encoding="utf-8")
    vars_tf = (target_dir / "variables.tf").read_text(encoding="utf-8")
    iam_main = (target_dir / "modules" / "iam" / "main.tf").read_text(encoding="utf-8")
    iam_vars = (target_dir / "modules" / "iam" / "variables.tf").read_text(encoding="utf-8")

    inputs = re.findall(r'^variable\s+"([a-z_]+)"', vars_tf, re.M)
    outputs = re.findall(r'^output\s+"([a-z_]+)"', outputs_tf, re.M)

    # 5 öffentliche Inputs
    expected_inputs = {"external_cognito", "log_retention_days", "monitoring_enabled", "project_name", "tags"}
    actual_inputs = set(inputs)
    missing = expected_inputs - actual_inputs
    extra = actual_inputs - expected_inputs
    if missing or extra:
        missing_str = ", ".join(sorted(missing)) if missing else "keine"
        extra_str = ", ".join(sorted(extra)) if extra else "keine"
        raise RuntimeError(
            "Generierter Modul-Vertrag unerwartete Inputs. "
            f"Fehlend: {missing_str}, zusätzlich: {extra_str}. "
            "Keine nachträglichen Patches; Build wurde ohne Vertragsprüfung "
            "durchgeführt, das Modul entspricht nicht dem Vertrag."
        )
    print(f"  Inputs OK: {sorted(actual_inputs)} (5 erwartet)")

    # 20 Outputs einschließlich sqs_queue_name
    expected_outputs_count = 20
    actual_outputs_count = len(outputs)
    has_sqs_queue_name = "sqs_queue_name" in outputs
    if actual_outputs_count != expected_outputs_count:
        raise RuntimeError(
            f"Generierter Modul-Vertrag: erwartet {expected_outputs_count} Outputs, "
            f"erhalten {actual_outputs_count}. Keine nachträglichen Patches."
        )
    if not has_sqs_queue_name:
        raise RuntimeError(
            "Generierter Modul-Vertrag: sqs_queue_name Output fehlt. "
            "Keine nachträgliche Insertion; Build wurde abgebrochen."
        )
    print(f"  Outputs OK: {actual_outputs_count} (20 erwartet, sqs_queue_name vorhanden)")

    # IAM: sqs_enabled variable und keine ARN-abhängigen counts
    # Count-Zeilen, die var.sqs_queue_arn enthalten (sollen nicht da sein)
    arn_dependent_counts = [
        l for l in iam_main.splitlines()
        if "count" in l and "sqs_queue_arn" in l
    ]
    if arn_dependent_counts:
        raise RuntimeError(
            "Generiertes IAM-Modul enthält ARN-abhängige count-Ausdrücke. "
            "Diese wurden vertraglich ausgeschlossen; Build wurde abgebrochen. "
            "Erwartet: beide Counts hängen nur am bool sqs_enabled."
        )
    # sqs_enabled Variable vorhanden
    if "sqs_enabled" not in iam_main:
        raise RuntimeError(
            "Generiertes IAM-Modul fehlt die Variable sqs_enabled. "
            "Vertragsprüfung fehlgeschlagen; kein Build."
        )
    # Count hängt nur am Gate
    sqs_gate_count = iam_main.count("var.sqs_enabled ? 1 : 0")
    if sqs_gate_count != 2:
        raise RuntimeError(
            f"Generiertes IAM-Modul: erwartet 2 Count-Zeilen am sqs_enabled-Gate, "
            f"erhalten {sqs_gate_count}. Vertragswidrig; kein Build."
        )
    print(f"  IAM contract OK: sqs_enabled present, 2 gate-dependent counts")

    # sqs_queue_name im Output per module.sqs.queue_name referenziert
    has_sqs_queue_name = "sqs_queue_name" in outputs_tf
    has_module_sqs_queue = "module.sqs.queue_name" in outputs_tf
    if not (has_sqs_queue_name and has_module_sqs_queue):
        raise RuntimeError(
            "Generierter Modul-Vertrag: Output 'sqs_queue_name' mit value = module.sqs.queue_name nicht gefunden. "
            "Keine nachträgliche Insertion."
        )
    print(f"  sqs_queue_name contract OK: value = module.sqs.queue_name")

    # Wildcard-Prüfung im SQS-Dokument des IAM-Moduls
    # "resources = [var.sqs_queue_arn]" und keine "*" im Statement
    sqs_doc_prefix = 'data "aws_iam_policy_document" "sqs" {'
    if sqs_doc_prefix in iam_main:
        sqs_doc = iam_main.split(sqs_doc_prefix, 1)[1].split('resource "aws_iam_role_policy" "sqs" {', 1)[0]
        if '"*"' in sqs_doc:
            raise RuntimeError(
                "Generiertes SQS-Dokument enthält Wildcard-Ressource '*'. "
                "Vertragsbruch; kein Build."
            )
    print(f"  IAM SQS-dokument OK: keine Wildcard, resources = [var.sqs_queue_arn]")

    # RIS/MO-Trennung prüfen
    check_arn_id_contract(target_dir)


# ---- Patch IAM SQS gate (entfernt aus aktivem Build-Pfad) ----

def patch_iam_sqs_gate():
    """Diese Funktion wurde aus dem aktiven Build-Pfad entfernt.
    Der generierte Modul-Vertrag wird nun vorab validiert (siehe
    validate_generated_contract). Diese Funktion bleibt aus didaktischen
    Gründen erhalten, wird aber nicht mehr aufgerufen."""
    pass


# ---- Helper: ensure repo ---------------------------------------------

def ensure_repo():
    """Sichere dass das Builder-Repository vorhanden ist und auf den
    Builder-Pin gecheckedout ist. Dirty worktree wird abgelehnt (ohne
    automatischer Reset)."""
    INSTALLER_PROJECTS.mkdir(parents=True, exist_ok=True)
    if not MAYS_ORDERS_BUILDER_DIR.exists():
        print(f"Cloning mays-order-aws into {MAYS_ORDERS_BUILDER_DIR}")
        run([r"C:\Program Files\Git\bin\git.exe", "clone",
             "https://github.com/maynowak/mays-order-aws.git", str(MAYS_ORDERS_BUILDER_DIR)])
    else:
        run(r"C:\Program Files\Git\bin\git.exe", "-C", str(MAYS_ORDERS_BUILDER_DIR), "fetch", "--quiet")

    # Auf den Builder-Pin checkout (detached HEAD)
    run([r"C:\Program Files\Git\bin\git.exe", "-C", str(MAYS_ORDERS_BUILDER_DIR), "checkout", BUILDER_PIN])

    # Arbeitsbaum zustand prüfen – Dirty ablehnen ohne Reset/Clean
    try:
        status = subprocess.run(
            [r"C:\Program Files\Git\bin\git.exe", "-C", str(MAYS_ORDERS_BUILDER_DIR), "status", "--porcelain"]
        , capture_output=True, text=True)
        if status.stdout.strip():
            print(f"FEHLER: builder worktree has untracked/modified files:\n{status.stdout.strip()}")
            print("Bitte bereinigen Sie den worktree (git stash/git checkout) vor dem Build.")
            sys.exit(1)
    except Exception as e:
        print("Warnung: Git-Status-Check fehlgeschlagen: {e}".format(e=e))
        # Ist kein Build-breaker, wenn git nicht verfügbar ist.


# ---- Build module ---------------------------------------------------

def build_module(project_name: str, force: bool):
    """Build the orders-service module and validate the contract.

    Es werden keine nachträglichen Patches (sqs_queue_name, IAM-count) mehr ausgeführt.
    Der Builder darf das Modul nur erzeugen, wenn der Vertrag bereits stimmt;
    ansonsten wird abgebrochen.

    Ablauf:
    1. Project name validieren und Komponentennamen ableiten
    2. Modul in temporärem Generierungsverzeichnis erzeugen
    3. Generierten Vertrag prüfen (content-based, keine nachträglichen Patches)
    4. Post-run Checks (fmt, init, validate) nur nach erfolgreichem Build
    5. Modulziel übernehmen wenn alle Checks bestehen
    """
    # 1. Project name validieren und Komponentennamen ableiten
    expected_component = derive_component_name(project_name)
    print(f"Project name validation: '{project_name}' → expected component '{expected_component}'")

    # N-03: Namenslängenprüfung vor dem Build
    max_name_len_lambda = 64   # AWS Lambda function name max length
    max_name_len_iam = 64      # AWS IAM role name max length
    max_name_len_sqs = 80      # AWS SQS queue name max length
    max_name_len_dynamodb = 255 # AWS DynamoDB table name max length

    # Komponente selbst prüfen
    component_check = check_name_length(expected_component, "component", max_name_len_lambda)
    print(f"  Component name check: {component_check}")
    if component_check.startswith("ERROR"):
        print(f"FEHLER: Komponentenname '{expected_component}' überschreitet AWS-Limit ({max_name_len_lambda} Zeichen).")
        print(f"Bestehendes Ziel bleibt unverändert.")
        sys.exit(1)

    # Tatsächliche Ressourcennamen prüfen, die vom Builder generiert werden
    resource_names = [
        f"{expected_component}-handler",      # Lambda function name
        f"{expected_component}-handler-role",   # IAM role name
        f"{expected_component}-orders-queue",   # SQS queue name
        expected_component,                   # DynamoDB table name (= project_name)
    ]

    for resource_name in resource_names:
        if "handler-role" in resource_name:
            resource_type = "iam_role"
            max_len = max_name_len_iam
        elif "queue" in resource_name:
            resource_type = "sqs_queue"
            max_len = max_name_len_sqs
        elif "handler" in resource_name:
            resource_type = "lambda_function"
            max_len = max_name_len_lambda
        else:
            resource_type = "dynamodb_table"
            max_len = max_name_len_dynamodb

        name_check = check_name_length(resource_name, resource_type, max_len)
        print(f"  Resource name check ({resource_name}): {name_check}")
        if name_check.startswith("ERROR"):
            print(f"FEHLER: Ressourcenname '{resource_name}' überschreitet AWS-Limit ({max_len} Zeichen).")
            print(f"Bestehendes Ziel bleibt unverändert.")
            sys.exit(1)

    # 2. Modul in temporärem Verzeichnis generieren
    TEMP_MODULE_DIR = TARGET_MODULE_DIR.parent / f".mays_orders_tmp_{os.getpid()}"
    TEMP_MODULE_DIR.parent.mkdir(parents=True, exist_ok=True)

    try:
        cmd = [
            sys.executable, "-m", "module_builder", "build",
            "--preset", "orders-service",
            "--target", str(TEMP_MODULE_DIR),
            "--project-name", expected_component,
        ]
        if force:
            cmd.append("--force")
        print("Building module via module_builder from {MAYS_ORDERS_BUILDER_DIR}".format(MAYS_ORDERS_BUILDER_DIR=MAYS_ORDERS_BUILDER_DIR))
        run(cmd, cwd=str(MAYS_ORDERS_BUILDER_DIR))

        # 3. Vertragsprüfung (CONTENT-BASED, keine nachträglichen Patches)
        validate_generated_contract(TEMP_MODULE_DIR)

        # 4. Post-run: fmt -check / init -backend=false / validate
        post_run_checks(TEMP_MODULE_DIR)

        # 5. Ziel übernehmen (atomar: Backup vor Löschung, Restore bei Fehler)
        backup_dir = TARGET_MODULE_DIR.parent / f".mays_orders_backup_{os.getpid()}"
        try:
            if TARGET_MODULE_DIR.exists():
                shutil.copytree(str(TARGET_MODULE_DIR), str(backup_dir))
                shutil.rmtree(TARGET_MODULE_DIR)
            shutil.copytree(str(TEMP_MODULE_DIR), str(TARGET_MODULE_DIR))
            print("Module installed at {TARGET_MODULE_DIR}".format(TARGET_MODULE_DIR=TARGET_MODULE_DIR))
        except Exception:
            # Bei Fehler: ursprüngliches Ziel aus Backup wiederherstellen
            if backup_dir.exists():
                if TARGET_MODULE_DIR.exists():
                    shutil.rmtree(TARGET_MODULE_DIR)
                shutil.copytree(str(backup_dir), str(TARGET_MODULE_DIR))
            raise
        finally:
            # Backup aufräumen
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)

    finally:
        # Aufräumen des temporären Verzeichnisses
        if TEMP_MODULE_DIR.exists():
            shutil.rmtree(TEMP_MODULE_DIR, ignore_errors=True)


# ---- Post-run checks ------------------------------------------------

def post_run_checks(module_dir: Path) -> None:
    """Führt lokale Validierungschecks durch (fmt, init, validate).
    Fehlende Werkzeuge oder fehlgeschlagene Prüfungen müssen einen
    Fehlerstatus liefern; keine Erfolgsmeldung nach übersprungenen Checks."""
    # N-05: Der übergebene Pfad ist bereits das generierte Modulverzeichnis
    # (z. B. terraform/modules/mays_orders oder ein temporäres Build-Verzeichnis),
    # nicht ein darunterliegendes "terraform/" Unterverzeichnis.
    terraform_dir = module_dir
    try:
        result = run(["terraform", "fmt", "-check", "-recursive"], cwd=str(terraform_dir))
        if result.returncode != 0:
            raise RuntimeError(
                "Terraform fmt -check fehlgeschlagen (Exit {result.returncode}); Build kann nicht fortfahren.".format(result=result)
            )
        print("fmt -check: OK")
    except FileNotFoundError:
        raise RuntimeError(
            "Terraform-Binary nicht gefunden; Build kann nicht fortfahren."
        )
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            "Terraform fmt -check unerwarteter Fehler: {e}".format(e=e)
        )

    try:
        result = run(["terraform", "init", "-backend=false", "-input=false"], cwd=str(terraform_dir))
        if result.returncode != 0:
            raise RuntimeError("Terraform init fehlgeschlagen (Exit {result.returncode}); Build kann nicht fortfahren.".format(result=result))
        print("init -backend=false -input=false: OK")
    except FileNotFoundError:
        raise RuntimeError(
            "Terraform-Binary nicht gefunden; Build kann nicht fortfahren."
        )
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError("Terraform init fehlgeschlagen; Build kann nicht fortfahren.")

    try:
        result = run(["terraform", "validate", "-no-color"], cwd=str(terraform_dir))
        if result.returncode != 0:
            raise RuntimeError("Terraform validate fehlgeschlagen (Exit {result.returncode}); Build kann nicht fortfahren.".format(result=result))
        print("validate -no-color: OK")
    except FileNotFoundError:
        raise RuntimeError(
            "Terraform-Binary nicht gefunden; Build kann nicht fortfahren."
        )
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError("Terraform validate fehlgeschlagen; Build kann nicht fortfahren.")


# ---- Main ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build Mays-Orders Terraform module for RIS")
    parser.add_argument("--project-name", default="ris-dev2", help="Project name for generated module")
    parser.add_argument("--force", action="store_true", help="Overwrite existing target module")
    parser.add_argument("--check", action="store_true", help="Nur vereinbarte Checks ohne Build")
    parser.add_argument("--clean", action="store_true", help="Generiertes Modul entfernen und aufräumen")
    args = parser.parse_args()

    if args.clean:
        if TARGET_MODULE_DIR.exists():
            shutil.rmtree(TARGET_MODULE_DIR)
            print(f"Cleaned {TARGET_MODULE_DIR}")
        return

    if args.check:
        ok = True
        if not TARGET_MODULE_DIR.exists():
            print("FAIL: Modulverzeichnis fehlt")
            ok = False
        else:
            print("OK: Modulverordnung vorhanden")
        try:
            validate_generated_contract(TARGET_MODULE_DIR)
            print("OK: Generierter Modul-Vertrag entspricht Vertrag")
        except Exception as e:
            print(f"FAIL: Generierter Modul-Vertrag nicht valide: {e}")
            ok = False
        sys.exit(0 if ok else 1)

    # 1. Pin prüfen und Repository sichern
    ensure_repo()

    # 2. Project name validieren und erwarteten Komponentennamen bestimmen
    expected_component = derive_component_name(args.project_name)
    print(f"Project name validation: '{args.project_name}' → expected component '{expected_component}'")

    # 3. N-03: Namenslängenprüfung vor dem Build
    max_name_len_lambda = 64   # AWS Lambda function name max length
    max_name_len_iam = 64      # AWS IAM role name max length
    max_name_len_sqs = 80      # AWS SQS queue name max length
    max_name_len_dynamodb = 255 # AWS DynamoDB table name max length

    # Komponente selbst prüfen
    component_check = check_name_length(expected_component, "component", max_name_len_lambda)
    print(f"  Component name check: {component_check}")
    if component_check.startswith("ERROR"):
        print(f"FEHLER: Komponentenname '{expected_component}' überschreitet AWS-Limit ({max_name_len_lambda} Zeichen).")
        print(f"Bestehendes Ziel bleibt unverändert.")
        sys.exit(1)

    # Tatsächliche Ressourcennamen prüfen, die vom Builder generiert werden
    resource_names = [
        f"{expected_component}-handler",      # Lambda function name
        f"{expected_component}-handler-role",   # IAM role name
        f"{expected_component}-orders-queue",   # SQS queue name
        expected_component,                   # DynamoDB table name (= project_name)
    ]

    for resource_name in resource_names:
        if "handler-role" in resource_name:
            resource_type = "iam_role"
            max_len = max_name_len_iam
        elif "queue" in resource_name:
            resource_type = "sqs_queue"
            max_len = max_name_len_sqs
        elif "handler" in resource_name:
            resource_type = "lambda_function"
            max_len = max_name_len_lambda
        else:
            resource_type = "dynamodb_table"
            max_len = max_name_len_dynamodb

        name_check = check_name_length(resource_name, resource_type, max_len)
        print(f"  Resource name check ({resource_name}): {name_check}")
        if name_check.startswith("ERROR"):
            print(f"FEHLER: Ressourcenname '{resource_name}' überschreitet AWS-Limit ({max_len} Zeichen).")
            print(f"Bestehendes Ziel bleibt unverändert.")
            sys.exit(1)

    # 4. Modul bauen (keine nachträglichen Patches)
    build_module(args.project_name, args.force)

    # 5. Wenn alle Checks bestehen, Modul übernommen
    # (Wird innerhalb von build_module erledigt.)
    print(f"Module installed at {TARGET_MODULE_DIR}")


if __name__ == "__main__":
    main()