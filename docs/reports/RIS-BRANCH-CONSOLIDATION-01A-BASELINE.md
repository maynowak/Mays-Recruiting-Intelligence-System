# RIS-BRANCH-CONSOLIDATION-01A — Repository and Branch Baseline

## Initial checkpoint

The consolidation started from a clean working tree at:

```text
Repository: C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-application-persistence-v1
Branch: feature/ris-application-persistence-v1
HEAD: 65a4b9a95732f5de0c4ec0192ba6af54cc277a41
```

No untracked files or pre-existing modifications were present. Existing
worktrees and branches were preserved; no reset, clean or stash was used.

## Remote and branch status

```text
origin: https://github.com/maynowak/Mays-Recruiting-Intelligence-System.git
origin/main after fetch: 26b36604204ff9822d66646a6a64c8f429025698
```

The working branch has no remote tracking branch yet. `git ls-remote` found no
`origin/feature/ris-application-persistence-v1` branch. The branch is 77
commits ahead of the fetched `origin/main`, while `origin/main` is 6 commits
ahead due to later upstream commits. The complete ahead commit list and
three-way diff were captured with the requested Git baseline commands.

The current worktree is one of several local worktrees. Other team branches,
including `feature/ris-partner-profile-persistence-v1` and
`feature/ris-dev2-mo-rc4-upgrade-e2e-01`, were not checked out, rewritten or
removed.

## Main-content comparison

`origin/main` already contains the merged partner-profile development from
`feature/ris-partner-profile-persistence-v1` (merge commit `d3e8fbf`). It also
contains the profile-related Terraform and API groundwork.

The current development branch still contains changes not present in
`origin/main`, including:

- `jobsearch/application_contract.py`;
- `jobsearch/application_repository.py`;
- ApplicationV1 handler/API/Terraform/table/IAM changes;
- ApplicationV1 tests, contracts and privacy/erasure integration;
- the later RIS-DEV2 packaging and deployment-gate reports.

The key ApplicationV1 paths are absent from `origin/main`; they remain local
branch changes and are the principal consolidation payload. The branch also
contains documentation and runtime changes from earlier RIS phases; no claim
is made that all 77 commits are independent feature commits.

## Safety findings

- No AWS or Terraform mutation was performed.
- No `main` checkout or direct push was performed.
- The Mays-Orders builder clone remains a separate ignored project boundary.
- Jobsearch files were inspected read-only and were not changed.
