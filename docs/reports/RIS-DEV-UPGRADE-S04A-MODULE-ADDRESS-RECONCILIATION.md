# RIS-DEV-UPGRADE-S04-A — Declarative Module Address Reconciliation

- **Datum:** 2026-11-03
- **Modus:** kontrollierte Terraform-Codekorrektur + Plan-only
- **Ziel:** `ris-dev` · Profil `mayaws` · Account `240571105849` · `eu-central-1`
- **Ergebnis:** **GREEN für S04-A** — Adressmigration vorbereitet, keine Deletes/Replacements, keine geschützten Änderungen, State unverändert
- **Kein Apply.**

---

## 1. Executive Summary

Die vier in S03 zerstörerisch geplanten Module werden jetzt deklarativ auf ihre indizierten Adressen migriert. Der neue Plan enthält:

- **0 DELETE** (vorher 54)
- **0 REPLACE** (vorher 0, aber als Module-Destroy maskiert)
- **48 CREATE** (rein additiv: 34 Routen, 7 Tabellen, 7 IAM-Policies)
- **3 UPDATE** (Lambda-Code/Env, 2 IAM-Policies)
- **54 MOVE** (alle `no-op`, also identische AWS-Ressourcen)

Cognito, Orders, CloudFront, OAC, DNS, ACM und alle bestehenden Datenbanktabellen bleiben unverändert. Der State wurde durch den Plan nicht verändert.

---

## 2. Git-Baseline

| Feld | Wert |
|---|---|
| Branch | `main` |
| HEAD bei Beginn | `4ccbcd4` |
| Neue Commits | `db0c0c2` (moved blocks), Report-Commit folgt |
| Working Tree | sauber bis auf geschützte fremde Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` (unverändert, nicht gestaged) |

Lokale Commits `4140fbc`, `64cc38f`, `d205bb2`, `5a73c66`, `9bfa37d`, `378d596`, `4ccbcd4` bleiben erhalten.

---

## 3. AWS-/State-Guard

| Prüfung | Wert |
|---|---|
| STS Account | `240571105849` ✅ |
| Profil | `mayaws` |
| Region | `eu-central-1` |
| Workspace | `ris-dev` |
| State-Key | `env:/ris-dev/dev/terraform.tfstate` |
| Lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` ✅ |
| Serial vor Plan | 36 ✅ |
| Ressourcen | 185 ✅ |
| Serial nach Plan | 36 (unverändert) |
| State-Version | `3tey8lIHFnMBSsaWeFErDer8a2BucoCK` (unverändert) |

Alle Guard-Werte entsprechen der S03-Baseline. Keine Abweichung, kein HARD STOP.

---

## 4. Ursachenanalyse der 54 Deletes

`terraform/main.tf` instanziiert seit dem PR-3-Stand vier Module mit `count`:

| Modul | Count-Ausdruck | Effektiv |
|---|---|---|
| `module.cognito` | `local.identity_managed ? 1 : 0` | 1 |
| `module.orders_reader` | `local.orders_enabled ? 1 : 0` | 1 |
| `module.mays_orders` | `local.orders_managed ? 1 : 0` | 1 |
| `module.monitoring_orders` | `local.orders_managed ? 1 : 0` | 1 |

Der State von `ris-dev` (seit 2026-10-31) speichert dieselben Ressourcen unter **unindizierten** Adressen (`module.cognito.*`). Terraform wertet `module.cognito` und `module.cognito[0]` als verschiedene Objekte und plant deshalb Destroy+Create des gesamten Moduls — 54 Deletes, 102 Creates im S03-Plan.

Es handelte sich nie um eine fachliche Änderung, sondern ausschließlich um eine Adressinkompatibilität.

---

## 5. Modul-Adressmatrix

| Modul | Alte State-Adresse | Neue Konfigurationsadresse | Count | Ressourcen | Identität |
|---|---|---|---:|---:|---|
| Cognito | `module.cognito` | `module.cognito[0]` | 1 | 12 | Pool `eu-central-1_ojbmoiYGM`, Clients `7ldh…`/`82ji…`, Domain `ris-dev-dev` |
| Orders | `module.mays_orders` | `module.mays_orders[0]` | 1 | 32 | API `zf8tc0k2r2`, Tabelle `ris-dev-mays-orders`, Pool `cmJWXujnb` |
| Orders-Reader | `module.orders_reader` | `module.orders_reader[0]` | 1 | 11 | Lambda `ris-dev-dev-orders-reader`, 4 Routen |
| Monitoring Orders | `module.monitoring_orders` | `module.monitoring_orders[0]` | 1 | 7 | Dashboard + 6 Alarme |

Alle 62 Ressourcen (12+32+11+7) sind 1:1 vorhanden. Für jedes Modul existiert genau ein Zielindex `[0]`; kein Modul hat mehr als eine Instanz. Die Zuordnung ist damit eindeutig und nicht pauschal angenommen.

---

## 6. Implementierte `moved`-Blöcke

In `terraform/main.tf` (Ende der Datei), mit erklärendem Kommentar:

```hcl
moved { from = module.cognito           to = module.cognito[0] }
moved { from = module.mays_orders       to = module.mays_orders[0] }
moved { from = module.orders_reader     to = module.orders_reader[0] }
moved { from = module.monitoring_orders to = module.monitoring_orders[0] }
```

Nur Adressen. Keine Ressourcenparameter, keine Berechtigungen, kein Lifecycle, keine Namen.

Verbotene Mittel wurden nicht verwendet: kein `terraform state mv`, kein Import, kein State-Push, kein `-target`/`-replace`/`-destroy`, kein deaktiviertes Locking, kein unterdrückter Refresh.

