# TERRAFORM-CONSOLIDATION-SOURCE-AUDIT-01

## Status

**RED** (Subjekt-Semantik wie in den Vorgänger-Audits): Die benannten Ursachen
bestehen unverändert (keine Reparatur in diesem Checkpoint). Neu ist: Jede
parallele Struktur ist jetzt mit Herkunft belegt — kein UNKNOWN mehr bei der
Frage "welche Seite kam zuerst". Der Report löscht/führt nichts zusammen.

## Objective

READ-ONLY ermitteln, welche Terraform-Strukturen die autoritative/aktuelle
Implementierung sind und welche aus parallelen, älteren oder kopierten
Implementierungen stammen. Folge von CI-TERRAFORM-INTEGRITY-AUDIT-01 (92c72e7).
Keine Entscheidung über Löschen/Zusammenführen/Ändern — nur Evidence für einen
späteren Konsolidierungs-/Reparaturschritt. Keine Vermutung als Tatsache.

## Scope

Git-Baseline, Vollinventar (26 Dateien), 5 Root-Duplikate, 12 Modul-Duplikate
(IAM 2, Lambda 4, Cognito 3, DynamoDB 3), Inline-vs-outputs.tf-Muster,
Git-Historie/Origin (welche Seite kam zuerst, mit Diffs statt nur Messages),
Parallel-Implementierungs-Indizien, Contract-Graph, stale Handler-Referenzen,
CloudTrail/Monitoring, CI-Anbindung, Root-Intent, Source-of-Truth-Matrix.

## Repository Baseline

Verifiziert (nicht übernommen): Root `/home/dci-student/projects/Mays-Recruiting-Intelligent-System`,
Branch `main`, HEAD `92c72e7` ("docs: audit Terraform repository integrity"),
Remote SSH `git@github.com:maynowak/Mays-Recruiting-Intelligence-System.git`,
0 modified, 7 untracked Vorarbeits-Dateien (vollständig unberührt).

## Terraform Inventory

26 Dateien (`find terraform -type f`, ohne `.terraform/`): Root 3
(main.tf, outputs.tf, variables.tf); 8 Module mit je main.tf + variables.tf;
outputs.tf zusätzlich in api, cloudtrail, cognito, dynamodb, iam, lambda,
monitoring (NICHT in sqs — dort Outputs inline in main.tf).

| Path | Category | Referenced? | Active/Historical/Unknown |
|------|----------|-------------|---------------------------|
| `terraform/main.tf` | ROOT/PROVIDER/BACKEND/RESOURCE | CI (soll) | ACTIVE |
| `terraform/outputs.tf` | OUTPUTS | — | ACTIVE (Duplikat, Original s.u.) |
| `terraform/variables.tf` | VARIABLES | Root/Calls | ACTIVE (Z.18 Syntaxfehler) |
| `modules/iam/main.tf` | IAM/RESOURCE | `module "iam"` | ACTIVE |
| `modules/iam/outputs.tf` | OUTPUTS | — (stale) | HISTORICAL (nie funktionsfähig, s.u.) |
| `modules/iam/variables.tf` | VARIABLES | Call (teilweise) | ACTIVE (2 Pflicht-Inputs ungefüttert) |
| `modules/lambda/main.tf` | LAMBDA/RESOURCE/IAM | `module "lambda"` | ACTIVE |
| `modules/lambda/outputs.tf` | OUTPUTS | — | PARALLEL/DUPLICATE (s.u.) |
| `modules/cognito/*` | COGNITO | `module "cognito"` | ACTIVE (Outputs dupliziert) |
| `modules/dynamodb/*` | DYNAMODB | `module "dynamodb"` | ACTIVE (Outputs dupliziert, Vars undeklariert) |
| `modules/api/*` | API | `module "api"` | ACTIVE (Outputs eindeutig) |
| `modules/sqs/main.tf` + `variables.tf` | SQS | `module "sqs"` | ACTIVE (Outputs inline, eindeutig) |
| `modules/cloudtrail/*` | CLOUDTRAIL | nirgends | UNCONNECTED (nie verdrahtet belegt) |
| `modules/monitoring/*` | MONITORING | nirgends (Block in G0.2 entfernt) | HISTORICAL (war G0.1 verdrahtet, s.u.) |

