# TERRAFORM-SOURCE-OF-TRUTH-DECISION-01

## Status

**GREEN** — Entscheidungsdeliverable vollständig: jede problematische Struktur
ist klassifiziert (CONFIRMED ACTIVE / HISTORICAL / STALE) oder explizit als
UNKNOWN markiert. Keine künstliche Entscheidung, keine Reparatur, keine
Löschung, keine Zusammenführung. Die Subjekt-Reparatur bleibt ausstehend
(weiterhin NICHT reparierte Probleme s. Ende).

## Objective

Ausschließlich Source-of-Truth-Frage klären (kein Terraform-Fix): welche
Terraform-Struktur ist autoritativ/aktuell, welche parallel/älter/kopiert.
Basis: TERRAFORM-CONSOLIDATION-SOURCE-AUDIT-01 (d86c048). Nur Analyse und
Entscheidungsgrundlage für einen späteren Repair-Schritt.

## Scope

Historische Quellen je Variante (Aufgabe 1), Root-Outputs (2), IAM (3),
Lambda (4), Cognito (5), DynamoDB (6), Monitoring/CloudTrail (7), CI (8),
Decision-Matrix, Report + AI_AUDITLOG, gezielter Commit. Kein `git add .`.

## Repository Baseline

Canonical Repository (verifiziert, kein Parallel-Workspace): toplevel
`/home/dci-student/projects/Mays-Recruiting-Intelligent-System`, Remote
`git@github.com:maynowak/Mays-Recruiting-Intelligence-System.git`
(fetch+push), Branch `main`, HEAD `d86c048`, 0 modified, 7 untracked
Vorarbeits-Dateien (unberührt). Genau EIN Audit-Log (`docs/AI_AUDITLOG.md`;
`AUDIT_MONITORING_ARCHITECTURE.md` ist Sach-Doku, kein Log) — kein STOP-Fall.

## Aufgaben 1–2 — Historische Quellen + Root Outputs

Historie (Diff-belegt, nicht aus Messages geraten): G0.1 (d87a48f) erzeugte
`terraform/outputs.tf` mit 5 Outputs bei 0 Inline-Outputs in `main.tf`;
G0.2 (0281613) fügte Inline-Kopien in `main.tf` hinzu (`+output
"lambda_functions"`-Diff). Tests (`tests/`) und Installer enthalten NULL
Terraform-Referenzen; CI referenziert keine einzelne Struktur (blind);
nicht-Terraform-Consumer der Root-Outputs: keine (py/yml/sh-Suche leer).
Doku beschreibt ModulDATEIEN als vorhanden (BACKUP/AUDIT-MONITORING-Architektur,
requirements-traceability) — das belegt Datei-Existenz, KEINE Verdrahtung.

| Output | outputs.tf (G0.1-Original) | main.tf-Inline (G0.2-Kopie) | Klassifikation |
|--------|---------------------------|----------------------------|----------------|
| `cognito_user_pool_id` | Z.1, blame G0.1 | Z.187 | ACTIVE / STALE |
| `api_endpoint` | Z.9, G0.1 | Z.191 | ACTIVE / STALE |
| `sqs_queues` | Z.17, G0.1 | Z.195 | ACTIVE / STALE |
| `dynamodb_tables` | Z.21, G0.1 | Z.199 | ACTIVE / STALE |
| `lambda_functions` | Z.31 | Z.205 (G0.2-Diff) | ACTIVE / STALE |

(Erstspalte = CONFIRMED ACTIVE als maßgebliche Definition; Inline-Kopien =
CONFIRMED STALE: neuer, redundant, consumerlos.)

## Aufgabe 3 — IAM

Gegenüberstellung: `aws_iam_role.lambda_role` (Name `${project}-lambda-role`,
Trust lambda.amazonaws.com, eigene Inline-Policy Logs/DynamoDB/S3) vs.
`handler`-Namen (nie existent, Total-Historie leer, geboren c83e3a2 mit
Order-Domäne/T011-Tag). `lambda_role_arn`-Erwartung (main.tf:92,
outputs.tf:37-38): geboren G0.2-Einzeiler (`-role_arn`→`+lambda_role_arn`),
nie mit Output-Seite. Boundary-Vars (`permissions_boundary`,
`dynamodb_gsi1_arn`): geboren c83e3a2, nie übergeben/verwendet.
`aws_iam_role.lambda_execution` (lambda-Modul, `${project}-${environment}-agent`,
an Funktion + 5 Policies gebunden: main.tf:28/75/101/123/145/165) ist die
einzige angebundene Laufzeit-Rolle; `iam.lambda_role` ist consumerlos
(außerhalb des iam-Moduls NULL Referenzen) — existiert aber als Ressource.

