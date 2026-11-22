# Job Parser Package Tests

The contract is covered in `tests/test_parser_agents.py`:

- adapter validation, size limit and error mapping;
- job agent success, missing job/title, retryable runtime failure;
- registry/discovery routes and idempotent registration;
- real jobsearch CLI integration (skipped when the CLI is not present).

Run: `python -m pytest tests/test_parser_agents.py -q`.