## Root Output Analysis

Alle 5 Duplikate: `outputs.tf`-Definition vs. Inline-`main.tf`-Definition,
funktional identische Values (`module.cognito.user_pool_id`,
`module.api.api_endpoint`, `module.sqs.queue_urls`, `module.dynamodb.*`,
`module.lambda.function_name`). Keine externen Consumer im Repo. Herkunft
(s. Git History): `outputs.tf` = ORIGINAL (G0.1, d87a48f, 0 Inline-Outputs in
main.tf), Inline-Kopien = später (G0.2, 0281613, `+output "lambda_functions"`).

| Output | outputs.tf | main.tf | References | Evidence |
|--------|-----------|---------|------------|----------|
| `cognito_user_pool_id` | Z.1 (G0.1) | Z.187 (G0.2) | `module.cognito.user_pool_id` | blame: Z.1 G0.1, value-Zeile später angerührt (5073d84) |
| `api_endpoint` | Z.9 (G0.1) | Z.191 (G0.2) | `module.api.api_endpoint` | dto. |
| `sqs_queues` | Z.17 (G0.1) | Z.195 (G0.2) | `module.sqs.queue_urls` | dto. |
| `dynamodb_tables` | Z.21 (G0.1) | Z.199 (G0.2) | `module.dynamodb.work_items_table_name` | dto. |
| `lambda_functions` | Z.31 | Z.205 (G0.2, Diff belegt `+output`) | `module.lambda.function_name` | Einführungs-Diff G0.2 |

## Module Output Analysis

| Module | Output | Definition A | Definition B | Differences | Consumers |
|--------|--------|--------------|--------------|-------------|-----------|
| iam | `role_arn` | main.tf:87 (`lambda_role` — existent) | outputs.tf:7 (`handler` — nichtexistent) | WIDERSPRÜCHLICH (nicht nur doppelt) | keine (Consumer erwarten `lambda_role_arn`) |
| iam | `role_name` | main.tf:91 (existent) | outputs.tf:2 (nichtexistent) | WIDERSPRÜCHLICH | keine |
| iam | `policy_name` | — (nur outputs.tf:12, `handler`) | — | ORPHAN (kein Zwilling, Ziel fehlt) | keine |
| lambda | `lambda_role_arn` + 3 weitere | main.tf:231ff | outputs.tf:18ff | IDENTISCH (`lambda_execution.arn` etc.) | root nutzt KEINE davon (erwartet sie fälschlich von iam) |
| cognito | `user_pool_id`/`endpoint`/`client_id` | main.tf | outputs.tf | je 2× (Werte per Diff-Stand identisch) | root nutzt `user_pool_*` (Adresse unkritisch, solange 1 Definition) |
| dynamodb | `work_items_*`/`agent_state_*` u.a. | main.tf | outputs.tf | je 2× | root nutzt mehrere (dto.) |
| api/sqs/cloudtrail/monitoring | alle | — | — | EINDEUTIG | api/sqs konsumiert; cloudtrail/monitoring ohne Consumer |

## Inline vs outputs.tf

Muster bestätigt SYSTEMATISCH (nicht zufällig): G0.2 fügte Inline-Outputs in
`main.tf` hinzu, statt `outputs.tf` zu ersetzen/erweitern (Diff `+output
"lambda_functions"` + 140 geänderte Zeilen main.tf vs. +42 outputs.tf im selben
Commit). Modul-`outputs.tf`-Dateien für lambda/api in G0.2 neu (+17 je),
iam/cognito/dynamodb-`outputs.tf` in c83e3a2 (Doku-Commit) neu — jeweils
parallel zu bestehenden Inline-Definitionen. Copy/Paste-Indizien: identische
Value-Expressions, fehlende Newlines am Dateiende (`\ No newline`),
deutsche Doku-Texte neben englischen ("fuer den Order Handler",
"Zusaetzliche Tags"), Ticket-Tag `# T011-03` nur in iam/outputs.tf,
Domain-Fremdname "Order Handler" (Mays-Orders-Domäne, nicht RIS-Agent-Domäne).
Trotzdem keine Alters-Aussage ohne Diff-Beleg — alle obigen mit Commit+D árv belegt.

