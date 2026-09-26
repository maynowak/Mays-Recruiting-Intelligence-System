# TERRAFORM-CONSOLIDATION-REPAIR-PLAN-01

## Status

**GREEN** — Plan vollständig, ausführbar, evidenzbasiert. Alle R01–R19 mit
Aktion, Dependency und Validierung. UNKNOWN-Positionen explizit DEFER.
Dies ist PLANUNG ONLY: keine Terraform-/IAM-/AWS-/CI-Änderung enthalten.

## Objective

Präziser, evidenzbasierter Reparaturplan für die Terraform-Konsolidierung auf
Basis der abgeschlossenen Audits. Keine Ausführung in diesem Checkpoint.

## Evidence Basis

Verwendete (nicht erfundene) Reports unter exakten Ticket-Namen, alle vorhanden:

- `docs/reports/CI-TERRAFORM-INTEGRITY-AUDIT-01.md` (validate EXIT 1, fmt EXIT 2,
  Contract-Brüche, Blind-Gate)
- `docs/reports/TERRAFORM-CONSOLIDATION-SOURCE-AUDIT-01.md` (Herkunft je Schicht:
  G0.1-Originale → G0.2-Kopien → c83e3a2-Neuanlagen)
- `docs/reports/TERRAFORM-SOURCE-OF-TRUTH-DECISION-01.md` (Decision-Matrix:
  ACTIVE / STALE / HISTORICAL / UNKNOWN)
- `docs/AI_AUDITLOG.md` (CHECKPOINTs 92c72e7, 346d6f4, d86c048, 81459d2)

Source of Truth (verifiziert): Repository `Mays-Recruiting-Intelligent-System`,
Branch `main`, Decision-Commit `81459d2` (HEAD, `cat-file`/`log` belegt).

## Repository Baseline

`main`, HEAD `81459d2`, SSH-Remote kanonisch, 0 modified, 7 untracked
Vorarbeits-Dateien (geschützt, unberührt). `git diff HEAD -- terraform/` leer.

## Repair Matrix

