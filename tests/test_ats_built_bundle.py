"""ORCH-05: the ATS contract and result body must work from the built bundle.

This test never imports the source tree for the module under test. A fresh
interpreter gets the built ``terraform/lambda.zip`` on sys.path and runs the
contract validator plus the result-body builder.
"""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "terraform" / "lambda.zip"
FIXTURE = ROOT / "tests" / "fixtures" / "ats_result_body" / "score-50-partial.json"

REQUIRED = (
    "agents/__init__.py",
    "agents/ats_agent/__init__.py",
    "agents/ats_agent/agent.py",
    "agents/ats_agent/contract.py",
    "agents/ats_agent/result_body.py",
    "agents/ats_agent/registry.py",
)


@unittest.skipUnless(BUNDLE.is_file(), "terraform/lambda.zip is not built")
class BuiltAgentBundleTest(unittest.TestCase):
    def test_ats_modules_are_packaged(self):
        with zipfile.ZipFile(BUNDLE) as archive:
            names = set(archive.namelist())
        for path in REQUIRED:
            self.assertIn(path, names)

    def test_contract_and_body_run_from_the_zip_only(self):
        program = (
            "import json, sys\n"
            f"sys.path.insert(0, {str(BUNDLE)!r})\n"
            "from agents.ats_agent.contract import "
            "CONTRACT_VERSION, validate_analysis_response\n"
            "from agents.ats_agent.result_body import "
            "RESULT_BODY_VERSION, build_ats_analysis_result_body\n"
            f"payload = json.load(open({str(FIXTURE)!r}, encoding='utf-8'))\n"
            "validate_analysis_response(payload)\n"
            "body = build_ats_analysis_result_body(payload, job_title='QA Engineer')\n"
            "print(json.dumps({\n"
            "    'contract': CONTRACT_VERSION,\n"
            "    'bodyVersion': RESULT_BODY_VERSION,\n"
            "    'bodyType': body['bodyType'],\n"
            "    'score': body['analysis']['score'],\n"
            "    'matches': [m['status'] for m in body['analysis']['matches']],\n"
            "}))\n"
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
        result = json.loads(completed.stdout)
        self.assertEqual(result["contract"], "1.1")
        self.assertEqual(result["bodyVersion"], "1.0")
        self.assertEqual(result["bodyType"], "ATSAnalysisResultBody")
        self.assertEqual(result["score"], 50)
        self.assertEqual(result["matches"], ["MATCHED", "UNKNOWN"])

    def test_bundle_hash_is_reported(self):
        digest = hashlib.sha256(BUNDLE.read_bytes()).hexdigest()
        print(f"\n[bundle] {BUNDLE}\n[bundle] sha256={digest}")
        self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
