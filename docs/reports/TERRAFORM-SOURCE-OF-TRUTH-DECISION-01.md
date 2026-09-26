# TERRAFORM-SOURCE-OF-TRUTH-DECISION-01

## Status

**GREEN** — Formale Entscheidung vollständig: alle Strukturen A–T mit genau
einer Kategorie (CONFIRMED ACTIVE / HISTORICAL / STALE / UNKNOWN) und
Confidence. Keine Zwischenkategorien, nichts künstlich aufgelöst. Kein
Terraform-Fix, keine Konsolidierung, keine Löschung.

## Objective

Formale Source-of-Truth-Entscheidung für die Terraform-Strukturen des canonical
Repositorys, ausschließlich auf Basis der vorliegenden Evidence aus
`docs/reports/TERRAFORM-CONSOLIDATION-SOURCE-AUDIT-01.md` und
`docs/AI_AUDITLOG.md`. Keine neue Historienanalyse (Source-Audit trägt),
keine neuen Annahmen, kein Fix.

## Evidence Basis

- `docs/reports/TERRAFORM-CONSOLIDATION-SOURCE-AUDIT-01.md` (gelesen;
  Herkunft je Schicht: G0.1-Originale → G0.2-Kopien → c83e3a2-Neuanlagen,
  jeweils mit Commit-Diffs statt nur Messages)
- `docs/AI_AUDITLOG.md` (gelesen; CHECKPOINTs INTEGRITY/CONSOLIDATION)
- Live rückbestätigt an HEAD (keine neuen Annahmen, nur Bestandsprüfung):
  `git diff HEAD -- terraform/` leer; `^output`-Zählung Root
  (outputs.tf 8 / main.tf 5); `aws_iam_role.handler` 2 Treffer (+1 Policy);
  `module.iam.lambda_role_arn` 2 Treffer; kein `working-directory`/`chdir`
  in `ci-cd.yml`.
- Hinweis: Ein früherer Report gleichen Namens (Commit 81459d2) existiert;
  dieses Dokument ersetzt ihn in der vom Ticket geforderten formalen Struktur
  A–T (keine zweite Struktur, keine Duplikat-Entscheidung — Inhalt aus
  derselben Evidence neu formalisiert).

## Repository Baseline

Canonical Repository (kein Parallel-/Old-/Backup-/Copy-Workspace):
toplevel `/home/dci-student/projects/Mays-Recruiting-Intelligent-System`,
Remote `git@github.com:maynowak/Mays-Recruiting-Intelligence-System.git`
(fetch+push), Branch `main`, HEAD `7b73036`, 0 modified, 7 untracked
Vorarbeits-Dateien (nicht verändert/gelöscht/committet).

## Decision Rules

- ACTIVE = belegte aktuelle Quelle. Bedeutet NICHT fehlerfrei
  (eine ACTIVE-Struktur kann gleichzeitig `validate FAIL` verursachen).
- STALE = existiert noch, ist aber NICHT als aktuelle Quelle für die spätere
  Reparatur zu verwenden.
- HISTORICAL = belegt früher aktiv/zugehörig, heute abgelöst/entfernt.
- UNKNOWN — EVIDENCE INSUFFICIENT = gültiges Ergebnis; wird nicht zur
  Vereinfachung aufgelöst.

## Source-of-Truth Matrix

| Struktur | Entscheidung | Evidence | Confidence |
|----------|--------------|----------|------------|
| A. Terraform Root (`terraform/`) | CONFIRMED ACTIVE | Einziger Root (Provider/Backend/6 Modulaufrufe); keine Konkurrenz im Repo | HIGH |
| B. Root outputs.tf | CONFIRMED ACTIVE | G0.1-Erzeugung (d87a48f) bei 0 Inline-Outputs; blame G0.1-Zeilen | HIGH |
| C. Root Inline Outputs (main.tf:187-209) | CONFIRMED STALE | G0.2-Einführungs-Diff (`+output "lambda_functions"`); neuer, redundant, consumerlos | HIGH |
| D. IAM (Modul + `lambda_role`) | CONFIRMED ACTIVE | Ressource existent, G0.1-Präsenz, Trust + Policies verdrahtet | HIGH |
| E. Lambda (Modul + Inline-Outputs) | CONFIRMED ACTIVE | Inline-Outputs G0.1-Original (`-S`-Diff); `invoke_arn`→api aktiv; Funktion an `lambda_execution` gebunden | HIGH |
| F. Cognito (Modul + Inline-Outputs) | CONFIRMED ACTIVE | Inline G0.1-Original; `user_pool_*` von api-Modul konsumiert | HIGH |
| G. DynamoDB (Modul + Inline-Outputs) | CONFIRMED ACTIVE | Inline G0.1-Original; Tabellen-Outputs von root + lambda konsumiert | HIGH |
| H. SQS | CONFIRMED ACTIVE | Single definition (Outputs inline, eindeutig); Calls decken sich | HIGH |
| I. API | CONFIRMED ACTIVE | Single definition (`outputs.tf`, G0.2); Inputs/Outputs referenziert | HIGH |
| J. Monitoring | CONFIRMED HISTORICAL (Block-Ära) | G0.1 verdrahteter Block → G0.2-Entfernungs-Diff; Dateien c83e3a2 nachträglich, heute UNCONNECTED | HIGH |
| K. CloudTrail | UNKNOWN — EVIDENCE INSUFFICIENT | Nie ein module-Block belegt (G0.1/G0.2-Greps leer); Zweck unbelegt | — |
| L. table_arn | CONFIRMED HISTORICAL | Nur G0.1-Call (`module.dynamodb.table_arn`) belegt; Output heute fehlend (Verbleib UNKNOWN, nicht künstlich entschieden) | MEDIUM |
| M. role_arn | CONFIRMED ACTIVE | G0.1-Vertrag (`module.iam.role_arn` im Call-Diff); Output existent | HIGH |
| N. lambda_role_arn (Erwartung an iam) | CONFIRMED STALE | G0.2-Einzeiler (`-role_arn`→`+lambda_role_arn`) ohne je geschaffene Output-Seite; 2 Referenzen, 0 Provider | HIGH |
| O. handler-Familie (3 Refs) | CONFIRMED STALE | c83e3a2-Neuanlage; Total-Historie der Ressource leer (nie ACTIVE); kein Consumer | HIGH |
| P. Boundary-Variablen (`permissions_boundary`) | CONFIRMED STALE | c83e3a2-Geburt; genau 1 Treffer (Deklaration); nie übergeben/verwendet | HIGH |
| Q. dynamodb_gsi1_arn | CONFIRMED STALE | Deklariert, 0 Verwendungen (auch modul-intern), nie übergeben; passt auf keine reale GSI (gsi-status/gsi-tenant/+1) | HIGH |
| R. table_config | CONFIRMED ACTIVE (Bedarf) | Nutzung `modules/dynamodb/main.tf:24-25` (TTL) aktiv; Root-Default vorhanden (`{true,"expiresAt"}`, variables.tf:49-59); Modul-Deklaration fehlt (Repair-Sache) | HIGH |
| S. Cognito environment (Arg) | CONFIRMED STALE | Undeklariert übergeben UND ungenutzt (keine Var-Nutzung in cognito/main.tf); totes Arg | HIGH |
| T. CI Terraform Working Directory | CONFIRMED GAP (keine Terraform-Datei) | Kein CWD gesetzt; Root-Vakuos-`Success!` (EXIT 0 ohne `*.tf`) belegt; Gates prüfen `terraform/` nie | HIGH |

