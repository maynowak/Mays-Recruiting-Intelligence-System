# SEARCH-PROFILE-STORAGE-03 — Final Consent Packet

**Status:** `AWAITING FINAL OPERATOR CONFIRMATION — NOTICE REMAINS DRAFT`  
**Date:** 2026-11-08

No notice change, apply, deployment or live E2E was performed. This packet is
the single confirmation request for the corrected text.

## 1. Final text

| Field | Value |
| --- | --- |
| Text version | `search-profile-storage-consent-2026-11-08-v2` |
| SHA-256 | `75919c8bc219c938bdd2452a8bf02955997d1336ba2ca716bc691dd54eaa7ef6` |
| Purpose | `search-profile-storage` |
| RIS notice | `search-profile-storage/1.0` — still `DRAFT` |
| `legalApprovalRef` | `null` |
| Privacy policy | `/datenschutz`, version 1.2, 2026-11-08 |
| Proposed approval ref | `JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08` — **not yet a legal approval** |

### Full canonical text

> Ich willige ein, dass der RIS-Speicherdienst meine manuellen Suchprofile, meine CV-Suchprofile und meine ATS-Suchprofile dauerhaft in meinem angemeldeten Konto speichert, damit ich sie später abrufen, bearbeiten, für Suchen und ATS-Analysen verwenden und löschen kann.
>
> Gespeichert werden: Profilname, Beschreibung, Suchkonfiguration (Skills, Zielrollen, Ort, Radius, Arbeitsmodelle und Beschäftigungsarten), Matching-Präferenzen (Muss-, Wunsch- und Ausschlusskriterien), ATS-Kriterien (Zielrollen, Skills und Anforderungen), Zeitstempel und Version sowie bei CV-Suchprofilen die Referenz auf den ausgewählten dauerhaft gespeicherten CV und bei ATS-Profilen die Referenz auf das übergeordnete Suchprofil. PDF-Dateien, im Browser ausgelesene CV-Texte, KI-Prompts und Provider-Nutzlasten werden durch diese Einwilligung nicht gespeichert.
>
> Die dauerhafte Speicherung erfolgt über die RIS-Infrastruktur einschließlich AWS. Das Speichern, Anlegen, Bearbeiten, Laden oder Löschen eines Suchprofils löst keine KI-Anfrage aus und ruft kein Modell auf. Eine spätere Verwendung von Suchprofilen bei KI-Funktionen, insbesondere ATS-Analysen, unterliegt deren gesonderten Verarbeitungsbedingungen und kann eine Übermittlung an KI-Anbieter umfassen.
>
> Ich kann diese Einwilligung jederzeit mit Wirkung für die Zukunft widerrufen. Der Widerruf blockiert neue Schreibzugriffe; bereits gespeicherte Profile bleiben im Rahmen der bestehenden Rechte lesbar und löschbar. Der Widerruf ist nicht automatisch eine sofortige physische Löschung.
>
> Gespeicherte Suchprofile bleiben bestehen, bis ich sie lösche. Sicherungen, Protokolle und gesetzliche Aufbewahrungspflichten können eine Löschung verzögern oder begrenzen.
>
> Diese Einwilligung gilt ergänzend zu den Datenschutzhinweisen unter /datenschutz (Datenschutzrichtlinie Version 1.2 vom 8. November 2026) und ersetzt diese nicht. Sie ist getrennt von der ApplicationV1-Speicherung und der CV-Speicherung.

## 2. Compact diff against the previously read v1

Only paragraph 3 and the policy reference changed. All other paragraphs are
byte-identical.

### Paragraph 3 — removed

> Die Speicherung erfolgt in der bestehenden RIS-Infrastruktur. Sie löst keine
> KI-Anfrage aus und übermittelt keine Profilinhalte an KI- oder sonstige
> Anbieter. Das Anlegen, Bearbeiten, Laden oder Löschen eines Profils ruft kein
> Modell auf.

### Paragraph 3 — new

> Die dauerhafte Speicherung erfolgt über die RIS-Infrastruktur einschließlich
> AWS. Das Speichern, Anlegen, Bearbeiten, Laden oder Löschen eines Suchprofils
> löst keine KI-Anfrage aus und ruft kein Modell auf. Eine spätere Verwendung
> von Suchprofilen bei KI-Funktionen, insbesondere ATS-Analysen, unterliegt
> deren gesonderten Verarbeitungsbedingungen und kann eine Übermittlung an
> KI-Anbieter umfassen.

### Paragraph 6 — policy reference

> Datenschutzrichtlinie Version 1.1 vom 7. November 2026 → **Version 1.2 vom
> 8. November 2026**

No other content change.

## 3. P1 policy correction

`public/legal/datenschutz.md` and `.html` are updated to version 1.2 / 8
November 2026. §9 now states that manual, CV-search and ATS profiles are a
separate `search-profile-storage` purpose, are not covered by the
ApplicationV1 consent, are stored in RIS/AWS, and that storage/CRUD does not
trigger AI; later AI use is governed separately.

This is the only policy content change. Existing ApplicationV1/CV consent texts
remain historical v1.1 references and are not edited.

## 4. P3 open boundary

Account-level erasure does **not** currently include partner search profiles.
Implemented is per-profile deletion; withdrawal blocks writes but does not
delete existing profiles. This remains an open boundary for a later general
rollout. No erasure redesign is part of this task.

## 5. Confirmation requested

Please confirm exactly once:

1. the final text `search-profile-storage-consent-2026-11-08-v2` with SHA-256
   `75919c8bc219c938bdd2452a8bf02955997d1336ba2ca716bc691dd54eaa7ef6`;
2. the P1 policy v1.2 correction;
3. the proposed approval reference `JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08`,
   approval date and approving body.

After that confirmation the notice will be set to `APPROVED`, the real
approval fields recorded, and the apply/deploy gates can be requested. Until
then the notice stays `DRAFT`.
