==================================================
CHECKPOINT: 2026-10-06 (P22-USER-AGENT-CAPABILITY-AND-PRODUCT-ADMIN-01) — GREEN mit dokumentierter Lücke (Branch: main, HEAD: 29baea7)
==================================================

- Current status: GREEN für den User-Flow und den Capability-Contract. Der Product-Admin-**Mutationsteil** ist bewusst NICHT implementiert (Option C, Auftrag Punkt 4): die nötige Produktsemantik ist nicht entschieden, und die Umsetzung bräuchte eine IAM-Erweiterung.
- Audit date/time: 2026-10-06
- Current Git branch and HEAD: main, 29baea7 (P21 abgeschlossen und gepusht; dieser Stand committet als Nachfolger)
- Audit scope: RIS-P22-USER-AGENT-CAPABILITY-AND-PRODUCT-ADMIN-01 — erster echter Produktfluss (Cognito Login -> User-/Tenant-Kontext -> positive Agent-Capability) plus Untersuchung des Product-Admin-Zugriffs auf Agent-/Produkt-Zuordnung.
- Live-Kontext (§14): AWS Account 240571105849, AWS Profile mayaws, Region eu-central-1, Terraform Workspace mays-ris, Git branch main, HEAD 29baea7. API-ID aboqolpm0f, Stage $default, Lambda mays-ris-dev-agent (Hash nach Apply 3sfzBvLWGVy7bwgwuydfDztAdzAAD1pcjTtkLFdolK0=).

- Festgehaltene Entscheidungen:
  - "Cognito remains the Managed Authentication Boundary. APIProfile/Credential/Entitlement provide additional product/API authorization inside that authenticated context."
  - "Frontend visibility is not a security boundary. Backend authorization remains authoritative."

- Completed audit sections:
  - Discovery A-E read-only, vor jeder Änderung
  - Frontend-Bestand geprüft (Auftrag Punkt 9)
  - Product-Admin-Entscheidung A/B/C aus dem Ist-Befund getroffen
  - Capability-Contract: Defekt gefunden und behoben (Doppelung)
  - 30 neue Tests, davon 4 mit Gegenprobe
  - Regression inkl. P21 Machine Boundary
  - Tenant-Isolation und Authorization Matrix live
  - Scope-Kontrolle, Security Logging, Commit, Push

