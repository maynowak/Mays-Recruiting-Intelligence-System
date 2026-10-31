# Legal & Transparency Matrix (R08-G0)

Status: **REVIEW REQUIRED** for every legal conclusion. This is a technical
gap analysis, not legal advice and not a claim of GDPR compliance.

| GDPR article | Topic | Current RIS state | Evidence/status | Required decision |
|---|---|---|---|---|
| Art. 5 | Principles, accountability | Data minimization in receipts/cursor; retention gaps; no deletion ledger | **PARTIAL** | Retention policy, accountability record |
| Art. 6 | Lawfulness | No final legal basis per purpose | **REVIEW REQUIRED** | Legal basis per processing purpose |
| Art. 7 | Consent | Receipt contract can record notice/consent events; no notice UI/version source | **GAP** | Notice wording/version, consent UX, legal validity |
| Art. 9 | Special categories | CVs may reveal health/other special data; no Art. 9 assessment | **REVIEW REQUIRED** | Art. 9 condition / DPIA decision |
| Art. 13/14 | Information duties | Privacy docs exist, but no served version/digest | **PARTIAL** | Publish notice, version/digest, timing |
| Art. 15 | Access | Orders export exists internally; RIS user export not implemented | **GAP** | `privacy.export`, user view |
| Art. 16 | Rectification | CRUD update paths exist; no privacy rectification workflow | **PARTIAL** | User flow and evidence |
| Art. 17 | Erasure | G5 erases some RIS data; partner profiles/S3 versions/Cognito/jobsearches/cursors missing | **GAP** | R08-C erasure lifecycle |
| Art. 18 | Restriction | No restriction state/flow | **GAP** | Restriction design |
| Art. 20 | Portability | No structured RIS user export | **GAP** | JSON export format |
| Art. 25 | Privacy by design | Identity binding, minimization, TTL, opaque cursors, least privilege | **PARTIAL** | Formal DPIA/privacy review |
| Art. 28 | Processors | AWS, Mays-Orders, Jobsearch, AI provider roles not fully contracted in code | **REVIEW REQUIRED** | DPA/processor mapping |
| Art. 30 | Processing register | Inventory exists; incomplete for R07 resources/cursor/backups | **PARTIAL** | Maintain register |
| Art. 32 | Security | Encryption, IAM, audit, opaque tokens | **PARTIAL** | Ongoing verification/incident process |
| Art. 35 | DPIA screening | No documented screening for CV/AI profiling | **REVIEW REQUIRED** | DPIA screening decision |

## Consent vs technical event

- A server-verified `CONSENT_GRANTED` receipt proves the server received a
  consent action for a notice version/digest.
- It does **not** prove the consent is legally valid, freely given, specific or
  informed. That remains a legal review/UX decision.
- A button click or general terms acceptance is not automatically consent.
- `AI_TRANSFER_CONFIRMED` requires third-party/server evidence; a browser event
  is at most `client_reported`.

## Release boundary

R08-G0 does **not** assert GDPR compliance. It supplies a contract and gap
list. A production privacy release needs legal review, notice publication,
retention decisions, processor agreements and the R08-A/B/C/D implementation.
