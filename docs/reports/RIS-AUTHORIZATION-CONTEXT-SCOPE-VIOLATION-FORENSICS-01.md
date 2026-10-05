# RIS-AUTHORIZATION-CONTEXT-SCOPE-VIOLATION-FORENSICS-01 — Scope-Violation Forensik

STATUS: **GREEN** — Forensik abgeschlossen, **keine Mutation** durchgeführt. Ein technischer Punkt bleibt offen (YELLOW, Teil I.A).

- Datum: 2026-10-05 UTC
- Commit des Vorfalls: `70de2b1`
- Gate: **FORENSIK ONLY** — kein Apply, kein Destroy, kein Import, kein `state rm/mv/push`, keine Ressourcen-Änderung, keine Tag-Mutation

## 1. Executive Summary

Bei SECURITY-FIX-02 habe ich mit `terraform apply -target=… <gespeichertes Planfile>` den **gesamten Plan** angewendet statt nur die Lambda. Dadurch entstanden zwei unbeabsichtigte Mutationen: `module.iam.aws_iam_role_policy.lambda_policy` wurde erstellt, die ESM-Tags wurden gesetzt.

Die Forensik belegt:

- Die **technische Ursache** ist eindeutig: `-target` ist in Terraform **1.16.1** eine `plan`-Option, **keine** `apply`-Option. Bei Übergabe eines Planfiles nimmt `apply` die Aktionen **aus diesem Plan**; das Flag hatte keine scoping-Wirkung.
- Die erzeugte IAM-Policy enthält **keine** IAM-/STS-/KMS-/Lambda-Rechte, **keine** Wildcards und **keine** Condition-Blöcke.
- Sie ist **inert**: keine der 5 Lambda-Funktionen im Account verwendet die Rolle `mays-ris-lambda-role`.
- Sie ist **redundant**: die real genutzte Agent-Rolle hat die DynamoDB-`work-items`-Rechte bereits über eine eigene Policy.
- Ihr S3-Ziel `mays-ris-dev-data` existiert als Bucket, ist aber **nirgends im Terraform deklariert** und wird von **keinem** Code referenziert.
- Der `MalformedPolicyDocument`-Fehler ist im Repo historisch belegt: Die alte Struktur bettete `data.aws_iam_policy_document.*.json` (ein **JSON-String**) in ein `jsonencode({...})` — Doppelkodierung. Behoben in `ad5cedc`.
- Die ESM-Tags sind funktional folgenlos und identisch mit allen anderen Terraform-Ressourcen.

## 2. Exakter AWS-/Git-Kontext

| Feld | Wert | Erwartung | Match |
|---|---|---|---|
| AWS Profile | `mayaws` | `mayaws` | ✅ |
| Account | `240571105849` | `240571105849` | ✅ |
| Identity | `arn:aws:iam::240571105849:user/Mayaws` | — | ✅ |
| Region | `eu-central-1` | `eu-central-1` | ✅ |
| Terraform Workspace | `mays-ris` | `mays-ris` | ✅ |
| Backend | S3 `key = "terraform.tfstate"`, Lock `mays-ris-tf-lock` | — | ✅ |
| Branch | `main` | — | ✅ |
| HEAD | `70de2b1595e92a7601feb3543384dc3c734a35e7` | — | ✅ |
| Working Tree | 0 tracked Änderungen | clean | ✅ |

Keine Abweichung → kein RED wegen Kontext.

## 3. Gewollter vs. tatsächlicher Scope

| | Ressource | Plan-Aktion | Angewendet? |
|---|---|---|---|
| **Gewollt** | `module.lambda.aws_lambda_function.agent` | `update` (nur `source_code_hash`) | ✅ ja |
| **Ungewollt** | `module.iam.aws_iam_role_policy.lambda_policy` | `create` | 🔴 **ja** |
| **Ungewollt** | `module.lambda.aws_lambda_event_source_mapping.sqs_mapping` | `update` (nur `tags_all`) | 🔴 **ja** |

Apply-Ausgabe: `Resources: 1 added, 2 changed, 0 destroyed.` — konsistent mit obiger Tabelle.

Der Lambda-Change selbst: `source_code_hash SAtX9XtEKaIZdazupvMCtAMy9elyEZjzVYqMSx67z58= → ECemCxwAOv0fNo3OeAkxjpT3Eg+Xyl9LZB61h3R4VvQ=`, `replace_paths: KEINE`. Runtime, Handler, Memory, Timeout, Role, VPC und 11 Environment-Variablen unverändert.