| ID | Finding | Current Source of Truth | Planned Action | Dependency | Validation |
|----|---------|-------------------------|----------------|------------|------------|
| R01 | Root Duplicate Outputs (5) | ACTIVE: `outputs.tf` (G0.1) / STALE: Inline-`main.tf` (G0.2) | REMOVE-STALE (5 Inline-Blöcke main.tf:187-209) | R19 (parse zuerst) | `validate` (Root-Fehler weg), `grep ^output` je 1× |
| R02 | IAM outputs.tf duplicates | ACTIVE: Inline main.tf:87-93 / STALE: outputs.tf `role_arn`/`role_name` (handler-Ziele) | REMOVE-STALE (outputs.tf-Blöcke role_arn/role_name) + REWIRE policy_name (s. R06) | R19, R01 | `validate` erreicht Modulebene |
| R03 | Lambda outputs.tf duplicates | ACTIVE: Inline main.tf (G0.1) / STALE: outputs.tf-Kopie (G0.2) | REMOVE-STALE (outputs.tf-Dateiinhalt, 4 Blöcke) | R19, R01 | dto. |
| R04 | Cognito outputs.tf duplicates | ACTIVE: Inline (G0.1) / STALE: outputs.tf (c83e3a2) | REMOVE-STALE (3 Blöcke) | R19, R01 | dto. |
| R05 | DynamoDB outputs.tf duplicates | ACTIVE: Inline (G0.1) / STALE: outputs.tf (c83e3a2) | REMOVE-STALE (duplizierte Blöcke) | R19, R01 | dto. |
| R06 | stale handler references (3) | CONFIRMED STALE, nie existent | REMOVE-STALE (outputs.tf:4/9/14-Blöcke; `policy_name`-Orphan gleich mit) | R02 (gleicher Commit sinnvoll) | `grep handler` in terraform/ leer (außer Doku) |
| R07 | `lambda_role_arn`-Contract | STALE-Erwartung (G0.2-Einzeiler ohne Output-Seite) | REWIRE: main.tf:92 + outputs.tf:37-38 auf `module.iam.role_arn` (G0.1-Vertrag) zurückführen | R01, R02 | `validate` (unsupported-attribute weg) |
| R08 | `dynamodb_gsi1_arn` + `var.dynamodb_table_name` (iam) | Var deklariert/nie genutzt/nie übergeben; `table_name` genutzt/nie deklariert | REMOVE-DECL (`dynamodb_gsi1_arn`-Block, 0 Referenzen belegt) + INVESTIGATE `table_name`-Bedarf (Policy-Zeile 15) | R02 | `validate` (required-variable + undeclared-ref weg) |
| R09 | `permissions_boundary` | deklariert/nie genutzt/nie übergeben | REMOVE-DECL (Block variables.tf:22-25, 1 Treffer = Deklaration) | R02 | dto. |
| R10 | `table_config`-Contract | Bedarf ACTIVE (TTL-Nutzung main.tf:24-25); Root-Default vorhanden (`{true,"expiresAt"}` variables.tf:49-59); Modul-Deklaration fehlt | DECLARE im Modul (Objekttyp spiegelgleich zum Root-Default — keine Werte-Erfindung) | R05 | `validate` (undeclared/unsupported weg) |
| R11 | Cognito `environment`-Arg | STALE (totes Arg: undeklariert + ungenutzt) | REMOVE-ARG (Root-Call-Zeile) | R04 | `validate` |
| R12 | DynamoDB GSI1-Vertrag | STALE (real: gsi-status/gsi-tenant/+1; Vertrag passt auf keinen, ungefüttert) | Keine Aktion (erledigt via R08 REMOVE-DECL); falls Repair einen GSI-ARN-Bedarf zeigt → DEFER mit Owner | R08 | `grep gsi1_arn` leer |
| R13 | `table_arn`-Historie | HISTORICAL (nur G0.1-Call); Verbleib UNKNOWN | DEFER (kein aktiver Consumer; keine Wiederbelebung ohne Owner) | — | keine (beobachten) |
| R14 | CloudTrail-Status | UNKNOWN (nie verdrahtet, Zweck unbelegt) | DEFER + DECISION REQUIRED (Owner klärt Zweck; kein Aktivieren/Löschen) | — | keine Code-Änderung |
| R15 | Monitoring-Status | HISTORICAL (Block) / ACTIVE (Root-Inline-CloudWatch) / UNCONNECTED (Dateien) | KEEP (Inline aktiv lassen); Dateien DEFER (kein Löschen ohne Owner) | — | keine |
| R16 | CI Terraform-CWD | Workflow ACTIVE, CWD nicht gesetzt | REWIRE (geplant): `defaults.run.working-directory: terraform` bzw. `-chdir=terraform` je Step — erst nach Phasen A–I grün | A–I lokal grün | CI-Log zeigt echte Prüfung |
| R17 | CI "blind gate" | Schutzbehauptung STALE (Vakuos-EXIT-0 belegt) | Geheilt via R16 + Gate-Assertion (s. Validierung) | R16 | Gate wird bei kaputtem Code rot (Negativ-Probe im Repair) |
| R18 | `on.plan`-Verhalten | NOT VERIFIED (kein GitHub-Event; Auswirkung GitHub-seitig) | INVESTIGATE (Workflow-Runs/Doku prüfen; keine Triggeränderung ohne Beleg) | — | DEFER bis Beleg |
| R19 | fmt / variables.tf:18 | Parse-Fehler (kein Stil-, sondern Syntax-Problem) | FIX-PARSE: Newline nach `default = "dev"` (1 Zeichen, variables.tf:17/18) | KEINE (Phase A, zuerst — blockiert validate UND fmt) | `validate` + `fmt -check` passieren Parse-Stufe |

## Duplicate Output Repair

Grundsatz (Decision): Originale behalten, Kopien auf BLOCK-Ebene entfernen —
nie "delete outputs.tf" pauschal (Root-outputs.tf IST das Original; dort fallen
die 5 Inline-Blöcke in main.tf). Pro Output: authoritative Definition (s. R01–
R05), stale Definition, Consumer (meist keine externen; `invoke_arn`→api,
Namen→root), geplante Änderung (Block-Removal), Validierung (`validate` +
`grep ^output <name>` genau 1 Treffer je Modul/Root). `function_arn`-Orphan
bleibt als ACTIVE-Definition erhalten (ungenutzt, kein Consumer → kein Eingriff).

## IAM / Lambda Repair