## Git History / Origin Analysis

Terraform-Historie (alle Branches): d87a48f (G0.1, Initial) → 0281613 (G0.2
Foundation) → 05a4df8 (Version-Upgrade) → 5073d84 (Platform-Foundation) →
748ddf7 (G0.3.1) → d0c8abe (G0.4) → c83e3a2/9f7aa46 (Doku). Danach keine
Terraform-Content-Commits mehr (Stand G0.4, mtimes Sep 09/10).

Welche Seite kam zuerst (verifiziert, nicht aus Messages geraten):

- Root-Outputs: `outputs.tf` (G0.1, 0 Inline-Outputs) VOR Inline-`main.tf`
  (G0.2). ORIGINAL = outputs.tf.
- `lambda_role_arn`-Erwartung: GEBORGER Obraschts in 0281613 als
  Ein-Zeilen-Änderung `- module.iam.role_arn` → `+ module.iam.lambda_role_arn`
  (Diff belegt), OHNE dass je ein solcher Output geschaffen wurde.
  G0.1-Vertrag war `module.iam.role_arn` (+ `module.dynamodb.table_arn` —
  ebenfalls heute nichtexistent: Vertrag evolutioniert, Rest UNKNOWN).
- `handler`-Outputs: GEBOREN in c83e3a2 als NEUE Datei (Diff `/dev/null` →
  outputs.tf) mit Zielen, die nie existierten
  (`-S 'resource "aws_iam_role" "handler"'` = leer über ALLE Commits).
  Niemals ACTIVE — stillborn.
- `permissions_boundary`/`dynamodb_gsi1_arn`: GEBOREN in derselben Datei
  (c83e3a2), nie übergeben, nie verwendet.
- Modul-`outputs.tf` (lambda/api): G0.2 neu; (iam/cognito/dynamodb):
  c83e3a2 neu — jeweils NACH den Inline-Definitionen.
- `monitoring`-Block: G0.1 verdrahtet (`module "monitoring"`, Lambda-Name aus
  `module.lambda.function_name`) → G0.2 ENTFERNT (Diff `-module "monitoring"`,
  ersetzt durch Inline-CloudWatch-Ressourcen im Root). ModulDATEIEN aber erst
  in c83e3a2 neu erzeugt — für ein bereits entferntes Modul.
- `cloudtrail`: in KEINER belegten main.tf-Revision als module-Block
  (`grep` in G0.1+G0.2 leer) — nie verdrahtet.

## Parallel Implementation Findings

| Indiz | Evidence | Klassifikation |
|-------|----------|----------------|
| Root-Inline-Outputs vs outputs.tf | Einführungs-Diff G0.2, identische Values | DUPLICATE (Original: outputs.tf) |
| Modul-outputs.tf vs Inline | Erzeugungs-Commits nach Inline-Stand | DUPLICATE/PARALLEL |
| iam `handler`-Outputs | nie existente Ziele, Doku-Commit, Order-Domäne, T011-Tag | HISTORICAL (nie ACTIVE), Fremdkontext-Einfluss |
| `monitoring`-Dateien nach Block-Entfernung | c83e3a2 erzeugt, Block G0.2 entfernt | HISTORICAL/UNCONNECTED |
| `cloudtrail`-Dateien ohne jede Verdrahtung | c83e3a2 erzeugt, nie referenziert | UNCONNECTED (Herkunft UNKNOWN) |
| Zwei Lambda-Rollen (`iam.lambda_role` + `lambda.lambda_execution`) | beide aktiv verdrahtet/konsumiert (zweite via Policies) | PARALLEL (effektive Rolle UNKNOWN) |
| Deutsche/englische Doku-Mischung, "Order Handler" | iam/outputs.tf + variables.tf | PARALLEL (Mays-Orders-Kontext) |
| `dynamodb.table_arn` (G0.1-Vertrag) vs heutige Outputs | G0.1-Call belegt, Output heute fehlend | HISTORICAL (evolutioniert, Rest UNKNOWN) |

