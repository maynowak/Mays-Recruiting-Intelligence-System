# MO-RIS-TESTED-MODULE-RECONCILIATION-01 — K01–K07

**Datum:** 2026-11-14
**Modus:** Read-only Review + lokale Tests. Kein Apply, kein Deployment, keine Migration.
**Ergebnis:** **BLOCKED WITH EVIDENCE** für das generierte Modul; lokale Integration reconciled.

---

## K01 — Git-Baseline

| Element | Wert |
|---|---|
| Integrations-Pin (dokumentiert) | `5cf50a0` (v0.5.0-rc.2) |
| Gewählte Entwicklungsbasis | `9627eb2` |
| Lambda-Diff Pin → Basis | **leer** (`git diff 5cf50a0 9627eb2 -- lambda/src` ohne Ausgabe) |
| Orders-HEAD | `2fa6900` |
| RIS-HEAD | `d35d892` |
| Änderungen der Feature-Linie | **nur additiv**, **keine Löschungen** (`--diff-filter=D` leer) |

Die Entwicklungsbasis ist lambda-identisch zum gepinnten RC2-Stand. Die
Integration erweitert diese Basis, sie ersetzt sie nicht.

---

## K02 — Nested Agent Order Contract

| Prüfung | Nachweis |
|---|---|
| `orderType = agent.execution` | Orders-Validator + RIS-Vertrag |
| verschachtelter `agentOrder` | `agents/orders/agent_order.py` (RIS) ↔ `lambda/src/agent_order.py` (Orders) |
| `target` / `input` / `metadata` / `processing` / `resultContract` | beide implementiert |
| Versionen `1` / `1.0` | beide akzeptiert, sonst abgelehnt |
| Fingerprint | `schemaVersion + target + input`, identisch auf beiden Seiten |
| Identitätsgrenzen | `metadata.*Ref` sind Referenzen, keine Autorisierung |

Cross-Repo-Vertragstests: **9 passed** (`test_mo_contract_compat.py`).
Fachliche Vertragstests: **43 passed** (`test_agent_order_body.py`).

---

## K03 — Additive Entwicklung (A04–A07)

| Gate | Nachweis | Status |
|---|---|---|
| A04 Body/Persistenz | 20 Tests, `agentOrder` intern | COMPLETE |
| Ownership | 32 Tests (P1+P2), fail-closed | COMPLETE |
| Projektion | 16 Tests, owner-only, sanitisiert | COMPLETE |
| A05 Dispatch | 18 Tests + 10 Cross-Repo | COMPLETE |
| A06 Result | 31 Tests, HMAC + Idempotenz | COMPLETE |
| A07 E2E | 16 Tests + 5 Bridge | COMPLETE (lokal) |

Frisch ausgeführt: Orders **217 OK**, RIS gezielt **73 passed**
(Body 43 + Compat 9 + A07 16 + Bridge 5).

Retail unverändert, Agent-Orders gehen nicht an den Retail-Worker,
Owner-Isolation fail-closed, `expectedWorkId` serverseitig gebunden,
Result idempotent — alles in den Tests belegt. Keine RC4-Komponente wird
vorausgesetzt.

---

## K04 — Modul-Builder und Deployment-Artefakt ⚠️

Geprüft am real generierten Modul
(`…\ris-application-persistence-v1\terraform\modules\mays_orders`):

| Frage | Befund | Bewertung |
|---|---|---|
| 1. Builder-Version / Pin | `module-builder 0.1.0`, Preset `orders-service`; RIS-Builder-Pin `1dbb0cb4…` | belegt |
| 2. Lambda-Dateien im Child-Modul | 7 Dateien: `errors, index, order_service, order_types, sqs_handler, state_machine, validation` | **Basis-Stand** |
| 3. Enthält das ZIP Agent-Order/Dispatch/Result/Ownership? | **Nein** — 7 Einträge, keines der neuen Module | **BLOCKED** |
| 4. DynamoDB-Indizes / IAM | nur `gsi1`, `gsi2`; **kein `gsi3`** (Ownership); kein Secrets-/KMS-Recht | **BLOCKED** |
| 5. Handler / Outputs / Variablen | Default `index.handler`; **kein** `result_consumer.handler` | **BLOCKED** |
| 6. Cognito MANAGED/EXTERNAL | laut Manifest unverändert (Laufzeitvariable) | OK |
| 7. Git-Modul oder lokal? | `module_mode: "local Terraform module"` — **nur lokal erzeugt** | BLOCKED für Reproduzierbarkeit |
| 8. Unveränderlicher Source-Ref? | Manifest: `source.commit = "unknown"` | **BLOCKED** |