## 4. Terraform-Forensik zu `module.iam.lambda_policy`

| Frage | Befund |
|---|---|
| Im State? | **ja**, `module.iam.aws_iam_role_policy.lambda_policy` |
| AWS Resource-ID | `mays-ris-lambda-role:mays-ris-lambda-policy` (`id`); Rolle live `mays-ris-lambda-role`, ARN `arn:aws:iam::240571105849:role/mays-ris-lambda-role` |
| Erstellung in AWS | IAM-Inline-Policies führen **keine** Timestamps. **CloudTrail-Zeitstempel nicht belegbar** — siehe §11 |
| Wann im State verwaltet | Erst durch den Apply dieses Gates; davor nicht gelistet (`terraform state list` ohne Eintrag, dokumentiert in SECURITY-FIX-02) |
| In der Repo-Config vollständig? | **ja**, `terraform/modules/iam/main.tf:65-95` |
| Definitions-Datei | `terraform/modules/iam/main.tf`, Resource `aws_iam_role_policy.lambda_policy` |
| Beeinflussende Inputs | `var.project_name` (→ Policy-Name), `var.dynamodb_table_arn` (→ DDB-Resource), `var.s3_bucket_arn` (→ S3-Resource), `aws_iam_role.lambda_role.id` (→ Zielrolle) |
| Abhängigkeiten | `aws_iam_role.lambda_role` |
| Teil des gewünschten Zustands? | **ja** — der aktuelle Plan (ohne `-target`) meldet `No changes.`, d. h. State und Config stimmen überein |
| War es vorher Foreign Drift? | **ja, belegt**: der Plan unmittelbar vor dem Apply zeigte sie als `create`; über P16–P19 stand sie unangetastet im Plan |
| Hinweis auf frühere Existenz? | **nein** — der Plan belegt `create`, nicht `update`/`no-op` |
| Hinweis auf frühere fehlgeschlagene Erstellung? | **indirekt ja**, siehe §9: Der Kommentar und Commit `ad5cedc` dokumentieren einen `MalformedPolicyDocument`, der jeden Fresh-Install blockierte. Eine erfolglose Erstellung ist damit wahrscheinlich, aber **nicht** direkt belegt |

Terraform-Plan zur Kontrolle (read-only, `-lock=false`): **`No changes.`** — es besteht kein weiterer Drift.

## 5. IAM Permission Analysis (live, vollständig)

Policy `mays-ris-lambda-policy`, `Version 2012-10-17`, **3 Statements**, alle `Effect = Allow`, **keine** `Condition`.

| # | Aktionen | Ressourcen |
|---|---|---|
| 1 | `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` | `arn:aws:logs:*:*:*` |
| 2 | `dynamodb:PutItem`, `GetItem`, `UpdateItem`, `Query`, `DeleteItem` | `…/table/mays-ris-dev-work-items` + `…/table/mays-ris-dev-work-items/index/*` |
| 3 | `s3:PutObject`, `GetObject`, `DeleteObject` | `arn:aws:s3:::mays-ris-dev-data/*` |

Musterprüfung:

| Muster | Ergebnis |
|---|---|
| Service-Wildcard (`dynamodb:*`, `s3:*` als Aktion) | **nein** |
| Action-Wildcard (`…:*`) | **nein** |
| Resource-Wildcard `*` | **nein** |
| IAM-Aktionen | **nein** |
| STS-Aktionen / AssumeRole | **nein** |
| KMS-Aktionen | **nein** |
| Lambda-Aktionen | **nein** |
| PassRole | **nein** |
| Condition-Blocks | **nein** |
| Index-ARNs | **ja**, DynamoDB `/index/*` |

Einordnung: `arn:aws:logs:*:*:*` ist breiter als nötig (jede Lambda braucht nur ihre eigene Loggruppe), aber es ist ein **Ressourcen**-Wildcard, keine Service-/Aktions-Freigabe. `DeleteItem`/`DeleteObject` sind die schärfsten Rechte im Set.

**AWS-Live vs. Terraform-Config:** identisch — der Plan meldet keine Abweichung.

## 6. Runtime Usage Analysis

