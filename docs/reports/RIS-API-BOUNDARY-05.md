# RIS-API-BOUNDARY-05

STATUS: YELLOW

- Date/Time: 2026-09-28 10:05 UTC
- Branch + HEAD: main, b00d0ad (Vorgänger 5b8338a intakt)
- Scope: Platform→JobSearch-Grenze read-only (Muster aus AI_AUDITLOG.md). Kein Umbau/Repair/Migration, keine Spec-/GW-/Lambda-/TF-Änderung
- Sections: Kapsel-Inventar → Route-Trace → OpenAPI-Grenze → Call-Graph → Intern/Extern → Lambda/GW/Data/IAM → Historie → Hypothese
- Findings: s. Conclusion (nur Belegtes)
- Evidence: jobsearch/*.py (alle gelesen/grepppt), handler.py:196-216/853-1100, TF (Tabellen/IAM/Env), 849ae1a/d6ccd09 (show), Grep-Leeren (Client-Nutzung/Codegen/TF-Tabelle/IAM)
- Classification: YELLOW
- Terraform Checks: KEINE (reine Code-Analyse)
- Git Status: 0 modified, 8 untracked (unberührt); AI_AUDITLOG Template-only
- Files Changed: nur Report + Execution-Log
- Open Questions: s. unten
- Risks: Keine durch Analyse
- Next Actions: Review; KEINE Folgeschritte ohne Review
- Resume Point: Analyse committet (s. Commit)

## Objective

Ist `/me/jobsearches*` die bestehende Platform→JobSearch-Domain-Grenze, und wie ist sie technisch realisiert? (Read-only.)

## JobSearch Component Inventory

| Komponente | Datei | Verantwortung (belegt) | Status |
|---|---|---|---|
| Domain-Modelle | domain_models.py, models.py | JobSearch-Objekt, Status | ACTIVE (Tests) |
| Repository | repository.py | DynamoDB-Persistenz (boto3, lazy, tenant-scoped CRUD) | ACTIVE (Code), Persistence-Env UNWIRED |
| Source-Interface | source_interface.py | Pluggable Quellen-Protokoll | ACTIVE (Definition) |
| Client | client.py (aiohttp, localhost:8000-Default) | HTTP-Client | UNGENUTZT (0 Aufrufer in lambda/agents) |
| Reference Actor | reference_actor.py | Mock-Daten-Implementierung | UNGENUTZT (Produktionspfad) |
| Apify-Adapter | apify_adapter.py | Externe Actor-Anbindung | UNGENUTZT (Produktionspfad) |
| Schemas | schemas/ + request_schema.json | Validierung | ACTIVE (Definition) |
| OpenAPI | openapi.yaml (3.1.0) | Vertrag (localhost) | ACTIVE (Vertrag), laufzeit UNGENUTZT |

Öffentlich: Repository-CRUD + Domain-Modelle (vom Handler genutzt). Intern: Rest.

## `/me/jobsearches*` Route Trace

GET/POST/PUT/DELETE (handler.py:196-216 → `_handle_jobsearch_*` 853-1100):
`_extract_user_context` (401) → `from jobsearch.repository import
JobSearchRepository` (LAZY, pro Call) → `repo.<crud>(userId, tenantId)` →
200/500. Kette: API (GW: KEINE Route!) → agent-Lambda → Handler → Repository →
DynamoDB (table None ohne Env — s. Data). KEIN Service-Layer dazwischen, KEIN
Client/Adapter/Queue/Lambda-Call.

## Platform → JobSearch Call Graph

Einziger Caller: `lambda/handler.py` (5 Handler-Funktionen) → Interface:
`JobSearchRepository`-Klasse (direkt, lazy import) → Implementation: boto3-
DynamoDB → Data Source: Tabelle aus `JOBSEARCH_TABLE`-Env (UNGESETZT →
None). KEIN HTTP (Client ungenutzt), KEIN SQS, KEIN Lambda-Invoke, KEINE Factory/
DI, KEINE URLs/ARNs/Env (außer gelesenem, ungesetztem Env).

## OpenAPI Boundary

Operationen: searchJobs/getJob/listSources (+ Schemas). Implementiert davon
im Handler: KEINE (Pfade `/v1/*` ≠ Handler `/me/jobsearches*`). Client aus
Spec: vorhanden (client.py) — vom Platform-Code NICHT verwendet (Grep leer).
Laufzeit-Bedarf: NEIN. Tests gegen Spec: KEINE. Codegenerierung: KEINE.
Adapter Spec↔Domain: KEINER. OpenAPI = reine Vertragsbeschreibung (PROVEN).

## Lambda Boundary

JobSearch Lambda: NOT FOUND (keine TF-Ressource, kein Handler, kein Mapping,
kein Invoke — Greps leer). Einzige Lambda bleibt `agent`.

## API Gateway Boundary

| Route | Handler | Gateway | OpenAPI | Implementierung |
|---|---|---|---|---|
| /me/jobsearches* | JA (CRUD) | NEIN (keine Route) | NEIN (`/v1/*` ≠) | Handler-intern, extern NICHT erreichbar |
| /v1/jobs/* | NEIN | NEIN | JA (Vertrag) | Nur Vertrag + ungenutzter Client |

Nur intern existent; extern erreichbar: KEINE (GW fehlt); nur dokumentiert:
`/v1/*` (Vertrag ohne Implementierung).

## Data Boundary

Komponente → Ressource: Repository → DynamoDB-Tabelle AUS `JOBSEARCH_TABLE`
(ungesetzt → None; Handler übergibt nichts). KEINE TF-Tabelle
(`jobsearch-job_searches` nur als Doku-Dict in `create_jobsearch_table_definitions`,
nicht in TF). KEIN S3/RDS/File. Memory/Mock: NUR Tests/Reference-Actor.
Tenant-Isolation: im Repository-Code (userId/tenantId-Parameter) — ohne Tabelle
laufzeit-unwirksam (Befund, keine Wertung).

## IAM Boundary

agent-Lambda-Policies: user-profile/agent-catalog/entitlements/work-items —
KEINE JobSearch-Abdeckung (Grep leer). Env: KEIN `JOBSEARCH_TABLE` in Lambda-
Config. Berechtigung im Codepfad benötigt (put/get bei gesetzter Tabelle),
aber NICHT vorhanden — Befund (keine Hinzufügung hier).

## Historical Integration

JobSearch d6ccd09 (Paket + Spec + Client, "contract") → Handler-CRUD 849ae1a
(+ Repo + Doku + Tests, 9 Tage später). NIEMALS: eigene Lambda, HTTP-Grenze,
GW-Kopplung, Codegen, Spec↔Handler-Tests. Integration UNVERÄNDERT seit 849ae1a
(keine spätere Änderung belegt).

## Route Matrix

| Route | Handler | Gateway | OpenAPI | Implementierung |
|---|---|---|---|---|
| GET/POST/PUT/DELETE /me/jobsearches* | JA | NEIN | NEIN | Handler→Repo (Env offen) |

## Architecture Hypothesis

| Beziehung | Ergebnis | Evidenz |
|---|---|---|
| Handler → Repository (direkt) | PROVEN | Lazy-Imports + CRUD-Calls |
| Repository → DynamoDB | PROVEN (Code) / UNWIRED (Env/TF/IAM) | table-None-Pfad + Leeren |
| Handler → Client/Adapter/HTTP | NOT PROVEN (0 Aufrufer) | Grep-Leere |
| OpenAPI → Implementierung | NOT PROVEN (Pfade disjunkt) | Pfad-Vergleich |
| Eigene JobSearch-Lambda | NOT FOUND | TF/Handler/Mapping-Leere |
| Kapsel (Paket/Spec/Client) | PROVEN (als Artefakt) | Verzeichnis + Commits |

## Proven Architecture

```text
[GW: KEINE Route]
        │
        ▼ (nur Handler-intern erreichbar)
agent Lambda (handler.py)
        │ 401-Gate (JWT)
        ▼ lazy Python-Import
JobSearchRepository ── tenant-scoped CRUD ──▶ DynamoDB (table=None ohne Env)
        │
   (Client/Adapter/Reference: vorhanden, UNGENUTZT)
[openapi.yaml: Vertrag ohne Implementierung]
```

## Open Questions

Tabelle/Env/IAM für Repository-Persistenz (Owner); Client-Zukunft (toter Code?);
Spec-vs-CRUD-Divergenz (Absicht UNKNOWN); GW-Anbindung (Absicht UNKNOWN).

## Conclusion

1. Ja — eigene Kapsel (Artefakt-belegt). 2. Ja — OpenAPI ist ihr Vertrag (laufzeit-ungenutzt). 3. Ja — `/me/jobsearches*` ist die EINZIGE Platform→JobSearch-Grenze (einziger Caller-Pfad). 4. INTERN (A): Python-Funktionsaufruf, kein HTTP/Queue/Lambda. 5. KEINE eigene Lambda (NOT FOUND). 6. KEINE dedizierte AWS-Ressource (keine Tabelle/IAM/Env). 7. KEINE JobSearch-IAM vorhanden. 8. Application Profile braucht: Domäne/Repo/Spec (vorhanden) + Persistenz-Verdrahtung (offen: Tabelle/Env/IAM) + GW-Anbindung (offen) + Client-Schicksal (offen).

---

*Analyse: RIS-API-BOUNDARY-05 · Muster aus AI_AUDITLOG.md · nur Nachgewiesenes ·
Antwort (A) INTERN, Antwort (D) für nichts · keine Architekturentscheidung.*
