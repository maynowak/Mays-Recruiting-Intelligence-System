# Analysis Agent Contracts

- Request `1.0`: `schemaVersion`, `requestedResults`, `input.cv|job|profile`,
  optional `idempotencyKey`.
- Results: `CVParserResultBody 1.0`, `JobParserResultBody 1.0`,
  `ATSAnalysisResultBody 2.0` (additive `atsTags`), `ComparisonResultBody 1.0`.
- Canonical contract and examples:
  `docs/reports/RIS-AGENT-ANALYSIS-ORCHESTRATION-04.md`.