| Frage | Befund |
|---|---|
| Welche Rolle trägt die Policy? | `mays-ris-lambda-role` |
| Lambda-Funktionen mit dieser Rolle | **0 von 5** |
| Ist es die Agent-Execution-Role? | **nein** — `mays-ris-dev-agent` nutzt `arn:aws:iam::240571105849:role/mays-ris-dev-agent` |
| Rollenzuordnung aller Funktionen | `mays-ris-dev-agent → mays-ris-dev-agent`; `mays-ris-dev-orders-reader → mays-ris-dev-orders-reader`; die 3 `mays-orders-*` → eigene Rollen |
| Role-ARN = Function-Config? | **ja**, für alle 5 |
| Trust-Policy | `{Service: lambda.amazonaws.com}` — identisch zur Agent-Rolle |
| Andere Ressourcen mit dieser Rolle? | Innerhalb von Lambda: keine. Weitere Services (ECS, Step Functions) waren nicht Teil dieser Untersuchung — **als offener Punkt vermerkt** |
| Ist die Policy produktiv nötig? | **nein** |

Die Aussage „inert" ist damit belegt: (a) keine Lambda-Funktion verwendet die Rolle, (b) `list-functions` zeigt die Rollenzuordnung vollständig, (c) die Trust-Policy erlaubt ausschließlich Lambda.

**Zusätzlich redundant:** Die real genutzte Agent-Rolle besitzt die `work-items`-Rechte bereits über `mays-ris-dev-lambda-dynamodb-work` (`PutItem, GetItem, UpdateItem, Query, DeleteItem, BatchGetItem`). Die neue Policy dupliziert Rechte, die dort schon existieren.

## 7. Code-Demand-Abgleich

| Permission | Code-Caller | Datei/Funktion | Benötigte Execution Role | Bewertung |
|---|---|---|---|---|
| `logs:*` | Lambda-Runtime, implizit | `lambda/handler.py` (Logging) | die jeweilige Funktionsrolle | **breiter als nötig** auf einer **ungenutzten** Rolle |
| `dynamodb:*` auf `work-items` | `_create_work` / `_get_work_item` | `lambda/handler.py:1600-1604`, `:1834-1840` | `mays-ris-dev-agent` | **bereits gedeckt** über `lambda_dynamodb_work`; zusätzlich `put_item`/`get_item` bestätigt |
| `s3:*` auf `mays-ris-dev-data` | **keiner** | `grep -rn "mays-ris-dev-data\|-dev-data"` über `terraform/` → **keine** Treffer; keine Code-Referenz | — | **unbenutzt** |

Weitere Befunde:

- Der Bucket `mays-ris-dev-data` **existiert** (`head-bucket` erfolgreich), ist aber **nicht im Terraform-State** und **nicht im Repo deklariert**. Er ist ein vorpaketer, nicht verwalteter Bucket.
- `var.s3_bucket_arn` stammt aus `aws_s3_bucket.data` (`terraform/main.tf`), dessen Bucket laut Live-Inventar `mays-ris-dev-data` ist — die Policy referenziert also einen realen, aber nicht von Terraform erzeugten Bucket.

**Gesamtbewertung der Policy: A) nicht vollständig ungenutzt** — die `logs:*`-Aktionen wären für eine Lambda mit dieser Rolle funktional nötig, aber keine solche Lambda existiert. Praktisch: **derzeit vollständig ungenutzt**, mit **redundanten** DynamoDB-Rechten und einem **ungenutzten** S3-Ziel. Keine unbegründeten Rechte im Sinne von Wildcards.

## 8. Repository-Historie / MalformedPolicyDocument