- Actual findings (nur verifizierte Fakten):

  A. IDENTITY:
  - Pool eu-central-1_dgQXgwUbv (mays-ris-dev-users), LastModifiedDate 2026-10-02, unverändert durch dieses Gate.
  - 7 Gruppen; belegt sind `admins` (5 User) und `Staff` (2 User). `candidates` und `recruiters` sind leer.
  - Schema enthält `custom:tenant_id`. Nur das ID-Token trägt Custom-Claims; das Access-Token führt `custom:tenant_id` nicht (im P21-E2E bereits beobachtet).
  - `_extract_user_context` (handler.py:286-315) liest `sub`, `email`, `preferred_username`, `custom:tenant_id` und normalisiert `cognito:groups` über `_normalize_groups` (fail-closed, keine permissiven Defaults).

  B. AGENT CATALOG:
  - Tabelle `agent-catalog`, PK agentId (HASH), kein Range-Key. Genau 1 Zeile: `reference_agent`, status ACTIVE, capabilities ["reference.echo"], version 1.0.0, risk_level low.
  - Terraform ist Source of Truth: `local.agent_catalog_seed` + `aws_dynamodb_table_item.agent_catalog_seed` (modules/dynamodb/main.tf:338-354). Ein Guard-Test (test_agent_catalog_terraform_seed.py) prüft, dass kein Runtime-Write-Pfad den Catalog anfasst.
  - `_handle_agents` liest über `_get_agent_catalog()` — die einzige bestehende Catalog-Quelle. Keine parallele Architektur angelegt.

  C. ENTITLEMENTS / OPEN-1:
  - OPEN-1 aus P21 wurde NICHT angefasst: `verify_api_credential` ruft `check_worker_entitlement` weiterhin ohne `api_profile_id`.
  - Für den Capability-Flow ist das NICHT blockierend: `_handle_agents` nutzt `_get_entitlements`, das profilgebundene Zeilen mitliefert. Der Execution-Pfad bleibt davon unberührt. Abhängigkeit dokumentiert, nicht repariert.

  D. APIPROFILE:
  - Bestand live: 18 Profile, überwiegend REVOKED aus Testgates. Keine neue Semantik eingeführt.

  E. EXISTING PLATFORM API — zentrale Entscheidung:
  - `GET /agents` IST bereits der positive Capability-Contract: JWT-geschützt, filtert Entitlements des JWT-`sub` (tenant-scoped über `_get_entitlements`), dann Schnitt mit dem Catalog, fail-closed auf `is_executable_status`, dann Zeitfenster.
  - Antwort enthält nur Catalog-Item-Felder. Live-Leak-Check: digest 0, secret 0, credentialId 0, entitlementId 0, ownerUserId 0, arn:aws 0, iam 0, tenantId 0. Kein Permission Oracle: die Antwort nennt keine Ablehnungsgründe.
  - ENTSCHEIDUNG: wiederverwendet. Kein zweiter `/capabilities`-Endpoint gebaut (Auftrag Punkt E ausdrücklich).

  BEFUND — DEFekt im bestehenden Contract (behoben):
  - Live-Beobachtung: `GET /agents` lieferte `reference_agent` ZWEIMAL.
  - Ursache: `_handle_agents` hängt pro Entitlement an, ohne Deduplizierung (alt: Liste + append). Der Testkontext hatte zwei Entitlements auf denselben Agenten (p21-e2e-ent profilgebunden, p21-e2e-ent2 user-weit aus dem P21-E2E).
  - Produktauswirkung: die Website hätte den Agenten mehrfach gerendert.
  - Fix: Schlüsselung nach agentId (`setdefault`), minimal und ohne Verhaltensänderung für echte Fälle. Live nach Apply: 1 Eintrag.

  §4 PRODUCT ADMIN — Entscheidung C (nicht implementieren, dokumentieren):
  - Bestehende Domainfunktion: `grant_offer` (agents/ecosystem/offers.py:480) mit Admin-Check, Cross-Tenant-Regel, Grund-Pflicht, Scope USER/APIPROFILE, Fensterprüfung, Idempotenz und Audit. 44 Tests vorhanden.
  - Blockierend 1: `grant_offer` verlangt ein Offer (Parameter `offer_id`, Fehler bei fehlendem/inaktivem Offer). Die Offers-Tabelle hat 0 Zeilen und es existiert KEINE Route, um Offers anzulegen.
  - Blockierend 2: Die Entitlements-Tabelle ist für den Lambda nur lesbar — IAM erlaubt `dynamodb:GetItem, Query, BatchGetItem` (modules/lambda/main.tf:66-71), KEIN PutItem.
  - Eine direkte Entitlement-Vergabe ohne Offer wäre eine NEUE Produktsemantik („ist eine Zuordnung offer-scoped oder direkt?"), die nirgends entschieden ist. Erfinden ist nach Auftrag Punkt 4 Option C untersagt.
  - Ergebnis: keine Mutation implementiert. Der unterstützte Product-Admin-Use-Case ist damit der Read-Pfad (siehe Matrix) plus die bereits bestehenden APIProfile-/Credential-Verwaltungsrouten, die `admins` bereits schützen.

  §9 FRONTEND:
  - Es existiert KEIN Frontend für die RIS-Plattform. Im Repository liegen zwei fremde Installer-Produkte: `mays_jobsearch` (mays-job-matcher, React/Vite, ohne Cognito-/Amplify-Abhängigkeit, nutzt die RIS-Agent-API nicht) und `mays_orders` (Backend-only mit eigenem Terraform).
  - Damit gab es keinen vorhandenen Login-Flow zu integrieren. Es wurde kein Frontend neu gebaut — das waere neue Arbeit außerhalb des Gate-Scope.

  LIVE E2E (vorhandener Testkontext, keine neue Produktmutation):
  - User A (Tenant p21-e2e-tenant, mit Entitlement): `GET /agents` -> ["reference_agent"], genau 1 Eintrag.
  - User A unauthentifiziert: 401 (Gateway).
  - User B (Tenant p22-tenant-b, ohne Entitlement, eigener Cognito-User): `GET /agents` -> [] — sieht A nicht.
  - User B `/me` liefert ausschließlich die eigene Identität.
  - Gegenprobe Header-Manipulation: User B mit `X-Api-Profile: aprof_9199d98c75be4a0c` (A-Profil) -> weiterhin [] — kein Leak.
  - Regression live: /me 200, /me/profile 404 (bestehender Vertrag: kein Auto-Provisioning durch Reads), /platform 200, /agents 200, /v1/introspection 200, /v1/apiprofiles 200, /health 200 ohne Auth.
  - P21 unveraendert: Machine-Route ohne JWT 401 (Gateway), mit JWT ohne Credential 401 `{"error": "Unauthorized"}` (Lambda).

  TESTS (§11):
  - Neu: tests/test_p22_agent_capability_contract.py, 30 Tests in 8 Klassen (positiver Contract, Deduplizierung, Identitaet nur aus JWT, Tenant-Isolation, Frontend-ist-keine-Grenze, Authorization Matrix, Catalog-Single-Source, Route-Grenze).
  - Gegenprobe zur Wirksamkeit: mit entfernter Deduplizierung fallen 3 der 4 Deduplizierungs-Tests um (verifiziert, danach Fix wiederhergestellt).
  - Suite (kanonisch, `tests/` ohne den installationsfremden `unit`-Teil): 875 passed, 8 failed, 8 skipped, 1 error.
  - Die 8 failures + 1 error sind EXAKT die bekannte Baseline (test_agent_invocation x2, test_platform_handlers x5, test_reference_agent x1, test_processing_chain error). Kein Baseline-Fehler wurde behoben; das wird nicht behauptet.
  - Ein zusaetzlicher Fehler `tests/unit/agents/test_source_connectivity.py::test_no_aws_imports` erscheint nur bei Ausfuehrung der VOLLEN Suite inkl. `tests/unit`. Ursache: Test-Pollution — tests/test_lambda_packaging.py und test_observability_foundation.py importieren boto3, danach sieht der Test 94 AWS-Module in sys.modules. Mit gestashten P22-Aenderungen tritt er identisch auf. Vorbestehend, in diesem Gate NICHT behoben (gehoert nicht zum Produktcode, sondern zur Test-Infrastruktur).

- Evidence / file references:
  - lambda/handler.py:714-760 (_handle_agents mit Deduplizierung), :286-315 (_extract_user_context), :2060-2093 (_get_entitlements tenant-scoped), :2095-2119 (_is_entitlement_valid)
  - agents/ecosystem/offers.py:480-516 (grant_offer, Offer-Pflicht), :633-648 (withdraw_entitlement), :99-113 (_require_admin/_audit)
  - terraform/modules/lambda/main.tf:64-72 (entitlements nur lesbar), :236-241 (offers mit PutItem)
  - terraform/modules/dynamodb/main.tf:338-354 (agent_catalog_seed, Terraform-SoT)
  - docs/reports/RIS-P22-USER-AGENT-CAPABILITY-AND-PRODUCT-ADMIN-01-EXECUTION_LOG.md
  - Live: /agents -> 1 Eintrag; /agents mit X-Api-Profile-Fremdprofil -> leer; CloudWatch 143 Zeilen, 0 Secret-Treffer

- Classification: GREEN (User-Flow und Capability-Contract) mit YELLOW (Product-Admin-Mutation nicht möglich, OPEN)
- Terraform checks actually executed and their results:
  - `terraform fmt -check modules/api/main.tf` -> sauber (keine .tf-Datei in diesem Gate geaendert)
  - `terraform validate` -> Success! (vorbestehende Deprecated-Warnungen, unveraendert)
  - `terraform plan` vor Apply -> `Plan: 0 to add, 1 to change, 0 to destroy`, ausschliesslich `module.lambda.aws_lambda_function.agent` (source_code_hash)
  - `terraform apply` -> `Apply complete! Resources: 0 added, 1 changed, 0 destroyed`
  - `terraform plan` nach Apply -> `No changes. Your infrastructure matches the configuration.`
  - IAM: 1 inline Policy, unveraendert. Cognito Pool LastModifiedDate unveraendert 2026-10-02. Gateway: 28 Routen, 1 Authorizer, unveraendert. Agent-Catalog: 1 Zeile, unveraendert.
- Git status: 2 modified tracked + 1 neue Testdatei + 1 neuer Report, committet und gepusht. Working Tree bei tracked Files sauber. Fremde untracked Reports und terraform/.terraform.lock.hcl unberuehrt.
- Files changed, if any:
  - `lambda/handler.py` — Deduplizierung in `_handle_agents` (der einzige Produktcode-Change)
  - `tests/test_p22_agent_capability_contract.py` — neu, 30 Tests
  - `docs/reports/RIS-P22-USER-AGENT-CAPABILITY-AND-PRODUCT-ADMIN-01-EXECUTION_LOG.md` — neu
  - Nicht committed: `terraform/lambda.zip` (gitignored), lokale Credential-Dateien in /tmp/opencode (0600)
- Explicit confirmation when no files were changed: Entfaellt — lambda/handler.py wurde geaendert. Hervorzuheben: keine Terraform-Ressource, keine IAM-Policy, keine Cognito-Ressource, keine Route, keine Tabelle und keine neue Produktlogik wurden angefasst. Der Capability-Contract wurde wiederverwendet statt ersetzt.
- Open questions:
  - OPEN-A (Product-Admin-Mutation): Ist eine Capability-Zuordnung offer-scoped (ueber `grant_offer`) oder direkt (eigene Funktion)? Das entscheidet, ob Offers zuerst eingefuehrt werden muessen. Zudem fehlt eine Route fuer Offer-Anlage.
  - OPEN-B (IAM): Soll der Lambda auf `entitlements` ueberhaupt schreiben duerfen? Aktuell bewusst read-only (B5-Entscheidung). Jede produktive Zuordnungsmutation erfordert eine bewusste IAM-Entscheidung, keine technische Notwendigkeit.
  - OPEN-C (Frontend): Es gibt keine RIS-Web-Oberflaeche. Ob eine gebaut wird, ist eine Produktentscheidung ausserhalb dieses Gates.
  - OPEN-D (P21 OPEN-1): profilgebundene Entitlements werden im Execution-Pfad abgewiesen. Hier nicht relevant, bleibt aber bestehen.
  - OPEN-E (Test-Pollution): `test_no_aws_imports` schlaegt in der vollen Suite fehl. Vorbestehend, hier nicht behoben.
  - Testdaten im Pool: p21-boundary-admin (aus P21) und p22-user-b (neu, Tenant p22-tenant-b) wurden fuer die Isolation angelegt. Sie besitzen keine produktiven Entitlements ausser den P21-E2E-Zeilen.
- Risks:
  - Der Fix aendert die Antwortform von `/agents` von potentiell doppelten auf eindeutige Eintraege. Das ist eine Verhaltensaenderung, aber genau die Korrektur des Defekts; ein Client, der Duplikate erwartete, waere ohnehin von einem Fehler ausgegangen.
  - Weil die Admin-Mutation fehlt, ist der komplette Produktfluss (Admin vergibt -> User sieht Agent) live NICHT als Ganzes beweisbar. Der User-seitige Flow ist mit bestehendem Kontext bewiesen; die Vergabeseite ist als OPEN dokumentiert und nicht per DDB-Workaround umgangen (Auftrag Punkt 12/8 ausdruecklich).
  - `admins` bleibt strikt eine Produktrolle. Es wurde nichts unternommen, um AWS-Rechte daraus abzuleiten.
- Recommended next actions:
  1. HARD STOP. Kein Privacy/Retention, kein OPEN-1-Fix, kein Billing, keine weitere Agent-Runtime, kein Health-Ausbau.
  2. OPEN-A als Produktentscheidung behandeln, bevor irgendeine Mutation gebaut wird.
  3. Falls ein RIS-Frontend gewuenscht ist: eigenes Gate, mit bestehender Cognito-Integration und ohne API-Keys im Browser.
- Current resume point: abgeschlossen — Commit und Push erfolgt, HARD STOP

==================================================