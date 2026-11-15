# RIS-MO-ADDITION-AGENT-E2E-01 — G01 Testpartnerseite

**Datum:** 2026-11-13
**Typ:** Lokale Demo + Tests (keine AWS-Abhängigkeit, kein Deployment)
**Ergebnis:** G01 COMPLETE (lokal). 15 Tests grün.

## 1. Git

| Feld | Wert |
|---|---|
| Branch | `feature/ris-mo-addition-agent-e2e-01` |
| Parent | `b2fe6ee` (G02) |

## 2. Was gebaut wurde

`examples/partner-addition-demo/`

| Datei | Inhalt |
|---|---|
| `demo_core.py` | Ports (`OrdersPort`, `RisPort`), `FakeOrders`, `FakeRis`, `DemoService` |
| `app.py` | stdlib-HTTP-Transport, Formularseite, `/api/orders`, `/api/orders/{id}`, `/health` |
| `README.md` | Start, Bedienung, Sicherheitsgrenzen |

Kein Node, kein npm, keine neue Dependency — der stdlib-Ansatz entspricht der
Python-only-Konvention des Repositories.

## 3. Ablauf (lokal verifiziert)

```
POST /api/orders {left:17,right:25}
  → Orders.create  → orderId (PENDING)
  → Ris.submit     → workId (Idempotenzkey = orderId)
  → 201 {orderId, workId, status:"IN_PROGRESS"}

GET /api/orders/{orderId}
  → Ris.status: QUEUED → RUNNING  → Order PROCESSING
  → Ris.status: COMPLETED         → Order DELIVERED, result {17,25,42}
```

Wiederholtes Lesen ändert das Ergebnis nicht (idempotente Übernahme im Fake).
Ein fehlgeschlagener Agent markiert die Order `FAILED` und setzt **kein** Ergebnis.

## 4. Sicherheitsgrenzen

| Regel | Nachweis |
|---|---|
| RIS-Key nur serverseitig | `build_service()` liest `RIS_API_KEY`; `test_build_service_reads_key_from_environment_only` |
| Kein Key in HTML/JSON | `test_page_contains_form_and_no_credential`, `test_key_is_never_in_order_or_response_payloads`, `test_end_to_end_over_http` |
| Kein Key im Browser-JS | alle Aufrufe laufen über eigene `/api/*`-Routen |
| Kein erfundenes Secret | ohne Key: `503` und `FAILED`, kein Platzhalter (`test_missing_ris_key...`) |
| Loopback + `no-store` | Default-Bind `127.0.0.1`, jede Antwort setzt `Cache-Control: no-store` |
| Eingabevalidierung | `{}`, fehlendes Feld, String, `bool` → 400, **keine** Order angelegt |
| Fremde Order | 404 |

## 5. Tests

`tests/test_partner_addition_demo.py` — **15 passed, 4 subtests**

- Referenzfall `17 + 25 = 42` über Service **und** HTTP
- Statusfortschritt `PENDING → PROCESSING → DELIVERED`
- stabile Ergebnisse bei wiederholtem Lesen
- negative Operanden
- 4 ungültige Bodies, jeweils ohne Order-Erzeugung
- unbekannte Order → 404
- fehlender Key → `FAILED`, kein Ergebnis
- Key-Abwesenheit in HTML/JSON (3 Tests)
- Capability-Gate im Fake (`math.divide` → Fehler)

## 6. Bewusste Grenzen

- **Kein** echter Cognito-Login. G01 nutzt den vorhandenen Cognito-Vertrag nur als
  Zielbild; die Demo läuft lokal ohne Identitätsanbieter. Ein echter Login wäre
  eine Live-Komponente (Phase C) und ist ohne Freigabe nicht zulässig.
- **Keine** Persistenz: Fakes sind in-memory und pro Prozess.
- Die Ports sind so geschnitten, dass `FakeRis` später durch den echten
  M2M-Client und `FakeOrders` durch die echte Orders-API ersetzt werden kann,
  ohne `DemoService` oder Seite zu ändern.

## 7. Abhängigkeit zu den Blocker-Entscheidungen

Die Demo belegt den **Ablauf**, nicht den Live-Vertrag. Sobald B1–B4 entschieden
sind, ändert sich voraussichtlich:

- das Orders-Payload-Feld (B1) → `FakeOrders.create`-Signatur,
- die Eigentümerprüfung (B2) → `/api/orders/{id}` bekommt einen Nutzerkontext,
- der Ergebnistransport (B3) → `RisPort.status` wird durch den Rückkanal ersetzt.

Deshalb ist die Demo bewusst adapter-zentriert: die Änderungen bleiben in den
Ports, nicht in der Orchestrierung.

## 8. Nächster Schritt

G05/G07/G08 bleiben blockiert. Für den Live-E2E fehlen zusätzlich:
`addition_agent` im persistenten Terraform-Katalog, eine aktive Orders-Instanz
und die Freigabe für Phase C.
