# RIS-B4-PERSISTENT-AGENT-CATALOG-WRITER-AND-SEEDER-01 — Execution Log

STATUS: **GREEN** — Writer, Seeder und Unseed implementiert; persistenter Agent Catalog erstmals befüllt; Read-Back über den **bestehenden** Read Path und **live im Lambda** belegt; 31 neue Tests grün; keine Regression; **keine** IAM-/Terraform-/Cognito-/Gateway-Änderung.

- Datum: 2026-10-05 UTC
- Git HEAD bei Gate-Start: `365b337` (Branch `main`)
- Account/Profil/Region/Workspace: `240571105849` / `mayaws` / `eu-central-1` / `mays-ris`
- Voraussetzung für: **B3** (bleibt blockiert)

---

## 1. Discovery Ausgangslage

Quelle: `docs/reports/RIS-B3-B4-COGNITO-AND-AGENT-ENTRYPOINT-DISCOVERY-07.md` (GREEN / HARD STOP).

| Artefakt | Discovery-Befund |
|---|---|
| Agent Registry | ✅ vorhanden (`agents/ecosystem/registry.py`, In-Memory) |
| persistent Catalog Read Path | ✅ vorhanden (`CatalogAdapter` + `handler._init_catalog`) |
| **Catalog Writer** | ❌ **fehlte** |
| **Seeder** | ❌ **fehlte** |

Belegte Ursache aus Discovery-07: In `agents/` und `lambda/` existierte **kein** `put_item`/`update_item`/`batch_writer` für `agent-catalog`. Alle Schreibpfade gingen in offers, credentials, api-profiles, work-queue, user-profile. Der fehlende Writer ist laut `agents/ats_agent/registry.py` eine **bewusste** Architekturgrenze, keine Regression.

## 2. Vorhandenes Catalog Schema — abgeleitet, nicht erfunden

**Terraform-Quelle** (`terraform/modules/dynamodb/main.tf:87-114`): `hash_key = "agentId"` (S), Attribut `status` (S), `ttl { attribute_name = "expiresAt", enabled = true }`, GSI `gsi-status` auf `status` mit `projection_type = "ALL"`.

**Live verifiziert** (`describe-table` + `describe-time-to-live`):

| Feld | Wert |
|---|---|
| TableName | `mays-ris-dev-agent-catalog` |
| TableArn | `arn:aws:dynamodb:eu-central-1:240571105849:table/mays-ris-dev-agent-catalog` |
| TableStatus | `ACTIVE` |
| KeySchema | `[{AttributeName: agentId, KeyType: HASH}]` |
| GSI | `['gsi-status']` |
| BillingMode | `PAY_PER_REQUEST` |
| TTL | `ENABLED` auf `expiresAt` |
| ItemCount bei Start | `0` |

> **Methodischer Hinweis:** `describe-table` lieferte `TimeToLiveDescription: null`. TTL habe ich deshalb **zusätzlich** über `describe-time-to-live` verifiziert (`ENABLED`/`expiresAt`) statt die API-Antwort zu interpretieren. Das ist relevant, weil der Seeder `expiresAt` bewusst nicht schreibt.

**Keine neue Tabelle, kein neues Attribut, keine Schema-Version** wurde erzeugt.

## 3. Vorhandener Read Path — vollständig nachvollzogen

Drei bestehende Leser müssen die Item-Form bedienen; alle drei lesen dieselbe Feldmenge:

| Leser | Ort | Rolle |
|---|---|---|
| `_init_catalog` | `lambda/handler.py:42-88` | **LIVE** Coldstart: `CatalogAdapter().get_all_agents()` → `normalize_agent_status()` → `AgentDescriptor` → `get_registry().register()` |
| `_convert_to_descriptor` | `agents/ecosystem/catalog_adapter.py:165` | `populate_registry_from_catalog()` — existiert, **kein** produktiver Aufrufer |
| `_get_agent_catalog` | `lambda/handler.py:1703` | Roh-Scan; Items werden ungefiltert als Response ausgegeben (`GET /agents`, `_get_agent`, `_execute_agent`) |

