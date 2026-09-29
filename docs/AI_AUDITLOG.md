==================================================
==================================================
EXECUTION LOG / CRASH RECOVERY — MANDATORY template
==================================================

Maintain a current execution log throughout the audit:

docs/reports/[NO. OF TASK ++]-[SUBWORKING NO.]-[TASK]-EXECUTION_LOG.md

This is mandatory even though the audit is READ-ONLY.

The execution log must be created or updated continuously after
meaningful audit milestones, NOT only at the end.

The log must preserve the latest verified state so that work can be
resumed safely after an agent crash, terminal failure, streaming
failure, IDE restart, or interrupted session.

Record only verified facts. Never invent findings or validation results.

The execution log must contain:

- current status
- audit date/time
- current Git branch and HEAD
- audit scope
- completed audit sections
- actual findings
- evidence / file references
- GREEN / YELLOW / ORANGE / RED / GRAY classification
- Terraform checks actually executed and their results
- Git status
- files changed, if any
- explicit confirmation when no files were changed
- open questions
- risks
- recommended next actions
- current resume point

After each major section, update the execution log before continuing.

At the end, finalize the log with the complete audit summary.

IMPORTANT:
The execution log itself is part of the audit workflow and must be
kept accurate even if the audit remains completely read-only.

==================================================
==================================================

==================================================
BLANK CHECKPOINT TEMPLATE (Mandatory-Felder, für nächstes Audit kopieren)
==================================================

CHECKPOINT: YYYY-MM-DD HH:MM UTC — [THEMA] (Branch: [branch], HEAD: [sha])

- Current status: [...]
- Audit date/time: [...]
- Current Git branch and HEAD: [...]
- Audit scope: [...]
- Completed audit sections: [...]
- Actual findings (nur verifizierte Fakten): [...]
- Evidence / file references: [...]
- Classification: GREEN / YELLOW / ORANGE / RED / GRAY
- Terraform checks actually executed and their results: [...]
- Git status: [...]
- Files changed, if any: [...]
- Explicit confirmation when no files were changed: [...]
- Open questions: [...]
- Risks: [...]
- Recommended next actions: [...]
- Current resume point: [...]

==================================================
