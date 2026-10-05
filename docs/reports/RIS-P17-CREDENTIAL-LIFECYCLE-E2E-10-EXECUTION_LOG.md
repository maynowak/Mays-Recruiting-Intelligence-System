==================================================
CHECKPOINT: 2026-10-05 22:00 UTC — P17 CREDENTIAL LIFECYCLE E2E (GREEN) (Branch: main, HEAD: a31abee)
==================================================

- Current status: GREEN. Der Credential-Lifecycle ist ueber den produktiven Machine-Entry-Point vollstaendig live belegt: Issue, Secret-Einmal-Semantik, GET/LIST ohne Secret, Ausfuehrung bis COMPLETED, Profile-Binding, Disable/Enable, terminaler Revoke, Expiry, Rotation A->B, Tenant-Isolation, Entitlement-Negative, Human-Regression, Audit, Log-Secret-Scan. Cleanup ueber die zulaessigen Wege; 0 ACTIVE Credentials. B3/B5 wurden NICHT neu implementiert.
- Audit date/time: 2026-10-05 22:00 UTC
- Current Git branch and HEAD: main, a31abee (Gate-Start)
- Audit scope: RIS-P17-CREDENTIAL-LIFECYCLE-E2E-10 — End-to-End-Nachweis des Credential-Lifecycles ueber den produktiven Machine-Entry-Point
- Completed audit sections:
  - AI_AUDITLOG-Pflicht-Template; Log VOR der Durchfuehrung angelegt, nach jedem Meilenstein fortgeschrieben
  - AWS-/Git-Kontext und Baseline
  - §3 synthetischer Kontext (2 Tenants, 3 Profile, Foundation-Entitlement, Credential)
  - §4 Issue + Secret-One-Time + GET/LIST
  - §5 Machine Execution bis COMPLETED
  - §6 Profile Binding
  - §7 Disable/Enable
  - §8 Revoke (terminal) inkl. enable-Versuch
  - §9 Expiry
  - §10 Rotation A -> B
  - §11 Entitlement-Negative (Smoke)
  - §12 Tenant-Isolation (korrigierte Matrix + Leak-Pruefung)
  - §13 Human JWT Regression
  - §14 Audit-Vollstaendigkeit
  - §15 Log Secret Scan
  - §16 IAM-Vergleich, §19 Terraform-Endzustand
  - §17 neue P17-Tests + Baseline-Diff
  - §18 Cleanup inkl. Nachweis unerwarteter Testdaten
