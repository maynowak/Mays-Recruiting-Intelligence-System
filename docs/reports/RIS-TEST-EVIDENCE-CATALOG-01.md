# Mays-RIS Test Evidence Catalog

## 1. Executive Summary
Canonical test inventory and evidence for Mays-Recruiting-Intelligence-System PXX baseline.

## 2. Baseline
- branch: main
- HEAD: c0a5f66
- command: python3 -m pytest tests/ -q
- timestamp: 2026-10-07
- collected: 1054
- passed: 1046
- failed: 0
- skipped: 8

## 3. Test Inventory Summary
Total test files: 54
Total collected: 1054
Passed: 1046
Skipped: 8
Failed: 0

## 4. Domain Classification
See per-file matrix in test-evidence.

## 5. Complete Per-File Test Matrix
See docs/reports/test-evidence/pytest-collection.txt and pytest-baseline.txt

## 6. P / Gate / Contract Traceability
- P17: tests/test_p17_credential_lifecycle.py
- P20: tests/test_p20_api_contract_consistency.py, tests/test_p20_health_contract.py
- P21: tests/test_p21_cognito_m2m_boundary.py
- P22: tests/test_p22_agent_capability_contract.py
- P23: tests/test_p23_offer_product_admin.py

## 7. Skip / Live Integration Evidence
8 integration-conditional skips documented in PXX-PHASE2-SKIPPED-TEST-AUDIT-01.md

## 8. Report Evidence Index
See docs/reports/

## 9. Test Evidence Gap Matrix
Live Observability tests require AWS credentials. No live evidence without credentials.

## 10. Baseline Interpretation
1046 passed = all executed tests successful. 8 skipped = live integration tests intentionally skipped.

## 11. Reproduction Commands
python3 -m pytest tests/ --collect-only -q
python3 -m pytest tests/ -q -rs

## 12. Conclusion
Baseline GREEN.
