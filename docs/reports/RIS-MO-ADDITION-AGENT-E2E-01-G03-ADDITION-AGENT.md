# RIS-MO-ADDITION-AGENT-E2E-01 — G03 Addition-Agent

**Datum:** 2026-11-13
**Typ:** Lokale Implementierung + Tests (keine AWS-Mutation, kein Deployment)
**Ergebnis:** G03 COMPLETE (lokal verifiziert). Referenzfall `17 + 25 = 42` grün.

## 1. Git

| Feld | Wert |
|---|---|
| Branch | `feature/ris-mo-addition-agent-e2e-01` |
| Parent | `c48164b` (G00) |
| Basis | `main` @ `2d0c67d` |

## 2. Implementierung

Neu: `agents/addition_agent/` (agent, registry, `__init__`).
Geändert: `agents/runtime/pipeline.py` — eine Registrierungszeile in
`ensure_reference_agent` (bestehende Verdrahtung, keine zweite Architektur).

Der Agent ist ein normaler `AgentBase`-Ableitling wie `reference_agent` und `ats_agent`.
Er nutzt ausschließlich die vorhandene Registry/Discovery/Eligibility/Selection-Kette
sowie den vorhandenen Agent Body.

## 3. Contract

**Capability:** `math.add`
**agentId:** `addition_agent`
**workType:** `agent_addition_agent`
**Version:** `1.0.0`
**Status:** ACTIVE

Eingang (`payload`):

```json
{ "left": 17, "right": 25 }
```

Ausgang (`data`):

```json
{ "left": 17, "right": 25, "sum": 42 }
```

Regeln:

| Fall | Verhalten |
|---|---|
| `int` / endlicher `float` | akzeptiert, exakte Dezimalarithmetik |
| `bool`, `None`, `str`, Liste, Objekt | `success:false`, `ValidationError` |
| `inf`, `-inf`, `nan` | `success:false`, `ValidationError` |
| unbekannte Capability | `success:false`, `ValidationError` (fail-closed) |
| fehlendes `payload` | `success:false`, `ValidationError` |

Bewusste Grenzen:

- **keine** Datenbank, **keine** Credentials, **keine** eigene Queue,
- kein Netzwerk, kein HTTP, keine Uhrzeit im Ergebnis (`data` ist zeitunabhängig),
- `Decimal`-Arithmetik verhindert Binärartefakte: `0.1 + 0.2 → 0.3`, nicht `0.30000000000000004`.

## 4. Tests

`tests/test_addition_agent.py` — **29 passed**

Abgedeckt:

- Referenzfall `17+25=42`
- 50-fache Wiederholung identisch (Determinismus)
- negative/Null-Operanden, `int`+`float`
- JSON-Serialisierbarkeit
- 8 ungültige Operandentypen
- 3 nicht-endliche Werte
- unbekannte Capability, fehlendes Payload, Fehler ohne Exception
- `validate_work` positiv/negativ
- idempotente Registrierung (genau 1 Descriptor pro Capability)
- **Ausführung über den bestehenden `AgentBody`** → `42`
- Routing allein über Capability, ohne `agentId`
- Lambda-Paritätshandler über SQS-Records

Regressionslauf (angrenzende Agenten-/Runtime-Suiten):
**125 passed, 5 subtests passed** in 1.67 s
(`test_routing`, `test_full_pipeline`, `test_execution_engine`,
`test_multi_agent_ecosystem`, `test_p22_agent_capability_contract`,
`test_agent_body`, `test_agent_status_normalization`, `test_addition_agent`)

`py_compile` und `git diff --check` sauber.

## 5. Sicherheit

- Keine Secrets, keine Zugangsdaten, keine Tenant- oder Partnerdaten im Agenten.
- Der Agent liest nur `work_item["payload"]`; er interpretiert **keine**
  Berechtigungsattribute und trifft keine Autorisierungsentscheidung.
- Autorisierung bleibt vollständig beim M2M-Handler (Credential + Registry-Bindung)
  und beim Execution-Time-Entitlement-Check.

## 6. Nicht enthalten (bewusst)

- **Kein Terraform-Catalog-Seed** für `addition_agent`. Der In-Memory-Katalog des
  Workers kennt den Agenten nach dieser Änderung, der persistente
  `agent-catalog`-Eintrag fehlt aber. Für die Live-M2M-Ausführung ist der Seed
  erforderlich — das ist eine Deployment-Änderung und damit nicht Teil von G03.
- Keine Änderung an Mays-Orders.
- Keine Ergebnisfreigabe, kein SQS-Rückkanal (G07, BLOCKED).

## 7. Blocker unverändert

G05/G07/G08 bleiben blockiert durch B1–B4 aus G00 (Payload-Feld, `subjectId`,
Ergebnis-Queue/Consumer, Status-vs-Ergebnis). G03 berührt keinen dieser Verträge.

## 8. Nächster Schritt

G01 (Testpartner-Demo, lokal mit Fake-Adaptern) und G02 (Authorization-Contract-Tests)
sind ohne B1–B4 möglich. Danach B1–B4 entscheiden und G05/G07 seriell integrieren.