Konsumierte Attribute: `agentId`, `status`, `name`, `version`, `capabilities`, `supported_bodies`, `supported_runtimes`, `risk_level`, `description`, `metadata`.

**Namensdiskrepanz, die ich nicht glätte:** `CatalogAdapter.get_agent` (`catalog_adapter.py:84-95`) projiziert `runtime`, `bodyVersion`, `config` — Felder, die **kein** anderer Leser verwendet; die Descriptor-Konverter lesen stattdessen `supported_runtimes`/`supported_bodies`. Diese Methode hat **null produktive Aufrufer** (`grep get_agent(` findet nur `handler._get_agent(event, …)`, eine andere Funktion). Ich habe deshalb **keine** Felder dafür geschrieben und **keine** Namensauflösung erfunden — der Konflikt ist dokumentiert und gehört in ein eigenes Gate.

## 4. `verify_api_credential` und sein Catalog-Lookup

`agents/ecosystem/credentials.py:816-830`, Schritt 14: `raw_status = catalog.get(agent_id)`; bei `dict` wird `.get("status")` genommen; danach die zentrale `is_executable_status()`. `None`/leer/unbekannt → **DENY `agent-not-executable`**. `catalog` ist **Pflicht** (`ValueError("catalog is required")`).

Das ist genau der Mechanismus, der B3 blockierte: leerer Catalog ⇒ `agent-not-executable`. Der Parameter wird live in `handler._build_introspection_sources()` gefüllt: `catalog = {agent_id: item.get("status") for …}`.

**Kein echtes opaque Credential erzeugt.** Geprüft wurde ausschließlich die Auflösbarkeit des Catalog-Agenten als Operation-Target.

## 5. Fehlender Write Path → implementierter Writer

**Neu:** `agents/ecosystem/catalog_writer.py`

```
Runtime AgentRegistry ──expliziter Aufruf──> CatalogWriter ──put_item──> DynamoDB agent_catalog
```

Die geforderte Richtung ist eingehalten: der Writer wird **nie** automatisch aus der Registry aufgerufen und hält **keine** Referenz auf eine `AgentRegistry` (belegt durch `test_writer_does_not_touch_runtime_registry`).

| Anforderung | Umsetzung |
|---|---|
| Eintrag persistieren | `CatalogWriter.put_agent(item)` / `put_descriptor(descriptor)` |
| Datenform wie Read Path | `catalog_item_from_descriptor()` projiziert **explizit** (kein generisches `asdict`) auf genau die 10 Felder des Read Paths |
| Idempotenz | `agentId` ist Hash-Key → `put_item` überschreibt in-place. Live belegt: 3 Läufe → 1 Row |
| **Fehler nicht verschlucken** | Jeder Store-Fehler → `CatalogWriteError`; ein „erfolgreich"-Ergebnis ist bei Fehler **unerreichbar** (Test `test_store_failure_is_raised_not_swallowed`) |
| Keine Runtime-Registry-Änderung | s. o. |
| Keine Business-Entitlements | geschlossene Feld-Allowlist; der Writer kennt Entitlements nicht |

**Status-Konvention wiederverwendet, nicht neu erfunden:** `normalize_agent_status()` / `is_executable_status()` aus `agents/ecosystem/agent_status.py`. Unbekannter/leerer Status wird beim Schreiben **abgelehnt** statt eine Zeile zu erzeugen, die kein Leser akzeptieren würde.

**Security-Härtung:** geschlossene Allowlist `WRITABLE_FIELDS`. Ein unbekanntes Attribut (z. B. `secretToken`) ist ein **harter Fehler**, kein stilles Mitschreiben — damit kann eine spätere Änderung das persistierte Feldset nicht unbemerkt weiten.

**`expiresAt` wird bewusst nicht geschrieben:** TTL ist auf diesem Attribut `ENABLED`; ein geschriebenes `expiresAt` ließe den Seed still verschwinden. Retention ist ein separates Gate (Discovery-07), dieses Modul erfindet dafür keine Architektur.

## 6. Seeder

**Neu:** `installer/scripts/seed_agent_catalog.py` — folgt der Repo-Konvention des vorhandenen Seeders `installer/projects/mays_orders/scripts/seed_orders.py` (boto3 **resource**-API, argparse, idempotent, Stat-Ausgabe).

