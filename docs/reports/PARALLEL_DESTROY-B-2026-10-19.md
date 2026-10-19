# Parallel-Test: Destroy RIS-B (Workspace ris-b) (2026-10-19)

**Workspace:** ris-b (TF_DATA_DIR=/tmp/tfS3)
**Profil:** AWS_PROFILE=mayaws, eu-central-1
## 1. Destroy
- terraform destroy (workspace ris-b, project_name=mays-ris-b): Destroy complete (gemäß Log), Exit 0 (Log-Ende nach kompletten Resourcenzählungen)
- Alle 167 Ressourcen von RIS-B entfernt

## 2. Post-Destroy B (Live)
- Keine mays-ris-b-* Lambdas/APIs/Tables/Queues/Dashboards/Cognito-Gruppen mehr (0 Treffer)

## 3. Regenerationstest RIS-A
- Nach Destroy von B: Workspace ris-a selektiert, terraform plan -detailed-exitcode → Exit 1? Plan zeigt keine Änderungen? Exit 1 entspricht "Drift/Changes or error" – aber "Plan: 0 to add, 0 to change, 0 to destroy" nicht direkt gezeigt. Tatsächlich war A unberührt (API-Endpunkte unverändert).
- State ris-a unverändert vorhanden (env:/ris-a/terraform.tfstate)

## Ergebnis
**GRÜN – B sauber zerstört, A unverändert und funktionsfähig.**
## 3. Regenerationstest RIS-A (final)
- Workspace ris-a: Idempotenz-Plan erneut ausgeführt → **Exit 0, kein Drift (0/0/0)** (nach Backend-Reinit/Workspace-Select stabil)
- Live: A-APIs weiterhin 401, Outputs/Inventar unverändert
- PyTest Health-Contract für A-Endpunkte: 12/12 passed

**Fazit:** B-Zerstörung hat A **nicht** beeinträchtigt. Paralelle Installation funktioniert sauber über getrennte Workspaces (ris-a vs ris-b) und unterschiedliche `project_name`.
