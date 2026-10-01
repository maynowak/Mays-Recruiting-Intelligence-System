"""Tests Gate 8: Installer-Projektmodell + Git-SHA-Pinning (Gate 8).

Offline (lokale file://-Repos als Remote-Ersatz):
Projektdefinition, Clone, SHA-Resolution, Pin-Persistenz,
Wiederholbarkeit, Projektisolation, Drift-Erkennung.
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from installer.orchestrator import RISInstaller


def run(*args, cwd=None):
    r = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"{args}: {r.stderr}"
    return r.stdout.strip()


def make_repo(path, filename="f.txt", content="v1"):
    os.makedirs(path, exist_ok=True)
    run("git", "init", "-q", cwd=path)
    run("git", "config", "user.email", "t@t.t", cwd=path)
    run("git", "config", "user.name", "t", cwd=path)
    with open(os.path.join(path, filename), "w") as fh:
        fh.write(content)
    run("git", "add", ".", cwd=path)
    run("git", "commit", "-qm", "init", cwd=path)
    return run("git", "rev-parse", "HEAD", cwd=path)


class TestProjectPinning(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp(prefix="gate8-pin-")
        self.repo_root = os.path.join(self.tmp, "ris")
        os.makedirs(os.path.join(self.repo_root, "installer", "projects"))
        self.remote = os.path.join(self.tmp, "remote.git")
        run("git", "init", "--bare", "-q", self.remote)
        work = os.path.join(self.tmp, "work")
        sha = make_repo(work)
        run("git", "push", "-q", self.remote, "HEAD:main", cwd=work)
        run("git", "symbolic-ref", "HEAD", "refs/heads/main", cwd=self.remote)
        self.remote_sha = run("git", "rev-parse", "HEAD", cwd=work)
        self.assertEqual(sha, self.remote_sha)
        self.inst = RISInstaller()
        self.inst.PROJECTS = dict(self.inst.PROJECTS)
        self.inst.PROJECTS["demo_proj"] = {
            "git_url": self.remote,
            "name": "Demo",
            "local_dir": "installer/projects/demo_proj",
            "kind": "reference",
        }

    def _clone(self):
        run("git", "clone", "-q", self.remote,
            os.path.join(self.repo_root, "installer", "projects", "demo_proj"))

    def test_definition_and_paths(self):
        from pathlib import Path
        local = self.inst.project_local_dir("demo_proj", repo_root=Path(self.repo_root))
        self.assertTrue(str(local).endswith("installer/projects/demo_proj"))
        pin = self.inst.pin_path("demo_proj", repo_root=Path(self.repo_root))
        self.assertTrue(str(pin).endswith("installer/demo-proj-clone.pinned.json"))
        self.assertNotIn("projects/demo", str(pin))

    def test_resolve_and_write_pin(self):
        from pathlib import Path
        self._clone()
        sha = self.inst.resolve_remote_sha(self.remote, "main")
        self.assertEqual(sha, self.remote_sha)
        path = self.inst.write_pin("demo_proj", "main", repo_root=Path(self.repo_root))
        record = json.loads(open(path).read())
        self.assertEqual(record["project"], "demo_proj")
        self.assertEqual(record["git_url"], self.remote)
        self.assertEqual(record["branch"], "main")
        self.assertEqual(record["pinned_commit"], self.remote_sha)
        self.assertEqual(record["clone_path"], "installer/projects/demo_proj")

    def test_verify_ok_and_drift(self):
        from pathlib import Path
        self._clone()
        self.inst.write_pin("demo_proj", "main", repo_root=Path(self.repo_root))
        self.assertTrue(self.inst.verify_pin("demo_proj", repo_root=Path(self.repo_root))["ok"])
        # Drift: neuer Commit im Clone -> verify False
        work = os.path.join(self.repo_root, "installer", "projects", "demo_proj")
        with open(os.path.join(work, "g.txt"), "w") as fh:
            fh.write("drift")
        run("git", "add", ".", cwd=work)
        run("git", "-c", "user.email=t@t.t", "-c", "user.name=t",
            "commit", "-qm", "drift", cwd=work)
        verdict = self.inst.verify_pin("demo_proj", repo_root=Path(self.repo_root))
        self.assertFalse(verdict["ok"])
        self.assertIn("Drift", verdict["reason"])

    def test_repeatability_and_isolation(self):
        from pathlib import Path
        self._clone()
        p1 = self.inst.write_pin("demo_proj", "main", repo_root=Path(self.repo_root))
        before = open(p1).read()
        p2 = self.inst.write_pin("demo_proj", "main", repo_root=Path(self.repo_root))
        after = open(p2).read()
        # Wiederholbar: gleicher SHA (Datum darf sich aendern, SHA nicht)
        self.assertEqual(json.loads(before)["pinned_commit"],
                         json.loads(after)["pinned_commit"])
        # Isolation: zweites Projekt unabhaengig
        self.inst.PROJECTS["demo_proj2"] = {
            "git_url": self.remote, "name": "Demo2",
            "local_dir": "installer/projects/demo_proj2", "kind": "reference",
        }
        run("git", "clone", "-q", self.remote,
            os.path.join(self.repo_root, "installer", "projects", "demo_proj2"))
        self.inst.write_pin("demo_proj2", "main", repo_root=Path(self.repo_root))
        self.assertTrue(self.inst.verify_pin("demo_proj", repo_root=Path(self.repo_root))["ok"])
        self.assertTrue(self.inst.verify_pin("demo_proj2", repo_root=Path(self.repo_root))["ok"])

    def test_unknown_project_rejected(self):
        from pathlib import Path
        with self.assertRaises(ValueError):
            self.inst.write_pin("unbekannt", repo_root=Path(self.repo_root))


if __name__ == "__main__":
    unittest.main()
