# MO-RIS-AWS-INTEGRATION-PLAN-01 — AWS SQS Boundary (Plan Only)

**Datum:** 2026-11-13
**Typ:** Infrastrukturplan + abgeschalteter Terraform-Code. **Keine AWS-Mutation.**
**Ergebnis:** Plan reviewbar. Kein Apply, kein Plan gegen fremde State-Kontexte.

## 1. Baseline (I00)

| Feld | Wert |
|---|---|
| RIS | `feature/ris-mo-addition-agent-e2e-01` @ `cd14f98` |
| Orders | `feature/mo-agent-order-body-01` @ `1e06468` |
| A07 | LOCAL E2E VERIFIED |
| Testbasen | RC2-/Modul-Contract-Linie (`5cf50a0` ≡ `9627eb2` im Lambda-Code), **kein** RC4 |

Vorhandene Infrastruktur (gelesen, nicht verändert):

| Repo | Queues | DLQ | KMS | Secrets Manager |
|---|---|---|---|---|
| Orders | 1 (`orders`, visibility 30 s, retention **120 s**) | nein | nein | nein |
| RIS | 5 (`work`, `cv`, `ats`, `match`, `dlq`), visibility 300 s | ja (`dlq`, 14 d) | nein | nein (nur eine IAM-Aktion auf `secretsmanager:GetSecretValue`) |

**Wichtig:** Die Retail-Queue (`orders`) ist **nicht** wiederverwendbar. Ihr
Consumer (`sqs_handler`) deutet `status` als Statusübergang und kennt kein
Envelope-Format. Eine Erweiterung würde den Retail-Lifecycle gefährden.

## 2. Soll-Topologie (I01)

```
Mays-Orders ──SendMessage──▶ agent-dispatch (RIS) ──ESM/Lambda──▶ RIS Worker
RIS Worker  ──SendMessage──▶ agent-results  (Orders) ──ESM/Lambda──▶ A06 Consumer
```

Eine Queue **pro Richtung**, nicht pro Agent.

| Kanal | Eigentümer | Producer | Consumer | DLQ | Visibility | Retention | Verschlüsselung |
|---|---|---|---|---|---|---|---|
| Dispatch | RIS (Consumer-Seite) | Orders-Rolle | RIS-Ingress | ja, maxReceive 3 | 300 s | 4 d | SSE-SQS |
| Result | Orders (Consumer-Seite) | RIS-Rolle | Orders A06 | ja, maxReceive 3 | 60 s | 4 d | SSE-SQS |

Idempotenz: Dispatch über `expectedWorkId` + `idempotencyKey`; Result über
`attribute_not_exists(processing)` + stabilen `idempotencyKey`.

## 3. IAM-Matrix (I02)

| Rolle | Darf | Darf nicht |
|---|---|---|
| Orders-Producer | `sqs:SendMessage` auf `agent-dispatch` | lesen, löschen, fremde Queues, Orders-DB für RIS |
| RIS-Ingress | `ReceiveMessage`/`DeleteMessage` auf `agent-dispatch` | senden, Orders-DB |
| RIS-Result-Producer | `sqs:SendMessage` auf `agent-results` | lesen, Orders-DB |
| Orders-A06-Consumer | `ReceiveMessage`/`DeleteMessage` auf `agent-results` | senden, RIS-DB |

Keine Queue-Policy mit `Principal: "*"`. Die Policy listet ausschließlich die
übergebenen Rollen-ARNs; eine leere Liste macht die Queue **inert**.

Technische Senderbindung und gespeicherte Korrelation werden gemeinsam geprüft:
HMAC über `messageId`+Body **und** `expectedWorkId`-Abgleich gegen die Order.

## 4. Contract-Kompatibilität (I03)

Neuer Test `tests/test_mo_contract_compat.py` (RIS, 9 Tests) verbindet beide
Implementierungen:

- RIS-`SCHEMA_VERSION` ∈ Orders-akzeptierte Versionen
- Result-Typen deckungsgleich (`ORDER_RESULT`, `ORDER_FAILED`)
- Richtung `ris → mays-orders`
- Pflichtfeldsätze **exakt gepinnt** (Änderung bricht den Test)
- Dispatch aus Orders wird von RIS akzeptiert (inkl. `execution.workId`)
- Result aus RIS wird von Orders akzeptiert
- Orders lehnt unbekannte Felder und Version `"2"` ab

Damit schlägt der Test bei stillem Auseinanderlaufen fehl.

## 5. Terraform-Änderungen (I05)

Bewusst **abgeschaltet by default** (`enable_agent_transport = false`):
ein bestehender Stack plant **null** Änderungen.

