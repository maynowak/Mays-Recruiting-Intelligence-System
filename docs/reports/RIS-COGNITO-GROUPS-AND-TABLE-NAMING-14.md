# RIS-COGNITO-GROUPS-AND-TABLE-NAMING-14

STATUS: YELLOW (Code GREEN + valide; Live-Anlage blockiert: kein RIS-Pool)

- Date/Time: 2026-09-30 13:40 UTC
- Branch + HEAD: main, 588f6cc (Vorgänger b0f8014 intakt)
- Scope: Cognito-Standardgruppen (wörtlich) + Lambda-ARN-Vertrag nach MO-Namensverhalten (Muster aus AI_AUDITLOG.md). Keine Policy-/Gruppen-Namens-Änderung darüber hinaus
- Sections: Baseline → MO-Namensverhalten → Gruppen-Frage (User: wörtlich) → Implementierung → Validate → Live-Pool-Check → E2E-Entscheid
- Findings (nur verifiziert):
  - MO-Muster: EINE `staff`-Gruppe + admin-only-Pool + `table_name`+`table_arn`-Explizit-Verdrahtung + Project-Tags + Workspace=project_name.
  - Gruppen (User-Entscheid WÖRTLICH): `Admin`, `Staff`, `user-user`, `user-requier` als 4 neue Ressourcen (bestehende 3 unangetastet).
  - Lambda-ARN: `dynamodb_table_arn` deklariert + aus `work_items_table_arn` gefüttert (MO-Muster: Name+ARN explizit); Ausdruck-Semantik (`/table/arn/*`) UNVERÄNDERT (keine Rechte-Erweiterung ohne Freigabe).
  - API-Authorizer-`tags` entfernt (per Validate ungültig — gleiche Beweisklasse, dokumentierte Scope-Erweiterung).
  - `validate` (mayaws): SUCCESS (nur Deprecation-Warnings) — ERSTMALS GRÜN (vorher 8 Fehler).
  - Live: NUR Pool `mays-orders-users` vorhanden, KEIN RIS-Pool → Gruppen-Anlage BLOCKIERT (kein Ziel-Pool; kein Workaround ohne Foundation-Apply).
  - Tests 41/41 (Mock, unberührt).
- Evidence: MO cognito/lambda/root-Dateien (gelesen); User-Antwort (wörtlich); main.tf-Diffs; validate-SUCCESS; `list-user-pools` (1 Pool, MO); fmt-Diffs (pre-existing)
- Classification: YELLOW
- Terraform Checks: `validate` GRÜN (lesend); KEIN plan/apply mit Backend (Pool fehlt); `fmt` nur pre-existing (kein Write)
- Git Status: 4 TF-Dateien + Report + Log; 8 untracked (+ Lock-Artefakt entfernt) unberührt; AI_AUDITLOG.md Template-only
- Files Changed: cognito/main.tf (+4 Gruppen), lambda/variables.tf (+Decl), main.tf (+Feed), api/main.tf (-tags)
- Explicit confirmation: KEINE Policy-/Gruppen-/Domain-Änderung sonst; KEINE AWS-Mutation (nur lesende Checks)
- Open questions: RIS-Pool-Deployment (Voraussetzung für Gruppen-Anlage); ARN-Ausdruck-Semantik; Threshold-Kalibrierung
- Risks: Keine durch Code (Syntax-Ebene); Live-Anlage ohne Pool unmöglich (korrekt gestoppt statt erzwungen)
- Next Actions: Review; Pool-Deployment (separater Foundation-Apply mit Freigabe) → DANACH gezielter Gruppen-Apply; KEIN Apply hier
- Resume Point: Code committet (s. Commit); `validate` GRÜN; Live-Anlage BLOCKIERT (Pool fehlt)

---

*Fix: Gruppen wörtlich + ARN-Vertrag nach MO-Muster · Muster aus AI_AUDITLOG.md ·
Live-Stop statt Workaround.*
