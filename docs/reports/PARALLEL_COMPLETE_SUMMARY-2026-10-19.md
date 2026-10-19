# Parallel-Installationstest (Workspace-basiert, nur terraform/) – Gesamtsummary

**Datum:** 2026-10-19
**Ansatz:** Parallele Installationen durch getrennte Terraform-Workspaces (ris-a, ris-b), S3-Backend env:/workspace/terraform.tfstate, Backend-Infrastruktur (mays-ris-tf-lock + mays-ris-tf-state-dev) bleibt

## Reihenfolge
1. RIS-A installieren (Workspace ris-a), projekt_name=mays-ris → Prefix mays-ris-dev-*; 167 to add
2. Volltest RIS-A: Idempotenz 0, Auth 401, PyTest 12+25 passed, Monitoring 2 Dashboards, Verkabelung orders_reader OK
3. Konflikt-Experiment RIS-B (Workspace ris-b), projekt_name=mays-ris identisch → Plan zeigt 167 to add, aber **Apply würde AWS-Namenskonflikte** (DynamoDB, Lambda, SQS, Cognito, S3) auslösen (State getrennt, Live nicht)
4. Saubere Parallelinstallation RIS-B (Workspace ris-b), projekt_name=mays-ris-b → Prefix mays-ris-b-dev-*; 167 to add, Apply erfolgreich (Live vollständig getrennt)
5. Volltest RIS-B: Auth 401, PyTest 12+25 passed, getrennte APIs/Tables/Queues/Alarme/Dashboards
6. Destroy B → nur B entfernt, A unverändert (Idempotenz recheck Exit 0, APIs weiter 401, Tests passed)
7. Destroy A → vollständig entfernt, nur mays-ris-tf-lock verbleibt

## Wesentliche Erkenntnis (Konflikt zwischen parallelen Installationen)
- **Trennung via Workspace + andere project_name:** Funktioniert (ris-b mit mays-ris-b erzeugt komplett separate Ressourcen)
- **Trennung via Workspace allein bei identischem project_name:** **nicht möglich** – AWS-Ressourcennamen kollidieren (region/global scoped). Terraform-Plan nutzt nur eigenen State, erkennt keine Live-Namenskonflikte → Apply bricht bei erster existierender Ressource.
- **Kein Cross-State-Konflikt:** ris-a/ris-b haben je eigenes State-Objekt (env:/ris-a/terraform.tfstate, env:/ris-b/terraform.tfstate), beeinflussen sich nicht bei Terraform-Operationen
- **Unverändertheit:** Zerstörung von B hat A nicht tangiert (nachgewiesen durch Idempotenz + Live-Checks)

## Reports
- PARALLEL_RIS-A_INSTALL-TEST-2026-10-19.md
- PARALLEL_RIS-B_CONFLICT-EXPERIMENT-2026-10-19.md
- PARALLEL_RIS-B_INSTALL-TEST-2026-10-19.md
- PARALLEL_DESTROY-B-2026-10-19.md
- PARALLEL_DESTROY-A-2026-10-19.md
## Cleanup-Status (final)
- A vollständig zerstört, B vollständig zerstört
- Übrig nur: Backend s3://mays-ris-tf-state-dev + DynamoDB-Lock mays-ris-tf-lock
- Kein mays-ris-b-* Live mehr
