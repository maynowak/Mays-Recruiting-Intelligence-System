# Analysis Agent — Handoff

- **Status:** LOCAL VERIFIED (25 pipeline tests); LIVE PENDING (Node runtime).
- **Requests:** `cv.tags`, `job.tags`, `ats.tags`, `comparison`.
- **Jobsearch CLI:** branch `feature/ris-analysis-parser-cli-04` @ `40a5db2`.
- **CV bridge:** RIS documents S3; structured data skips parsing.
- **Temporary job store:** 2h default, 4h maximum, 1 MiB, opaque refs.
- **Next:** approve the Node execution path, apply the job-bucket plan and run a
  synthetic canary before LIVE VERIFIED.
