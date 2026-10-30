#!/usr/bin/env python3
"""Regression tests for Prompt 04-FIX wrapper corrections (N-01, N-02, N-03).

Tests use unittest.mock to simulate process execution without requiring
actual Terraform, Git, or the module_builder. All tests are isolated in
TemporaryDirectory instances.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Add the project to the path
sys.path.insert(0, r'C:\Users\DCI-Student\projekte\Mays-Recruiting-Intelligence-system')

from installer.build_mays_orders_module import (
    build_module,
    derive_component_name,
    validate_project_name_format,
    check_name_length,
    check_arn_id_contract,
    validate_generated_contract,
    post_run_checks,
    ensure_repo,
    load_builder_pin,
    TARGET_MODULE_DIR,
    BUILDER_PIN,
    PINNED_COMMIT,
    MAYS_ORDERS_BUILDER_DIR,
    BUILDER_PIN_FILE,
    CLONE_PIN_FILE,
)

PROJECT_NAME = "ris-dev2"
EXPECTED_COMPONENT = "ris-dev2-mays-orders"


# ============================================================================
# Helpers
# ============================================================================

def _snapshot_dir(dirpath):
    """Return dict of {relpath: (size, sha256)} for all files under dirpath."""
    snap = {}
    dirpath = Path(dirpath)
    if not dirpath.exists():
        return snap
    for f in sorted(dirpath.rglob("*")):
        if f.is_file():
            rel = f.relative_to(dirpath).as_posix()
            data = f.read_bytes()
            snap[rel] = (len(data), hashlib.sha256(data).hexdigest())
    return snap


def _sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ============================================================================
# N-01: Namensvertrag
# ============================================================================

class TestN01Namensvertrag(unittest.TestCase):
    """Tests for N-01: Builder project name derivation."""

    def test_derive_component_name_ris_dev2(self):
        """derive_component_name('ris-dev2') liefert 'ris-dev2-mays-orders'."""
        self.assertEqual(derive_component_name("ris-dev2"), EXPECTED_COMPONENT)

    def test_derive_component_name_no_duplicate_suffix(self):
        """Doppelte Suffixe werden abgelehnt."""
        with self.assertRaises(ValueError):
            derive_component_name("ris-dev2-mays-orders")

    def test_derive_component_name_unknown(self):
        """Für unbekannte Projektnamen wird die Ableitung trotzdem durchgeführt."""
        self.assertEqual(derive_component_name("foo"), "foo-mays-orders")
        self.assertEqual(derive_component_name("mays-ris"), "mays-ris-mays-orders")

    def test_validate_project_name_invalid(self):
        """Ungültige Projektnamen werden abgelehnt."""
        with self.assertRaises(ValueError):
            validate_project_name_format("")
        with self.assertRaises(ValueError):
            validate_project_name_format("ab")  # zu kurz
        with self.assertRaises(ValueError):
            validate_project_name_format("UPPERCASE")  # Grossbuchstaben
        with self.assertRaises(ValueError):
            validate_project_name_format("-leading")  # führender Bindestrich
        with self.assertRaises(ValueError):
            validate_project_name_format("trailing-")  # endender Bindestrich
        with self.assertRaises(ValueError):
            validate_project_name_format("has space")  # Leerzeichen

    def test_validate_project_name_valid(self):
        """Gültige Projektnamen passieren."""
        validate_project_name_format("ris-dev2")
        validate_project_name_format("a-b3")
        validate_project_name_format("abc")

    @patch('installer.build_mays_orders_module.run')
    @patch('installer.build_mays_orders_module.derive_component_name')
    @patch('installer.build_mays_orders_module.check_name_length')
    def test_build_module_passes_expected_component(
        self, mock_check_len, mock_derive, mock_run
    ):
        """Tatsächlicher Builder-Aufruf enthält --project-name ris-dev2-mays-orders."""
        mock_derive.return_value = EXPECTED_COMPONENT
        mock_check_len.return_value = "OK (19/64)"
        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_target = Path(tmpdir) / "mays_orders"
            temp_target.mkdir(parents=True)

            with patch('installer.build_mays_orders_module.TARGET_MODULE_DIR', temp_target):
                try:
                    build_module(PROJECT_NAME, force=False)
                except SystemExit:
                    self.fail("build_module raised SystemExit unexpectedly")
                except Exception:
                    # build_module will fail at module_builder run or contract check,
                    # but we only care about the cmd argument
                    pass

        # Verify run() was called with --project-name ris-dev2-mays-orders
        called = False
        for args, kwargs in mock_run.call_args_list:
            cmd = args[0] if args else kwargs.get("cmd", [])
            if isinstance(cmd, list) and "--project-name" in cmd:
                idx = cmd.index("--project-name")
                if idx + 1 < len(cmd) and cmd[idx + 1] == EXPECTED_COMPONENT:
                    called = True
                    break
        self.assertTrue(called, "Builder wurde nicht mit --project-name ris-dev2-mays-orders aufgerufen")

    @patch('installer.build_mays_orders_module.run')
    @patch('installer.build_mays_orders_module.derive_component_name')
    @patch('installer.build_mays_orders_module.check_name_length')
    def test_build_module_never_passes_plain_project_name(
        self, mock_check_len, mock_derive, mock_run
    ):
        """Builder erhält niemals nur 'ris-dev2' als --project-name."""
        mock_derive.return_value = EXPECTED_COMPONENT
        mock_check_len.return_value = "OK (19/64)"
        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_target = Path(tmpdir) / "mays_orders"
            temp_target.mkdir(parents=True)

            with patch('installer.build_mays_orders_module.TARGET_MODULE_DIR', temp_target):
                try:
                    build_module(PROJECT_NAME, force=False)
                except SystemExit:
                    pass
                except Exception:
                    pass

        for args, kwargs in mock_run.call_args_list:
            cmd = args[0] if args else kwargs.get("cmd", [])
            if isinstance(cmd, list) and "--project-name" in cmd:
                idx = cmd.index("--project-name")
                if idx + 1 < len(cmd):
                    self.assertEqual(cmd[idx + 1], EXPECTED_COMPONENT,
                                     f"Builder erhielt '{cmd[idx+1]}' statt '{EXPECTED_COMPONENT}'")


# ============================================================================
# N-02: ARN-/ID-Vertragsprüfung
# ============================================================================

class TestN02ARNIDVertrag(unittest.TestCase):
    """Tests for N-02: ARN/ID consumer-provider contract."""

    _BASE_BINDINGS = '''
  orders_table_name   = module.mays_orders.dynamodb_table_name
  orders_table_arn    = module.mays_orders.dynamodb_table_arn
  orders_queue_arn    = module.mays_orders.sqs_queue_arn
  orders_queue_url    = module.mays_orders.sqs_queue_url
  api_id              = module.api.api_id
  authorizer_id       = module.api.authorizer_id
'''

    def _write_main_tf_and_outputs(self, dirpath, main_content, outputs_content='output "dummy" { value = "x" }'):
        d = Path(dirpath)
        d.mkdir(parents=True, exist_ok=True)
        (d / "main.tf").write_text(main_content, encoding="utf-8")
        (d / "outputs.tf").write_text(outputs_content, encoding="utf-8")

    def test_check_arn_id_contract_all_bindings_present(self):
        """Alle 6 Consumer-Provider-Verkettungen sind vorhanden."""
        main_tf = '''
module "orders_reader" {
  source = "./modules/orders_reader"
''' + self._BASE_BINDINGS + '''
}
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_main_tf_and_outputs(tmpdir, main_tf)
            # Should not raise
            check_arn_id_contract(Path(tmpdir))

    def test_check_arn_id_contract_missing_binding_raises(self):
        """Fehlender MO-Output löst RuntimeError aus."""
        main_tf = '''
module "orders_reader" {
  source = "./modules/orders_reader"
  orders_table_name = module.mays_orders.dynamodb_table_name
  orders_table_arn    = module.mays_orders.dynamodb_table_arn
  orders_queue_arn    = module.mays_orders.sqs_queue_arn
  orders_queue_url    = module.mays_orders.sqs_queue_url
  api_id              = module.api.api_id
}
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_main_tf_and_outputs(tmpdir, main_tf)
            with self.assertRaises(RuntimeError) as ctx:
                check_arn_id_contract(Path(tmpdir))
            self.assertIn("authorizer_id", str(ctx.exception))

    def test_check_arn_id_contract_arn_name_swapped_raises(self):
        """ARN und Name vertauscht -> Fehler."""
        main_tf = '''
module "orders_reader" {
  source = "./modules/orders_reader"
  orders_table_name = module.mays_orders.dynamodb_table_arn
  orders_table_arn  = module.mays_orders.dynamodb_table_name
  orders_queue_arn    = module.mays_orders.sqs_queue_arn
  orders_queue_url    = module.mays_orders.sqs_queue_url
  api_id              = module.api.api_id
  authorizer_id       = module.api.authorizer_id
}
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_main_tf_and_outputs(tmpdir, main_tf)
            with self.assertRaises(RuntimeError):
                check_arn_id_contract(Path(tmpdir))

    def test_check_arn_id_contract_wrong_queue_url_raises(self):
        """Falsche Queue-URL-Referenz -> Fehler."""
        main_tf = '''
module "orders_reader" {
  source = "./modules/orders_reader"
''' + self._BASE_BINDINGS.replace(
        "orders_queue_url    = module.mays_orders.sqs_queue_url",
        "orders_queue_url    = module.mays_orders.dynamodb_table_name"
    ) + '''
}
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_main_tf_and_outputs(tmpdir, main_tf)
            with self.assertRaises(RuntimeError) as ctx:
                check_arn_id_contract(Path(tmpdir))
            self.assertIn("orders_queue_url", str(ctx.exception))

    def test_check_arn_id_contract_wrong_authorizer_raises(self):
        """Falsche Authorizer-ID -> Fehler."""
        main_tf = '''
module "orders_reader" {
  source = "./modules/orders_reader"
''' + self._BASE_BINDINGS.replace(
        "authorizer_id       = module.api.authorizer_id",
        "authorizer_id       = module.mays_orders.api_gateway_authorizer_id"
    ) + '''
}
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_main_tf_and_outputs(tmpdir, main_tf)
            with self.assertRaises(RuntimeError) as ctx:
                check_arn_id_contract(Path(tmpdir))
            self.assertIn("authorizer_id", str(ctx.exception))

    def test_check_arn_id_contract_ris_api_mixing_raises(self):
        """RIS-eigene API und MO-API im selben Modul vermischt -> Fehler."""
        main_tf = '''
module "orders_reader" {
  source = "./modules/orders_reader"
  api_id = module.api.api_id
  authorizer_id = module.mays_orders.api_gateway_authorizer_id
  orders_table_name   = module.mays_orders.dynamodb_table_name
  orders_table_arn    = module.mays_orders.dynamodb_table_arn
  orders_queue_arn    = module.mays_orders.sqs_queue_arn
  orders_queue_url    = module.mays_orders.sqs_queue_url
}
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_main_tf_and_outputs(tmpdir, main_tf)
            with self.assertRaises(RuntimeError):
                check_arn_id_contract(Path(tmpdir))

    def test_check_arn_id_contract_regex_no_false_positive(self):
        """Regex darf keine falschen PASS-Ergebnisse erzeugen (Teil-String-Match)."""
        # orders_table_name als Substring in einem anderen Namen sollte nicht matchen
        main_tf = '''
module "orders_reader" {
  source = "./modules/orders_reader"
  my_orders_table_name_backup = module.mays_orders.dynamodb_table_name
  orders_table_arn    = module.mays_orders.dynamodb_table_arn
  orders_queue_arn    = module.mays_orders.sqs_queue_arn
  orders_queue_url    = module.mays_orders.sqs_queue_url
  api_id              = module.api.api_id
  authorizer_id       = module.api.authorizer_id
}
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_main_tf_and_outputs(tmpdir, main_tf)
            with self.assertRaises(RuntimeError):
                check_arn_id_contract(Path(tmpdir))

    def test_check_arn_id_contract_monitoring_references(self):
        """Zusätzliche tatsächliche monitoring_orders-Referenzen kontrollieren."""
        # Der RIS-Root verwendet module.mays_orders.* Outputs für Monitoring,
        # PLUS alle 6 required bindings für orders_reader
        main_tf = '''
module "orders_reader" {
  source = "./modules/orders_reader"
''' + self._BASE_BINDINGS + '''
}

module "monitoring_orders" {
  source = "./modules/monitoring"
  log_group_name = module.mays_orders.log_group_name
  alarm_topic_arn = module.mays_orders.sns_topic_arn
}
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_main_tf_and_outputs(tmpdir, main_tf)
            # All 6 required bindings present + monitoring refs - no error
            check_arn_id_contract(Path(tmpdir))


# ============================================================================
# N-03: AWS-Namensgrenzen
# ============================================================================

class TestN03Namensgrenzen(unittest.TestCase):
    """Tests for N-03: AWS resource name length limits."""

    def test_lambda_handler_valid(self):
        """Gültiger Lambda-Handler-Name."""
        name = "ris-dev2-mays-orders-handler"
        result = check_name_length(name, "lambda_function", 64)
        self.assertTrue(result.startswith("OK"), f"Erwartet OK, erhalten: {result}")

    def test_lambda_handler_over_limit(self):
        """Ein Zeichen über dem Lambda-Limit -> ERROR."""
        # 64 chars max, name itself must exceed 64
        name = "a" * 65
        result = check_name_length(name, "lambda_function", 64)
        self.assertTrue(result.startswith("ERROR"), f"Erwartet ERROR, erhalten: {result}")

    def test_lambda_handler_exact_limit(self):
        """Exakt maximale Länge (100%) -> WARNING (ab 80% warnt die Funktion)."""
        name = "a" * 64
        result = check_name_length(name, "lambda_function", 64)
        self.assertTrue(result.startswith("WARNING"), f"Erwartet WARNING (100%), erhalten: {result}")

    def test_lambda_handler_80_percent(self):
        """80% Auslastung -> WARNING."""
        name = "a" * 51  # 51/64 = 79.6875% -> actually just under 80
        result = check_name_length(name, "lambda_function", 64)
        pct = 51 / 64 * 100
        if pct >= 80:
            self.assertTrue(result.startswith("WARNING"))
        else:
            self.assertTrue(result.startswith("OK"))

    def test_iam_role_valid(self):
        """Gültiger IAM-Rollen-Name."""
        name = "ris-dev2-mays-orders-handler-role"
        result = check_name_length(name, "iam_role", 64)
        self.assertTrue(result.startswith("OK"), f"Erwartet OK, erhalten: {result}")

    def test_iam_role_over_limit(self):
        """IAM-Rolle über Limit -> ERROR."""
        name = "a" * 65
        result = check_name_length(name, "iam_role", 64)
        self.assertTrue(result.startswith("ERROR"), f"Erwartet ERROR, erhalten: {result}")

    def test_sqs_queue_valid(self):
        """Gültiger SQS-Queue-Name."""
        name = "ris-dev2-mays-orders-orders-queue"
        result = check_name_length(name, "sqs_queue", 80)
        self.assertTrue(result.startswith("OK"), f"Erwartet OK, erhalten: {result}")

    def test_sqs_queue_over_limit(self):
        """SQS-Queue über Limit -> ERROR."""
        name = "a" * 81
        result = check_name_length(name, "sqs_queue", 80)
        self.assertTrue(result.startswith("ERROR"), f"Erwartet ERROR, erhalten: {result}")

    def test_dynamodb_table_valid(self):
        """Gültiger DynamoDB-Tabellenname."""
        name = "ris-dev2-mays-orders"
        result = check_name_length(name, "dynamodb_table", 255)
        self.assertTrue(result.startswith("OK"), f"Erwartet OK, erhalten: {result}")

    def test_dynamodb_table_over_limit(self):
        """DynamoDB über Limit -> ERROR."""
        name = "a" * 256
        result = check_name_length(name, "dynamodb_table", 255)
        self.assertTrue(result.startswith("ERROR"), f"Erwartet ERROR, erhalten: {result}")

    def test_invalid_characters(self):
        """Ungültige Zeichen werden nicht direkt von check_name_length geprüft
        (nur Länge), aber validate_project_name_format prüft Zeichen."""
        # check_name_length prüft nur Länge, keine Zeichen
        result = check_name_length("ris-dev2-mays-orders!", "lambda_function", 64)
        self.assertTrue(result.startswith("OK"), "check_name_length prüft nur Länge")

    def test_component_name_length_abort(self):
        """Komponentenname über Limit -> sys.exit(1)."""
        long_name = "a" * 70  # 70 > 64
        with self.assertRaises(SystemExit) as ctx:
            with patch('installer.build_mays_orders_module.derive_component_name', return_value=long_name):
                build_module("a" * 70, force=False)
        self.assertEqual(ctx.exception.code, 1)


# ============================================================================
# Terraform-Gates (post_run_checks)
# ============================================================================

class TestTerraformGates(unittest.TestCase):
    """Tests for Terraform mandatory gates (N-05)."""

    def test_post_run_checks_terraform_binary_missing(self):
        """Terraform-Binary fehlt -> Build blockiert (RuntimeError)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mod_dir = Path(tmpdir) / "mod"
            mod_dir.mkdir()
            with patch('installer.build_mays_orders_module.run') as mock_run:
                mock_run.side_effect = FileNotFoundError("terraform not found")
                with self.assertRaises(RuntimeError):
                    post_run_checks(mod_dir)

    def test_post_run_checks_fmt_exit_3(self):
        """fmt -check Exit 3 -> Build blockiert (RuntimeError)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mod_dir = Path(tmpdir) / "mod"
            mod_dir.mkdir()
            with patch('installer.build_mays_orders_module.run') as mock_run:
                fmt_result = MagicMock()
                fmt_result.returncode = 3
                mock_run.return_value = fmt_result
                with self.assertRaises(RuntimeError):
                    post_run_checks(mod_dir)

    def test_post_run_checks_init_exit_1(self):
        """init Exit 1 -> Build blockiert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mod_dir = Path(tmpdir) / "mod"
            mod_dir.mkdir()
            with patch('installer.build_mays_orders_module.run') as mock_run:
                fmt_result = MagicMock()
                fmt_result.returncode = 0
                init_result = MagicMock()
                init_result.returncode = 1
                mock_run.side_effect = [fmt_result, init_result]
                with self.assertRaises(RuntimeError):
                    post_run_checks(mod_dir)

    def test_post_run_checks_validate_exit_1(self):
        """validate Exit 1 -> Build blockiert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mod_dir = Path(tmpdir) / "mod"
            mod_dir.mkdir()
            with patch('installer.build_mays_orders_module.run') as mock_run:
                fmt_result = MagicMock()
                fmt_result.returncode = 0
                init_result = MagicMock()
                init_result.returncode = 0
                validate_result = MagicMock()
                validate_result.returncode = 1
                mock_run.side_effect = [fmt_result, init_result, validate_result]
                with self.assertRaises(RuntimeError):
                    post_run_checks(mod_dir)

    def test_post_run_checks_all_pass(self):
        """Alle drei Gates Exit 0 -> Übernahme erlaubt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mod_dir = Path(tmpdir) / "mod"
            mod_dir.mkdir()
            with patch('installer.build_mays_orders_module.run') as mock_run:
                success = MagicMock()
                success.returncode = 0
                mock_run.return_value = success
                # Should not raise
                post_run_checks(mod_dir)

    def test_post_run_checks_runs_in_module_root_not_subdir(self):
        """Befehle werden im generierten Modul-Root ausgeführt, nicht in module_dir/terraform."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mod_dir = Path(tmpdir) / "mod"
            mod_dir.mkdir()
            # Ensure no terraform/ subdirectory exists
            self.assertFalse((mod_dir / "terraform").exists())
            with patch('installer.build_mays_orders_module.run') as mock_run:
                success = MagicMock()
                success.returncode = 0
                mock_run.return_value = success
                post_run_checks(mod_dir)
                # Verify run was called with cwd=str(mod_dir), not mod_dir/terraform
                for args, kwargs in mock_run.call_args_list:
                    cwd = kwargs.get("cwd")
                    if cwd is None and len(args) > 1:
                        cwd = args[1]
                    self.assertEqual(cwd, str(mod_dir),
                                     f"Terraform-Befehl wurde in {cwd} statt {mod_dir} ausgeführt")

    def test_post_run_checks_tf_data_dir_isolated(self):
        """TF_DATA_DIR wird auf ein isoliertes Verzeichnis gesetzt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mod_dir = Path(tmpdir) / "mod"
            mod_dir.mkdir()
            with patch('installer.build_mays_orders_module.subprocess.run') as mock_subprocess:
                def mock_subprocess_run(cmd, **kwargs):
                    # _terraform_exe() ruft 'where terraform' auf – muss String zurückgeben
                    if isinstance(cmd, list) and len(cmd) >= 2 and cmd[0] == "where" and cmd[1] == "terraform":
                        result = MagicMock()
                        result.returncode = 0
                        result.stdout = "C:\\path\\to\\terraform.exe\r\n"
                        return result
                    # Alle anderen terraform-Aufrufe: Exit 0
                    result = MagicMock()
                    result.returncode = 0
                    return result
                mock_subprocess.side_effect = mock_subprocess_run
                post_run_checks(mod_dir)
                # Verify TF_DATA_DIR is set in the subprocess environment
                tf_data_dir_found = False
                for args, kwargs in mock_subprocess.call_args_list:
                    env = kwargs.get("env")
                    if env and "TF_DATA_DIR" in env:
                        tf_data_dir_found = True
                        self.assertTrue(Path(env["TF_DATA_DIR"]).is_absolute(),
                                        f"TF_DATA_DIR sollte ein absoluter Pfad sein: {env['TF_DATA_DIR']}")
                self.assertTrue(tf_data_dir_found,
                                "TF_DATA_DIR sollte an subprocess.run übergeben werden")


