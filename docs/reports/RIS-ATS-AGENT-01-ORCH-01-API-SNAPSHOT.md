# RIS-ATS-AGENT-01 — ORCH-01 Jobsearch-ATS-API Snapshot

**Datum:** 2026-11-15
**Gate:** ORCH-01 (read-only Abholung)
**RIS-Branch:** `feature/ris-dev2-ats-agent-pinned-core-01`
**Jobsearch-Quelle:** `https://github.com/maynowak/mays-jobsearch.git`
**Verifizierter HEAD:** `a5640d12dba8ca39258484f5212def17eabf4eca`
**Commit-Datum:** 2026-11-13 19:27:05 +0100
**Subject:** `Merge pull request #18 from maynowak/feature/mays-xrepo-shared-state-reconciliation-02`

Read-only-Clone: `installer/projects/mays_jobsearch_ats_readonly`
(gitignored, keine Mutation). Arbeitsbaum sauber.

---

## 1. Aktualitätsprüfung

| Prüfung | Ergebnis |
|---|---|
| Frischer `git clone` / HEAD gelesen | `a5640d12…` |
| Plan-Baseline `a5640d12…` | **stimmt überein** |
| Historischer RIS-Pin `29d8b730…` | existiert, ist **Vorfahr** von `a5640d12…` |
| Jobsearch-Mutation | **keine** (kein Branch/Tag/Commit/Patch) |

Der historische Pin `29d8b730` ist **nicht** der aktuelle ATS-Stand und bleibt in
`installer/mays-jobsearch-clone.pinned.json` als historische Referenz erhalten.

---

## 2. Dateien und Importgraph

| Datei | Zeilen | Rolle |
|---|---|---|
| `api/ats-analysis.mjs` | 252 | HTTP-Handler, Request-Validierung, Response-Form |
| `api/_lib/ats.mjs` | 792 | deterministische ATS-Analyse, Matching, Empfehlungen |
| `api/_lib/filter.mjs` | 262 | Tokenisierung, HTML/Text, Sprach- und Skill-Filter |

Importe:

```
api/ats-analysis.mjs
  -> ./_lib/filter.mjs   (HttpError)
  -> ./_lib/ai.mjs       (chat)
  -> ./_lib/ats.mjs      (Analyse-Funktionen)
  -> ./_lib/config.mjs   (getConfig)

api/_lib/ats.mjs
  -> ./filter.mjs        (tokenize, stripHtml, htmlToPlainText, detectLanguage)

api/_lib/filter.mjs
  -> keine internen Importe
```

Transitive Abhängigkeiten sind damit auf `filter.mjs`, `ai.mjs`, `config.mjs`
und deren eigene Importe begrenzt. `ai.mjs`/`config.mjs` sind für die
**deterministische** Analyse nicht erforderlich; sie werden nur für den
optionalen KI-Zweig geladen.

---

## 3. Request-Vertrag

| Element | Befund |
|---|---|
| Methode | `POST` (OPTIONS → 204, sonst 405) |
| Body | `{ job, profile?, ai? }` |
| Validierung | `validateRequest(body)`; fehlendes/ungültiges `job` → 400 |
| CORS | `Access-Control-Allow-Origin: *` |
| Dokument-/PDF-Eingang | **nicht vorhanden** — nur strukturierte `job`/`profile`-Objekte |

---

## 4. Response-Vertrag (tatsächlich)

```json
{
  "analysis": {
    "score": 0,
    "keywordCoverage": { "overall": 0 },
    "criticalGaps": [],
    "requirements": [
      { "id": "tag_0", "text": "Python", "category": "skill", "importance": "high" }
    ],
    "matches": [
      { "requirementId": "tag_0", "status": "MATCHED", "confidence": "HIGH" }
    ]
  },
  "recommendations": [
    {
      "requirementId": "tag_0",
      "changeType": "add_skill",
      "priority": "high",
      "proposedChange": "…",
      "rationale": "…",
      "evidence": []
    }
  ],
  "ai": {
    "requested": false,
    "executed": false,
    "consentRequired": true,
    "consentGiven": false,
    "provider": null,
    "model": null,
    "externalProcessing": false,
    "dataMinimized": false,
    "privacyStatus": null,
    "dataCategories": [],
    "privacyPolicy": null,
    "formulations": []
  }
}
```

### Feldmatrix

| Feld | Typ | Herkunft / Semantik |
|---|---|---|
| `analysis.score` | int 0–100 | `scores.overall`; importance-weighted |
| `analysis.keywordCoverage.overall` | int 0–100 | `scores.keywordMatch`; `(matched+partial)/total` |
| `analysis.criticalGaps` | array | Requirement-Objekte mit Importance ≥ `high` bei Widerspruch/fehlender Evidenz |
| `analysis.requirements[]` | `{id,text,category,importance}` | Handler reduziert das interne Requirement-Objekt |
| `analysis.matches[]` | `{requirementId,status,confidence}` | Status ∈ `MATCHED`, `PARTIAL`, `UNKNOWN` |
| `recommendations[]` | `{requirementId,changeType,priority,proposedChange,rationale,evidence}` | aus `generateCVRecommendations` |
| `ai.*` | Objekt | Default deaktiviert; nur bei `enabled && consent` ausgeführt |

