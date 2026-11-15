# RIS-MO-ADDITION-AGENT-E2E-01 — G02 Authorization-Matrix

**Datum:** 2026-11-13
**Typ:** Lokale Contract-Tests (keine AWS-Mutation, kein Deployment, keine echten Credentials)
**Ergebnis:** G02 COMPLETE (lokal). Matrix 16/16 grün.

## 1. Git

| Feld | Wert |
|---|---|
| Branch | `feature/ris-mo-addition-agent-e2e-01` |
| Parent | `c3b64b2` (G03) |

## 2. Vorgehen

Kein zweiter Test-Harness: die Datei nutzt die **echten** In-Memory-Stores
(`InMemoryApiProfileStore`, `InMemoryCredentialStore`) und den **echten**
Handler-Einstiegspunkt `handler.handler`. Nur die AWS-Seiteneffekte sind ersetzt:

- `_build_introspection_sources` → In-Memory-Quellen,
- `_enqueue_agent_work` → Recorder (kein SQS/DynamoDB),
- `resolve_partner_application` → Registry-Stub.

Damit wird die reale Kette geprüft, nicht eine Nachbildung:
Cognito-Claims → `verify_api_credential` → Partner-Registry-Bindung → Execution-Contract.

## 3. Matrix-Ergebnis

| # | Fall | Erwartung | Ergebnis |
|---|---|---|---|
| 1 | Partner A, gültiges JWT + RIS-Key + Entitlement | 202 ALLOW | **PASS** |
| 2 | Partner B ohne Entitlement | 403 DENY | **PASS** |
| 2b | Entitlement für anderen Agenten | 403 DENY | **PASS** |
| 2c | Entitlement abgelaufen (`validUntil` vorbei) | 403 DENY | **PASS** |
| 2d | Entitlement noch nicht gültig (`validFrom` in Zukunft) | 403 DENY | **PASS** |
| 2e | Entitlement widerrufen (Zeile entfernt) | 403 DENY | **PASS** |
| 3 | Falscher RIS-Key | 401 DENY | **PASS** |
| 3b | Fehlender RIS-Key | 401 DENY | **PASS** |
| 4 | Widerrufener Key | 403 DENY | **PASS** |
| 5 | Agent INACTIVE | 403 DENY | **PASS** |
| 5b | Agent unbekannt | 403 DENY | **PASS** |
| 6 | Fremder Tenant in der Registry-Bindung | 403 DENY | **PASS** |
| 6b | Fremdes APIProfile in der Registry-Bindung | 403 DENY | **PASS** |
| 6c | Cognito-Tenant ≠ Credential-Tenant | DENY oder Ausführung als Credential-Tenant | **PASS** |
| 7 | Payload `17/25` überlebt die Grenze unverändert | identisch | **PASS** |
| 8 | Secret/Header nie im WorkItem oder Response | nicht enthalten | **PASS** |

Regressionslauf: **112 passed, 7 subtests passed** in 0.57 s
(inkl. `test_p21_cognito_m2m_boundary`, `test_p17_credential_lifecycle`,
`test_entitlement_provisioning`).

## 4. Zwei Befunde, die den Vertrag präzisieren

### 4.1 Entitlements haben kein `status`-Feld

Mein erster Test modellierte „widerrufenes Entitlement" als `status: "REVOKED"`
und wurde **autorisiert**. Ursache ist kein Sicherheitsleck, sondern das
tatsächliche Modell:

- `worker_authorization.is_entitlement_valid` prüft **nur** `validFrom`/`validUntil`,
- `_row_matches` prüft Agent und Tenant,
- Widerruf läuft über `offers.withdraw_entitlement` → `delete_entitlement` → `delete_item`.

Ein `status`-Feld auf einer Entitlement-Zeile wird schlicht ignoriert.
**Konsequenz für G02:** „widerrufen" ist als **fehlende Zeile** und „abgelaufen"
als **Zeitfenster** zu testen — beides ist jetzt abgedeckt. Wer künftig ein
`status`-Feld einführt, muss den Verifier mitändern, sonst entsteht ein
still wirkungsloses Feld.

### 4.2 Autorisierung erfolgt pro Agent, nicht pro Capability

`verify_api_credential(agent_id=...)` prüft Agent-Status, Credential, Profil,
Tenant und Entitlement — **nicht** die Capability aus dem Body. Die Capability
wird unverändert in das WorkItem übernommen und erst im Worker durch
Discovery/Eligibility geprüft; ein falsche Capability führt dort zu
„kein geeigneter Agent" und damit zu einem kontrollierten Fehlschlag.

Das ist **kein Autorisierungsbypass** (es wird nichts ausgeführt), aber es ist
ein Accept-then-Fail: der Aufrufer erhält `202`, obwohl die Capability nicht
zum Agenten passt. Für G05 sollte entschieden werden, ob die Capability
bereits am M2M-Rand gegen den Katalog geprüft werden soll (dann `400`/`403`
statt `202`). Ich habe das **nicht** geändert — es wäre eine Vertragsänderung.

## 5. Sicherheit

- Kein Secret im WorkItem, in der Response oder in Logs (explizit getestet).
- Keine echten Credentials erzeugt; alle Werte sind synthetisch und lokal.
- Keine AWS-Aufrufe, keine Cognito-/CloudFront-/DNS-Änderung.

## 6. Nicht enthalten

- Kein Live-Partner, kein echter Cognito-Client, keine Persistenz (das ist G02-Phase C).
- Keine Änderung an `verify_api_credential` oder am Entitlement-Modell.
- G01 (Demo-Oberfläche) bleibt offen.

## 7. Nächster Schritt

G01 (Testpartner-Demo mit Fake-Adaptern) ist weiterhin ohne B1–B4 möglich.
G05/G07/G08 bleiben blockiert. Zusätzlich liegt jetzt eine konkrete
Entscheidungsvorlage für die Capability-Prüfung am M2M-Rand vor (§4.2).
