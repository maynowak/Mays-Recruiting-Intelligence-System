"""RIS-ANALYSIS-CANARY-10A — deployment preparation invariants.

Unit-level checks for the artifact builder and the Terraform runtime gate. The
read-only plans themselves are produced by the installer and recorded in
docs/reports/RIS-ANALYSIS-CANARY-10A.md; they are not committed (plan binaries
are configuration-, backend- and state-specific).
"""

import importlib.util
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
MODULE = ROOT / "terraform" / "modules" / "analysis_runtime"


def load_tool(name):
    path = TOOLS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def module_source():
    return "\n".join(
        (MODULE / name).read_text(encoding="utf-8")
        for name in sorted(os.listdir(MODULE)) if name.endswith(".tf"))


class ArtifactBuilderTest(unittest.TestCase):
    def setUp(self):
        self.builder = load_tool("build_analysis_parser_artifact")

    def make_tree(self, root: Path) -> Path:
        files = {
            "lambda/ris_parser_handler.mjs": "export async function handler(){}",
            "scripts/ris-parser-cli.mjs": "export async function runParser(){}",
            "api/_lib/analysis/service.mjs": "export const x = 1;",
            "api/_lib/ats.mjs": "export const y = 1;",
            "api/_lib/analysis/service.mjs.map": "ignored",
            "api/_lib/analysis/service.test.mjs": "ignored",
            "api/_lib/__tests__/ignored.mjs": "ignored",
            "node_modules/pdfjs-dist/legacy/build/pdf.mjs": "export {};",
            "node_modules/pdfjs-dist/package.json": "{}",
            "node_modules/pdfjs-dist/web/ignored.mjs": "ignored",
            "node_modules/@napi-rs/canvas/package.json": "{}",
            "node_modules/@napi-rs/canvas/index.js": "module.exports={}",
        }
        for name, body in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        canvas = root / "canvas-platform"
        canvas.mkdir(parents=True)
        (canvas / "package.json").write_text("{}", encoding="utf-8")
        (canvas / "skia.node").write_bytes(b"\x7fELF")
        return canvas

    def test_build_is_deterministic_and_filters_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobsearch"
            canvas = self.make_tree(root)
            out1 = Path(tmp) / "a.zip"
            out2 = Path(tmp) / "b.zip"
            first = self.builder.build(
                root, out1, {"canvas-linux-arm64-gnu": canvas})
            second = self.builder.build(
                root, out2, {"canvas-linux-arm64-gnu": canvas})
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(out1.read_bytes(), out2.read_bytes())
            names = zipfile.ZipFile(out1).namelist()
            self.assertIn("lambda/ris_parser_handler.mjs", names)
            self.assertIn(
                "node_modules/@napi-rs/canvas-linux-arm64-gnu/skia.node", names)
            self.assertFalse(any(name.endswith(".map") for name in names))
            self.assertFalse(any("__tests__" in name for name in names))
            self.assertFalse(any("/web/" in name for name in names))
            self.assertFalse(any(name.endswith(".test.mjs") for name in names))

    def test_missing_canvas_binary_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobsearch"
            self.make_tree(root)
            empty = Path(tmp) / "empty"
            empty.mkdir()
            with self.assertRaises(SystemExit):
                self.builder.collect_entries(
                    root, {"canvas-linux-arm64-gnu": empty})

    def test_missing_required_module_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jobsearch"
            canvas = self.make_tree(root)
            (root / "api/_lib/ats.mjs").unlink()
            with self.assertRaises(SystemExit):
                self.builder.collect_entries(
                    root, {"canvas-linux-arm64-gnu": canvas})


class RuntimeGateInvariantTest(unittest.TestCase):
    def setUp(self):
        self.source = module_source()

    def test_parser_resources_are_the_only_addition(self):
        import re

        gated = len(re.findall(
            r"count\s*=\s*var\.enable_analysis_runtime\s*\?\s*1\s*:\s*0",
            self.source))
        self.assertGreaterEqual(gated, 6)
        import re

        found = set(re.findall(
            r'resource "([a-z0-9_]+)" "([a-z0-9_]+)"', self.source))
        expected = {
            ("aws_iam_role", "parser"),
            ("aws_iam_role_policy", "parser_logs"),
            ("aws_cloudwatch_log_group", "parser"),
            ("aws_lambda_function", "parser"),
            ("aws_iam_role_policy", "analysis_invoke_parser"),
            ("aws_lambda_permission", "parser_invoke_analysis"),
        }
        self.assertTrue(expected.issubset(found), expected - found)

    def test_runtime_is_arm64_node22_and_private(self):
        self.assertIn('runtime       = var.parser_runtime', self.source)
        self.assertIn('default = "nodejs22.x"',
                      (MODULE / "variables.tf").read_text(encoding="utf-8"))
        self.assertIn('architectures    = ["arm64"]', self.source)
        self.assertIn('handler       = "lambda/ris_parser_handler.handler"',
                      self.source)
        for forbidden in ("aws_apigateway", "aws_lambda_function_url",
                          "aws_cloudfront", "aws_sqs", "aws_secretsmanager",
                          "aws_dynamodb"):
            self.assertNotIn(forbidden, self.source)

    def test_parser_role_is_logs_only(self):
        role = self.source.split('resource "aws_iam_role_policy" "parser_logs"', 1)[1]
        role = role.split('resource "', 1)[0]
        self.assertIn("logs:CreateLogStream", role)
        self.assertIn("logs:PutLogEvents", role)
        for forbidden in ("s3:", "sqs:", "secretsmanager:", "dynamodb:",
                          "lambda:InvokeFunction"):
            self.assertNotIn(forbidden, role)

    def test_jobs_bucket_is_private_encrypted_and_expiring(self):
        for marker in (
            'block_public_acls       = true',
            'block_public_policy     = true',
            'restrict_public_buckets = true',
            'sse_algorithm = "AES256"',
            'id     = "expire-temporary-jobs"',
            'days = var.job_retention_days',
        ):
            self.assertIn(marker, self.source)


class CanaryPdfGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.generator = load_tool("make_synthetic_canary_pdf")

    def test_pdf_is_deterministic_and_synthetic(self):
        first = self.generator.build()
        second = self.generator.build()
        self.assertEqual(first, second)
        self.assertTrue(first.startswith(b"%PDF-1.7"))
        self.assertIn(b"CANARY APPLICANT", first)
        for marker in (b"@", b"linkedin", b"+49", b"phone"):
            self.assertNotIn(marker, first.lower())


if __name__ == "__main__":
    unittest.main()