**Wichtig:** Es gibt **keinen** `GAP`-Status in `matches`; Lücken werden über
`criticalGaps` und `UNKNOWN`-Matches ausgedrückt.

---

## 5. Scoring-Semantik

Gewichte: `critical=4`, `high=3`, `medium=2`, `low=1`.

```
overall        = round(matchedWeight / totalWeight * 100)
keywordCoverage = round((matched + partial) / total * 100)   # 0 wenn total=0
```

- `PARTIAL` zählt mit **0.5** Gewicht.
- `0`, `50`, `100` sind damit deterministisch konstruierbar
  (keine Requirements / Hälfte partial / alle matched).
- Kein Zufall, keine Uhrzeit, kein LLM im deterministischen Pfad.

---

## 6. Änderungen seit dem historischen Pin `29d8b730`

| Datei | Diff `29d8b730..HEAD` |
|---|---|
| `api/ats-analysis.mjs` | unverändert |
| `api/_lib/ats.mjs` | +77 Zeilen netto |
| `api/_lib/filter.mjs` | +47 / −21 |

Commits, die ATS-Dateien berühren:

| Commit | Bedeutung |
|---|---|
| `c186619` | semantische Normalisierung + Metadatenfilter |
| `4fb852b` | UI-Polish-Report zur Skill-Angleichung (Doku) |
| `8456b1d` | gruppierte ATS-Begriffe bleiben erhalten |

Damit bestätigt sich der Planbefund: der API-Handler allein ist **nicht** der
vollständige Stand; die Änderungen liegen in `ats.mjs` und `filter.mjs`.

---

## 7. Tests und UI-Vertrag

| Artefakt | Rolle |
|---|---|
| `tests/api/ats-analysis.test.js` | Response-Form, AI-Consent, Datenminimierung, PII |
| `tests/api/ats-extraction.test.js` | Requirement-Extraktion |
| `tests/api/ats-model-selection.test.mjs` | Modellwahl im KI-Zweig |
| `tests/api/filter.test.js` | Tokenisierung/Filter |
| `src/components/AtsOverlay.test.tsx` | UI erwartet `score`, `keywordCoverage.overall`, `criticalGaps`, `requirements`, `matches`, `recommendations` |
| `src/components/AtsOverlay.tsx`, `ATSDetails.tsx` | Darstellung |

UI-Fixtures verwenden u. a. `score: 75` / `keywordCoverage.overall: 75` und
`25`/`25`. Die Darstellung ist an genau die oben genannten Felder gebunden.

---

## 8. Abgleich mit dem aktuellen RIS-`ats_agent`

| Aspekt | Ist (RIS) | Ziel (ORCH-03/04) |
|---|---|---|
| Datenquelle | HTTP `POST /api/ats-analysis` gegen veränderlichen Dienst | lokaler, gepinnter ATS-Core |
| Ergebnis | `{success, data:{analysis:<ganze Antwort>, jobTitle, candidateSkills}}` | versionierter `ATSAnalysisResultBody V1` |
| Agent-ID / Capability | `ats-agent` / `analyze.job` | unverändert |
| Runtime | bestehende AgentBase/Pipeline | unverändert |
| KI | HTTP-Dienst entscheidet | Default aus; eigener Consent-Gate |

Der aktuelle RIS-Agent reicht die Jobsearch-Antwort **unverändert** unter
`data.analysis` durch. Eine typisierte Body-Definition existiert noch nicht.

---

## 9. Grenzen dieses Snapshots

- Keine Aussage über PDF-/DOCX-Extraktion: die API nimmt ausschließlich
  strukturierte `job`/`profile`-Daten.
- Keine Aussage über einen npm-Paket-Release: es gibt kein belegtes
  eigenständiges Paket; das ist Gegenstand von ORCH-02.
- Keine Cloud-/Deploy-Aussage.
- Keine Jobsearch-Mutation.

---

## 10. Nächster Schritt

**ORCH-02** — Paketstrategie und unveränderlicher Source-Pin:

1. Prüfen, ob der ATS-Core als eigenständiges Paket nutzbar ist.
2. Falls nicht: minimaler Vendor-/Core-Adapter ausschließlich im RIS-Buildpfad
   aus `a5640d12…` und den tatsächlichen Importen.
3. Manifest mit Repo, vollem SHA, Datei-/Artefakt-Hash, Buildkommando,
   Lizenz/NOTICE und Runtime-Anforderungen.
4. Zweimal bauen, SHA vergleichen, echte Artefakt-Tests.

**Status: ORCH-01 COMPLETE (read-only).** Kein Push.
