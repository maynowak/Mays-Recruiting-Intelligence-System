# ATSAnalysisResultBody V1

**Status:** implementiert · **Version:** `1.0`
**Quelle:** projiziert aus `MAYS-JOBSEARCH-ATS-ANALYSIS-V1` (Contract 1.1)

Der RIS-Result-Body ist eine **versionierte, RIS-eigene Projektion** der
Jobsearch-ATS-Antwort. Er enthält nur die Felder, die RIS-Consumer brauchen.
Jobsearch bleibt die einzige ATS-Implementierung.

## Position im Result-Vertrag

```json
{
  "success": true,
  "data": { "...": "ATSAnalysisResultBody V1" },
  "metrics": {
    "durationMs": 12.3,
    "workId": "…",
    "agentVersion": "1.0.0",
    "contractVersion": "1.1",
    "resultBodyVersion": "1.0"
  }
}
```

## Body

```json
{
  "bodyType": "ATSAnalysisResultBody",
  "bodyVersion": "1.0",
  "analysis": {
    "score": 50,
    "keywordCoverage": { "overall": 50 },
    "requirementCoverage": 50,
    "profileEvidenceCoverage": 50,
    "roleMatch": null,
    "analysisStatus": "limited",
    "basis": {
      "requirementCount": 2,
      "titleRequirementCount": 1,
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
    "consentGiven": false
  },
  "source": {
    "system": "mays-jobsearch",
    "contract": "MAYS-JOBSEARCH-ATS-ANALYSIS-V1",
    "contractVersion": "1.1",
    "contractCommit": "464783b936647b281df63d6dd8c18b15ad732aa3"
  },
  "jobTitle": "QA Engineer"
}
```

## Feldregeln

| Feld | Regel |
|---|---|
| `bodyType` | konstant `ATSAnalysisResultBody` |
| `bodyVersion` | `1.0`; eigener Versionszyklus, unabhängig vom API-Contract |
| `analysis.score` | int 0–100 |
| `analysis.keywordCoverage.overall` | int 0–100 |
| `analysis.requirementCoverage` | int 0–100 (Alias des API-Feldes) |
| `analysis.profileEvidenceCoverage` | int 0–100 |
| `analysis.roleMatch` | int 0–100 oder `null` |
| `analysis.analysisStatus` | `complete`, `limited`, `insufficient` |
| `analysis.basis` | vier Zähl-/Flag-Felder |
| `analysis.criticalGaps[]` | `{id,text,category,importance}` |
| `analysis.requirements[]` | `{id,text,category,importance}` |
| `analysis.matches[]` | `{requirementId,status,confidence}`; Status `MATCHED/PARTIAL/UNKNOWN` |
| `recommendations[]` | `{requirementId,changeType,priority,proposedChange,rationale,evidence}` |
| `ai` | nur bekannte Felder; fehlende optionale Felder werden weggelassen |
| `source` | System, Contract, Version, Commit — **keine** PII |
| `jobTitle` | optional, nur wenn vorhanden |

## Projektionsregeln (Data Minimization)

- **Whitelist:** Nur die oben genannten Felder werden übernommen.
- **Verworfen:** `normalized`, `source`, `explicitness` und andere interne
  Tokenizer-/Requirement-Artefakte.
- **Kein Profil-Input:** `candidateSkills` und `profile` sind **nicht** im Body.
- **Keine Roh-CVs, keine Secrets, keine Tokens.**
- Duplikate aus der API werden **nicht** stillschweigend entfernt; sie bleiben
  sichtbar (Datenqualitätsentscheidung bleibt beim Consumer).
- Zusätzliche API-Felder werden ignoriert, bis der Contract bewusst erweitert
  wird.

## Versionierung

| Änderung | Version |
|---|---|
| Additives Feld, abwärtskompatibel | minor, z. B. `1.1` |
| Feld entfernt/umbenannt oder Typ geändert | major, z. B. `2.0` |

Der Body ist unabhängig vom API-Contract versioniert: Jobsearch kann Contract
1.2 liefern, während RIS weiter Body 1.0 erzeugt, solange die Projektion
kompatibel bleibt.

## Fixtures und Tests

`tests/fixtures/ats_result_body/`:

| Fixture | Fall |
|---|---|
| `score-0-empty.json` | keine Requirements, leerer Body |
| `score-50-partial.json` | MATCHED + UNKNOWN, Empfehlung |
| `score-100-matched.json` | vollständig gematcht |
| `duplicates.json` | doppelte Requirements/Matches |
| `optional-missing.json` | fehlende optionale KI-Felder, `roleMatch: null` |

`tests/test_ats_result_body.py` prüft Projektion, Version, Quellenmetadaten,
Data-Minimization und den `success/data/metrics`-Vertrag.

## Lizenz

Der Body enthält nur Interface-Metadaten und Analyseergebnisse, keinen
Jobsearch-Quellcode. Die AGPL-Grenze bleibt eine Netzwerk-Service-Grenze.
