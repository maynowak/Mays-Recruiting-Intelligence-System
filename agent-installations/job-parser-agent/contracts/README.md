# Job Parser Contracts

- Parser envelope: `schemaVersion 1.0`, `capability parse.job`,
  `parserVersion`, `data`, `confidence`.
- Input: `payload.job` with `title` or `descriptionPlain`; description max
  100000 characters.
- Output: `stableId` (SHA-256), `title`, `company`, `location`, `language`,
  `requirements.required`, `requirements.preferred`, `skills`,
  `experienceYears`, `metadata`.
- Canonical implementation: `maynowak/mays-jobsearch` →
  `api/_lib/parsers/ris.mjs` v1.0.0 (CLI `scripts/ris-parser-cli.mjs`), reusing
  `api/_lib/ats.mjs`.