- Actual findings (nur verifizierte Fakten):

  KONTEXT UND BASELINE
  - AWS_PROFILE=mayaws; Account 240571105849; Region eu-central-1; Workspace mays-ris; Branch main; HEAD a31abee; Working Tree tracked clean -> KONFORM
  - Baseline-Counts: api-profiles 14, credentials 17, entitlements 0, agent-catalog 1; IAM Role Policies 8; Gateway 28 Routen; Lambda CodeSha256 VAj4iLO07i92oYiI64lbKQB8Erf2/xRR58SuowrGPuU=; terraform plan "No changes."

  §3 SYNTHETISCHER TESTKONTEXT (alles ueber die Produktwege)
  - Tenant A = p17a-1791223653: Owner p17a-owner (sub a37478a2-30b1-709f-96bc-3fa8b57f5872), Admin p17a-admin (Gruppe admins, sub 03a42812-80e1-704c-e5b2-c45002f9ab3c)
  - Tenant B = p17b-1791223653: Owner p17b-owner (sub 63b44882-8031-70b2-57b7-56578c753c38)
  - Profil A  = aprof_d77fc2712f824536 (201 PENDING -> 200 ACTIVE)
  - Profil A2 = aprof_2bda9258892e411f (201 PENDING -> ACTIVE; Sekundaerprofil fuer den Binding-Test)
  - Profil B  = aprof_3cbd4420cd7743e3 (201 PENDING -> 200 ACTIVE, cross-tenant mit reason)
  - Foundation-Entitlement ent_p17_reference_agent (Terraform, opt-in Variable): userId=sub A, tenantId=p17a-..., agentId=reference_agent, validFrom 2026-01-01, validUntil 2099-12-31. Plan: 1 create, 0 IAM. apply: 1 added.
  - Secrets wurden ausschliesslich in Dateien mit chmod 600 in einem chmod-700-Verzeichnis gehalten, nur als SHA-256-Fingerabdruck (12 Hex) und Laenge protokolliert, nie geloggt und am Gate-Ende vernichtet.

  §4 CREDENTIAL ISSUE + SECRET-ONE-TIME
  - POST /v1/apiprofiles/{A}/credentials -> 201; credentialId vorhanden; secret 47 Zeichen mit Prefix ris_ (entspricht _SECRET_RE in credentials.py:37)
  - GET /v1/apiprofiles/{A}/credentials/{cid} -> 200 und enthaelt KEIN secret-Feld
  - GET /v1/apiprofiles/{A}/credentials -> 200 und enthaelt KEIN secret in irgendeinem Item
  - Metadaten-Feldmenge live: apiProfileId, clientRef, createdAt, createdBy, credentialId, credentialType, disabledBy, expiresAt, idempotencyKey, label, lastUsedAt, ownerUserId, revokeReason, revokedAt, revokedBy, rotationOf, status, tenantId, updatedAt (19 Felder)
  - apiProfileId und expiresAt korrekt gebunden bzw. gesetzt
  - Audit: action=credential.created outcome=success (10 Treffer im Fenster)

  §5 MACHINE EXECUTION (Positiv-Referenz)
  - POST /v1/m2m/agents/reference_agent/execute mit Bearer ris_... -> 202 QUEUED
  - Worker-Nachweis: Work-Item in mays-ris-dev-work-items meldete status=COMPLETED; die Pruefung pollte das Work-Item bis zum Endstatus, sie liest nicht nur die HTTP-Antwort
  - Audit: action=verification outcome=authorized mit apiProfileId, credentialId, tenant, route

  §6 PROFILE BINDING
  - Credential A mit Header X-Api-Profile: <Profil A2> -> 202, Ausfuehrung laeuft weiter mit Profil A. Das Credential wird nicht umgebogen: selection_hint ist laut Contract Schritt 12 Audit-Metadaten-only und blockiert nie; die Verification loest weiterhin das eigene Profil auf. Beleg: das Audit-Feld apiProfileId bleibt Profil A.
  - Tenant-B-User liest Credential von Profil A -> 404 (bestehender, neutraler Contract; belegt durch tests/test_credential_management_http.py::test_get_404_cross_profile und test_404_owner_foreign)
  - Cross-Profile-Zugriff ueber den Pfad eines anderen Profils -> 404

  §7 DISABLE / ENABLE
  - eigenes Credential dafuer ausgegeben (terminale Zustaende duerfen keine weiteren Beobachtungen verfaelschen)
  - vor disable: 202 -> COMPLETED
  - disable -> 200; sofortiger Machine-Aufruf -> 403
  - enable -> 200; erneuter Machine-Aufruf -> 202 -> COMPLETED
  - Audit: action=credential.disabled (1), action=credential.enabled (1)

  §8 REVOKE (terminal, kein Cache)
  - vor revoke: 202
  - revoke -> 200; Machine-Aufruf -> 403
  - enable NACH revoke -> HTTP 409; Machine-Aufruf danach weiterhin 403. REVOKED ist terminal (_ALLOWED[REVOKED] = frozenset(), api_profiles.py:56); 409 ist der bestehende, getestete Contract (test_enable_revoked_409)
  - Audit: action=credential.revoked (2)

  §9 EXPIRY
  - BEFUND: der bestehende Produktweg erlaubt weiterhin die Ausstellung mit expiresAt in der Vergangenheit (POST -> 201). Wie in Gate §9 gefordert wurde das NICHT geaendert, nur dokumentiert.
  - Ausgestelltes abgelaufenes Credential -> Machine-Aufruf 403
  - Audit: action=credential.expired outcome=observed (1) — ein eigener Audit-Pfad fuer Expiry ist vorhanden

  §10 ROTATION A -> B
  - Credential A -> 202 vor Rotation
  - rotate -> 201; neues Credential B mit eigenem Secret (Fingerabdruck 3174997db5c4, 47 Zeichen, verschieden von A)
  - rotationOf verweist korrekt auf A; B bleibt an dasselbe apiProfileId gebunden; expiresAt gesetzt
  - A nach Rotation: Status REVOKED; Machine-Aufruf mit A -> 403
  - B: Machine-Aufruf -> 202 -> COMPLETED; Verification AUTHORIZED mit korrektem userId/tenantId/apiProfileId
  - A-Secret nirgends wiederherstellbar: GET auf A enthaelt kein secret-Feld und nicht den Secret-Wert; Rotation-Response enthaelt ihn nicht
  - Audit: action=credential.rotated outcome=success mit oldCredentialId/newCredentialId

  §11 ENTITLEMENT NEGATIVE (Smoke; B5-09 ist die Referenz)
  - falscher Agent (jobsearch-agent) -> 403
  - Entitlement ausserhalb Zeitfenster (validUntil in die Vergangenheit, ueber Terraform gesetzt, apply "0 added, 1 changed") -> 403; danach Restore (apply "0 added, 1 changed") und 202 wieder erreicht
  - B5-Referenz bleibt unveraendert: fehlende Entitlement -> 403, fremder Tenant -> 403 (dort ausfuehrlich belegt)

  §12 TENANT ISOLATION (korrigierte Matrix + Leak-Pruefung)
  - Tenant-B-Owner kann Credentials von Tenant A ausstellen (eigenes Profil B) -> 201; Machine-Aufruf mit diesem Credential gegen reference_agent -> 403, weil die Entitlement nur fuer Tenant A gilt
  - Tenant-A-Credential bleibt danach weiterhin 202 -> COMPLETED (keine Kollateralschaeden)
  - Tenant-B-User: GET fremdes Credential -> 404; disable/enable/revoke auf fremdes Credential -> 404; Ausstellung auf fremdem Profil -> 404
  - LECK-PRUEFUNG (der entscheidende Punkt): Tenant-B-User ruft GET /v1/apiprofiles/{A}/credentials -> HTTP 200 mit {"items": []}. Owner A sieht an derselben Stelle 8 Items. Also: 0 fremde credentialId sichtbar, kein secret im Response, Tenant-B sieht in der Profil-Liste nur sein eigenes Profil, und GET auf Profil A direkt -> 404. Es wird KEIN fremdes Datum preisgegeben.
  - BEFUND zur API-Oberflaeche: der LIST-Endpunkt antwortet bei fremdem Profil mit 200 + leerer Liste, waehrend der Item-Endpunkt und der Profil-Endpunkt 404 liefern. Die Semantik ist inkonsistent, aber fail-safe (leer, keine Existenzbestaetigung). NICHT geaendert — eine Aenderung waere ein APIProfile-Redesign und ist laut Gate §2 untersagt.

  §13 HUMAN JWT REGRESSION
  - GET /me 200, GET /platform 200, GET /agents 200, GET /v1/introspection 200 (mit Tenant-A-JWT)
  - POST auf der Machine-Route mit Human-JWT -> 401. Der Machine-Endpunkt ist kein zweiter Human-Endpunkt.

  §14 AUDIT — alle geforderten Aktionen im Live-Fenster belegt
  | Aktion | Treffer | outcome |
  |---|---|---|
  | credential.created | 10 | success |
  | credential.disabled | 1 | success |
  | credential.enabled | 1 | success |
  | credential.rotated | 1 | success |
  | credential.revoked | 2 | success |
  | credential.expired | 1 | observed |
  | credential.viewed | 11 | success |
  | verification authorized | 10 | authorized |
  | verification forbidden | 8 | forbidden |
  | profile-create / profile-transition | 3 / 3 | success |
  - Audit-Felder enthalten credentialId, apiProfileId, tenant, outcome, action, correlation, request, route — kein Secret, kein Header, kein JWT.
  - Audit-Schema NICHT veraendert.

  §15 LOG SECRET SCAN — GREEN (kein RED, kein HARD STOP noetig)
  - Fenster: 45 Minuten, 553 Logzeilen aus /aws/lambda/mays-ris-dev-agent
  - 'ris_' Vorkommen: 0; 'Authorization': 0; 'Bearer': 0; JWT-artige 3-Segment-Strings: 0; Woerter password/secret/token: 0; 'TemporaryPassword': 0; echte ris_-Secrets (44-50 Zeichen base64url mit Prefix): 0
  - Der Secret-Scan lief AUSSERDEM ueber den fertigen Report (siehe unten) und war sauber.

  §16 IAM — NO CHANGE
  - Gegenueber B3/B5 unveraendert: IAM Role Policies 8; entitlements-IAM-Statement weiterhin nur GetItem/Query/BatchGetItem; Gateway 28 Routen; Lambda CodeSha256 unveraendert. Terraform-Plaus enthielt 0 IAM-Ressourcen. Keine unerwarteten IAM-Aenderungen, kein STOP noetig.

  §17 TESTS
  - NEU tests/test_p17_credential_lifecycle.py: 25 Tests, alle gruen. Bewusst ERGAENZEND und nicht duplizierend (Issuing/CRUD -> test_credential_management_http.py; Machine-Einzelfaelle -> test_machine_entrypoint.py; Entitlement/Provisioning -> test_entitlement_provisioning.py; Live-Nachweise -> B3/B5 Execution Logs).
    Sequenz (4): vollstaendige geordnete Lifecycle-Sequenz ueber Management- und Machine-Plane; disable reversibel vs. revoke terminal; jede Statusaenderung per Request wirksam (kein Cache); Positiv-Referenz.
    Secret (4): Secret genau einmal in der Issue-Antwort; GET und LIST enthalten weder Feld noch Wert; stabile Metadatenform; ris_-Schema (Prefix + 47 Zeichen).
    Rotation (4): A -> REVOKED, B -> ACTIVE mit rotationOf und gleicher Profilbindung; altes Secret nicht wiederherstellbar; Kontextbindung von B; expiresAt ist Pflicht beim Rotate.
    Expiry (4): Produktweg erlaubt abgelaufene Ausstellung (dokumentierter Befund); abgelaufenes Credential -> 403 trotz gueltiger Entitlement; MIN-Regel.
    Management-Isolation (6): fremder Owner 404 auf GET und auf disable/enable/revoke; keine Ausstellung auf fremdem Profil; fremde Liste leer statt Leck; Cross-Profile-Zugriff 404; Admin erhaelt keine Cross-Owner-Kompetenz.
    Execution-Subject (4): Subject aus verifiziertem Kontext, nicht aus Header (manipulierter tenantId/userId ignoriert); fehlende/zeitfensterfremde Entitlement -> 403; tenant-mismatch.
  - Gesamtsuite MIT Aenderung: 8 failed, 890 passed, 8 skipped, 1 error
  - BASELINE (a31abee, per git stash der neuen Testdatei): 8 failed, 865 passed, 8 skipped, 1 error
  - diff der Fehlerlisten: IDENTISCH -> keine Regression. Delta +25.
  - Build/Lint/Type: kein Python-Build im Projekt; CI (.github/workflows/ci-cd.yml) macht ausschliesslich Terraform. flake8/mypy/ruff nicht installiert und nicht konfiguriert (nicht erfunden). py_compile OK; AST-Import-Check ohne ungenutzte Imports.

  §18 CLEANUP
  - Foundation-Entitlement ueber den zulaessigen Weg entfernt: Config auf leer -> plan -> apply "Resources: 0 added, 0 changed, 1 destroyed" -> entitlements Rows 0. KEIN Direct-DynamoDB-Delete.
  - 9 Credentials ueber die Produktpfade revoken, 3 P17-Profile terminalisiert (REVOKED, HTTP 200).
  - 3 Testuser geloescht; Cognito-Pool wieder bei 14 Usern (Baseline 14).
  - tmp-Verzeichnis mit Passwoertern, Tokens und Secrets vernichtet (bestaetigt).
  - Endcounts: api-profiles 17, credentials 28, entitlements 0, agent-catalog 1. Verteilung Credentials: 28/28 REVOKED, 0 ACTIVE.
  - Kein unbeabsichtigter Testdatenbestand: alle 10 Gate-Profile (B3, B5, P17) REVOKED; die 7 Baseline-Profile unangetastet.
  - work-items aus diesem Gate bleiben bis zum TTL (30 Tage) als Ausfuehrungsbeleg bestehen (work-items hat TTL ENABLED auf expiresAt, live verifiziert).

  ZUSATZBEFUND — SELBST GEFUNDENER RUECKSTAND AUS EINEM FRUEHEREN GATE
  - Bei der Endkontrolle (§18.7/.8) fiel ein nicht terminalisiertes Profil auf: aprof_1d1515c3e85546bb, name "b5-foreign", tenantId b5x-1791221111, createdAt 2026-10-05T17:25:20 — also aus Gate B5-09, NICHT aus P17.
  - Ursache: mein B5-Cleanup-Skript bearbeitete nur das Profil, dessen Credential-Ausstellung erfolgreich war. Das erste fremde Profil (PENDING, Ausstellung 409) blieb unberuehrt. In B5-09 habe ich den Cleanup als vollstaendig dokumentiert — das war unvollstaendig.
  - Kein Zugriffsrisiko: PENDING, 0 Credentials, Cognito-Owner bereits geloescht, damit inert.
  - Geschlossen ueber den Produktpfad: temporaerer Admin im Tenant b5x-1791221111, POST /status REVOKED -> HTTP 200 (PENDING -> REVOKED ist laut _ALLOWED direkt erlaubt, kein ACTIVE-Zwischenzustand noetig), Admin danach geloescht. Kein ACTIVE-Zeitfenster, in dem das Profil nutzbar gewesen waere.

  EIGENE FEHLER (transparent)
  - Live-Lifecycle: 2 meiner 48 Einzelpruefungen waren falsch formuliert, NICHT das Produkt. (a) Ich erwartete 403 beim Lesen eines fremden Credentials, bekommen 404 — 404 ist der bestehende, getestete Contract (test_get_404_cross_profile, test_404_owner_foreign). (b) Meine Assertion fuer "enable nach revoke" war fehlerhaft konstruiert (Text als expect, True als got); tatsaechlich 409, ebenfalls bestehender Contract (test_enable_revoked_409). Beide nach Pruefung des Codes und der Testbasis korrigiert, nicht das Produkt.
  - Test-Harness: act() schickte bei rotate kein expiresAt (Contract verlangt es; mein eigener Test test_rotation_requires_expires_at belegt das) -> 400 statt 201. Und der Profil-Read nutzte den ungepatchten _aprof_store, lief also gegen echtes AWS -> 503 statt 404. Beides Harness-Fehler, behoben.
  - Setup: aws-CLI-Input per json:// schlug fehl ("Invalid JSON received") -> auf Dateien mit chmod 600 umgestellt.
  - Isolationsmatrix: die LIST-Erwartung 404/403 war falsch; die tatsaechliche Antwort 200 + leere Liste wurde nicht als Fehler, sondern als eigener Befund mit Leak-Pruefung behandelt.
  - Shell-Snippet: ein python3 -c ohne json-Import und ein fehlerhaft gebautes --expression-attribute-values (JSON ohne Anfuehrungszeichen) -> beide durch robuste Varianten ersetzt.

