"""RIS-ANALYSIS-16C2-QA2: generated module result-transport output contract."""

import hashlib
import tempfile
import unittest
from pathlib import Path

import installer.build_mays_orders_module as builder


class TransportOutputInjectionTest(unittest.TestCase):
    BASE = 'output "sqs_queue_name" {\n  value = module.sqs.queue_name\n}\n'

    def _write(self, text=BASE, name="outputs.tf"):
        self._counter += 1
        directory = Path(self.tmp.name) / f"mod{self._counter}"
        directory.mkdir()
        path = directory / name
        path.write_text(text, encoding="utf-8")
        return directory, path

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._counter = 0

    def tearDown(self):
        self.tmp.cleanup()

    def test_injection_adds_exactly_three_references_deterministically(self):
        first, first_path = self._write()
        second, second_path = self._write()
        builder.inject_transport_outputs(first)
        builder.inject_transport_outputs(second)
        first_text = first_path.read_text(encoding="utf-8")
        second_text = second_path.read_text(encoding="utf-8")
        self.assertEqual(first_text, second_text)
        self.assertEqual(
            hashlib.sha256(first_path.read_bytes()).hexdigest(),
            hashlib.sha256(second_path.read_bytes()).hexdigest(),
        )
        for name, ref in (
            ("results_queue_url",
             "module.agent_transport[0].results_queue_url"),
            ("results_queue_arn",
             "module.agent_transport[0].results_queue_arn"),
            ("result_hmac_secret_arn",
             "module.agent_transport[0].result_hmac_secret_arn"),
        ):
            self.assertEqual(1, first_text.count(f'output "{name}"'))
            self.assertIn(ref, first_text)

    def test_duplicate_injection_fails_closed(self):
        directory, path = self._write()
        builder.inject_transport_outputs(directory)
        before = path.read_text(encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "exportiert bereits"):
            builder.inject_transport_outputs(directory)
        self.assertEqual(before, path.read_text(encoding="utf-8"))

    def test_existing_upstream_output_fails_closed(self):
        text = self.BASE + '\noutput "results_queue_url" {\n  value = "x"\n}\n'
        directory, path = self._write(text)
        before = path.read_text(encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "exportiert bereits"):
            builder.inject_transport_outputs(directory)
        self.assertEqual(before, path.read_text(encoding="utf-8"))

    def test_missing_output_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "genau einmal"):
            builder.validate_transport_outputs(self.BASE)

    def test_duplicate_output_is_rejected(self):
        text = self.BASE + (
            '\noutput "results_queue_url" {\n'
            '  value = try(module.agent_transport[0].results_queue_url, "")\n'
            '}\n'
        ) * 2
        with self.assertRaisesRegex(RuntimeError, "genau einmal"):
            builder.validate_transport_outputs(text)

    def test_wrong_reference_is_rejected(self):
        text = self.BASE
        for name in builder.TRANSPORT_OUTPUT_NAMES:
            text += (
                f'\noutput "{name}" {{\n'
                f'  value = module.wrong.{name}\n'
                '}\n'
            )
        with self.assertRaisesRegex(RuntimeError, "referenziert nicht"):
            builder.validate_transport_outputs(text)

    def test_outputs_add_no_resources_permissions_or_secret_values(self):
        block = builder.TRANSPORT_OUTPUTS
        self.assertEqual(3, block.count("output "))
        for forbidden in (
            'resource "', 'data "', "aws_secretsmanager_secret",
            "secret_string", "policy", "iam", "sqs_queue",
        ):
            self.assertNotIn(forbidden, block)
        for name in builder.TRANSPORT_OUTPUT_NAMES:
            self.assertIn(f'output "{name}"', block)

    def test_active_build_calls_injection_before_validation(self):
        source = Path(builder.__file__).read_text(encoding="utf-8")
        inject = source.index("inject_transport_outputs(TEMP_MODULE_DIR)")
        validate = source.index("validate_generated_contract(TEMP_MODULE_DIR)")
        self.assertLess(inject, validate)
        self.assertIn('required_outputs_count = 23', source)
        for name in builder.TRANSPORT_OUTPUT_NAMES:
            self.assertIn(f'"{name}"', source)


class PatchFreeContractDetectionTest(unittest.TestCase):
    """MO 03B (db4f9e7+) is detected from its generated files only."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _module(self, outputs=True, variable=True, merge=True):
        root = self.root
        (root / "modules" / "lambda").mkdir(parents=True)
        output_blocks = "\n".join(
            f'output "{name}" {{\n  value = try(module.agent_transport[0].{name}, "")\n}}\n'
            for name in builder.TRANSPORT_OUTPUT_NAMES
        ) if outputs else 'output "sqs_queue_name" {\n  value = "x"\n}\n'
        variable_block = ('variable "additional_environment" {\n  type = map(string)\n}\n'
                          if variable else "")
        lambda_main = ('variables = merge({\n  ORDERS_TABLE = "x"\n}, '
                       'var.additional_environment)\n' if merge else
                       'variables = { ORDERS_TABLE = "x" }\n')
        (root / "outputs.tf").write_text(output_blocks, encoding="utf-8")
        (root / "variables.tf").write_text(variable_block, encoding="utf-8")
        (root / "modules" / "lambda" / "main.tf").write_text(
            lambda_main, encoding="utf-8")
        return root

    def test_complete_contract_is_patch_free(self):
        self.assertTrue(builder.is_patch_free_contract(self._module()))

    def test_missing_transport_output_falls_back_to_legacy(self):
        self.assertFalse(builder.is_patch_free_contract(self._module(outputs=False)))

    def test_missing_additional_environment_falls_back_to_legacy(self):
        self.assertFalse(builder.is_patch_free_contract(self._module(variable=False)))

    def test_missing_env_merge_falls_back_to_legacy(self):
        self.assertFalse(builder.is_patch_free_contract(self._module(merge=False)))

    def test_incomplete_module_falls_back_to_legacy(self):
        self.assertFalse(builder.is_patch_free_contract(self.root / "absent"))


if __name__ == "__main__":
    unittest.main()
