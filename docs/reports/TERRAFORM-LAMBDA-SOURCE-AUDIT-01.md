# TERRAFORM-LAMBDA-SOURCE-AUDIT-01

## STATUS: YELLOW

Lambda-Bestand vollständig identifiziert (kein Fix, keine Konsolidierung, keine
Architekturentscheidung). Eine Funktion, zwei Rollenbezüge (unentschieden),
vier Output-Duplikate, zwei reale Doppel-Ressourcen (Permission + Log-Gruppe),
ein toter Input (bereits R01-Repair: entfernt), eine ungenutzte Variable.
Laufzeitfragen explizit UNKNOWN.

## 1. Lambda variants found

Genau EIN Lambda-Modul (`terraform/modules/lambda`), EINE Funktion. "4 Varianten"
= 4 duplizierte Outputs (je Inline G0.1-Original + `outputs.tf`-Kopie G0.2).

## 2. Exact Terraform addresses/locations

- `module.lambda` ← `terraform/main.tf:87` (vollständig verdrahteter Call).
- `aws_lambda_function.agent` ← `modules/lambda/main.tf:163`.
- `aws_iam_role.lambda_execution` ← `modules/lambda/main.tf:7` (+ 5 Policies
  Z.26/73/99/121/143).
- `aws_lambda_permission.api_gateway` ← ZWEIMAL: `modules/lambda/main.tf:203`
  UND `modules/api/main.tf:81`.
- `aws_lambda_event_source_mapping.sqs_mapping` ← `modules/lambda/main.tf:211`.
- `aws_cloudwatch_log_group` ← ZWEIMAL: Root `main.tf:140` (`lambda`) UND
  `modules/lambda/main.tf:196` (`lambda_logs`), GLEICHER Name
  `/aws/lambda/${project}-${environment}-agent`.
- Outputs: `modules/lambda/main.tf:219-234` (inline) + `modules/lambda/
  outputs.tf:3-21` (Kopien).

## 3. Classification of every variant

| Variante | Adresse | Status |
|----------|---------|--------|
| function_name/invoke_arn Outputs (inline) | main.tf:219-229 | ACTIVE + CONNECTED (api-Modul + root outputs) |
| function_arn Output (inline) | main.tf:223 | ACTIVE, nur Public-Export-verbunden |
| lambda_role_arn Output (inline) | main.tf:231 | ACTIVE (Definition), UNREFERENCED (kein Consumer) |
| outputs.tf-Kopien (alle 4) | outputs.tf:3-21 | DUPLICATE (G0.2-Kopien identischer Values) |
| `aws_lambda_function.agent` | main.tf:163 | ACTIVE + CONNECTED |
| `lambda_execution` + Policies | main.tf:7-161 | ACTIVE + CONNECTED (Funktion Z.165, depends_on) |
| Permission (lambda-Modul) | main.tf:203 | ACTIVE + CONNECTED (function_name + var.api_arn) |
| Permission (api-Modul) | api/main.tf:81 | DUPLICATE (redundant; eigene Adressen → kein Plan-Konflikt, AWS-Effekt überlappend) |
| Log-Gruppe (Root) | main.tf:140 | DUPLICATE (gleicher Name wie Modul-Gruppe → Apply-Konflikt) |
| Log-Gruppe (Modul) | main.tf:196 | ACTIVE + CONNECTED (depends_on der Funktion) |
| `var.iam_role_arn` (Input) | variables.tf (ex) | Bereits R01-Repair ENTFERNT (0 Leser PROVEN); Root-Arg gleich mit |
| `var.aws_region` | variables.tf:86 | UNREFERENCED (deklariert + Default, 0 Nutzungen) |
| Restliche 16 Vars | variables.tf | ACTIVE (deklariert + konsumiert, Zählung belegt) |

## 4. Root → Lambda wiring