---

## 7. Testnachweise

| Prüfung | Ergebnis |
|---|---|
| `terraform fmt -check -recursive` | PASS |
| `terraform validate` | PASS (bekannte Deprecation-Warnungen) |
| `moved`-Syntax | vom Provider/Validator akzeptiert |
| Contract-Tests (`agent_catalog_terraform_seed`, `application_api_security`, `application_privacy_contract`, `p20_api_contract_consistency`) | **51 passed** |
| Installer-Tests (aus S03) | 37 passed |

---

## 8. Neuer Plan

| Feld | Wert |
|---|---|
| Plan-Datei | `/tmp/opencode/ris-dev-s04a.tfplan` (außerhalb Git) |
| Plan-JSON | `/tmp/opencode/ris-dev-s04a-plan.json` (außerhalb Git) |
| **SHA-256** | **`3bb88eddc75055cbb9a1861368344c42eda0037f4d8b0e04caee07e220c5c5af`** |
| Terraform | 1.16.1 |
| Erstellt über | Installer-`plan` (unveränderter Mechanismus) |
| State-Serial danach | 36 (unverändert) |

---

## 9. Änderungsmatrix

| Aktion | Anzahl |
|---|---:|
| CREATE | 48 |
| UPDATE | 3 |
| DELETE | **0** |
| REPLACE | **0** |
| MOVE | 54 |
| READ | 0 |
| no-op | 167 |
| Drift | 1 |

### Creates (48) — vollständig additiv

- **34 API-Routen**: 9 Applications, 8 CVs, 5 CV-Search-Profiles, 5 ATS-Search-Profiles, 5 Manual-Search-Profiles, 2 Privacy (Inspect/Export)
- **7 DynamoDB-Tabellen**: `partner-profiles`, `privacy-receipts`, `erasure-operations`, `s3-erasure-phases`, `upload-ticket-ledger`, `upload-cutover`, `applications`
- **7 IAM-Policies**: applications, partner_profiles, erasure_operations, privacy_receipts, s3_erasure_phases, upload_cutover, upload_ticket_ledger

Routen-Rechnung aufgelöst: 35 Live-Routen, davon 4 Orders-Routen aus `module.orders_reader`; 31 Kernel-Routen live + 34 neue = **65 deklarierte Kernel-Routen**.

### Updates (3)

| Adresse | Art |
|---|---|
| `module.lambda.aws_lambda_function.agent` | neues Code-Bundle + `APPLICATIONS_TABLE` (kein Secret) |
| `module.lambda.aws_iam_role_policy.lambda_documents` | erweiterte Dokument-Handoff-Rechte |
| `module.lambda.aws_iam_role_policy.lambda_dynamodb_platform` | neue Tabellen-ARNs |

Keine dieser Änderungen betrifft Cognito, Orders, CloudFront, DNS oder ACM.

### Drift (1)

`module.cognito[0].aws_cognito_user_pool.users`, Attribut `domain` (`""` → `ris-dev-dev`). Das ist ein **berechnetes** Attribut, das nicht in der Konfiguration steuerbar ist; Terraform plant dafür **keine** Änderung (`resource_changes` enthält no-op). Kein Eingriff nötig.

---

## 10. Schutzgüter-Vergleich

| Gate | Anforderung | Ergebnis |
|---|---|---|
| Cognito Deletes | 0 | **0** ✅ |
| Cognito Replacements | 0 | **0** ✅ |
| Cognito Updates | 0 | **0** (Ressourcenänderungen); 1 informativer Computed-Drift ✅ |
| Orders Deletes | 0 | **0** ✅ |
| Orders Replacements | 0 | **0** ✅ |
| Orders Updates | 0 | **0** ✅ |
| CloudFront / OAC | 0 Änderungen | **0** ✅ |
| DNS / ACM | 0 Änderungen | **0** ✅ |
| Bestehende Tabellen | 0 Delete/Replace | **0** ✅ (11 bestehende unverändert) |
| Modul-Adressmigration | eindeutige 1:1 | **54 Moves, alle no-op** ✅ |
| Unbekannte Änderungen | 0 | **0** ✅ |
| State-Serial nach Plan | unverändert | **36** ✅ |

Jobsearch: Pool `ZURSMpD2O`, Client `5hb3…`, Domain `auth.mays-job-matcher.app`, ACM und die externe CloudFront-Nutzung in Account `590490809858` sind im Plan nicht enthalten.

---

## 11. Verbleibende Blocker

| # | Blocker | Status |
|---|---|---|
| 1 | `RIS_CURSOR_SECRET` nicht bereitgestellt | offen (S03) |
| 2 | Application-Erasure nicht produktiv verdrahtet | offen (S03) |
| 3 | Orders-SQS `Principal="*"` (extern) | offen, nicht Teil des Upgrades |
| 4 | PITR-Entscheidung für neue/bestehende Tabellen | offen |
| 5 | Drift am Cognito-Pool (berechnet, kein Plan-Change) | informativ |

Kein Blocker betrifft mehr die Adressmigration selbst.

---

## 12. GO/NO-GO

**GREEN für S04-A**: Die Adressmigration ist vorbereitet, der Plan ist frei von Deletes und Replacements, alle Schutzgüter bleiben unverändert, der State ist unverändert.

**Keine Deployment-Freigabe.** Vor einem Apply bleiben Secret-Bereitstellung, Erasure-Entscheidung und PITR zu klären; der Plan muss nach diesen Änderungen neu erzeugt und erneut geprüft werden.

**STOP nach S04-A. Kein Apply, keine AWS-Ressourcenänderung.**
