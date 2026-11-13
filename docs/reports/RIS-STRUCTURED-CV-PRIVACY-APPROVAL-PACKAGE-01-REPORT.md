# RIS-STRUCTURED-CV-PRIVACY-APPROVAL-PACKAGE-01

**Status:** `PRIVACY PACKAGE READY / HUMAN LEGAL APPROVAL REQUIRED`

**Date:** 2026-11-13

**Branch:** `feature/ris-structured-cv-privacy-approval-package-01`

**Baseline:** `0e08822`

## Result

Created the decision package
`docs/privacy/STRUCTURED-CV-PRODUCTION-APPROVAL-PACKAGE.md` for the separate
purpose `cv-builder-profile-storage`.

It covers Art. 6/Art. 9 questions, controller/processor roles, data
minimization, a DRAFT German notice candidate, retention/withdrawal proposals,
data-subject rights, backups/PITR limits and an approval matrix.

The notice remains `structured-cv-profile-storage-2026-11-12-draft-1`, state
`DRAFT`, `legalApprovalRef: null`. No approval, activation, grant or withdrawal
was performed.

## Key open decisions

- final Art. 6/Art. 9 basis and whether free-text Art. 9 data can be avoided;
- controller/processor/DPA role and AWS sub-processor confirmation;
- final notice text, version, hash and legal approval reference;
- active retention, withdrawal grace (30 days is proposal only), read/export
  after withdrawal and regrant behavior;
- PITR/backup retention and restore reconciliation;
- Release Owner approval for consent/feature activation.

## Evidence boundary

This is a documentation-only package. No legal conclusion is claimed, no RIS
deployment or AWS operation occurred, and no real CV data was used.

## Commit

Committed on `feature/ris-structured-cv-privacy-approval-package-01`.