| Struktur | Decision | Evidenz |
|----------|----------|---------|
| `lambda_role` + Inline-Outputs `role_arn`/`role_name` (main.tf:46-93) | CONFIRMED ACTIVE (Ressource/Definition) | existent, G0.1-Präsenz, korrekte Ziele |
| `handler`-Outputs `role_arn`/`role_name`/`policy_name` (outputs.tf) | CONFIRMED STALE | nie existente Ziele, kein Consumer |
| `module.iam.lambda_role_arn`-Erwartung | CONFIRMED STALE (als Vertrag; Code-Stelle aktiv-broken) | kein Output je, G0.2-Einzeiler-Diff |
| `permissions_boundary` / `dynamodb_gsi1_arn` (deklariert) | CONFIRMED STALE (als Bedarfs-These unbelegt) / Pflicht-Inputs offen | geboren c83e3a2, 1 Grep-Treffer (Deklaration) |
| Effektive IAM-Rolle zur Laufzeit | UNKNOWN — EVIDENCE INSUFFICIENT | zwei Rollenstrukturen, keine Live-/Plan-Evidenz (nicht geraten) |

## Aufgabe 4 — Lambda (Matrix)

Inline-Outputs (`function_name`/`function_arn`/`invoke_arn`): G0.1-Original
(`-S`-Diff); `outputs.tf`-Datei: G0.2-Neuanlage mit allen 4 (inkl. neuem
`lambda_role_arn`). Values identisch (`lambda_execution.*`).

| Output | Inline (main.tf) | outputs.tf | Consumer | Decision |
|--------|-----------------|------------|----------|----------|
| `function_name` | G0.1-Original | G0.2-Kopie | root ×2 (dup), historisch monitoring-Block | ACTIVE / STALE |
| `invoke_arn` | G0.1-Original | G0.2-Kopie | `module.api` (aktiv) | ACTIVE / STALE |
| `function_arn` | G0.1-Original | G0.2-Kopie | KEINER (orphan) | ACTIVE (ungenutzt) / STALE |
| `lambda_role_arn` | G0.2-neu (Diff) | G0.2-Kopie | KEINER (root will sie fälschlich von iam) | ACTIVE (ungenutzt) / STALE |

Modulstruktur/Inputs: 1 Modul, Calls vollständig (Referenzebene intakt).
Runtime: Funktion + Policies an `lambda_execution` gebunden (belegt).
IAM-Verbindung eingangsseitig broken (`iam_role_arn`-Input aus nichtexistentem
Output) — als Vertragsentscheidung bereits unter Aufgabe 3 (STALE) erfasst.

## Aufgabe 5 — Cognito

Inline-Outputs (`user_pool_id`/`endpoint`/`client_id` + weitere): G0.1-Original;
`outputs.tf`: c83e3a2-Kopie. Consumer (alle Adressen in beiden Kopien
vorhanden): `module.api` (3 Inputs, aktiv), root-Outputs. `environment`-Arg
(Root-Call): undeklariert UND ungenutzt (`main.tf` ohne undeklarierte
Var-Nutzung) → totes Arg. Keine Reparatur.

Decision: Inline-Definitionen CONFIRMED ACTIVE; outputs.tf-Kopien CONFIRMED
STALE; `environment`-Arg CONFIRMED STALE.

## Aufgabe 6 — DynamoDB

Inline-Outputs: G0.1-Original; `outputs.tf`: c83e3a2-Kopie (je 2×:
`work_items_*`, `agent_state_*` u.a.). Consumer: root + lambda-Modul (Adressen
vorhanden). `table_arn`: nur G0.1-Call (`module.dynamodb.table_arn`) belegt,
Output heute fehlend → CONFIRMED HISTORICAL (evolutioniert; Verbleib UNKNOWN).
`table_config`/`environment`-Args: undeklariert übergeben; `var.table_config`
in main.tf:24-25 aktiv genutzt (TTL) → Bedarf CONFIRMED ACTIVE, Deklaration
fehlend (Repair-Sache, nicht hier). GSI: real `gsi-status`/`gsi-tenant` (+1)
vorhanden (main.tf:28/77/107); `dynamodb_gsi1_arn`-Vertrag passt auf keinen
davon (Namen) und ist ungefüttert → Vertrag CONFIRMED STALE.

Decision: Inline-Outputs CONFIRMED ACTIVE; outputs.tf-Kopien CONFIRMED STALE;
`table_arn` CONFIRMED HISTORICAL; `table_config`-Bedarf CONFIRMED ACTIVE
(Deklaration fehlt); GSI1-Vertrag CONFIRMED STALE.

