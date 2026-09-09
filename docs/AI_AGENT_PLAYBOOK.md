# AI Agent Playbook — Ground Zero

This playbook defines how AI coding agents must work on the Ground Zero project.

## Execution Lifecycle

```
START
  ↓
ANALYSIS
  ↓
DESIGN
  ↓
DOCUMENT
  ↓
IMPLEMENT
  ↓
TEST
  ↓
REPORT
  ↓
STOP
```

## 1. ANALYSIS

Before working:

- [ ] Review existing documentation
- [ ] Check Git status (`git status`, `git log --oneline`)
- [ ] Verify branch context
- [ ] Identify task requirements
- [ ] Locate relevant files

**Mandatory**: Understand what exists before making changes.

## 2. DESIGN

Define the approach:

```text
- What needs to change?
- Where should it go?
- What are the dependencies?
- What could go wrong?
- How to verify?
```

**Mandatory**: Design before implementation.

## 3. DOCUMENT

Documentation is part of implementation.

- [ ] Update relevant docs
- [ ] Record decisions
- [ ] Maintain architecture docs
- [ ] Update status reports

**Mandatory**: Document every change.

## 4. IMPLEMENT

Actual coding changes.

**Rules**:

- Make minimal, focused changes
- Follow existing patterns
- Use project conventions
- Replace placeholder code

## 5. TEST

Validation before reporting:

- [ ] Syntax check (Python, Terraform)
- [ ] Unit tests (if applicable)
- [ ] Integration tests (if applicable)
- [ ] Git diff review
- [ ] Documentation accuracy

**Mandatory**: Verify before committing.

## 6. REPORT

Update execution log with:

- what changed
- why changed
- validation results
- any issues
- next verification points

**Mandatory**: Report every significant change.

## 7. STOP

Explicit boundaries:

- STOP after declared task completion
- DON'T start next task without permission
- DON'T implement uncommitted features
- DON'T deploy without approval

## Crash Recovery

After interruption:

1. Check `git status`
2. Read latest report in `docs/reports/`
3. Resume from last verified state
4. Do not repeat verified work
5. Document recovery point

## Git Discipline

```bash
# Before starting
git status
git pull

# After changes
git diff --check
git add <files>
git commit -m "descriptive message"
```

## Evidence-Based Reporting

Never claim:

- "Implemented successfully" without test
- "File exists" without checking
- "Status is X" without verification
- "No changes" without git diff

Always verify:

```bash
git diff
terraform validate
python -m py_compile
```

## Execution Log Updates

The log (`docs/reports/TASK-EXECUTION.md` or similar) must be updated:

1. After every meaningful step
2. With verified facts only
3. With resume point

Format:

| Step | Status | Evidence |
|------|--------|----------|
| ... | ... | ... |

## Deployment Governance

Terraform deployment requires:

1. `terraform plan` reviewed
2. State bucket exists
3. IAM roles verified
4. Resource costs checked
5. Production requires approval

**NEVER** run `terraform apply` without:

- [ ] State infrastructure ready
- [ ] Plan reviewed
- [ ] Cost analysis
- [ ] Security check
- [ ] Human approval (prod)

## Quality Gates

| Check | Tool | Expected |
|-------|------|----------|
| Format | terraform fmt | No changes |
| Lint | python -m flake8 | Clean |
| Validate | terraform validate | Success |
| Diff | git diff | Intended changes only |
| Status | git status | Clean staging |

## Final Commit

When complete:

```bash
git add .
git commit -m "task: brief description"
```

Message must describe the actual change.

---

**Remember**: The goal is a working, documented system. Good documentation is as important as working code.