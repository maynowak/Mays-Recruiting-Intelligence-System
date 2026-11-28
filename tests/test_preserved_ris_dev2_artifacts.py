"""Contracts for the RIS-DEV2-only preserved Lambda artifact inputs."""

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TERRAFORM = ROOT / "terraform"
OVERRIDES = TERRAFORM / "ris-dev2-19g2-artifact-overrides.tfvars.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_19g2_override_paths_are_terraform_inputs_and_match_preserved_hashes():
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    assert set(overrides) == {"analysis_lambda_zip_path", "filename"}

    assert overrides["analysis_lambda_zip_path"] == "analysis-lambda.zip"
    assert overrides["filename"] == "../lambda/dist/orders-reader.zip"
    analysis = TERRAFORM / "artifacts" / (
        "ris-dev2-analysis-276b4e4420272167dd32c590d6dbabed4008724a7091e4d86504d5444fe26b10.zip"
    )
    reader = TERRAFORM / "artifacts" / (
        "ris-dev2-orders-reader-610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b.zip"
    )
    assert _sha256(analysis) == (
        "276b4e4420272167dd32c590d6dbabed4008724a7091e4d86504d5444fe26b10"
    )
    assert _sha256(reader) == (
        "610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b"
    )

    root = (TERRAFORM / "main.tf").read_text(encoding="utf-8")
    analysis_module = root.split('module "analysis_runtime"', 1)[1].split("\n}", 1)[0]
    reader_module = root.split('module "orders_reader"', 1)[1].split("\n}", 1)[0]
    assert "analysis_zip_path       = local.analysis_artifact_filename" in analysis_module
    assert "filename          = local.reader_artifact_filename" in reader_module
    assert 'abspath("${path.root}/${var.analysis_lambda_zip_path}")' in root
    assert 'abspath("${path.root}/${var.filename}")' in root
    assert 'replace(local.reader_artifact_path, "/", "\\\\")' in root

    analysis_resource = (
        TERRAFORM / "modules" / "analysis_runtime" / "main.tf"
    ).read_text(encoding="utf-8")
    reader_resource = (
        TERRAFORM / "modules" / "orders_reader" / "main.tf"
    ).read_text(encoding="utf-8")
    assert "filebase64sha256(var.analysis_zip_path)" in analysis_resource
    assert "filebase64sha256(var.filename)" in reader_resource


def test_preserved_reader_members_match_current_source_after_line_ending_normalization():
    reader = TERRAFORM / "artifacts" / (
        "ris-dev2-orders-reader-610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b.zip"
    )
    members = {
        "worker_authorization.py": ROOT / "agents/ecosystem/worker_authorization.py",
        "agent_order.py": ROOT / "agents/orders/agent_order.py",
        "order_transport.py": ROOT / "agents/transport/order_transport.py",
        "orders_reader.py": ROOT / "lambda/orders_reader.py",
    }
    with zipfile.ZipFile(reader) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == list(members)
        for name, source in members.items():
            packaged = archive.read(name).replace(b"\r\n", b"\n")
            current = source.read_bytes().replace(b"\r\n", b"\n")
            assert packaged == current, name