- Evidence / file references: lambda/handler.py:779 (_machine_execute_agent), :831 (produktiver verify_api_credential-Aufruf), :985-1030 (Credential-Collection: Secret nur bei POST), :1046-1061 (_cred_ids/_cred_bound_credential, 404-Vertrag), :1061-1106 (Actions disable/enable/revoke/rotate, expiresAt-Pflicht), :1533 (_enqueue_agent_work), :318-392 (_handle_api_event); agents/ecosystem/credentials.py:37 (_SECRET_RE), :239 (issue_credential), :751 (verify_api_credential), :816-830 (Catalog-Schritt), :909 (DynamoDBCredentialStore); agents/ecosystem/api_profiles.py:51-57 (_ALLOWED, REVOKED terminal), :104-109 (_is_admin/_is_staff), :217,243; agents/ecosystem/worker_authorization.py:40-78 (is_entitlement_valid), :91 (check_worker_entitlement), :154-186 (Resolver gsi-user); terraform/modules/dynamodb/main.tf (foundation_entitlement); terraform/modules/lambda/main.tf (entitlements-IAM read-only); tests/test_p17_credential_lifecycle.py; tests/test_credential_management_http.py:127,207,301 (bestehende Vertragsbelege); docs/reports/RIS-B3-MACHINE-CREDENTIAL-ENTRYPOINT-IMPLEMENTATION-08-EXECUTION_LOG.md; docs/reports/RIS-ENTITLEMENT-PROVISIONING-FOUNDATION-09-EXECUTION_LOG.md; CloudWatch /aws/lambda/mays-ris-dev-agent (Audit + Secret-Scan)