| Anforderung | Umsetzung |
|---|---|
| Als Seed-Schritt erkennbar | eigenständiges Provisioning-Skript unter `installer/scripts/`; **kein** Import in den Worker-/Lambda-Pfad |
| Synthetisch, nicht personenbezogen | nur Agent-Fähigkeitsbeschreibung; Test `test_seed_item_is_synthetic` prüft explizit auf `secret`, `token`, `password`, `credential`, `@`, `bearer`, `key` |
| Deterministisch | keine Uhrzeit, keine Zufallswerte, keine Laufzeitabhängigkeit; Test `test_rerun_is_deterministic` vergleicht zwei frische Tabellen |
| Kein Duplikatbestand | `put_item` auf Hash-Key; live belegt: 3 Läufe → 1 Row; `--skip-existing` lässt eine vorhandene Zeile unangetastet (Konvention `seed_orders.py`) |
| Naming-Konventionen übernommen | `agentId`/`status` aus Terraform; Status-Enum aus `registry.py`; Feldnamen aus dem bestehenden Read Path |
| Read Path bedienen | Descriptors werden identisch zu `handler._init_catalog`/`_convert_to_descriptor` projiziert |

**Unseed:** `installer/scripts/unseed_agent_catalog.py` — explizite Positiv-Liste `("reference_agent",)`, kein „alles löschen", kein Pattern-Match. Meldet verbleibende Fremdeinträge und liefert dann Exit-Code 1. **Live nicht ausgeführt** (der Seed soll stehen bleiben).

## 7. Verwendeter synthetischer Agent

**`reference_agent`** — der bereits im Repo vorhandene kanonische Referenz-/Nachweis-Agent. Kein neuer Agent-Typ erfunden.

| Eigenschaft | Wert | Quelle |
|---|---|---|
| `agentId` | `reference_agent` | `agents/runtime/pipeline.py:53` (`REFERENCE_AGENT_ID`) |
| `capabilities` | `["reference.echo"]` | `REFERENCE_CAPABILITY`, `pipeline.py:54` |
| `supported_bodies` | `["1.0.0"]` | `BODY_VERSION`, `pipeline.py:51` |
| `supported_runtimes` | `["python3.14"]` | `RUNTIME_LAMBDA`, `pipeline.py:52` |
| `status` | `ACTIVE` | `AgentStatus.ACTIVE` (Pipeline-Definition) |
| `description` | „Technischer Nachweis-Agent (Echo, keine Domain-Logik)" | `pipeline.py:107` |

Der Seeder **liest diese Konstanten** aus `agents.runtime.pipeline` statt sie ein zweites Mal zu hartkodieren — der Seed kann nicht vom kanonischen Runtime-Definition abdriften. Test `test_seed_descriptor_taken_from_runtime_pipeline` belegt das. Zusätzlich bricht der Seeder ab, falls Modul- und Seeder-Konstante auseinanderlaufen (`seed agent id mismatch … refusing to guess`) — keine stillen Annahmen.

**Warum `reference_agent` und nicht `ats-agent`:** `ats-agent` ist als „erster echter Domain Agent" annotiert und delegiert via HTTP an `mays-jobsearch`. Ein synthetischer Seed-Eintrag sollte keine Domain-Integration suggerieren. `reference_agent` ist explizit ein technischer Nachweis-Agent ohne Domain-Logik — die semantisch richtige Wahl. Der Tester entscheidet das; ich habe es begründet und nicht erweitert.

## 8. Idempotenz

| Nachweis | Ergebnis |
|---|---|
| Unit: 3× `seed()` auf dieselbe Fake-Tabelle | `put_calls == 3`, **1** Item |
| Unit: `--skip-existing` bei vorhandener Zeile | `outcome=skipped`, Status bleibt `INACTIVE` (unangetastet) |
| Unit: zwei frische Tabellen | identische Items (deterministisch) |
| Unit: `--dry-run` | `put_calls == 0`, Tabelle leer |
| **Live: 3 Seeder-Läufe gegen `mays-ris-dev-agent-catalog`** | **Lauf 1 `written`, Lauf 2 `written` (overwrite), Lauf 3 `--skip-existing` → `skipped`; `scan` = 1 Row** |
| Live: unseed-Simulation | `test_unseed_removes_only_seed_entries` — Fremdeintrag bleibt, Exit-Code-1-Pfad existiert |