CURRENT: `iam_role_arn = module.iam.lambda_role_arn` (2 Stellen), Provider:
kein solcher Output; tatsächliche Rollen: `iam.lambda_role` (orphan, existent)
+ `lambda.lambda_execution` (an Funktion + 5 Policies gebunden).
EXPECTED (G0.1-Vertrag): `module.iam.role_arn`.
CONSUMER: `module.lambda` (Input) + Root-Output.
PLANNED CHANGE: REWIRE beider Stellen auf `module.iam.role_arn`; stale
handler-Blöcke entfernen (R06); `dynamodb_gsi1_arn`/`permissions_boundary`-
Deklarationen entfernen (R08/R09, je 0 Referenzen); `var.dynamodb_table_name`-
Bedarf klären (Policy-Zeile 15: entweder deklarieren oder Ressourcen-Ausdruck
auf ARN-Basis umstellen — Entscheidung im Repair nach `validate`-Feedback,
keine Vorab-Erfindung).
VALIDATION: `validate` ohne unsupported-attribute/required-variable-Fehler.
Keine IAM Policy Expansion, keine neuen Permissions (explizit verboten).

## DynamoDB Repair

`dynamodb_gsi1_arn`: current = deklariert/unbenutzt/ungefüttert → REMOVE-DECL.
`table_config`: current = Root-Default vorhanden, Modul-Nutzung aktiv,
Deklaration fehlend → DECLARE (Typ aus Root-Default gespiegelt). Herkunftsfrage
beantwortet: `table_config` kommt aus Root-`var.table_config` (belegt,
variables.tf:49-59) — die Referenz ist aktiv, nicht stale; es fehlt nur die
Modul-Deklaration. GSI1: kein Repair (R12). `table_arn`: DEFER (R13).
Validierung: `validate` (kein undeclared/unsupported mehr).

## Cognito Repair

CURRENT CONTRACT: Modul deklariert `project_name`/`tags`; Caller übergibt
zusätzlich `environment` (undeklariert, ungenutzt).
PLANNED ACTION: REMOVE-ARG (1 Zeile im Root-Call). Keine neue Variable.
VALIDATION: `validate`.

## CloudTrail / Monitoring

DECISION REQUIRED / DEFER mit Evidence: CloudTrail nie verdrahtet, Zweck
UNKNOWN → weder aktivieren noch löschen; Owner-Frage ("Zweck im RIS-Kontext?")
offen. Monitoring: Root-Inline aktiv lassen (KEEP); Moduldateien weder
reaktivieren noch löschen (DEFER). Doku-Aussagen ("IMPLEMENTED") beziehen sich
belegt nur auf Datei-Existenz, nicht auf Verdrahtung — kein Widerspruch zum Plan.

## CI Working Directory

CURRENT: kein `working-directory`/`-chdir`; Jobs laufen in Root (keine `*.tf`).
TARGET: alle Terraform-Steps laufen in `terraform/` (via Job-`defaults` oder
pro Step `-chdir=terraform` — Detailentscheidung im Repair).
Affected workflow: `.github/workflows/ci-cd.yml` (einzige Datei).
Commands affected: `init -backend=false`, `validate`, `fmt -check`, `init`,
`plan`, `apply` (alle).
Validation: CI-Log muss echte Prüfung zeigen (bei kaputtem Fixture rot);
Negativ-Probe im Repair einplanen. Reihenfolge-Hinweis: erst nach lokalem
Grün (Phasen A–I), sonst schaltet der Repair CI bewusst auf Rot — das ist
korrekt, aber als eigener Commit F (Gate) sichtbar zu machen. Keine CI-Änderung
in diesem Plan-Checkpoint.

## on.plan

Aktuelle Triggerdefinition (`ci-cd.yml:4-7`): `push.branches: [main]` plus
`plan.branches: [dev, test]` — `plan` ist kein GitHub-Events-Schlüssel.
Betroffene Jobs: indirekt `plan`-Job (dessen `if`-Gates zusätzlich filtern).
Erwartete Trigger (vermutet, NICHT belegt): vermutlich `pull_request` o.ä. —
als Vermutung gekennzeichnet, kein Planungs-Faktum.
GitHub-Semantik aus Repo belegbar: nur, dass der Schlüssel ungültig ist;
Laufzeit-Verhalten NOT VERIFIED (braucht Workflow-Runs/Admin-Sicht).
Unknowns: ob GitHub den Workflow wegen ungültigem Schlüssel ablehnt oder den
Schlüssel ignoriert. Keine Triggeränderung im Plan (INVESTIGATE/DEFER).