- Classification: GREEN

- Terraform checks actually executed and their results:
  - `terraform plan` zu Gate-Beginn (read-only) = "No changes."
  - `terraform plan` mit Foundation-Variable = 1 create, 0 IAM; `apply` = 1 added
  - `terraform apply` mit validUntil in der Vergangenheit = 0 added, 1 changed; Restore = 0 added, 1 changed
  - `terraform plan` mit leerer Variable = 1 destroy; `apply` = 0 added, 0 changed, 1 destroyed (Cleanup der Entitlement)
  - `terraform plan` nach Cleanup (Default) = "No changes."
  - KEIN Destroy der Tabelle, KEIN taint, KEIN state rm, KEIN IAM-Manipulation, KEIN Lambda/Gateway/Cognito-Change

- Git Commit / Push: Commit `ebcbabf` (`test(p17): credential lifecycle e2e coverage`); Push `a31abee..ebcbabf main -> main` (Fast-Forward); lokaler HEAD und origin/main identisch `ebcbabfb174c9de23c00cd40ea167ff8d1cce029`; keine Divergenz, kein Force-Push
- Git status: bei Start 0 modified tracked; nach Commit 0 modified tracked (nur die 2 neuen Dateien dieses Gates committed; lambda.zip und .terraform.lock.hcl bewusst nicht)