## 9. Read-back Ergebnis

Vier unabhängige Nachweise. Die Kette ist bewusst **nicht** aus dem Write-Result abgeleitet.

| # | Nachweis | Ergebnis |
|---|---|---|
| 1 | Seeder-intern über **bestehenden** Read Path (`CatalogAdapter.get_all_agents()`) | `readback_found=True`, `readback_status=ACTIVE` |
| 2 | Echter Produktiv-Codepfad `handler._init_catalog()` gegen die **Live**-Tabelle | `Registered agent: reference_agent`, `Catalog initialized: 1 agents registered`; Descriptor vollständig korrekt (`status=AgentStatus.ACTIVE`, `capabilities=['reference.echo']`, `can_execute('reference.echo')=True`, `supports_capability('reference.echo')=True`) |
| 3 | **LIVE Lambda** (Gateway `GET /agents`, Produktion, echte Tabelle) | CloudWatch-Log des echten Coldstarts: `Registered agent: reference_agent` + `Catalog initialized: 1 agents registered` |
| 4 | **LIVE** `verify_api_credential`-Schritt-14-Logik gegen die Live-Tabelle | Produktionsform `{'reference_agent': 'ACTIVE'}` → Lookup `raw_status='ACTIVE'` → `is_executable_status=True` → **kein** `agent-not-executable` |

**Persistiertes Live-Item (vollständig):**

```
agentId            = reference_agent
status             = ACTIVE
name               = reference_agent
version            = 1.0.0
description        = Technischer Nachweis-Agent (Echo, keine Domain-Logik)
capabilities       = ["reference.echo"]
supported_bodies   = ["1.0.0"]
supported_runtimes = ["python3.14"]
risk_level         = low
metadata           = {}
```

Kein `expiresAt` — wie beabsichtigt.

### Live-HTTP-Gegenprobe und warum sie leer ist

`GET /agents` lieferte `{"agents": []}` und `/v1/introspection` lieferte `capabilities: []`. **Das ist kein Fehler des Seeds**, sondern korrektes fail-closed-Verhalten:

`handler._handle_agents` (`:682-717`) ist **kein** roher Catalog-Dump, sondern **entitlement-gefiltert**: es iteriert `_get_entitlements(userId, tenantId)` und gibt nur Agenten zurück, für die eine gültige Entitlement existiert **und** die im Catalog `ACTIVE` sind. Die `entitlements`-Tabelle hat **0 Rows** → keine Entitlement → keine Agent-Anzeige. Die Probe-User bekamen bewusst **keine** Entitlement: das Gate verbietet unter §1 „Entitlements redesign" und unter §5 „KEINE Business-Entitlements erfinden".

Die Entitlements liegen genau **vor** dem Catalog in der Kette Credential → APIProfile → **Entitlement** → Agent Catalog → Agent Status → Execution. Der Catalog-Nachweis selbst ist über die Lambda-Logs (Nachweis 3) und die Schritt-14-Logik (Nachweis 4) erbracht.

## 10. `verify_api_credential` Ergebnis

| Prüfung | Ergebnis |
|---|---|
| Catalog-Auflösung für `reference_agent` | ✅ `raw_status='ACTIVE'` → ausführbar |
| Negativ-Gegenprobe: unbekannter `agentId` | ✅ `None` → `is_executable_status=False` → `agent-not-executable` |
| Gegenprobe: Catalog leer (Zustand vor diesem Gate) | ✅ `is_executable_status(None)=False` — das war der B3-Blocker |
| **Voraussetzung für B3** | ✅ **erfüllt**: ein real existierender, auflösbarer Catalog-Eintrag steht bereit |
| Produktive Aufrufer von `verify_api_credential` | **unverändert 0** — Test `test_verify_api_credential_still_has_no_productive_caller` per `grep` über `lambda/` und `agents/` belegt, dass dieses Gate B3 **nicht** versehentlich verdrahtet hat |