## Confirmed Active Structures

A (Root), B (Root outputs.tf), D (IAM-Modul/`lambda_role`), E (Lambda + Inline),
F (Cognito + Inline), G (DynamoDB + Inline), H (SQS), I (API), M (`role_arn`),
R (`table_config`-Bedarf). Root-Inline-CloudWatch (aus CONSOLIDATION-Audit
übernommen, ACTIVE). Hinweis gem. Regel: ACTIVE ≠ fehlerfrei (validate FAIL
bleibt bis Repair bestehen).

## Confirmed Historical Structures

J (monitoring-Block, G0.1–G0.2), L (`table_arn`, nur G0.1-Call).

## Confirmed Stale Structures

C (Root-Inline-Kopien), Modul-`outputs.tf`-Kopien (iam/lambda/cognito/dynamodb),
N (`lambda_role_arn`-Erwartung), O (handler-Familie), P (Boundary-Vars),
Q (`dynamodb_gsi1_arn`), S (Cognito-`environment`-Arg), CI-Schutzbehauptung
(Schutz STALE; Datei selbst aktiv — s. T als GAP).

## Unknown Structures

K (CloudTrail-Zweck), effektive Laufzeit-Rolle (zwei Strukturen, keine
Live-Evidenz — nicht geraten), `table_arn`-Verbleib, Post-Fix-Validate,
fmt-Rest, CI-nach-CWD-Fix, `on.plan`-Laufzeit, IAM-Runtime (NOT REACHED).
Nicht als "unnötig" klassifiziert, nicht aufgelöst.

## Repair Implication

Planungsfolgen (keine aktuellen Änderungen):

- CONFIRMED ACTIVE → preserve / repair in place (Originale behalten;
  Verträge darauf zurückführen, z. B. N→M).
- CONFIRMED STALE → candidate for removal/deprecation in later repair
  (C-Kopien, Modul-outputs.tf-Kopien, O-, P-, Q-, S-Inhalte entfernen;
  Schutzbehauptung via CWD-Fix heilen).
- CONFIRMED HISTORICAL → nicht wiederbeleben (L, J-Block); Dateien (J/K)
  weder reaktivieren noch löschen ohne Owner.
- UNKNOWN → do not modify until resolved (K- fate, effektive Rolle,
  `table_arn`-Verbleib brauchen Owner/Live-Evidenz vor jeder Änderung).

## Explicit Non-Decisions

- Keine Lösch-Reihenfolge festgelegt (nur Kandidaten benannt).
- Keine `table_name`-Policy-Lösung gewählt (Deklarieren vs. Umschreiben —
  Repair-Entscheidung am `validate`-Feedback).
- Kein CloudTrail-Schicksal (aktivieren/löschen/defer mit Owner — offen).
- Keine effektive Rolle bestimmt (UNKNOWN).
- Kein CI-Trigger-Fix (`on.plan` NOT VERIFIED).
- Kein Urteil über GSI-Sharding-Bedarf (Zielvolumen-Doku gehört mays-order-aws).

## Unknowns

Siehe Unknown Structures. Zusätzlich: ob Phase-I-Validate weitere latente
Schichten zeigt (STOP einkalkuliert); keine neuen Unknowns gegenüber
CONSOLIDATION-Audit erzeugt.

## Next Step

Repair-Plan-Checkpoint auf Basis dieser Matrix (Schichten in Geburtsreihenfolge,
Commits A–F-Schema aus REPAIR-PLAN-01); Freigabe eigener Schritt. Keine
Ausführung hier.

---

*Decision: TERRAFORM-SOURCE-OF-TRUTH-DECISION-01 · formal A–T · kein
Terraform-Fix · keine Konsolidierung · keine Löschung · kein IAM-/CI-Fix ·
keine Datei außer den zwei Dokumentationsdateien berührt.*