UNKNOWN bleibt nur, wo kein Diff-Beleg existiert (cloudtrail-Zweck,
effektive Rolle, table_arn-Verbleib).

## Module Contract Graph

```
root
 ├── module.cognito ──outputs(user_pool_*)──▶ module.api inputs ✓ (Adresse ok)
 ├── module.sqs ──outputs(queue_*)──▶ root + module.lambda ✓
 ├── module.dynamodb ──outputs──▶ root ✓ (Adresse) · ABER Call Args environment/table_config UNDEKLARIERT ✗ · main.tf nutzt var.table_config UNDEKLARIERT ✗
 ├── module.iam ──outputs(role_arn/role_name)──▶ NIEMAND (Consumer will lambda_role_arn ✗) · Pflicht-Inputs dynamodb_gsi1_arn/permissions_boundary UNGEFÜTTERT ✗
 ├── module.lambda ──inputs(iam_role_arn=module.iam.lambda_role_arn ✗) · eigene lambda_role_arn-Outputs doppelt, unkonsumiert
 ├── module.api ──inputs ok──▶ (invoke_arn/api_id Adressen ok) ✓
 ├── module.cognito ◀── root übergibt environment UNDEKLARIERT ✗
 └── (cloudtrail/monitoring: keine Kanten)
```

| Consumer | Input | Provider | Output | Exists | Status |
|----------|-------|----------|--------|--------|--------|
| module.lambda | `iam_role_arn` | module.iam | `lambda_role_arn` | NEIN | BROKEN (seit G0.2-Diff) |
| module.iam | `dynamodb_gsi1_arn` | root | — (nichts) | NEIN | BROKEN (seit c83e3a2) |
| module.iam | `permissions_boundary` | root | — | NEIN | BROKEN (dto.) |
| module.dynamodb | `environment`/`table_config` | root | — (undeklariert) | NEIN | BROKEN (Args) |
| module.dynamodb intern | `var.table_config` | — | — | NEIN | BROKEN (Ref Z.24-25) |
| module.cognito | `environment` | root | — (undeklariert) | NEIN | BROKEN (Arg) |
| module.api | alle 7 | cognito/lambda/root | alle | JA | OK (Referenzebene) |
| module.sqs | alle | root | — | JA | OK |

## Stale References

`aws_iam_role.handler` ×2 + `aws_iam_role_policy.handler` ×1, alle in
`modules/iam/outputs.tf:4/9/14`. Ressource/Name/ursprüngliche Definition:
nie existent (Gesamthistorie leer). Letzte Änderung: Erzeugungs-Commit c83e3a2
(Doku-Commit, "Order Handler"-Domäne). Referenziert von: niemandem.
Klassifikation: STALE/HISTORICAL (nie ACTIVE — schärfer als nur "stale",
mit Total-Historienbeleg).

## CloudTrail / Monitoring

- Ressourcen/Variablen/Outputs in Dateien vorhanden (cloudtrail 140+23+10,
  monitoring 194+40+97 Zeilen, alle c83e3a2).
- Root-Einbindung: cloudtrail NIE (kein Block je belegt) → UNCONNECTED.
- monitoring: G0.1 CONNECTED → seit G0.2 UNCONNECTED (Block-Diff belegt);
  heutige Dateien nachträglich erzeugt → HISTORICAL.
- Outputs konsumiert: keine. Als "unnötig" NICHT klassifiziert (kein
  Lösch-Urteil in diesem Audit).

## CI Connection

