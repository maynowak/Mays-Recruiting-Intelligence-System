==================================================
CHECKPOINT: 2026-10-06 (P21-COGNITO-M2M-AUTHORIZATION-BOUNDARY-01) — GREEN (Branch: main, HEAD: 1233c54 vor Commit)
==================================================

- Current status: GREEN. Beide Scopes umgesetzt, live verifiziert, committed und gepusht.
- Audit date/time: 2026-10-06
- Current Git branch and HEAD: main, 1233c54 (P20-01 abgeschlossen und gepusht; dieser Gate-Stand committet als 59a8ec9-Nachfolger)
- Audit scope: RIS-P21-COGNITO-M2M-AUTHORIZATION-BOUNDARY-01 — Architekturentscheidung: "Cognito bleibt die Managed-Authentication-Boundary. APIProfile/Credential/Entitlement liefern zusaetzliche Produkt-/API-Autorisierung innerhalb dieses bereits authentifizierten Kontexts." Die opake ris_...-Credential bleibt bestehen und wird NICHT durch Cognito ersetzt.
- Live-Kontext (§12):
  - AWS Account 240571105849, AWS Profile mayaws, Region eu-central-1
  - Terraform Workspace mays-ris, Git branch main
  - API-ID aboqolpm0f, Stage $default, Basis-URL https://aboqolpm0f.execute-api.eu-central-1.amazonaws.com
  - Lambda mays-ris-dev-agent, CodeSha256 UZGwmqoqvojqspg9dDH9hQA3gi+wN9yz8NT5U7ALk5k=
  - Cognito User Pool eu-central-1_dgQXgwUbv, Client mays-ris-dev-client (3pkcifopuisumo14cg1pj0cfeo)

- Completed audit sections:
  - Discovery A-G read-only (Gateway, Authorizer, Handler-JWT, verify-Kette, Tests, Wiederverwendbarkeit)
  - Header-Konflikt geklaert und als Design-Entscheidung dokumentiert
  - Terraform: Machine-Route NONE -> JWT, fmt/validate/plan kontrolliert
  - Lambda minimal angepasst: Credential-Kanal + Cognito-Identitaetspflicht
  - Tests: 32 neue (P21), 3 bestehende Suites auf neuen Transport umgestellt
  - Positive E2E bis COMPLETED, 11 Negativfaelle live
  - Regression: alle 28 Routen, /health, Human-API
  - Scope-Kontrolle, Security Logging, Commit, Push

