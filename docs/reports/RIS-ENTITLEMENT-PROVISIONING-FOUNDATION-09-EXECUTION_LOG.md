==================================================
CHECKPOINT: 2026-10-05 20:15 UTC — ENTITLEMENT PROVISIONING FOUNDATION (GREEN) (Branch: main, HEAD: 01853ff)
==================================================

- Current status: GREEN. Foundation-Entitlement ist Terraform-managed (opt-in), Runtime bleibt read-only, IAM = NO CHANGE; B3 Schritt 13 liefert live ALLOW und reference_agent laeuft live bis COMPLETED; 7 negative Faelle live korrekt; Cleanup vollstaendig ueber den IaC-Lifecycle; 40 neue Tests gruen, keine Regression.
- Audit date/time: 2026-10-05 20:15 UTC
- Current Git branch and HEAD: main, 01853ff (Gate-Start)
- Audit scope: RIS-ENTITLEMENT-PROVISIONING-FOUNDATION-09 — kontrollierter, reproduzierbarer Provisionierungsweg fuer Entitlements; danach B3 positive Live-E2E
- Completed audit sections:
  - AI_AUDITLOG-Pflicht-Template; Log VOR der Implementierung angelegt, nach jedem Meilenstein fortgeschrieben
  - §3 Entitlement-Schema aus Terraform, Live-DynamoDB, Produktivcode abgeleitet
  - §4 Suche nach vorhandener, aber unerreichbarer Grant-Funktion (mit Korrektur meiner eigenen B3-08-Aussage)
  - §5 Strategieentscheidung A/B/C
  - §7/§8 Terraform-Seed mit Foundation-Variable + Idempotenz-Nachweis
  - §6/§9/§13 Runtime-IAM read-only + Security-Pruefung
  - §15 fmt/validate/plan/apply mit Vor-Checks
  - §10 B3 positive Live-E2E bis COMPLETED
  - §11 negative Gegenproben (live, teils ueber Terraform-Variation)
  - §12 Cleanup ueber IaC-Lifecycle
  - §14 Tests + Baseline-Diff
