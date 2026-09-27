# TERRAFORM-DYNAMODB-SOURCE-AUDIT-01

STATUS: YELLOW

## 1. Audit Metadata

- Date/time: 2026-09-26 17:25 UTC
- Branch: main
- HEAD: 7c381a1 (`fix(terraform): repair Cognito contracts`; Vorgänger b5a2703/21cc04a/c34e1e9 unangetastet)
- Previous checkpoint: TERRAFORM-COGNITO-CONTRACT-REPAIR-01
- Git status: 0 modified, 7 untracked (unberührt); genau 1 Audit-Log
- AWS mutation: NONE (read-only; kein init/plan/apply, kein Backend/Provider-Setup)

## 2. Variant Inventory

| Variant | Location | Terraform address | Classification | Evidence |
|---------|----------|-------------------|----------------|----------|
| Inline-Outputs (10, alle Tabellen name+arn) | modules/dynamodb/main.tf:157-167+ | `module.dynamodb.*_table_{name,arn}` | ACTIVE (G0.1-Originale, korrekte Ziele) | `-S`-Historie G0.1; Ressourcen existent |
| outputs.tf-Kopien (10, identische Values) | modules/dynamodb/outputs.tf:3-41 | dto. Namen | DUPLICATE (c83e3a2-Neuanlage, keine Abweichung) | Erzeugungs-Commit; Wert-Vergleich identisch |
| Call-Arg-Schicht (environment/table_config) | terraform/main.tf (dynamodb-Call) | — | BROKEN als Vertrag (unproven als Bedarf? Bedarf PROVEN, s. §6) | undeklariert übergeben + genutzt |

"3 Varianten" = Inline vs. Kopie vs. Call-Args. Kein historischer Zweit-Pool (Referenz-belegt, nicht aus Namen geraten).

## 3. Table Inventory (physisch je `${project}-${environment}-<suffix>`)

| Logisch | Physisch | PK/SK | GSIs | Billing | TTL | SSE/PITR/Delete-Prot |
|---------|----------|-------|------|---------|-----|----------------------|
| work_items | `…-work-items` | workId (S), kein SK | gsi-status (tenantId/status, ALL) | On-Demand | via `var.table_config` | keine Blöcke (Defaults) |
| agent_state | `…-agent-state` | key (S), kein SK | keine | On-Demand | expiresAt/true (hart) | keine Blöcke |
| user_profile | `…-user-profile` | userId (S), kein SK | gsi-tenant (tenantId, ALL) | On-Demand | expiresAt/true (hart) | keine Blöcke |
| agent_catalog | `…-agent-catalog` | agentId (S), kein SK | gsi-status (status, ALL) | On-Demand | expiresAt/true (hart) | keine Blöcke |
| entitlements | `…-entitlements` | entitlementId (S), kein SK | gsi-user (userId), gsi-agent (agentId), ALL | On-Demand | expiresAt/true (hart) | keine Blöcke |

LOGICAL vs. PHYSICAL: 5 logische Tabellen = 5 physische AWS-Tabellen (kein
Shared-Table). `gsi-status` existiert auf ZWEI Tabellen (work_items,
agent_catalog) — unkritisch (GSI-Namen gelten pro Tabelle). Keine LSIs.

## 4. Root → DynamoDB Wiring

root (`project_name`, `environment`, `table_config`, `tags`) → Modul (5 Tabellen)
→ Consumer: Lambda-Env (4 Namen: work/agent_catalog/entitlements/user_profile —
NICHT agent_state), Lambda-Policies (Plattform-ARNs + Work-ARNs), Root-Outputs
(10 explizite `dynamodb_*`). `agent_state` hat KEINEN Terraform-Consumer
(s. §9).

## 5. Key Schema Contract

Je Tabelle: PK deklariert + typisiert (alle S); Attribute für GSI-Keys
mitdeklariert (tenantId/status/userId/agentId); `key_schema` passt zu
`attribute`-Blöcken (je geprüft, keine Widersprüche). Keine Sort-Keys
irgendwo. Keine widersprüchlichen Varianten derselben Tabelle.

## 6. GSI Contract

gsi-status (work_items: tenantId+status), gsi-tenant (user_profile: tenantId),
gsi-status (agent_catalog: status), gsi-user/gsi-agent (entitlements) — alle
`projection_type = "ALL"`, Adressen in Moduldatei, keine externen GSI-Refs.
`gsi1pk`/`gsi1sk`-Vertrag: NULL-Beleg (Grep über tf/py außerhalb Audit-Doku +
Monitoring-Kommentar leer) — der iam-seitige `dynamodb_gsi1_arn`-Bedarf hat
KEIN Gegenstück auf Tabellen-Seite (PROVEN nicht-existent, nicht "invalid").

## 7. Variable Contract

Modul deklariert: `project_name`, `tags` (beide konsumiert). Root übergibt
zusätzlich `environment` + `table_config`: UNDEKLARIERT, aber BEIDE genutzt
(`environment` 5× Tabellennamen; `table_config` work_items-TTL Z.24-25) →
DECLARED+CONSUMED fehlt, REFERENCED+UNDECLARED trifft zu; Bedarf PROVEN
(Namen/TTL hängen dran). Root-`table_config`-Default vorhanden
(`{ttl_enabled=true, ttl_attribute="expiresAt"}`). Keine Duplikate, kein
weiterer Stale-Fund. Repair offen (eigener Checkpoint).

