# Partner Addition Demo (Testpartner A)

Lokale, isolierte Testpartnerseite für **RIS-MO-ADDITION-AGENT-E2E-01 (G01)**.
Sie zeigt den vollständigen Pfad

```
Browser → Demo-Service → Orders (Fake) → RIS (Fake, math.add) → Ergebnis → Browser
```

**Keine AWS-Abhängigkeit.** Beide Adapter (`FakeOrders`, `FakeRis`) sind
in-memory und deterministisch. Der RIS-Key wird ausschließlich serverseitig
gelesen und niemals in HTML, JSON oder Logs geschrieben.

## Starten

```bash
RIS_API_KEY=ris_demo_not_a_real_key python examples/partner-addition-demo/app.py
# → http://127.0.0.1:8080
```

Ohne `RIS_API_KEY` startet die Demo trotzdem, aber die Order-Erstellung schlägt
kontrolliert mit `503` fehl — es wird **kein** Platzhalter-Key erfunden.

Optionen: `DEMO_HOST` (Default `127.0.0.1`), `DEMO_PORT` (Default `8080`).

## Bedienung

1. Zwei Zahlen eingeben (Default `17` und `25`).
2. **Addition beauftragen** → HTTP 201 mit `orderId`.
3. **Status prüfen** → `PENDING`/`PROCESSING`, danach `DELIVERED` mit
   `{"left":17,"right":25,"sum":42}`.

## Sicherheitsgrenzen

| Regel | Umsetzung |
|---|---|
| RIS-Key nur serverseitig | `build_service()` liest `RIS_API_KEY`; die Seite enthält kein Secret |
| Key nie in Antworten | Tests prüfen HTML/JSON auf Abwesenheit |
| Kein Key im Browser-JS | alle Aufrufe gehen an die eigenen `/api/*`-Routen |
| Loopback-Bind | Default `127.0.0.1` |
| `no-store` | jede Antwort setzt `Cache-Control: no-store` |
| Keine echten Credentials | nur synthetische Testwerte |

## Struktur

| Datei | Zweck |
|---|---|
| `demo_core.py` | Ports (`OrdersPort`, `RisPort`), Fakes, `DemoService` |
| `app.py` | stdlib-HTTP-Transport, Formularseite, `/api/orders`, `/health` |
| `../../tests/test_partner_addition_demo.py` | 15 lokale Tests |

Die Ports sind absichtlich schmal. Für einen späteren echten Betrieb werden
`FakeRis` → RIS-M2M-Client (`POST /v1/m2m/agents/addition_agent/execute` +
`X-Api-Credential`) und `FakeOrders` → Mays-Orders-API ersetzt, ohne
`DemoService` oder die Seite zu ändern.

## Modi

| Modus | Adapter | Zweck |
|---|---|---|
| Standard | `FakeOrders` / `FakeRis` | UI- und Ablaufentwicklung ohne zweites Repo |
| `DEMO_MODE=real` | echte Orders-/RIS-Komponenten, lokaler SQS-Bus | End-to-End-Nachweis (A07) |

```bash
# Fake-Modus (Default)
RIS_API_KEY=ris_demo_not_a_real_key python examples/partner-addition-demo/app.py

# Realer Modus: nutzt den echten Orders-Handler, A05-Dispatch, RIS-Transport,
# AgentBody und den A06-Result-Consumer. SQS bleibt lokal simuliert.
MO_ORDERS_SRC=/pfad/zu/mays-order-aws/lambda/src \
ORDERS_COGNITO_ISSUER=https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_X \
ORDERS_COGNITO_CLIENT_ID=client-x \
ORDER_RESULT_SERVICE_SECRET=local-secret \
DEMO_MODE=real python examples/partner-addition-demo/app.py
```

Im realen Modus läuft die Kette
`POST /orders → A05 Dispatch → RIS → AdditionAgent → ORDER_RESULT → A06 → GET`,
ohne dass die Oberfläche etwas davon weiß. Es wird **nichts** deployt.

## Nicht enthalten

- Kein echter Cognito-Login (G01 akzeptiert den vorhandenen Cognito-Vertrag;
  die Demo läuft lokal ohne Identitätsanbieter).
- Keine Persistenz, kein Deployment.
- Der Live-Pfad bleibt durch B1–B4 (G00) blockiert.
