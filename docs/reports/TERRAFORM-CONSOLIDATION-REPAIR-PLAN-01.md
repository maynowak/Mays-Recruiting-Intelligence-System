# TERRAFORM-CONSOLIDATION-REPAIR-PLAN-01

## Status

**GREEN** — Verbindlicher Plan vollständig: R01–R21 mit Risiko + Commit,
Block-Aktionen mit Dependency-Check, Phasen 0–9, Gates G1–G11, Rollback,
Commit-Strategie, Stops, Final State. PLANUNG ONLY — keine Implementierung.

## Objective

Verbindlicher, evidenzbasierter Reparaturplan für die Terraform-Konsolidierung
auf Basis der formalen Decision 9d5b603. Kein Terraform-/IAM-/AWS-/CI-Eingriff.

## Evidence Basis

Gelesen (exakte Ticket-Namen, alle vorhanden): DECISION-01 (9d5b603,
verbindlich), CONSOLIDATION-SOURCE-AUDIT-01, INTEGRITY-AUDIT-01,
DEPLOY-PERMISSION-AUDIT-01, AI_AUDITLOG.md. Konsistenzprüfung: keine
Inkonsistenz zwischen den Reports entdeckt (SoT-Mengen identisch,
Herkunftsketten widerspruchsfrei) → keine SoT-Frage erneut geöffnet.
Fehlendes bleibt UNKNOWN (nicht ergänzt/geraten).

## Repository Baseline

Canonical Repo, `main`, HEAD `9d5b603` (erwarteter Stand, verifiziert —
nicht blind übernommen), SSH-Remote, 0 modified, 7 untracked
Vorarbeits-Dateien (geschützt). Kein clean/reset.

## Source-of-Truth Dependency

Verbindlich übernommen (ACTIVE ≠ fehlerfrei; ACTIVE = Reparaturbasis):
ACTIVE: `terraform/`-Root, Root-`outputs.tf`, IAM role/`role_arn`, aktive
Lambda-/Cognito-/DynamoDB-Strukturen, SQS, API, `table_config`-Bedarf.
STALE: Root-Inline-Kopien, Modul-`outputs.tf`-Kopien, `lambda_role_arn`,
handler-Familie, Boundary-Varianten, `dynamodb_gsi1_arn`,
Cognito-`environment`, CI-Schutzbehauptung. HISTORICAL: Monitoring-Block,
`table_arn` (Verbleib UNKNOWN). UNKNOWN: CloudTrail, effektive Runtime-Rolle,
`table_arn`-Verbleib, Post-Fix-Validate, CI-nach-Fix, `on.plan`, IAM-Runtime.

## Repair Matrix

