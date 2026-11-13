# Structured CV Release Approval Sheet

**Status:** PREPARED FOR HUMAN APPROVAL — **NO APPROVAL GIVEN**

**Reference:** `docs/privacy/STRUCTURED-CV-PRODUCTION-APPROVAL-PACKAGE.md`

**Purpose:** `cv-builder-profile-storage`

**Notice:** `structured-cv-profile-storage-2026-11-12-draft-1` — DRAFT;

**Legal approval ref:** none.

## Decision sheet

| # | Decision | Proposed option | Human owner | Evidence required | Approved? |
|---|---|---|---|---|---|
| P1 | Art. 6 basis | Explicit consent lead option; legal alternative review | Privacy/Legal | Signed decision memo | NO |
| P2 | Art. 9 basis | Explicit Art. 9 consent, minimization review | Privacy/Legal | Art. 9 assessment | NO |
| P3 | Controller/processor/DPA | DPA and role matrix | Legal/Procurement | Signed DPA/roles | NO |
| P4 | Notice text/version | Candidate in production package | Privacy/Legal/Product | Approved text, version, SHA-256, legal ref | NO |
| P5 | Active retention | Until delete/erasure | Privacy/Ops | Retention schedule | NO |
| P6 | Withdrawal writes | Block immediately | Privacy/Legal | Policy decision | NO |
| P7 | Withdrawal read/export | Grace-period proposal only | Privacy/Legal | Policy + UX | NO |
| P8 | Withdrawal deletion | Delete after approved grace | Privacy/Ops | Policy/runbook | NO |
| P9 | Regrant | Never restores deleted data | Privacy/Product | UX/policy | NO |
| P10 | Export/delete after withdrawal | Define before activation | Privacy/Legal | Decision + tests | NO |
| P11 | Backup/PITR | PITR + restore reconciliation | Ops/Privacy | Restore test | NO |
| P12 | Consent activation | Separate gate after P1-P11 | Release Owner + Privacy | Flags/notice/consent evidence | NO |

## Mandatory human statements

- [ ] The notice text and legal approval reference are approved.
- [ ] Art. 6 and Art. 9 processing is approved for this purpose.
- [ ] Controller/processor/DPA roles are confirmed.
- [ ] Retention, withdrawal, export and erasure policy is approved.
- [ ] Backup/PITR and post-restore reconciliation is approved.
- [ ] Synthetic test identities and activation window are approved.

No agent may check these boxes or activate the notice/consent/feature.

## Explicit non-equivalences

- structured-CV storage is not PDF storage;
- structured-CV storage is not AI processing;
- existing PDF/application/search-profile consent does not authorize this
  purpose;
- a passing technical test is not a legal approval.
