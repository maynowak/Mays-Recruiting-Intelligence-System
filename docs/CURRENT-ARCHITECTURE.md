# Mays-RIS – Current Architecture & Development Status

> Stand: 2026-09-28 (HEAD f71d40f, Commit folgt). Resume-/Context-Quelle für
> weitere Entwicklung OHNE Chat-Archäologie. NUR belegter Ist-Stand (keine
> Zielarchitektur als implementiert). Muster: AI_AUDITLOG-Mandatory-Felder.

## 1. Current Product Boundary

API-Plattform (PROVEN): Cognito/JWT → API-GW (5 Routen) → `agent`-Lambda →
DynamoDB/SQS → AgentBody → Agents. Domänen: Profile/Katalog/Entitlements/Work
(verdrahtet), JobSearch (PARTIAL), ATS (PREPARED), CV (Vorgabe). Consumer:
Web-App per Vorgabe + Frontend-Vertrag (kein Frontend im Repo).

## 2. Current System Architecture

```text
User → Cognito → GW (JWT, 4/5 Routen) → agent Lambda ──READ→ 3 Tabellen
                                                    ├──WRITE→ work-items ──SEND→ work-queue ──► agent Lambda ──► AgentBody/Router/Registry ──► Agents
                                                    └── JobSearch-CRUD ──► (Tabelle offen)
```

EINE Lambda (API+Worker), 5 GW-Routen, 4 Tabellen (+JobSearch-offen), 5 Queues
(1 verdrahtet), Cognito-Pool/Client/3 Groups/Domain. KEIN EventBridge/SNS,
KEINE 2. Lambda, KEINE MO-Verbindung.

## 3. Identity / Registration / User Profile

Cognito-Pool `users` (Policy 8/upper/lower/number; custom:tenant_id; KEINE
explizite Signup-Config im Code → Registrierungs-Weg UNKNOWN); KEINE
Signup-/Login-Route im Repo (Login außerhalb: Cognito-Hosted-UI/Client);
JWT → Authorizer → Claims (sub/email/tenant/groups); `/me` (Echo),
`/me/profile` (DynamoDB-Get + Tenant-Check). KEINE Website/Frontend-Page
im Repo (Sibling-Dirs, nicht untersucht).

## 4. Platform API

GW-Routen: health(NONE)/platform/me/me-profile/agents (JWT). Handler-Super-Set
(Execute/JobSearch/Work NUR intern). v2-vs-REST-BRUCH (statisch PROVEN, live
UNVERIFIED). Spec: NUR JobSearch-Vertrag (keine Platform-Spec).

## 5. Agent Platform

Registry (populiert) / Descriptor / Router / Discovery+Eligibility (Framework,
kein Prod-Pfad) / Invoker+Contract (ungenutzt) / Chain (Templates) / Reference
(registriert) / Katalog-Adapter (DynamoDB).

## 6. Agent Body / Runtime

Body→Executor→Router→Handler + Context/Result/Monitor; InvocationContract für
Agent-zu-Agent (ungenutzter Pfad); Harness: tests/test_agent_body.py.
Resume Point (NICHT als erledigt dargestellt): **Worker → Agent Body**
(SQS-Mapping → Records-Parse → `AGENT_BODY.execute`) — Mapping (batch 5)
PROVEN, Receive-Regel-LÜCKE offen.

## 7. SQS / Worker

work-queue (+DLQ, SSE, redrive 3, Visibility 300s) VERDRAHTET; cv/ats/match
DEFINIERT-UNGENUTZT; KEIN function_response/window/Filter. SQS-WIP: KEINS im
Tree (Status-Beleg, nichts angefasst).

## 8. JobSearch / CV / ATS

JobSearch: Paket/Spec/CRUD PROVEN, Persistenz UNWIRED (keine Tabelle/Env/IAM).
CV: NUR Vorgabe + Queue-Name (kein Code). ATS: Paket + Tests + Reg-Funktion
(PREPARED), Prod-Caller + URL offen; externer ATS-HTTP-Client (unverdrahtet).

## 9. Mays-Orders Integration Boundary

Definiert (unverändert): Runtime → OrdersPort → DevelopmentOrdersAdapter →
(später) RealMaysOrdersAdapter → Mays-Orders-AWS. TECHNSICHER Connector:
NICHT vorhanden (kein Prod-Caller; Real-Adapter nur Doku-Muster mit
Platzhalter). KEIN Order/Event/Lambda/SQS-Pfad belegt. KEINE Erfindung.

## 10. AWS / Terraform / Infrastructure

TF-Root partiell (Backend-Literale; Bucket/Region per `-backend-config`
offen); Duplikate/Contracts schichtweise repariert (Roadmap s. Reports);
validate NICHT grün (Modul-/Var-Reste + fehlendes init); Runner/BackendConfig
bereit, UNGENUTZT (kein Caller; CI direkt ohne CWD); KEIN init/State/Migration.
Owner UNKNOWN (eigener Account DECIDED, ID offen); Live dev-Tripel ABSENT.

## 11. Proven / Partial / Prepared / Contract / Open

PROVEN: Auth-Kette, 4 Tabellen-Wege, Work-Pfad, Body/Router/Registry,
GW-Routen/Integration, JobSearch-CRUD-Code. PARTIAL: JobSearch-Persistenz,
ATS-Laufzeit, GW-v2-Verdrahtung. PREPARED: Framework, ATS-Paket, 4 Queues,
Runner/BackendConfig. CONTRACT: JobSearch-Spec, OrdersPort/Adapter,
Frontend-Vertrag. OPEN: R20, agent_state, PITR, Client-Attribute, Laufzeit,
Owner/Live/CWD/Integration, v2-Wirkung, GW-Anbindung, Receive-Regel.

## 12. Current Runtime Resume Point

**SQS work-queue → Mapping (batch 5) → `_handle_sqs_event` (Records-Parse) →
`_process_work_item` → `AGENT_BODY.execute` → Executor/Router → Agent.**
(NICHT als erledigt dargestellt: Receive-Regel fehlt; v2-Dispatch betrifft
API-Pfad, nicht Worker.)

## 13. First User-Facing Vertical Slice

Registration (FEHLT: kein Weg im Repo) → Login (AUSSERHALB: Cognito) → JWT
(PROVEN) → `/me` (PROVEN) → `/me/profile` (PROVEN: Get + Tenant-Check) →
DynamoDB-Profil (PROVEN: Tabelle+IAM+Env) → Name+E-Mail (PROVEN: Claims/Item)
→ Frontend-Page (FEHLT: nicht im Repo). Kleinster realer Slice HEUTE:
Cognito-Nutzer (extern angelegt) → JWT → /me → /me/profile. NICHT nötig dafür:
Agenten/Queues/MO/CI-Änderungen/TF-Repairs (außer laufende Gates).

## 14. Next Development Gates (unentschieden, nur benannt)

Registrierungs-Weg (Owner) · v2-Vertrag (A/B/C) · GW-Anbindung Execute ·
JobSearch-Persistenz (Owner) · Receive-Regel · ATS-Produktivierung ·
Backend-Owner/Live/Integration · S3-Schicksal · Laufzeit-Belege.

---

*Baseline: RIS-CURRENT-ARCHITECTURE-BASELINE-10 · Stand heute, kein Zielbild ·
Resume-fähig.*