| ID | Problem | Source of Truth | Geplante Änderung | Risiko | Validation | Commit |
|----|---------|-----------------|-------------------|--------|------------|--------|
| R01 | Root Duplicate Outputs (5) | ACTIVE outputs.tf / STALE Inline main.tf:187-209 | REMOVE-STALE: 5 Inline-Blöcke (kein Blind-Delete; outputs.tf bleibt) | NIEDRIG (Values identisch, keine externen Consumer belegt) | `validate` Root-Fehler weg; `grep ^output <name>` 1× | 1 |
| R02 | IAM outputs.tf duplicates | ACTIVE Inline main.tf:87-93 / STALE outputs.tf (`role_arn`/`role_name` widersprüchlich, `policy_name` orphan) | REMOVE-STALE: 3 Blöcke nach Consumer-Grep | NIEDRIG-MITTEL (widersprüchliche Ziele → Grep zuerst) | Modulebene in `validate` erreicht | 1 |
| R03 | Lambda outputs.tf duplicates | ACTIVE Inline (G0.1) / STALE Datei-Kopie (G0.2) | REMOVE-STALE: 4 Blöcke | NIEDRIG (identisch, `invoke_arn`-Consumer via Moduladresse unberührt) | dto. | 1 |
| R04 | Cognito outputs.tf duplicates | ACTIVE Inline / STALE Kopie (c83e3a2) | REMOVE-STALE: 3 Blöcke | NIEDRIG | dto. | 1 |
| R05 | DynamoDB outputs.tf duplicates | ACTIVE Inline / STALE Kopie | REMOVE-STALE: duplizierte Blöcke | NIEDRIG | dto. | 1 |
| R06 | IAM role_arn Contract | ACTIVE `role_arn` / STALE `lambda_role_arn`-Erwartung | REWIRE main.tf:92 + outputs.tf:37-38 auf `module.iam.role_arn`; keine neue Rolle/Policy/Boundary | MITTEL (Vertragsänderung, 2 Stellen) | `unsupported attribute` weg | 3 |
| R07 | stale handler references (3) | CONFIRMED STALE (nie existent) | REMOVE candidate nach Referenz-Grep (keine aktiven Consumer belegt; bei Fund STOP/DEFER) | NIEDRIG (tote Refs, derzeit parse-maskiert) | `grep handler` terraform/ leer (außer Doku) | 1 |
| R08 | stale boundary variables | STALE (`permissions_boundary`, `dynamodb_gsi1_arn`: 0 Referenzen) | REMOVE candidate (Deklarationsblöcke) nach Grep-Beleg; `var.dynamodb_table_name`-Lücke (iam/main.tf:15, undeklariert) als Repair-Entscheidung am validate-Feedback | NIEDRIG (Deklaration) / OFFEN (table_name) | `required variable`/`undeclared` weg | 3 |
| R09 | DynamoDB GSI1 contract | STALE (real gsi-status/gsi-tenant/+1; Vertrag ungefüttert) | Keine Aktion über R08 hinaus; bei aktivem Consumer im Repair → REPAIR CONTRACT, sonst erledigt | KEINS | `grep gsi1_arn` leer | 3 |
| R10 | DynamoDB table_config | Bedarf ACTIVE; Root-Default vorhanden; Modul-Deklaration fehlt | DECLARE im Modul (Objekttyp = Root-Default `{ttl_enabled,ttl_attribute}` — keine Werte-Erfindung); Call-Kette Caller→Input→Variable→Resource (main.tf:24-25) belegt | NIEDRIG-MITTEL (neue Deklaration) | undeclared/unsupported weg | 3 |
| R11 | Cognito environment | STALE (totes Arg) | REMOVE-ARG (1 Root-Call-Zeile); keine Variable wiederherstellen | NIEDRIG | `validate` | 3 |
| R12 | variables.tf / formatting | Parse-Fehler (Syntax, kein Stil): Newline nach `default = "dev"` fehlt (Z.17/18) | Minimal-Edit (1 Zeichen); kein `fmt`-Write im Plan; später minimal edit → `fmt -check` → `validate` | MINIMAL | Parse-Stufe passiert (validate + fmt) | 1 |
| R13 | CI Terraform CWD | Workflow ACTIVE; CWD nicht gesetzt | REWIRE (geplant): `terraform/` als Working Directory aller Terraform-Steps (Detail im Repair); EIGENER Checkpoint, nicht mit Code-Repair vermischt | MITTEL (macht blindes Grün ehrlich rot/grün) | CI-Log zeigt echte Prüfung | 4 |
| R14 | CI validate gate | Blind (STALE als Schutz) | Geheilt via R13 + Negativ-Probe (kaputtes Fixture → rot erwartet) | MITTEL | Gate schlägt bei Fehlern an | 4 |
| R15 | CI fmt gate | dto. | dto. | MITTEL | dto. | 4 |
| R16 | CI plan gate | dto. (plus Backend-init nötig) | dto.; `plan` nur nach A–K grün | MITTEL | Plan-Artefakt lesbar | 4 |
| R17 | CloudTrail | UNKNOWN | DEFER UNTIL EVIDENCE (NO REPAIR/DELETE/RESTORE/ENABLE) | KEINS (keine Aktion) | keine Code-Änderung | — |
| R18 | Monitoring | HISTORICAL/UNCONNECTED | DEFER / EXPLICIT ARCHITECTURE DECISION (Inline-CloudWatch KEEP; Dateien weder löschen noch reaktivieren) | KEINS | keine | — |
| R19 | table_arn | HISTORICAL, Verbleib UNKNOWN | DEFER; keine neue table_name/table_arn-Struktur erfinden | KEINS | keine | — |
| R20 | effective IAM Runtime Role | NOT REACHED/UNKNOWN | Keine Runtime-Reparatur, keine Policy-Erweiterung; erst nach validate→plan→Identity-Verification (eigener Audit-Checkpoint) | KEINS (hier) | — | — |
| R21 | on.plan | NOT VERIFIED | Separater CI-Trigger-Audit falls nach CWD-Fix relevant; keine Triggeränderung | KEINS | DEFER | — |

## Root Output Repair

Je der 5 Outputs: authoritative Definition (`outputs.tf`, G0.1), stale
Definition (Inline `main.tf`, G0.2-Diff), Consumer (keine externen; CLI/Show),
geplante Änderung (Inline-Block entfernen), Validierung (s. R01). Kein
"delete outputs.tf" — die aktive Datei bleibt. `lambda_functions` kam erst mit
der stale Schicht (belegt) — fällt mit ihr.

## Module Output Repair