Zusätzlich: der Builder-Pin `1dbb0cb` ist **kein Vorfahr** der Feature-Linie
(`git merge-base --is-ancestor` → not ancestor) und enthält in
`lambda/src/` nur die sieben Basisdateien.

**Kernaussage:** Das generierte Orders-Service-Modul ist **nicht** das Artefakt,
gegen das A07 getestet wurde. Es kann die Integration nicht enthalten, weil
seine Quelle den Feature-Stand nicht kennt.

---

## K05 — Integrationstest

| Ebene | Nachweis |
|---|---|
| Lokal, Feature-Code | **A07 `17 + 25 = 42`**, 16 + 5 Tests, beide Lambda-Entrypoints |
| Lokal, generiertes Modul-Artefakt | **nicht möglich** — ZIP enthält die Handler nicht |
| AWS, plan-verifiziert | RIS: 191 Creates (enabled) / 183 (default-off) |
| Live E2E | **nicht erfolgt** |

Es wird ausdrücklich **nicht** behauptet, dass das Feature-ZIP dem Modul-ZIP
entspricht. Es entspricht ihm nachweislich nicht.

---

## K06 — AWS-Umgebungen

| Element | Wert |
|---|---|
| RIS-Konto | `262370457690` (STS bestätigt) |
| Orders-Konto | `240571105849` (Datei-Evidenz, **nicht zugreifbar**) |
| RIS-Ziel | `ris-dev2` (seit 2026-11-09 abgebaut, State reconciled, serial 36) |
| Planbedeutung | 191 Creates = **Neuinstallation der RIS-Plattform**; **nicht freigegeben** |
| `ris-agent` | dokumentierte Alternative, **kein** automatisch zulässiges Ersatzziel |
| Orders-Testinstallation | State/Instanz **nicht nachgewiesen** (403) |
| Cross-Account | echte Rollen-ARNs **unbekannt**; Policies bleiben `Principal: []` (fail-closed) |

Keine Wildcards, keine erfundenen Principals.

---

## K07 — Review-Matrix

| Punkt | Nachweis | Status |
|---|---|---|
| Ursprünglicher Modul-Pin | `5cf50a0` | dokumentiert |
| Entwicklungsbasis | `9627eb2` (lambda-identisch) | **PASS** |
| A04–A07-Kompatibilität | 217 Orders + 73 RIS | **PASS** |
| Builder-/Modul-Version | 0.1.0 / `1dbb0cb` | belegt |
| Generierte Lambda-Artefakte | 7 Basisdateien, keine Integration | **BLOCKED** |
| RIS-Vertragskompatibilität | 9 + 43 Tests | **PASS** |
| Testnachweise | lokal vollständig | **PASS** |
| AWS-Konto/State | RIS ja, Orders nein | **PARTIAL** |
| Cross-Account | ARNs fehlen | **BLOCKED** |
| Ressourcen-Diffs | RIS 8 / 183 / 191 | belegt |

### Vier Stufen, sauber getrennt

| Stufe | Status |
|---|---|
| 1. Lokale Integration vollständig | **JA** |
| 2. Generiertes Modul integrationsgetestet | **NEIN** |
| 3. AWS-Infrastruktur planverifiziert | **RIS ja, Orders nein** |
| 4. Live E2E | **NEIN** |

---

## Blocker und Wege

| # | Blocker | Lösung |
|---|---|---|
| B1 | Builder-Quelle kennt den Feature-Stand nicht | Builder-Pin auf einen Commit setzen, der A04–A07 enthält (Branch `feature/mo-agent-order-body-01`, HEAD `2fa6900`), dann Modul neu bauen |
| B2 | Manifest ohne Source-Commit (`unknown`) | Builder muss den Commit schreiben; sonst keine Reproduzierbarkeit |
| B3 | Generiertes Modul nur lokal, nicht als Git-Modul | Entscheidung: Modul als versioniertes Artefakt oder Build-at-apply |
| B4 | `gsi3`/Result-Handler fehlen im Modul | folgt aus B1 |
| B5 | Orders-Konto nicht zugreifbar | Profil/Zugang für `240571105849` |
| B6 | Cross-Account-ARNs unbekannt | aus dem Orders-Konto liefern |

**Empfehlung:** B1 und B2 zuerst. Ein Modul, das den Feature-Code nicht enthält,
kann nicht „integrationsgetestet" sein — unabhängig davon, wie grün die lokalen
Tests sind.

**Status: BLOCKED WITH EVIDENCE** (Modul-Artefakt), lokale Integration reconciled.
