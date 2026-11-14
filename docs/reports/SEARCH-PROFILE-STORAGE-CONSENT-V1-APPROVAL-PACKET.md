# Search-Profile Storage Consent v1 — Approval Packet

## Status

`AWAITING OPERATOR APPROVAL OF THE SEARCH-PROFILE CONSENT TEXT`

No activation, no BFF/UI wiring, no deployment, no AWS/Terraform change and no
new ApplicationV1/CV consent version.

## 1. Exact text

| Field | Value |
| --- | --- |
| Text version | `search-profile-storage-consent-2026-11-08-v1` |
| SHA-256 | `926d1b9bbeefac4b97a5c51e3b6e6c1ed33a3affc3698e07456132be39b0f0f8` |
| Purpose | `search-profile-storage` |
| RIS notice | `search-profile-storage/1.0` (candidate, currently DRAFT) |
| Privacy policy | `/datenschutz`, version 1.1, 2026-11-07 |

Canonical text (paragraphs joined by a blank line; this is the exact text
hashed above):

Ich willige ein, dass der RIS-Speicherdienst meine manuellen Suchprofile, meine CV-Suchprofile und meine ATS-Suchprofile dauerhaft in meinem angemeldeten Konto speichert, damit ich sie später abrufen, bearbeiten, für Suchen und ATS-Analysen verwenden und löschen kann.

Gespeichert werden: Profilname, Beschreibung, Suchkonfiguration (Skills, Zielrollen, Ort, Radius, Arbeitsmodelle und Beschäftigungsarten), Matching-Präferenzen (Muss-, Wunsch- und Ausschlusskriterien), ATS-Kriterien (Zielrollen, Skills und Anforderungen), Zeitstempel und Version sowie bei CV-Suchprofilen die Referenz auf den ausgewählten dauerhaft gespeicherten CV und bei ATS-Profilen die Referenz auf das übergeordnete Suchprofil. PDF-Dateien, im Browser ausgelesene CV-Texte, KI-Prompts und Provider-Nutzlasten werden durch diese Einwilligung nicht gespeichert.

Die Speicherung erfolgt in der bestehenden RIS-Infrastruktur. Sie löst keine KI-Anfrage aus und übermittelt keine Profilinhalte an KI- oder sonstige Anbieter. Das Anlegen, Bearbeiten, Laden oder Löschen eines Profils ruft kein Modell auf.

Ich kann diese Einwilligung jederzeit mit Wirkung für die Zukunft widerrufen. Der Widerruf blockiert neue Schreibzugriffe; bereits gespeicherte Profile bleiben im Rahmen der bestehenden Rechte lesbar und löschbar. Der Widerruf ist nicht automatisch eine sofortige physische Löschung.

Gespeicherte Suchprofile bleiben bestehen, bis ich sie lösche. Sicherungen, Protokolle und gesetzliche Aufbewahrungspflichten können eine Löschung verzögern oder begrenzen.

Diese Einwilligung gilt ergänzend zu den Datenschutzhinweisen unter /datenschutz (Datenschutzrichtlinie Version 1.1 vom 7. November 2026) und ersetzt diese nicht. Sie ist getrennt von der ApplicationV1-Speicherung und der CV-Speicherung.

## 2. Scope — Option A

- Manual search profiles: durable, no CV parent.
- CV search profiles: durable only for a **durable RIS CV** with a `cvId`.
- ATS search profiles: durable only under a durable RIS CV search profile.
- Session CVs and their search/ATS profiles remain session-only until the CV
  is explicitly stored.
- No automatic CV upload and no artificial RIS CV IDs.
- No PDF/CV text/AI prompt/provider payload is stored by this consent.
- This consent is separate from `application-storage` and `cv-storage`.

## 3. Planned enforcement

- RIS purpose `search-profile-storage` with its own notice.
- Write gate for create/update of manual, CV-search and ATS profiles.
- Reads and deletion remain available after withdrawal.
- Pilot restricted by the existing confirmed-operator allowlist.
- No global enablement.

## 4. Planned implementation after approval

1. RIS consent purpose/notice, gate, tests.
2. Jobsearch BFF for manual/CV-search/ATS profile CRUD.
3. Persistence adapter for durable profiles with session fallback.
4. UI status and per-profile persistence controls.
5. Tests, auditlog, commits.
6. Separate plan/release approval.

## 5. Approval requested

Please confirm:

1. the exact text above as `search-profile-storage-consent-2026-11-08-v1`
   with SHA-256 `926d1b9bbeefac4b97a5c51e3b6e6c1ed33a3affc3698e07456132be39b0f0f8`;
2. the RIS notice `search-profile-storage/1.0` as `APPROVED` or `ACTIVE`;
3. the exact `legalApprovalRef`, approval date and approval body.

After approval I will wire the RIS notice, BFF, adapter and UI, then present a
separate activation plan. No apply/deploy occurs without the next explicit GO.