root → `module.lambda` (17 Inputs, alle belegt außer entferntem totem Input) →
Funktion (`role=lambda_execution`, Handler/Runtime/Timeout/Memory/Filename aus
`lambda_config`, Defaults: python3.14 / handler.lambda_handler / 30s / 128MB /
lambda.zip / 14d) → Env-Vars (4 Tabellen-Namen, Queue-URL, LOG_LEVEL) →
Outputs (s. 8). Keine Architecture-/Layer-Definition (AWS-Defaults gelten —
etablierter Vertrag, kein Befund).

## 5. Lambda → IAM wiring (kein Entscheid)

Funktion ← `lambda_execution` (einzige Bindung, Z.165). `module.iam` liefert
NICHTS an Lambda (toter Input entfernt; `main.tf:92`-Broken-Ref entfiel mit).
`iam.lambda_role` orphan-existent. Rollen-Entscheid NICHT getroffen (R20).

## 6. Lambda → SQS/API/event wiring (nur Referenzen, kein Runtime-Schluss)

- SQS: `sqs_mapping` ← `var.sqs_queue_arn` (= `module.sqs.work_queue_arn`,
  Root) + `batch_size = 5`; Funktion ← Mapping. Receive-Seite: iam-Modul?
  Nein — SQS-Receive liegt NICHT in den Lambda-Policies (nur Send);
  Worker-Leserecht-Herkunft hier NICHT belegt (kein Schluss aus Dateinamen).
- API: `integration_uri = var.lambda_invoke_arn` (api/main.tf:38) + Permission
  beidseitig (s. 3). Direkte Invocation: `invoke_arn` öffentlich exportiert.

## 7. Variable contract findings

16/18 aktiv genutzt (Zählung); `aws_region` UNREFERENCED (Default vorhanden,
harmlos); `iam_role_arn` bereits entfernt. Keine undeklarierte Nutzung im
Modul gefunden (Stichprobe aller `var.*` gegen Deklarationen — alle übrigen
gedeckt).

## 8. Output contract findings

`invoke_arn` → api + root outputs; `function_name` → root outputs (+ historisch
monitoring-Block); `function_arn` → nur root outputs; `lambda_role_arn` →
niemand. Inline = ACTIVE, `outputs.tf` = DUPLICATE (Werte identisch).

## 9. Duplicate/stale/unreferenced contracts

s. Tabelle (3): Doppel-Permission, Doppel-Log-Gruppe, Doppel-Outputs,
`aws_region`, `lambda_role_arn`-Orphan. Stale-`handler`: Lambda-seitig keine
Referenz (IAM-Scope). Kein HISTORICAL im Lambda-Modul selbst (alles G0.1+ aktiv
oder G0.2-Duplikat).

## 10. Unknowns (statisch unbeweisbar → UNKNOWN, DO NOT GUESS)

Effektive Laufzeit-Rolle (Plan/Live); SQS-Receive-Recht-Herkunft; ob doppelte
Permission/ Log-Gruppe bei Apply kollidiert oder idempotent ist (Plan nötig);
batch_size=5-Angemessenheit (Runtime); `aws_region`-Zukunft (ungenutzt).

## 11. Recommended NEXT SMALL REPAIR only

TERRAFORM-LAMBDA-CONTRACT-REPAIR-01 (nach Review): (a) `outputs.tf`-Kopien
entfernen (4 Blöcke, PROVEN identisch); (b) Doppel-Permission + Doppel-Log-
Gruppe je auf EINE Adresse zurückführen (Reihenfolge: Plan-Beleg zuerst);
(c) `aws_region` deklariert lassen oder entfernen (trivial, Owner-Entscheid).
KEIN Rollen-Eingriff, KEIN SQS/API-Redesign.

---

*Audit: TERRAFORM-LAMBDA-SOURCE-AUDIT-01 · read-only · kein init/plan/apply ·
keine AWS-Mutation · keine Datei umgeschrieben (fmt/read-only) · Mays-Orders
nur als Muster (Ein-Rollen-Verbrauch `role = var.iam_role_arn`), RIS behält
eigene Architektur.*
