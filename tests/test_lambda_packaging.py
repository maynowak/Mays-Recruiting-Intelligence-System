"""Tests Packaging-Lifecycle (Gate LIFECYCLE-01, Matrix A–H).

A–D/F/G lokal (deterministisch, ohne AWS). E/H lesen Live-State
(Ueberspringen ohne mayaws-Credentials, CI-sicher).
"""

import hashlib
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "lambda"))

from build_zip import (  # noqa: E402
    ALLOWED_SUFFIXES,
    build_agent_bundle,
    build_reader_bundle,
)

ACCOUNT = "240571105849"


def _live():
    import boto3
    profile = os.environ.get("AWS_PROFILE")
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    try:
        ident = session.client("sts", region_name="eu-central-1").get_caller_identity()
        return session if ident.get("Account") == ACCOUNT else None
    except Exception:
        return None


def _names(zip_path):
    with zipfile.ZipFile(zip_path) as archive:
        return archive.namelist()


class TestPackage(unittest.TestCase):
    def test_a_clean_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "agent.zip")
            import build_zip
            files = build_zip._collect(__import__("pathlib").Path(REPO_ROOT),
                                       ["lambda/handler.py", "agents", "jobsearch"])
            info = build_zip.build_bundle(
                __import__("pathlib").Path(REPO_ROOT), files,
                lambda s: "handler.py" if s == "lambda/handler.py" else s, out)
            self.assertTrue(os.path.exists(out))
            self.assertGreater(info["files"], 30)

    def test_b_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            import build_zip
            from pathlib import Path
            build_zip.build_bundle(
                Path(REPO_ROOT), ["lambda/orders_reader.py"],
                lambda s: "orders_reader.py",
                os.path.join(tmp, "reader.zip"))
            names = _names(os.path.join(tmp, "reader.zip"))
            self.assertEqual(names, ["orders_reader.py"])

    def test_c_exclusions(self):
        names = _names(os.path.join(REPO_ROOT, "terraform", "lambda.zip"))
        for name in names:
            self.assertTrue(name.endswith(".py"), name)
            for banned in ("__pycache__", ".git/", ".pyc", ".md", ".yaml", ".json"):
                self.assertNotIn(banned, name)
        self.assertIn("handler.py", names)
        self.assertIn("agents/runtime/pipeline.py", names)

    def test_d_reproducibility(self):
        import build_zip
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            o1 = os.path.join(t1, "a.zip")
            o2 = os.path.join(t2, "a.zip")
            files = build_zip._collect(Path(REPO_ROOT),
                                       ["lambda/handler.py", "agents", "jobsearch"])
            arc = lambda s: "handler.py" if s == "lambda/handler.py" else s
            h1 = build_zip.build_bundle(Path(REPO_ROOT), files, arc, o1)["sha256"]
            h2 = build_zip.build_bundle(Path(REPO_ROOT), files, arc, o2)["sha256"]
            self.assertEqual(h1, h2)


class TestSourceChange(unittest.TestCase):
    def test_f_change_detected_and_g_restored_noop(self):
        import build_zip
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            mirror = os.path.join(tmp, "repo")
            shutil.copytree(REPO_ROOT, mirror,
                            ignore=shutil.ignore_patterns(".git", "__pycache__",
                                                          ".terraform", ".pytest_cache",
                                                          "installer/projects",
                                                          "node_modules", ".venv"))
            files = build_zip._collect(Path(mirror),
                                       ["lambda/handler.py", "agents", "jobsearch"])
            arc = lambda s: "handler.py" if s == "lambda/handler.py" else s
            base = build_zip.build_bundle(
                Path(mirror), files, arc, os.path.join(tmp, "base.zip"))["sha256"]
            with open(os.path.join(mirror, "lambda", "handler.py"), "a") as fh:
                fh.write("\n# lifecycle-test: temporaere Aenderung\n")
            changed = build_zip.build_bundle(
                Path(mirror), files, arc, os.path.join(tmp, "changed.zip"))["sha256"]
            self.assertNotEqual(base, changed, "Source-Aenderung muss Hash aendern")
            with open(os.path.join(mirror, "lambda", "handler.py")) as fh:
                content = fh.read()
            with open(os.path.join(mirror, "lambda", "handler.py"), "w") as fh:
                fh.write(content.replace("\n# lifecycle-test: temporaere Aenderung\n", ""))
            restored = build_zip.build_bundle(
                Path(mirror), files, arc, os.path.join(tmp, "restored.zip"))["sha256"]
            self.assertEqual(base, restored, "Restore muss Hash zuruecksetzen")


class TestLiveContract(unittest.TestCase):
    def test_e_noop_live_hash_matches(self):
        """Gleiche Quelle -> gleicher Hash wie Live-State (kein TF-Delta)."""
        session = _live()
        if session is None:
            raise unittest.SkipTest("keine mayaws-Credentials")
        import build_zip
        from pathlib import Path
        files = build_zip._collect(Path(REPO_ROOT),
                                   ["lambda/handler.py", "agents", "jobsearch"])
        arc = lambda s: "handler.py" if s == "lambda/handler.py" else s
        with tempfile.TemporaryDirectory() as tmp:
            local = build_zip.build_bundle(
                Path(REPO_ROOT), files, arc,
                os.path.join(tmp, "live-check.zip"))["sha256"]
        tf = session.client("lambda", region_name="eu-central-1")
        live_sha = tf.get_function_configuration(
            FunctionName="mays-ris-dev-agent")["CodeSha256"]
        import base64
        self.assertEqual(base64.b64decode(live_sha).hex(),
                         local,
                         "Live-Code muss kanonischem Build entsprechen")

    def test_h_reader_hash_matches(self):
        session = _live()
        if session is None:
            raise unittest.SkipTest("keine mayaws-Credentials")
        info = build_reader_bundle(REPO_ROOT)
        tf = session.client("lambda", region_name="eu-central-1")
        live_sha = tf.get_function_configuration(
            FunctionName="mays-ris-dev-orders-reader")["CodeSha256"]
        import base64
        self.assertEqual(base64.b64decode(live_sha).hex(), info["sha256"])


if __name__ == "__main__":
    unittest.main()
