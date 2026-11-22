"""RIS-ANALYSIS-CANARY-10A STEP B — artifact verifier invariants."""

import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_verifier():
    path = ROOT / "tools" / "verify_analysis_parser_artifact.py"
    spec = importlib.util.spec_from_file_location("artifact_verifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MANIFEST = {
    "architecture": "arm64",
    "handler": "lambda/ris_parser_handler.handler",
    "publicEndpoint": False,
    "sha256": "0" * 64,
}


class ArtifactInspectorTest(unittest.TestCase):
    def setUp(self):
        self.verifier = load_verifier()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "artifact.zip"

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, extra=(), drop=()):
        names = list(self.verifier.REQUIRED) + ["api/_lib/filter.mjs"]
        names += ["node_modules/@napi-rs/canvas-linux-arm64-gnu/skia.node"]
        names = [name for name in names if name not in drop] + list(extra)
        with zipfile.ZipFile(self.path, "w") as archive:
            for name in names:
                archive.writestr(name, "x")
        return zipfile.ZipFile(self.path)

    def test_complete_artifact_has_no_problems(self):
        with self.make() as archive:
            self.assertEqual([], self.verifier.inspect(archive, MANIFEST))

    def test_missing_handler_is_reported(self):
        with self.make(drop=("lambda/ris_parser_handler.mjs",)) as archive:
            problems = self.verifier.inspect(archive, MANIFEST)
        self.assertTrue(any("ris_parser_handler" in p for p in problems))

    def test_second_native_binary_is_rejected(self):
        with self.make(extra=(
                "node_modules/@napi-rs/canvas-win32-x64-msvc/canvas.node",)
        ) as archive:
            problems = self.verifier.inspect(archive, MANIFEST)
        self.assertTrue(any("native" in p for p in problems))

    def test_maps_tests_and_public_endpoint_flag_are_rejected(self):
        with self.make(extra=(
                "api/_lib/x.mjs.map", "api/_lib/__tests__/x.mjs")) as archive:
            problems = self.verifier.inspect(archive, MANIFEST)
        self.assertTrue(any(".map" in p for p in problems))
        self.assertTrue(any("__tests__" in p for p in problems))

        with self.make() as archive:
            problems = self.verifier.inspect(
                archive, {**MANIFEST, "publicEndpoint": True})
        self.assertTrue(any("public endpoint" in p for p in problems))

    def test_required_closure_matches_the_builder(self):
        builder_path = ROOT / "tools" / "build_analysis_parser_artifact.py"
        spec = importlib.util.spec_from_file_location("artifact_builder",
                                                      builder_path)
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        for entry in self.verifier.REQUIRED:
            self.assertTrue(
                entry in builder.REQUIRED_ENTRIES
                or entry.startswith("node_modules/@napi-rs/canvas-linux-arm64-gnu/"),
                entry)


if __name__ == "__main__":
    unittest.main()