`.github/workflows/ci-cd.yml` (lesend): validate/plan/deploy ohne
`working-directory`/`-chdir` (grep: NOT SET). Versuchte Struktur: Repo-Root
(dort keine `*.tf` → vakuos grün, EXIT 0 belegt). Tatsächliche Struktur:
`terraform/` (wird nie geprüft). `on.plan`-Trigger kein GitHub-Event
(Auswirkung NOT VERIFIED). Fazit: CI versucht effektiv KEINE der belegten
Strukturen zu validieren — Befunde konnten sich seit G0.2 ansammeln.

## Current Root Assessment

**CURRENT ROOT** (nicht ambiguous): `terraform/` mit `main.tf` (Provider,
Backend, 6 Modulaufrufe, Inline-Ressourcen/Outputs) ist der einzig belegte
Root — keine konkurrierende Root-Konfiguration im Repo. Die Ambiguität liegt
NICHT beim Root-Standort, sondern bei den Duplikat-Schichten darin
(Original outputs.tf vs. spätere Inline-Kopien) und beim blinden CI-CWD.

## Source of Truth Matrix

| Component | Current Candidate | Evidence | Historical Candidate | Confidence |
|-----------|-------------------|----------|----------------------|------------|
| Root-Outputs | `terraform/outputs.tf` (G0.1-Original) | G0.1-Erzeugung, 0 Inline damals; Inline erst G0.2-Diff | Inline-`main.tf`-Kopien (G0.2) | HIGH |
| IAM-Rolle | `aws_iam_role.lambda_role` (existent, konsumiert) | main.tf + Root-Call `dynamodb_table_arn` | `handler`-Namen (nie existent) | HIGH |
| IAM-Output-Name | `role_arn` (G0.1-Vertrag `module.iam.role_arn`) | G0.1-Call-Diff | `lambda_role_arn`-Erwartung (G0.2-Einzeiler ohne Output) | HIGH (Bruchstelle G0.2) |
| Lambda-Outputs | unentschieden (beide identisch) | identische Values | — | MEDIUM (funktional egal, formal doppelt) |
| Cognito/DynamoDB-Outputs | unentschieden (je 2×, Werte gleich) | — | — | MEDIUM |
| DynamoDB-Vertrag | UNKNOWN (weder `table_arn` noch `table_config` je konsistent) | G0.1-Call vs. heutige Vars | `table_arn` (G0.1) | LOW |
| SQS/API | aktuelle Stände (eindeutig, konsumiert) | keine Duplikate, Calls decken sich | — | HIGH |
| CloudTrail | kein Current (unverdrahtet) | nie ein Block belegt | — | LOW (Zweck UNKNOWN) |
| Monitoring | Root-Inline-Ressourcen (aktiv) statt Modul | G0.2-Entfernungs-Diff | Modul-Block (G0.1) + Moduldateien (c83e3a2) | MEDIUM |
| CI-Ziel | `terraform/` (soll) vs. Root (ist) | Workflow ohne CWD + Vakuos-Beleg | — | HIGH (Fixpunkt bekannt) |

Keine subjektive Gesamtwertung über die Matrix hinaus.

## Findings

1. Jede Duplikat-Schicht hat eine belegte Geburtsreihenfolge (G0.1-Original →
   G0.2-Inline-Kopien → c83e3a2-Modul-outputs.tf) — "welche kam zuerst" ist
   beantwortet, Lösch-Reihenfolge bleibt späterem Schritt vorbehalten.
2. `lambda_role_arn`-Bruch ist ein G0.2-Einzeiler ohne Output-Seite (kein
   schleichender Verfall, sondern punktuelle Fehländerung).
3. `handler`-Familie war nie aktiv (Total-Historie leer) — Fremdkontext
   (Order-Domäne, T011-Tag) in Doku-Commit importiert.
4. monitoring war aktiv und wurde bewusst ent-inline-t (G0.2-Diff); Dateien
   kamen danach — kein "vergessenes" Modul, sondern Schichten aus
   verschiedenen Zeiten. cloudtrail war nie verdrahtet.
