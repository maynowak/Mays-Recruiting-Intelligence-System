==================================================
CHECKPOINT: 2026-10-05 18:45 UTC — B3 MACHINE CREDENTIAL ENTRYPOINT IMPLEMENTATION (BLOCKED / YELLOW) (Branch: main, HEAD: 03f48c7)
==================================================

- Current status: Machine-Entry-Point ist IMPLEMENTIERT, getestet, deployed und live erreichbar; 9 negative Live-Fälle liefern exakt die Contract-Semantik (401/403); Human-Regression GREEN; IAM = NO CHANGE. Der positive Live-Nachweis der vollen Kette ist BLOCKED: fuer die Entitlements der Verification existiert KEIN Provisionierungs-Pfad (keine Route, kein Handler, keine Modul-Funktion, Lambda-Rolle nur lesend). Kein Direct-DDB-Write — Entscheidung des Auftraggebers war Option 3 (eigenes Gate statt Workaround).
- Audit date/time: 2026-10-05 18:45 UTC
- Current Git branch and HEAD: main, 03f48c7 (Gate-Start)
- Audit scope: RIS-B3-MACHINE-CREDENTIAL-ENTRYPOINT-IMPLEMENTATION-08 — Option D aus Discovery-07 produktiv anbinden
- Completed audit sections:
  - AI_AUDITLOG-Pflicht-Template; Log VOR der Implementierung angelegt, nach jedem Meilenstein fortgeschrieben
  - §3 Bestandsanalyse (verify_api_credential, Execution-Pfad, Handler/Gateway, IAM-Bedarf)
  - §2/§6 gemeinsamer Execution-Helper `_enqueue_agent_work`; Human-Pfad darauf umgestellt
  - §5/§6 Machine-Entry-Point: Bearer-Extraktion, agent_id, zentrale Verification, Outcome-Mapping
  - §4 Gateway-Route `POST /v1/m2m/agents/{agentId}/execute` (authorization_type NONE, bestehende Integration)
  - §10 22 neue Tests (positiv/negativ/Plangrenze)
  - §13 fmt/validate/plan, Bundle deterministisch gebaut
  - §14 apply + Live-E2E ueber Produktwege
  - §11 Human-Regression-Smoke
  - §15 Security/Audit
  - Cleanup
