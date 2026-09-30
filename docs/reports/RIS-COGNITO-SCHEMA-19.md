# RIS-COGNITO-SCHEMA-19

STATUS: GREEN (validate SUCCESS — erstmalig vollständig grün)

- Date/Time: 2026-09-30 13:55 UTC
- Branch + HEAD: main, 588f6cc (Vorgänger b0f8014 intakt)
- Scope: Cognito-Schema-Deadlock lösen (Muster aus AI_AUDITLOG.md). Keine Policy-/Gruppen-Änderung, keine anderen Module
- Sections: Live-Schema lesen → 21-Zeichen-Täter → ignore_changes → Block-Reduktion → Validate GRÜN
- Findings (nur verifiziert):
  - Live-Signatur VOLLSTÄNDIG gelesen (22 Attribute mit Typ/Mutable/Required/Constraints).
  - Täter: `phone_number_verified` (21 Zeichen, EINZIGER Name >20; Provider-Hash-Reihenfolge erklärt Index 1).
  - Deadlock: Entfernen verboten (AWS) + Deklarieren verboten (Provider-Limit) → Lösung `lifecycle.ignore_changes[schema]` (Drift ignorieren statt bekämpfen; tenant_id-Block bleibt als Intent + greift bei Neu-Erstellung).
  - Reduktion 22→1 Blöcke (per Skript, Uniqueness-asserted); tenant_id-Intent erhalten.
- Evidence: Describe-Output (22 Zeilen), Längen-Nachweis (21), validate-SUCCESS (mayaws, CWD-verifiziert)
- Classification: GREEN
- Terraform Checks: `validate` SUCCESS (nur Deprecation-Warnings); KEIN plan/apply; `fmt` nur pre-existing (kein Write)
- Git Status: 1 TF-Datei + Report + Log; 8 untracked (+ Lock-Artefakt entfernt) unberührt; AI_AUDITLOG.md Template-only
- Files Changed: terraform/modules/cognito/main.tf (Schema-Teil); sonst nur Doku
- Explicit confirmation: KEINE Policy-/Gruppen-/Domain-/Modul-Änderung sonst; KEINE AWS-Mutation (nur validate + Describe lesend)
- Open questions: Provider-Limit vs. AWS-Realität (Upstream-Thema, nicht RIS); Schema-Evolution künftig (ignore-Regime dokumentiert)
- Risks: Keine durch Fix (Drift-Status quo ante: live KORREKT, Code greift nicht ein)
- Next Actions: Review; KEINE Folgeschritte ohne Review
- Resume Point: Schema-Deadlock GELÖST + validate GRÜN committet (s. Commit)

---

*Fix: RIS-COGNITO-SCHEMA-19 · Muster aus AI_AUDITLOG.md ·
Deadlock analysiert statt umgangen.*