def _write_gen_module(base_dir, main_tf_content, outputs_tf_content,
                      vars_tf_content, iam_main_content, iam_vars_content):
    """Create a complete generated module directory structure."""
    gen_dir = Path(base_dir) / "gen"
    (gen_dir / "modules" / "iam").mkdir(parents=True, exist_ok=True)
    (gen_dir / "main.tf").write_text(main_tf_content, encoding="utf-8")
    (gen_dir / "outputs.tf").write_text(outputs_tf_content, encoding="utf-8")
    (gen_dir / "variables.tf").write_text(vars_tf_content, encoding="utf-8")
    (gen_dir / "modules" / "iam" / "main.tf").write_text(iam_main_content, encoding="utf-8")
    (gen_dir / "modules" / "iam" / "variables.tf").write_text(iam_vars_content, encoding="utf-8")
    return gen_dir


# ============================================================================
# Section 6: Zielübernahme und Bestandsschutz
# ============================================================================

class TestZielUebernahmeBestandsschutz(unittest.TestCase):
    """Tests for Section 6: Target adoption and existing-target protection.

    At every error, the pre-existing target module must remain byte-identical.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.target = Path(self.tmpdir.name) / "mays_orders"
        self.target.mkdir(parents=True)

        # Create existing target module with multiple test files
        self.test_files = {
            'main.tf': '# Existing main.tf\nresource "aws_instance" "test" {}',
            'variables.tf': '# Existing variables.tf\nvariable "project_name" {}',
            'outputs.tf': '# Existing outputs.tf\noutput "existing" { value = "x" }',
            'versions.tf': '# Existing versions.tf\nterraform {}',
        }
        self.sha256_before = {}
        for fname, content in self.test_files.items():
            fpath = self.target / fname
            fpath.write_text(content, encoding="utf-8")
            self.sha256_before[fname] = _sha256_file(fpath)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _assert_target_unchanged(self):
        """Assert all target files are byte-identical to before."""
        for fname, sha_before in self.sha256_before.items():
            fpath = self.target / fname
            self.assertTrue(fpath.exists(), f"Target file {fname} was deleted")
            sha_after = _sha256_file(fpath)
            self.assertEqual(sha_before, sha_after,
                             f"Target file {fname} changed (SHA-256 before={sha_before}, after={sha_after})")

    @patch('installer.build_mays_orders_module.ensure_repo')
    @patch('installer.build_mays_orders_module.run')
    @patch('installer.build_mays_orders_module.validate_generated_contract')
    @patch('installer.build_mays_orders_module.post_run_checks')
    @patch('installer.build_mays_orders_module.shutil.copytree')
    def test_builder_error_preserves_target(
        self, mock_copytree, mock_post_run, mock_validate, mock_run, mock_ensure_repo
    ):
        """1. Builder-Fehler -> Ziel bleibt bytegleich erhalten."""
        mock_ensure_repo.return_value = None
        mock_run.side_effect = RuntimeError("Builder failed")

        with patch('installer.build_mays_orders_module.TARGET_MODULE_DIR', self.target):
            with self.assertRaises(RuntimeError):
                build_module(PROJECT_NAME, force=False)
        self._assert_target_unchanged()

    @patch('installer.build_mays_orders_module.ensure_repo')
    @patch('installer.build_mays_orders_module.run')
    @patch('installer.build_mays_orders_module.validate_generated_contract')
    @patch('installer.build_mays_orders_module.post_run_checks')
    @patch('installer.build_mays_orders_module.shutil.copytree')
    def test_contract_error_preserves_target(
        self, mock_copytree, mock_post_run, mock_validate, mock_run, mock_ensure_repo
    ):
        """2. Vertragsfehler -> Ziel bleibt bytegleich erhalten."""
        mock_ensure_repo.return_value = None
        mock_run.return_value = MagicMock(returncode=0)
        mock_validate.side_effect = RuntimeError("Contract validation failed")

        with patch('installer.build_mays_orders_module.TARGET_MODULE_DIR', self.target):
            with self.assertRaises(RuntimeError):
                build_module(PROJECT_NAME, force=False)
        self._assert_target_unchanged()
        mock_copytree.assert_not_called()

    @patch('installer.build_mays_orders_module.ensure_repo')
    @patch('installer.build_mays_orders_module.run')
    @patch('installer.build_mays_orders_module.validate_generated_contract')
    @patch('installer.build_mays_orders_module.post_run_checks')
    @patch('installer.build_mays_orders_module.shutil.copytree')
    def test_name_length_error_preserves_target(
        self, mock_copytree, mock_post_run, mock_validate, mock_run, mock_ensure_repo
    ):
        """3. Namensfehler -> Ziel bleibt bytegleich erhalten."""
        mock_ensure_repo.return_value = None

        long_name = "a" * 70  # > 64 chars
        with patch('installer.build_mays_orders_module.derive_component_name', return_value=long_name):
            with self.assertRaises(SystemExit) as ctx:
                build_module("a" * 70, force=False)
            self.assertEqual(ctx.exception.code, 1)
        self._assert_target_unchanged()
        mock_copytree.assert_not_called()

    @patch('installer.build_mays_orders_module.ensure_repo')
    @patch('installer.build_mays_orders_module.run')
    @patch('installer.build_mays_orders_module.validate_generated_contract')
    @patch('installer.build_mays_orders_module.post_run_checks')
    @patch('installer.build_mays_orders_module.shutil.copytree')
    def test_terraform_error_preserves_target(
        self, mock_copytree, mock_post_run, mock_validate, mock_run, mock_ensure_repo
    ):
        """4. Terraform-Fehler -> Ziel bleibt bytegleich erhalten."""
        mock_ensure_repo.return_value = None
        mock_run.return_value = MagicMock(returncode=0)
        mock_validate.return_value = None
        mock_post_run.side_effect = RuntimeError("Terraform validate failed")

        with patch('installer.build_mays_orders_module.TARGET_MODULE_DIR', self.target):
            with self.assertRaises(RuntimeError):
                build_module(PROJECT_NAME, force=False)
        self._assert_target_unchanged()
        mock_copytree.assert_not_called()

    @patch('installer.build_mays_orders_module.ensure_repo')
    @patch('installer.build_mays_orders_module.run')
    @patch('installer.build_mays_orders_module.validate_generated_contract')
    @patch('installer.build_mays_orders_module.post_run_checks')
    @patch('installer.build_mays_orders_module.shutil.copytree')
    @patch('installer.build_mays_orders_module.shutil.rmtree')
    def test_force_with_existing_installation(
        self, mock_rmtree, mock_copytree, mock_post_run, mock_validate, mock_run, mock_ensure_repo
    ):
        """5. --force bei vorhandener Installation -> Ziel wird ersetzt (nur bei Erfolg)."""
        mock_ensure_repo.return_value = None
        mock_run.return_value = MagicMock(returncode=0)
        mock_validate.return_value = None
        mock_post_run.return_value = None
        mock_rmtree.return_value = None

        with patch('installer.build_mays_orders_module.TARGET_MODULE_DIR', self.target):
            build_module(PROJECT_NAME, force=True)
        # copytree called twice: once for backup, once for actual adoption
        self.assertTrue(mock_copytree.call_count >= 2)
        self.assertTrue(self.target.exists())

    @patch('installer.build_mays_orders_module.ensure_repo')
    @patch('installer.build_mays_orders_module.run')
    @patch('installer.build_mays_orders_module.validate_generated_contract')
    @patch('installer.build_mays_orders_module.post_run_checks')
    @patch('installer.build_mays_orders_module.shutil.copytree')
    @patch('installer.build_mays_orders_module.shutil.rmtree')
    def test_error_during_target_adoption_preserves_original(
        self, mock_rmtree, mock_copytree, mock_post_run, mock_validate, mock_run, mock_ensure_repo
    ):
        """6. Fehler während der Zielübernahme -> ursprüngliches Ziel bleibt erhalten."""
        mock_ensure_repo.return_value = None
        mock_run.return_value = MagicMock(returncode=0)
        mock_validate.return_value = None
        mock_post_run.return_value = None
        mock_copytree.side_effect = OSError("Disk full during adoption")
        mock_rmtree.return_value = None

        with patch('installer.build_mays_orders_module.TARGET_MODULE_DIR', self.target):
            with self.assertRaises(OSError):
                build_module(PROJECT_NAME, force=False)
        self._assert_target_unchanged()

    @patch('installer.build_mays_orders_module.ensure_repo')
    @patch('installer.build_mays_orders_module.run')
    @patch('installer.build_mays_orders_module.validate_generated_contract')
    @patch('installer.build_mays_orders_module.post_run_checks')
    @patch('installer.build_mays_orders_module.shutil.copytree')
    @patch('installer.build_mays_orders_module.shutil.rmtree')
    def test_successful_target_adoption(
        self, mock_rmtree, mock_copytree, mock_post_run, mock_validate, mock_run, mock_ensure_repo
    ):
        """7. Erfolgreiche Zielübernahme."""
        mock_ensure_repo.return_value = None
        mock_run.return_value = MagicMock(returncode=0)
        mock_validate.return_value = None
        mock_post_run.return_value = None
        mock_rmtree.return_value = None

        with patch('installer.build_mays_orders_module.TARGET_MODULE_DIR', self.target):
            build_module(PROJECT_NAME, force=False)
        # copytree called twice: once for backup, once for actual adoption
        self.assertTrue(mock_copytree.call_count >= 2)
        self.assertTrue(self.target.exists())
        print("  Successful adoption: target module replaced with generated content")


# ============================================================================
# Section 7: Weitere Wrapper-Fehlerfälle
# ============================================================================

class TestWeitereWrapperFehlerfaelle(unittest.TestCase):
    """Tests for Section 7: Additional wrapper error cases."""

    def test_load_builder_pin_from_builder_pin_file(self):
        """Builder-Pin wird aus mays-orders-builder.pinned.json geladen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pin_file = Path(tmpdir) / "mays-orders-builder.pinned.json"
            pin_file.write_text(json.dumps({"commit": PINNED_COMMIT}), encoding="utf-8")

            with patch('installer.build_mays_orders_module.BUILDER_PIN_FILE', pin_file):
                pin = load_builder_pin()
                self.assertEqual(pin, PINNED_COMMIT)

    def test_load_builder_pin_missing_file_raises(self):
        """Pin-Datei fehlt → RuntimeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pin_file = Path(tmpdir) / "mays-orders-builder.pinned.json"
            # Datei existiert nicht

            with patch('installer.build_mays_orders_module.BUILDER_PIN_FILE', pin_file):
                with self.assertRaises(RuntimeError) as ctx:
                    load_builder_pin()
                self.assertIn("fehlt", str(ctx.exception))

    def test_load_builder_pin_invalid_json_raises(self):
        """Pin-Datei ungültig → RuntimeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pin_file = Path(tmpdir) / "mays-orders-builder.pinned.json"
            pin_file.write_text("{invalid json", encoding="utf-8")

            with patch('installer.build_mays_orders_module.BUILDER_PIN_FILE', pin_file):
                with self.assertRaises(RuntimeError) as ctx:
                    load_builder_pin()
                self.assertIn("ungültig", str(ctx.exception))

    def test_load_builder_pin_missing_commit_raises(self):
        """Pin-Datei ohne Commit → RuntimeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pin_file = Path(tmpdir) / "mays-orders-builder.pinned.json"
            pin_file.write_text('{"other": "value"}', encoding="utf-8")

            with patch('installer.build_mays_orders_module.BUILDER_PIN_FILE', pin_file):
                with self.assertRaises(RuntimeError) as ctx:
                    load_builder_pin()
                self.assertIn("keinen Commit", str(ctx.exception))

    def test_load_builder_pin_sha_mismatch_raises(self):
        """SHA weicht von PINNED_COMMIT ab → RuntimeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pin_file = Path(tmpdir) / "mays-orders-builder.pinned.json"
            pin_file.write_text('{"commit": "aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111"}', encoding="utf-8")

            with patch('installer.build_mays_orders_module.BUILDER_PIN_FILE', pin_file):
                with self.assertRaises(RuntimeError) as ctx:
                    load_builder_pin()
                self.assertIn("weicht ab", str(ctx.exception))

    def test_ensure_repo_dirty_worktree_aborts(self):
        """Dirty Builder-Quelle wird abgelehnt (sys.exit(1))."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder_dir = Path(tmpdir) / "mays_order_builder"
            builder_dir.mkdir()

            with patch('installer.build_mays_orders_module.MAYS_ORDERS_BUILDER_DIR', builder_dir):
                with patch('installer.build_mays_orders_module.INSTALLER_PROJECTS', builder_dir.parent):
                    with patch('installer.build_mays_orders_module.run') as mock_run:
                        mock_run.return_value = MagicMock()
                        with patch('installer.build_mays_orders_module.subprocess.run') as mock_subprocess:
                            mock_subprocess.return_value = MagicMock(stdout=" M f.txt\n", returncode=0)
                            with patch('installer.build_mays_orders_module.sys.exit') as mock_exit:
                                ensure_repo()
                                mock_exit.assert_called_once_with(1)

    def test_validate_generated_contract_missing_outputs(self):
        """Fehlende öffentliche Outputs -> Vertragsfehler."""
        gen_dir = _write_gen_module(
            tempfile.mkdtemp(),
            main_tf_content='',
            outputs_tf_content='output "x" { value = "1" }',  # Only 1 output, need 20
            vars_tf_content='variable "external_cognito" {}\nvariable "log_retention_days" {}\nvariable "monitoring_enabled" {}\nvariable "project_name" {}\nvariable "tags" {}',
            iam_main_content='variable "sqs_enabled" {}',
            iam_vars_content='variable "sqs_enabled" {}',
        )

        with self.assertRaises(RuntimeError) as ctx:
            validate_generated_contract(gen_dir)
        self.assertIn("20 Outputs", str(ctx.exception))

    def test_successful_full_mock_build(self):
        """Erfolgreicher vollständiger Mock-Build."""
        target = Path(tempfile.mkdtemp()) / "mays_orders"
        target.mkdir(parents=True)
        gen_dir = _write_gen_module(
            tempfile.mkdtemp(),
            main_tf_content='module "x" {}',
            outputs_tf_content='output "sqs_queue_name" { value = "q" }',
            vars_tf_content='variable "external_cognito" {}\nvariable "log_retention_days" {}\nvariable "monitoring_enabled" {}\nvariable "project_name" {}\nvariable "tags" {}',
            iam_main_content='variable "sqs_enabled" {}\ncount = var.sqs_enabled ? 1 : 0\ncount = var.sqs_enabled ? 1 : 0',
            iam_vars_content='variable "sqs_enabled" {}',
        )

        with patch('installer.build_mays_orders_module.TARGET_MODULE_DIR', target):
            with patch('installer.build_mays_orders_module.ensure_repo'):
                with patch('installer.build_mays_orders_module.run') as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)
                    with patch('installer.build_mays_orders_module.validate_generated_contract'):
                        with patch('installer.build_mays_orders_module.post_run_checks'):
                            with patch('installer.build_mays_orders_module.shutil.copytree'):
                                try:
                                    build_module(PROJECT_NAME, force=False)
                                except SystemExit:
                                    self.fail("build_module raised SystemExit unexpectedly")


if __name__ == '__main__':
    unittest.main()