- Actual findings (nur verifizierte Fakten):

  Ausgangslage Discovery-07:
  - B3 als "kein M2M-Einstiegspunkt" identifiziert; Option D (Human-JWT fuer Identity/Management + opaque Credential fuer APIProfile-Nutzung) als Empfehlung. Diese Entscheidung wurde in diesem Gate uebernommen und NICHT neu diskutiert.

  IAM — Ergebnis: NO CHANGE (pragmatisch geprueft, §12)
  - Welche Operationen ruft der neue produktive Code tatsaechlich auf? credentials get_by_digest (GetItem) + mark_used (UpdateItem); api-profiles GetItem; entitlements Query auf gsi-user; agent-catalog Scan; work-items PutItem; sqs SendMessage.
  - Alle sechs sind in der vorhandenen Rolle mays-ris-dev-agent bereits abgedeckt (Policies mays-ris-dev-lambda-dynamodb-product bzw. -platform bzw. -work bzw. lambda-sqs-send). Live nach Apply verifiziert: Role Policies 8, unveraendert; das IAM-Statement auf agent-catalog bleibt GetItem/Query/BatchGetItem/Scan.
  - Es wurde KEINE Permission ergaenzt, keine Rolle angelegt, keine Wildcard verwendet. Plan enthaelt 0 IAM-Ressourcen.

  Gewaehlte Route
  - `POST /v1/m2m/agents/{agentId}/execute`, Terraform-Ressource module.api.aws_apigatewayv2_route.m2m_agent_execute, authorization_type NONE, target = BESTEHENDE Integration ewy9u57, api_id aboqolpm0f. RouteId live 3gl13l1.
  - Begruendung: P03 hatte den /v1/m2m/-Prefix bereits vorgeschlagen; die bestehende Gateway-Struktur kennt nur die geteilte AWS_PROXY-Integration, also wurde sie wiederverwendet. Keine $default-Route, keine ANY-/Greedy-Route, nur diese eine Route. Live: 27 -> 28 Routen, die 27 bestehenden unveraendert.
  - agent_id kommt aus dem PFADPARAMETER, nicht aus einem Default und nicht aus einer Capability->Agent-Abbildung. Das Gate nennt als Beispiel einen Body mit agent_id, verlangt aber zugleich "an den bestehenden Execution Contract anpassen, nicht parallel einen zweiten erfinden". Der bestehende Contract ist /api/agents/{agentId}/execute mit Body {capability, payload, idempotencyKey?}; deshalb Pfadparameter + identischer Body. Ein Test haelt fest, dass /v1/m2m/ NICHT beliebige Pfade einsammelt.
  - Warum NONE und nicht JWT: das Credential ist absichtlich kein JWT; der Cognito-JWT-Authorizer lehnt es strukturell ab (in P17-06 als error="invalid_token" / "invalid number of segments" belegt). P03 Route-Grenze: kein "erst JWT, sonst Key" — die human Routen bleiben JWT-only, die Machine-Route ist JWT-frei.

  Authorization Flow (produktiv)
  - Handler-Kette in _machine_execute_agent (lambda/handler.py:779 ff.):
    1 Header extrahieren (lower-cased, Schema "Bearer" + Wert ohne Leerzeichen)
    2 agent_id aus Pfad ermitteln und auf [A-Za-z0-9_.-] bereinigen
    3 Sources ueber den BESTEHENDEN Builder _build_introspection_sources() (profile_store, credential_store, entitlement_resolver, offer_store, catalog) — kein zweiter Builder
    4 verify_api_credential(bearer, agent_id, ...) aufrufen — die zentrale Verification ist die einzige Autorisierungsquelle
    5 Outcome mappen: AUTHORIZED -> weiterleiten; UNAUTHORIZED -> 401; FORBIDDEN -> 403; CredentialStoreUnavailable bzw. nicht konfigurierte Stores -> 503
    6 nur bei AUTHORIZED den gemeinsamen Execution-Helper aufrufen
  - Es gibt KEINE vereinfachte Pruefung wie "if credential_exists: execute()". Das ist strukturell ausgeschlossen: der Handler besitzt keine Logik, die Credential/Profil/Entitlement/Catalog selbst auswertet.
  - Das Ausfuehrungs-Subject kommt aus dem VERIFIZIERTEN Kontext (tenantId/userId des persistierten Credentials), nie aus Header oder Body. Ein Test belegt das explizit mit absichtlich manipuliertem Body.
  - verify_api_credential hat damit ENDGÜLTIG einen produktiven Aufrufer (lambda/handler.py:831). Das P17-Problem "0 productive callers" ist behoben.

  Ein gemeinsamer Execution Contract
  - Vorher bauten _execute_agent (Human) und der Machine-Pfad jeweils ein eigenes work_item. Neu: _enqueue_agent_work (lambda/handler.py:1533) ist der einzige Ort, der work_item baut, in WORK_ITEMS_TABLE schreibt und an WORK_QUEUE_URL sendet. Beide Pfade nutzen ihn.
  - work_item-Felder unverändert: workId, type=agent_{agentId}, tenantId, userId, requestedBy, agentId, capability, idempotencyKey, payloadVersion, agentVersion, requestId, status=QUEUED, attempt, payload, createdAt, expiresAt; Antwort 202 {workId, status, requestId}. Der Downstream-Pfad (SQS -> pipeline.process_record -> Execution-Time-Recheck) ist unveraendert.
  - Belege fuer "genau ein Contract": grep "'type': f'agent_{agent_id}'" liefert 1 Vorkommen (vorher 2).
  - BEMERKENSWERT: /api/agents/* und /work haben im Gateway KEINE Route (grep in terraform/modules/api/main.tf: 0 Treffer; Routenliste 27 ohne /api/agents). Der bestehende Execution-Pfad war also ueber das Gateway unerreichbar — die Machine-Route ist der erste produktive Zugang dazu. Das ist kein Nebeneffekt des Gates, sondern der Grund, warum ein eigener Route-Eintrag nötig war.

  Terraform Plan / Apply
  - `terraform fmt modules/api/main.tf` — keine Formatabweichung
  - `terraform validate` — Success (Warnungen Baseline)
  - `terraform plan` vor Bundle-Rebuild — 1 create (nur die Route); show -json: Zerstoerungen [], Ersetzungen [], keine verbotenen Typen, KEINE IAM-Aenderung, bestehende aws_lambda_permission unveraendert
  - Bundle: `python3 lambda/build_zip.py --bundle agent` -> terraform/lambda.zip, 52 Dateien, sha256 5408f888b3b4ee2f76a18888eb895b29. Zwei Builds lieferten identischen Hash -> deterministisch (bestehender Lifecycle-Vertrag). Bundle enthaelt _machine_execute_agent, verify_api_credential(, _enqueue_agent_work, /v1/m2m/.
  - `terraform plan` nach Rebuild — 2 Aenderungen: route create + module.lambda.aws_lambda_function.agent update (source_code_hash aus filebase64sha256(lambda.zip)). 0 Zerstoerungen, 0 IAM, keine unerwarteten Cognito-/SQS-/DynamoDB-Table-/API-/Stage-Aenderungen. Von 25 Routen-Ressourcen im Plan: 24 no-op -> Human-Routen unveraendert.
  - `terraform apply` — "Resources: 1 added, 1 changed, 0 destroyed."
  - Lambda CodeSha256: ECemCxwAOv0fNo3OeAkxjpT3Eg+Xyl9LZB61h3R4VvQ= -> VAj4iLO07i92oYiI64lbKQB8Erf2/xRR58SuowrGPuU=

  Live E2E (§14) — ausschliesslich Produktwege, kein Direct-DDB-Write
  - APIProfile: POST /v1/apiprofiles (Owner-JWT) -> 201 aprof_7f25211860244f9e status PENDING; POST /status (Admin-JWT) ACTIVE -> 200. Beide Profile dieses Gates (aprof_7f25211860244f9e, aprof_a929e651af5d498d) ueber den Produktweg erzeugt.
  - Credentials: 4 Stueck pro Lauf ueber POST /v1/apiprofiles/{id}/credentials -> je 201, Secret 47 Zeichen. Terminale Zustaende ueber die Produktpfade revoke/disable.
  - Secret-Hygiene: nur SHA-256-Fingerabdruck (12 Hex) protokolliert, nie der Wert; state-Datei chmod 600 im chmod-700-Verzeichnis; am Ende vernichtet.
  - Ergebnis der MACHINE-Route, live:

    | Fall | Ergebnis | erwartet |
    |---|---|---|
    | unbekanntes Credential | 401 Unauthorized | 401 |
    | "Bearer" ohne Wert | 401 Unauthorized | 401 |
    | fehlerhaftes Credential (ris_short) | 401 Unauthorized | 401 |
    | Human-JWT als Credential | 401 Unauthorized | 401 |
    | revoked Credential | 403 Forbidden | 403 |
    | disabled Credential | 403 Forbidden | 403 |
    | abgelaufenes Credential | 403 Forbidden | 403 |
    | unbekannter Agent (gibtsnicht) | 403 Forbidden | 403 |
    | gueltiges Credential, keine Entitlement | 403 Forbidden | 403 |

  - Die ersten vier Faelle belegen Schritt 1-2 (Format/Digest) und negative 10 live. Die folgenden vier belegen, dass revoked/disabled/expired und der Catalog-Schritt serverseitig durchgesetzt werden — der Agent war ACTIVE im Terraform-verwalteten Catalog, wurde also nicht wegen "unbekannt" abgelehnt.
  - Der letzte Fall ist zugleich der Blocker und zugleich ein Positivbefund: er beweist live, dass Schritt 13 (Entitlement) der Verification wirklich greift. Mit korrektem Credential und ACTIVE-Profil wird genau an der fehlenden Entitlement abgelehnt.

  WARUM der positive Live-Nachweis blockiert ist (neu entdeckter Blocker B5)
  - B5: fuer Entitlements existiert KEIN Provisionierungs-Pfad.
    * Keine Gateway-Route (grep entitlements in den 28 Routen: 0 Treffer)
    * Kein Handler: in lambda/handler.py gibt es nur _get_entitlement_for_agent, _get_entitlements, _is_entitlement_valid — alle lesend
    * Keine Modul-Funktion: repo-weite Suche nach put_item/update_item/create/grant in Verbindung mit entitlements liefert 0 Treffer (die Treffer in offers.py betreffen offers, nicht entitlements)
    * Die Lambda-Rolle hat auf mays-ris-dev-entitlements nur dynamodb:GetItem, Query, BatchGetItem — kein PutItem
    * Auch Terraform hat keinen Entitlement-Seed (der aws_dynamodb_table_item aus B4-TERRAFORM-01 betrifft ausschliesslich den Agent-Catalog)
  - Damit kann die vollstaendige Kette Credential -> APIProfile -> Entitlement -> AgentCatalog -> Execution live nicht durchlaufen werden, ohne eine Zeile manuell in DynamoDB zu schreiben.
  - ENTSCHEIDUNG DES AUFTRAGGEBERS: Option 3 — kein Direct-DDB-Write, kein Workaround, sondern ein eigenes Gate. Bewertet als sauber isolierter Blocker: NICHT RED wegen Credential-Logik.

  APIProfile-Bindung / Agent-Routing / Catalog / Entitlement — Nachweise
  - APIProfile-Bindung: das Credential ist an genau ein Profil gebunden; ein Request gegen die Machine-Route nutzt ausschliesslich dieses Profil (verify_api_credential Schritt 3-8). Live belegt dadurch, dass revoked/disabled/expired Credential auch bei ACTIVE-Profil abgelehnt werden.
  - Agent-Routing: agent_id aus dem Pfad; Test belegt, dass /v1/m2m/agents/x (ohne /execute), /v1/m2m/, /v1/m2m/other und .../execute/extra NICHT von der Machine-Route erfasst werden (400/401/404, nie Execution).
  - Agent Catalog: der Terraform-managed Eintrag reference_agent wird live aufgeloest (Lambda-Coldstart-Log "Registered agent: reference_agent", "Catalog initialized: 1 agents registered" aus dem B4-Gate; hier genutzt durch Schritt 14 der Verification).
  - Entitlement: Schritt 13 wirkt live (403 im letzten Fall). Die positive Auswirkung ist mangels Provisionierungspfad nicht live nachweisbar; in der Testsuite vollstaendig (TestPositive.test_full_chain_reaches_entitlement_and_catalog entfernt nacheinander Entitlement und Catalog-Status und erwartet jeweils 403).
  - reference_agent E2E: bis Schritt 13 live belegt; ab dort BLOCKED (B5). Kein Ausfuehrungsnachweis live.
  - Existing Execution Path: die Weitergabe in _enqueue_agent_work ist implementiert und getestet; die Ausfuehrung selbst (SQS -> pipeline) wurde live NICHT angestossen, weil kein autorisierter Request bis dorthin gelangen kann. Der Worker-Pfad ist unveraendert.

  Human Regression (§11)
  - Mit bestehendem Cognito-JWT: GET /me 200, GET /platform 200, GET /agents 200, GET /v1/introspection 200.
  - Zusatznegativ: /v1/m2m/agents/reference_agent/execute mit JWT-Authorizer-Claims, aber ohne Bearer-Header -> 401, keine Execution.
  - Testsuite: alle bestehenden Human-Pfade unveraendert; Fehlerbestand identisch zur Baseline (siehe Tests).

  Security / Audit (§15)
  - Kein Credential-Secret im Lambda-Log: geprueft ueber 263 Logzeilen der letzten 20 min -> exaktes Secret: False; "ris_" 0x; "authorization" 0x; "bearer" 0x; JWT-artige 3-Segment-Strings 0.
  - Audit-Events fuer die Machine-Verifikation vorhanden und secret-frei, z. B.:
    action=verification outcome=unauthorized route=POST /v1/m2m/agents/{agentId}/execute (ohne credentialId — bei unbekanntem Credential korrekt)
    action=verification outcome=forbidden apiProfileId=aprof_7f25211860244f9e credentialId=cred_5298184d97d74975 tenant=b3-1791215000 clientRef=None request=... route=POST /v1/m2m/agents/{agentId}/execute
  - Audit-Felder enthalten nur ref, action, outcome, request, route, credentialId, apiProfileId, tenant, clientRef — kein Secret, kein Header, kein JWT.
  - Denial-Body ist neutral: {"error":"Unauthorized"} bzw. {"error":"Forbidden"}. Test belegt, dass weder credentialId, credential, profile, entitlement, catalog noch der Secret-Wert im Body erscheinen (kein Orakel).
  - Revocation-Semantik bleibt wirksam: revoked/disabled/expired live 403 (siehe Live-Tabelle).
  - Store-Ausfall wird nie als 401/403 gemeldet: Unit-Test mit explizit werfendem Store -> 503; nicht konfigurierte Sources -> 503.

  Tests (§10)
  - NEU tests/test_machine_entrypoint.py: 22 Tests, alle gruen.
    Positiv (4): gueltiges Credential erreicht den Execution Contract; Ausfuehrungs-Subject kommt aus dem verifizierten Kontext (manipulierter Body ignoriert); agent_id aus Pfad; volle Kette (Entitlement UND Catalog wirklich konsultiert).
    Negativ (12): unbekannt 401; kaputt 401 (5 Varianten); revoked 403; disabled 403; expired 403; nicht-ACTIVE-Profil 403; fehlende Entitlement 403; unbekannter Agent 403; nicht ausfuehrbarer Agent 403; Human-JWT 401; kein Header 401; Store-Ausfall 503; unkonfigurierte Sources 503; Denial-Body ohne Orakel.
    Plangrenze (4): Machine-Route nicht mit JWT-Kontext nutzbar; /v1/m2m/ erfasst keine fremden Pfade; agent_id-Extraktion strikt; Sanitizing schuetzt vor Pfadtraversal.
  - KEINE kuenstliche Testzahl: jeder Test prueft Verhalten der Kette oder der Plangrenze.
  - Gesamtsuite MIT Aenderung: 8 failed, 825 passed, 8 skipped, 1 error.
  - BASELINE (03f48c7, per git stash inkl. der neuen Testdatei): 8 failed, 803 passed, 8 skipped, 1 error.
  - diff der Fehlerlisten: IDENTISCH -> keine Regression. Delta +22 = exakt die neuen Tests.
  - Zusaetzlicher Nachweis der Testwirkung: mit gestashtem handler.py (also OHNE die Implementierung) schlagen alle 20 Machine-Verhaltenstests fehl — sie testen also tatsaechlich den neuen Code.
  - Build/Lint/Type: kein Python-Build im Projekt; CI (.github/workflows/ci-cd.yml) macht ausschliesslich Terraform, kein pytest, kein Linter. flake8/mypy/ruff nicht installiert und nicht konfiguriert (nicht erfunden). TypeScript nicht anwendbar. py_compile OK; AST-Import-Check ohne ungenutzte Imports. fmt: modules/api/main.tf und modules/dynamodb/main.tf formatiert; die 6 nicht formatierten Dateien sind die Baseline aus Discovery-07 und wurden nicht angefasst.

  Cleanup (§9/§15)
  - 6 Credentials dieses Gates ueber den Produktpfad REVOKE + 2 Testprofile ueber den Admin-Pfad REVOKED (HTTP 200). Der Revoke-Status wurde live bestaetigt (revidiertes Credential -> 403).
  - 2 Testuser (b3-owner, b3-admin) geloescht; Cognito-Pool wieder bei 14 Usern; admins-Gruppe wieder auf die 4 vorbestehenden Mitglieder.
  - tmp-Verzeichnis mit Passwoertern, Tokens und Secrets entfernt (bestaetigt).
  - Endstand nach Nachzaehlung: credentials 14 = 6 Baseline + 8 dieses Gates, ALLE 14 REVOKED, 0 ACTIVE im gesamten Bestand. api-profiles 11 = 9 Baseline + 2 dieses Gates, beide REVOKED. entitlements 0 — es wurde nie eine geschrieben.
  - Korrektur einer eigenen Zwischennotiz: ich hatte vorlaeufig "vor diesem Gate: 11/12/0" notiert. Die korrekte Baseline war 9 Profile / 6 Credentials (aus dem B4-TERRAFORM-01-Abschluss). 6 + 8 = 14 und 9 + 2 = 11 — die Endzahlen stimmen, die Baseline-Notiz war falsch.
  - Machine-Route nach Cleanup aktiv: 401 ohne Credential (erwartet).

  Eigene Fehler in diesem Gate (transparent)
  - range_key-Argument zuerst gesetzt, obwohl die Tabelle keinen sort key hat — entfernt
  - Freie Attribute als Argumente von aws_dynamodb_table_item verwendet — 4 validate-Fehler; korrigiert auf item als AttributeValue-JSON (B4-Gate, hier nur erwähnt)
  - Live-E2E-Skript sandte den Authorization-Header OHNE "Bearer "-Praefix -> alle Faelle 401; nach Korrektur Contract-Semantik korrekt
  - Live-E2E-Skript verwendete einen festen Profilnamen -> zweiter Lauf 404 (create_profile erlaubt keinen Namensdoppel), pid=None; mit eindeutigem Namen behoben
  - Drei Test-Fehlpraezisionen (meine Testlogik, nicht die Implementierung): InMemoryCredentialStore-Attribut heisst by_id (nicht _rows); Sanitizing-Erwartung pruefte faelschlich den Punkt (Punkte sind in Agent-IDs zulaessig, der Pfadtrenner nicht); Baseline-Vergleich stufte zunächst nur zwei Dateien statt auch die neue Testdatei
  - Extraktion des Execution-Helpers: nach dem Umbau fehlte zuerst der return-202-Block — ergaenzt, per Diff gegen Baseline verifiziert

- Evidence / file references: lambda/handler.py:392 (Dispatch-Zweig /v1/m2m/), :731 _machine_bearer, :759 _machine_agent_id, :779 _machine_execute_agent, :831 verify_api_credential-Aufruf, :1533 _enqueue_agent_work, :1697ff _execute_agent (nutzt den Helper); agents/ecosystem/credentials.py:48-58 (VerifyOutcome/CredentialStoreUnavailable), :627-641 (VerifyDecision), :751 verify_api_credential, :816-830 (Schritt 14 Catalog), :909 DynamoDBCredentialStore; agents/ecosystem/worker_authorization.py:154-186 (Resolver, gsi-user); agents/ecosystem/catalog_adapter.py; terraform/modules/api/main.tf (Route m2m_agent_execute, authorization_type NONE), :40-45 (bestehende Integration), :28-38 (JWT-Authorizer); terraform/modules/lambda/main.tf (IAM read-only, env); lambda/build_zip.py (Bundle-Vertrag); tests/test_machine_entrypoint.py; docs/reports/RIS-B3-B4-COGNITO-AND-AGENT-ENTRYPOINT-DISCOVERY-07.md (Optionsentscheidung D); docs/reports/RIS-B4-PERSISTENT-AGENT-CATALOG-TERRAFORM-EXTENSION-01-EXECUTION_LOG.md (reference_agent, Terraform-managed); CloudWatch /aws/lambda/mays-ris-dev-agent (Audit + Secret-Pruefung)

- Classification: YELLOW (Implementierung vollstaendig, produktiv deployed, 9 negative Live-Faelle + Human-Regression GREEN; BLOCKED fuer den positiven Live-Nachweis durch neuen Blocker B5 "kein Entitlement-Provisionierungspfad"). Kein RED: kein Sicherheits- oder Autorisierungsfehler in der Credential-Logik gefunden.

- Terraform checks actually executed and their results:
  - `terraform fmt modules/api/main.tf`, `terraform fmt -check -recursive` — meine Dateien formatiert; 6 nicht formatierte Dateien = Baseline
  - `terraform validate` — Success (Warnungen Baseline)
  - `terraform plan` x3 — (1) 1 create Route; (2) 1 create Route + 1 update Lambda-Code; (3) nach apply "No changes."
  - `terraform show -json` x2 — Zerstoerungen [], Ersetzungen [], 0 IAM-Ressourcen, keine verbotenen Typen, 24 von 25 Routen no-op
  - `terraform apply` — "Resources: 1 added, 1 changed, 0 destroyed."
  - KEIN Destroy, KEIN taint, KEIN state rm, KEINE IAM-Manipulation

- Git status: bei Start 0 modified tracked; vor Commit: geaendert lambda/handler.py, terraform/modules/api/main.tf, neu tests/test_machine_entrypoint.py + dieses Log + Build-Artefakt terraform/lambda.zip; nach Commit 0 modified tracked

- Files changed, if any:
  - GEÄNDERT: lambda/handler.py (Execution-Helper extrahiert + Machine-Entry-Point + Dispatch)
  - GEÄNDERT: terraform/modules/api/main.tf (eine Route)
  - NEU: tests/test_machine_entrypoint.py
  - NEU: docs/reports/RIS-B3-MACHINE-CREDENTIAL-ENTRYPOINT-IMPLEMENTATION-08-EXECUTION_LOG.md
  - Build-Artefakt: terraform/lambda.zip (deterministisch neu gebaut; von Terraform per source_code_hash konsumiert)
  - NICHT committed: 8 vorbestehende untracked Reports fremder Gates; terraform/.terraform.lock.hcl

- Explicit confirmation when no files were changed: entfaellt — es wurden Dateien geaendert. Hervorzuheben: keine bestehende Human-Route, kein bestehender Authorization-Pfad, keine IAM-Policy, kein Cognito-Setup und keine bestehende Produktlogik wurden veraendert. Die Machine-Route ist additiv; die Human-Ausfuehrung nutzt unveraendert dieselbe Entitlement-/Catalog-Logik und nur denselben Enqueue-Helper.

- Open questions:
  - B5 (neu): wie sollen Entitlements provisioniert werden? VOR der Entscheidung ist zu pruefen, ob das bestehende Architekturmodell eher zu Terraform-/Foundation-Seeding passt (analog Agent Catalog) oder ob es einen offiziellen Managementpfad geben sollte. Es wird hier KEINE automatische HTTP-Admin-Route gebaut und KEIN Entitlement-System entworfen.
  - `_catalog`-Zugriff in der Machine-Route: agent_version wird aus sources["catalog"] gelesen, das ist ein agentId->STATUS-Map; der Wert ist dort nicht vorhanden, also greift der Default 1.0.0. Unsauber, aber harmlos und dokumentiert — sauber waere der versionierte Catalog-Zugriff (exists: CatalogAdapter). Entweder so belassen oder in einem Folge-Gate mit dem B5-Gate zusammen korrigieren.
  - Abgelaufene Credentials koennen ueber den Produktweg ausgestellt werden (expiresAt in der Vergangenheit wird akzeptiert). Das ist kein Fehler dieses Gates, aber eine Entscheidung, die jemand treffen sollte: entweder Ausstellung ablehnen oder bewusst zulaessig.
  - `introspect_credential` bleibt weiterhin unerreichbar (handler.py:790 unter if bearer_credential). Dieses Gate hat nur den Execution-Pfad angebunden; Introspection fuer Maschinen ist NICHT Teil des Auftrags.
  - GET /agents bleibt entitlement-gefiltert; mit provisionierten Entitlements waere es erstmals befuellt.

- Risks:
  - Keine Secrets, Tokens, Passwoerter oder Authorization-Header im Report oder im Lambda-Log (263 Zeilen geprueft: 0 Treffer fuer Secret, ris_, authorization, bearer, JWT-Muster).
  - Die Machine-Route ist bewusst ohne JWT-Authorizer. Das ist korrekt und notwendig, bedeutet aber: ihr Schutz liegt zu 100% im Lambda-Code. Deshalb ist die Testabdeckung der Kette (22 Tests) und die Live-Negativpruefung (9 Faelle) die eigentliche Absicherung.
  - Kein Runtime-Schreibrecht auf dem Agent-Catalog; Provisionierung bleibt Terraform (B4-Gate).
  - 2 Testprofile und 8 Testcredentials bleiben als REVOKED terminal zurueck, weil kein produktiver Delete-Pfad existiert (Gate 04/05) — bewusst, dokumentiert, kein Zugriffsrisiko.
  - B5 ist ein Blocker fuer den Nachweis, NICHT fuer die Sicherheit: die Kette verweigert ohne Entitlement korrekt den Dienst (403). Das ist fail-closed, also kein offenes Risiko.
  - Die Kette ist in der Unit-Ebene vollstaendig positiv belegt; das fehlende Stueck ist ausschliesslich die Live-Fixture fuer Entitlement.

- Recommended next actions:
  - P17 und P20 NICHT automatisch starten.
  - Eigenes Gate RIS-ENTITLEMENT-PROVISIONING-FOUNDATION-09 beauftragen: erst Discovery des bestehenden Entitlement-Modells und der IaC-/Provisioning-Grenze, dann entscheiden, ob Terraform der richtige Writer ist oder ob ein offizieller Managementpfad existiert. Ziel: genau eine synthetische Foundation-Entitlement fuer reference_agent, reproduzierbar, ausserhalb des Runtime-Pfads, ohne neue Business-Entitlement-Logik.
  - Danach B3-08 erneut aufnehmen, um den positiven Live-Nachweis bis zur Ausfuehrung zu vervollstaendigen.
  - Kleinigkeiten optional in einem Folge-Gate: versionierter Catalog-Zugriff in der Machine-Route, Ausstellung abgelaufener Credentials.

- Current resume point: Commit + Push dieser Gate-Aenderungen, danach HARD STOP

==================================================