## Formatting

`variables.tf:18` ist SYNTAX (Parser bricht ab), nicht Stil: `fmt -check`
(EXIT 2) und `validate` (EXIT 1) scheitern beide daran. Datei: `terraform/
variables.tf`, Änderung: Newline nach `default = "dev"` (Phase A, 1 Zeichen).
Validierung: `fmt -check` erreicht danach echte Formatprüfung (dahinterliegende
Diffs derzeit NOT VERIFIED — eigene Sichtung im Repair). Semantik unberührt
(Validation-Block `in ["dev","test","prod"]` bleibt identisch).

## Repair Order

Phasen A–M aus dem Ticket, Dependency-Anpassung aus Evidence begründet
(Parse-Fehler blockiert ALLES → Phase A zuerst; Duplikate danach, weil
`validate` sie schichtweise meldet; CI-CWD erst nach lokalem Grün, damit Gates
nie vakuos-lügen):

- PHASE A — Root/Parsing: R19 (Newline). Warum zuerst: belegt alle
  Terraform-Operationen (validate + fmt).
- PHASE B — Duplicate Outputs: R01–R05 (Block-Removals) + R06 (handler).
  Warum danach: erste `validate`-Fehlerschicht.
- PHASE C — Variables/Contracts: R10 (DECLARE table_config), R11 (REMOVE-ARG
  environment), dynamodb-Call-Args. Warum: zweite Fehlerschicht.
- PHASE D — IAM/Lambda: R07 (REWIRE role_arn), R08/R09 (REMOVE-DECLs),
  `table_name`-Klärung. Warum: dritte Schicht (required/unsupported/undeclared).
- PHASE E — DynamoDB-Vertrag: R12 erledigt (via R08), R13 DEFER festschreiben.
- PHASE F — Cognito: R11-Ausführung (fällt ggf. mit C zusammen — klein halten).
- PHASE G — CloudTrail/Monitoring: R14/R15 DEFER + Owner-Fragen (kein Code).
- PHASE H — Formatting: `fmt -check` echte Prüfung; nur Whitespace-Fixes falls
  gemeldet (keine Semantik).
- PHASE I — `terraform validate`: Muss EXIT 0 liefern (CWD-verifiziert, wie in
  Audits). STOP falls neue Strukturschicht erscheint (s. Stop-Conditions).
- PHASE J — CI-CWD: R16 (Workflow-Änderung, 1 Datei).
- PHASE K — CI-Gates: R17 (Negativ-Probe: kaputtes Fixture → rot) + R18-Status.
- PHASE L — `terraform plan`: NUR lesend gegen Dev-Kontext, kein Apply;
 Ago nur wenn A–K grün. (Ausführung separater Checkpoint.)
- PHASE M — AWS-Identität/Deploy-Audit: Secrets-Identität mit geeignetem
  Prinzipal (separater Checkpoint; hier nur eingeplant).

## Validation Matrix

| Repair | Static Check | terraform validate | fmt-check | plan | CI |
|--------|--------------|--------------------|-----------|------|----|
| R19 | Diff 1 Zeichen | Parse-Stufe passiert | Parse-Stufe passiert | — | — |
| R01–R06 | `grep ^output` 1× je Name/Modul | Root-Fehler weg | — | — | — |
| R07–R11 | Call↔Var-Abgleicheldet | EXIT 0 erwartet | — | — | — |
| R08-DECL/R10-DECL | Deklaration vorhanden | dto. | — | — | — |
| R13–R15 | keine Code-Änderung | unverändert | — | — | — |
| Phase H | `git diff` nur Whitespace | EXIT 0 | EXIT 0 | — | — |
| Phase I | — | EXIT 0 (CWD-pwd-belegt) | — | — | — |
| R16/R17 | Workflow-Diff 1 Datei | — | — | — | echte Prüfung (Negativ-Probe) |
| Phase L | — | — | — | lesend, nur nach A–K grün | — |
| Phase M | — | — | — | — | separater Audit-Checkpoint |

