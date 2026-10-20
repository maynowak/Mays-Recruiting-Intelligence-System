#!/usr/bin/env python3
"""
Wrapper: Build Mays-Orders Terraform module for RIS integration.

- Checks out mays-order-aws into installer/projects/mays_orders (pinned commit)
- Runs module_builder from that checkout to generate orders-service preset
- Installs generated module into terraform/modules/mays-order
- Performs clean post-run: terraform fmt -check / validate

Usage:
  python -m installer.build_mays_orders_module --project-name mays-ris --force

Requires: git, Python 3.14+, module_builder from mays-order-aws
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

RIS_ROOT = Path(__file__).resolve().parent.parent
INSTALLER_PROJECTS = RIS_ROOT / "installer" / "projects"
MAYS_ORDERS_BUILDER_DIR = INSTALLER_PROJECTS / "mays_order_builder"
TARGET_MODULE_DIR = RIS_ROOT / "terraform" / "modules" / "mays_orders"
PIN_FILE = RIS_ROOT / "installer" / "mays-orders-clone.pinned.json"

def run(cmd, cwd=None):
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    result.check_returncode()
    return result

def ensure_repo():
    INSTALLER_PROJECTS.mkdir(parents=True, exist_ok=True)
    if not MAYS_ORDERS_BUILDER_DIR.exists():
        print(f"Cloning mays-order-aws into {MAYS_ORDERS_BUILDER_DIR}")
        run(["git", "clone", "https://github.com/maynowak/mays-order-aws.git", str(MAYS_ORDERS_BUILDER_DIR)])
    else:
        run(["git", "-C", str(MAYS_ORDERS_BUILDER_DIR), "fetch", "--quiet"])
    
    # Ensure we are on main branch for module_builder availability
    # Pinned commit is for installer integration; module_builder requires newer main
    print("Checking out main branch for module_builder")
    run(["git", "-C", str(MAYS_ORDERS_BUILDER_DIR), "checkout", "main"])
    # ensure clean
    status = subprocess.run(["git", "-C", str(MAYS_ORDERS_BUILDER_DIR), "status", "--porcelain"], capture_output=True, text=True)
    if status.stdout.strip():
        print("Warning: mays_order_builder worktree not clean", file=sys.stderr)

def build_module(project_name, force):
    TARGET_MODULE_DIR.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "module_builder", "build",
        "--preset", "orders-service",
        "--target", str(TARGET_MODULE_DIR),
        "--project-name", project_name,
        "--validate"
    ]
    if force:
        cmd.append("--force")
    print(f"Building module via module_builder from {MAYS_ORDERS_BUILDER_DIR}")
    run(cmd, cwd=str(MAYS_ORDERS_BUILDER_DIR))
    
    # post-run sanity
    if TARGET_MODULE_DIR.exists():
        print("Module built successfully")
    else:
        raise RuntimeError("Target module directory not created")
    
    # Patch outputs for RIS wiring: ensure sqs_queue_name output exists
    outputs_file = TARGET_MODULE_DIR / "outputs.tf"
    if outputs_file.exists():
        content = outputs_file.read_text()
        if 'output "sqs_queue_name"' not in content:
            patch = '''
output "sqs_queue_name" {
  description = "Name der Orders-SQS-Queue."
  value       = module.sqs.queue_name
}
'''
            # Insert before sqs_worker_lambda_arn
            if 'output "sqs_worker_lambda_arn"' in content:
                content = content.replace('output "sqs_worker_lambda_arn"', patch + '\noutput "sqs_worker_lambda_arn"')
                outputs_file.write_text(content)
                print("Patched outputs.tf with sqs_queue_name")
            else:
                outputs_file.write_text(content + patch)
                print("Appended sqs_queue_name to outputs.tf")
        else:
            print("sqs_queue_name output already present")
    
    # Patch RIS terraform main.tf to use component name semantics
    # project_name for mays_orders module must be "${var.project_name}-mays-orders"
    main_tf = RIS_ROOT / "terraform" / "main.tf"
    if main_tf.exists():
        tf_content = main_tf.read_text()
        # Replace project_name = var.project_name within module "mays_orders" block
        # Simple heuristic: find module block and replace first project_name line
        import re
        pattern = r'(module "mays_orders" \{[^}]*?project_name\s*=\s*)var\.project_name(\s*)'
        replacement = r'\1"${var.project_name}-mays-orders"\2'
        new_tf_content, count = re.subn(pattern, replacement, tf_content, flags=re.DOTALL)
        if count > 0:
            main_tf.write_text(new_tf_content)
            print("Patched terraform/main.tf: mays_orders project_name uses component naming")
        else:
            print("Warning: could not patch main.tf for mays_orders project_name")

def post_run_checks():
    terraform_dir = RIS_ROOT / "terraform"
    print("Running post-run Terraform checks...")
    # fmt check
    run(["terraform", "fmt", "-check", "-recursive"], cwd=str(terraform_dir))
    # validate
    run(["terraform", "init", "-backend=false"], cwd=str(terraform_dir))
    run(["terraform", "validate"], cwd=str(terraform_dir))
    print("Post-run checks passed")

def main():
    parser = argparse.ArgumentParser(description="Build Mays-Orders Terraform module for RIS")
    parser.add_argument("--project-name", default="mays-ris", help="Project name for generated module")
    parser.add_argument("--force", action="store_true", help="Overwrite existing target")
    parser.add_argument("--check", action="store_true", help="Nur prüfen ob Wrapper-Routinen erledigt sind, ohne zu bauen")
    parser.add_argument("--clean", action="store_true", help="Generiertes Modul entfernen und aufzuräumen")
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
            print("OK: Modulverzeichnis vorhanden")
        outputs_file = TARGET_MODULE_DIR / "outputs.tf"
        if outputs_file.exists() and 'output "sqs_queue_name"' in outputs_file.read_text():
            print("OK: sqs_queue_name Output vorhanden")
        else:
            print("FAIL: sqs_queue_name Output fehlt")
            ok = False
        main_tf = RIS_ROOT / "terraform" / "main.tf"
        if main_tf.exists() and '${var.project_name}-mays-orders' in main_tf.read_text():
            print("OK: main.tf Component-Naming vorhanden")
        else:
            print("FAIL: main.tf Component-Naming fehlt")
            ok = False
        # simple terraform validate check
        try:
            run(["terraform", "validate"], cwd=str(RIS_ROOT / "terraform"))
            print("OK: terraform validate PASS")
        except Exception as e:
            print(f"FAIL: terraform validate {e}")
            ok = False
        sys.exit(0 if ok else 1)
    
    ensure_repo()
    build_module(args.project_name, args.force)
    post_run_checks()
    print(f"Module installed at {TARGET_MODULE_DIR}")

if __name__ == "__main__":
    main()
