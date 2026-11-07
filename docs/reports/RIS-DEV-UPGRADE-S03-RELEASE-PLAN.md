# RIS-DEV-UPGRADE-S03 — Release Preparation & Protected Terraform Plan

- **Datum:** 2026-11-03
- **Modus:** Vorbereitung + Terraform-Plan; **kein Apply, keine AWS-Mutation**
- **Ziel:** `ris-dev` · Profil `mayaws` · Account `240571105849` · `eu-central-1`
- **Gesamtergebnis:** **RED — NO-GO für S04**

Der Plan ist technisch erzeugbar, würde aber **54 geschützte Ressourcen zerstören** und 102 neu erzeugen. Ursache ist eine Modul-Adressmigration (`module.cognito` → `module.cognito[0]`), keine fachliche Änderung. Ein Apply ist untersagt.

---

## 1. Git- und AWS-Baseline

| Feld | Wert |
|---|---|
| Branch | `main` |
| HEAD bei Beginn | `d205bb2` |
| Neue Commits | `5a73c66` (IAM-Reihenfolge), `9bfa37d` (Installer-Pfadfix) |
| HEAD vor Plan | `9bfa37d` |
| Working Tree | sauber bis auf geschützte fremde Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` (unverändert) |
| AWS-Profil | `mayaws` |
| Account | `240571105849` (`arn:aws:iam::240571105849:user/Mayaws`) |
| Region | `eu-central-1` |

---

## 2. Geschützte Identitätsinfrastruktur

| Objekt | Live-Zustand | Terraform-Adresse | Bewertung |
|---|---|---|---|
| RIS-Pool | `eu-central-1_ojbmoiYGM` (`ris-dev-dev-users`) | `module.cognito[0].aws_cognito_user_pool.users` | **im Plan: DELETE** |
| Human-Client | `7ldhihlpdgsgcl3puvu4oi7ksv` | `module.cognito[0].…user_pool_client.client` | **DELETE** |
| M2M-Client | `82ji073smu1b3fsvj96sonso` | `module.cognito[0].…client.m2m[0]` | **DELETE** |
| RIS-Domain | `ris-dev-dev` (ACTIVE) | `module.cognito[0].…user_pool_domain.domain[0]` | **DELETE** |
| Gruppen | 7 Gruppen | `module.cognito[0].…user_group.*` | **DELETE** |
| Orders-Pool | `eu-central-1_cmJWXujnb` | `module.mays_orders[0].module.cognito[0]` | **DELETE** |
| Orders-Stack | API/Tabelle/Queue/Lambdas | `module.mays_orders[0].*`, `module.orders_reader[0].*` | **DELETE** |
| Jobsearch-Domain | `auth.mays-job-matcher.app` (Pool `ZURSMpD2O`) | nicht im State | korrekt geschützt |
| ACM | `0bfb2603…`, `ISSUED` | Referenz only | unverändert |

**Keine geplante Änderung an CloudFront, OAC, DNS, ACM oder am Jobsearch-Pool.** Das ist der einzige grüne Teil des Plans.

`identity_custom_domain_enabled=false` im Overlay ist korrekt und verhindert den Domain-Konflikt. `orders_lifecycle=managed` bleibt unverändert.

---

## 3. Lokale Codekorrekturen

### 3.1 IAM-Reihenfolge (`5a73c66`)

`lambda_dynamodb_applications` fehlte in `depends_on` der Agent-Lambda. Ergänzt; keine Berechtigung geändert.

### 3.2 Installer-Pfadauflösung (`9bfa37d`)

`terraform_vars()` leitete das Repo-Root eine Ebene zu hoch ab und erzeugte
`/home/dci-student/projects/lambda/dist/...`. Dadurch brach jeder Plan vor Terraform ab (auch in S02 dokumentiert). Korrigiert auf `dirname(terraform_dir)`; Test prüft, dass alle drei Bundle-Pfade absolut und innerhalb des Repos liegen. `tests/test_ris_installer.py`: **37 passed**.

---

## 4. Erasure-Readiness

| Aspekt | Befund |
|---|---|
| Executor implementiert | ✅ `ApplicationErasureExecutor`, `ProfileOnlyErasureExecutor._delete_applications` |
| Lokale Tests | ✅ `tests/test_application_erasure.py` (3 Tests) |
| Produktionsaufruf | ❌ `POST /me/erasure` nutzt `PrivacyErasure` (Credentials, API-Profile, WorkItems, Documents, UserProfile) — **Applications fehlen** |
| Feature-Flags | alle `false`; Application-Erasure hat keinen eigenen Flag |
| Freigabe | Retention-/Legal-Entscheidung offen (`RIS-APPLICATION-V1-RETENTION-DECISION#APPROVAL_REQUIRED`) |