| Repo | Datei | Inhalt |
|---|---|---|
| RIS | `terraform/modules/agent_transport/main.tf` | Dispatch-Queue, DLQ, Redrive, Queue-Policy, Outputs |
| RIS | `terraform/main.tf`, `variables.tf` | `module "agent_transport"` mit `count = 0`-Default, zwei Variablen |
| Orders | `terraform/modules/agent_transport/main.tf` | Result-Queue, DLQ, Redrive, Queue-Policy, Outputs |
| Orders | `terraform/main.tf`, `variables.tf` | dito, `count = 0`-Default |

Validierung: `terraform fmt -check` = 0, `terraform validate` = **Success** in
beiden Repos (Terraform 1.17.0, `-backend=false`).

**Kein `terraform plan` erzeugt:** Dafür wäre ein ausdrücklich freigegebener
State-/Credential-Kontext nötig. Es wurden keine Profile oder Backends geraten.

## 6. Blast Radius eines späteren Apply

Mit `enable_agent_transport = false` (Default): **0 Ressourcen**.
Mit `true`: **je 3** Ressourcen pro Repo, ausschließlich neu:

RIS: `aws_sqs_queue.dispatch`, `aws_sqs_queue.dispatch_dlq`,
`aws_sqs_queue_policy.dispatch`.
Orders: `aws_sqs_queue.results`, `aws_sqs_queue.results_dlq`,
`aws_sqs_queue_policy.results`.

Keine Änderung, kein Replace, kein Delete an bestehenden Ressourcen.
**Nicht** enthalten (bewusst): Consumer-Lambdas, IAM-Rollen, Secrets.

## 7. Secrets (I04)

Es gibt **kein** KMS-/Secrets-Manager-Modul in beiden Repos. Der HMAC-Schlüssel
(`ORDER_RESULT_SERVICE_SECRET`) müsste heute als Env-Variable verteilt werden —
das ist für den Testbetrieb vertretbar, für Produktion nicht.

Empfehlung: vorhandenes Secrets-Manager-Muster des Kontos nutzen, Secret nur den
beiden technischen Rollen lesbar, Rotation dokumentiert. **Kein neuer KMS-Key**
ohne nachgewiesenen Bedarf; SSE-SQS deckt die Queue-Verschlüsselung ab.

## 8. Sicherheit und Datenschutz

- Kein RIS-Key im Transport (A05/A07 belegt).
- Keine Nutzer-JWTs, keine Owner-Identity im Envelope.
- Kein direkter Datenbankzugriff zwischen den Systemen.
- Technische Rollen erhalten **keine** Eigentümerrechte.
- Payload-Größe begrenzt (16 KiB), Secret-Muster werden abgelehnt.
- Order-Inhalte verlassen das System nur im Envelope an die freigegebene Queue.

## 9. Tests und Validierung

| Prüfung | Ergebnis |
|---|---|
| RIS Contract-Compat | **9 passed** |
| RIS A07-E2E | 16 passed |
| RIS A05-Handoff | 10 passed |
| Orders Suite | 193 OK |
| `terraform fmt -check` (beide) | 0 |
| `terraform validate` (beide) | Success |

## 10. Kosten

Bei Dev-Volumen (wenige tausend Nachrichten/Monat) liegen die SQS-Kosten im
Cent-Bereich; DLQ-Speicher ist vernachlässigbar. Es entstehen **keine** neuen
Dauerkosten, solange die Consumer-Lambdas nicht deployed werden.

## 11. Blocker und Risiken

| # | Blocker | Wirkung |
|---|---|---|
| B1 | **Dispatch-Ingress-Lambda fehlt** (Envelope → WorkItem) | Queue würde sich füllen; RIS kann das Envelope-Format nicht direkt konsumieren |
| B2 | **Result-Consumer-Lambda fehlt** (eigene Funktion mit `result_handler.handler`) | Ergebnisse würden nicht übernommen |
| B3 | **Cross-Account-Entscheidung offen** | Rollen-ARNs/Principal und ggf. KMS nötig |
| B4 | **Secret-Verteilung** ohne Secrets-Manager-Modul | Produktion nicht freigabefähig |
| B5 | Orders-Retail-Queue ohne DLQ | vorbestehend, **nicht** Teil dieses Plans |

**Rollback:** `enable_agent_transport = false` → Plan entfernt die sechs
Ressourcen; alternativ `terraform destroy -target=module.agent_transport`
(nach Freigabe). Bestehende Ressourcen sind nicht betroffen.

## 12. STOP

Kein Apply. Vor dem Apply sind B1–B4 zu entscheiden und ein `terraform plan`
gegen einen freigegebenen State-Kontext zu erzeugen und zu reviewen.
