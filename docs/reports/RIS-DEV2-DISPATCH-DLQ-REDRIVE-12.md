# RIS-DEV2-DISPATCH-DLQ-REDRIVE-12

**Datum:** 2026-11-26
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `6c755688cb09bcc2f00b023fe6f4d1d2b336ee12`
**AWS:** `262370457690` / `eu-central-1` / `ris-dev2`
**Status:** **BLOCKED — PARTIALLY VERIFIED**
(Redrive und Dispatch-IAM verifiziert; E2E scheitert an einem unvollständigen WorkItem.)

## 1. Preflight (PASS)

| Prüfung | Ergebnis |
| --- | --- |
| Konto / Region / Workspace | `262370457690` / `eu-central-1` / `ris-dev2` |
| Ingress-IAM | `dynamodb:ConditionCheckItem` live vorhanden |
| Synthetic-Modus | `true`, Ablauf `2026-11-26T17:40:28Z` |
| Entitlement | gültig (`1795714828`) |
| Dispatch-DLQ | genau 1 Nachricht |
| Order | `ord_676668fe5ab468284ed7fcf2`, `PENDING`, keine WorkItems |
| ESMs | Dispatch/Worker/Result-Consumer alle `Enabled` |

## 2. Redrive (einmalig, inhaltlich geprüft)

Die Nachricht wurde empfangen und vor dem Senden strikt geprüft:

| Feld | Wert |
| --- | --- |
| DLQ-Message-ID | `89c41981-c122-4a19-a0c9-d317bc6df2fa` |
| Typ | `ORDER_DISPATCH` |
| OrderId | `ord_676668fe5ab468284ed7fcf2` |
| WorkId | `work-eb1185ecc14c889a` |
| ContextRef | `aprof_cdbd3b6f803744bf` |
| Recipient | `analysis-agent` / `analysis.run` |
| Sender | `mays-orders` |
| Payload | `job.tags`-Request (synthetisch) |

Die exakte Body-Zeichenkette wurde einmal an
`ris-dev2-dev-agent-dispatch` gesendet (neue Message-ID
`550a89bb-7060-44d8-a01b-8485b4e171fc`); erst danach wurde die DLQ-Nachricht
gelöscht. Kein Bulk-Redrive, keine weitere Nachricht.

## 3. Verarbeitung

| Schritt | Ergebnis |
| --- | --- |
| Dispatch-Ingress | verarbeitet; Work-Queue erhielt die Nachricht; Dispatch-Queue/DLQ 0 |
| WorkItem | **nur** `workId` + `enqueuedAt` persistiert — **kein** `status`, keine Identität, kein Payload |
| Worker | `Error processing record: WORK_ADMISSION_STATE_UNSAFE` (07:11:31, Retry 07:16:22) |
| Analysis | nie aufgerufen |
| ORDER_RESULT / Consumer | nicht erreicht |
| Order | weiterhin `PENDING`, `processing=null` |
| Queues | Work-Queue: 1 in-flight (dritter Versuch läuft); Work-DLQ 0 (Stand 07:20:39) |

### Beleg

```text
WorkItem: {"workId":"work-eb1185ecc14c889a","enqueuedAt":"2026-11-26T07:11:21.879859+00:00"}
Worker:   WORK_ADMISSION_STATE_UNSAFE
pipeline.py:654  raise RuntimeError("WORK_ADMISSION_STATE_UNSAFE")
```

## 4. Ursache (belegt) und kleinster Fixbedarf

Der WorkItem ist unvollständig. Der Code-Pfad in
`agents/runtime/work_queue.py::enqueue_work_item` kann genau das erzeugen:

1. Die Transaktion (`ConditionCheck` + `Put`) wird als *conditional* abgelehnt
   (`TransactionCanceledException`/`ConditionalCheckFailedException`).
2. `inserted=False`; der Code liest die WorkItem-Zeile, findet **keine**,
   sendet trotzdem an die Work-Queue.
3. Das anschließende `update_item("SET enqueuedAt")` **erzeugt** die Zeile
   (DynamoDB UpdateItem legt fehlende Items an) — nur mit `workId` und
   `enqueuedAt`.
4. Der Worker sieht keine `status`/Identität und verweigert korrekt mit
   `WORK_ADMISSION_STATE_UNSAFE`.

Der exakte Auslöser der Transaktionsablehnung wurde read-only nicht bewiesen
(kein Fence-Row für die Identität vorhanden: full/empty/no-partner keys alle
`False`). Das ist ein Produktfehler im Enqueue-/Fail-closed-Pfad, **kein**
IAM-Problem mehr: der Dispatch-Ingress hat die Nachricht erfolgreich
weitergegeben.

**Kleinster sicherer Fix (separate Freigabe, nicht umgesetzt):** Nach einer
abgelehnten Transaktion darf nur dann gesendet werden, wenn eine
**vollständige** bestehende WorkItem-Zeile mit passendem Status existiert;
andernfalls muss der Handler fail-closed retryen/abbrechen. Dazu ein
Regressionstest „Cancelled + keine Zeile ⇒ kein Send, kein Update“. Die
Transaktionsablehnung selbst ist separat zu untersuchen.

## 5. Aktueller AWS-Zustand (nicht weiter verändert)

- Order `PENDING`; keine WorkItem-Verarbeitung, kein ORDER_RESULT.
- Dispatch-Queue/DLQ 0; Work-Queue 1 in-flight; Work-DLQ 0 (Snapshot).
- `ANALYSIS_SYNTHETIC_MODE=true`; Entitlement gültig bis 17:40:28Z.
- Terraform-State Serial 73 unverändert; keine weiteren Writes nach dem
  Redrive.

## 6. Grenzen eingehalten

Keine neue Order, kein Terraform-Apply, kein neuer Grant, keine
Cognito-Änderung, kein Cleanup/Rollback, kein Main-Merge. Nach dem Redrive
nur read-only Beobachtung.

## 7. Entscheidung

**BLOCKED — PARTIALLY VERIFIED.** Der Redrive-Pfad und die IAM-Korrektur sind
live belegt; der E2E ist am unvollständigen WorkItem und der
`WORK_ADMISSION_STATE_UNSAFE`-Admission gescheitert. Ohne den fail-closed-Fix
im Enqueue-Pfad ist kein vollständiger ORDER_DISPATCH→Analysis→ORDER_RESULT-Lauf
möglich.
