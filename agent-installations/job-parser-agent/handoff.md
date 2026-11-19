# Job Parser Agent — Handoff

- **Status:** LOCAL VERIFIED (16 parser/adapter tests, real jobsearch CLI).
  LIVE enablement is PENDING because the Python Lambda has no node runtime.
- **Package:** `agent-installations/job-parser-agent`.
- **Source:** `agents/job_parser_agent`, adapter `agents/parsers/node_adapter.py`.
- **Shared library:** `maynowak/mays-jobsearch`, branch
  `feature/ris-parser-library-01`, commit `d330179`, version `1.0.0`.
- **No catalog row:** dispatch-only. Adding one is a reviewed Terraform change.
- **No partner surface:** no external partner references for this agent.
- **Next step:** decide the Node invocation path, then run one synthetic
  canary and add the entitlement.
- **Stop conditions:** missing parser CLI, missing node, schema-version
  mismatch, or any request to add a second parser engine.
