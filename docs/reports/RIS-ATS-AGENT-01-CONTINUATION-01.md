# RIS-ATS-AGENT-01 — Continuation 01 (Orchestrierung)

**Datum:** 2026-11-17
**Branch:** `feature/ris-dev2-ats-agent-pinned-core-01`
**Kontext:** `ris-dev2`, Konto `262370457690`
**Status:** **SAFE LOCAL FIXES COMPLETE / PRODUCT RESULT PATH OPEN**

---

## 1. Auftrag und Vorgehen

Zwei parallele Read-only-Analysen (Subagenten) haben den öffentlichen
Partner-API-Pfad und den autorisierten ATS-Result-Abruf geprüft. Der Commander
hat daraus die sicheren, lokalen Fixes umgesetzt und die verbleibenden
Architekturentscheidungen abgegrenzt.

Kein AWS Apply, Destroy, Deployment, Merge oder Push nach `main`.

---

## 2. Befunde der Analysen

### 2.1 Öffentlicher Partner-API-Pfad

| Befund | Evidenz |
|---|---|
| Route existiert | `POST /v1/partner/agents/{agentId}/execute`, JWT + `X-Api-Credential` |
| Antwort | **202** mit `{workId,status,requestId}` — **kein** Result-Body |
| Agent-Auflösung | Agent-ID aus dem Pfad; Capability aus dem Body |
| **Kritische Lücke** | `ats-agent` fehlte im **Terraform-Catalog-Seed**; live würde die Route `403 agent-not-executable` liefern |
| `ATS_API_BASE_URL` | nicht in Terraform verdrahtet; Fallback auf die Live-URL |
| Result-Read-back | keine öffentliche Route; der alte `GET /work/{workId}` ist nicht provisioniert und liefert kein gespeichertes Result |

### 2.2 Autorisierter ATS-Result-Abruf

| Befund | Evidenz |
|---|---|
| RIS-Work-Row | enthält `result.data` mit dem ATS-Body |
| **Secret-Scan** | `analysis.metadata.titleTokens` enthält den verbotenen Teilstring `token` → Transport wird abgelehnt |
| **Kein Producer** | Nur die Demo baut ein `ORDER_RESULT`; der Worker persistiert lokal, sendet aber nichts an Orders |
| **Keine Korrelation** | Die persistierte Row enthält **kein** `orderId`/`correlationId`; `result_from_work_item` braucht das Dispatch-Envelope |
| Wrapper | Pipeline speichert `{success,data}`; der Transport erwartet den Body (`data`) |
| Orders-Reader | `GET /orders/{orderId}` prüft nur JWT, **keine** Owner-/Tenant-Bindung |
| Orders-Modul | Result-Queue/-Consumer nur bei `enable_agent_transport=true` (Default **false**) |

---

## 3. Umgesetzte lokale Fixes

### 3.1 ATS im Agent-Catalog-Seed

`terraform/modules/dynamodb/main.tf`:

```hcl
"ats-agent" = {
  agentId            = "ats-agent"
  version            = "1.0.0"
  status             = "ACTIVE"
  capabilities       = ["analyze.job"]
  supported_bodies   = ["1.0.0"]
  supported_runtimes = ["python3.14"]
  risk_level         = "low"
}
```

Test: `tests/test_agent_catalog_terraform_seed.py::test_declared_ats_agent_matches_the_runtime`.

**Wirkung:** Die öffentliche Route würde `ats-agent` nach einem Apply als
executable erkennen. **Der Apply ist nicht erfolgt.**

### 3.2 Transport-sicherer Result-Body 2.0

`ATSAnalysisResultBody` ist jetzt **2.0**. `analysis.metadata.titleTokens`
wird **nicht mehr projiziert**. Grund: Der generische Secret-Scan lehnt jeden
Schlüssel mit `token` ab; das Feld ist ein Tokenizer-Artefakt, kein Secret.
Der Scan bleibt unverändert streng.

- `agents/ats_agent/result_body.py`
- `docs/contracts/ATS-ANALYSIS-RESULT-BODY-V1.md`
- `docs/contracts/JOBSEARCH-ATS-ANALYSIS-V1.md`
- Tests: Body-/Bundle-/Fixture-Erwartungen auf 2.0