- Actual findings (nur verifizierte Fakten):

  DISCOVERY (A-G, read-only, vor jeder Aenderung):
  - A: Machine-Route war live `AuthorizationType NONE`, `AuthorizerId: null`, Zielintegration agent.
  - B: Authorizer `9ghezn`, Name mays-ris-dev-jwt, JWT, IdentitySource `$request.header.Authorization`,
      Audience `3pkcifopuisumo14cg1pj0cfeo`, Issuer `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_dgQXgwUbv`.
      Live-Gegenprobe: Fake-JWT auf /platform -> 401, also Signaturpruefung aktiv.
  - C: Der Handler las JWT-Claims NIE aus Authorization, sondern aus `requestContext.authorizer.jwt.claims`
      (_extract_user_context, handler.py:286-315). Die Gateway-Verifikation ist also die einzige JWT-Quelle;
      die Handler-Extraktion ist reine Weiterreichung und nicht faehlsch.
  - D: verify_api_credential setzt `context.userId = profile.ownerUserId` (credentials.py:831) — die
      Ausfuehrungsidentitaet stammt aus dem CREDENTIAL-Profil, nicht aus dem JWT und nicht aus Body/Header.
  - E: Entitlement-Pruefung via check_worker_entitlement (worker_authorization.py:91-151), Katalog-Pruefung
      ueber is_executable_status. Beides unveraendert wiederverwendet.
  - F: Relevante Tests: test_machine_entrypoint (22), test_p17_credential_lifecycle (25),
      test_entitlement_provisioning (39), test_credential_verification, test_authorization_context,
      test_worker_entitlement_recheck, test_introspection_capability — zusammen 155 Tests.
  - G: Die bestehende Authorizer-Konfiguration erfuellt den Vertrag (issuer+audience+signatur) und wurde
      ohne jede Aenderung wiederverwendet. Keine Cognito-Ressource wurde angefasst.

  KERNBEFUND — Header-Konflikt:
  Der Authorizer liest `$request.header.Authorization`; die Machine-Route las denselben Header als opaken
  Bearer (_machine_bearer, handler.py:756-780). Ein Header kann nicht beides tragen: ein JWT hat drei
  Punkt-Segmente, ein ris_-Secret keines. Entscheidung: Authorization bleibt der JWT-Kanal (kein Eingriff
  in den geteilten Authorizer, keine der 26 Human-Routen betroffen), die opake Credential wandert nach
  `X-Api-Credential`. Repo-Konvention `X-Api-Profile` (SELECTION_HEADER) als Praezedenzfall.
  Das ist KEINE neue Credential-Technik: gleiches Secret, gleicher Digest-Store, gleicher Verifier.

  SCOPE 1 — Gateway/Terraform:
  - Geandert wurde ausschliesslich `terraform/modules/api/main.tf` (Route m2m_agent_execute):
    authorization_type NONE -> JWT, authorizer_id = aws_apigatewayv2_authorizer.jwt.id.
  - Plan vor Apply: `0 to add, 1 to change, 0 to destroy`, danach mit Lambda-Code genau 2 Aenderungen.
  - Live nach Apply: AuthorizationType JWT, AuthorizerId 9ghezn, 27 JWT / 1 NONE, /health bleibt die
    einzige NONE-Route, 28 Routen unveraendert, 1 Authorizer unveraendert.

  SCOPE 2 — Lambda (minimal):
  - Neue Konstante `MACHINE_CREDENTIAL_HEADER = 'x-api-credential'`.
  - `_machine_bearer` liest dieses Header; JWT-Form (>=2 Punkte) wird abgewiesen.
  - Neue `_machine_cognito_context` verlangt eine Cognito-Identitaet (`sub`) und gibt 401 sonst.
    Das ist die Lambda-seitige Absicherung gegen direkte Aufrufe, die den Gateway umgehen.
  - Denials loggen jetzt `cognitoUser`, `outcome` und `requestId` — ausschliesslich sichere Metadaten.
  - Kein bestehener Produktpfad geaendert: verify_api_credential, APIProfile-, Entitlement- und
    Agent-Pruefung sind unveraendert.

  IDENTITAETSBINDUNG (§3):
  - Die Cognito-Identitaet wird fuer Audit erfasst, waehlt aber NIE die Ausfuehrungsidentitaet.
  - Live bewiesen (Negativfall 10): Body mit `userId=u-attacker, tenantId=t-attacker, agentId=some-other-agent`
    ergab 202, das WorkItem fuehrt jedoch userId=Cognito-sub, tenantId=p21-e2e-tenant, agentId=reference_agent.
    Ein Scan ueber alle WorkItems fand kein einziges mit u-attacker/t-attacker.
  - `agentId` stammt weiterhin ausschliesslich aus dem Route-Path (_machine_agent_id).

  POSITIVE E2E (§5, live):
  - Cognito Login (kontrollierter Testuser p21-boundary-admin, Gruppe admins, custom:tenant_id gesetzt)
    -> ID-Token -> Gateway-JWT-Pruefung bestanden.
  - APIProfile aprof_9199d98c75be4a0c angelegt und auf ACTIVE gesetzt; Credential cred_3314146eb35c4fd2
    ausgestellt (Secret einmalig).
  - 202 QUEUED, workId df04bac6-abad-4a49-8208-6e68c55fc06a.
  - WorkItem -> SQS (Queue auf 0 konsumiert) -> Worker -> reference_agent -> COMPLETED (WorkItem-Status live).
  - Hinweis: das ID-Token war noetig, weil nur dieses `custom:tenant_id` traegt; das Access-Token fuehrt
    Custom-Claims nicht. Ausserdem muss ein Entitlement user-weit sein (ohne apiProfileId), weil
    verify_api_credential check_worker_entitlement ohne api_profile_id aufruft — beide sind bestehende
    Vertragsdetails, keine Aenderung dieses Gates.

  NEGATIVE E2E (§6, live, 11 von 12 Punkten):
  - 1 kein Authorization: 401 `{"message":"Unauthorized"}` (Gateway)
  - 2 ungueltiger/random JWT: 401 (Gateway)
  - 3 Human JWT ohne Credential: 401 `{"error":"Unauthorized"}` (Lambda)
  - 4 unbekannte Credential: 401 (Lambda)
  - 5 revoked Credential: 403
  - 6 disabled Credential: 403
  - 7 expired Credential: 403
  - 8 falscher agentId / kein passendes Entitlement: 403
  - 9 fremdes Profil via X-Api-Profile: 403
  - 10 manipulierte Identitaet im Body: 202, aber WorkItem zeigt verifizierte Identitaet (siehe oben)
  - 11 falscher agentId in der Route (existiert nicht): 404 vom Gateway
  - 12 Human API unveraendert: /platform, /me, /agents, /v1/introspection, /v1/apiprofiles je 200 mit JWT
  - KERNFALL (Auftrag Punkt 6, besonders wichtig): gueltige ris_ OHNE Cognito-JWT -> 401.
    Zwei Varianten geprueft (ris_ in Authorization und ris_ in X-Api-Credential), beide 401 vom Gateway.

  BEWEIS „VOR LAMBDA“ (nicht nur Statuscode):
  - Fehlerformat trennt die Grenzen: Gateway antwortet `{"message":"Unauthorized"}`, der Handler
    `{"error":"Unauthorized"}`. Die abgewiesenen Faelle zeigen die Gateway-Form.
  - CloudWatch-Gegenprobe im selben Zeitfenster: 1x `API request: GET /health` (Lambda erreicht),
    0x `API request: POST /v1/m2m`. Kein Request ohne gueltiges Cognito-JWT hat den Lambda erreicht.

  REGRESSION (§9):
  - Alle 28 Routen ohne JWT geprueft: 27x 401, 1x 200 (/health).
  - /health unveraendert 200 mit demselben Body wie vor diesem Gate.
  - /me, /platform, /agents, /v1/introspection, /v1/apiprofiles je 200 mit gueltigem JWT.
  - APIProfile- und Credential-Management bleiben Human-JWT-gebunden (kein Credential-Header noetig).

  TESTS (§11):
  - Neu: tests/test_p21_cognito_m2m_boundary.py, 32 Tests (Cognito-Grenze, Credential-Kette,
    Identity Binding, Anti-Oracle, Security Logging, Regression).
  - Angepasst: test_machine_entrypoint, test_p17_credential_lifecycle (Event-Bau auf neuen Transport),
    test_p20_api_contract_consistency (NONE-Anker von 2 auf 1 Route).
  - Suite: 952 passed, 8 failed, 8 skipped, 1 error.
  - Die 8 failures + 1 error sind EXAKT die bekannte Baseline aus P20 (test_agent_invocation x2,
    test_platform_handlers x5, test_reference_agent x1, test_processing_chain error).
    Kein Baseline-Fehler wurde durch dieses Gate behoben; das wird ausdruecklich NICHT behauptet.
  - Zwei zusaetzliche Fehler traten nur auf, solange `AWS_PROFILE=mayaws` in der Shell exportiert war
    (test_ris_installer erwartet sauberes Env; test_lambda_packaging las einen veralteten Live-Hash).
    Nach Bundle-Neubau und ohne exportiertes AWS_PROFILE: 8 failed, 952 passed — Baseline identisch.