iam/lambda/cognito/dynamodb: Outputs + Consumer + Output-/Resource-Referenzen
je Modul geprüft (Evidence §§E8–E13 der Audits). Ergebnis: Inline KEEP,
`outputs.tf`-Kopien REMOVE (R02–R05), `policy_name`-Orphan REMOVE (R07),
`function_arn`-Orphan KEEP (ACTIVE-Definition, ungenutzt — kein Eingriff).
DEFER-Regel: bei nicht eindeutig überprüfbarem Consumer → DEFER statt REMOVE.

## IAM / Lambda Contract Repair

CURRENT Provider `module.iam` / Output `role_arn` / Broken Consumer
`module.iam.lambda_role_arn` (2 Stellen) / TARGET `role_arn`-Vertrag.
Änderung: REWIRE (R06). Gleichzeitig: Doppel-Rolle dokumentiert
(`iam.lambda_role` orphan-existent vs. `lambda.lambda_execution` angebunden) —
keine Rollen-Entscheidung im Repair ohne Live-Evidenz (R20). Keine Policy-
Expansion, keine neuen Permissions, keine Boundary-Ergänzung (verboten).

## DynamoDB Contract Repair

`dynamodb_gsi1_arn` REMOVE-Kandidat (R09: Consumer/ Input/Output/GSI/IAM-Refs
alle NULL belegt). `table_config`: Call-Kette Root-Var (Default vorhanden) →
Modul-Input (fehlt) → Variable (fehlt) → Resource-Nutzung (aktiv): DECLARE
(R10). NICHT "Variable ergänzen damit grün" — Bedarf ist belegt (TTL-Nutzung),
Typ aus bestehendem Default gespiegelt. Widerspruchsfrei (kein Gegenbeleg).

## Cognito Contract Repair

CURRENT: Caller übergibt `environment`; Modul deklariert nur
`project_name`/`tags`; keine Resource-Nutzung. PLANNED: REMOVE-ARG (R11).
Keine neue Variable. VALIDATION: `validate`.

## Variables / Formatting Repair

A) Syntax/Parsing: JA (blockiert alles). B) Newline: die 1-Zeichen-Ursache.
C) Semantik: nein (Validation-Block bleibt). D) Contract: separat (R10/R11).
Änderung: Z.17/18 Newline. Validierung: `fmt -check` erreicht echte Prüfung +
`validate` passiert Parse-Stufe.

## CI Working Directory Repair

CURRENT: kein CWD (alle Steps Root). TARGET: `terraform/` für validate/fmt/
plan/deploy + `init` davor im korrekten Root. VALIDATION: CI-Log-Beleg echter
Prüfung. Eigener Checkpoint (Commit 4), nicht mit Code-Repair vermischt.

## CI Gate Repair

Nach CWD-Fix: validate-/fmt-/plan-Gates mit Negativ-Probe (R14–R16). `plan`
braucht Backend-init (belegt via Plan-Job) — kein Backend-`init` in diesem
Plan-Checkpoint ausgeführt.

## Deferred UNKNOWN Areas

R17/R18/R19/R20/R21: DEFER mit Owner-Bedarf (CloudTrail-Zweck, effektive Rolle,
`table_arn`-Verbleib, Post-Fix-Validate, on.plan-Laufzeit). Kein Code, keine
Platzhalter-Architektur.

## Repair Order

- PHASE 0 — Baseline/Git-Safety: Status-Beleg, untracked-Schutz, `terraform/`-Diff leer.
- PHASE 1 — Root structural repair: R12 (zuerst — belegt ALLES blockierend) → R01.
- PHASE 2 — Module output consolidation: R02–R05 + R07 (gleiche Fehlerschicht).
- PHASE 3 — Module contracts: R06/R08 (REWIRE/REMOVE-DECL + table_name-Entscheid),
  R10 (DECLARE), R11 (REMOVE-ARG).
- PHASE 4 — Static validation: `fmt -check` (echte Prüfung) + `validate` EXIT-0-Ziel.
- PHASE 5 — CI CWD (R13, eigener Checkpoint).
- PHASE 6 — CI validate/fmt gates (R14/R15 + Negativ-Probe).
- PHASE 7 — CI plan gate (R16).
- PHASE 8 — Terraform plan (lesend, eigener Checkpoint, nur nach Phase 4–7 grün).
- PHASE 9 — AWS identity / IAM runtime audit (R20, eigener Checkpoint).
- UNKNOWN (R17–R19, R21) außerhalb der Sequenz bis Evidence.
- Begründung aus Evidence (nicht Allgemeinwissen): Parse-Fehler abortet alle
  Operationen → Phase 1 zuerst; `validate` meldet schichtweise (Root → Module →
  Contracts) → Phasen 2–3 in dieser Reihenfolge; CI-CWD erst nach lokalem Grün,
  damit Gates nie vakuos-lügen (Phasen 5–7).