**Kein echtes Credential erzeugt, kein Bearer getestet, kein Secret gespeichert.** B3 bleibt blockiert.

## 11. IAM Änderungen

**Keine. Zero-IAM-Mutation.**

| Aspekt | Befund |
|---|---|
| Lambda-Rolle `mays-ris-dev-agent` auf agent-catalog | **nur lesend**: `GetItem`, `Query`, `BatchGetItem`, `Scan` (`mays-ris-dev-lambda-dynamodb-platform`) — **kein `PutItem`** |
| Warum das richtig ist | Der Runtime-Pfad soll den persistenten Catalog **nie** schreiben. Least Privilege wird dadurch nicht durch eine neue Policy hergestellt, sondern **erhalten** |
| Seeder-Kontext | `arn:aws:iam::240571105849:user/Mayaws` — der bestehende Operator-Kontext, kein neues IAM-Objekt |
| Neue Wildcard-Rechte | **keine** |
| IAM-Rollen-Policies gesamt | 8 — unverändert zu Discovery-07 |
| `mays-ris-lambda-policy` | unangetastet |

Der Schreibzugriff ist damit ein **Out-of-Band-Provisioning-Schritt**, kein Runtime-Recht. Das ist genau die Architekturgrenze, die Discovery-07 als bewusste Trennung beschrieben hat.

## 12. AWS Mutation

| Schritt | Ergebnis |
|---|---|
| Kontext vorher | `240571105849` / `mayaws` / `mays-ris` / `main`@`365b337`; Ziel-Resource eindeutig per ARN verifiziert |
| Dry-Run vor der Mutation | `Outcome=dry-run`, 10 geplante Felder, **kein** `expiresAt` |
| Lauf 1 | `written`, `readback_found=True` |
| Lauf 2 (Idempotenz) | `written` (overwrite), `readback_found=True` |
| Lauf 3 (`--skip-existing`) | `skipped` |
| Endstand Catalog | **1 Row**: `reference_agent` / `ACTIVE` / `["reference.echo"]` |
| Probe-User | `b4-probe` angelegt (JWT/Claim-Lesen), danach gelöscht — User-Bestand **14 → 14** verifiziert |
| tmp-Verzeichnis | Passwort/Token-Verzeichnis (`chmod 700`) entfernt |

### Unveränderte Ressourcen (Nachweis)

| Ressource | Wert | Vergleich |
|---|---|---|
| `api-profiles` | 9 | Gate-06-Endstand ✅ |
| `credentials` | 6 | Gate-06-Endstand ✅ |
| `entitlements` | **0** | unverändert ✅ |
| `user-profile` | 1 | (Gate 06: nach Löschen des Probe-Users 1 verblieben) ✅ |
| Cognito Pool | `LastModifiedDate 2026-10-02T18:31:08.262+00:00` | identisch ✅ |
| Gateway | 27 Routen, 1 Authorizer | identisch ✅ |
| Lambda | `CodeSha256 ECemCxwAOv0fNo3OeAkxjpT3Eg+Xyl9LZB61h3R4VvQ=` | identisch ✅ |
| IAM Role Policies | 8 | identisch ✅ |
| Terraform | keine Datei angefasst (`git status terraform/` ohne tracked Änderung) | ✅ |

**Einzige Datenmutation dieses Gates: 1 Zeile in `mays-ris-dev-agent-catalog`.**

> **Ehrliche Anmerkung:** `describe-table` meldete nach dem Write `ItemCount = 0`. Das ist die bekannte verzögerte Metrik-Aktualisierung von DynamoDB. Der autoritative Nachweis ist `scan` (1 Row) sowie die vier Read-Backs in §9.

## 13. Security