- Files changed, if any:
  - NEU: tests/test_p17_credential_lifecycle.py
  - NEU: docs/reports/RIS-P17-CREDENTIAL-LIFECYCLE-E2E-10-EXECUTION_LOG.md
  - Kein Python-Laufzeitcode geaendert, kein Terraform geaendert, kein bestehender Test geaendert.
  - NICHT committed: 8 vorbestehende untracked Reports fremder Gates; terraform/.terraform.lock.hcl; lambda.zip

- Explicit confirmation when no files were changed: entfaellt — es wurden zwei neue Dateien hinzugefuegt (eine Testdatei, dieses Log). Am Live-System wurde KEIN Code, KEIN Terraform und KEINE bestehende IAM-/Cognito-/Gateway-/Lambda-Konfiguration geaendert; saemtliche Aenderungen an AWS-Daten gingen ueber die bestehenden Produktpfade bzw. die opt-in Terraform-Entitlement-Variable.

- Open questions:
  - Der Produktweg erlaubt weiterhin, Credentials mit expiresAt in der Vergangenheit auszustellen. Das ist fail-safe (die Verification lehnt sie ab, Audit meldet credential.expired/observed), aber es erzeugt unnoetige Datensaetze. Eine Entscheidung, ob die Ausstellung abgelaufener Credentials abgelehnt werden soll, ist offen und wurde hier bewusst nicht getroffen.
  - GET /v1/apiprofiles/{fremdes Profil}/credentials antwortet 200 mit leerer Liste, waehrend Item- und Profil-Endpunkt 404 liefern. Fail-safe, aber inkonsistent. Eine Vereinheitlichung waere ein APIProfile-Vertrags-Thema und ist in diesem Gate untersagt.
  - Alle terminalen Testdaten (10 Profile, 28 Credentials) bleiben mangels produktivem Delete-Pfad bestehen (Gate 04/05). REVOKED ist inert; fuer eine datensparsame Umgebung waere ein Delete-Pfad die Ursprungsfrage, nicht dieses Gate.
  - 2 work-items dieses Gates sind als Ausfuehrungsbeleg noch vorhanden und laufen nach 30 Tagen ueber TTL weg.

