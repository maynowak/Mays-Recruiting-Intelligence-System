# Mays-RIS System Architecture (konsolidiert, Stand Gates 0–9)

Status: VERIFIED (Code + Gate-Nachweise G5–G9). Ersetzt Detail-Aussagen aus
`docs/CURRENT-ARCHITECTURE.md` (Stand 2026-09-28, überholt: u. a. „keine
MO-Verbindung", „Persistenz UNWIRED", „TF validate nicht grün") — Historie
bleibt erhalten, diese Datei ist maßgeblich für den aktuellen Stand.

## 1. Systemgrenze

Mays-RIS ist die Agent-Runtime-Plattform (AWS, eu-central-1). Externe
Systemgrenzen (nicht im Eigentum, nur per Contract angebunden):

- Mays-Orders (eigene AWS-Infrastruktur, eigenes Team): Order-Lifecycle,
  erreicht über OrdersPort → RealMaysOrdersAdapter → HTTP. KEIN Zugriff
  auf deren TF/IAM/Lambda/SQS/State.
- Mays-Jobsearch-Frontend (Referenzprojekt, gepinnt): keine Laufzeit-Abhängigkeit.
- Externe ATS-API (Dritt-Deployment): nur vom ATS-Agent genutzt.

## 2. Gesamtbild (live verifiziert)

```text
User → Cognito/JWT → API-GW (mays-ris-dev-api, 9 Routen, JWT ausser /health)
       ├── /platform /me /me/profile /agents /health → agent-Lambda
       └── /orders, /orders/{id}, PATCH …/status, POST /orders → orders-reader-Lambda
API → WorkItem → Shared Work Queue (mays-ris-dev-work-queue)
      → DLQ nach 3 Empfängen (mays-ris-dev-dlq, bestehend)
      → Worker (mays-ris-dev-agent, Mapping Batch 5, Enabled)
      → Agent Ecosystem (Registry/Discovery/Eligibility/Selection)
      → Agent Body (Context/Router/Executor/Invoker/Result)
      → Domain Agents: reference | ats | jobsearch | orders-function | dummy-a/b (DEV)
      → DynamoDB (work-items, jobsearches, user-profile, agent-catalog,
         entitlements, agent-state) → Result/Status
Installer: project_name-Isolation, S3-Backend + Workspace, Git-SHA-Pinning
  (mays-orders@9c61237, mays_jobsearch@3cd58b81, je verifiziert)
```

## 3. Begriffstrennung (verbindlich)

| Begriff | Bedeutung | Identität |
|---|---|---|
| API Request | synchroner HTTP-Aufruf | Request/Response-Paar |
| WorkItem | konkrete Arbeit (workId/type/tenantId/idempotencyKey Pflicht) | workId |
| Queue Event / Activation | „Arbeit kann starten" (SQS-Nachricht = READY-Signal) | messageId |
| Agent Run | fachliche Ausführung eines WorkItems | workId + attempt_no |
| Execution | einzelne Agenten-Ausführung im Body | execution_id |
| Attempt | Wiederholung desselben Schritts (nicht neuer Auftrag) | attempt_no + attempt_id |
| Business Order | fachliche Bestellung in Mays-Orders | orderId (`ord_*`) |
| Result | Body-Ergebnis + `result_reference=work:<id>:attempt:<n>` | Referenz |

Es gilt: Event ≠ WorkItem ≠ Agent Run ≠ Attempt ≠ Business Order.

## 4. Komponenten (Verantwortung → Details in RUNTIME-PATH.md)

- Identity: Cognito User Pool (`users`), JWT-Authorizer (Audience=Client, Issuer=https-Endpoint); Claims `sub`, `email`, `preferred_username`/`cognito:username`, `cognito:groups`, `custom:tenant_id`.
  Hauptweg (immer): User → Cognito (E-Mail + Passwort) → Cognito JWT → API-Gateway → RIS.
  Optional (Gate 13A, Standard AUS): User → Cognito → Google Federation → Cognito JWT → API-Gateway → RIS.
  Google ist ein optionaler externer Identity Provider, der über Cognito Federation angebunden wird — KEIN separates Backend-Auth-System, KEIN neuer Haupt-IdP. Cognito bleibt die zentrale Identity-/Token-Grenze; das Backend arbeitet weiterhin nur mit Cognito JWTs.
  Registrierung: SignUp → Confirm → Login → POST /me/profile (explizit, Conditional) — nie via Read (Gate 10). Self-Signup erlaubt; E-Mail-Verifikation per Cognito konfiguriert (Gate 11: auto_verified email + Template, Versand AWS-managed; Inbox-Nachweis OPEN).
  Profile Boundary (Gate 12 + 13A): Identity ≠ Application Profile. UserProfile `{userId=sub, tenantId, nickname, firstName, lastName, email, status, createdAt, updatedAt}` — ein Google-Federation-Login erzeugt KEIN Profil (GET /me/profile → 404 bis expliziter Initialisierung). Google-Attribute (email/given_name/family_name/name) duerfen hoechstens initiale Profilwerte liefern (firstName/lastName sind bereits v1-Felder — keine neuen Felder), niemals Wahrheit noch Ersatz des Profils.
  Federation-Status: YELLOW — Foundation konfiguriert (TF-optional, Mapping, Code-Flow), aber live federation has not yet been verified (kein IdP, kein Test-Account).
  Linking-Vertrag (nur Definition, Gate 13A aktiviert NICHTS): Automatic account linking by email is not implemented. Google account linking is prepared but not activated in Gate 13A. Spaeter NUR explizit durch bereits authentifizierten User (OAuth-Abschluss nach Identitaetsnachweis); keine Auto-Zusammenfuehrung (weder E-Mail noch Name noch Attribut), kein implizites Merge, kein Profiltransfer.
- API: 9 Routen (5 Plattform + 4 Orders), Payload v2, AutoDeploy `$default`.
- Queue: 1 verdrahtete Work-Queue (Visibility 300s) + DLQ; ats/cv/match-Queues definiert-ungenutzt (Bestand, kein Scope).
- Worker: SQS-Records → WorkItem-Validierung → Pipeline (Envelope→Discovery→Eligibility→Selection→Engine→Body); Fehler → Raise → Redelivery (Attempt+1); Duplikat → kein neuer Run.
- Ecosystem: Registry (Descriptoren), Discovery (Capability/AgentId, ACTIVE), Eligibility-Pipeline, Selection (first_match), ExecutionEngine (identitätserhaltend).
- Agents: reference.echo (Echo), ats-agent/analyze.job (externe API, urllib-Fallback), jobsearch-agent (create/get/list, Repository, Tenant-isoliert), orders_function (Port-Delegation), dummy-a/b (DEV/TEST ONLY).
- Persistence: DDB PAY_PER_REQUEST; JobSearch-Tabelle (Hash jobSearchId, GSI gsi-user/gsi-status, TTL expiresAt).
- OrdersPort: `submit_order/get_order_status/can_handle`; Development-Adapter (lokal) + Real-Adapter (HTTP, Fehlerklassen Transient/kontrolliert, POST nie blind retrybar).
- Observability (Foundation, Gate OBS-01): CloudTrail (`mays-ris-trail`, multi-region, Logging, eigener S3 `mays-ris-cloudtrail-<account>` mit PAB+SSE — strikt getrennt vom TF-State) = AWS-/Account-Audit; CloudWatch (`mays-ris-overview`-Dashboard mit echten System-/Queue-/Error-Widgets + 7 Alarme inkl. DLQ, Log-Gruppen) = Runtime-Monitoring. project_name-Namen, keine Fake-Metriken, Extensions nur mit Vertrag.
- Installer: `package/validate/plan/apply/preflight/install/state/destroy`; Backend `mays-ris-tf-state-dev` + Lock `mays-ris-tf-lock`; Workspace = project_name; Lambda-Bundles deterministisch per `package`-Befehl (Vertrag: package → plan → apply; Full-Plan braucht `terraform/lambda.zip`, CI erstellt keins — OPEN).

## 5. Tenant Isolation / Security

JWT-Tenant (`custom:tenant_id`) + Code-Guards (Repository get/list filtern userId/tenantId; get prüft Besitz). IAM Least-Privilege pro Funktion (nur eigene Tabellen/Queues + Logs). Keine Secrets im Repo (Env-Muster; Temp-Credentials per Shred entsorgt). Bekannte OPENs: SQS-`*`-Policy + fehlende DLQ auf Mays-Orders-Seite (fremd, dokumentiert); kein serverseitiger MO-Idempotency-Key (Retry-Regel dagegen).

## 6. Status je Bereich (implemented / verified / prepared / open)

- implemented+verified: Runtime-Pfad, Idempotency/Retry/DLQ-Nutzung, Orders-Integration (eigener Pfad), ATS/JobSearch/Reference/Dummy-Auswahl, Installer-Pinning, Tabellen/Queues/Mapping, Observability-Foundation (Trail/Dashboard/Alarme live).
- prepared: JobSearch update/delete (Repository kann, Agent bietet nur create/get/list), ATS-Vertiefung, ats/cv/match-Queues.
- open: POST-Reconciliation nach Timeout, MO-Idempotency-Key, CI-ohne-Package (bekannt, nicht umgebaut), 5 pre-existing Test-Defekte, OpenAPI-Abdeckung Plattform-Routen (s. API-Standard).

## 7. Dokumenten-Verantwortung

- Diese Datei: Gesamtbild + Begriffe (maßgeblich).
- `RUNTIME-PATH.md`: Detail je Stufe. `../api/API-STANDARD.md`: HTTP-Regeln.
- `../roadmap/ROADMAP.md`: Fortschritt/Zukunft. Gate-Reports: Nachweise.
- Ältere Architektur-Docs (CURRENT-ARCHITECTURE.md u. a.): Historie, im Zweifel gilt diese Datei + Code.