| Prüfung | Ergebnis |
|---|---|
| Least Privilege des Schreibers | ✅ Schreiben nur out-of-band; Runtime bleibt read-only |
| Keine neuen Wildcard-IAM-Rechte | ✅ keine IAM-Änderung |
| Keine Secrets im Catalog | ✅ Feld-Allowlist; `metadata={}`; Test prüft auf `secret`/`token`/`password`/`credential`/`bearer`/`key` |
| Keine Tokens / Passwörter | ✅ nur `reference_agent`-Deskriptor |
| Keine personenbezogenen Daten | ✅ keine User-ID, kein Tenant, keine E-Mail |
| Keine unnötigen Logs | ✅ Seeder gibt nur Agent-ID, Outcome, Status, Capabilities aus; Writer loggt nichts |
| Kein Cross-Tenant-Zugriff | ✅ Catalog-Eintrag ist tenantneutral; keine `tenantId` geschrieben |
| Kein Credential im Catalog | ✅ getestet und live verifiziert |
| Unbekanntes Attribut | ✅ harter Fehler statt stillem Mitschreiben |

**Gesamt: GREEN.** Kein neu entdecktes Sicherheitsproblem.

## 14. Tests

### Neue Tests

| Datei | Tests | Inhalt |
|---|---|---|
| `tests/test_agent_catalog_writer.py` | **16** | Writer-Unit (Persistenz, Item-Form, kein `expiresAt`, Status-Normalisierung, unbekannter Status/Attribut/fehlendes Feld, Store-Fehler, Registry-Unberührung, fehlende Table-Config) + Read-Back über bestehenden Read Path (4) |
| `tests/test_agent_catalog_seeder.py` | **15** | Seed-Descriptor aus Pipeline (4), Idempotenz (6), `verify_api_credential`-Auflösung (4), Negativ-Gegenprobe, B3-nicht-verdrahtet-Garantie |
| **Summe** | **31** | alle grün |

### Bestehende Suite — Baseline-Diff statt Bauchschmerz

Ich habe die vorhandenen Fehler **nicht** als „vorbestehend" behauptet, sondern gemessen (`git stash`, identischer Lauf):

| Lauf | Ergebnis |
|---|---|
| `tests/` mit meinen Änderungen | 8 failed, **813 passed**, 8 skipped, 1 error |
| `tests/` auf HEAD (Änderungen gestasht) | 8 failed, **782 passed**, 8 skipped, 1 error |
| `diff` der Fehlerlisten | **IDENTISCH** → **keine Regression** |

Delta: **+31 passed** (meine neuen Tests), Fehlerbestand unverändert.

Die 8 Failures + 1 Error sind Baseline und bestehen **unabhängig von diesem Gate**: `test_agent_invocation` (2), `test_platform_handlers` (5: Entitlement-Validierung, `test_me_extracts_groups`, `test_platform_with_custom_env`, SQS), `test_reference_agent::test_valid_work_item`, `test_processing_chain::test_handler`. Zusätzlich 6 Collection-Errors unter `installer/projects/mays_orders/**` (`ModuleNotFoundError: No module named 'installer.core' / 'index' / 'errors' / 'state_machine'`) — ein **getrenntes** Projekt mit eigenen Importpfaden, vom Repo-Root-`pytest` nicht auflösbar. Keine dieser Dateien wurde von mir angefasst.

**Kein Test wurde abgeschwächt, geändert oder gelöscht.** Keine künstlichen Tests zum Erhöhen der Testzahl: jeder neue Test prüft Writer-, Idempotenz-, Fail-closed- oder Read-Back-Verhalten, kein Test prüft nur Existenz.

### Bestehender Read Path bleibt GREEN (§10 D)

`tests/test_agent_status_normalization.py` (Status-Fail-closed, Eligibility) läuft unverändert grün. Zusätzlich belegen die neuen Tests, dass `populate_registry_from_catalog` weiterhin fail-closed blockiert (`test_existing_read_path_still_fail_closed_on_bad_status`) und den Seed korrekt registriert (`test_existing_registry_population_registers_it`).

## 15. Build / Lint / Type Checks

