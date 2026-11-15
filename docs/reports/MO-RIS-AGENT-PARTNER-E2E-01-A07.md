# MO-RIS-AGENT-PARTNER-E2E-01 — A07 Full Local End-to-End

**Datum:** 2026-11-13
**Basis:** RIS `7d7f446`, Orders `1e06468`
**Ergebnis:** LOCAL E2E VERIFIED. `17 + 25 = 42` über die echten
Anwendungskomponenten; SQS bleibt lokal simuliert.

## 1. E01 — Was ersetzt wurde

`DemoService` und die Oberfläche (`app.py`) sind **unverändert**. Ersetzt wurden
ausschließlich die beiden Fakes:

| Fake | Ersatz |
|---|---|
| `FakeOrders` | `OrdersApplicationAdapter` → echter `index.handler` (API-Gateway-v2-Event mit verifizierten Claims), danach A05-Dispatch |
| `FakeRis` | `RisApplicationAdapter` → echter Transport-Parser, Registry/Discovery/Eligibility/Entitlement, bestehender AgentBody, signierter A06-Consumer |
| — | `LocalSqsBus` (gleiche Nachrichtenformate, gleiche Consumer-Einstiege) |
| — | `InMemoryOrdersTable` (Storage-Double mit den Conditional-Semantiken) |

Es entsteht **keine** zweite Agent-Runtime und **keine** zweite
Order-Persistenz: alle Regeln (Ownership, Fingerprint, Dispatch-Bindung,
Result-Idempotenz) liegen im Anwendungscode.

Umschaltbar: `DEMO_MODE=real` startet die Demo gegen die echten Ports.

## 2. E02 — Happy Path (belegt)

```
Partner A (Claims) → POST /orders → Order + Owner
  → A05: prepare_dispatch (expectedWorkId, atomar)
  → ORDER_DISPATCH auf den lokalen Bus
    → RIS: validate_envelope → dispatch_to_work_item (gleiche workId)
      → Discovery/Eligibility/Entitlement → AgentBody → AdditionAgent → 42
        → ORDER_RESULT signiert → A06-Consumer
          → apply_result (genau einmal)
            → GET /orders/{id} (Owner) → processing.result.sum = 42
```

Der fachliche Order-`status` bleibt `PENDING`; die Anzeige nutzt den
Verarbeitungsstatus getrennt davon (`orderStatus` vs. `status`).

## 3. E03 — Negative Fälle

| Fall | Ergebnis |
|---|---|
| Partner B liest fremde Order | `404` |
| Keine Dispatch-Nachricht | `503`, kein vorgetäuschter Erfolg |
| Fremder Tenant | `403`, nichts gespeichert |
| Nicht unterstützte Capability | `403` (keine Eligibility) |
| Fehlende Identitätsreferenz | `missing_identity_reference`, kein Dispatch |
| Wiederholter Dispatch | gleiche WorkId, keine zweite Ausführung |
| Doppeltes Result | idempotent, ein Abschluss |
| Falsche WorkId | `work_mismatch` |
| Stale Attempt | `stale_attempt` |
| Storniert | `order_cancelled` |
| Manipulierte Signatur | verworfen |
| Secrets in HTML/Transport/Antwort | keine |

**Zum RIS-Key:** Im Partner-Order-Pfad wird **kein** RIS-Key übertragen — die
Ausführung ist Service-zu-Service über den internen Boundary. „Falscher/widerrufener
RIS-Key" ist deshalb kein Fall dieses E2E, sondern der direkten M2M-Route
(abgedeckt in G02 durch 16 Tests). Der E2E prüft stattdessen die stärkere
Eigenschaft: kein Key im Transport.

## 4. E04 — Darstellung

Die Demo zeigt Order-ID, `status`, `result.sum` (42) und `error` im
bestehenden Formular. Der Abruf läuft ausschließlich über
`GET /orders/{orderId}` mit Owner-Claims — keine direkte Datenbankabfrage aus
der Partnerseite.

## 5. E05 — Regression

| Suite | Ergebnis |
|---|---|
| Orders (alle) | **193 OK** |
| RIS A07-E2E | **16 passed** |
| RIS A05-Handoff | **10 passed** |
| RIS gezielt (Transport, Body, Agent, Auth) | **149 passed** |
| RIS Gesamtsuite | 2530 passed, 78 skipped, 425 subtests |

**Vorbestehende Umgebungsfehler (nicht von diesem Gate):** 34 Failures und 4
Collection-Errors in der Gesamtsuite. Belegt durch Einzelproben: Tests, die
`python3` als Subprozess starten, scheitern auf diesem Windows-Rechner mit
`FileNotFoundError`; `test_ats_agent` scheitert an fehlendem Modul `requests`.
Betroffen sind `test_ris_admin_credentials`, `test_dependency_check`,
`test_ats_agent`, die Consent-Suiten und `test_http_e2e_integration` — keine
davon berührt die Agent-/Dispatch-/Result-Kette.

Keine Retail-Änderung, kein Bruch des Transport-V1, keine zusätzliche
Infrastruktur für den lokalen Test.

## 6. Betriebsgrenzen

- Kein Terraform-Apply/-Destroy, kein Deployment, keine Cognito-/CloudFront-/DNS-Änderung.
- Kein RC-Upgrade, kein Merge.
- Keine echten Zugangsdaten in Fixtures.
- **Die lokale SQS-Simulation ist keine AWS-SQS-Zustellung.**

## 7. Nächster Schritt

Infrastrukturplan für die isolierte AWS-Integration (Queues, IAM, Secret,
Consumer-Lambda) als Plan zur separaten Freigabe. Kein Apply in diesem Gate.
