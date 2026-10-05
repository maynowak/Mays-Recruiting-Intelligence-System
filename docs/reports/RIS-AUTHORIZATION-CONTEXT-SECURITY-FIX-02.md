# RIS-AUTHORIZATION-CONTEXT-SECURITY-FIX-02 — Claim-Normalisierung Fix

STATUS: **RED / HARD STOP** — Der Sicherheitsfix ist korrekt deployed, **aber ich habe bei Apply zwei out-of-scope Ressourcen mutiert.** Live-Validierung wurde nicht durchgeführt.

- Datum: 2026-10-05 UTC
- Branch/HEAD: `main`, `8633fec`
- Account/Region/Workspace: `240571105849` (`user/Mayaws`) / `eu-central-1` / `mays-ris`

## 1. Eigener Fehler — zuerst und ungeschmückt

Ich habe diesen Befehl ausgeführt:

```
terraform apply -input=false -auto-approve -target=module.lambda.aws_lambda_function.agent /tmp/sf.tfplan
```

Die Kombination aus **`-target` und gespeichertem Planfile** war falsch. Terraform hat nicht auf die Lambda begrenzt, sondern den **gesamten Plan** angewendet:

```
Apply complete! Resources: 1 added, 2 changed, 0 destroyed.
```

Erwartet war: `1 changed` (nur Lambda-Code). Tatsächlich:

| Ressource | Soll | Ist | Bewertung |
|---|---|---|---|
| `aws_lambda_function.agent` | Code-Update | Code-Update | ✅ wie beabsichtigt |
| `module.iam.aws_iam_role_policy.lambda_policy` | **nicht angefasst** | **created** | 🔴 **Scope-Verletzung** |
| `module.lambda.aws_lambda_event_source_mapping.sqs_mapping` | **nicht angefasst** | **Tags gesetzt** | 🔴 **Scope-Verletzung** |

Beide waren über mehrere Gates hinweg bewusst als Fremd-Drift stehen gelassen worden. Ich habe sie mit einem Befehl erzeugt, den ich vorher hätte auf Kombinierbarkeit prüfen müssen.

## 2. Impact-Bewertung (read-only verifiziert)

### 2.1 `mays-ris-lambda-policy` (neu erstellt)

| Merkmal | Wert |
|---|---|
| Rolle | `mays-ris-lambda-role` (CreateDate **2026-09-30**, also **nicht** neu) |
| `logs:*` auf | `arn:aws:logs:*:*:*` |
| `dynamodb:*` auf | `mays-ris-dev-work-items` (+ `/table/…/*`) |
| `s3:*` auf | `mays-ris-dev-data/*` |
| Wildcards | **keine** (`logs:*:*:*` ist der übliche Logs-Scope, kein `*`-Service) |
| Von einer Lambda verwendet | **nein** — `list-functions` findet keine Funktion mit dieser Rolle |
| Agent-Rolle (`mays-ris-dev-agent`) | **unverändert, 8 Policies** wie vor dem Apply |

Die Policy ist wörtlich die Deklaration aus `terraform/modules/iam/main.tf:65-…` — also die Absicht des Repos, kein erfundenes Recht. Ihre Wirkung ist derzeit **inert**, weil keine Lambda-Funktion diese Rolle verwendet. Sie war allerdings über P16–P19 hinweg bewusst nicht deployed, unter anderem weil ihr Kommentar (`:66-68`) auf einen früheren `MalformedPolicyDocument`-Fehler verweist, der einen Fresh-Install blockierte. Diese Historie ist jetzt ungeprüft — der Zustand ist entstanden, aber **nicht** auf seine Tauglichkeit geprüft.

### 2.2 ESM-Tags

`Environment`/`Maker`/`Project` wurden auf `7cc946b9…` gesetzt. Das sind die Provider-`default_tags` aus `terraform/main.tf:30-38`, identisch zu allen anderen Terraform-verwalteten Ressourcen. Funktional harmlos, aber ebenfalls out-of-scope.

### 2.3 Unverändert (verifiziert)

| Bereich | Befund |
|---|---|
| Lambda | nur Code; `CodeSha256 ECemCxwAOv0fNo3OeAkxjpT3Eg+Xyl9LZB61h3R4VvQ=` = lokaler Build, `LastUpdateStatus Successful`, Runtime/Handler/Memory/Timeout/Role/VPC/Env(11) unverändert |
| ESM | UUID, `Enabled`, Batch 5 unverändert |
| Gateway | **27 Routen, Soll-Set vollständig, keine fehlend, keine neu** |
| Cognito | `AutoVerifiedAttributes ["email"]`, 7 Gruppen unverändert |
| DynamoDB / SQS | keine Mutation |
| IAM-Rollen | 22, keine neue Rolle |

