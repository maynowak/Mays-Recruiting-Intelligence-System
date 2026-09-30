# RIS-COGNITO-CONSOLIDATION-12

STATUS: GREEN (Cognito-Modul validiert sauber; Rest fremde Scopes)

- Date/Time: 2026-09-30 13:00 UTC
- Branch + HEAD: main, b0f8014 (Vorgänger 4916471 intakt)
- Scope: MO-Cognito ground-up → RIS-Abgleich → NUR bewiesene Cognito-Lücken (Muster aus AI_AUDITLOG.md). Keine Policy-Entscheidung (admin-only/Symbole/Domain), keine anderen Module
- Sections: MO-Modul (Pool/Client/Group) → RIS-Abgleich → 3 Fixes → Validate → Tests → Doku
- Findings (nur verifiziert):
  - MO-Muster (PROVEN, ADRs): admin-only Pool, Standard-Password, MFA OFF, KEINE Custom-Attribute, KEINE Domain (bewusst), Client `app` mit `explicit_auth_flows` (USER_PASSWORD_AUTH + REFRESH), Public-Client, EINE Gruppe `staff`.
  - Fix 1: `account_attributes` (invalide) → `schema`-Block tenant_id (Claim-Erhalt PROVEN nötig: Handler + Tests lesen `custom:tenant_id`).
  - Fix 2: bogus Client-Attribute → MO-belegte `explicit_auth_flows` (generate_secret=false war schon korrekt).
  - Fix 3: Client-`tags` ENTFERNT (per Validate bewiesen: Provider kennt das Argument nicht; Project-Scope bleibt auf Pool/Groups).
  - NICHT geändert (Owner-Entscheide, dokumentiert): admin-only, Symbole, Domain, Gruppen-Namen (RIS-Domäne bleibt).
- Evidence: MO main.tf (vollständig gelesen), RIS main.tf (vorher/nachher-Diff), Handler/Tests-Claim-Greps, `validate`-Fehlerliste (Cognito: VORHER 1 → NACHHER 0)
- Classification: GREEN
- Terraform Checks: `validate` (mayaws, CWD-verifiziert): Cognito-Fehler WEG (0); Rest 7+1 (Root-Alarm-Vars ×4, Lambda-ARN ×3, API-Authorizer-Tags ×1 — fremde Scopes, dokumentiert-offen); `fmt` nur pre-existing Alignment (kein Write)
- Git Status: 1 TF-Datei + Report + Log; 8 untracked (+ Lock-Artefakt entfernt) unberührt; AI_AUDITLOG.md Template-only
- Files Changed: terraform/modules/cognito/main.tf (+16/-7); sonst nur Doku
- Explicit confirmation: KEINE Policy-/Gruppen-/Domain-Änderung; KEINE anderen Module; KEINE AWS-Mutation (nur validate lesend)
- Open Questions: admin-only/Symbole/Domain (Owner); Rest-Fehler (fremde Scopes je separat)
- Risks: Keine durch Fix (Syntax-Ebene, Claim erhalten, Tests unberührt)
- Next Actions: Review; KEINE Folgeschritte ohne Review (nächster Block separat)
- Resume Point: Cognito-Modul valide committet (s. Commit)

---

*Konsolidierung: MO ground-up → RIS-Cognito · Muster aus AI_AUDITLOG.md ·
nur Bewiesenes · Policy-Entscheide offen gelassen.*
