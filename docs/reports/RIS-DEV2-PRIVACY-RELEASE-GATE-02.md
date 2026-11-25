# RIS-DEV2-PRIVACY-RELEASE-GATE-02

**Datum:** 2026-11-25
**Repository:** `maynowak/Mays-Recruiting-Intelligence-System`
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `383dbe724c16e0714dfddb844ab8f2297d3d9e7a`
**MO-Pin (unverändert):** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`
**Plan-Kandidat (unverändert):** `2bbf81424b9761712008ef698f5afe5bb6b5ac1db0eaa74220427e8f09b7facd`

**Verdict: READY FOR HUMAN APPLY APPROVAL — ausschließlich mit synthetischen Testdaten**

Keine Codeänderung erforderlich. Die Prüfung ergab eine **Dokumentationslücke**
(öffentliche Projektion), die in `docs/api/API-STANDARD.md` korrigiert wurde, und
eine **vorbestehende, nicht durch dieses Release eingeführte** DSAR-Lücke für
Orders (keine GSI2-Verknüpfung). Beide sind für `ris-dev2` mit synthetischen
Daten vertretbar; vor echten Personendaten ist ein separates Privacy-Gate nötig.

---

## 1. Öffentliche Reader-Antworten

Evidence: realer Reader-Request im In-Memory-E2E mit dem gepinnten MO-Stack
(`tests/test_agent_order_dispatch_e2e.py`), danach `GET /orders/{orderId}` als
Eigentümer.

| Prüfung | Ergebnis |
| --- | --- |
| Top-Level-Felder | `createdAt, currency, customer, items, orderDescription, orderId, orderType, status, totalAmount, updatedAt` |
| Strukturiertes `agentOrder` | **nicht enthalten** |
| `orderDescription` | 640 Zeichen, unverändert der serialisierte AgentOrder V1 |
| JSON-Keys darin | `input, metadata, processing, resultContract, schemaVersion, target` |
| `metadata`-Keys | `apiProfileRef, idempotencyKey, partnerApplicationRef, requestId, source` |
| Werte im Test | `source=e2e`, `requestId=corr-e2e`, `apiProfileRef=aprof-e2e`; `idempotencyKey`/`partnerApplicationRef` = `null` |
| `processing` (normalisiert) | `trigger, parentOrderId, parentWorkId, executionProfile` |
| `GET /orders` (Liste) | enthält **kein** `orderDescription`/`agentOrder` (nur Listenprojektion) |

Damit sieht der **authentifizierte Eigentümer** die von ihm selbst gesetzten
Referenzen (`apiProfileRef`, optional `partnerApplicationRef`,
`idempotencyKey`, `requestId`, `source`) sowie den normalisierten
`processing`-Block innerhalb der Beschreibung. Es sind **keine** Secrets,
fremden Referenzen oder serverseitig erzeugten IDs enthalten: der Reader
serialisiert das validierte Client-Dokument; der Validator ergänzt nur
`null`-Defaults (`idempotencyKey`, `partnerApplicationRef`) und den
nicht-sensitiven `processing`-Block.

### Abgleich mit dem dokumentierten Vertrag

`docs/api/API-STANDARD.md` führte `metadata.{apiProfileRef,partnerApplicationRef,
idempotencyKey}` und `agentOrder.processing` als „werden nie ausgeliefert“.
Über `orderDescription` werden diese Werte jedoch als Teil des opaken
Client-Texts zurückgegeben. Das ist **kein Server-Leak**, aber der Vertragstext
war für den OrderV1-Vertrag nicht präzise.

**Korrektur (Dokumentation, kein Code):** API-STANDARD unterscheidet jetzt:

- neue OrderV1-Agent-Aufträge: kein strukturiertes `agentOrder`;
  `orderDescription` ist verbatim Client-Text und kann die serialisierte
  AgentOrder samt client-gesetzter Metadaten enthalten; der Reader fügt keine
  serverseitigen Kennungen hinzu;
- Legacy-Zeilen ohne `orderDescription`: bisherige strukturierte, gefilterte
  `agentOrder`-Projektion;
- die Nicht-Auslieferungsliste gilt für strukturierte Felder.

---

## 2. Auskunft, Export, Erasure, Anonymisierung

Evidence: MO `OrderService.inspect_subject` / `export_subject` /
`erase_subject` (gepinnt `db4f9e7`) gegen eine **real erzeugte Reader-Zeile**.

| Operation | Ergebnis auf der Reader-Zeile |
| --- | --- |
| Zeilen-Keys | `agentOrder`, `orderDescription`, `ownerSubject`, `gsi3*`; **kein** `subjectId`, **kein** `gsi2pk/gsi2sk` |
| `inspect_subject(ownerSubject)` | `affectedRecords = 0`, `dataCategories = []` |
| `export_subject(ownerSubject)` | `recordCount = 0` |
| `erase_subject(PREVIEW, ANONYMIZE)` | `affectedRecords = 0` |

Ursache: die MO-Privacy-Funktionen selektieren ausschließlich über
`gsi2pk = "SUBJECT#<subject>"`. Die Reader-Zeile trägt keinen Subject-Index.

### Ist das Reader-spezifisch? Nein.

- `grep gsi2pk` im gepinnten MO-Code: **kein** Erzeugungspfad schreibt
  `gsi2pk` (nur die Privacy-Lese-/Löschpfade und `INTERNAL_FIELDS`).
- Live-Read-only-Zählung der Orders-Tabelle (`--select COUNT`, keine Werte):
  **10 Orders, 10 ohne `gsi2pk`, 0 mit `gsi2pk`, 0 mit `orderDescription`**.
- Die Dateninventur führt „Mays-Orders orders“ bereits als **REVIEW REQUIRED**.
- Der Privacy-Capability-Vertrag erlaubt RIS den MO-Privacy-Aufruf nur „wenn
  eine Order tatsächlich mit dem Subject verknüpft ist“.

Die fehlende Orders-Verknüpfung ist damit **vorbestehend für alle Orders**
(auch MO-erzeugte), nicht durch den Plan oder den Reader-Fix entstanden.

### Hypothetisch: verknüpfte Zeile (nur In-Memory, nicht live)

Mit künstlich gesetztem `subjectId`/`gsi2pk`:

| Operation | Ergebnis |
| --- | --- |
| `inspect_subject` | `affectedRecords = 1`, Kategorien `customer.name`, `customer.email`, `orderDescription` |
| `export_subject` | 1 Record mit `orderId, status, createdAt, customer, currency, totalAmount, orderDescription`; **kein** `agentOrder` |
| `erase_subject(EXECUTE, ANONYMIZE)` | 1 anonymisiert; `customer` → `ANONYMIZED`/`anonymized@example.com`; `orderDescription` entfernt |
| Danach | **`agentOrder` bleibt vorhanden, inkl. `input.data`** |

Damit ist die Anonymisierung einer verknüpften Zeile **nicht vollständig**:
die interne AgentOrder-Kopie (Eingabedaten, Referenzen) überlebt. `ERASE`
löscht dagegen die gesamte Zeile. Das ist eine MO-Semantik
(`db4f9e7`), keine Änderung dieses Fixes; sie wäre vor echten Personendaten zu
schließen (MO-Commit + neuer Pin).

---

## 3. Freigabe nur mit synthetischen Testdaten

Belege:

- `docs/testing/RIS-DEV2-PARTNER-GATEWAY-E2E-PLAYBOOK.md`:
  „**Gültigkeit:** ausschließlich `ris-dev2`, synthetische Testdaten. **Nicht**
  als Produktionsfreigabe verwenden.“
- `RIS-P20-PLATFORM-PRODUCTION-READINESS-DISCOVERY-01`: Die Plattform enthält
  ausschließlich synthetische Daten; das einzige Klarnamenfeld lag in einer
  Restzeile eines deaktivierten Testusers.
- Live-Zählung: 10 Orders, alle vom **2026-11-18** (vor dem OrderV1-Feature),
  **0** mit `orderDescription`; der neue Vertrag ist noch nicht live.
- Der Plan ändert nur Lambda-Code und führt keine Daten ein.

**Entscheidung:** `ris-dev2` darf mit diesem Plan freigegeben werden, solange
ausschließlich synthetische Testdaten verarbeitet werden. Es besteht **kein**
Personenbezug, der die fehlende Orders-DSAR-Verknüpfung akut auslösen würde.

---

## 4. Risikoentscheidung

| Risiko | Bewertung | Bedingung / Maßnahme |
| --- | --- | --- |
| `orderDescription` enthält client-gesetzte Metadaten-Referenzen | **niedrig** — nur Eigentümer, nur eigene Eingaben, keine Secrets | API-Vertrag präzisiert (dieses Gate) |
| Orders (alle, nicht nur Reader) sind nicht über `subjectId`/GSI2 verknüpft | **mittel für echte Daten**, **nicht akut** bei synthetischen Daten | Vor echten Personendaten: Verknüpfung + DSAR-Abdeckung als eigenes Gate |
| Anonymisierung lässt `agentOrder` samt `input.data` stehen | **mittel für echte Daten** | Ebenfalls Teil des Folge-Gates (MO-Änderung + neuer Pin) |
| `orderType: generic`/Retail-Zeilen mit `orderDescription` | unverändert; Export/Anonymize behandeln `orderDescription` | keine Aktion |

**Keine Codeänderung in diesem Gate:**

- Ein Entfernen der Metadaten aus `orderDescription` würde den MO-OrderV1-Vertrag
  und den RIS-Parser brechen (`metadata.requestId` ist die Korrelation).
- Eine GSI2-Verknüpfung im Reader wäre eine neue Privacy-Architektur und löst
  die Anonymize-Lücke nicht (MO lässt `agentOrder` stehen) — laut Auftrag nicht
  Teil dieses Gates.
- Der funktionierende ORDER_RESULT-Fix bleibt unangetastet.

---

## 5. Plan-Status

- Plandatei unverändert: `C:\tmp\ris-dev2-correlation-fix.tfplan`
- SHA-256 unverändert: `2bbf81424b9761712008ef698f5afe5bb6b5ac1db0eaa74220427e8f09b7facd`
- Summary erneut geprüft: **0 Add / 7 Change / 0 Destroy**, 0 Replace
- Workspace `ris-dev2`; Doku-Änderungen beeinflussen den Plan nicht.
- **Kein neuer Plan erforderlich**, da keine Code-/Terraform-Änderung.

---

## 6. Nicht ausgeführt

Kein `terraform apply`, keine AWS-Mutation, kein State-Write, kein Main-Merge,
keine MO-/Pin-Änderung. Live-Nachweise (Post-Apply-Smoke-Test des Result-Rückwegs)
bleiben offen und sind nach der Freigabe mit synthetischen Daten nachzuholen.
