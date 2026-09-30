# PROJECT-STACK-ISOLATION-CHECK-01

STATUS: GREEN

| Feld | Wert |
|---|---|
| Date/Time | 2026-09-30 11:00 UTC |
| Branch + HEAD | main, 0b8ecf7 |
| Scope | Multi-Projekt-Fähigkeit MO + RIS (Muster aus AI_AUDITLOG.md); kein Umbau, kein AWS-Kontakt über Profil-Checks hinaus (read-only) |
| Classification | GREEN |
| Terraform Checks | KEINE E2E; lokale Ableitung + Unit-Tests (22/22); `diff --check` PASS |
| Git Status | 0 modified, 8 untracked (unberührt); AI_AUDITLOG Template-only |
| Files Changed | nur Report + Execution-Log |
| AWS Mutation | NONE (kein init/plan/apply; nur lesende Profil-Checks aus Vor-Gate) |

## Kernsatz (User-Vorgabe bestätigt)

| Aussage | Beleg | Status |
|---|---|---|
| Profil (z. B. mayaws) ist projektunabhängig nutzbar | Trennung erfolgt über project_name/Workspace/Vars, NICHT über Credentials (beide Repos) | PROVEN (Mechanismus) |
| Mays-Orders mit anderem Projektnamen installierbar | Auto-Ableitung (context.py:86-90) + Tag-Policy (validate-plan.py:88-95) + getestete Parallelläufe (09-01/09-02, je 37 Ressourcen) | PROVEN (Code + Tests) |
| Mays-RIS mit anderem Projektnamen installierbar | Workspace-Ableitung + -Vars + Namens-/Tag-Trennung (live verifiziert, s. unten) | PROVEN (Mechanismus) |
| Stacks werden getrennt gehandhabt | Je Projekt: Workspace + Vars + Namen + Tags (s. Matrix) | PROVEN (Mechanismus) |

## Live-Nachweis RIS (kein AWS-Kontakt, reine Ableitung)

| Projekt A (`mays-ris`) | Projekt B (`mays-ris-test`) | Getrennt |
|---|---|---|
| Workspace `mays-ris` | Workspace `mays-ris-test` | JA (distinct, live) |
| Vars `{mays-ris, dev}` | Vars `{mays-ris-test, dev}` | JA (live) |
| Runner-Workspace A/B | Runner-Workspace B | JA (live) |
| Ressourcen `mays-ris-dev-*` | Ressourcen `mays-ris-test-dev-*` | JA (Namens-Prefix, Code) |
| Tag `Project=mays-ris` | Tag `Project=mays-ris-test` | JA (Code) |

## Stack-Trennungs-Matrix (RIS)

| Schicht | Mechanismus | Beleg | Live-Status |
|---|---|---|---|
| Workspace | `workspace_for_project()` (Identität) + Runner select/new | runner.py + Live-Check + Tests | Mechanismus PROVEN |
| State | Gleicher Key, Workspace-Trennung (S3-Default-Verhalten, unbelegt als Code-Fakt) | main.tf:Key-Literal; kein Prefix im Vertrag | UNVERIFIED (live) |
| Namen | `${project_name}-${environment}-*` + `local.prefix` | main.tf:24 + Modul-Namen | PROVEN (Code) |
| Tags | `Project = var.project_name` | main.tf:33/113/158 | PROVEN (Code) |
| Vars | project_name/environment je Call | Live-Check + Tests | PROVEN |
| Credentials | Profil-agnostisch (keine Projekt-Bindung) | Kein Projekt-Bezug im Code | PROVEN (Negativ) |

## MO-Referenz (belastbar, nichts kopiert)

| Muster | MO-Beleg | RIS-Entsprechung |
|---|---|---|
| Workspace-Auto-Ableitung | context.py:86-90 + Env-Export | runner.py + CLI (identische Semantik) |
| Tag-basierte Policy | validate-plan.py:88-95 | NICHT übernommen (kein Bedarf belegt) |
| Parallele Testläufe | 09-01/09-02 (37+37 Ressourcen) | Tests (Mock) + Ableitung (live) |

## Offene Punkte (ehrlich)

| Punkt | Status |
|---|---|
| State-Trennung live (S3-Prefix-Verhalten) | UNVERIFIED (braucht Backend + Live-Test) |
| Backend-Werte/Owner (RIS) | OPEN (Vor-Gates) |
| Runner-Integration (Caller) | OPEN (kein Caller) |

---

*Check: PROJECT-STACK-ISOLATION-CHECK-01 · Muster aus AI_AUDITLOG.md ·
Profil ≠ Projekt (Beleg statt Annahme) · keine AWS-Mutation.*