**Ergebnis: BLOCKED.** Keine Codeänderung vorgenommen. Eine Verdrahtung würde das Löschverhalten produktiv ändern und benötigt eine explizite Datenschutzfreigabe. Der Plan ist davon unabhängig, die Betriebsfreigabe nicht.

---

## 5. Cursor-Secret-Readiness

| Prüfung | Befund |
|---|---|
| Code | `jobsearch/application_repository.py:76-79` verlangt `RIS_CURSOR_SECRET`, sonst `RuntimeError` → 503 |
| Lambda-Environment | **nicht gesetzt** |
| Terraform-Variablen | **nicht vorhanden** |
| Secret Store | kein Secret `RIS_CURSOR_SECRET` in Secrets Manager/SSM gefunden |
| IAM | keine `secretsmanager:GetSecretValue`-Policy für die Agent-Rolle |

**Bewertung:** Ein Klartextwert in `lambda.environment` landet im Terraform-State und in Planfiles → **nicht freigabefähig**.

Empfohlenes Verfahren (nicht umgesetzt, keine AWS-Erstellung):

1. Secret außerhalb Terraform anlegen (Secrets Manager, Rotation möglich).
2. Agent-Rolle erhält eine eng begrenzte `GetSecretValue`-Policy auf genau dieses Secret.
3. Runtime liest das Secret beim Cold Start (gecacht), nicht per Env-Variable.
4. Alternativ: Deployment-Pipeline injiziert den Wert zur Laufzeit, nicht Terraform.

**Ergebnis: BLOCKED** — ohne bereitgestelltes Secret ist Pagination nach dem Upgrade nicht funktionsfähig.

---

## 6. Packaging-Ergebnis

| Artefakt | Größe | SHA-256 |
|---|---:|---|
| `terraform/lambda.zip` | 250.611 B (76 Dateien) | `6132b3b3bd38844cb5a0ea5b3b47a7e52f046edd4f866bcebbb75e0375470fc2` |
| `lambda/dist/orders-reader.zip` | 4.321 B | `e405858718101db34a8d5c1237e36d41a47b7dceb8e0ebff8b01bd86d1c366e5` |

Kein Upload. ZIP-Struktur und Handler-Importe wurden über den Build und die Tests abgedeckt.

---

## 7. Regressionstests

| Lauf | Ergebnis |
|---|---|
| Application/Profile/CV/ATS/Privacy/API-Contract (10 Dateien) | **119 passed, 2 skipped** |
| Installer (`test_ris_installer.py`) | **37 passed** |
| `terraform fmt -check -recursive` | PASS |
| `terraform init -backend=false` | PASS |
| `terraform validate` | PASS (bekannte Deprecation-Warnungen) |

Keine vollständige Suite ausgeführt (nicht erforderlich, keine Architekturänderung).

---

## 8. Terraform-State

