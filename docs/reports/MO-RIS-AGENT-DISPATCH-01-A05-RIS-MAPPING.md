# A05 — RIS-Seite: Dispatch-Mapping und Handoff-Nachweis

**Datum:** 2026-11-13
**Basis:** `feature/ris-mo-addition-agent-e2e-01` @ `f44cea2`
**Typ:** Additive Mapping-Ergänzung + Cross-Repo-Test (kein Deployment)

## 1. Änderung

Der eingefrorene Transport-V1-Validator akzeptierte `execution.workId` bei
`ORDER_DISPATCH` bereits — die Abbildung auf das WorkItem ignorierte den Wert
jedoch und erzeugte eine neue ID. Damit war die von Mays-Orders gebundene
`expectedWorkId` für RIS bedeutungslos und jedes Ergebnis wäre an A06 mit
`work_mismatch` gescheitert.

Umgesetzt:

1. `validate_envelope`: `execution` wird auch bei `ORDER_DISPATCH` strukturell
   geprüft (`workId` Pflicht, sobald `execution` vorhanden ist).
2. `dispatch_to_work_item`: verwendet `execution.workId`, wenn vorhanden;
   andernfalls bleibt das bisherige Verhalten (Empfänger generiert).

**Keine Schemaänderung:** kein neues Feld, keine Versionserhöhung, keine zweite
Transportstruktur. Der Envelope bleibt V1; ältere Sender ohne `execution` werden
unverändert verarbeitet.

## 2. Sicherheit

- Die WorkId ist Transport-Korrelation, **kein** Berechtigungsnachweis.
- Identität kommt weiterhin ausschließlich aus `VerifiedContext`; der Empfänger
  löst `identity.contextRef` gegen seinen vertrauenswürdigen Store auf.
- `identity.contextRef` wird nur auf Gleichheit mit dem verifizierten Kontext
  geprüft, nie übernommen.

## 3. Cross-Repo-Nachweis

`tests/test_mo_dispatch_handoff.py` (Skip ohne `MO_ORDERS_SRC`):

```
Order speichern → prepare_dispatch (bindet WorkId)
  → dispatch_envelope (V1)
    → validate_envelope → dispatch_to_work_item  (gleiche WorkId)
      → AdditionAgent → 42
        → result_from_work_item → ORDER_RESULT
          → Orders apply_result → 42, genau einmal
```

Zusätzlich abgedeckt: Wiederholung liefert dieselbe WorkId, doppelte
Result-Nachricht ist idempotent, falsche WorkId → `work_mismatch`, stale Attempt
→ `stale_attempt`, unsignierte Nachricht wird verworfen, fremder Eigentümer und
stornierte Order werden nicht dispatcht.

## 4. Testergebnis

| Lauf | Ergebnis |
|---|---|
| RIS mit `MO_ORDERS_SRC` | **149 passed** (inkl. 10 Cross-Repo) |
| RIS ohne `MO_ORDERS_SRC` | **96 passed, 10 skipped** |
| Orders (separat) | **193 passed** |

## 5. Grenzen

- Kein AWS-Aufruf, kein Apply, kein Deployment.
- Queues/IAM/Secret bleiben offen und freigabepflichtig.
- Der echte SQS-Handoff ist **NOT DEPLOYED / NOT LIVE VERIFIED**.
