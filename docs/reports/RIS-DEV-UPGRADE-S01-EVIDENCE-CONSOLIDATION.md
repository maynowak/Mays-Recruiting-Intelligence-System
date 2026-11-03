# RIS-DEV-UPGRADE-S01 — Evidence Consolidation

- **Datum:** 2026-11-03
- **Rolle:** OpenCode Commander
- **Zielinstallation:** `ris-dev`
- **Referenzinstallation:** `ris-dev2`
- **Arbeitsmodus:** Repository-Analyse, **keine AWS-Zugriffe, kein Terraform-Plan/Apply**
- **Baseline:** `main` @ `37782f8` (Merge PR #3, ApplicationV1 Persistence)
- **Lokaler Ausgangsstand:** `c49eb2b`, **182 Commits hinter `origin/main`**; vor der Analyse per Fast-Forward synchronisiert
- **Klassifikation S01:** **GREEN für den S01-Auftrag** (Inventar, Trennung historisch/aktuell, Schutzgüter, S02-Aufträge)
- **Klassifikation Upgrade-Bereitschaft:** **RED** — drei blockierende Befunde vor jedem Plan (siehe §7)

---

## 1. Governance und Ausgangslage

Geprüft wurden `docs/AI_AUDITLOG.md`, Branch/HEAD, Working Tree und Remote-Stand. Der tatsächliche Git-Stand widersprach der Auftragsannahme nicht im Inhalt, aber im lokalen Zustand: PR #3 war lokal nicht vorhanden. Nach `git fetch` und Fast-Forward steht der Arbeitsbaum auf `37782f8`.

Vier read-only Analysen wurden parallel durchgeführt:

| Agent | Fokus | Ergebnis |
|---|---|---|
| A | RIS-DEV2-Evidence in `docs/reports/` | Inventar erstellt; zentrale Aussage: **kein belegtes In-Place-Upgrade** |
| B | ApplicationV1 auf `main` | Vollständige Code-/Contract-Analyse inkl. 10 Lücken |
| C | Terraform-Verträge `ris-dev2` vs. `ris-dev` | Overlay-Diff, Ressourceninventar, Replacement-Kandidaten |
| D | Protected Infrastructure | Hard-Stop-Liste, externe vs. Terraform-verwaltete Güter, Widersprüche |

Es wurden keine Dateien außerhalb dieses Reports und der Auditlog-Ergänzung verändert. Historische Reports blieben unverändert.

---

## 2. Evidence-Matrix

| Komponente | DEV2-Evidence | Aktueller Git-Stand | Relevanz für RIS-DEV | Offene Prüfung |
|---|---|---|---|---|
| **Foundation** | `RIS-DEV2-DEPLOY-01-ABSCHLUSSBERICHT.md` / `-EXECUTION.md` (2026-11-02, `35800ed`, Plan `4b25970`): Plan-SHA256 `FC30B406…F431D`, 153 create, Apply „153 added“, State serial 17→23, 160 Ressourcen, Account `262370457690`, Profil `default`. Explizit: „IN-PLACE UPGRADE VERIFIED — NO“. | `main` @ `37782f8`; `ris-dev`-State laut `JM-RIS-AUTH-POOL-REPAIR-01` (2026-10-31) 185 Ressourcen, Account `240571105849`, Workspace `ris-dev`. | Hoch: Ziel erreicht **nie** denselben Reifegrad wie DEV2 in einem Schritt; DEV2 ist Greenfield, nicht Upgrade. | S02: Live-State `ris-dev` (Account, Key, Serial, Lineage, SHA256) und Ist-Ressourcenzahl bestätigen. |
| **Terraform** | `MO-RIS-DEV2-P09-FINAL-INTEGRATION-EVIDENCE-2026.md` (2026-10-28, `06a37a4`, `17398fb`): Plan mit **170 add / 0 change / 0 destroy** in `262370457690`, Workspace `ris-dev2`; drei Lambda-ZIPs als **0-Byte-Platzhalter**; State-Pfad-Diskrepanz `env:/ris-dev2/…` vs. `…/dev/…`; **kein Apply**. `03C`/`03J`: 11 create / 1 update, **85 Drift**. | Root-Module: `api`, `lambda`, `dynamodb` (17 Tabellen), `sqs`, `cognito`, `iam`, `documents`, `health_plane`, `health_public`, `cloudtrail`, `monitoring`, `orders_reader`, `mays_orders` (generiert). | Mittel: Der 170-Ressourcen-Plan ist **nicht** die reale DEV2-Installation und darf nicht als Sollbild gelten. | S02: Plan gegen `ris-dev` neu erstellen und **jede** `replace`-Adresse einzeln ausweisen. |
| **Lambda** | `RIS-DEV2-AUTH-06C-LAMBDA-PACKAGING.md` (2026-11-03): `build_zip.py --bundle all` → `terraform/lambda.zip`, 252192 B, 76 Einträge, SHA256 `f2630322a6887fef860552264f6c6fbeb4e1e8985acc7dbe612e99b6dea8d613`; **nicht hochgeladen**, deployed Hash abweichend. `MO-RIS-DEV2-S02` (2026-10-25, `6afdfb2`): lokaler Build reproduzierbar auf Dateiebene, Container-Reproduzierbarkeit **nicht** verifiziert. | `lambda/build_zip.py` packt `jobsearch/`; PR #3 ergänzt Pfad-Traversal-Schutz (`build_zip.py:188-202`). Neue Env-Variable `APPLICATIONS_TABLE` (`terraform/modules/lambda/main.tf:560`). | Hoch: Bundle muss vor jedem Plan neu gebaut und gehasht werden; 0-Byte-ZIPs sind ein bekannter Fehlerpfad. | S02: Bundles bauen, SHA256 dokumentieren, gegen Installer-Erwartung prüfen; keine 0-Byte-Artefakte zulassen. |
| **SQS** | `MO-RIS-DEV2-P08-B-DEPLOYMENT-ISOLATION-2026.md` (2026-10-28, `17398fb`): **F-03 DEPLOYMENT BLOCKER** — `Principal="*"` in der Orders-SQS-Policy; F-01 offen. | `sqs`-Modul: work, dlq, cv, ats, match; Orders-Queue im generierten Modul. | Hoch: unverändert gültiger Blocker; ein Upgrade darf ihn nicht „miterledigen“. | S02: Policy-Statement in Live/Plan prüfen und als separaten Auftrag behandeln. |
| **Cognito** | `RIS-APPLICATION-DEPLOY-03A-BASELINE.md`: DEV2-Plan referenziert RIS-Pool `ojbmoiYGM` als **extern** (Account `240571105849`) — Cross-Account. `03A` bestätigt `orders_lifecycle=disabled`. | `identity_mode` Default **`managed`** (`terraform/variables.tf:35-44`), `identity_m2m_enabled` Default **`true`**; `ris-dev2` setzt `m2m=false` + Fallback-Issuer/-Client. `ris-dev`-Overlay setzt beides nicht. | Sehr hoch: identische Konfiguration kann auf `ris-dev` **andere** Ressourcen erzeugen als auf `ris-dev2`; M2M-Fallback ist DEV2-spezifisch. | S02: effektive Identity-Shape von `ris-dev` aus State + Plan bestimmen; `identity_m2m_enabled` explizit entscheiden. |
| **CloudFront** | `03A`: DEV2-CloudFront `E1IZKHFPZ5X7SN`; `03C`/`03J`: 85 Drift-Einträge, u. a. CloudFront; `03J` `BLOCKED`, `03K` `REVIEWABLE`. | Nur eine CF-Distribution im Repo (`health_public`); Installer-Guard erlaubt `aws_cloudfront_*` nur über ris-dev2-Allowlist (`installer/ris.py:973-986`). | Hoch: CloudFront-Ersetzung ist ein Stop-Zustand; Guard und Live-Bestand müssen zusammenpassen. | S02: Distribution im `ris-dev`-State identifizieren und Drift getrennt von Anwendungsänderungen bewerten. |
| **ApplicationV1** | `RIS-APPLICATION-E2E-04-ABSCHLUSSBERICHT.md` (2026-11-03): Infrastruktur PASS, **CRUD/Status/Idempotenz/Export/Isolation/Erasure alle BLOCKED** (keine autorisierte synthetische Identität). `05A/05B`: keine aktiven Partner-Apps/Profile/Credentials; Cross-Account-Cognito blockiert Provisioning. | 1 Tabelle `applications` (+ GSI `gsi-owner`), 9 JWT-Routen unter `/v1/partner/me/applications*`, 1 IAM-Policy, 1 Env-Variable; 33 Tests (alle lokal/moto oder statisch). | Hoch: fachlich neu, aber **kein positiver Live-Nachweis**; mehrere Produktionslücken (§3.1). | S02: Anwendungsressourcen im Plan isolieren; `RIS_CURSOR_SECRET` bereitstellen; Erasure-Wiring entscheiden. |
| **IAM** | `03L-APPLY.md` (2026-11-03, `554d37a`): Apply PASS, 11 added / 1 changed, serial 23→24; negative Auth **27/27 → 401**. | Neue Policy `lambda_dynamodb_applications` (`lambda/main.tf:253-269`) mit `TransactWriteItems` auf Tabelle + GSI; **nicht** in `depends_on` der Lambda (`main.tf:592-608`). | Hoch: additive Policy ist unkritisch; Reihenfolge-Lücke kann beim ersten Apply kurz fehlschlagen. | S02: `depends_on` prüfen; Policy-Wirkung im Plan bestätigen. |
| **Runtime** | `RIS-DEV2-AUTH-06`/`06H`: 177 Tests/304 Subtests, ein Windows-Packaging-Fehler; Gate READY, 0 create / 1 update, kein Apply. `E2E-06`: lokaler Harness 8 passed (moto), DEV2-Preflight read-only PASS. | `lambda/handler.py:527-530` dispatcht Application-Routen ohne Agent-/Modellaufruf; Fehler-Mapping 404/409/422/405/503 (`handler.py:635-646`). | Mittel: Handler-Pfad ist sauber getrennt, aber ungetestet gegen echte API GW. | S02: keine Runtime-Blocks; positiver Auth-Test bleibt S03-Thema. |
| **Datenschutz** | `RIS-APPLICATION-DEPLOY-03A`: alle Privacy-Flags `false`, `orders_lifecycle=disabled`. `E2E-04E`: Privacy/Erasure BLOCKED. | Acht Flags hart `"false"` (`lambda/main.tf:575-587`). `ProfileOnlyErasureExecutor` existiert, hat aber **keinen Produktionsaufrufer**; `POST /me/erasure` löscht Applications **nicht**. | Sehr hoch: Datenschutzmatrix/ADR behaupten Teilnahme, der Produktionspfad erfüllt sie nicht. | S02: Erasure-Lücke als Blocker dokumentieren; keine Privacy-Claims für `ris-dev` freigeben. |

---

## 3. Befunde im Detail

### 3.1 ApplicationV1 — verifizierte Lücken (Agent B)

| # | Befund | Evidenz | Auswirkung |
|---|---|---|---|
| 1 | Konto-Erasure löscht Applications nicht | `lambda/handler.py:1190-1285` vs. `agents/ecosystem/privacy_erasure.py:143-207`; Executor ohne Aufrufer | DSGVO-Löschzusage derzeit falsch |
| 2 | `RIS_CURSOR_SECRET` nirgends provisioniert | `jobsearch/application_repository.py:75-79`; kein Treffer in `terraform/` | Pagination/Cursor → 503 im Deployment |
| 3 | Delete nicht versionskonditional, ungepaginated | `application_repository.py:229-233` | Race: Patch kann verloren gehen; >100 Children / >4 MB → Transaktion scheitert |
| 4 | `profileRef`/`cvRef` ohne Ownership-Prüfung | `jobsearch/application_contract.py:53-58,78-83` | Fremde IDs referenzierbar (nur Referenz, kein Inhalt) |
| 5 | History/Cover-Letter erhöhen `version` nicht | `application_repository.py:195-221` | `expectedVersion` schützt Append-Reihenfolge nicht |
| 6 | Inspect/Export liefern nur erste Seite, melden `COMPLETE` | `handler.py:3998-4019,4196-4218` | Unvollständige Auskunft |
| 7 | Keine PITR/Deletion-Protection; TTL auf ungenutztem Attribut aktiv | `terraform/modules/dynamodb/main.tf:496-537` | Kein Wiederherstellungsschutz, irreführende TTL |
| 8 | IAM-Policy nicht in Lambda-`depends_on` | `terraform/main.tf:592-608` | Kurzes Fenster ohne Grant beim ersten Apply |
| 9 | Acht Privacy-Flags default `false` | `terraform/modules/lambda/main.tf:575-587` | Erasure-/Freeze-Maschinerie unerreichbar |
| 10 | Kein Terraform-Wiring-Test für Tabelle/Policy/Env | `tests/` | Regression würde nicht auffallen |

### 3.2 Terraform-Vertragsdelta `ris-dev2` → `ris-dev` (Agent C)

| Schlüssel | `ris-dev` | `ris-dev2` | Wirkung |
|---|---|---|---|
| `identity_m2m_enabled` | nicht gesetzt → **`true`** | `false` | Verhaltensdelta |
| `identity_m2m_fallback_issuer` | nicht gesetzt | `…eu-central-1_ojbmoiYGM` | DEV2-spezifisch |
| `identity_m2m_fallback_client_id` | nicht gesetzt | `82ji073smu1b3fsvj96sonso` | DEV2-spezifisch |
| `orders_lifecycle` | nicht gesetzt → **`managed`** | `disabled` | **≈42 zusätzliche Ressourcen** |
| OAuth-Callbacks/Logouts | 3 Produktions-URLs | nur localhost | Wertdelta |
| `identity_custom_domain_enabled` | **`true`** (HEAD) | `false` | Domain-Flip, 409-Risiko |
| `api_cors_origins` | 3 Origins | nicht gesetzt → `[]` | Wertdelta |

**Replacement-erzwingende Attribute** (Auszug, vollständig in §4 der Agent-C-Analyse): `project`/`environment`-Präfix in allen Namen; `aws_cognito_user_pool.name`; beide `aws_cognito_user_pool_domain`-Ressourcen; `aws_dynamodb_table.name`/Key-Schema (17 Tabellen); alle S3-Bucket-Namen; SQS-Queue-Namen; Lambda-/Rollen-Namen; CloudTrail-Name; CloudFront-OAC + Distribution (folgt Bucket-Namen).

Historische Planzahlen (nicht aktuelle Wahrheit): 2026-10-19 `159 to add`; 2026-10-20 Rename `169 added`; 2026-10-31 `ris-dev` 185 Ressourcen; DEV2 `153 added` → 160, danach `11 added / 1 changed` → 161.

### 3.3 Protected Infrastructure (Agent D)

**Hard-Stop-Liste** — darf durch das `ris-dev`-Upgrade niemals ersetzt/zerstört werden:

- RIS-Pool `eu-central-1_ojbmoiYGM`, Clients `7ldhihlpdgsgcl3puvu4oi7ksv` und `82ji073smu1b3fsvj96sonso`, beide Domain-Ressourcen
- Orders-Pool `eu-central-1_cmJWXujnb`
- ACM `arn:aws:acm:us-east-1:240571105849:certificate/0bfb2603-a919-4b06-b4b9-da246c4edf75`
- **Jobsearch-Produktion:** Pool `eu-central-1_ZURSMpD2O`, Client `5hb3f6dj5ialg77jf4blur9g6g`, Domain `auth.mays-job-matcher.app`, CloudFront `dsv3el0c1dn2.cloudfront.net` — vollständig extern
- Fremde E2E-Distribution `E1R3BHTJNMC6XW` und `mays-ris-e2e-*` OAC
- Route53/Checkdomain-Records (keine `aws_route53_*` im Repo)
- State-Bucket `mays-ris-tf-state-dev`, Lock-Table `mays-ris-tf-lock`, Trail `ris-dev-trail`

**Kritischer Widerspruch:** HEAD `installer/project-configs/ris-dev.json:16` setzt `identity_custom_domain_enabled = "true"` auf `auth.mays-job-matcher.app`, und `tests/test_project_config_overlay.py:74-78` erzwingt diesen Wert. Die Reparatur vom 2026-10-31 (Domain gehört Jobsearch) war im Arbeitsbaum, aber **nicht committet**. Ein Plan auf diesem Stand würde die Prefix-Domain zerstören und die Produktions-Domain an den RIS-Pool binden wollen.

---

## 4. Historisch vs. aktuell

| Kategorie | Einstufung |
|---|---|
| `MO-RIS-DEV2-S00`–`S08`, `P08-A`, `DEPENDENCY-HANDOFF` | **Historisch** (2026-10-25/28); nur Blocker-Listen (F-01…F-07) weiterhin gültig |
| `MO-RIS-DEV2-P09` (170-Ressourcen-Plan) | **Historisch und nie angewendet**; nicht als Sollbild verwenden |
| `RIS-DEV2-DEPLOY-01` | **Historisch**, aber einziger belegter DEV2-Apply (Account `262370457690`) |
| `RIS-APPLICATION-DEPLOY-03*`, `E2E-04*`–`06*` | **Aktuell für DEV2**, aber **nicht übertragbar** auf `ris-dev` (anderer Account/State) |
| `RIS-DEV2-AUTH-06C-LAMBDA-PACKAGING` | **Aktuell** als Methode/Hash-Nachweis, nicht als Deployment-Nachweis |
| `RIS-DEV-UPGRADE-01-EXECUTION.md` | **Historisch**: stoppte bei `validate`, `mayaws` nicht verfügbar, `default` zeigte auf `262370457690` |
| `JM-RIS-AUTH-POOL-REPAIR-01` (2026-10-31) | **Aktuell** für `ris-dev`-Restore und Domain-Schutz |
| `JM-GOOGLE-LOGIN-READINESS-01` (2026-10-31) | **Aktuell** für Auth-Grenzen |

---

## 5. Fehlende Nachweise (explizit)

- Kein `MO-RIS-DEV2-S09`-Report vorhanden.
- Evidenzverzeichnisse für S05, S06, S08 fehlen, obwohl Reports sie behaupten.
- `S06`-Report existiert nur unter abweichendem Dateinamen (`S06_RIS-Wrapper-Pin-And-Build-2026.md`).
- Kein Report belegt ein **In-Place-Upgrade** von `ris-dev2` (DEPLOY-01: ausdrücklich „NO“).
- Kein positiver authentifizierter ApplicationV1-E2E (alle 04*-Phasen BLOCKED).
- Kein Nachweis, welcher Apply State-Serial 24→25 bewegt hat.
- Keine Live-Evidence für `ris-dev` nach dem Restore (nur bis Serial 35/185 aus 2026-10-31).
- Die untracked Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` ist intern inkonsistent (`mayaws`/`mays-ris-*` vs. „RIS-Dev2“) und **keine** verwertbare Evidence.

---

## 6. Wiederverwendbare Ergebnisse

- ApplicationV1-Code ist vollständig auf `main` und additiv deploybar (Tabelle, GSI, 9 Routen, Policy, Env).
- Der Handler-Pfad ist vom Agent-/Modellpfad getrennt und folgt dem bestehenden 401/403/409/422/503-Vertrag.
- Tenant-Isolation ist serverseitig aus JWT + `X-Api-Credential` abgeleitet; Client-Identitätsfelder werden abgewiesen.
- Idempotenz ist serverseitig (`sha256(scope|key)` + `requestHash`) umgesetzt.
- Der DEV2-Lambda-Packaging-Nachweis liefert eine reproduzierbare Methode samt Hash.
- Der DEV2-Plan-/Drift-Prozess (03C → 03J → 03K → 03L) ist als **Verfahren** übertragbar: nie mit Drift applyen, Plan-Hash dokumentieren.

---

## 7. Blocker und Risiken für das Upgrade

1. **Produktions-Domain-Konflikt (RED):** `ris-dev`-Overlay beansprucht `auth.mays-job-matcher.app`; die Domain gehört live zum Jobsearch-Pool. Ein Plan würde sie umhängen oder mit 409 scheitern.
2. **Kein Upgrade-Nachweis (RED):** Weder DEV2 noch `ris-dev` haben ein belegtes In-Place-Upgrade; DEV2 ist ein Greenfield-Apply in einem anderen Account.
3. **Orders-SQS `Principal="*"` (RED, extern):** unverändert offener Deployment-Blocker.
4. **ApplicationV1-Datenschutzlücke (RED):** Konto-Erasure entfernt Applications nicht, obwohl ADR/Privacy-Matrix Teilnahme behaupten.
5. **`RIS_CURSOR_SECRET` fehlt (ORANGE):** Pagination bricht im Deployment.
6. **Identity-Shape-Delta (ORANGE):** `identity_m2m_enabled` default `true` auf `ris-dev` vs. `false` auf DEV2.
7. **`orders_lifecycle` default `managed` (ORANGE):** ≈42 Ressourcen, die DEV2 bewusst ausgeschlossen hat.
8. **Fehlende Evidence (ORANGE):** S09, S05/S06/S08-Evidenz, Serial-24→25-Apply.

---

## 8. Aufträge für S02 (konkret)

**S02-A — Live-Baseline `ris-dev` (read-only):**
STS-Account/Region/Profil, Workspace `ris-dev`, Backend-Key `env:/ris-dev/dev/terraform.tfstate`, Bunny-Version, Lineage, Serial, SHA256, Ressourcenzahl; Nachweis, dass es **nicht** `262370457690` ist.

**S02-B — Schutzgüter-Abgleich:**
Für jedes Hard-Stop-Objekt aus §3.3 im State prüfen: vorhanden/fehlend, Adresse, `prevent_destroy`-Status. Abweichungen stoppen den Plan.

**S02-C — Plan-Scope ohne Anwendung:**
Neuen Plan mit `project_name=ris-dev`, `orders_lifecycle=disabled`, `identity_custom_domain_enabled=false` erzeugen. Erwartung: additiv (Applications-Tabelle, GSI, 9 Routen, IAM, Env) plus ggf. Orders-Out-of-Scope. Jede `replace`/`delete`-Adresse einzeln ausweisen und begründen.

**S02-D — Identity-Entscheidung:**
`identity_m2m_enabled` und ggf. Fallback-Issuer/Client explizit festlegen; prüfen, ob `ris-dev` dadurch M2M-Ressourcen ändert.

**S02-E — Artefakte:**
`python lambda/build_zip.py --bundle all`, SHA256 für `terraform/lambda.zip` und `lambda/dist/*.zip` dokumentieren; 0-Byte-Artefakte ausschließen; `RIS_CURSOR_SECRET`-Bereitstellung entscheiden.

**S02-F — Drift- und Schutz-Gate:**
Drift-Inventar getrennt nach Typ; jede Änderung an Cognito/CloudFront/Route53/ACM/JWT/Orders ist ein Stop. Plan-Hash dokumentieren, Review vor Apply.

**S02-G — Datenschutz-Entscheidung:**
Erasure-Wiring für Applications vor jedem echten Datenfluss; bis dahin keine Privacy-Claims für `ris-dev`.

---

## 9. Abnahmekriterien S01

| Kriterium | Status |
|---|---|
| RIS-DEV2-Reports inventarisiert | ✅ 20+ Reports, inkl. Lückenliste |
| ApplicationV1-Änderungen identifiziert | ✅ Tabelle/GSI, 9 Routen, IAM, Env, 10 Lücken |
| Geschützte Ressourcen dokumentiert | ✅ Hard-Stop-Liste + extern/TF-Klassifikation |
| Historisch und aktuell getrennt | ✅ §4 |
| Fehlende Nachweise benannt | ✅ §5 |
| S02 erhält konkrete Prüfaufträge | ✅ §8 |

**STOP nach S01. Kein Start von S02.**
