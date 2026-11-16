# Jobsearch → RIS: ATS Analysis Contract V1

**Status:** contract pin · **Quelle:** `maynowak/mays-jobsearch` (live)
**Contract-Version:** `1.1` · **Contract-Commit:** `464783b936647b281df63d6dd8c18b15ad732aa3`

Die ATS-Implementierung bleibt **eine**: in Mays-Jobsearch. RIS kopiert keinen
Code, sondern nutzt den veröffentlichten HTTP-Contract. Damit bleibt die
AGPL-3.0-Grenze eine Service-Grenze.

## Endpoint

```
POST /api/ats-analysis
Content-Type: application/json
```

## Request

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `job` | ja | strukturiertes Job-Objekt |
| `profile` | nein | strukturiertes Profil (Skills etc.) |
| `ai` | nein | `{enabled, consent, model?}`; Default **aus** |

PDF-/DOCX-Extraktion ist **nicht** Teil dieses Contracts. Eingang sind
strukturierte Daten.

## Response

```json
{
  "analysis": {
    "score": 0,
    "keywordCoverage": { "overall": 0 },
    "requirementCoverage": 0,
    "profileEvidenceCoverage": 0,
    "roleMatch": null,
    "analysisStatus": "insufficient",
    "basis": {
      "requirementCount": 0,
      "titleRequirementCount": 0,
      "hasDescription": false,
      "roleMatchAvailable": false
    },
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

Statuswerte in `matches`: `MATCHED`, `PARTIAL`, `UNKNOWN`. Es gibt **keinen**
`GAP`-Status; Lücken stehen in `criticalGaps` und `UNKNOWN`-Matches.

## Scoring

| Größe | Formel |
|---|---|
| Gewichte | `critical=4`, `high=3`, `medium=2`, `low=1` |
| Partial | zählt mit **0,5** |
| `analysis.score` | `round(matched_weight / total_weight * 100)` über **Nicht-Titel**-Requirements |
| `keywordCoverage.overall` | `round((matched + partial) / total * 100)` über **Nicht-Titel**-Requirements |
| `requirementCoverage` | Alias von `keywordCoverage.overall` |
| `profileEvidenceCoverage` | Profil-Evidenz (aktuell gleicher Wert) |
| `roleMatch` | 0–100 oder `null` (Titel vs. `targetRoles`) |
| `analysisStatus` | `complete` (Beschreibung vorhanden), `limited` (ohne), `insufficient` (keine Requirements) |
| `basis` | `requirementCount`, `titleRequirementCount`, `hasDescription`, `roleMatchAvailable` |
| keine Requirements | 0 |

**Vertragsänderung 1.1:** Titel-Tokens gelten nur noch als Rollensignal. Sie
zählen nicht mehr als eigenständige Requirements, nicht als Gap und nicht in
den Score. `score` und `keywordCoverage` beziehen sich auf die tatsächlichen
Job-Requirements.

Deterministisch: 0/50/100 sind ohne Zufall oder Uhrzeit konstruierbar.

## Aktualisierung (ein Befehl)

Der Contract ist gepinnt und wird **nicht** automatisch überschrieben:

```bash
# Drift prüfen (lokal, ohne Netz)
python installer/jobsearch_api_contract.py check

# Remote-Stand holen und prüfen
python installer/jobsearch_api_contract.py check --fetch

# Nach Review auf einen neuen Commit pinnen
python installer/jobsearch_api_contract.py refresh --commit <40-char-sha>
```

`check` schlägt fehl, wenn:

- der gepinnte Commit im Clone fehlt,
- eine Datei nicht mehr dem Manifest-Hash entspricht,
- ein erwarteter Contract-Marker im Quellstand fehlt,
- der lokale/Remote-HEAD vom Pin abweicht (Drift).

`refresh` verweigert das Schreiben, wenn Marker fehlen. Das Contract-JSON wird
**nicht** automatisch geändert — eine echte Vertragsänderung bleibt ein
bewusster Review-Schritt.

Read-only-Clone (falls nicht vorhanden):

```bash
git clone https://github.com/maynowak/mays-jobsearch.git \
  installer/projects/mays_jobsearch_ats_readonly
```

## Lizenz

| Punkt | Wert |
|---|---|
| Quelle | `AGPL-3.0-only` |
| Code kopiert | **nein** |
| Nutzung | Netzwerk-Service-Grenze |
| In RIS gespeichert | nur Interface-Metadaten + Datei-Hashes |

Das Manifest (`mays-jobsearch-api.manifest.json`) hält Repo, Commit und
SHA-256 der drei Contract-Dateien fest. Es enthält keinen Quellcode.
