# MO-RIS-AWS-LAMBDA-BRIDGE-01 — Dispatch Ingress & Result Consumer (lokal)

**Datum:** 2026-11-13
**Typ:** Lokale Implementierung + Tests. **Kein AWS-Aufruf, kein Deployment.**
**Ergebnis:** Beide Lambda-Einstiegspunkte existieren und sind über den
vollständigen Referenzauftrag belegt: `17 + 25 = 42`.

## 1. Baseline

| Repo | Branch | HEAD vor |
|---|---|---|
| Orders | `feature/mo-agent-order-body-01` | `3ea30fb` |
| RIS | `feature/ris-mo-addition-agent-e2e-01` | `ada5a1d` |

## 2. L01 — RIS Dispatch-Ingress (`lambda/dispatch_ingress.py`)

Dünner SQS-Einstieg: Record → Transport V1 → verifizierter Kontext →
kanonisches WorkItem → **bestehende** `process_record`-Pipeline.

| Anforderung | Umsetzung |
|---|---|
| Schema/Type prüfen | `validate_envelope(..., expected_type=ORDER_DISPATCH)` |
| Queue-Kontext | `eventSourceARN` muss `DISPATCH_QUEUE_ARN` entsprechen, sonst Ablehnung |
| Identität **nicht** aus der Nachricht | `resolve_context()` liest das APIProfile aus dem Store; `contextRef` wird nur nachgeschlagen |
| Partner/APIProfile/Tenant | `VerifiedContext` aus dem Profil; abweichende Claims → `identity_mismatch` |
| WorkId unverändert | `execution.workId` ist Pflicht; fehlt sie → `missing_work_id` |
| Registry/Eligibility | unverändert (im Pipeline-Pfad) |
| Keine zweite Runtime | `process_record` ist die Worker-Funktion selbst |
| Keine Credentials | WorkItem enthält keine Keys (Test) |

Fehlerverhalten:

| Fall | Verhalten |
|---|---|
| ungültig/fremd/inaktiv/keine WorkId | permanent abgelehnt, konsumiert |
| Infrastrukturfehler | `batchItemFailures` → SQS retry |
| Duplikat | `process_record` erkennt `workId` → keine zweite Ausführung |

## 3. L02 — Orders Result-Consumer (`lambda/src/result_consumer.py`)

Eigene Funktion, gleicher A06-Boundary, Secret aus **Secrets Manager**.

| Punkt | Umsetzung |
|---|---|
| Secret-Bezug | `ORDER_RESULT_SECRET_ARN` → `GetSecretValue`, pro Container gecacht |
| Kein Klartext im Code/State | nur ARN in der Umgebung; Wert nie geloggt/ausgegeben |
| Rotation | Secret `{"current": "...", "previous": "..."}`; beide werden akzeptiert |
| Fehlt/ unlesbar | fail-closed, `reason: secret_reference_missing` / `secret_unavailable` |
| HMAC | vorhandene `verify_signature`, konstanter Vergleich |
| Übernahme | vorhandenes `apply_result` (Idempotenz, Stale, Stornierung unverändert) |

`result_handler` wurde minimal refaktoriert: `process_records(records, secrets,
service=None)`; `handler` bleibt der Env-Variant für Rückwärtskompatibilität.
Bestehende 175+ Tests unverändert grün.

## 4. L04 — Packaging-Befund (wichtig)

`lambda/build_zip.py` der Orders-Seite enthielt eine **fest verdrahtete
Modulliste** mit sieben Dateien. Die seit A04 ergänzten Module
(`identity`, `agent_order`, `result_envelope`, `result_handler`, `dispatch`,
`result_consumer`) wären **nicht** im Deployment-ZIP gelandet — der Fehler wäre
erst beim ersten echten Invoke aufgetreten.

Behoben: automatische Ermittlung aller `src/*.py`. Verifiziert am gebauten ZIP
(13 Module, inkl. `result_consumer.py`).

RIS: `AGENT_FILES` um `lambda/dispatch_ingress.py` erweitert; Bundle enthält
`dispatch_ingress.py` (91 Dateien).

**Nicht** umgesetzt: die Terraform-Ressourcen für die beiden Lambdas, ihre
Rollen und Event-Source-Mappings. Das bleibt der nächste, freigabepflichtige
Schritt — der Plan nennt bisher 8 Ressourcen ohne Lambdas.

## 5. L03/L05 — Tests

| Suite | Ergebnis |
|---|---|
| RIS Ingress (`test_dispatch_ingress_lambda.py`) | **15 passed** |
| RIS Lambda-Bridge-E2E (`test_lambda_bridge_e2e.py`) | **5 passed** |
| RIS Contract-Compat | 9 passed |
| RIS gesamt (gezielt) | **210 passed** |
| Orders gesamt | **205 OK** |

Abgedeckt (Auszug): gültiger Dispatch, gültiges Result, `ORDER_FAILED`, falsche
Version, unbekannter Typ, manipulierte Senderdaten, fremder Tenant, fremdes
APIProfile, ungültige Capability, fehlende/falsche WorkId, Duplikat, stale
Attempt, storniert, fehlende Secret-Referenz, falsche Signatur, transienter
Fehler (`batchItemFailures`), partieller Batch, keine Secrets, keine doppelte
Ausführung.

**L05** führt durch **beide echten Handler**: Orders-Create → Dispatch-Ingress →
AgentBody → `ORDER_RESULT` → Result-Consumer → autorisiertes `GET` liefert 42;
fremder Partner erhält 404; Duplikat ist idempotent; manipulierte Nachricht wird
verworfen.

## 6. Sicherheitsgrenzen

- Senderbehauptung im JSON ist kein Vertrauen: Kontext kommt aus dem Store,
  Queue-Bindung aus der Konfiguration, Ergebnis aus der HMAC-Signatur.
- Keine öffentliche Result-Write-Route.
- Keine Änderung der Retail-Statusmaschine.
- Secret nur als ARN; Wert out-of-band.
- Keine Datenbankzugriffe zwischen den Systemen.

## 7. Bekannte Baseline (unverändert)

Die RIS-Gesamtsuite hat weiterhin **34 vorbestehende Failures** und **4
Collection-Errors** aus Umgebungsgründen (`python3`-Subprozess fehlt auf Windows,
`requests` nicht installiert). Sie betreffen Admin-CLI, Dependency-Tooling,
ATS-Client und Consent-Suiten — keine der hier gebauten Komponenten.

## 8. Status

**LOCAL LAMBDA E2E VERIFIED — NOT DEPLOYED.**

Offen und freigabepflichtig: Terraform-Ressourcen für beide Lambdas (Rollen,
ESM, Handler-Pfade), Secret-Wert, echter Plan gegen `240571105849`.