## Validation Gates

| Gate | Voraussetzung | Check | Erfolg | Hard Stop |
|------|---------------|-------|--------|-----------|
| G1 | — | `git status` clean-Checkpoint (bis auf geschützte untracked) | Beleg je Schritt | untracked betroffen → STOP |
| G2 | Phase 0 | Static source check (`grep`-Zählungen) | Duplikat-Zähler sinken wie geplant | unerwartete Treffer → STOP |
| G3 | Phase 1–3 | `fmt -check` (CWD-pwd-belegt) | EXIT 0 | neue Parse-Schicht → STOP |
| G4 | G3 | `terraform validate` | EXIT 0 | neue Strukturschicht → STOP |
| G5 | G4 | CI CWD check (Workflow-Diff + Log-Pfad) | Steps laufen in `terraform/` | Scope-Bruch → STOP |
| G6 | G5 | CI validate | echt grün (Negativ-Probe bestanden) | blind → STOP |
| G7 | G5 | CI fmt | dto. | dto. |
| G8 | G6+G7 | CI plan | Artefakt lesbar | Backend-Zwang ohne Freigabe → STOP |
| G9 | G8 | Terraform plan (lesend) | keine unerwarteten Diffs ohne Owner | Überraschung → STOP |
| G10 | G9 | AWS identity (lesend) | Identität bekannt | Mutation nötig → STOP |
| G11 | G10 | IAM deploy permissions | Abgleich möglich | Runtime nötig ohne Checkpoint → STOP |

Kein späteres Gate erfolgreich ohne vorheriges (strikte Sequenz).

## Commit Strategy

Getrennte Commits (Anpassung nach Evidence erlaubt): Commit 1 `terraform: repair
root configuration` (R12+R01+R02–R05+R07) · Commit 2 `terraform: consolidate
module outputs` (falls B/C-Trennung nötig, sonst in 1) · Commit 3 `terraform:
repair module contracts` (R06/R08/R10/R11) · Commit 4 `ci: scope terraform
gates to terraform root` (R13–R16). Je: Änderung → Validation → AI_AUDITLOG →
Commit → Status → HARD STOP. Keine Sammel-Commits.

## Rollback Safety

Je Schritt: erwartete Dateien (1–3 .tf / 1 Workflow), erwartete Diff-Größe
(Blöcke/Zeilen vorab benannt), erwartete Validation (Matrix), Rollback via
`git revert` des Schritt-Commits (atomar). Verboten als Standard: `git reset
--hard`, `git clean`. Untracked-Schutz: nur scoped `git add <Pfade>` + Status-
Beleg je Schritt.

## Stop Conditions

HARD STOP + Report + AI_AUDITLOG + Commit bei: SoT-Widerspruch (neuer Beleg) ·
aktiver Consumer einer STALE-Struktur gefunden · UNKNOWN für Reparatur
erforderlich · neue Architektur nötig · AWS State nötig · IAM-Runtime nötig ·
Backend-Zugriff nötig · CI-Scope-Bruch · untracked betroffen · `validate` zeigt
neue Strukturschicht. Kein eigenmächtiges Weiterarbeiten.

## Expected Final State

`terraform/` eindeutiger Root; EINE autoritative `outputs.tf`; je Modul EINE
Output-Struktur (Inline-Originale); IAM `role_arn`; Lambda am IAM-Contract;
DynamoDB konsistent (GSI/Tabelle ohne Phantom-Vertrag, `table_config`
deklariert); Cognito konsistent (ohne Phantom-Arg); CI mit explizitem
`terraform/`-CWD; `fmt -check` + `validate` PASS. Danach CI-Plan, danach
AWS-Identity/IAM-Audit. Keine Aussage, dieser Zustand sei erreicht (ist er
nicht — PLANUNG ONLY).

## Next Checkpoint

Repair-Freigabe + Phase-0/1-Ausführung (Commit 1) als eigener Checkpoint mit
eigenem AI_AUDITLOG-Eintrag. Freigabe bleibt eigene Entscheidung.

---

*Plan: TERRAFORM-CONSOLIDATION-REPAIR-PLAN-01 (verbindlich, R01–R21) ·
PLANUNG ONLY · keine Terraform-/IAM-/AWS-/CI-Änderung · kein Backend-init,
kein Plan/Apply/Destroy, kein fmt-Write · keine Datei gelöscht/verschoben/
umbenannt · keine untracked Datei berührt.*