- Evidence / file references:
  - terraform/modules/api/main.tf:218-247 (Machine-Route, Kommentar + JWT-Verknuepfung)
  - lambda/handler.py:756-800 (_machine_bearer, MACHINE_CREDENTIAL_HEADER), :802-825
    (_machine_cognito_context), :843-941 (_machine_execute_agent mit beiden Grenzen),
    :941-950 (Denial-Audit mit cognitoUser)
  - docs/api/API-STANDARD.md §1 (Authentifizierung/Autorisierung), §1.1 (zwei Credentials),
    §2.1 (Machine API, Identity Binding), §5, §8 (Vertragsaenderung P21-01)
  - tests/test_p21_cognito_m2m_boundary.py (32 Tests)
  - Live-Nachweis: Gateway AuthorizationType JWT / AuthorizerId 9ghezn; WorkItem
    df04bac6-abad-4a49-8208-6e68c55fc06a COMPLETED; WorkItem 8159598f-d240-4955-b8c7-ac1961bc5b6f zeigt
    verifizierte Identitaet trotz manipuliertem Body

- Classification: GREEN
- Terraform checks actually executed and their results:
  - `terraform fmt modules/api/main.tf` (nur die geaenderte Datei) -> formatiert; `fmt -check` -> sauber.
    Gegenprobe mit git stash belegt: fmt-Drift in den anderen Dateien bestand BEREITS VOR diesem Gate
    und wurde bewusst nicht angefasst (verhindert ungefragten Fremd-Diff).
  - `terraform validate` -> Success! (mit vorbestehenden Deprecated-Warnungen, unveraendert)
  - `terraform plan` vor Apply -> `Plan: 0 to add, 1 to change, 0 to destroy`, nur m2m_agent_execute
  - `terraform plan` nach Bundle -> 2 Aenderungen: m2m_agent_execute + agent source_code_hash
  - `terraform apply` -> `Apply complete! Resources: 0 added, 2 changed, 0 destroyed`
  - `terraform plan` nach Apply -> `No changes. Your infrastructure matches the configuration.`
  - IAM: 0 attached, 1 inline Policy — unveraendert. Cognito: Client und Pool unveraendert
    (LastModifiedDate 2026-10-02, 22 Schema-Attribute). Tabellen: alle unveraendert.
