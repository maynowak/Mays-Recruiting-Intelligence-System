# CV Parser Contracts

- Parser envelope: `schemaVersion 1.0`, `capability parse.cv`,
  `parserVersion`, `data`, `confidence`.
- Input: `payload.text` (20..100000 characters).
- Output fields (compatible with the existing job-search profile):
  `name`, `email`, `phone`, `skills`, `experienceLevel`, `targetRoles`,
  `location`, plus `summary`, `education`, `languages`, `experience`,
  `totalYears`, `stableId`.
- Canonical implementation: `maynowak/mays-jobsearch` →
  `api/_lib/parsers/ris.mjs` v1.0.0 (CLI `scripts/ris-parser-cli.mjs`).
