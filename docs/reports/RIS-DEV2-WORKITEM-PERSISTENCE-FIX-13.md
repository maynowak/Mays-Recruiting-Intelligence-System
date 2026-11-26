# RIS-DEV2-WORKITEM-PERSISTENCE-FIX-13

**Datum:** 2026-11-26
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `184c47ae1c967644d169263272933070bd2f6600`
**AWS:** `262370457690` / `eu-central-1` / `ris-dev2`
**Status:** **READY FOR PERSISTENCE FIX APPLY APPROVAL**
**Modus:** Codefix + Tests + Plan; keine AWS-Writes, kein Apply, kein Redrive

## 1. Fix

`agents/runtime/work_queue.py`:

- Eine abgelehnte Transaktion wird **nicht** mehr pauschal als Duplikat
  behandelt.
- Das bestehende WorkItem wird mit `ConsistentRead` gelesen und muss
  vollständig und identisch sein: `workId`, `status` (QUEUED/RUNNING/FAILED/
  COMPLETED/CANCELLED/DEAD_LETTER), `tenantId`, `userId`,
  `partnerApplicationId`, `issuer`, `agentId`, `capability`, `payload` (dict),
  `idempotencyKey`.
- Fehlt die Zeile, ist sie unvollständig oder identitätsfremd ⇒
  `WorkEnqueueError`, **kein SQS-Send, kein Marker-Update**.
- Nur gültige, passende Zeilen werden nach dem bestehenden Idempotenzvertrag
  wiederverwendet (terminal oder `enqueuedAt` ⇒ Duplikat ohne Send).
- `CancellationReasons` werden als **Index/Code** geloggt (z. B.
  `ConditionalCheckFailed`, `TransactionConflict`), nie Werte oder Payloads.
- Das `enqueuedAt`-Update trägt `ConditionExpression="attribute_exists(workId)"`
  und kann damit keine marker-only-Zeile mehr erzeugen.

## 2. Root Cause (belegt / nicht belegt)

| Prüfung | Ergebnis |
| --- | --- |
| Fence-Eintrag für die Identität | **nicht vorhanden** (full/empty/no-partner Keys alle `False`) |
| WorkItem vor dem Redrive | **nicht vorhanden** (0 Zeilen für die Order) |
| Persistierte Zeile | nur `workId` + `enqueuedAt` |
| Alter Code | verwarf `CancellationReasons`; las die Zeile ohne ConsistentRead und sendete trotzdem |

Damit ist eine **Fence-Blockade nicht belegt** und wird nicht behauptet. Der
exakte Transaktions-Auslöser ist aus den bestehenden Logs nicht
rekonstruierbar; der neue Code protokolliert die Gründe beim nächsten Fall.
Die belegte Verkettung ist: abgelehnte Transaktion → kein vollständiger Put →
trotzdem Send → `update_item` erzeugt die marker-only-Zeile → Worker
`WORK_ADMISSION_STATE_UNSAFE`.

## 3. Tests

| Lauf | Ergebnis |
| --- | --- |
| `test_work_queue.py` (inkl. neuer Fälle) | PASS |
| `test_dispatch_ingress_lambda.py` | PASS |
| `test_agent_order_dispatch_e2e.py` (MO `db4f9e7`) | PASS |
| `test_analysis_ecosystem_wiring.py` | PASS (Pin auf neue Bundles) |
| `test_mo_dispatch_handoff.py` | PASS |
| Fokussiert gesamt | **59 passed** |

Neue Fälle: fehlende Zeile, unvollständiges Item, Identitätsmismatch
(tenant/user/partner/issuer/agent/capability), gültiges Duplikat
(`enqueuedAt`/terminal), gültige QUEUED-Zeile ohne Marker (ein Send,
Marker mit Condition), erfolgreiche Erstpersistenz, nicht-konditionaler
Persistenzfehler (kein Send/Update), sichere Reason-Logs.

## 4. Aktueller Zustand (read-only)

| Prüfung | Ergebnis |
| --- | --- |
| WorkItem `work-eb1185ecc14c889a` | nur `workId` + `enqueuedAt` (beschädigt) |
| Order `ord_676668fe5ab468284ed7fcf2` | `PENDING`, `processing=null` |
| Dispatch-Queue/DLQ | 0 / 0 |
| Work-Queue | 0 (Nachricht hat Retries erschöpft) |
| Work-DLQ (`ris-dev2-dev-dlq`) | **1** |
| Synthetic-Modus | `true`, Ablauf 2026-11-26T17:40:28Z |

## 5. Wiederherstellungsweg (vorbereitet, nicht ausgeführt)

Der beschädigte Datensatz blockiert denselben WorkId; ein Redrive der
Work-DLQ-Nachricht würde mit dem Fix korrekt fail-closed scheitern.

**Option A (bevorzugt, nach Fix-Apply + separater Datenfreigabe):**
1. Work-DLQ-Nachricht read-only prüfen (sie enthält den vollständigen
   WorkItem-Body aus dem Dispatch).
2. Den marker-only-Datensatz durch den validierten vollständigen WorkItem
   ersetzen **oder** gezielt löschen und den Dispatch erneut ausführen —
   beides ist eine Datenkorrektur und benötigt ausdrückliche Freigabe.
3. Erst dann die Work-DLQ-Nachricht einmal redriven; Worker/Status prüfen.

**Option B (ohne Datenkorrektur):** Nach Fix-Apply eine neue synthetische
Order mit neuer WorkId anlegen (separate Freigabe); die beschädigte Zeile und
die alte Order bleiben für das Cleanup.

Keine der Optionen wurde ausgeführt.

## 6. Deployment-Plan

| Feld | Wert |
| --- | --- |
| Datei | `C:\tmp\ris-dev2-workitem-persistence-fix-13.tfplan` |
| Größe | 252 131 Bytes |
| SHA-256 | `03a5a3ed9ba38da67fd514c7f678490d61f63abcc0b43bade3a143c60942a4fe` |
| Terraform | 1.17.0; `applyable/complete` |
| Diff | **0 Add / 3 Change / 0 Destroy / 0 Replace** |
| Funktionen | `agent`, `agent-dispatch-ingress` (Agent-Bundle), `analysis` (Analysis-Bundle) |
| Attribute | jeweils nur `source_code_hash` + `last_modified` |
| Neue Hashes | Agent/Ingress `qVY5Zjus…`, Analysis `FQMeiVNp…` |
| Synthetic-Env | unverändert `true` (Plan mit Basis- und Canary-Var-Datei) |
| State | Serial **73**, Lineage unverändert; S3-Version `5UJcb…` unverändert |
| Drift | eine bekannte Beobachtung (`dispatch_ingress` Rollen-`inline_policy`-Aggregat), keine Planänderung |

## 7. Grenzen eingehalten

Keine AWS-Writes, kein Apply, kein Redrive, keine neue Order, keine
Datenkorrektur, kein Cleanup. Nur lokale Code-/Test-/Plan-Erstellung.