## Aufgabe 7 — Monitoring / CloudTrail (nur Belege)

Monitoring: eingeführt G0.1 (verdrahteter `module "monitoring"`-Block mit
`module.lambda.function_name`); getrennt G0.2 (Entfernungs-Diff, ersetzt durch
Root-Inline-CloudWatch); ModulDATEIEN erst c83e3a2 neu erzeugt; aktuelle
Referenzen: NULL (kein Block, kein Consumer). → CONFIRMED HISTORICAL
(Block-Ära) + UNCONNECTED (Dateien). Root-Inline-CloudWatch: CONFIRMED ACTIVE.
CloudTrail: eingeführt c83e3a2 (Dateien); Modulaufrufe: NULL je belegt
(G0.1/G0.2-main.tf ohne Treffer); Terraform-Verbindungen: NULL; Doku beschreibt
Dateien als vorhanden/implementiert (kein Verdrahtungsbeleg); Zweck aus
Repository NICHT ableitbar → UNKNOWN — EVIDENCE INSUFFICIENT (nicht als
"unnötig" klassifiziert).

## Aufgabe 8 — CI (nur Befund, keine Änderung)

`.github/workflows/ci-cd.yml`: validate (`init -backend=false`, `validate`,
`fmt -check`), plan, prod-gated deploy — alles OHNE `working-directory`/`-chdir`
(belegt: NOT SET). Root enthält keine `*.tf`; `validate` dort EXIT 0 vakuos
(belegt). Verwendetes Verzeichnis für Terraform: de facto keines —
`terraform/` wird nie geprüft. `on.plan`-Trigger: kein GitHub-Event
(Auswirkung NOT VERIFIED, GitHub-seitig). CodeBuild: im Repo nicht vorhanden
(keine Referenz). Decision: Workflow-Datei CONFIRMED ACTIVE; Schutzbehauptung
"CI validiert Terraform" CONFIRMED STALE.

## TERRAFORM ROOT INTENT

CURRENT ROOT (nicht ambiguous): `terraform/` — Provider, Backend, 6
Modulaufrufe, Inline-Ressourcen. Keine konkurrierende Root-Konfiguration.
Ambiguität nur innerhalb der Duplikat-Schichten (entschieden s.o.).

## SOURCE-OF-TRUTH DECISION (Matrix)

| Struktur | Kandidaten | Historische Quelle | Aktive Referenz | Status | Evidenz |
|----------|------------|--------------------|-----------------|--------|---------|
| Root-Outputs (5) | outputs.tf vs Inline-main.tf | outputs.tf (G0.1) | keine externen Consumer; Values identisch | ACTIVE: outputs.tf / STALE: Inline | G0.1-Erzeugung, G0.2-`+output`-Diff, blame |
| IAM-Rolle | `lambda_role` vs `handler` | `lambda_role` (G0.1) | `lambda_role` (Modul); `handler` nirgends | ACTIVE / STALE | Existenz + Total-Historie-leer |
| IAM-Output-Name | `role_arn` vs `lambda_role_arn` | `role_arn` (G0.1-Call) | `lambda_role_arn` nirgends lieferbar | ACTIVE (Name) / STALE (Erwartung) | G0.1-Call, G0.2-Einzeiler-Diff |
| Boundary/GSI1-Vars | deklariert vs verwendet | c83e3a2 (Geburt) | NULL Verwendung | STALE | 1-Treffer-Grep, ungefütterte Pflicht |
| Lambda-Outputs (4) | Inline vs outputs.tf | Inline (G0.1) | invoke_arn→api, name→root; arn/role_arn orphan | ACTIVE / STALE | `-S`-Diffs, Consumer-Grep |
| Cognito-Outputs (3) | Inline vs outputs.tf | Inline (G0.1) | api-Modul (3×) | ACTIVE / STALE | dto. + Call-Abgleich |
| Cognito-`environment`-Arg | übergeben vs deklariert | G0.2-Call-Seite | NULL Nutzung | STALE | Var-Dateien + Nutzungs-Grep |
| DynamoDB-Outputs (3+) | Inline vs outputs.tf | Inline (G0.1) | root + lambda | ACTIVE / STALE | dto. |
| `table_arn` | G0.1-Call | G0.1 | NULL | HISTORICAL | G0.1-Call-Zeile; Verbleib UNKNOWN |
| `table_config`-Bedarf | Nutzung vs Deklaration | Nutzung aktiv (TTL) | main.tf:24-25 | ACTIVE (Bedarf) | Nutzungs-Grep; Deklaration fehlt |
| SQS/API | single definition | G0.1/G0.2 | Calls decken sich | ACTIVE | keine Duplikate |
| Monitoring-Dateien | Dateien vs Block | Block G0.1–G0.2 | NULL | HISTORICAL/UNCONNECTED | Entfernungs-Diff, c83e3a2-Erzeugung |
| Root-Inline-CloudWatch | Ressourcen | G0.2 | aktiv (Root) | ACTIVE | G0.2-Diff |
| CloudTrail-Dateien | Dateien | c83e3a2 | NULL | UNKNOWN | nie verdrahtet, Zweck unbelegt |
| Effektive Laufzeit-Rolle | 2 Rollen | beide alt | keine Live-Evidenz | UNKNOWN | nicht geraten |
| CI-Gates | Datei vs Wirkung | Datei aktiv | Wirkung NULL | ACTIVE (Datei) / STALE (Schutz) | fehlendes CWD, Vakuos-Beleg |