| Check | Ergebnis |
|---|---|
| `python3 -m py_compile` (alle 6 geänderten/neuen Dateien) | ✅ OK |
| Ungenutzte-Import-Prüfung (AST, stdlib) | ✅ keine — ein zunächst unbenutzter Import in `test_agent_catalog_seeder.py` wurde entfernt |
| `pytest tests/` | ✅ 813 passed |
| `flake8` / `mypy` / `ruff` | **nicht im Projekt vorhanden** (`No module named …`) — es gibt keine solche Konfiguration (`setup.py`, `pyproject.toml`, `tox.ini`, `.flake8` existieren nicht). Ich erfinde keinen Linter |
| TypeScript | **nicht anwendbar** — kein TS-Build im Repo-Build-Pfad |
| `terraform validate` | ⚠️ „validation warnings as shown above" — **Baseline**, keine `.tf`-Datei angefasst |
| `terraform fmt -check -recursive` | ⚠️ 6 Dateien nicht formatiert (`main.tf`, `variables.tf`, 4 Module) — **Baseline**, `git status terraform/` zeigt keine tracked Änderung dieses Gates |
| Build | **nicht anwendbar** — kein Build-Schritt für Python im Projekt; `.github/workflows/ci-cd.yml` macht ausschließlich Terraform (`init`/`validate`/`fmt`/`plan`/`apply`), keinen Python-Build und kein pytest |

## 16. Korrektur am bestehenden Read Path