- Actual findings (nur verifizierte Fakten):

  KORREKTUR MEINER EIGENEN VORHERIGEN ANALYSE (Gate B3-08):
  - Ich hatte in B3-08 behauptet, es gebe "keine Modul-Funktion" und "keinen Erzeugungspfad" fuer Entitlements. Das war FALSCH. Ursache: zu grober Grep (ich suchte put_item|update_item|insert|create|grant zusammen mit dem Wort entitlements in derselben Zeile).
  - Tatsaechlich existiert in agents/ecosystem/offers.py ein vollstaendiger Schreibpfad: class DynamoDBEntitlementStore (offers.py:239) mit put_entitlements_batch (286, transaktional via transact_write_items mit ConditionExpression attribute_not_exists(entitlementId)), find_by_user, find_by_key, get_entitlement (317), delete_entitlement (324); class InMemoryEntitlementStore (207); def grant_offer(...) (480) mit admin-only Grant, Scope USER XOR APIPROFILE, vollstaendiger Vorabvalidierung, Idempotency-Key-Wiederverwendung und Konflikterkennung; def withdraw_entitlement (633).
  - Der korrekte Befund lautet: der Schreibpfad EXISTIERT im Code, hat aber NULL produktive Aufrufer (grep grant_offer|withdraw_entitlement ausserhalb von offers.py: 0 Treffer; beide nur in der __all__).

  BESTEHENDES ENTTITLEMENT-SCHEMA (verifiziert):
  - Terraform terraform/modules/dynamodb/main.tf:117-155: hash_key entitlementId (S), TTL auf expiresAt, GSI gsi-user (userId) und GSI gsi-agent (agentId), beide ProjectionType ALL.
  - Live bestaetigt (describe-table / describe-time-to-live): KeySchema [{entitlementId, HASH}]; AttributeDefinitions entitlementId=S, userId=S, agentId=S; beide GSI vorhanden; ItemCount 0; TTL ENABLED auf expiresAt.
  - AUTORITATIVE ZEILENFORM aus dem Produkt-Grant-Pfad (grant_offer, offers.py:588-611): entitlementId, userId, tenantId, agentId, validFrom, validUntil, expiresAt, offerId, grantId, createdAt, createdBy, optional apiProfileId, optional idempotencyKey.
  - STATUSMODELL: es gibt KEIN status-Attribut. grant_offer schreibt keins, der Read Path liest keins. Die Gate-Vorgabe "status = bestehendes gueltiges Statusmodell" loest sich damit auf: das bestehende Modell hat kein Status-Feld. Ich erfinde keins. Gueltigkeit ist ausschliesslich zeitlich (is_entitlement_valid, worker_authorization.py:40-78, liest nur validFrom/validUntil; unparsbar wird mit Warnung ignoriert).

  BESTEHENDER READ PATH (unveraendert):
  - check_worker_entitlement (worker_authorization.py:91, Signatur inkl. work_id) + is_entitlement_valid + _row_matches; DynamoDBEntitlementResolver.find_entitlements (154-186) queryt gsi-user per userId; Handler _get_entitlements/_get_entitlement_for_agent/_is_entitlement_valid; Introspection _build_capabilities (introspection.py:91).

  §5 GEWAEHLTE STRATEGIE: Option B (Terraform-managed Foundation Fixture)
  - OPTION A (vorhandener offizieller Managementpfad = grant_offer) ist NICHT VERWENDBAR, dreifach belegt: (1) 0 produktive Aufrufer, keine Route, kein Handler; (2) grant_offer verlangt ein ACTIVE offer mit agentIds — die offers-Tabelle hat live 0 Zeilen und es gibt auch fuer Offers keinen Provisionierungsweg (dieselbe Luecke eine Ebene hoeher); (3) grant_offer schreibt transaktional via transact_write_items, waehrend die Lambda-Rolle auf entitlements nur GetItem/Query/BatchGetItem hat (live verifiziert) — der Runtime-Pfad koennte es also nicht ausfuehren, ohne genau die Schreibrechte zu erweitern, die §6 verbietet. Option A zu nutzen hiesse Offer-System plus Admin-Route plus Runtime-Schreibrechte, also die untersagte Option C.
  - OPTION C (neue Management-API) ist nicht erforderlich und wurde NICHT gebaut.
  - Gewaehlt: Option B, analog zum vom Auftraggeber bestaetigten B4-Muster.Provisioning Plane schreibt (Terraform), Runtime Plane liest (Lambda) — genau die geforderte Trennung.

  §7 SYNTHETISCHE FOUNDATION-ENTITLEMENT (live)
  - entitlementId = ent_b5_reference_agent (for_each-Key, keine erfundene ID-Logik)
  - userId  = e3c4d8c2-8041-7046-6ad4-2fb6b76c4a52 (synthetischer Cognito-sub des Test-Owners)
  - tenantId = b5-1791220725 (synthetischer Test-Tenant)
  - agentId = reference_agent (der Terraform-managed Catalog-Agent aus B4)
  - validFrom = 2026-01-01T00:00:00+00:00, validUntil = 2099-12-31T23:59:59+00:00
  - createdBy = {actor: terraform, role: provisioning}
  - BEWUSST NICHT geschrieben: offerId und grantId (kein Offer hinter einer Foundation-Fixture; plausibel aussehende Werte wuerden die Provenance verfaelischen — der Read Path liest sie nicht) sowie expiresAt (siehe unten).
  - WARUM userId ein Terraform-Input ist: das Entitlement ist user-gebunden. check_worker_entitlement liest userId aus dem verifizierten Credential-Kontext = ownerUserId des APIProfiles = Cognito-sub des authentifizierten Owners. Ein Profil kann nur fuer den authentifizierten sub angelegt werden, und Cognito-subs werden von AWS vergeben und sind im Repo nicht Terraform-verwaltbar (keine aws_cognito user-Ressource). Der Wert ist daher ein expliziter Input ueber eine Variable mit Default {}.
  - WARUM expiresAt NICHT geschrieben ist: Terraform kann keine Epoch-Sekunden aus einem ISO-String berechnen (timestamp() liefert kein Epoch; mein erster Versuch erzeugte einen validate-Fehler "Too many function arguments"), und eine handgebaute Umrechnung waere erfundene Arithmetik. Zusaetzlich wuerde ein befuelltes expiresAt die Fixture still loeschen (TTL ENABLED), waehrend ihre Entfernung ein expliziter IaC-Akt ist. Gleiche Begruendung wie beim B4-Catalog-Seed.

  §8 IDEMPOTENZ
  - Lauf 1 (apply): 1 added -> entitlements Rows 1.
  - Lauf 2 (plan mit identischer Variable): show -json -> 0 Ressourcen mit Aenderung. Rows weiterhin 1.
  - Lauf 3: ebenfalls 0 Aenderungen.
  - Begruendung: aws_dynamodb_table_item mit for_each-Key = entitlementId (Hash-Key) ersetzt die Zeile in place; es entsteht kein Duplikatbestand. Es gibt keine uuid()/timestamp()-Generierung im Block (per Test abgesichert).

  §6/§13 IAM: NO CHANGE
  - Welche AWS-Operation braucht der gewaehlte Weg? Der Provisionierungsweg ist Terraform, der mit eigener Execution-Identity schreibt. Es ist KEINE Lambda-Permission noetig.
  - Live verifiziert nach allen Variationen: mays-ris-dev-lambda-dynamodb-platform traegt auf mays-ris-dev-entitlements (+ /index/*) ausschliesslich dynamodb:GetItem, dynamodb:Query, dynamodb:BatchGetItem. Kein PutItem, kein DeleteItem, kein UpdateItem, kein TransactWriteItems, kein Scan.
  - Role Policies 8, unveraendert. Der Terraform-Plan enthaelt 0 IAM-Ressourcen. Ein Test verhindert kuenftig IAM-Zeilen in der Terraform-Diff.

  §15 TERRAFORM
  - fmt: modules/dynamodb/main.tf und modules/dynamodb/variables.tf sind formatiert. fmt -check -recursive zeigt unveraendert die 6 Baseline-Dateien (main.tf, variables.tf, modules/cognito, modules/monitoring, modules/orders_reader, modules/sqs) — von mir keine neue Formatabweichung und keine fremde Datei umformatiert.
  - validate: Success (Warnungen Baseline).
  - Vor-Checks vor dem Apply: Account 240571105849, Profile mayaws, Region eu-central-1, Workspace mays-ris, Ziel-ARN arn:aws:dynamodb:eu-central-1:240571105849:table/mays-ris-dev-entitlements, entitlements Rows 0 — alle wie erwartet.
  - plan ohne Variable: "No changes." (Opt-in-Nachweis: produktive Workspaces bekommen nichts).
  - plan mit Variable: genau 1 create — module.dynamodb.aws_dynamodb_table_item.foundation_entitlement["ent_b5_reference_agent"]. show -json: Zerstoerungen [], Ersetzungen [], 0 IAM-Ressourcen, keine verbotenen Typen, keine Output-Aenderungen. Item enthielt genau die 8 deklarierten Felder.
  - apply: 1 added.

  §10 B3 POSITIVE LIVE-E2E — KERNNACHWEIS
  - Machine-Aufruf: HTTP 202 {"status":"QUEUED","workId":"ffa0f6f2-...","requestId":"b8e2d5ba-..."}
  - Schritt 13 der Verification liefert damit ALLOW statt 403. Audit-Beleg: action=verification outcome=authorized apiProfileId=aprof_5580b1ba30f846e6 credentialId=cred_60fa5b60bd174042 tenant=b5-1791220725 route=POST /v1/m2m/agents/{agentId}/execute (ohne Secret, ohne Header).
  - Ausfuehrung bis COMPLETED: Work-Item in mays-ris-dev-work-items zeigt status=COMPLETED, agentId=reference_agent, type=agent_reference_agent. Worker-Log: "Processing work item: ffa0f6f2-..., type: agent_reference_agent" -> "Registered agent: reference_agent" -> "Selected agent reference_agent [candidates: 1, reason: Specific agent requested]" -> "Executing agent reference_agent [capability: reference.echo]" -> "Work item ffa0f6f2-... processed: COMPLETED".
  - Damit ist die vollstaendige Kette live: Machine Client -> Gateway -> Lambda -> verify_api_credential -> APIProfile (ACTIVE) -> Entitlement (ALLOW) -> Agent Catalog (ACTIVE) -> bestehender Execution Path (work_item + SQS) -> ReferenceAgent -> COMPLETED.

  §11 NEGATIVE GEGENPROBEN (live)
  | Fall | Ergebnis | erwartet |
  |---|---|---|
  | gueltiges Credential + gueltige Entitlement (Positiv-Kontrolle) | 202 QUEUED | 202 |
  | falscher Agent (jobsearch-agent) | 403 Forbidden | 403 |
  | revoked Credential | 403 Forbidden | 403 |
  | deaktiviertes Profil (DISABLED) | 403 Forbidden | 403 |
  | fremder Tenant (zweiter Owner in Tenant b5x-..., eigenes ACTIVE-Profil, eigenes gueltiges Credential) | 403 Forbidden | 403 |
  | unbekanntes Credential | 401 Unauthorized | 401 |
  | Human-JWT auf dem Machine-Pfad | 401 Unauthorized | 401 |
  | Entitlement ABGELAUFEN (validUntil in der Vergangenheit, per Terraform gesetzt) | 403 Forbidden | 403 |
  | Entitlement FEHLT (leere Variable -> Terraform entfernt die Zeile) | 403 Forbidden | 403 |
  - Die letzten beiden wurden ueber den IaC-Lifecycle variiert und nach dem Test ueber Terraform wiederhergestellt (202). Das belegt gleichzeitig, dass Provisionierung und Entfernung in beide Richtungen ueber Terraform laufen.
  - Keine neuen Fehlercodes: 401/403 exakt nach bestehender Contract-Semantik.

  §12 CLEANUP (ueber den zulaessigen Mechanismus, kein manueller DDB-Delete)
  - Credentials: 2 Credentials ueber die Produktpfade REVOKE, 2 Testprofile ueber den Admin-Pfad REVOKED (HTTP 200).
  - Entitlement: Config auf leer -> plan -> "module.dynamodb.aws_dynamodb_table_item.foundation_entitlement["ent_b5_reference_agent"]: Destroying" -> apply "Resources: 0 added, 0 changed, 1 destroyed" -> entitlements Rows 0.
  - Testuser: b5-owner, b5-admin, b5x-owner geloescht; Pool wieder bei 14 Usern; admins-Gruppe wieder bei den 4 vorbestehenden Mitgliedern.
  - tmp-Verzeichnis mit Passwoertern, Tokens und Secrets entfernt (bestaetigt).
  - Endstand: entitlements 0 (vor dem Gate 0), agent-catalog 1 (unveraendert), credentials 17 = 14 Baseline + 3 dieses Gates, ALLE 17 REVOKED, 0 ACTIVE; api-profiles 14 = 11 + 3, alle REVOKED.
  - work-items bleiben als Audit-Beleg bestehen; die Tabelle hat TTL ENABLED auf expiresAt (live verifiziert) und der Execution Contract setzt expiresAt = createdAt + 30 Tage — sie verschwinden also von selbst.
  - EIGENE CLEANUP-LUECKE, gefangen und geschlossen: mein Cleanup-Skript benutzte fuer das FREMDE Profil den Owner-Token des b5-Owners, dadurch wurde dessen Credential nicht revokiert und blieb ACTIVE. Das fiel nur auf, weil ich den ACTIVE-Count aktiv gezaehlt habe statt "Cleanup erledigt" anzunehmen. Geschlossen ueber den Produktpfad: temporaerer Admin im Tenant des fremden Profils angelegt, Credential per Management-API revoken (HTTP 200, revokedBy/revokedAt gesetzt), Admin wieder geloescht. Kontrolle danach: 17/17 REVOKED.

  §9 SECURITY
  - Geplante Row auf Secrets/PII geprueft: secret, token, password, credential, bearer, email, @, cv, resume — jeweils nicht enthalten.
  - createdBy = {actor: terraform, role: provisioning}: die Fixture gibt NICHT vor, ein Human-Admin-Grant zu sein (grant_offer schreibt role "admin").
  - Keine Wildcards und keine "Resource"-Policy in der Terraform-Diff (per Test gesichert).
  - Runtime-IAM read-only (per Test gegen das Statement gesichert).
  - Audit-/Execution-Logs enthalten keine Credentials, keine Authorization-Header und keine Secrets: Secrets wurden ausschliesslich in Dateien mit chmod 600 in einem chmod-700-Verzeichnis gehalten, nur als Fingerabdruck/Laenge protokolliert und am Ende vernichtet. Secret-Scan ueber den Report laeuft sauber.
  - Keine Cross-Tenant-Berechtigung: die Foundation-Entitlement gilt genau fuer userId+tenantId des synthetischen Owners; der fremde Tenant wurde live mit 403 abgelehnt.

  §14 TESTS
  - NEU tests/test_entitlement_provisioning.py: 39 Tests, alle gruen.
    Schema/IaC (11): bestehende Tabelle, kein range_key, nur Contract-Attribute, alle vom Read Path benoetigten Felder, kein status, kein expiresAt, kein offerId/grantId, opt-in per Default {}, Root-Durchreichung, entitlements-Tabelle unveraendert (3 Attribute, beide GSI, TTL).
    Runtime read-only (3): keine Schreibaktionen im entitlements-IAM-Statement, Query auf gsi-user bleibt, keine IAM-Zeile in der Diff.
    Unit (8): gueltige/fehlende/verschwundene/abgelaufene/noch-nicht-aktive Entitlement, Agent-Bindung, falscher Agent, fremder Tenant, nur-Zeitfenster-Kriterium.
    B3-Integration (7): positive Machine Execution AUTHORIZED, fehlende/abgelaufene/falscher-Agent/nicht-ausfuehrbarer Agent -> FORBIDDEN, Gesamtkette (jedes fehlende Glied kippt die Entscheidung), Denial ohne Kontext, Profilstatus bindet weiter.
    Provisioning (5): for_each-Key als PK, keine generierte ID, deterministische Zeile, Werte aus Variable statt hartkodiert, B4-Catalog-Seed unberuehrt.
    Security (3): keine Secrets/PII, actor=provisioning statt admin, keine Wildcards.
  - ANPASSUNG EINES BESTEHENDEN TESTS (vom Baseline-Diff aufgedeckt): tests/test_agent_catalog_terraform_seed.py::test_only_one_resource_type_added behauptete "insgesamt genau 1 aws_dynamodb_table_item in modules/dynamodb/main.tf". Das war fuer den B4-Catalog-Seed allein korrekt; B5 fuegt legitim eine zweite, unverbundene Item-Ressource hinzu, wodurch der Test an einer richtigen Aenderung scheiterte. Ersetzt durch test_exactly_the_expected_item_resources_exist (prueft die exakte Namensmenge {agent_catalog_seed, foundation_entitlement} und dass der Catalog-Seed genau einmal vorkommt) plus test_catalog_seed_untouched_by_b5. Der Schutzzweck bleibt erhalten und ist sogar schaerfer; kein Test wurde abgeschwaecht oder geloescht.
  - Gesamtsuite MIT Aenderung: 8 failed, 865 passed, 8 skipped, 1 error.
  - BASELINE (01853ff, per git stash inkl. terraform/ und der neuen Testdatei): 8 failed, 825 passed, 8 skipped, 1 error.
  - diff der Fehlerlisten nach der Testanpassung: IDENTISCH -> keine Regression. Delta +40 Tests.
  - Build/Lint/Type: kein Python-Build im Projekt; CI (.github/workflows/ci-cd.yml) macht ausschliesslich Terraform. flake8/mypy/ruff nicht installiert und nicht konfiguriert (nicht erfunden). py_compile OK; AST-Import-Check ohne ungenutzte Imports.

  EIGENE FEHLER (transparent)
  - validate-Fehler "Too many function arguments": ich hatte expiresAt = tostring(timestamp(each.value.validUntil)) verwendet; timestamp() liefert kein Epoch. Loesung: expiresAt weglassen und begruenden.
  - terraform fmt auf terraform/main.tf und terraform/variables.tf hat bestehende, nicht von mir angefasste Bloecke kosmetisch umformatiert (module "lambda", module "monitoring"). Das verletzt die im B4-Gate eingehaltene Discipline. Beide Dateien per git checkout zurueckgesetzt und nur meine Zeile neu eingefuegt; Diff enthaelt jetzt 0 fremde Auszeichnungszeilen.
  - Testfehler: check_worker_entitlement verlangt work_id als positionales Argument — in meinen Tests vergessen.
  - Testfehler: test_opt_in_by_default suchte den Block in TF_ROOT statt in den beiden Variable-Dateien und nutzte eine zu kleine Blockgrenze.
  - Test-Erwartung falsch: fehlt nur das APIProfile, ist das Credential weiterhin BEKANNT und der Contract klassifiziert das als FORBIDDEN (403), nicht UNAUTHORIZED (401). Erwartung an den bestehenden Contract angepasst, statt den Contract zu aendern.
  - E2E-Skript: Cognito-CLI-Input per json:// schlug fehl ("Invalid JSON received") -> auf Dateien mit chmod 600 umgestellt.
  - E2E-Skript: fremdes Profil zuerst PENDING, Credential-Ausstellung ergab 409 — korrektes Verhalten (Ausstellung verlangt ACTIVE); Profil danach cross-tenant mit reason aktiviert.
  - Cleanup-Luecke: falscher Owner-Token fuer das fremde Profil (siehe §12).
  - Baseline-Diff fand eine Regression in einem bestehenden Test (siehe §14), die durch den Test selbst aufgedeckt wurde.

- Evidence / file references: terraform/modules/dynamodb/main.tf:117-155 (entitlements-Tabelle), neu angehaengt (variable foundation_entitlements in variables.tf, resource aws_dynamodb_table_item.foundation_entitlement); terraform/main.tf (Durchreichung in module "dynamodb"); terraform/variables.tf (Variable mit Default {}); terraform/modules/lambda/main.tf (entitlements-IAM read-only); agents/ecosystem/offers.py:239-330 (DynamoDBEntitlementStore), :333-350 (_validate_agents), :480-631 (grant_offer inkl. Zeilenform :588-611), :633 (withdraw_entitlement); agents/ecosystem/worker_authorization.py:40-78, :76-89, :91, :154-186; agents/ecosystem/introspection.py:91; agents/ecosystem/credentials.py:751 (verify_api_credential), :816-830 (Catalog-Schritt); lambda/handler.py:779 (_machine_execute_agent), :831 (produktiver verify_api_credential-Aufruf), :1533 (_enqueue_agent_work), :1703 (_get_agent_catalog); tests/test_entitlement_provisioning.py; tests/test_agent_catalog_terraform_seed.py (angepasst); CloudWatch /aws/lambda/mays-ris-dev-agent (Audit authorized + Ausfuehrungslog); docs/reports/RIS-B3-MACHINE-CREDENTIAL-ENTRYPOINT-IMPLEMENTATION-08-EXECUTION_LOG.md (Vorgabegate, B5 als Blocker)

- Classification: GREEN

- Terraform checks actually executed and their results:
  - `terraform fmt modules/dynamodb/main.tf modules/dynamodb/variables.tf` — meine Dateien formatiert
  - `terraform fmt -check -recursive` — unveraendert 6 Baseline-Dateien, meine Dateien nicht enthalten
  - `terraform validate` — Success (Warnungen Baseline)
  - `terraform plan` ohne Variable — "No changes." (Opt-in)
  - `terraform plan` mit Variable — 1 create; show -json: 0 Zerstoerungen, 0 Ersetzungen, 0 IAM, keine verbotenen Typen
  - `terraform apply` (Plan-Datei) — 1 added
  - `terraform plan` Lauf 2 und 3 mit identischer Variable — 0 Aenderungen (Idempotenz)
  - `terraform apply` mit abgelaufener validUntil — 0 added, 1 changed
  - `terraform apply` mit leerer Variable — 0 added, 0 changed, 1 destroyed (Cleanup)
  - `terraform apply` Restore — 1 added (202 wieder erreicht)
  - `terraform plan` nach Cleanup ohne Variable — "No changes."
  - KEIN Destroy der Tabelle, KEIN taint, KEIN state rm, KEIN IAM-Manipulation

- Git status: bei Start 0 modified tracked; vor Commit 5 modified tracked (terraform/main.tf, terraform/variables.tf, terraform/modules/dynamodb/main.tf, terraform/modules/dynamodb/variables.tf, tests/test_agent_catalog_terraform_seed.py) + 2 new (tests/test_entitlement_provisioning.py, dieses Log); nach Commit 0 modified tracked

- Files changed, if any:
  - GEÄNDERT: terraform/variables.tf (Variable, Default {}), terraform/main.tf (eine Durchreichungszeile), terraform/modules/dynamodb/variables.tf (Variable + Begründung), terraform/modules/dynamodb/main.tf (eine Item-Ressource)
  - GEÄNDERT: tests/test_agent_catalog_terraform_seed.py (ein Test praezisiert, einer ergaenzt)
  - NEU: tests/test_entitlement_provisioning.py
  - NEU: docs/reports/RIS-ENTITLEMENT-PROVISIONING-FOUNDATION-09-EXECUTION_LOG.md
  - NICHT committed: 8 vorbestehende untracked Reports fremder Gates; terraform/.terraform.lock.hcl; lambda.zip (Build-Artefakt aus B3-08)

- Explicit confirmation when no files were changed: entfaellt — es wurden Dateien geaendert. Hervorzuheben: die Runtime (lambda/, agents/) wurde in diesem Gate NICHT angefasst. Kein einziges Python-Modul wurde geaendert — B5 ist rein IaC plus Tests.

- Open questions:
  - grant_offer bleibt weiterhin ohne produktiven Aufrufer. Das ist eine bewusste, hier NICHT adresste Luecke: sie zu schliessen hiesse Offer-Provisionierung plus Admin-Route plus Runtime-Schreibrecht (TransactWriteItems) — ein eigenes, deutlich groesseres Gate. Die Foundation-Fixture umgeht sie, ohne sie zu verdecken.
  - withdraw_entitlement hat ebenfalls 0 Aufrufer; es gibt also keinen produktiven Rueckbau fuer Entitlements ueber die Produkt-API. Der Cleanup dieses Gates nutzt deshalb korrekt den IaC-Lifecycle.
  - Ob Entitlements langfristig offers-gebunden provisioniert werden sollen (Antwort: ja, aber in einem eigenen Gate) oder dauerhaft per Foundation-Fixture existieren, ist eine Produktentscheidung. Dieses Gate liefert nur EINEN synthetischen, entfernbaren Datensatz und behauptet kein Produktmodell.
  - Die Foundation-Entitlement hat kein expiresAt und damit keinen TTL. Sie bleibt bestehen, bis sie per Terraform entfernt wird. Das ist dieselbe Eigenschaft wie der B4-Catalog-Seed und in beiden Faellen dokumentiert; ein Retention-Konzept bleibt ein eigenes Gate.
  - userId ist ein Terraform-Input. Fuer eine reproduzierbare Provisionierung ueber Workspace-Grenzen hinweg muss der sub-Wert dokumentiert werden (z. B. als Workspace-Input). Hier wurde er aus dem kontrollierten synthetischen Fixture gelesen und beim Apply uebergeben.

- Risks:
  - Keine Secrets, Tokens, Passwoerter oder Authorization-Header im Report oder in Logs. Secrets nur in chmod-600-Dateien im chmod-700-Verzeichnis, am Ende vernichtet.
  - Provisionierung liegt in Terraform mit eigener Identity und State im Lock-geschuetzten S3-Backend; die Runtime hat nachweislich kein Schreibrecht.
  - Die Foundation-Entitlement ist fail-closed wirksam: ohne sie 403 (live dreifach belegt: abgelaufen, fehlend, fremder Tenant).
  - 3 Testprofile und 3 Credentials bleiben als REVOKED terminal zurueck (kein produktiver Delete-Pfad, Gate 04/05) — kein Zugriffsrisiko.
  - 2 work-items aus der Live-E2E bleiben bis zum TTL (30 Tage) als Ausfuehrungsbeleg bestehen.
  - Terraform-Policy-Transitions: keine dynamischen Blocker.

- Recommended next actions:
  - P17 und P20 NICHT starten (ausdruecklich untersagt).
  - B3 ist jetzt vollstaendig live GREEN: positive Ausfuehrung bis COMPLETED ist belegt. Ein erneuter B3-Lauf ist nicht noetig; wer die Kette erneut dokumentieren will, kann die Foundation-Entitlement kurz per Terraform setzen und per Cleanup wieder entfernen.
  - Optional als eigenes, unabhaengiges Gate: produktive Offer-Provisionierung plus Admin-Route, damit grant_offer und withdraw_entitlement einen Aufrufer bekommen. Das ist NICHT Voraussetzung fuer die jetzt funktionierende Machine-Kette.

- Current resume point: Commit + Push, danach HARD STOP

==================================================
