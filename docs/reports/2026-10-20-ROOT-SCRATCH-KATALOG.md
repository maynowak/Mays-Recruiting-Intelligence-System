# Root-Scratch-Katalog (Konsolidierung 2026-10-20)

Diese Datei katalogisiert die bis 2026-10-20 untracked im Repo-Root liegenden
Agenten-Scratch-Dateien, ihre Herkunft/Purpose und ihr Ziel. Sie sind **keine**
Projekt-Dokumentation; die kanonischen Ablagen sind `docs/reports/` und
`docs/AI_AUDITLOG.md`.

Alle Dateien wurden **nicht gelöscht**, sondern nach
`/tmp/opencode/ris-scratch-20261020-1800/` archiviert (außerhalb des Repos).

## Themencluster

| Cluster | Dateien | Purpose / Herkunft | Ziel |
|---|---|---|---|
| Cleanup / State | `AWS_CLEANUP_FINAL.md`, `CLEANUP_COMPLETE.md`, `CLEANUP_COMPLETE_FINAL.md`, `CLEANUP_DIGEST_ENTRIES_COMPLETE.md`, `CLEANUP_FINAL_VERIFIED.md`, `CLEANUP_VERIFICATION.md`, `CLEAR_AWS_STATES_GUIDE.md`, `CURRENT_STATE_STATUS.md`, `STATE_CLEANUP_STATUS.md` | Session-Snapshots der AWS-/State-Bereinigung vor frischen Tests (2026-10-18/19) | Snapshots; inhaltliche Doppelgänger liegen in `docs/reports/2026-10-1*-*`; siehe `docs/reports/2026-10-19-AI-AUDITLOG-STRUCTUR-CHECK.md` |
| Phased Apply (`--through`) | `FINAL_SUMMARY.md`, `IMPLEMENTATION_SUMMARY.txt` | Begleit-Notizen zur Implementierung der phasenweisen Installation via `--through` (Code in `installer/ris.py`) | Archiv; Code ist separat committet |
| Discovery-Investigation | `DISCOVERY_COMPARISON.md`, `DISCOVERY_FUNCTIONALITY.md`, `DISCOVERY_IN_MAYS_ORDERS_REPORTS.md`, `DISCOVERY_SEARCH_IN_MAYS_ORDERS.md`, `MAYS_ORDER_DISCOVERY_CHECK.md`, `PLAN_FOLDER_IN_MAYS_ORDERS_INSTALLER.md` | Lese-Investigation der Discovery-Funktion des (fremden) Mays-Orders-Installers | Archiv (fremdes Projekt, rein lokal) |
| Mays-Orders-Ressourcen-Fragen | `CHECK_MAYSRISB_MAYS_ORDERS.md`, `CLARIFY_SQS_WORKER_RESOURCES.md`, `LAMBDA_FUNCTIONS_EXPLAINED.md` | Antworten auf Fragen zu `maysris-*-mays-orders*`-Ressourcen (IAM/Lambda/SQS) | Archiv |
| Integration / Cross-Installer | `REPORT_TERRAFORM_MODULE_INTEGRATION_PLAN.md`, `NOTE_CROSS_INSTALLER_STATES.md` | Plan-/Beobachtungsnotizen zur Modul-Integration und State-Überlagerung | Archiv |
| State-Check-Kommandos | `STATE_CHECK_COMMANDS.md`, `STATE_CHECK_COMMANDS_EXTENDED.md`, `STATE_CHECKS_FIXED.sh`, `STATE_CHECKS_SEQUENTIAL.sh`, `STATE_CHECKS_SEQUENTIAL_FIXED.md` | Kommando-Sammlungen zur State-Prüfung (teils ausführbare `.sh`) | Archiv |
| Auditlog-Fragmente | `AI_AUDITLOG_BACKEND_NOTE.md`, `AI_AUDITLOG_MAYS_ORDERS_PHASE2.md` | Template-konforme Einzel-Einträge | **In `docs/AI_AUDITLOG.md` übernommen** (kein Root-Duplikat mehr) |
| Lokale Artefakte | `installer/ris.py.backup`, `installer/ris.py.work_in_progress`, `tmp/replacement.txt` | Editor-Backups / Cache | Archiv |

## Konsequenz

- Reine Scratch-Muster im Root (`/AI_AUDITLOG_*.md`, `/CLEANUP_*.md`, `/STATE_*.md`,
  `/STATE_CHECKS_*.sh`, `installer/*.backup`, `installer/*.work_in_progress`, `tmp/`)
  sind künftig per `.gitignore` ausgeschlossen, damit der Repo-Root sauber bleibt.
- Kanonische Ablage bleibt `docs/reports/` + `docs/AI_AUDITLOG.md`.