**Korrektur einer eigenen Fehlmessung:** Ich maß zunächst „25 Routen" und „Cognito-Gruppen 6 ≠ 7" und meldete beide als Auffälligkeit. Beides war mein Messfehler: die Wiederholungsmessung zeigte 27 Routen mit exakt passendem Set, und die 7 Gruppen (`admins`, `Staff`, `Admin`, `candidates`, `recruiters`, `user-user`, `user-requier`) waren der bisherige Zustand — ich hatte die TF-Resource-Namen fälschlich als Gruppennamen erwartet.

## 3. Root Cause und Codeänderung

Unverändert zu Gate 01: Der API-Gateway-JWT-Authorizer liefert `cognito:groups` stringifiziert (`"[admins]"`). `split(",")` erzeugte `["[admins]"]`, wodurch `_is_admin()`/`_is_staff()` fehlschlugen.

**Neu in `lambda/handler.py`:**

1. `_normalize_groups(raw)` — zentrale, deterministische Normalisierung.
2. `_extract_user_context` ruft nur noch `_normalize_groups(jwt_claims.get('cognito:groups'))` auf; das `split(",")` ist entfernt.
3. `import re` und `List` im Typing-Import.

Behandlung der 10 geforderten Formen (alle verifiziert):

| Eingabe | Ergebnis |
|---|---|
| `None` | `[]` |
| `[]` | `[]` |
| `["admins"]` | `["admins"]` |
| `["Staff"]` | `["Staff"]` |
| `"[admins]"` | `["admins"]` |
| `"[Staff]"` | `["Staff"]` |
| `'["admins", "Staff"]'` | `["admins", "Staff"]` |
| `"admins,Staff"` | `["admins", "Staff"]` |
| `""` / `"   "` | `[]` |
| `42`, `True`, `dict` | `[]` |

**Korrektur während der Umsetzung:** Mein erster Entwurf nutzte `json.loads` mit Rückfall auf `[]`. Das war falsch — `"[admins]"` ist **kein** valides JSON (unquotierte Elemente), es ist Pythons `str(list)`. Ergebnis wäre `[]` gewesen, also der Fehler wäre bestehen geblieben. Korrigiert auf: JSON zuerst, sonst Klammern abschneiden und kommagetrennt zerlegen.

## 4. Sicherheitsinvariante — kein permissiver Fallback

Zusätzlich zur Formen-Behandlung gilt strikt: **ein fehlerhafter Claim verwirft die gesamte Gruppe**, er wird nicht teilweise ausgewertet.

| Fehlwert | Ergebnis | privilegiert |
|---|---|---|
| `"[not json"` | `[]` | nein |
| `"["` | `[]` | nein |
| `'[["admins"]]'` | `[]` | nein |
| `"[<script>]"` | `[]` | nein |
| `"a] , admins"` | `[]` | nein |
| `["admins", 7]` | `[]` | nein |
| `"admin s"` | `[]` | nein |
| `{"a": "admins"}` | `[]` | nein |
| `"Admin"` (deprecated) | `["Admin"]` | **nein** |
| `"mayaws"` | `["mayaws"]` | **nein** |

Der Fall `"a] , admins"` ist der Grund für die strikte Regel: Teilparsing hätte `"admins"` behalten. Eine Token-Whitelist (`^[A-Za-z0-9_.:@-]+$`) verhindert zusätzlich, dass Klammern oder Fremdzeichen in Gruppenwerten überleben.

## 5. Rollenmodell — unverändert

`admins` = RIS Product Admin · `Staff` = RIS Staff · `Admin` = deprecated, nicht verwendet · normaler User = Owner · `mayaws` = **ausschließlich** AWS-/Deployment-Kontext.

Product Admin ≠ AWS Administrator. Es wurden aus RIS-Rollen **keine** AWS-Berechtigungen abgeleitet. `mayaws` wurde in diesem Gate ausschließlich für AWS-Reads verwendet.

## 6. Tests

`tests/test_authorization_context.py`, **32 Tests**, alle grün: 14 Formen-Tests, 4 Fallback-Tests (inkl. `mayaws` und `Admin` inert), 7 Rollentrennungs-Tests, 7 Domain-Contract-Tests.

Die Domain-Tests schließen den previously proven permissiven Pfad und sichern die erlaubte Support-Funktion:

