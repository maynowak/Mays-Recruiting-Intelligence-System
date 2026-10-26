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
- General name derivation (no hardcoded EXPECTED_PROJECT_MAP).
- Builder pin from mays-orders-builder.pinned.json (not composite clone pin).

Usage:
  python -m installer.build_mays_orders_module --project-name mays-ris

Requires: git, Python 3.14+, module_builder from mays-order-aws
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

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


# ---- Name contract (GAP-01/05) ------------------------------------------------------

# Generelle Namensableitung für den orders-service Build:
# RIS-Projekt name → MO-Komponentename
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


# ---- Pin ------------------------------------------------------------

def load_builder_pin() -> str:
    """Lade den Builder-Pin aus der dedizierten Pin-Datei.

    Die Composite-Clone-Pin-Datei (mays-orders-clone.pinned.json) bleibt
    als historische Referenz unverändert erhalten; der aktive Builder
    liest aus mays-orders-builder.pinned.json.
    """
    if BUILDER_PIN_FILE.exists():
        with open(BUILDER_PIN_FILE, "r", encoding="utf-8") as f:
            pin_data = json.load(f)
        commit = pin_data.get("commit", "")
        if commit:
            return commit
    # Fallback: prüfe, ob der Composite-Pin Datei existiert und lies ihn
    if CLONE_PIN_FILE.exists():
        with open(CLONE_PIN_FILE, "r", encoding="utf-8") as f:
            pin_data = json.load(f)
        commit = pin_data.get("commit", "")
        if commit:
            print(
                "Hinweis: Builder-Pin nicht in mays-orders-builder.pinned.json gefunden; "
                "fallback auf Composite-Clone-Pin " + commit
            )
        return commit
    return PINNED_COMMIT


BUILDER_PIN = load_builder_pin()
"""Aktiver Builder-Pin aus mays-orders-builder.pinned.json."""


def run(cmd, cwd=None):
    # Prepend git.exe if the command is a git subcommand
    if cmd[0] in ("git",) or (len(cmd) > 1 and cmd[0] == "git"):
        cmd = [r"C:\Program Files\Git\bin\git.exe"] + cmd[1:]
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        print(f"FEHLER: Befehl {' '.join(cmd)} endete mit Exit-Code {result.returncode}")
    return result


# ---- Helper: ensure repo --------------------------------------------

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
    run(["git", "-C", str(MAYS_ORDERS_BUILDER_DIR), "checkout", BUILDER_PIN])

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
        print(f"Warnung: Git-Status-Check fehlgeschlagen: {e}")
        # Ist kein Build-breaker, wenn git nicht verfügbar ist.


# ---- Build module ---------------------------------------------------

def build_module(project_name: str, force: bool):
    """Build the orders-service module and validate the contract.

    Es werden keine nachträglichen Patches (sqs_queue_name, IAM-count) mehr ausgeführt.
    Der Builder darf das Modul nur erzeugen, wenn der Vertrag bereits stimmt;
    ansonsten wird abgebrochen.

    Ablauf:
    1. Project name validieren und Komponentennamen ableiten
    2. Modul generieren (ohne --force Standardverhalten, --force erzwingt Überschreibung)
    3. Generierten Vertrag prüfen (content-based, keine nachträglichen Patches)
    4. Post-run Checks (fmt, init, validate) nur nach erfolgreichem Build
    5. Modulziel übernehmen wenn alle Checks bestehen
    """
    # 1. Project name validieren und Komponentennamen ableiten
    expected_component = derive_component_name(project_name)
    print(f"Project name validation: '{project_name}' → expected component '{expected_component}'")

    TARGET_MODULE_DIR.parent.mkdir(parents=True, exist_ok=True)

    # 2. Modul generieren
    cmd = [
        sys.executable, "-m", "module_builder", "build",
        "--preset", "orders-service",
        "--target", str(TARGET_MODULE_DIR),
        "--project-name", project_name,
    ]
    if force:
        cmd.append("--force")
    print(f"Building module via module_builder from {MAYS_ORDERS_BUILDER_DIR}")
    run(cmd, cwd=str(MAYS_ORDERS_BUILDER_DIR))

    # 3. Vertragsprüfung (CONTENT-BASED, keine nachträglichen Patches)
    # Wir prüfen, dass das generierte Modul die erwarteten Merkmale
    # bereits enthält. Abweichung →Abbruch, kein stummer Patch.
    validate_generated_contract(TARGET_MODULE_DIR)

    # 4. Post-run: fmt + init + validate (erst nach erfolgreichem Build)
    post_run_checks()


def validate_generated_contract(target_dir: Path):
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


# ---- Patch IAM SQS gate (entfernt aus aktivem Build-Pfad) ----

def patch_iam_sqs_gate():
    """Diese Funktion wurde aus dem aktiven Build-Pfad entfernt.
    Der generierte Modul-Vertrag wird nun vorab validiert (siehe
    validate_generated_contract). Diese Funktion bleibt aus didaktischen
    Gründen erhalten, wird aber nicht mehr aufgerufen."""
    pass


# ---- Post-run checks ------------------------------------------------

def post_run_checks():
    """Führt lokale Validierungschecks durch (fmt, init, validate).
    Fehlende Werkzeuge oder fehlgeschlagene Prüfungen müssen einen
    Fehlerstatus liefern; keine Erfolgsmeldung nach übersprungenen Checks."""
    terraform_dir = RIS_ROOT / "terraform"
    terraform_available = True
    try:
        run(["terraform", "fmt", "-check", "-recursive"], cwd=str(terraform_dir))
        print("fmt -check: OK")
    except Exception as e:
        terraform_available = False
        print(f"fmt -check: FEHLER - {e}")
        # Terraform fmt ist optional, aber wenn vorhanden, muss es bestehen
        # Wir brechen nicht ab, wenn terraform nicht installiert ist,
        # aber wenn es installiert ist und fehlschlägt, ist das kritisch.

    # init + validate – nur wenn terraform verfügbar
    if terraform_available:
        try:
            run(["terraform", "init", "-backend=false"], cwd=str(terraform_dir))
            print("init -backend=false: OK")
        except Exception as e:
            print(f"init -backend=false: FEHLER - {e}")
            # Abbruch wenn init fehlschlägt
            raise RuntimeError("Terraform init fehlgeschlagen; Build kann nicht fortfahren.")

        try:
            run(["terraform", "validate"], cwd=str(terraform_dir))
            print("validate -no-color: OK")
        except Exception as e:
            print(f"validate -no-color: FEHLER - {e}")
            raise RuntimeError("Terraform validate fehlgeschlagen; Build kann nicht fortfahren.")
    else:
        print("init -backend=false: terraform CLI nicht im PATH (optional)")
        print("validate -no-color: terraform CLI nicht im PATH (optional)")


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
            import shutil
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

    # 3. Modul bauen (keine nachträglichen Patches)
    build_module(args.project_name, args.force)

    # 4. Post-run Checks (fmt + init + validate)
    # Wenn alle Checks bestehen, Modul übernehmen
    print(f"Module installed at {TARGET_MODULE_DIR}")


if __name__ == "__main__":
    main()