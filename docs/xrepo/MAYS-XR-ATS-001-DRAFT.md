# MAYS-XR-ATS-001 — Draft (kein Dispatch)

**Status:** DRAFT · **Keine Issues angelegt · Kein `repository_dispatch`**
**Datum:** 2026-11-17

## Zweck

Koordination der ATS-Contract-Änderungen zwischen
`maynowak/mays-jobsearch` (Contract-Eigentümer) und
`maynowak/Mays-Recruiting-Intelligence-System` (Consumer), ohne die
bestehenden Tasks `MAYS-XR-E2E-001` oder `MAYS-SCV-RC3-001` zu berühren.

## Vorgeschlagene Task-ID

```
MAYS-XR-ATS-001
```

## Richtung

| Fall | Source | Destination | Startstatus |
|---|---|---|---|
| Jobsearch ändert den ATS-Contract | Jobsearch-Issue | RIS-Issue | `IMPLEMENTATION_READY` |
| RIS fordert eine Contract-Änderung | RIS-Issue | Jobsearch-Issue | `REQUESTED` |

Für den aktuellen Stand (Contract 1.2, Commit `8456910`) ist die
Jobsearch→RIS-Richtung maßgeblich: Jobsearch liefert die Änderung, RIS
integriert und verifiziert.

## Pflichtfelder des Events

| Feld | Wert |
|---|---|
| `protocol` | `MAYS-XREPO-V1` |
| `taskId` | `MAYS-XR-ATS-001` |
| `eventId` | UUIDv4 |
| `status` | `REQUESTED` … `COMPLETED` |
| `source.repository` | `maynowak/mays-jobsearch` |
| `source.issue` | neu anzulegendes Issue |
| `source.commit` | voller 40-stelliger SHA |
| `destination.repository` | `maynowak/Mays-Recruiting-Intelligence-System` |
| `destination.issue` | neu anzulegendes Issue |
| `summary` | ≤ 500 Zeichen |
| `evidence` | ≤ 10 Einträge; Commit/Test/Issue/Document/Workflow |
| `sequence` | Start 1, monoton |

## Bindung und Sicherheit

- Beide Issues müssen die **exakte Task-ID** als eigenständiges Token
  enthalten und sich gegenseitig referenzieren.
- Nur Kommentare von `github-actions[bot]` gelten als vertrauenswürdige
  Marker; gewöhnlicher Text ist kein Zustand.
- `IMPLEMENTATION_READY`, `VERIFIED`, `COMPLETED` benötigen Commit-Evidenz,
  deren URL exakt zu `source.commit` passt.
- Kein paralleler Dispatch. Der Ablauf ist **sequenziell**; bei einem
  History-Konflikt wird fail-closed gestoppt.
- Kein Payload wird als Shell ausgeführt; keine Secrets/PII im Event.

## Aktueller Stand

- Contract-Pin: `8456910a9ae64f51ec4a33ea1e9e82068f82bfff`
- Contract-Version: `1.2`
- Result-Body: `ATSAnalysisResultBody` 1.1
- Live-E2E in `ris-dev2`: ATS `COMPLETED`, Addition `42`, Duplikat `true`
- Anderer Agent arbeitet in xrepo; **keine** Issues/kein Dispatch ohne
  ausdrückliche Freigabe.

## Nächster Schritt (nach Freigabe)

1. Zwei Issues mit `MAYS-XR-ATS-001` anlegen und gegenseitig verlinken.
2. `xrepo-send.yml` mit `REQUESTED`/`IMPLEMENTATION_READY` starten.
3. Antwort abwarten, dann sequenziell `INTEGRATING`/`VERIFIED`.
4. Kein `COMPLETED` ohne `VERIFIED` und Commit-Evidenz.

**Keine Aktion in diesem Draft.**
