# TERRAFORM-CI-SOURCE-AUDIT-01

STATUS: YELLOW

- Date/Time: 2026-09-26 18:40 UTC
- Branch + HEAD: main, 3996e25 (Vorgänger 5894543/18d65ec intakt)
- Scope: CI/CD-Terraform-Vertrag read-only (Muster aus AI_AUDITLOG.md). Kein Repair, keine Pipeline-Änderung, kein Run
- Sections: Inventar → Workflow tief → Roots → `on.plan` exakt → Command-Contract → Trennung/Checkout/Auth → Cross-Repo → SoT → Repair-Kandidat
- Findings (nur verifiziert):
  - Inventar: GENAU 1 Workflow (`.github/workflows/ci-cd.yml`, 75 Zeilen); KEINE Buildspecs/Skripte/Makefiles/Wrapper; KEINE Pipeline-Terraform (kein codepipeline/codebuild in tf/); EIN Terraform-Root (`terraform/` + 8 Moduldirs, keine Zweit-Roots); keine tfvars.
  - Workflow: 3 Jobs (validate → plan → deploy), alle ubuntu-latest, je actions/checkout@v4 OHNE Parameter (Default-Verhalten, nicht gesetzt — kein Guess zu depth); Setup Terraform `>=1.16,<2.0`; validate=init -backend=false/validate/fmt-check; plan=init(mit Backend)/plan -var environment=ref_name/show-json; deploy=init/apply -auto-approve (prod-gated, `environment: production`). KEINE Matrix.
  - CWD: KEIN Mechanismus IRGENDWO (kein defaults/working-directory/chdir/TF_ROOT/TF_WORKING_DIR/cd/Skript — Repo-Grep leer). Ist-Verhalten PROVEN: alle Steps laufen in Checkout-Root (dort keine `*.tf` → Vakuos-Beleg aus Vor-Audits trägt). `terraform/` wird von KEINEM Step adressiert. Als gesetzter Vertrag: NICHT gesetzt (nicht automatisch "kaputt" — UNPROVEN/OPEN).
  - `on.plan` präzisiert: Exakte Schreibweise ist Schlüssel `plan:` unter `on:` (Z.6-7, branches [dev,test]) — KEIN Literal `on.plan` irgendwo im Repo (Grep belegt; Vor-Audits nutzten `on.plan` als Kürzel). Vorhandensein PROVEN; GitHub-Wirkung NOT VERIFIED (braucht Run; kein Guess zu invalid/ignoriert).
  - Command-Contract: validate-CWD=Root (vakuos), plan-CWD=Root (Backend-init + plan ohne Config — Laufzeit UNVERIFIED), deploy-CWD=Root + Secrets-env (Namen only, keine Werte gelesen). Plan/validate-Jobs haben KEIN AWS-env (nur deploy) — Backend-Zugriff des Plan-Jobs UNVERIFIED.
  - Trennung: VALIDATE/PLAN/APPLY deklariert getrennt (needs/if-Gates); DESTROY nirgends (kein Destroy-Job). Gate-Wirksamkeit UNVERIFIED (kein Run).
  - Auth: Region/Keys nur via Secrets im deploy-Job; KEIN OIDC/Role (kein aws-actions-Treffer); Provider-Region = var.aws_region (Default eu-central-1).
  - Cross-Repo (Mays-Orders @ 9c61237, Git-only): KEIN Terraform-CI-Workflow (nur codeql/dependency/security) → kein CWD-Muster vorhanden; RIS-Evidenz maßgeblich.
- Evidence: ci-cd.yml:1-75 (vollständig gelesen); Leer-Greps (CWD/Buildspec/Pipeline-TF/`on.plan`-Literal); Root-Verzeichnisliste; Vor-Audit-Vakuos-Beleg (referenziert)
- Classification: YELLOW
- Terraform Checks: KEINE (init/plan/apply/destroy/import/Provider/Backend verboten; kein Run); statische Datei-/Grep-Beweise; `fmt` nicht geschrieben
- Git Status: 0 modified, 7 untracked (unberührt); genau 1 Audit-Log
- Files Changed: nur Report + dieser Eintrag (keine Implementierung)
- Explicit confirmation when no files were changed: Workflow/Terraform/CI unverändert (Diff leer, s. Commit-Prüfung)
- Open Questions: GitHub-Verhalten `plan:`-Key; tatsächliche Job-Läufe (alle UNVERIFIED); Plan-Job-Auth ohne env; Backend-Erreichbarkeit
- Risks: Blinde Gates weiter offen (Vakuos-Grün möglich); unbekannter Trigger-Status; Deploy-Pfad Secrets-abhängig (Namen only bekannt)
- Next Actions: Review; danach ggf. TERRAFORM-CI-CONTRACT-REPAIR-01 (NUR bei Freigabe: CWD setzen + Negativ-Probe) — KEIN Run ohne Freigabe
- Resume Point: Audit committet (s. Commit); wartet auf Review; alles unverändert

## CI Source-of-Truth Matrix

| Bereich | Quelle | Status | Evidence |
|---|---|---|---|
| Workflow | ci-cd.yml (einzig) | ACTIVE | Inventar-Grep |
| Terraform Root | `terraform/` (einzig) | ACTIVE (als Config), UNCONNECTED (von CI) | Dir-Liste; kein Step adressiert ihn |
| CWD | nicht gesetzt (alle Steps Root) | UNPROVEN/OPEN (nicht automatisch kaputt) | Leer-Grep alle Mechanismen |
| Validate | init -backend=false/validate/fmt-check @Root | DEKLARIERT, Wirkung UNVERIFIED (vakuos plausibel) | Datei Z.21-28 + Vakuos-Beleg |
| Plan | init/plan/show @Root, Backend-Flag | DEKLARIERT, Wirkung UNVERIFIED | Datei Z.43-50; Auth-Lücke notiert |
| Apply | init/apply @Root, prod-gated, Secrets | DEKLARIERT, Wirkung UNVERIFIED | Datei Z.67-75 |
| Destroy | — (nicht vorhanden) | UNCONNECTED (kein Job) | Datei-Volltext |
| `on.plan` | Schlüssel `plan:` unter `on:` (Z.6-7) | PROVEN vorhanden / Wirkung NOT VERIFIED | Exakt-Text; kein Literal sonstwo |

## Candidate Next Repair

`NO PROVEN CONTRACT REPAIR` — CWD ist belegt NICHT gesetzt, aber "nicht explizit"
≠ kaputt (Ticket-Regel); ein CWD-Fix braucht Freigabe + Negativ-Probe (eigener
Repair-Checkpoint nach Review). Kein toter Vertrag, keine stale Variable, keine
kaputte Root-Referenz im CI-Scope gefunden.

---

*Audit: TERRAFORM-CI-SOURCE-AUDIT-01 · Muster aus AI_AUDITLOG.md · read-only ·
kein Run · keine Annahme erfunden (`plan:`-Exaktheit statt `on.plan`-Kürzel).*