## Findings

1. Einheitliches Entstehungsmuster belegt: G0.1-Originale (Root-outputs.tf;
   Modul-Inline-Outputs) → G0.2-Inline-Kopien (Root) bzw. G0.2/c83e3a2-`outputs.tf`-
   Kopien (Module) — mit genau einer relevanten Ausnahme: Root (dort ist die
   Datei das Original).
2. Zwei echte (nicht nur doppelte) Widersprüche: iam-`handler`-Ziele und
   `lambda_role_arn`-Erwartung — beide mit Geburts-Diff und ohne je
   funktioniert zu haben.
3. Zwei tote Args (`environment`→cognito; `environment`/`table_config`→dynamodb)
   vs. ein lebendiger undeklarierter Bedarf (`var.table_config`-Nutzung).
4. monitoring ist Geschichte mit Beleg (kein "vielleicht aktiv"), cloudtrail
   bleibt ehrlich UNKNOWN.
5. Die einzige "aktive" Rolle mit Funktionsbindung ist `lambda_execution`;
   welche Rolle effektiv gelten soll, ist damit NICHT entschieden (UNKNOWN).

## Unknowns

CloudTrail-Zweck; effektive Laufzeit-Rolle; `table_arn`-Verbleib;
Post-Fix-Validate; fmt-Rest; CI-nach-CWD-Fix; `on.plan`; IAM-Runtime
(NOT REACHED). UNKNOWN ist hier Endzustand, kein Mangel.

## Evidence

E1 Git-Baseline (canonical Remote/Branch/HEAD d86c048, 0 modified, 7 untracked,
1 Audit-Log) · E2 `find terraform` (26 Dateien) · E3 Root-G0.1-Beleg
(outputs.tf voll, 0 Inline) · E4 G0.2-Diffs (`+output`, monitoring-Entfernung,
`role_arn`→`lambda_role_arn`-Einzeiler) · E5 c83e3a2-Neuanlagen (iam-outputs.tf,
-Vars, cognito/dynamodb-outputs.tf, cloudtrail/monitoring-Dateien) · E6
Total-Historie-leer für `handler`-Ressource · E7 Erzeugungs-Commits je
Modul-outputs.tf (G0.2/c83e3a2) · E8 Inline-Originale G0.1 (`-S`-Suchen) ·
E9 Blame-Root-outputs.tf (G0.1-Zeilen) · E10 Consumer-Greps (api↔invoke_arn,
root↔Namen, function_arn/table_arn/handler orphan) · E11 GSI-Bestand vs
GSI1-Vertrag · E12 Rollen-Bindungs-Grep (lambda_execution 6×, lambda_role 0×
außerhalb iam) · E13 Tests/Installer-NULL, Doku-nur-Datei-Existenz,
CI-ohne-CWD + Vakuos-EXIT-0 · E14 `diff --check` clean, `diff HEAD --
terraform/` leer.

## Recommended Next Step

(Nur Beschreibung, keine Ausführung:) Repair-Plan als Review-Dokument auf Basis
dieser Matrix erstellen — Schichten in Geburtsreihenfolge (Root-Inline-Kopien →
`lambda_role_arn`-Einzeiler → Modul-outputs.tf-Kopien → handler-Inhalte →
Variablen-Verträge → CI-CWD), UNKNOWN-Positionen (CloudTrail, effektive Rolle,
table_arn) als Entscheidungspunkte mit Owner markieren; Freigabe eigener Schritt.

---

*Decision: TERRAFORM-SOURCE-OF-TRUTH-DECISION-01 · Analyse + Entscheidungsgrundlage,
kein Fix · keine Terraform-/IAM-/AWS-/CI-Änderung · keine Datei gelöscht/
verschoben/umbenannt · kein fmt-Write, kein Plan/Apply · keine Vermutung als Tatsache.*