**Ein bestehender Defekt gefunden und minimal behoben** (im Gate-Scope „bestehende Catalog-Verification absichern"):

`populate_registry_from_catalog(registry, table_name)` konnte **kein** `dynamodb`-Resource injizieren. Folge: Der Read Path war gegen eine InMemory-Quelle **nicht testbar** — mein erster Testlauf griff deshalb auf echtes AWS zu (Fehlerbild: `AccessDeniedException … Scan` auf Account `992382612204`, also die *falsche* Identität über ambient credentials).

Korrektur (`catalog_adapter.py`): optionaler Parameter `dynamodb=None`, additiv und rückwärtskompatibel — bei `None` bleibt das Produktionsverhalten unverändert. Damit ist der bestehende Read Path überhaupt erst verifizierbar, und Tests können ihn nicht versehentlich gegen echtes AWS fahren.

**Keine Verhaltensänderung in Produktion.** Nachgewiesen durch den unveränderten Lambda-Hash (kein Deployment) und die grüne Suite.

**Eigener Fehler, transparent:** dieser Test-Hit auf den falschen Account war mein Fehler (fehlende Dependency-Injection-Annahme), nicht eine bestehende Sicherheitslücke. Ich habe ihn im Log dokumentiert statt ihn wegzulassen.

## 17. Git Commit

Geänderte/neue Dateien:

| Datei | Art |
|---|---|
| `agents/ecosystem/catalog_writer.py` | neu — der Writer |
| `installer/scripts/seed_agent_catalog.py` | neu — der Seeder |
| `installer/scripts/unseed_agent_catalog.py` | neu — expliziter Unseed |
| `tests/test_agent_catalog_writer.py` | neu — 16 Tests |
| `tests/test_agent_catalog_seeder.py` | neu — 15 Tests |
| `agents/ecosystem/catalog_adapter.py` | geändert — additive `dynamodb`-Injektion (1 Signatur + 1 Aufrufzeile + Docstring) |
| `docs/reports/RIS-B4-PERSISTENT-AGENT-CATALOG-WRITER-AND-SEEDER-01-EXECUTION_LOG.md` | neu — dieser Log |

**Nicht** committed: 9 vorbestehende untracked Reports (fremde Gates), `terraform/.terraform.lock.hcl` (Nebenprodukt meiner `terraform`-Läufe, kein Gate-Inhalt).

## 18. Push

Nach `git status` → Tests → Commit → `git push origin main`.

`main` hatte **keinen Upstream-Branch** konfiguriert; deshalb explizit `origin main` (kein `--set-upstream`, kein Force).

| Feld | Wert |
|---|---|
| Commit | `40f56a4` (`feat(catalog): persistent agent catalog writer and seeder`) |
| Push | `8387933..40f56a4  main -> main` (Fast-Forward) |
| lokaler HEAD | `40f56a40c87e82395c8c34b6c7d59e6c9b4904f4` |
| `origin/main` | `40f56a40c87e82395c8c34b6c7d59e6c9b4904f4` — **identisch** |
| Divergenz | keine |

Hinweis: `origin/main` stand vor dem Push auf `8387933`, also **ahead** meines Gate-Start-HEADs `365b337`. Diese Commits waren bereits in meiner lokalen Historie enthalten — der Push war ein sauberer Fast-Forward, kein Force, kein Verlust fremder Commits.

## 19. Working Tree

Nach dem Gate: **0 modified tracked files** (verifiziert nach Commit).

Verbleibend untracked und **bewusst nicht** committed:

| Eintrag | Grund |
|---|---|
| 8 vorbestehende `docs/reports/*.md` | fremde Gates, nicht in diesem Auftrag |
| `terraform/.terraform.lock.hcl` | Nebenprodukt meiner `terraform`-Läufe, kein Gate-Inhalt (keine `.tf`-Datei geändert) |

## 20. AI Audit

- `docs/AI_AUDITLOG.md` befolgt: Kontext-Gate, Precheck, Findings, Evidence-Referenzen, Classification, Terraform-/AWS-Checks, Git-Status, Dateiliste, Open Questions, Risks, Recommended next actions.
- Secrets: kein Secret, Token, Passwort oder vollständiges JWT in diesem Log. Der Probe-User wurde gelöscht, sein tmp-Verzeichnis (Passwort/Token) entfernt. Der Credential-Secret-Scan über die Report-Dateien lief vor dem Commit.
- Alle Aussagen in §9/§10 beruhen auf **live ausgeführten** Kommandos mit ausgegebenem Ergebnis; keine Behauptung ohne Beleg.
- Eigene Fehler (CLI-Parameter, falscher Test-Hit auf den falschen Account, unbenutzter Import, CJK-Prüfung) sind im Log benannt statt geglättet.
- Keine eigenmächtige Entscheidung über den Gate-Auftrag hinaus: kein Seed-Agent erfunden, keine Entitlements erzeugt, kein B3 verdrahtet, keine Retention-Architektur, keine Terraform-/IAM-Änderung.

## 21. Nicht implementiert (bewusst)

Kein B3/opake Credential, kein APIProfile-Code, keine Credential-Ausstellung, kein Credential-Verification-Redesign, kein Cognito/OAuth/Resource-Server/Scope, kein API-Gateway-Auth, keine Tenant-Claim-Änderung, kein Offers-/Entitlements-Redesign, kein Frontend, kein Jobsearch, kein Agent-Registry-Redesign, kein Retention-/Privacy-Gate, kein P17, kein P20.

## 22. Offene Punkte

1. **`CatalogAdapter.get_agent`-Namensdiskrepanz** (`runtime`/`bodyVersion`/`config` vs. `supported_runtimes`/`supported_bodies`) — tote Methode, aber echte Inkonsistenz. Eigenes Gate.
2. **`GET /agents` bleibt entitlement-gefiltert.** Um den Seed über HTTP sichtbar zu machen, wäre eine Entitlement nötig — vom Gate ausdrücklich untersagt. Gehört in ein eigenes Gate, das Agent-Authorization Ende-zu-Ende prüft.
3. **`expiresAt` bleibt offen.** Der Seed ist dauerhaft und synthetisch; Unseed existiert als expliziter Weg. Retention bleibt eigenes Gate.
4. **Weitere Agenten im persistenten Catalog?** Nicht entschieden — der Seeder registriert genau den einen kanonischen Referenz-Agenten. Ob `ats-agent`, `jobsearch-agent`, `orders_function` in den persistenten Catalog gehören, ist eine Produktentscheidung aus Discovery-07.
5. **B3 benötigt weiterhin die `agent_id`-Routing-Entscheidung** (Contract verbietet Raten). Dieses Gate löst sie **nicht**.
6. `user-profile` enthält 1 Zeile (Rest eines deaktivierten Testusers aus früheren Gates) — außerhalb dieses Gates, nicht angefasst.

## 23. Status

**GREEN** — alle 16 Erfolgskriterien erfüllt (Commit `40f56a4`, Push als Fast-Forward auf `origin/main` verifiziert). Kein neues Sicherheitsproblem, keine Regression, keine unerlaubte Mutation. **B3 bleibt blockiert.**