| Test | Ergebnis |
|---|---|
| Staff kann **kein** Profil anlegen (`"[Staff]"` und `["Staff"]`) | `UnauthorizedProfileAction`, Store leer |
| Owner kann **weiterhin** anlegen | 201-Äquivalent, `PENDING` |
| Admin kann **weiterhin** für Zieluser anlegen | `createdBy.role=admin` |
| **Staff-Support-Read mit Reason weiterhin möglich** | mit Reason sichtbar, ohne Reason `None` |
| Staff kann **nicht** `PENDING→ACTIVE` | `UnauthorizedProfileAction` |
| Admin kann `PENDING→ACTIVE` | `ACTIVE` |

**Regressionsvergleich gegen HEAD:**

| | Fehler | Passed |
|---|---|---|
| HEAD (Baseline) | 15 | 743 |
| mit Fix (ohne neue Tests) | **8** | 750 |
| mit Fix + neue Tests | 8 | 782 |

**Null Regressionen** (maschineller Listenvergleich). Die 7 neu grünen Tests sind **nicht** durch die Claim-Normalisierung repariert, sondern durch das ebenfalls notwendige `import re`: in `HEAD:lambda/handler.py` fehlte `re`, wodurch `_extract_path_param` (`:1359`) mit `NameError` abbrach. Diese Funktion bedient `/api/agents/*` und ist laut P17A ohne Gateway-Route, also nicht live erreichbar. Ich nenne das ausdrücklich, damit es nicht als Wirkung des Security-Fix missverstanden wird. Keine Tests gelöscht oder abgeschwächt; nur eine Datei hinzugefügt.

## 7. Live-Validierung — NICHT durchgeführt

Der zuvor bewiesene permissive Staff-Pfad ist **nicht** live nachgewiesen geschlossen. Grund: HARD STOP nach der Scope-Verletzung in §1. Es wurden keine Testfixtures neu angelegt, kein Rollenpfad live gefahren, keine Secrets erzeugt.

Damit ist die entscheidende GREEN-Bedingung des Gates **nicht** nachgewiesen: „Der zuvor bewiesene permissive Staff-Create-Pfad muss nach dem Fix nicht mehr reproduzierbar sein."

## 8. AWS Mutation

| Art | Umfang |
|---|---|
| **Lambda** | 1× Code-Update, `ECemCxwAOv0fNo3OeAkxjpT3Eg+Xyl9LZB61h3R4VvQ=` |
| **IAM (unbeabsichtigt)** | 1× `CreateRolePolicy` `mays-ris-lambda-policy` an `mays-ris-lambda-role` |
| **ESM (unbeabsichtigt)** | Tags auf `7cc946b9…` gesetzt |
| Gateway / Cognito / DynamoDB / SQS | keine |
| Neue IAM-Rolle | keine |

## 9. Weiterhin OPEN — in diesem Gate bewusst nicht berührt

1. **Audit-Integrität** (Gate 01): Contract-Verletzungen erscheinen als `outcome=success`, `createdBy.role=owner`. Nicht adressiert, wie beauftragt.
2. **403 vs. 404** (Gate 01): neutrale 404 statt 403 bei Rollenverletzungen. Nicht umgebaut, wie beauftragt.
3. **Cleanup** `aprof_352e4133…` (PENDING, aus dem Staff-Missbrauch): per Produktpfad nicht bereinigbar, da `REVOKE`/`DISABLED` die Admin-Rolle brauchen — die war vor diesem Fix defekt. **Nach diesem Fix könnte der Cleanup möglich sein**, sobald ein Admin-Fixture existiert. Nicht ausgeführt.
4. **`mays-ris-lambda-policy`:** Wirkung derzeit inert, aber die Historie zum früheren `MalformedPolicyDocument`-Fehler ist ungeprüft. Entscheidung nötig: belassen, prüfen oder zurücknehmen (Rücknahme wäre eine weitere Mutation mit Freigabepflicht).

## 10. Status

**RED / HARD STOP.**

Der Code-Fix selbst ist korrekt, minimal, getestet (32 neue Tests, 0 Regressionen) und live deployed (Hash verifiziert). Aber:

- Ich habe **zwei Ressourcen außerhalb des Auftrags mutiert** — mein Fehler, in §1 offengelegt.
- Die **Live-Verifikation des Fixes steht aus**, die zentrale GREEN-Bedingung ist damit unbelegt.
- Eine **ungeprüfte IAM-Policy** ist live, deren historische Tauglichkeit nicht validiert ist.
