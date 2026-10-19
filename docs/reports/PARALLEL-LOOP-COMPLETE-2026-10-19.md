# Paralleler Installationszyklus — Gesamtbericht (2026-10-19)

**Ablauf wie gefordert:** Install A → Test A → Install B → Test A&B → Destroy B → Test A → Destroy A

## Ergebnis-Tabelle

| Schritt | Aktion | Ergebnis | Tests |
|---|---|---|---|
| 1 | **Install A** (ws `ris-a`, `project_name=ris-a`) | 167 added, Exit 0 | — |
| 2 | **Test A** | Präfix-Isolation sauber, A vollständig | **12/12 PASS** |
| 3 | **Install B** (ws `ris-b`, `project_name=ris-b`) | 167 added, Exit 0, Plan ohne A-Präfixe | — |
| 4 | **Test A+B parallel** | beide live, kein Cross-Talk, 0 Namensüberschneidungen | **11/11 PASS** |
| 5 | **Destroy B** | Lauf 1 BucketNotEmpty → geleert, Lauf 2 Exit 0, State 0 | **1/1 PASS** (B weg) |
| 6 | **Test A nach B-Zerstörung** | A identisch zu Schritt 2, idempotent, PyTest 12+25 | **13/13 PASS** |
| 7 | **Destroy A** | Lauf 1 BucketNotEmpty → geleert, Lauf 2 Exit 0, State 0 | **1/1 PASS** (A weg) |

**Gesamt: 38/38 Tests bestanden.**

## Was die Tests jetzt testen (Vorgabe „Tests müssen wissen, was sie testen")
Jeder Test benennt pro Punkt: **Ziel-Installation → Ressourcen-Präfix → Erwartungswert → Ist-Wert**.
- Runner: `scripts/parallel_tests.sh <ris-a|ris-b|both|destroy-check> [präfix]`
- Manifest: `docs/reports/PARALLEL_TEST-MANIFESTE-2026-10-19.md`
- Ownership-Register: wer besitzt was, was darf wer anfassen (inkl. „fremd → nie anfassen")

## Wo der Konflikt zwischen parallel arbeitenden liegt
1. **State ist per Workspace sauber getrennt** (`env:/ris-a/terraform.tfstate` vs `env:/ris-b/`).
   Kein State-Mix möglich → hier **kein** Konflikt.
2. **Der echte Konflikt ist der AWS-Namensraum.** Gleicher `project_name` ⇒ gleiche
   Ressourcennamen ⇒ `AlreadyExists/ResourceInUse` beim zweiten Apply. Terraform-Plan
   merkt das **nicht**, weil er nur den eigenen State kennt → Plan sagt „167 to add", Apply scheitert.
   **Lösung: unterschiedlicher `project_name` (ris-a vs ris-b).**
3. **Bedienfehler ist die größere Praxisgefahr:** Workspace-Wahl (T-3-Lauf: Test lief
   zunächst in `ris-b`, zeigte „167 to add" statt „No changes") und falsch etikettierte
   Plan-Dateien (Durchlauf 1: A wurde mit `mays-ris-dev-*` gebaut).
   Beides durch Präfix-Spotcheck vor Apply + `workspace show` vor jedem Lauf abgesichert.

## Verkabelung
Je Installation intern über Module-Outputs (keine hartcodierten Kreuzverweise):
`orders_table_arn`, `orders_queue_url`, `orders_queue_arn` aus `module.mays_orders.*`;
Lambda-Env `ORDERS_TABLE` / `ORDERS_SQS_QUEUE_URL` folgen dem eigenen Präfix.

## Bekannte, entschärfte Fallstricke
- CloudFront/Provider-Crash → Teil-State → Ownership-Prüfung vor Weiterarbeit
- BucketNotEmpty bei Destroy → Bucket leeren, Destroy wiederholen (kein Defekt)
- S3-Buckets mit laufenden Writern (CloudTrail, Health) füllen sich während des Destroy

## Dateien
- `docs/reports/PARALLEL_TEST-MANIFESTE-2026-10-19.md`
- `docs/reports/T1-RIS-A-TEST-2026-10-19.md`
- `docs/reports/T2-A-B-PARALLEL-TEST-2026-10-19.md`
- `docs/reports/T3-DESTROY-B-TEST-A-2026-10-19.md`
- `docs/reports/T4-DESTROY-A-2026-10-19.md`
- `scripts/parallel_tests.sh`