| Feld | Vor Plan | Nach Plan |
|---|---|---|
| State-Key | `env:/ris-dev/dev/terraform.tfstate` | unverändert |
| Objekt-Version | `3tey8lIHFnMBSsaWeFErDer8a2BucoCK` | unverändert |
| LastModified | 2026-10-31 21:16:27 UTC | unverändert |
| Serial | 36 | 36 |
| Lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` | unverändert |
| Ressourcen | 185 | 185 |

Der Plan hat den State nicht verändert. Ein Backend-Lock bestand nur während der Plan-Ausführung.

---

## 9. Terraform-Plan

| Feld | Wert |
|---|---|
| Plan-Datei | `/tmp/opencode/ris-dev-s03.tfplan` (außerhalb des Repos) |
| Plan-JSON | `/tmp/opencode/ris-dev-s03-plan.json` (außerhalb des Repos) |
| **SHA-256** | **`e5d3b28d8ea0836ac78721a628d61129908cdedecaa40a7f78861ceccf45f4dd`** |
| Terraform-Version | 1.16.1 |
| Erstellt über | Installer `plan` (vorhandener Pfad), `--terraform-dir` absolut |

### Aktionszahlen

| Aktion | Anzahl |
|---|---:|
| CREATE | **102** |
| UPDATE | **5** |
| DELETE | **54** |
| REPLACE | **0** |
| READ | 3 |
| no-op | 111 |
| Drift-Einträge | **1** |

> `REPLACE = 0` ist **kein Entwarnungssignal**: Die Modulmigration erscheint als getrennte DELETE+CREATE-Paare auf Modulebene.

### Updates (5)

- `module.api.aws_apigatewayv2_authorizer.jwt`
- `module.api.aws_apigatewayv2_authorizer.jwt_m2m`
- `module.lambda.aws_lambda_function.agent` (Code/Env)
- `module.lambda.aws_iam_role_policy.lambda_documents`
- `module.lambda.aws_iam_role_policy.lambda_dynamodb_platform`

### Deletes (54) — alle geschützt

| Modul | Anzahl | Wirkung |
|---|---:|---|
| `module.cognito` | 11 | Pool, 2 Clients, Domain, 7 Gruppen, Resource-Server |
| `module.mays_orders` | 22 | Orders-API, Cognito, Tabelle, Queue, Lambdas, IAM |
| `module.orders_reader` | 10 | Reader-Lambda, Routen, IAM |
| `module.monitoring_orders` | 7 | Dashboard + 6 Alarme |
| übrige | 4 | Einzelressourcen |

### Creates (102)

Fachlich erwartet: 7 Tabellen, 33 Routen, 7 IAM-Policies. Zusätzlich werden **alle oben gelöschten Module neu erzeugt** (Cognito 11, Orders 22, Reader 10, Monitoring 7) — deshalb 102 statt ca. 47.

---

## 10. Ursache (Root Cause)

`terraform/main.tf` führt auf `main` `count` für vier Module ein:

- `module.cognito` → `count = local.identity_managed ? 1 : 0`
- `module.orders_reader` → `count = local.orders_enabled ? 1 : 0`
- `module.mays_orders` → `count = local.orders_managed ? 1 : 0`
- `module.monitoring_orders` → `count = local.orders_managed ? 1 : 0`

Der State von `ris-dev` (seit 2026-10-31) enthält diese Module **ohne Index** (`module.cognito.*`, nicht `module.cognito[0].*`). Terraform interpretiert das als andere Adresse und plant Destroy+Create.

Damit ist das In-place-Upgrade nicht durch den Code, sondern durch die **Adressmigration** blockiert. Dieselbe Ursache erklärt die 104 Ersetzungen aus dem fehlerhaften 2026-10-31-Apply.

---

## 11. Sicherheits- und Datenschutzblocker

| # | Blocker | Schwere |
|---|---|---|
| 1 | 54 Deletes an Cognito/Orders/IAM durch Modul-Adressmigration | **RED** |
| 2 | `RIS_CURSOR_SECRET` fehlt; unsichere Env-Variante nicht freigebbar | RED |
| 3 | Application-Erasure nicht verdrahtet | RED (fachlich) |
| 4 | Drift am Cognito-Pool (1 Update) | YELLOW |
| 5 | Orders-SQS `Principal="*"` (extern, unverändert) | RED (extern) |
| 6 | PITR auf Kerntabellen deaktiviert | YELLOW |
| 7 | Keine positive Auth-E2E für ApplicationV1 | YELLOW |

---

## 12. Rollback-Voraussetzungen

Vor jedem späteren Apply:

1. State-Backup als versioniertes Objekt sichern (`3tey8lI…` bleibt lesbar; zusätzliche Kopie empfohlen).
2. Modul-Adressmigration separat freigeben (`moved`-Blöcke oder `state mv`) — **nicht** in diesem Auftrag.
3. Plan erneut erzeugen und auf **0 Deletes an geschützten Modulen** prüfen.
4. PITR für die 7 neuen Tabellen und bestehende Kerntabellen entscheiden.
5. `RIS_CURSOR_SECRET` bereitstellen.
6. Erasure-Freigabe dokumentieren.
7. Plan-Hash dokumentieren; Rollback = erneuter Plan gegen unveränderten State, kein Ad-hoc-Apply.

---

## 13. GO / NO-GO

**NO-GO für S04.**

Der Plan ist vollständig erzeugt und ausgewertet, aber er verletzt die Schutzmatrix (Cognito, Orders, IAM). Ein Apply würde den produktiven RIS-Login und den Orders-Stack zerstören.

S04 darf erst starten, wenn:

- die Modul-Adressmigration freigegeben und umgesetzt ist,
- ein neuer Plan **0 DELETE/REPLACE** an Cognito, CloudFront, DNS, ACM, Orders zeigt,
- `RIS_CURSOR_SECRET` sicher bereitgestellt ist,
- die Erasure-Entscheidung dokumentiert ist.

**STOP nach S03. Kein Apply, keine AWS-Ressourcenänderung.**