5. CI-Blindheit erklärt die Akkumulation seit G0.2 (kein Gate hat je die echte
   Config gesehen).
6. REST-Unknowns (Vor-Audit): dynamodb-Vertrag (`table_arn`→`table_config`)
   und effektive Lambda-Rolle bleiben LOW/UNKNOWN — brauchen Repair-Kontext.

## Unknowns

- cloudtrail-Modulzweck im RIS-Kontext (kein Beleg).
- Effektive Lambda-Rolle zur Laufzeit (beide Strukturen aktiv referenziert).
- `table_arn`-Verbleib (nur G0.1-Call belegt).
- Post-Fix-Validate, dahinterliegende fmt-Diffs (Repair-Kontext).
- `on.plan`-Auswirkung, CI-Verhalten nach CWD-Fix (GitHub-seitig).

## Evidence

| # | Quelle (read-only) | Ergebnis |
|---|--------------------|----------|
| E1 | Git-Baseline-Befehle + `cat-file 92c72e7` | main/92c72e7/SSH, 0 modified, 7 untracked |
| E2 | `find terraform -type f` | 26 Dateien (s. Inventar) |
| E3 | `git log --all -- terraform/` + `--follow` main/outputs | Historie G0.1→G0.4, danach nur Doku |
| E4 | `git show d87a48f:terraform/outputs.tf` + `grep -c ^output` main | G0.1: outputs.tf voll, 0 Inline |
| E5 | `git show 0281613 --stat/-- main.tf` | G0.2: +140 main (inkl. `+output`), +42 outputs.tf, monitoring-Block entfernt |
| E6 | `-S`-Suchen (cognito-output, lambda_role_arn, handler, lambda_role, boundary) | Einführungs-Commits je Struktur |
| E7 | `git show c83e3a2 -- modules/iam/` | handler-outputs.tf + boundary-Vars als neue Dateien geboren |
| E8 | `-S 'resource "aws_iam_role" "handler"'` (alle Commits) | leer → nie existent |
| E9 | Modul-`--diff-filter=A` für lambda/cognito/dynamodb/api-outputs.tf | Erzeugungs-Commits (G0.2 bzw. c83e3a2) |
| E10 | `blame -L 1,10 terraform/outputs.tf` | G0.1-Zeilen + spätere Value-Anpassungen |
| E11 | CloudTrail/monitoring-Erzeugung + Verdrahtungs-Greps G0.1/G0.2 | c83e3a2-Dateien; monitoring G0.1→G0.2 entfernt; cloudtrail nie |
| E12 | G0.1-Call-Zeilen (`role_arn`, `table_arn`) vs. G0.2-Diff (`lambda_role_arn`) | Bruchstelle Einzeiler G0.2 |
| E13 | Contract-Abgleich Root↔Modul-Vars | iam 2 Pflicht offen; dynamodb/cognito undeklarierte Args/Refs |
| E14 | Workflow-Lektüre + Root-Vakuos-Validate | Blind-Gate belegt |
| E15 | `git diff --check`, `git status`, `git diff HEAD -- terraform/` | clean / nur Audit-Delta / leer |

## Recommended Next Step

Nächster technischer Arbeitsschritt (separater Checkpoint, keine Ausführung
hier): Auf Basis dieser Matrix einen Repair-Plan als Review-Dokument erstellen
(Schichten in Geburtsreihenfolge adressieren: Root-Duplikate →
`lambda_role_arn`-Einzeiler → Modul-Duplikate → stale handler-Datei-Inhalte →
Variablen-Verträge → CI-CWD), ohne vorab zu löschen oder zusammenzuführen;
Freigabe des Plans bleibt eigener Schritt.

---

*Audit: TERRAFORM-CONSOLIDATION-SOURCE-AUDIT-01 · Read-Only · keine
Terraform-/IAM-/AWS-Mutation · kein init mit Backend, kein Plan/Apply, kein
fmt-Write · keine Datei gelöscht/verschoben/umbenannt · keine untracked Datei
berührt · keine Vermutung als Tatsache.*