- Git status: 6 modified tracked + 1 neue Testdatei, committet und gepusht. Working Tree bei tracked
  Files sauber. Fremde untracked Reports und terraform/.terraform.lock.hcl unberuehrt.
- Files changed, if any:
  - `terraform/modules/api/main.tf` — Machine-Route auf JWT umgestellt, veralteter Kommentar ersetzt
  - `lambda/handler.py` — Credential-Kanal, Cognito-Kontextpflicht, Denial-Audit, Docstring
  - `docs/api/API-STANDARD.md` — Auth-Architektur, zwei Credentials, Machine API, Identity Binding,
    Vertragsaenderung P21-01
  - `tests/test_p21_cognito_m2m_boundary.py` — neu, 32 Tests
  - `tests/test_machine_entrypoint.py` — Event-Bau auf neuen Transport (keine Aussage geaendert)
  - `tests/test_p17_credential_lifecycle.py` — dito
  - `tests/test_p20_api_contract_consistency.py` — NONE-Anker und Doku-Erwartungen an P21 angepasst
  - Nicht committed: `terraform/lambda.zip` (gitignored), lokale Credential-Dateien in /tmp/opencode
    (0600, ausserhalb des Repos)
- Explicit confirmation when no files were changed: Entfaellt — Dateien wurden geaendert. Hervorzuheben:
  keine IAM-Policy, keine Cognito-Ressource, keine DynamoDB-Tabelle, keine neue Route, keine neue
  Integration, keine bestehende Human-Route und keine Produktlogik in verify_api_credential wurden
  angefasst. Alle 9 Baseline-Testfehler unveraendert.
- Open questions:
  - Vertragsaenderung ist bewusst: Machine-Clients, die bisher nur ein ris_ in Authorization senden,
    erhalten ab sofort 401 vom Gateway. Das ist die geforderte Architektur, aber ein Client-seitiger
    Migrationsschritt. Dokumentiert in API-STANDARD.md §8.
  - Verdaechtiger Nebenbefund (nicht in diesem Gate behoben): verify_api_credential ruft
    check_worker_entitlement OHNE api_profile_id auf. Profil-gebundene Entitlements
    (apiProfileId gesetzt) werden dadurch als `profile-mismatch` abgewiesen. Das ist bestehendes
    Verhalten, kein P21-Einfuehrungsfehler — im E2E wurde deshalb ein user-weites Entitlement verwendet.
    Als OPEN-1 notiert, nicht eigenmaechtig geaendert.
  - Es existiert weiterhin kein produktiver HTTP-Pfad, um Entitlements anzulegen; fuer das E2E wurde
    eines per CLI geschrieben (zwei Zeilen). Das ist ein Testartefakt, kein Produktfeature.
  - Der Testuser p21-boundary-admin bleibt im Pool. Weitere Test-Entities (APIProfile, 4 Credentials,
    2 Entitlements, 2 WorkItems) bleiben zur Nachvollziehbarkeit bestehen; Credentials sind revoked bzw.
    disabled, also nicht nutzbar.
- Risks:
  - Machine-Clients brechen ohne Anpassung. Bewusst so entschieden und dokumentiert.
  - Die Gateway-Pruefung allein reicht nicht als defense in depth: ein direkter Lambda-Aufruf umgeht
    sie. Deshalb verlangt `_machine_cognito_context` zusaetzlich Cognito-Claims im Event.
  - Ein JWT-Claim wird fuer Audit geloggt (cognitoUser). Das ist ein Pseudonym, kein Secret, und war
    bereits auf Human-Routen ueblich; Log-Scan bestaetigt 0 Secret-Treffer.
  - Wer `verify_api_credential` spaeter um `api_profile_id` erweitert, aendert die Entitlement-Semantik
    und muss den bestehenden P17-Nachweis erneut pruefen.
- Recommended next actions:
  1. HARD STOP. Kein Frontend, kein Product-Admin-UI, kein Privacy/Retention-Gate aus diesem Auftrag.
  2. OPEN-1 (Entitlement api_profile_id) als eigenes Gate terminieren, falls gewuenscht.
  3. Client-seitige Meldung des neuen `X-Api-Credential`-Kanal dokumentieren, sobald es Clients gibt.
- Current resume point: abgeschlossen — Commit und Push erfolgt, HARD STOP

==================================================