# RIS-R08-PR-08F — GitHub Handoff

Existing PR query: no PR returned by the unauthenticated GitHub API. `gh` is
not installed and `GITHUB_TOKEN`/`GH_TOKEN` are absent. The feature ref is not
present on origin. No push, PR creation, check query, or merge was attempted.

Safe handoff command sequence for an authorized maintainer:

```text
git push origin feature/ris-privacy-r08-gate-b-orchestration-01
gh pr create --base main --head feature/ris-privacy-r08-gate-b-orchestration-01
gh pr checks
```

Before execution, the maintainer must install/authenticate GitHub tooling,
review the 29 documented local environment failures, and preserve the
NO-GO/production-blocked gates. No workflow on a feature push performs Apply;
the workflow's deploy condition is `github.ref == refs/heads/prod`, while its
push trigger is restricted to `main`.
