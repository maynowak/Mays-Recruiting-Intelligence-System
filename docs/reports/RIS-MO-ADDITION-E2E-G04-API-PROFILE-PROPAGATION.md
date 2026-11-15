# RIS-MO-ADDITION-E2E-G04 — Verified APIProfile Propagation

**Datum:** 2026-11-13
**Typ:** Lokale Implementierung + Tests (keine AWS-Mutation, kein Deployment)
**Ergebnis:** COMPLETE. Die beim RIS-Eingang verifizierte `apiProfileId` erreicht
den Execution-Time-Check des Workers.

## 1. Git

| Feld | Wert |
|---|---|
| Branch | `feature/ris-mo-addition-agent-e2e-01` |
| Parent | `962bf66` (Transport V1) |
| Remote vor Start | `962bf66` (identisch) |

## 2. Ausgangsbefund (verifiziert, nicht angenommen)

Alle drei `_enqueue_agent_work`-Aufrufstellen übergaben **keine** `apiProfileId`:

| Aufrufstelle | Kontext vorhanden | übergeben |
|---|---|---|
| `_partner_execute_agent` | `context["apiProfileId"] = meta.get(...)` | ✗ |
| `_machine_execute_agent` | `context["apiProfileId"]` aus `verify_api_credential` | ✗ |
| `_execute_agent` (human) | `user_context` (kein Profil) | ✗ |

Der Worker las dagegen bereits `work.get("apiProfileId")` und reichte es als
`api_profile_id` an `check_worker_entitlement()` weiter — bekam aber immer `None`.
Damit war die Profilbindung an der Ausführungsgrenze faktisch abgeschaltet.

## 3. Änderungen

| Datei | Änderung |
|---|---|
| `agents/runtime/work_item.py` | `api_profile_id`, `partner_application_id`, `issuer` als First-Class-Parameter (weiterhin **eine** Baufunktion) |
| `lambda/handler.py` | `_enqueue_agent_work(..., api_profile_id=None)`; alle drei Aufrufstellen übergeben den verifizierten Wert |
| `agents/transport/order_transport.py` | nutzt die neuen Parameter statt `extra` (identische Ausgabe) |
| `agents/runtime/pipeline.py` | Fail-closed-Guard: partner-spezifisches WorkItem ohne `apiProfileId` wird abgelehnt |
| `agents/addition_agent/agent.py` | Payload-Auflösung für beide realen Einstiegspfade (siehe §5) |

Keine zweite WorkItem-Baufunktion, keine neue Autorisierung, keine Änderung an
Mays-Orders, kein neues Berechtigungssystem.

## 4. Sicherheitsverhalten

| Regel | Umsetzung |
|---|---|
| Profil nur aus verifiziertem Kontext | Wert kommt aus `verify_api_credential` / Credential-Meta, nie aus Body oder Header |
| Kein Fallback auf user-wide bei Partner-Aufträgen | Guard: `partnerApplicationId` gesetzt **und** `apiProfileId` leer → Ablehnung |
| User-wide bleibt erhalten | Human-Pfad hat kein Partner-Feld → `apiProfileId=""` → bisherige Semantik |
| Fremdes Profil | `check_worker_entitlement` → `profile-mismatch` → DENIED |
| Zwischen Enqueue und Ausführung entzogen | Resolver liefert keine Zeile → DENIED, kein Retry-Loop |
| Keine Secrets | WorkItem/Message enthalten weder `ris_` noch `X-Api-Credential` (getestet) |

Der Guard greift **vor** dem Entitlement-Check: selbst eine user-wide-Zeile, die
sonst autorisieren würde, kann einen partner-spezifischen Auftrag ohne
Profilbindung nicht durchlassen.

## 5. Befund: Pipeline verschachtelt die Agent-Payload

Beim End-to-End-Test über `process_record` schlug der Addition-Agent mit
`Field 'left' must be a finite number` fehl, obwohl die Nutzlast korrekt war.

Ursache: `ExecutionEngine.execute_from_decision` baut den `InvocationContract`
mit `payload=processing_envelope.input`. `envelope.input` ist aber das
**gesamte WorkItem** (so legt `_to_event` es an). Der Agent erhält daher
`work_item["payload"]["payload"]["left"]` statt `work_item["payload"]["left"]`.

Das ist bestehendes Runtime-Verhalten, nicht durch G04 entstanden. Ich habe es
**nicht** global geändert (das würde die Eingabe jedes Agents verändern),
sondern der Addition-Agent akzeptiert beide Formen — nur wenn das verschachtelte
Objekt tatsächlich wie ein WorkItem aussieht. Andere Agenten bleiben unberührt.

Empfehlung für ein separates Gate: `InvocationContract` auf die fachliche
Payload zu stellen und die Abhängigkeit der Eligibility von `envelope.input`
(voller WorkItem) sauber aufzulösen. Das ist eine Runtime-Änderung und gehört
nicht in G04.

## 6. Tests

`tests/test_api_profile_propagation.py` — **14 passed**

| Bereich | Nachweis |
|---|---|
| M2M-Eingang | verifiziertes Profil erreicht `_enqueue_agent_work`; Wert stammt aus dem Credential, nicht aus dem Body |
| Fremde Bindung | 403, nichts eingereiht |
| Unautorisierter Aufruf | 401, nichts eingereiht |
| Persistenz == SQS | dieselbe `apiProfileId`, `partnerApplicationId`, `issuer`; Body und DDB-Item feldgleich |
| Kein Profil | wird zu `""`, nichts erfunden |
| Keine Secrets | weder persistiert noch gesendet |
| Worker | profilgebundene Berechtigung → `COMPLETED`, `42` |
| Fremdes Profil | `profile-mismatch`, `DEAD_LETTER` |
| Partner ohne Profil | `api-profile-binding-missing`, `DEAD_LETTER`, keine Ausführung |
| User-wide | weiterhin autorisiert |
| Entzug vor Ausführung | DENIED, kein Ergebnis |
| Spy | `check_worker_entitlement` erhält `api_profile_id="profile-a"` |

Regression: **253 passed, 11 subtests** über Transport-V1 (53), Addition-Agent,
G01-Demo, G02-Matrix, Worker-Recheck, p21, Machine-Entrypoint, Routing, Pipeline,
Entitlement-Provisioning.

## 7. Diff-/Scope-Prüfung

- `git diff --check` sauber, `py_compile` für alle geänderten Module grün.
- Nur fünf Produktdateien + eine Testdatei geändert/angelegt.
- Keine Berührung von Terraform, Orders, Queues, Cognito, CloudFront.

## 8. Status

| Gate | Status |
|---|---|
| G04 | **COMPLETE** (Propagation + Enforcement, lokal verifiziert) |
| T06 | PARTIAL (unverändert) |
| G05 | **BLOCKED** — B1/B3 |
| G07 | **BLOCKED** — B3/B4 |

Es wurde nichts deployt und nichts an Mays-Orders gesendet.
