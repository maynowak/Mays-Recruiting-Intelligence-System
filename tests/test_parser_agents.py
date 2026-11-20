"""Tests for the shared-parser RIS agents (parse.cv / parse.job)."""

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.cv_parser_agent.agent import CvParserAgent  # noqa: E402
from agents.cv_parser_agent.registry import (  # noqa: E402
    get_cv_parser_descriptor,
    register_cv_parser_agent,
)
from agents.job_parser_agent.agent import JobParserAgent  # noqa: E402
from agents.job_parser_agent.registry import (  # noqa: E402
    get_job_parser_descriptor,
    register_job_parser_agent,
)
from agents.parsers.node_adapter import (  # noqa: E402
    ParserInputError,
    ParserUnavailable,
    parse_via_node,
)

JOBSEARCH_CLI = Path(os.environ.get(
    "RIS_PARSER_CLI",
    r"C:\Users\DCI-Student\projekte\mays-jobsearch\scripts\ris-parser-cli.mjs"))


def envelope(capability, data=None, confidence=None, version="1.0.0"):
    return {
        "schemaVersion": "1.0",
        "capability": capability,
        "parserVersion": version,
        "data": data or {"stableId": "a" * 64},
        "confidence": confidence or {"stableId": "high"},
    }


class TestNodeAdapter(unittest.TestCase):
    def test_unsupported_capability_is_an_input_error(self):
        with self.assertRaises(ParserInputError):
            parse_via_node("parse.other", {}, runner=lambda c, p: {})

    def test_oversized_payload_is_rejected(self):
        with self.assertRaises(ParserInputError):
            parse_via_node(
                "parse.cv", {"text": "x" * 100001},
                runner=lambda c, p: envelope(c))

    def test_wrong_envelope_fails_closed(self):
        with self.assertRaises(ParserUnavailable):
            parse_via_node(
                "parse.cv", {"text": "x" * 30},
                runner=lambda c, p: envelope("parse.job"))

    def test_runner_exception_is_unavailable(self):
        def boom(capability, payload):
            raise RuntimeError("node missing")

        with self.assertRaises(ParserUnavailable):
            parse_via_node("parse.cv", {"text": "x" * 30}, runner=boom)

    def test_valid_runner_result_is_validated(self):
        result = parse_via_node(
            "parse.cv", {"text": "x" * 30},
            runner=lambda c, p: envelope(c))
        self.assertEqual("1.0.0", result.parser_version)
        self.assertEqual("parse.cv", result.capability)


class TestCvParserAgent(unittest.TestCase):
    def work(self, text="Ada Beispiel\nada@example.invalid\nSkills\nPython"):
        return {"workId": "work-cv1", "agentId": "cv-parser-agent",
                "capability": "parse.cv", "payload": {"text": text}}

    def test_success_shape(self):
        agent = CvParserAgent(runner=lambda c, p: envelope(
            c, data={"stableId": "b" * 64, "email": "ada@example.invalid"}))
        out = agent.process_work(self.work())
        self.assertTrue(out["success"])
        self.assertEqual("parse.cv", out["metrics"]["capability"])
        self.assertEqual("b" * 64, out["metrics"]["stableId"])

    def test_missing_text_is_a_validation_error(self):
        agent = CvParserAgent(runner=lambda c, p: envelope(c))
        out = agent.process_work({"workId": "w", "payload": {}})
        self.assertFalse(out["success"])
        self.assertEqual("ValidationError", out["error"]["type"])

    def test_too_short_text_is_rejected_before_the_adapter(self):
        called = []
        agent = CvParserAgent(runner=lambda c, p: called.append(c) or envelope(c))
        out = agent.process_work(self.work("short"))
        self.assertFalse(out["success"])
        self.assertEqual([], called)

    def test_unavailable_runtime_propagates_for_retry(self):
        def unavailable(capability, payload):
            raise ParserUnavailable("no node")

        agent = CvParserAgent(runner=unavailable)
        with self.assertRaises(ParserUnavailable):
            agent.process_work(self.work())


