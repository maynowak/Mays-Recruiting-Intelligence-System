# Parallel-Test: Destroy RIS-A (Workspace ris-a) (2026-10-19)

**Workspace:** ris-a
**Profil:** AWS_PROFILE=mayaws, eu-central-1

## 1. Destroy
- terraform destroy (workspace ris-a): Destroy complete (gemäß Log)
- 167 Ressourcen vollständig entfernt

## 2. Post-Destroy (Live)
- Keine mays-ris-*/-dev-* Ressourcen mehr (nur mays-ris-tf-lock verbleibt – Lock-Tabelle für S3-Backend)
- Lambdas 0, APIs 0, DynamoDB-Tables nur mays-ris-tf-lock, SQS 0, Dashboards 0, Cognito Pools 0

## 3. Workspaces
- ris-a/ris-b wurden durch die Backend-Struktur nicht mehr sichtbar (nach Destroy/Wechseln) – normales Workspace-Verhalten bei leerem State

## Ergebnis
**GRÜN – A vollständig zerstört. Nur Backend-Infrastruktur mays-ris-tf-lock bleibt (bewusst).**
