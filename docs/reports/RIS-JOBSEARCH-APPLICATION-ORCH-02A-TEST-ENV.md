# RIS-JOBSEARCH-APPLICATION-ORCH-02A — Test Environment

## Result: PASS with manifest limitation

An isolated environment was created outside the repository:

`C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-orch02-py314`

Interpreter: Python 3.14.10. Installed test/runtime dependencies:

- pytest 9.2.0
- pytest-cov 7.1.0
- boto3 1.43.123
- botocore 1.43.123
- moto 5.2.5

The complete `requirements.txt` installation is not currently possible on
Python 3.14 because its optional `types-all>=2024.1.0` constraint has no
matching PyPI release. No project manifest was changed and no global Python,
AWS profile, credential, or endpoint configuration was changed. The available
runtime/test dependencies were installed directly into the isolated venv.

## Gate evidence

- Previously skipped repository/E2E Moto tests: **11 passed**.
- Full ApplicationV1 selection after enabling Moto: **43 passed**.
- No ApplicationV1 test remained skipped.
- No AWS access or deployment was used.

The optional typing/tooling constraint is an environment reproducibility
follow-up, not a blocker for the runtime test gate.