class TestJobParserAgent(unittest.TestCase):
    def work(self, job=None):
        return {"workId": "work-job1", "agentId": "job-parser-agent",
                "capability": "parse.job",
                "payload": {"job": job if job is not None else {
                    "title": "Python Engineer",
                    "descriptionPlain": "Must have 3+ years experience."}}}

    def test_success_shape(self):
        agent = JobParserAgent(runner=lambda c, p: envelope(
            c, data={"stableId": "c" * 64,
                     "requirements": {"required": ["Python"],
                                      "preferred": ["AWS"]}}))
        out = agent.process_work(self.work())
        self.assertTrue(out["success"])
        self.assertEqual("parse.job", out["metrics"]["capability"])
        self.assertEqual(["Python"], out["data"]["requirements"]["required"])

    def test_missing_job_is_a_validation_error(self):
        agent = JobParserAgent(runner=lambda c, p: envelope(c))
        out = agent.process_work({"workId": "w", "payload": {}})
        self.assertFalse(out["success"])
        self.assertEqual("ValidationError", out["error"]["type"])

    def test_job_without_title_or_description_is_rejected(self):
        agent = JobParserAgent(runner=lambda c, p: envelope(c))
        out = agent.process_work(self.work({"company": "Example"}))
        self.assertFalse(out["success"])


class TestRegistration(unittest.TestCase):
    def test_descriptors(self):
        cv = get_cv_parser_descriptor()
        job = get_job_parser_descriptor()
        self.assertEqual("cv-parser-agent", cv.agent_id)
        self.assertEqual(["parse.cv"], cv.capabilities)
        self.assertEqual("job-parser-agent", job.agent_id)
        self.assertEqual(["parse.job"], job.capabilities)

    def test_registration_is_idempotent_and_routes_exist(self):
        from agents.agent_body import AgentBody
        from agents.ecosystem.registry import AgentRegistry

        registry = AgentRegistry()
        body = AgentBody()
        register_cv_parser_agent(registry, body)
        register_job_parser_agent(registry, body)
        register_cv_parser_agent(registry, body)
        self.assertTrue(registry.is_registered("cv-parser-agent"))
        self.assertTrue(registry.is_registered("job-parser-agent"))

    def test_pipeline_registers_both_agents(self):
        from agents.runtime.pipeline import ensure_reference_agent

        registry, body = ensure_reference_agent()
        self.assertTrue(registry.is_registered("cv-parser-agent"))
        self.assertTrue(registry.is_registered("job-parser-agent"))


@unittest.skipUnless(JOBSEARCH_CLI.is_file(),
                     "jobsearch parser CLI not available")
class TestParserCliIntegration(unittest.TestCase):
    PDF_FIXTURE = Path(
        r"C:\Users\DCI-Student\projekte\mays-jobsearch\docs\reports\assets"
        r"\CV-BUILDER-PDF-EXPORT-FIX-01\template-classic.pdf")

    def test_real_cli_parses_job(self):
        job = parse_via_node(
            "parse.job",
            {"job": {"title": "Python Engineer",
                     "descriptionPlain": "Must have 5+ years experience."}},
            cli=str(JOBSEARCH_CLI))
        self.assertEqual("parse.job", job.capability)
        self.assertGreaterEqual(job.data.get("stableId") is not None, True)

    @unittest.skipUnless(PDF_FIXTURE.is_file(), "CV PDF fixture not available")
    def test_real_cli_parses_cv_pdf(self):
        import base64

        pdf = base64.b64encode(self.PDF_FIXTURE.read_bytes()).decode("ascii")
        cv = parse_via_node("parse.cv", {"pdfBase64": pdf},
                             cli=str(JOBSEARCH_CLI))
        self.assertEqual("parse.cv", cv.capability)
        self.assertTrue(any("aws" in str(skill).lower()
                            for skill in cv.data.get("cvTags", [])))


if __name__ == "__main__":
    unittest.main()