### 3.3 Tests

| Datei | Neue Fälle |
|---|---|
| `tests/test_partner_security_boundary.py` | ATS `202` + Enqueue; `403` ohne Catalog; `403` bei Profile-gebundener Entitlement-Abweichung |
| `tests/test_order_transport_contract.py` | ATS-Body round-trip; `titleTokens` wird weiterhin abgelehnt |
| `tests/test_agent_catalog_terraform_seed.py` | ATS-Seed-Parität |

### 3.4 xrepo-Draft

`docs/xrepo/MAYS-XR-ATS-001-DRAFT.md` (Commit `ff0b3ef`):
Task-ID, Richtung, Pflichtfelder, Issue-Bindung, Evidence-Regeln,
sequenzieller Ablauf. **Keine Issues, kein Dispatch.**

---

## 4. Testnachweise

| Lauf | Ergebnis |
|---|---|
| Fokussierte ATS-/Catalog-/Transport-Suite | **130 passed**, 9 skipped, 9 subtests |
| Etablierte Gesamtregression + neue Tests | **508 passed**, 8 skipped, 20 subtests |
| `terraform fmt -check` | Exit 0 |

Keine neuen Fehler. Die Änderungen sind rein lokal; die Live-Umgebung bleibt
auf Body **1.1** und ohne ATS-Catalog-Seed, bis ein kontrollierter Apply
erfolgt.

---

## 5. Verbleibende Produkt-Lücken (Entscheidung erforderlich)

| # | Lücke | Was fehlt |
|---|---|---|
| 1 | **Live-Catalog-Seed** | Terraform-Apply auf `ris-dev2` (DynamoDB-Item `ats-agent`) |
| 2 | **Result-Forwarder** | Produktiver Producer, der nach `_persist_result` ein `ORDER_RESULT` baut und an die Orders-Result-Queue sendet |
| 3 | **Korrelation** | `orderId`/`correlationId` in der Work-Row persistieren; Dispatch-Envelope für `result_from_work_item` verfügbar machen |
| 4 | **Wrapper/Body** | Pipeline speichert `{success,data}`; Transport erwartet `data` — entweder Forwarder extrahiert `data` oder Transport akzeptiert beide Formen |
| 5 | **Public Read-back** | Es gibt keine öffentliche Route für das gespeicherte ATS-Result |
| 6 | **Orders-Reader** | Owner-/Tenant-Prüfung und Field-Whitelist fehlen |
| 7 | **Orders-External** | Konto `240571105849` (403), Cross-Account-ARNs, Secret |
| 8 | **xrepo** | Issues/Handoff nach Freigabe; anderer Agent aktiv |
| 9 | **Merge** | Branch reviewfähig; kein Merge nach `main` |

---

## 6. Empfohlener nächster Entwicklungsschritt

**Ein Auftrag „ATS Result Link"** (Design + lokale Implementierung, kein
Apply):

1. `orderId`/`correlationId` in `_register_processing` persistieren.
2. Im Worker nach `_persist_result` einen `ORDER_RESULT`-Forwarder bauen:
   Body aus `result.data`, Envelope aus der Work-Row/Dispatchereihenfolge,
   SQS-Send nur wenn Queue/Secret konfiguriert.
3. Transport-Scan mit ATS-Body 2.0 testen (ohne `titleTokens`).
4. Orders-Reader: Owner-/Tenant-Prüfung + Field-Whitelist.
5. Danach separater **Apply** für Catalog-Seed + Body 2.0 + ggf.
   `enable_agent_transport`.

Das ist eine echte Architektur-/Sicherheitsentscheidung (Queue, Secret,
Cross-Account); deshalb **kein automatischer Apply** in diesem Auftrag.

---

## 7. Commits

| Commit | Inhalt |
|---|---|
| `ff0b3ef` | xrepo-Draft `MAYS-XR-ATS-001` |
| `3296b6c` | Catalog-Seed, Body 2.0, Partner-/Transport-Tests |

**Status: SAFE LOCAL FIXES COMPLETE / PRODUCT RESULT PATH OPEN.**