`plan` steht nur bei Phase L (nach allen Gates). Kein Plan wird hier ausgeführt.

## Commit Strategy

Kleine, fachlich getrennte Commits (Plan; Anpassung nach Evidence erlaubt).
Jeder: Änderung → Check (`validate`/`fmt -check`/`grep`, CWD-pwd-belegt) →
AI_AUDITLOG-Eintrag → `git commit` (scoped `add <Pfade>`, nie `add .`) →
clean checkpoint (bis auf geschützte untracked Files):

- Commit A — Duplicate-Konsolidierung (R01–R06, R19): Parse-Fix + Stale-Removals.
- Commit B — Modul-Verträge (R10, R11, dynamodb-Args): DECLARE/REMOVE-ARG.
- Commit C — IAM/Lambda-Vertrag (R07–R09 + table_name-Klärung): REWIRE/REMOVE-DECL.
- Commit D — DynamoDB/Cognito-Rest + Format (R12/R13-Festschreibung, Phase H).
- Commit E — Validierungs-Gate (Phase I): `validate` EXIT-0-Beleg im Log.
- Commit F — CI-CWD-Gate (R16/R17, R18-Status): Workflow-Änderung + Negativ-Probe.

Keine Sammel-Commits. Untracked Vorarbeits-Dateien nie stagen.

## Rollback / Safety

Je Repair-Schritt: erwartete Dateien (1–3 .tf), erwartete Änderung (Block/Diff
vorab im Commit-Log beschreiben), lokale Validierung (s. Matrix),
Git-Checkpoint (Commit pro Schritt = atomarer Rollback-Punkt via `git revert`,
kein `reset --hard`, kein `clean` — beide explizit verboten).
Untracked-Schutz: ausschließlich scoped `git add <exakte Pfade>`; Vorab-`git
status`-Beleg je Schritt, dass die 7 Dateien unangetastet sind.
Bei Überraschung: STOP + REPORT (s. Stop-Conditions), kein eigenmächtiges
Weiterarbeiten, kein Zurücksetzen fremder Änderungen.

## Stop Conditions

HARD STOP + REPORT (kein Weiterarbeiten) wenn: Source-of-Truth widersprochen
wird (neuer Beleg gegen Matrix) · Duplicate-Definition nicht eindeutig
klassifizierbar · Contract nicht ableitbar (z. B. `table_name`-Bedarf unklar) ·
AWS State nötig wäre · IAM-Runtime nicht verifizierbar · Scope-Überschreitung
nötig wäre · untracked Files betroffen wären · `validate` nach Fix unerwartete
neue Strukturschicht zeigt · CI-Negativ-Probe ausbleibt (Gate bleibt blind).

## Unknowns

Aus Decision übernommen (gültige Endzustände): CloudTrail-Zweck, effektive
Laufzeit-Rolle, `table_arn`-Verbleib, Post-Fix-Validate, fmt-Rest,
CI-nach-CWD-Fix, `on.plan`-Laufzeit, IAM-Runtime. Zusätzlich plan-spezifisch:
ob Phase I weitere latente Schichten zeigt (einkalkuliert via STOP) und ob
`table_name`-Policy-Zeile Deklaration oder Umschreibung braucht (Repair-
Entscheidung an `validate`-Feedback, kein Raten).

## Recommended Execution Sequence

A (R19) → B (R01–R06) → C (R10/R11/Args) → D (R07–R09 + table_name) → E/F
(Festschreibung) → G (DEFER/Owner) → H (Whitespace) → I (EXIT-0-Beleg) →
J/K (CI-CWD + Negativ-Probe) → L (lesender Plan, eigener Checkpoint) → M
(Identitäts-Audit, eigener Checkpoint). Jeder Pfeil = eigener validierter
Commit (A–F). Freigabe des Plans und jedes Repairs bleiben eigene Schritte.

---

*Plan: TERRAFORM-CONSOLIDATION-REPAIR-PLAN-01 · PLANUNG ONLY · keine
Terraform-/IAM-/AWS-/CI-Änderung · kein Backend-init, kein Plan/Apply/Destroy,
kein fmt-Write · keine Datei gelöscht/verschoben/umbenannt · keine Vermutung
als Tatsache · keine untracked Datei berührt.*
