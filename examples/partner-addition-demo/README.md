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

## Nicht enthalten

- Kein echter Cognito-Login (G01 akzeptiert den vorhandenen Cognito-Vertrag;
  die Demo läuft lokal ohne Identitätsanbieter).
- Keine Persistenz, kein Deployment.
- Der Live-Pfad bleibt durch B1–B4 (G00) blockiert.
