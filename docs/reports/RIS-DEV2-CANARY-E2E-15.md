# RIS-DEV2-CANARY-E2E-15

**Datum:** 2026-11-26
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `dbb4a79f721361c592dc9f87187446eacb1fa979`
**AWS:** `262370457690` / `eu-central-1` / `ris-dev2`
**Status:** **BLOCKED — PARTIALLY VERIFIED**
(Order + fail-closed Dispatch korrekt; E2E erneut an einer ConditionCheck-Validierung blockiert.)

## 1. Preflight (PASS)

- STS/Region/Installation korrekt; State Serial **74**, Lineage unverändert.
- Fix-13A live: agent/dispatch `cb88nW8g…`, analysis `ezyObh3l…`, `Successful`.
- Ingress-IAM enthält `ConditionCheckItem`; `MODE=true`; Identität/Ablauf korrekt.
- Profil ACTIVE, Partner-Bindung korrekt, Offer `off_4b4f…` ACTIVE, Entitlement gültig.
- Alte Order `PENDING`, altes WorkItem bare, Work-DLQ 1 — unangetastet.

## 2. Neue Order (genau eine)

| Feld | Wert |
| --- | --- |
| OrderId | `ord_a566f415ef9d77720cd97cd4` |
| WorkId | `work-2c26e835ee8fee7c` |
| CorrelationId | `corr-canary-07-02` |
| IdempotencyKey | `canary-07-job-tags-02` |
| Create | HTTP **201**, Status `PENDING` |
| Dispatch | `SENT`, messageId `msg_work-2c26e835ee8fee7c_order_dispatch` |

## 3. E2E-Verlauf

| Schritt | Ergebnis |
| --- | --- |
| Order angenommen | ja (201) |
| ORDER_DISPATCH | zugestellt; Dispatch-Queue 1 in-flight |
| WorkItem | **keines** persistiert (`0` Zeilen) |
| Worker / Analysis | nicht aufgerufen |
| ORDER_RESULT / Consumer | nicht erreicht |
| Owner-GET | HTTP 200, aber `PENDING`, `processing=null` |
| Fail-closed-Fix | **wirkt**: `WorkEnqueueError`, kein SQS-Send, kein Marker-Update, keine bare Zeile |

### Sichere Cancellation-Codes (CloudWatch)

```text
work item transaction cancelled:
[{"code": "ValidationError", "index": 0}, {"code": "None", "index": 1}]
work item not enqueued: existing row missing
WorkEnqueueError: existing work item is not reusable: missing
```

Index 0 ist die **ConditionCheck**-Operation (Fence-Key), Index 1 der nicht
ausgewertete Put. Der Fehler ist **kein** IAM-Problem und **keine** Fence-Blockade.

## 4. Einordnung (ohne Spekulation)

- Tabellen-Schlüssel ist `workId` (String, Hash-only); Fence-Key ist ein
  78-Byte-String, kein Fence-Row vorhanden.
- Der Put-Item-Entwurf ist gültig (1 390 Bytes, keine leeren/ungültigen Typen;
  `parentWorkId` ist NULL).
- AWS meldet für die **ConditionCheck** einen `ValidationError`, obwohl Key und
  Bedingung (`attribute_not_exists(workId)`) dem Schema entsprechen.
- Die konkrete AWS-`Message` wurde bewusst **nicht** geloggt (Vorgabe: nur
  sichere Codes). Eine weitere Diagnose oder ein Fix würde einen neuen,
  gesondert freigegebenen Schritt erfordern.

## 5. AWS-Zustand (Snapshot 09:00:05Z)

| Prüfung | Ergebnis |
| --- | --- |
| Neue Order | `PENDING`, Dispatch `SENT`, kein Processing |
| Neues WorkItem | 0 |
| Dispatch-Queue / DLQ | 0 / 0 (1 in-flight) |
| Work-Queue / DLQ | 0 / 1 (alte Nachricht unverändert) |
| Alte Order / WorkItem | `PENDING` / weiterhin nur `workId` + `enqueuedAt` |
| State / S3 | Serial **74** / `d24K7fWh…`, unverändert |
| Synthetic-Modus | `true`, Ablauf 2026-11-26T17:40:28Z |

## 6. Grenzen eingehalten

Genau eine neue Order; kein zweiter Versuch. Kein Redrive, keine
Datenkorrektur, kein Cleanup, kein Terraform-Apply, kein neuer Grant, kein
Main-Merge. Nach der Order-Erstellung nur read-only Beobachtung; die
automatischen SQS-Retries des Dispatch-Ingress laufen ohne Eingriff.

## 7. Entscheidung

**BLOCKED — PARTIALLY VERIFIED.** Order-Annahme und fail-closed-Verhalten sind
belegt; der E2E scheitert erneut an der ConditionCheck-Validierung. Ohne einen
separat freigegebenen Diagnose-/Fix-Schritt (z. B. sichere Erfassung der
AWS-`Message` oder gezielte Prüfung der ConditionCheck-Struktur) ist kein
vollständiger Lauf möglich.
