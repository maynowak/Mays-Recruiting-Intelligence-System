# JM-CV-UX-08 — CV DELETE FIX & CARD UX

**Status:** `A — RELEASE APPROVAL PENDING — PR #37 CLEAN`
**Jobsearch branch:** `feature/jm-cv-ux-08-cv-delete-ux`
**Base:** previous CV fix branch `feature/jm-cv-ux-07-persistence-delete-editor-return` (`04ef910`)
**Code:** `bce210c`
**PR:** [#37](https://github.com/maynowak/mays-jobsearch/pull/37) — Draft, `MERGEABLE` / `CLEAN`
**No Main merge, no Production deployment, no RIS/AWS/Cognito/Terraform/Consent change.**

## 1. Delete-Verhalten

### Ursache des sichtbaren Fehlers

Der RIS-Delete-Pfad unterscheidet mehrere 409-Fälle. Die bisherige
Jobsearch-Anzeige behandelte jeden 409 pauschal als:

```text
"Der Lebenslauf wurde zwischenzeitlich geändert."
```

Damit wurde insbesondere ein **Child-Profile-Konflikt** als falscher
Versionskonflikt angezeigt. Der RIS-BFF liefert bei einem Delete ohne
S3-Berührung jetzt den getrennten Code:

```text
CV_HAS_CHILD_PROFILES
```

Die UI zeigt dafür:

> Der Lebenslauf wird noch von Such- oder ATS-Profilen verwendet.
> Bitte lösche zuerst diese Profile; der Lebenslauf bleibt erhalten.

Ein echter 409 aktualisiert die Liste, zeigt eine verständliche Meldung und
startet **keinen automatischen Delete-Retry**.

### Erfolgreicher Delete

Der bestehende Pfad bleibt:

```text
PersistentCvList
  -> usePersistentCvStorage.remove(cvId)
  -> DELETE /api/ris/cvs?id=...
  -> Antwort prüfen
  -> Karte sofort lokal entfernen
  -> Liste über RIS refresh synchronisieren
```

Die Karte verschwindet erst nach erfolgreicher Serverantwort. Bei 404/409
wird die Liste neu geladen; bei Fehler bleibt die Karte erhalten.

## 2. X und dauerhaftes Löschen

Die Aktionen sind jetzt getrennt:

| Aktion | Verhalten |
|---|---|
| **X** oben rechts | Entfernt die Karte nur aus der aktuellen Ansicht; kein API-Aufruf, nach Reload wieder sichtbar |
| **Löschen** in den Kartenaktionen | Öffnet die separate Bestätigung |
| **Dauerhaft löschen** | Ruft den bestehenden RIS-Delete-Pfad auf |

X:

- 40 × 40 px Klickfläche
- 24-px-Icon
- sichtbarer Fokus-/Hover-Zustand
- `aria-label` und Tooltip
- semantisch getrennt von dauerhaftem Löschen

Bestätigung:

- zeigt den Dateinamen
- „Abbrechen“ ohne API-Aufruf
- „Dauerhaft löschen“ nur nach ausdrücklicher Bestätigung

## 3. Editor-Return

Der vorherige Root-Cause-Fix bleibt erhalten:

```text
handleProcessPersistentCv
  -> kein automatischer Wechsel auf cvStorageMode="session"
```

Damit bleibt die persistente Liste nach dem PDF-Download/Editor-Handoff
sichtbar. Der Regressionstest aus `JM-CV-UX-07` bleibt bestehen.

## 4. Tests

Fokussiert:

```text
PersistentCvList + usePersistentCvStorage + Persistence + BFF: 36 PASS
```

Abgedeckt:

- X blendet nur lokal aus, kein Delete
- Reload holt die Karte zurück
- Abbrechen ohne API
- erfolgreicher Delete
- Delete-Fehler mit sichtbarer Meldung
- Child-Profile-Code getrennt vom Versionskonflikt
- 409-Refresh ohne automatischen Retry
- BFF-Mapping `s3Touched=false -> CV_HAS_CHILD_PROFILES`

Gesamt:

```text
npm run build:                  PASS
npx vitest run --maxWorkers=2:  1964 PASS / 11 skipped
profile-ux-final E2E:           PASS
```

Browser-E2E (lokal, synthetische Session/Mock-API):

```text
X hide without delete:          PASS
Reload returns card:            PASS
Confirmed durable delete:       PASS
Responsive 320–1024:             PASS / 0 overflow / 44-px toggle
```

Produktive CV-Löschung wurde in diesem UI-Auftrag nicht ausgeführt; der
separate RIS-IAM-/Delete-E2E ist bereits als
`PILOT LIVE VERIFIED — CV CREATE / DOWNLOAD / DELETE` dokumentiert.

## 5. RIS

Es war **keine RIS-Änderung** erforderlich. Der bestehende Delete-Endpunkt
und die IAM-Permission `dynamodb:ConditionCheckItem` sind aktiv; die
Jobsearch-Schicht klassifiziert den vorhandenen 409-Vertrag nur genauer.
Der frühere IAM-Plan ist angewendet; keine weitere Infrastrukturänderung.

## 6. Dokumentation / Grenzen

- Keine echten Bewerberdaten, keine Tokens in Tests/Reports.
- Keine Änderung an RIS, AWS, Cognito, Terraform oder Consent-Gates.
- Kein Main-Merge, kein Production-Deployment.
- X ist ausschließlich eine lokale Ansichtsaktion.

**Ergebnis:** `A — IMPLEMENTED & VERIFIED — READY FOR CONTROLLED INTEGRATION`

## 7. Controlled Integration Preflight (2026-11-18)

**Status:** `A — RELEASE APPROVAL PENDING — PR #37 CLEAN`

- `origin/main`: `6fc40d2` (Merge PR #36)
- Merge-Base: `6fc40d2`; branch is **0 behind / 7 ahead** of `origin/main`
- No conflicts; fast-forward/mergeable
- PR: [#37](https://github.com/maynowak/mays-jobsearch/pull/37), still **Draft**
- GitHub checks:
  - CodeQL Analysis: **PASS**
  - Vercel – mays-job-matcher Preview: **PASS**
  - Vercel – mays-jobsearch Preview: **PASS**
  - Vercel Deployments – Maymilly: **PASS**
- Local verification on the final branch:
  - `npm run build`: **PASS**
  - Full frontend suite: **1964 PASS / 11 skipped**
  - `node --check api/_lib/ris/cvsHandler.mjs`: **PASS**
  - `git diff --check`: **PASS**
- Preview deployments are not Production; no real CV data or tokens were used.

### Deployment impact

`vercel.json` sets:

```json
"git": { "deploymentEnabled": { "main": true } }
```

Therefore a merge to `main` starts **automatic Production deployments** for
both Vercel projects. No manual `vercel --prod` is planned. The release
approval must explicitly cover both:

1. merge of PR #37 into `main`, and
2. the resulting automatic Production deployment.

### Rollback

No schema, data migration, RIS, AWS, Cognito, Terraform or consent change.
Rollback is a revert of the merge commit or re-promotion of the previous
Production deployment. The existing RIS CV delete contract remains unchanged.

### Required approval

**STOP — no merge and no Production deployment until explicit release
approval is given.** After approval: merge PR #37, verify Production build
identity and run the authenticated synthetic E2E:

- X hides a card without an API delete
- reload restores the card
- permanent delete requires confirmation
- successful delete removes the card
- child-profile conflict shows the correct message
