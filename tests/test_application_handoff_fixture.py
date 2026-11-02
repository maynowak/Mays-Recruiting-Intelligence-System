import json
import unittest
from pathlib import Path

from jobsearch.application_contract import validate_create, validate_transition


FIXTURE = Path(__file__).parent / "fixtures" / "application-handoff-v1.json"


class ApplicationHandoffFixtureTests(unittest.TestCase):
    def test_session_fixture_maps_without_identity_fields(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        request = data["createRequest"]
        parsed = validate_create(request)
        self.assertEqual("job-42", parsed["job"]["jobId"])
        for field in data["forbiddenClientFields"]:
            self.assertNotIn(field, parsed)

    def test_explicit_submit_and_conflict_are_remote_operations(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        status = data["remoteLifecycleExamples"]["statusRequest"]
        validate_transition("READY", status["status"], confirm=status["confirm"])
        self.assertEqual(409, data["remoteLifecycleExamples"]["conflictResponse"]["status"])

    def test_fixture_has_no_real_document_or_credential_material(self):
        raw = FIXTURE.read_text(encoding="utf-8")
        self.assertNotIn("Authorization", raw)
        self.assertNotIn("Bearer ", raw)
        self.assertNotIn("base64", raw.lower())
        self.assertNotIn("application/pdf", raw)


if __name__ == "__main__":
    unittest.main()