- Risks:
  - Secrets wurden nie geloggt: Log-Scan ueber 553 Zeilen ergab 0 Treffer fuer ris_, Authorization, Bearer, JWT-Muster, password/secret/token und TemporaryPassword; 0 echte ris_-Secrets. Report-Scan ebenfalls sauber. Kein RED, kein HARD STOP noetig.
  - Audit enthaelt credentialId, apiProfileId, tenant, outcome und action, aber kein Secret, keinen Header, kein Token und kein Passwort.
  - Terminale Zustaende wurden per Request wirksam belegt: direkt nach disable/enable/revoke war der jeweils naechste Machine-Aufruf 403 bzw. 202. Es gibt keinen Cache, der einen alten positiven Zustand liefert.
  - Kein Cross-Tenant-Leak: Tenant B sieht 0 fremde Credentials und 0 fremde Profile.
  - IAM unveraendert; die Runtime schreibt weiterhin keine Entitlements.
  - Terraform-Zustand sauber ("No changes."), Plan enthielt ausschliesslich B5-relevante Entitlement-Zeilen.
  - Restbestand: 10 REVOKED Testprofile und 28 REVOKED Credentials ohne Zugriffsrisiko.

- Recommended next actions:
  - P20 NICHT starten.
  - B3, B5 und P17 sind damit gemeinsam live GREEN: Credential-Lifecycle inklusive Ausstellung, Nutzung, Rotation, Disable/Enable, Ablauf, Revoke und Isolation ueber den produktiven Machine-Entry-Point nachgewiesen.
  - Optional als eigenes, unabhaengiges Gate: Verweigerung der Ausstellung bereits abgelaufener Credentials (Fail-safe heute, aber vermeidbarer Datensatz).
  - Optional: Vereinheitlichung der 200/404-Semantik beim Credential-Listing auf fremde Profile.

- Current resume point: Commit + Push, danach HARD STOP

==================================================
