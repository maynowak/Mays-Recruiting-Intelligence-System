"""Tests for the mays-jobsearch contract snapshot tool.

The tool reads a pinned source state and never copies code. Tests use a fake
source so they are deterministic and require no network or clone.
"""

import json
import tempfile
import unittest
from pathlib import Path

from installer import jobsearch_api_contract as contract

BASE = {
    "protocol": "MAYS-JOBSEARCH-API-SNAPSHOT-V1",
    "contract": "docs/contracts/JOBSEARCH-ATS-ANALYSIS-V1.json",
    "source": {"repo": "maynowak/mays-jobsearch"},
    "license": {
        "source": "AGPL-3.0-only",
        "code_copied": False,
        "boundary": "network-service",
    },
}

FILES = {
    "api/ats-analysis.mjs": (
        "// /api/ats-analysis validateRequest\n"
        'const response = { analysis: { score: 0, keywordCoverage: { overall: 0 }, '
        'requirementCoverage: 0, profileEvidenceCoverage: 0, roleMatch: null, '
        'analysisStatus: "insufficient", basis: {}, metadata: {}, criticalGaps, '
        'requirements: [], matches: [] }, recommendations: [], ai: { } };\n'
    ).encode(),
    "api/_lib/ats.mjs": (
        "export function analyzeJobForAts() {}\n"
        "export function extractRequirementsFromJob() {}\n"
        "export function matchRequirement() {}\n"
        "export function calculateRoleMatch() {}\n"
        "export function extractJobMetadata() {}\n"
        "export function generateCVRecommendations() {}\n"
        "const importanceWeight = {}; const criticalGaps = [];\n"
        "const analysisStatus = 'complete'; const requirementMatch = 0;\n"
    ).encode(),
    "api/_lib/filter.mjs": (
        "export function tokenize() {}\n"
        "export function stripHtml() {}\n"
        "export function htmlToPlainText() {}\n"
        "export function detectLanguage() {}\n"
    ).encode(),
}


class FakeSource:
    def __init__(self, files=None, head="a" * 40, commit="a" * 40):
        self.files = dict(files or FILES)
        self._head = head
        self._commit = commit

    def head(self):
        return self._head

    def has_commit(self, commit):
        return commit == self._commit

    def read(self, commit, path):
        return self.files[path]


class ContractToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.manifest_path = Path(self.tmp.name) / "manifest.json"
        self.manifest_path.write_text(json.dumps(BASE), encoding="utf-8")
        self.source = FakeSource()

    def _pin(self):
        contract.refresh(self.source, self.manifest_path)
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def test_check_up_to_date(self):
        self._pin()
        result = contract.check(self.source, self.manifest_path)
        self.assertEqual(result["status"], "UP_TO_DATE")
        self.assertEqual(result["problems"], [])
        self.assertEqual(result["files"], 3)

    def test_check_detects_drift(self):
        self._pin()
        drifting = FakeSource(head="b" * 40, commit="a" * 40)
        result = contract.check(drifting, self.manifest_path)
        self.assertEqual(result["status"], "DRIFT")

    def test_check_detects_hash_mismatch(self):
        self._pin()
        changed = dict(FILES)
        changed["api/_lib/filter.mjs"] = FILES["api/_lib/filter.mjs"] + b"// changed\n"
        result = contract.check(FakeSource(files=changed), self.manifest_path)
        self.assertEqual(result["status"], "MISMATCH")
        self.assertTrue(any("filter.mjs" in p for p in result["problems"]))

    def test_check_detects_missing_marker(self):
        self._pin()
        broken = dict(FILES)
        broken["api/_lib/ats.mjs"] = FILES["api/_lib/ats.mjs"].replace(
            b"analyzeJobForAts", b"renamedFunction"
        )
        result = contract.check(FakeSource(files=broken), self.manifest_path)
        self.assertEqual(result["status"], "MISMATCH")
        self.assertTrue(any("missing contract markers" in p for p in result["problems"]))

    def test_refresh_writes_deterministic_manifest(self):
        self._pin()
        first = self.manifest_path.read_bytes()
        contract.refresh(self.source, self.manifest_path)
        second = self.manifest_path.read_bytes()
        self.assertEqual(first, second)
        manifest = json.loads(first)
        self.assertEqual(manifest["source"]["commit"], "a" * 40)
        self.assertEqual(sorted(manifest["files"]), sorted(contract.MARKERS))
        self.assertFalse(manifest["license"]["code_copied"])

    def test_refresh_fails_closed_and_does_not_write(self):
        self._pin()
        before = self.manifest_path.read_bytes()
        broken = dict(FILES)
        broken["api/ats-analysis.mjs"] = b"// no contract markers here\n"
        with self.assertRaises(contract.ContractError):
            contract.refresh(FakeSource(files=broken), self.manifest_path)
        self.assertEqual(self.manifest_path.read_bytes(), before)

    def test_manifest_rejects_unknown_file_set(self):
        self._pin()
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["api/extra.mjs"] = "0" * 64
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        result = contract.check(self.source, self.manifest_path)
        self.assertEqual(result["status"], "MISMATCH")


class ContractDocumentTest(unittest.TestCase):
    def test_contract_and_manifest_agree(self):
        root = Path(__file__).resolve().parents[1]
        contract_doc = json.loads(
            (root / "docs/contracts/JOBSEARCH-ATS-ANALYSIS-V1.json").read_text(
                encoding="utf-8"
            )
        )
        manifest = json.loads(
            (root / "docs/contracts/mays-jobsearch-api.manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract_doc["protocol"], "MAYS-JOBSEARCH-ATS-ANALYSIS-V1")
        self.assertEqual(contract_doc["contract_version"], "1.2")
        self.assertEqual(contract_doc["endpoint"]["path"], "/api/ats-analysis")
        self.assertEqual(contract_doc["statuses"], ["MATCHED", "PARTIAL", "UNKNOWN"])
        self.assertIn("requirementCoverage", contract_doc["response"]["analysis"]["required"])
        self.assertIn("analysisStatus", contract_doc["response"]["analysis"]["required"])
        self.assertFalse(contract_doc["license"]["code_copied"])
        self.assertEqual(manifest["contract"], "docs/contracts/JOBSEARCH-ATS-ANALYSIS-V1.json")
        self.assertFalse(manifest["license"]["code_copied"])
        self.assertEqual(manifest["source"]["repo"], "maynowak/mays-jobsearch")


if __name__ == "__main__":
    unittest.main()
