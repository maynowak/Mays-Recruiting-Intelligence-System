"""R08-POLICY-01 documentation guardrails; no AWS or production writes."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVACY = ROOT / "docs" / "privacy"
REPORT = ROOT / "docs" / "reports" / "RIS-R08-POLICY-01-PRIVACY-DECISION-GATE.md"


def read(path):
    return path.read_text(encoding="utf-8")


def test_policy_documents_are_present_and_not_approvals():
    for name in (
        "RIS-JOBSEARCH-PROCESSING-PURPOSES-V1.md",
        "RIS-JOBSEARCH-RETENTION-POLICY-V1.md",
        "RIS-JOBSEARCH-PRIVACY-NOTICE-DRAFT-V1.md",
        "RIS-PRIVACY-RECEIPT-RETENTION-DECISION.md",
    ):
        text = read(PRIVACY / name)
        assert ("REVIEW_REQUIRED" in text or "BLOCKED" in text
                or "nicht juristisch freigegeben" in text)
    assert "nicht juristisch freigegeben" in read(
        PRIVACY / "RIS-JOBSEARCH-PRIVACY-NOTICE-DRAFT-V1.md")


def test_all_ten_processing_purposes_are_documented():
    text = read(PRIVACY / "RIS-JOBSEARCH-PROCESSING-PURPOSES-V1.md")
    for number in range(1, 11):
        assert f"P-{number:02d}" in text


def test_retention_matrix_covers_required_resources():
    text = read(PRIVACY / "RIS-JOBSEARCH-RETENTION-POLICY-V1.md")
    for term in (
        "UserProfile", "CVDocument metadata", "S3 PDF", "S3 versions",
        "ManualSearchProfile", "CVSearchProfile", "ATSSearchProfile",
        "PrivacyReceiptV1", "Idempotency records", "Cursor records",
        "Capacity counters", "Lifecycle guards", "Logs / CloudTrail",
        "Backups/PITR",
    ):
        assert term in text


def test_receipt_policy_and_report_keep_writes_blocked():
    receipt = read(PRIVACY / "RIS-PRIVACY-RECEIPT-RETENTION-DECISION.md")
    report = read(REPORT)
    assert "PRIVACY_RECEIPT_JOURNAL_ENABLED=false" in receipt
    assert "PRODUCTION BLOCKED" in report
    assert "R08-A2 policy enablement" in report
    assert "BLOCKED / REVIEW_REQUIRED" in report


def test_policy_documents_do_not_contain_real_secret_markers():
    corpus = "\n".join(read(path) for path in PRIVACY.glob("RIS-JOBSEARCH-*.md"))
    assert "AKIA" not in corpus
    assert "BEGIN PRIVATE KEY" not in corpus
    assert "ris_" not in corpus