## 8. Output Contract

- CONSUMED: alle 10 (Lambda-Env/Policies via Namen+ARNs; Root-Outputs).
- EXPORTED (root, explizit): alle 10 `dynamodb_*` (c34e1e9-Konsolidierung).
- DUPLICATE: outputs.tf-Kopien (10, identisch).
- STALE/BROKEN/UNKNOWN: keine (alle Adressen existent).
- NICHTS entfernt (Audit).

## 9. Consumer Map

- PROVEN CONSUMER: Lambda-Env (4 Namen), Lambda-Policies (Plattform + Work),
  Root-Outputs (10), Handler-Code (`_get_user_profile/_get_entitlements/
  _get_agent_catalog`, tenantId-scoped), api-Modul indirekt (via Lambda).
- `agent_state`: KEIN Terraform-/Code-Consumer gefunden (Grep: nur
  Definition + Outputs) — UNREFERENCED als Nutzung (Ressource ACTIVE).
- DOCUMENTATION ONLY: Backup-/Audit-Doku (PITR-Behauptungen s. §13).
- tests/test_platform_handlers.py: nutzt Tabellen-Namen (Test-Abhängigkeit
  beachten).
- HISTORICAL: `table_arn`-G0.1-Call (nicht mehr existent).

## 10. IAM / Lambda Relationship (nur Referenzen, R20 offen)

iam-Modul: `dynamodb_table_arn`-Input (= work_items-ARN) + Policy-Dokumente;
`table_name`-Lücke (Repair-Beleg aus IAM-Checkpoint). Lambda: Env-Namen (4),
Policy-ARNs (Plattform-Tabellen + Work). KEINE direkte Cognito/SQS-Kante auf
Tabellen-Ebene. Keine Änderung, keine Bewertung.

## 11. SQS / Processing Relationship (nur Evidence)

SQS-Mapping → Lambda → Handler liest/schreibt Tabellen (Profil/Entitlements/
Katalog per userId/tenantId/agentId; Work-Items via WORK_ITEMS_TABLE-Env).
`agent_state` ohne belegten Processing-Pfad. Keine Runtime-Semantik aus Namen
abgeleitet.

## 12. Findings

PROVEN: Tabellen/Keys/GSIs/TTL oben; Kopien identisch; Env-/table_config-
Doppellage (Arg + Nutzung, keine Deklaration); `gsi1*`- Nichtexistenz;
Consumer-Kette; agent_state ohne Consumer; Mays-Orders-Muster (Single-Table
`orders`, pk/sk, On-Demand — Vergleich, kein Vorbildzwang).
UNPROVEN: Apply-Verhalten der Duplikate (Plan nötig); ob `agent_state`
bewusst reserve ist (Absicht unbelegt).
UNKNOWN: Laufzeit-Tabellenstände (kein Lookup, DO NOT GUESS).

## 13. Contract Problems

- Undeklarierte Args (`environment`, `table_config`): PROVEN (Call + Nutzung
  vs. Var-Datei).
- `gsi1`-Vertrag ohne Tabellen-Seite: PROVEN (kein Gegenstück).
- Backup-Doku behauptet PITR ("PITR enabled") — im Modul KEIN `point_in_time_
  recovery`-Block: Doku-vs-Code-DIVERGENZ (PROVEN, kein Urteil über AWS-Seite).
- Keine Key-Schema-Widersprüche, keine Namens-Kollisionen (PROVEN ok).
- Reparatur fehlt überall absichtlich (Audit) — kein Ersatz erfunden.

## 14. Candidate Next Small Repair (nach Review, NICHT hier)

TERRAFORM-DYNAMODB-CONTRACT-REPAIR-01: (a) outputs.tf-Kopien entfernen (10
Blöcke, PROVEN identisch); (b) `environment` + `table_config` nach
Modul-Konvention deklarieren (Typen aus Nutzung/Root-Default, keine Erfindung);
(c) `agent_state`-Nutzung klären (Owner) BEVOR etwas daran geschieht. KEINE
Tabellen-/Key-/GSI-/TTL-Änderung.

## 15. Risks

PITR-Divergenz (Doku vs. Code — Klärung nötig, kein Eingriff); `agent_state`
ohne Consumer (Löschen VERBOTEN ohne Owner); Duplikate blockieren validate
nach Init-Schicht.

## 16. Resume Point

Audit committet (s. Commit); wartet auf Review vor
TERRAFORM-DYNAMODB-CONTRACT-REPAIR-01. Keine Implementierungsänderung erfolgt;
`terraform/`-Diff leer.

---

*Audit: TERRAFORM-DYNAMODB-SOURCE-AUDIT-01 · read-only · Muster aus
AI_AUDITLOG.md (Mandatory-Felder) · Mays-Orders nur Vergleich (Single-Table
vs. RIS-5-Tabellen — RIS-Modell bleibt).*