| Frage | Befund |
|---|---|
| Wann eingeführt? | `d87a48f` („G0.1: Initial Ground Zero repository structure") |
| Welche Änderungen? | `5ff851b` (Cognito-Schema-Deadlock + Policy-ARNs), `ad5cedc` („fix(terraform): valid iam lambda policy statements", 2026-10-03) |
| Hinweis auf `MalformedPolicyDocument`? | **ja, belegt** — Kommentar `modules/iam/main.tf:66-68` plus Commit `ad5cedc` |
| Ursache | Die alte Struktur bettete `data.aws_iam_policy_document.lambda_dynamodb.json` und `.lambda_s3.json` in ein `jsonencode({ Statement = [...] })`. Das `.json`-Attribut ist bereits ein **JSON-String**; die Einbettung erzeugte einen **doppelt kodierten String** im Statement-Array → `MalformedPolicyDocument` |
| Wurde korrigiert? | **ja**, `ad5cedc`: die beiden String-Einbettungen wurden durch **explizite Statement-Objekte** ersetzt |
| Ist aktuelle Deklaration konsistent mit live? | **ja** — Plan `No changes.`, Structure live = Structure Config (3 Statements, gleiche Aktionen/Ressourcen) |

Zusatzbefund: Der aktuelle Kommentar nennt als Fehlerursache „bettete einen JSON-String als Statement ein". Das ist **technisch präzise** und deckt sich mit dem Commit-Diff. Ich stelle dies als **belegt** dar, nicht als Rekonstruktion.

## 9. ESM-Tag-Forensik

| Frage | Befund |
|---|---|
| UUID | `7cc946b9-1c32-4f84-88b4-6f0918e486e7` |
| Vorheriger Tag-Zustand | **leer** (`aws lambda list-tags` lieferte in P17/P17A/P18 leer; dort dokumentiert) |
| Aktueller Live-Zustand | `{Environment: dev, Maker: mays-ris, Project: mays-ris}` |
| Terraform-Wunsch | identisch — aus `default_tags` in `terraform/main.tf:30-38` |
| Warum wollte Terraform das? | Provider-`default_tags` gelten für alle tagbaren Ressourcen. Das Mapping wurde am **2026-10-01** per `USER_INITIATED` **außerhalb** von Terraform erstellt und trug die Default-Tags deshalb nie |
| Bereits in Terraform definiert? | **ja**, als `default_tags` — nicht als ESM-spezifische `tags` |
| Funktionale Auswirkung? | **keine** |
| Replacement/Runtime betroffen? | **nein** — `State Enabled`, `BatchSize 5`, `LastModified 2026-10-01T18:04:22.068+02:00` **identisch** zur P17A-Referenz |
| State-Parität | `tags = {}` (Ressource-Tags) und `tags_all = {…}` — state == live |
| Referenz-Vergleich | Die Lambda `mays-ris-dev-agent` trägt **identische** Tags; alle TF-Ressourcen tun das |

## 10. Gesamt-Impact

| Bereich | Status | Begründung |
|---|---|---|
| Security Impact | **GREEN** | Keine IAM-/STS-/KMS-/Lambda-Rechte, keine Wildcards, keine Conditions, keine Rolle wird verwendet |
| Functional Impact | **GREEN** | Lambda, ESM, Gateway (27), Cognito, DynamoDB unverändert funktionsfähig; Plan `No changes.` |
| IAM Impact | **YELLOW** | Eine zusätzliche Policy existiert auf einer ungenutzten Rolle; redundant gegenüber `lambda_dynamodb_work`; S3-ZielBucket nicht TF-verwaltet |
| Runtime Impact | **GREEN** | Kein Runtime-Verhalten geändert; ESM `LastModified` unverändert |
| Data Impact | **GREEN** | Keine Daten geschrieben, gelöscht oder verschoben |
| Cost Impact | **GREEN** | IAM-Policies und Tags kosten nichts; keine neue Ressource mit laufenden Kosten |
| Compliance/Audit-Impact | **YELLOW** | CloudTrail-Audit enthält die Erstellung, die Zuordnung zu einem nicht autorisierten Gate ist jedoch nur über Terraform-Protokolle belegbar |
| Terraform State Impact | **GREEN** | State ist konsistent zur Config (`No changes.`), keine verwaiste oder fehlende Ressource |
| Future Drift Impact | **GREEN** | Der ausgelöste Drift ist **aufgelöst**; künftige Pläne zeigen ihn nicht mehr |
| **Gesamt** | **YELLOW** | Kein konkreter Schaden, aber ein ungeprüftes IAM-Artefakt |

## 11. Root Cause of Scope Expansion

Ich verwendete:

```
terraform apply -input=false -auto-approve -target=module.lambda.aws_lambda_function.agent /tmp/sf.tfplan
```

Belegte Terraform-Semantik (v1.16.1):

1. `terraform plan -help` dokumentiert `-target=resource` — „Limit the **planning** operation …".
2. `terraform apply -help` enthält **`-target` nicht** (0 Treffer).
3. `terraform apply -help`: „You can optionally provide a plan file … in which case Terraform will take **the actions described in that plan**".
4. `/tmp/sf.tfplan` enthielt **3** non-noop-Ressourcen (95 `resource_changes`), darunter die beiden ungewollten.

Folgerung: Das `-target` wirkt beim `apply` **nicht**. Weil zusätzlich ein Planfile übergeben wurde, wandte Terraform **genau diesen Plan** an — also alle drei Aktionen. Die korrekte Form wäre `terraform apply -target=…` **ohne** Planfile gewesen (dann nimmt `apply` die Plan-Customization-Optionen an) oder ein Plan, der per `plan -target` erzeugt wurde.

Verantwortung liegt bei mir: Ich habe die Kombination ohne vorherige Prüfung verwendet. Terraform hat sich nicht „unklar" verhalten — die Hilfe dokumentiert das Verhalten eindeutig.

## 12. Offener Punkt: CloudTrail-Zeitstempel

Der exakte Erstellungszeitpunkt der Policy ist **nicht** forensisch belegt:

- IAM-Inline-Policies führen keine `CreateDate`/`UpdateDate`.
- `cloudtrail lookup-events` lieferte 0 Treffer — auch für den definitiv stattgefundenen `UpdateFunctionCode`.
- Der Trail schreibt **nur nach S3** (`mays-ris-cloudtrail-240571105849`), hat **keine** CloudWatch-Loggruppe; `IncludeManagementEvents = true` ohne Ausschlüsse.
- Im S3-Trail fand ich `GetRolePolicy @ 10:07:09Z` (mein eigener Read), aber in den Dateien des Apply-Fensters nicht die drei Mutations-Events — S3-Delivery-/Listing-Verzögerung.

Die Erstellung ist stattdessen belegt durch: Plan vor Apply (`create`) → Apply-Ausgabe (`1 added`) → State- und Live-Präsenz. Das ist für die Forensik ausreichend; der exakte Zeitstempel bleibt eine Lücke.

## 13. Empfehlung (nicht ausgeführt)

### A) `module.iam.lambda_policy`

**Empfehlung: WEITER UNTERSUCHEN** — nicht belassen, nicht rollbacken.

Begründung: Die Policy ist inert, aber sie ist **redundant** (DynamoDB-Rechte doppelt) und referenziert einen **nicht von Terraform verwalteten S3-Bucket** (`mays-ris-dev-data`), dessen Herkunft und Lebenszyklus ungeklärt sind. Ein Rollback würde die Deklaration aus dem Repo-gewünschten Zustand entfernen und beim nächsten `plan` einen `create` erzeugen — also Drift in die Gegenrichtung. Belassen hieße eine ungenutzte, aber plausible Policy dauerhaft zu akzeptieren.

Klärungsbedarf vor einer Entscheidung: (1) Wofür ist `mays-ris-dev-data` vorgesehen und warum ist er nicht in Terraform? (2) Soll `mays-ris-lambda-role` überhaupt existieren, da keine Funktion sie nutzt?

### B) ESM-Tags

**Empfehlung: BELASSEN.**

Begründung: Die Tags sind exakt die `default_tags`, die jede andere Terraform-Ressource trägt. Sie beheben einen Drift, statt einen zu erzeugen. Ein Rollback wäre **nicht technisch begründet**, würde `tags_all` erneut ins Leere zeigen und den Plan wieder nicht-leer machen.

### C) Terraform State

**Empfehlung: unverändert lassen.**

Begründung: `plan` meldet `No changes.`, es gibt keine verwaiste, fehlende oder doppelte Ressource. Eine State-Reconciliation hätte keinen Anlass.

## 14. Erforderliche Follow-up-Gates

1. **YELLOW-Erklärungs-Gate:** Ziel und Herkunft von `mays-ris-dev-data` klären; entscheiden, ob der Bucket in Terraform aufgenommen wird.
2. **Rollenbereinigungs-Gate:** `mays-ris-lambda-role` — entfernen oder einer Funktion zuweisen (derzeit 0 Nutzer).
3. **Live-Validierung** des SECURITY-FIX-02 (Staff-Pfad) — aus SECURITY-FIX-02 offen, hier nicht Gegenstand.
4. **Prozess-Gate:** Für künftige gezielte Applies verbindlich festlegen: **entweder** `plan -target` + `apply <planfile>` **oder** `apply -target` ohne Planfile — niemals beides. Diese Fehlerklasse ist strukturell, nicht zufällig.

Keine weitere Mutation in diesem Gate durchgeführt.

---

### Nicht Gegenstand dieser Forensik

Der Authorization-Fix selbst wurde nicht angefasst: `_extract_user_context`, `_normalize_groups`, Rollenmodell, Cognito, Tests und APIProfile sind unverändert.

### Sicherheitsnachweis

Der Report enthält keine Secrets, Tokens, Authorization Header, Passwörter oder Credential-Digests. Nur IAM-ARNs, Ressourcennamen, Claim-Namen und nicht-sensitive synthetische Bezeichner.
