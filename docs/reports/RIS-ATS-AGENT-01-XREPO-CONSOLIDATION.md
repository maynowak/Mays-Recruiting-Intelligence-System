# RIS-ATS-AGENT-01 — XREPO-Konsolidierung (Entscheidung)

**Datum:** 2026-11-16
**Branch:** `feature/ris-dev2-ats-agent-pinned-core-01`
**Status:** **DECISION RECORDED** — keine Codeänderung in diesem Schritt.

---

## 1. Ziel

Es soll **eine** ATS-Implementierung geben. Jobsearch hat sie für Benutzer
entwickelt und live getestet. RIS soll diese Arbeit **konsumieren**, nicht
duplizieren.

Damit ist der ursprüngliche ORCH-02-Ansatz (Vendor/Kopie des ATS-Cores oder
Python-Port) **überholt**.

---

## 2. Befund

| Prüfung | Ergebnis |
|---|---|
| Jobsearch HEAD (read-only) | `a5640d12dba8ca39258484f5212def17eabf4eca` (2026-11-13) |
| ATS-Endpoint | `POST /api/ats-analysis` (live, von Jobsearch betrieben) |
| Jobsearch-Lizenz | **AGPL-3.0-only** |
| ATS-Core-Autoren | nur `maynowak` (22 Commits) |
| RIS `ats_agent` | ruft den Endpoint bereits auf (`ATS_API_BASE_URL`) |
| RIS-Fachlogik | keine — reine Delegation |
| xrepo-Protokoll | `MAYS-XREPO-V1`, Allowlist = RIS + `mays-jobsearch` |

Das separate Repository `maynowak/mays-xrepo-orchestration` enthält nur
`README.md` (Titel) und `LICENSE` (GPLv3). Die **funktionierende**
xrepo-Implementierung liegt in RIS: `docs/xrepo/MAYS-XREPO-V1.md` und
`scripts/xrepo/`.

Bereits aktive xrepo-Tasks (Open Issues):

| Task | RIS | Jobsearch |
|---|---|---|
| `MAYS-XR-E2E-001` | Issue 7 | Issue 3 |
| `MAYS-SCV-RC3-001` | Issue 8 | Issue 17 |

Ein weiterer Agent arbeitet dort. **Kein paralleler Dispatch, kein Überschreiben
fremder Task-Zustände.**

---

## 3. Entscheidung

1. **ATS bleibt in Jobsearch.** Kein Vendor-Pin, kein Python-Port, kein npm-Paket.
2. **RIS integriert über den HTTP-Contract**, gepinnt durch:
   - Source-Commit `a5640d12…` als Contract-Referenz,
   - Endpoint `POST /api/ats-analysis`,
   - dokumentiertes Request-/Response-Schema (ORCH-01-Snapshot),
   - fail-closed Client-Validierung,
   - explizite Timeouts und Fehlerklassen,
   - Contract-Fixtures aus dem gepinnten Stand.
3. **AGPL bleibt eine Service-Grenze.** Es wird kein AGPL-Code kopiert; damit
   entsteht keine Copyleft-Übertragung auf RIS.
4. **xrepo ist der Koordinationskanal**, nicht der Code-Transport. Ein neuer
   Task `MAYS-XR-ATS-001` wäre der saubere Weg — Issue-Erstellung und Dispatch
   erst nach ausdrücklicher Freigabe und sequenziell.

---

## 4. Was sich am ORCH-Plan ändert

| Gate | Vorher | Jetzt |
|---|---|---|
| ORCH-02 | Vendor-/Core-Adapter mit Manifest | **Contract-Pin**: Commit, Endpoint, Schema, Fixtures, Client-Validator |
| ORCH-03 | lokaler ATS-Core + Node-/Python-Grenze | **Client-Härtung**: Schema-Check, Timeouts, Fehler-Mapping; keine Fachlogik in RIS |
| ORCH-04 | `ATSAnalysisResultBody V1` | **unverändert sinnvoll** — Body aus den API-Feldern ableiten |
| ORCH-05 | Integration/Regression | unverändert (ohne Cloud-Tests als lokal auszugeben) |
| ORCH-06 | Handoff | unverändert |

---

## 5. Risiken und Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| Drift der Live-API | Commit-Pin + Schema-Validierung + Contract-Tests; bei Abweichung fail-closed |
| Ausfall/Latenz | Timeout, definierte Fehlerklasse, kein stiller Fallback auf alte Daten |
| AGPL-Copyleft | kein Code-Kopie-Transfer; nur Service-Nutzung |
| xrepo-Kollision | neuer Task, sequenzielle Übergabe, kein Parallel-Dispatch |
| „Live getestet" als Beweis überschätzt | Live-Test bleibt Jobsearch-Evidenz; RIS belegt nur seinen Contract-Test |

---

## 6. Nächster Schritt

**ORCH-02 (revised) — Contract-Pin, kein Vendor:**

1. Fixtures für `0 / 50 / 100`, Duplikate, fehlende optionale Felder.
2. Client-seitiger Schema-Validator für `analysis`, `recommendations`, `ai`.
3. Contract-Test gegen die Fixtures; optional ein env-gated Live-Smoke.
4. Dokumentierte Fehlerklassen: Timeout, 4xx, 5xx, Schema-Mismatch.

Erst danach ORCH-03 (Agent-Härtung). Kein Push, kein Merge, keine AWS-Aktion.
