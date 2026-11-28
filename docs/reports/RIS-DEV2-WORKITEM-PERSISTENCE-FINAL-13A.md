# RIS-DEV2-WORKITEM-PERSISTENCE-FINAL-13A

**Datum:** 2026-11-26
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `b693c959b03d278c213d413c7d3416c960f99c29`
**AWS:** `262370457690` / `eu-central-1` / `ris-dev2`
**Status:** **READY FOR PERSISTENCE FIX APPLY APPROVAL**
**Modus:** Codehärtung + Tests + neuer Plan; keine AWS-Writes, kein Apply

## 1. Härtung (Commit `8eb18fc`)

`_reuse_problem()` prüft jetzt zusätzlich:

- **Payload-Gleichheit** (strukturell, inkl. verschachtelter Werte),
- **gleichen `idempotencyKey`**,
- **`apiProfileId`** und **`type`** in der WorkItem-Bindung.

`enqueue_work_item` lehnt ein Request-Item ohne Dict-`payload` oder ohne
`idempotencyKey` bereits vor jeder Persistenz ab. Unverändert gilt:
fehlend/unvollständig/identitätsfremd ⇒ `WorkEnqueueError`, kein Send, kein
Marker-Update; terminal/`enqueuedAt` ⇒ gültiges Duplikat ohne Send.

## 2. Tests (62 passed)

| Lauf | Ergebnis |
| --- | --- |
| `test_work_queue.py` inkl. neuer Fälle | PASS |
| `test_dispatch_ingress_lambda.py` | PASS |
| `test_agent_order_dispatch_e2e.py` (MO `db4f9e7`) | PASS |
| `test_analysis_ecosystem_wiring.py` (neuer Bundle-Pin) | PASS |
| `test_mo_dispatch_handoff.py` | PASS |
| Fokussiert gesamt | **62 passed** |

Neue Negativfälle: anderer Payload, anderer `idempotencyKey`, anderer
`apiProfileId`, anderer `type` ⇒ jeweils **kein SQS-Send, kein Marker-Update**.
Positiv: identischer verschachtelter Payload + Key bleibt idempotent
(Duplikat, kein Send).

## 3. Reproduzierbare Bundles

| Bundle | SHA-256 |
| --- | --- |
| Agent (`terraform/lambda.zip`) | `71bf3c9d6f204a64c03cde68d4df08b5127c73dc7849eb980330452cce3f4142` |
| Analysis (`terraform/analysis-lambda.zip`) | `7b3c8e6e1de5af7c0ffc14ccf5b889761757cc8d3688ffc1b4768a4974980ec8` |
| Reader | unverändert `610004f6…` |
| MO-Modul | unverändert `aa70eaaa…` |

## 4. Frischer Plan

| Feld | Wert |
| --- | --- |
| Datei | `C:\tmp\ris-dev2-workitem-persistence-fix-13a.tfplan` |
| Größe | 253 381 Bytes |
| SHA-256 | `41fef4bcf4c1c779b20378cbf2899a8e69099f2a0828725c46bc3fc844c582d3` |
| Diff | **0 Add / 3 Change / 0 Destroy / 0 Replace** |
| Funktionen | `agent`, `agent-dispatch-ingress`, `analysis` |
| Attribute | nur `source_code_hash` + `last_modified` |
| Code-Hashes | Agent/Ingress `cb88nW8g…`, Analysis `ezyObh3l…` |
| Synthetic-Env | unverändert `MODE=true` |
| State | Serial **73**, Lineage unverändert; S3-Version `5UJcb…` unverändert |
| Drift | eine bekannte Beobachtung (`dispatch_ingress` Rollen-`inline_policy`-Aggregat), keine Planänderung |

Der frühere Plan `03a5a3ed…` ist durch den Code-Rebuild **überholt** und wird
nicht verwendet.

## 5. Unveränderter AWS-Zustand

- WorkItem `work-eb1185ecc14c889a` weiterhin nur `workId` + `enqueuedAt`.
- Order `ord_676668fe5ab468284ed7fcf2` weiterhin `PENDING`.
- Work-DLQ 1, Dispatch-DLQ 0, `MODE=true` (Ablauf 17:40:28Z).
- Keine Writes in diesem Schritt.

## 6. Wiederherstellung (unverändert vorbereitet, nicht ausgeführt)

Nach Fix-Apply + separater Datenfreigabe: Work-DLQ-Body prüfen, marker-only-Zeile
durch validierten vollständigen WorkItem ersetzen oder gezielt löschen und
Dispatch erneut ausführen, dann einmal redriven. Alternativ neue Order mit
neuer WorkId (separate Freigabe). Ein Redrive vor der Datenkorrektur scheitert
mit dem Fix korrekt fail-closed.

## 7. Grenzen eingehalten

Keine AWS-Writes, kein Apply, kein Redrive, keine Datenkorrektur, keine neue
Order, kein Cleanup.
