"""M05/M06 — verify the *generated* Orders module artifact, not ``lambda/src``.

Set ``MO_ORDERS_MODULE`` to the generated module directory (the one that
contains ``module-builder.manifest.json`` and ``lambda/dist/lambda.zip``).
Optional pins make the check fail-closed when the expected identity is known:

    MO_ORDERS_MODULE_ZIP_SHA256   expected SHA-256 of lambda/dist/lambda.zip
    MO_ORDERS_SOURCE_COMMIT       expected source.commit of the manifest

Nothing in this file reads the repository checkout ``lambda/src``. The import
proof runs in a fresh interpreter whose only non-stdlib path entry is the ZIP.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

MODULE_DIR = os.environ.get("MO_ORDERS_MODULE", "")
ZIP_PATH = (
    os.path.join(MODULE_DIR, "lambda", "dist", "lambda.zip") if MODULE_DIR else ""
)
EXPECTED_ZIP_SHA256 = os.environ.get("MO_ORDERS_MODULE_ZIP_SHA256", "")
EXPECTED_SOURCE_COMMIT = os.environ.get("MO_ORDERS_SOURCE_COMMIT", "")

EXPECTED_MODULES = {
    "agent_order.py",
    "dispatch.py",
    "errors.py",
    "identity.py",
    "index.py",
    "order_service.py",
    "order_types.py",
    "result_consumer.py",
    "result_envelope.py",
    "result_handler.py",
    "sqs_handler.py",
    "state_machine.py",
    "validation.py",
}

HANDLER_ENTRYPOINTS = ("index", "result_consumer", "result_handler", "sqs_handler")


def _read(relative):
    with open(os.path.join(MODULE_DIR, relative), encoding="utf-8") as handle:
        return handle.read()


@unittest.skipUnless(
    MODULE_DIR and os.path.isfile(ZIP_PATH), "MO_ORDERS_MODULE not set"
)
class GeneratedModuleArtifactTest(unittest.TestCase):
    """Every assertion here is made against the built module, never the source."""

    def test_manifest_records_the_exact_source_commit(self):
        manifest = json.loads(_read("module-builder.manifest.json"))
        commit = manifest["source"]["commit"]
        self.assertRegex(commit, r"^[0-9a-f]{40}$", "source.commit must be a full SHA")
        self.assertNotEqual(commit, "unknown")
        self.assertEqual(manifest["preset"], "orders-service")
        if EXPECTED_SOURCE_COMMIT:
            self.assertEqual(commit, EXPECTED_SOURCE_COMMIT)
        self.assertIn("lambda/dist/lambda.zip", manifest["artifacts_sha256"])

    def test_zip_is_intact_and_has_the_deployment_set(self):
        with zipfile.ZipFile(ZIP_PATH) as archive:
            self.assertIsNone(archive.testzip(), "ZIP CRC check failed")
            names = set(archive.namelist())
        self.assertEqual(names, EXPECTED_MODULES, "unexpected deployment file set")

    def test_zip_sha256_matches_the_recorded_artifact(self):
        with open(ZIP_PATH, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        manifest = json.loads(_read("module-builder.manifest.json"))
        self.assertEqual(manifest["artifacts_sha256"]["lambda/dist/lambda.zip"], digest)
        if EXPECTED_ZIP_SHA256:
            self.assertEqual(digest, EXPECTED_ZIP_SHA256)
        # Surfaced in the report: the exact path and hash the tests loaded.
        print(f"\n[artifact] {ZIP_PATH}\n[artifact] sha256={digest}")

    def test_every_handler_module_imports_from_the_zip_only(self):
        """A fresh interpreter sees the ZIP and nothing else from the build."""
        program = (
            "import json, sys\n"
            f"sys.path.insert(0, {ZIP_PATH!r})\n"
            "import importlib\n"
            f"modules = {sorted(name[:-3] for name in EXPECTED_MODULES)!r}\n"
            "result = {}\n"
            "for name in modules:\n"
            "    module = importlib.import_module(name)\n"
            "    result[name] = getattr(module, '__file__', None)\n"
            "print(json.dumps(result))\n"
        )
        with tempfile.TemporaryDirectory() as neutral_cwd:
            completed = subprocess.run(
                [sys.executable, "-c", program],
                cwd=neutral_cwd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        loaded = json.loads(completed.stdout)
        self.assertEqual(set(loaded), {name[:-3] for name in EXPECTED_MODULES})
        for name, path in loaded.items():
            self.assertIsNotNone(path, f"{name} has no file")
            self.assertIn("lambda.zip", path.replace("\\", "/"), f"{name} not from ZIP")

    def test_lambda_handlers_expose_a_callable_handler(self):
        program = (
            "import sys\n"
            f"sys.path.insert(0, {ZIP_PATH!r})\n"
            "import importlib\n"
            f"for name in {list(HANDLER_ENTRYPOINTS)!r}:\n"
            "    module = importlib.import_module(name)\n"
            "    assert callable(getattr(module, 'handler', None)), name\n"
            "print('ok')\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", program], capture_output=True, text=True, timeout=120
        )
        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])

    def test_dynamodb_module_carries_the_ownership_index(self):
        dynamodb = _read(os.path.join("modules", "dynamodb", "main.tf"))
        self.assertIn('name               = "gsi3"', dynamodb)
        self.assertIn('name = "gsi3pk"', dynamodb)
        self.assertIn('name = "gsi3sk"', dynamodb)

    def test_cognito_modes_are_evaluation_safe(self):
        main_tf = _read("main.tf")
        outputs = _read("outputs.tf")
        variables = _read("variables.tf")
        # MANAGED (default) instantiates the pool; EXTERNAL leaves it empty.
        self.assertIn('count        = var.external_cognito == null ? 1 : 0', main_tf)
        self.assertRegex(variables, r'variable "external_cognito" \{(?:.|\n)*?default\s*=\s*null')
        # No bare attribute access on the counted module (validate would fail).
        for attribute in (
            "user_pool_endpoint",
            "user_pool_client_id",
            "user_pool_id",
            "user_pool_arn",
            "user_pool_group_staff_name",
        ):
            pattern = rf"module\.cognito\.{attribute}\b"
            self.assertNotRegex(main_tf, pattern)
            self.assertNotRegex(outputs, pattern)

    def test_agent_transport_is_wired_and_default_off(self):
        main_tf = _read("main.tf")
        variables = _read("variables.tf")
        transport = _read(os.path.join("modules", "agent_transport", "main.tf"))
        transport_lambda = _read(os.path.join("modules", "agent_transport", "lambda.tf"))

        self.assertRegex(main_tf, r'module "agent_transport" \{\s*\n\s*count\s+= var\.enable_agent_transport')
        self.assertRegex(
            variables,
            r'variable "enable_agent_transport" \{(?:.|\n)*?default\s*=\s*false',
        )
        # Result consumer entrypoint and its infrastructure boundary.
        self.assertIn('handler       = "result_consumer.handler"', transport_lambda)
        self.assertIn('secretsmanager:GetSecretValue', transport_lambda)
        self.assertIn('aws_sqs_queue" "results"', transport)
        self.assertIn('aws_sqs_queue" "results_dlq"', transport)
        self.assertIn('aws_secretsmanager_secret" "result_hmac"', transport)


if __name__ == "__main__":
    unittest.main()
