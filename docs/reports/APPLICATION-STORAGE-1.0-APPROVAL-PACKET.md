# APPLICATION-STORAGE-1.0 — APPROVAL PACKET

**Status:** `APPROVED — LIMITED BETA PILOT ONLY` (no general rollout)
**Approval date:** 2026-11-08
**Approval body:** Betreiberin May's Job Matcher
**Approval reference:** `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08`
**Date:** 2026-11-07 (packet), 2026-11-08 (approval)
**Purpose:** record the approved v4 text, identifiers, data categories,
retention facts and open decisions for the RIS consent notice
`application-storage/1.0`, scoped to the limited beta pilot.
**Owner of the decision:** RIS operator + legal reviewer (not the engineering
agents).

**Repositories / baselines**

| Side | Branch | Commit |
| --- | --- | --- |
| RIS | `feature/jm-ris-storage-activation-01` | `197fb1c` |
| Jobsearch | `feature/jm-ris-storage-activation-01` | code `5ac025f` (v4 text; docs include the same commit) |

> The approval is **limited to the beta pilot**. It is not `ACTIVE`, not a
> general rollout, and does not resolve the open account-deletion,
> consent-history-retention or DPA/transfer checks. No deployment, flag or
> environment change is made by this document.

---

## 1. Critical finding

1. The RIS draft `docs/privacy/RIS-JOBSEARCH-PRIVACY-NOTICE-DRAFT-V1.md` is
   explicitly marked **"Arbeitsentwurf — nicht juristisch freigegeben, nicht
   veröffentlichen"** and covers **Profil-, CV- und Suchprofildaten**, not
   ApplicationV1 application/cover-letter storage. It cannot serve as the
   application-storage consent notice as-is.
2. Supporting material exists in the Jobsearch public policy **§9**
   (`public/legal/datenschutz.md`, v1.1, 2026-11-07) and the Jobsearch UI
   strings; both are privacy *notice/description* material, not by themselves
   the consent declaration.
3. **A complete declaration exists and is approved for the limited beta pilot,
   with a real `legalApprovalRef` and a RIS `1.0` mapping.** Candidate D
   (§3.4, Jobsearch `src/lib/applicationStorageConsent.ts` /
   `api/_lib/ris/consentText.mjs`, commit `5ac025f`) is the approved v4
   first-person declaration (explicit Art. 9 consent incl. Sexualleben/
   sexuelle Orientierung, no inference). Approval: 2026-11-08,
   Betreiberin May's Job Matcher, reference
   `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08`. It is `APPROVED`, **not**
   `ACTIVE`; no general rollout. The previous v3/v2/v1 texts are historical and
   superseded.
4. The RIS processing-purpose and retention matrices
   (`RIS-JOBSEARCH-PROCESSING-PURPOSES-V1.md`,
   `RIS-JOBSEARCH-RETENTION-POLICY-V1.md`) contain **no ApplicationV1
   application/cover-letter row**. Their rows cover profile, CV, search-profile
   and technical data only.
5. Therefore notice `application-storage/1.0` must stay `DRAFT` with
   `legalApprovalRef = null` until an approved declaration, an approved
   retention rule for ApplicationV1 and an approved RIS↔Jobsearch version
   mapping exist.

---

## 2. Version identifiers (exact)

| Side | Identifier | State | Mapping |
| --- | --- | --- | --- |
| RIS purpose | `application-storage` | — | — |
| RIS notice version | `application-storage` / `1.0` | `APPROVED` (pilot), `legalApprovalRef = JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` | `1.0` |
| Jobsearch ApplicationV1 text version | `application-storage-consent-2026-11-07-v4` | `APPROVED` (candidate D, §3.4) | `1.0` (pilot) |
| Jobsearch ApplicationV1 text SHA-256 | `8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7` | — | — |
| Jobsearch historical text version (v3) | `application-storage-consent-2026-11-07-v3` | `DRAFT`, superseded by v4 | **none** |
| Jobsearch historical text version (v2) | `application-storage-consent-2026-11-07-v2` | `DRAFT`, superseded by v3 | **none** |
| Jobsearch historical text version (v1) | `application-storage-consent-2026-11-07-v1` | `DRAFT`, superseded by v2 | **none** |
| Jobsearch legacy text version | `STORAGE_CONSENT_TEXT_VERSION = "2026-11-04-draft-1"` | DRAFT | **none** |
| Jobsearch legacy privacy-notice version | `STORAGE_CONSENT_PRIVACY_NOTICE_VERSION = "2026-11-04-draft-1"` | DRAFT | **none** |

Sources: `jobsearch/consent_contract.py` (`NOTICE_REGISTRY`,
`EXTERNAL_NOTICE_REFS`); Jobsearch `src/lib/applicationStorageConsent.ts` and
`api/_lib/ris/consentText.mjs` at commit `5ac025f`.

`application-storage-consent-2026-11-07-v4` is current. The earlier
`...-v3`, `...-v2` and `...-v1` remain historical/superseded, and
`2026-11-04-draft-1` remains a legacy draft. All are known to RIS as external
references but are never accepted as a `noticeVersion`. Renaming an identifier,
or matching a hash, is not an approval. A mapping to `1.0` requires a separate,
documented operator/legal decision. Only v4 can back an Art. 9 consent.

---

## 3. Candidate texts (verbatim quotes only — no invented wording)

### 3.1 Candidate A — RIS internal draft (not ApplicationV1-specific)

Source: `docs/privacy/RIS-JOBSEARCH-PRIVACY-NOTICE-DRAFT-V1.md`
(`Version: 1.0-draft · 2026-11-01`).

> **Arbeitsentwurf — nicht juristisch freigegeben, nicht veröffentlichen**
>
> Dieser Entwurf betrifft nur die optionale Speicherung von Profil-, CV- und
> Suchprofildaten in Mays-RIS. Er ersetzt nicht die bestehende Erklärung für
> Stellensuche, Browserverarbeitung oder KI-Funktionen.
>
> ## Was und warum wird gespeichert?
>
> Nach einer ausdrücklichen Speicheraktion können Konto-/Namensdaten, CV-
> Metadaten und eine ausgewählte PDF, manuelle Suchprofile, CV-Suchprofile und
> ATS-Varianten gespeichert werden. Zweck ist der spätere Abruf, die Änderung,
> der Export und die Löschung der ausgewählten Daten.
>
> Die konkrete Rechtsgrundlage und Frist werden vor produktiver Freischaltung
> festgelegt. Eine Speicheraktion ist nicht automatisch eine Einwilligung für
> AI-Analyse, Providerübermittlung oder jede andere Verarbeitung.
>
> ## Abgrenzung und Zugriff
>
> Browserseitige CV-Auslese, Stellensuche und optionale KI-Analyse sind eigene
> Verarbeitungsvorgänge. Die Analyse speichert nicht automatisch einen CV im
> RIS-Konto. RIS verarbeitet die Kontodaten in der vorgesehenen AWS-
> Infrastruktur mit serverseitiger Konto-, Tenant- und Partnerprüfung. Ein
> vertrauliches RIS-Partner-Credential darf nicht im Browser liegen.
>
> Tatsächliche Empfänger, Regionen, Unterauftragsverarbeiter und
> Drittlandgarantien müssen vor Veröffentlichung anhand der produktiven
> Konfiguration ergänzt werden.
>
> ## Aufbewahrung, Änderung, Export und Löschung
>
> Es gilt keine pauschal freigegebene Frist. Jede Ressource erhält eine
> zweckgebundene Retention-Regel. S3-Versionen, Backups und Logs können eigene
> Fristen haben. Das Löschen des aktuellen Dokuments beweist nicht automatisch
> die Löschung alter Versionen oder Backups.
>
> Nach Freigabe sollen Nutzer Profile ändern, ausgewählte CVs/Profile löschen
> und Auskunft/Export anfordern können. Eine vollständige Löschung wird nur für
> den tatsächlich geprüften Umfang bestätigt; verbleibende Backups, gesetzliche
> Pflichten oder externe Systeme werden gesondert ausgewiesen.
>
> ## Besondere Kategorien in CVs
>
> Lebensläufe können Gesundheitsdaten, politische/religiöse Informationen,
> Gewerkschaftszugehörigkeit, biometrische Angaben oder andere besondere
> Kategorien enthalten. Nicht benötigte sensible Angaben sollten entfernt
> werden. Vor produktiver Speicherung ist eine gesonderte Art.-9-Prüfung und
> gegebenenfalls eine ausdrückliche, spezifische Entscheidung erforderlich.
>
> ## Kontolöschung und Vorbehalt
>
> Eine Kontolöschung startet einen kontrollierten Prozess für Konto-, Profil-
> und Dokumentdaten. Profilkinder, S3-Versionen/Marker, technische Restdaten,
> Backups und Datenschutzbelege können eigene Behandlung benötigen. Ein
> Teilstatus darf nicht als vollständige physische Löschung bezeichnet werden.
>
> Dieser Text ist technische/redaktionelle Vorlage, keine Rechtsberatung, keine
> Einwilligungserklärung und keine Freigabe für produktive Speicherung.

Assessment: covers profile/CV/search profiles, **not** ApplicationV1, and
self-declares "keine Einwilligungserklärung".

### 3.2 Candidate B — Jobsearch public privacy policy v1.1, section 9 and 10

Source: `public/legal/datenschutz.md` (Jobsearch, version 1.1, 2026-11-07),
§9 "OPTIONALE DAUERHAFTE SPEICHERUNG VON BEWERBUNGEN (APPLICATIONV1)":

> Die dauerhafte Speicherung von Bewerbungen und Bewerbungsunterlagen ist
> technisch vorbereitet, aber nicht standardmäßig aktiv. Sie wird nur angeboten,
> wenn die Funktion freigegeben ist und eine wirksame, zweckgebundene
> Einwilligung vorliegt. Ohne eine solche Einwilligung bleiben die zugehörigen
> Funktionen gesperrt.
>
> Nach ausdrücklicher Freigabe und Einwilligung können insbesondere
> Bewerbungen, Anschreiben, Dokumentversionen, ausgewählte CV- und Suchprofile
> sowie zugehörige Metadaten in der vorgesehenen RIS-/AWS-Infrastruktur
> gespeichert werden. Zweck ist der spätere Abruf, die Änderung, der Export und
> die Löschung der ausgewählten Daten. Eine Einwilligung zur Speicherung ist
> nicht automatisch eine Einwilligung für jede andere Verarbeitung,
> insbesondere nicht für jede KI-Analyse oder jede Providerübermittlung.
>
> Die Einwilligung wird nach Zweck getrennt und versioniert erfasst. Die bei der
> Zustimmung angezeigte Textfassung ist maßgeblich. Der aktuelle Status, die
> Version und die Historie können über die vorgesehenen Einwilligungsfunktionen
> angezeigt werden. Ein Widerruf verhindert neue abhängige Schreibzugriffe;
> bereits gespeicherte Daten bleiben im Rahmen der bestehenden Rechte lesbar,
> exportierbar und löschbar, soweit keine gesetzlichen Aufbewahrungspflichten
> oder technischen Restfristen entgegenstehen. Ein Widerruf ist nicht
> automatisch eine sofortige physische Löschung.

§10 "EINWILLIGUNG, VERSIONIERUNG UND WIDERRUF":

> Soweit eine Verarbeitung auf einer Einwilligung beruht, wird diese vor der
> Verarbeitung eingeholt. Die Einwilligung ist zweckbezogen, versioniert und
> kann jederzeit mit Wirkung für die Zukunft widerrufen werden. Die Anzeige
> nennt die verwendete Text- und Hinweisversion. Eine Versionskennung allein
> ist keine rechtliche Freigabe.
>
> Die Einwilligungsverwaltung unterscheidet insbesondere zwischen nicht
> erteilter, erteilter und widerrufener Einwilligung. Wiederholte Zustimmungen
> zur selben Fassung werden idempotent behandelt. Widerrufe bleiben in der
> Historie nachvollziehbar. Ein fehlender Datensatz gilt nicht als Einwilligung.

Assessment: this is the closest existing application-storage description. It is
still a privacy notice, not a consent declaration signed by the user.

### 3.3 Candidate C — exact Jobsearch UI strings shown next to the grant button

Source: `src/components/StorageConsentLive.tsx` and `src/i18n.tsx` (Jobsearch).

| UI element | Exact text (DE) |
| --- | --- |
| Section heading | `Speicherung von Bewerbungen` |
| Status labels | `erteilt` / `widerrufen` / `nicht erteilt` |
| Status line | `Status: <label> (Textversion <version>)` |
| Blocked hint | `Die Einwilligungs-Textversion ist noch nicht freigegeben. Die Zustimmung ist gesperrt.` |
| Blocked hint, RIS state | `RIS-Status: <stateLabel> (<STATE>).` |
| Blocked hint, reason | `Die RIS-Textversion ist weder freigegeben (APPROVED) noch aktiv (ACTIVE).` |
| Privacy link | `Datenschutzhinweise zur Bewerbungsspeicherung` |
| Displayed text version | `Angezeigte Textfassung: 2026-11-04-draft-1` |
| RIS text version | `RIS-Textversion: 1.0` |
| Grant button | `Speicherung zustimmen` |
| Withdraw button | `Einwilligung widerrufen` |
| History button | `Verlauf anzeigen` |

From `src/i18n.tsx` (`privacyStorage.*`, DE):

| Key | Exact text (DE) |
| --- | --- |
| `privacyStorage.purpose.application_storage` | `Bewerbungen speichern` |
| `privacyStorage.purpose.application_storage.description` | `Bewerbungen, Anschreiben und Dokumentversionen.` |
| `privacyStorage.notice` | `Die dauerhafte Speicherung deiner Bewerbungsunterlagen wird vorbereitet und ist derzeit noch nicht verfügbar.` |
| `privacyStorage.requiredText` | `Anmelde- und Kontodaten werden für die Bereitstellung deines Kontos verarbeitet. Das ist getrennt von der optionalen Speicherung deiner Bewerbungsunterlagen.` |
| `privacyStorage.aiText` | `KI-Anfragen haben eine eigene Einwilligung und Datenschutzgrenze. Eine KI-Einwilligung ist keine Speichereinwilligung und aktiviert keine dauerhafte Speicherung deiner Bewerbungsunterlagen.` |
| `privacyStorage.sessionText` | `Suche, Lebenslauf-Werkstatt, Anschreiben und Bewerbungen bleiben derzeit nur in dieser Browsersitzung. Beim Neuladen werden sie verworfen.` |
| `privacyStorage.risText` | `Die dauerhafte Speicherung setzt einen verifizierten RIS-Dienst, serverseitige Einwilligungsnachweise, Aufbewahrungsregeln und Löschverfahren voraus. In diesem Stand ist sie nicht aktiv.` |
| `privacyStorage.rightsText` | `Ein späterer Widerruf muss serverseitig registriert werden und die abhängigen optionalen Verarbeitungen wirksam unterbinden. Ein Widerruf ist nicht automatisch eine sofortige Löschung, soweit gesetzliche Aufbewahrungspflichten gelten.` |
| `privacyStorage.actions.withdraw` | `Einwilligung widerrufen` |

Candidate D is rendered verbatim above the consent button at Jobsearch
`5ac025f` (v4); the grant button is the affirmative act after the declaration.
Candidates A–C remain supporting/context material. v3/v2/v1 are historical and
superseded.

### 3.4 Candidate D — approved ApplicationV1 declaration (v4, limited beta pilot)

Source: `src/lib/applicationStorageConsent.ts` (Jobsearch commit `5ac025f`),
canonical text = the nine paragraphs below joined with `\n\n` (UTF-8).

| Field | Value |
| --- | --- |
| Text version | `application-storage-consent-2026-11-07-v4` |
| SHA-256 | `8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7` |
| Supersedes | `...-v3`, `...-v2` and `...-v1` (historical, never approved) |
| Intended RIS notice | `application-storage` / `1.0` |
| State | **`APPROVED` — limited beta pilot only, not `ACTIVE`** |
| `legalApprovalRef` | `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` |
| RIS ↔ Jobsearch mapping | **`1.0` (limited beta pilot)** |
| Art. 9 categories | `health`, `religious_or_philosophical_beliefs`, `trade_union_membership`, `political_opinions`, `sexual_orientation`, `sex_life`, `biometric_data`, `genetic_data`, `racial_or_ethnic_origin` |
| Stored proof (RIS) | `specialCategoriesConsent`, `specialCategories`, `externalTextVersion`, `externalTextSha256` |
| Privacy-policy reference inside text | v1.1, 7 November 2026 |
| BFF gate | `RIS_CONSENT_TEXT_VERSION` / `RIS_CONSENT_TEXT_SHA256` / `RIS_CONSENT_TEXT_STATE`; only exact version+hash with `APPROVED` opens a grant |

> Ich willige ein, dass der RIS-Speicherdienst meine Bewerbungsdaten im nachfolgend beschriebenen Umfang dauerhaft speichert, damit ich sie später abrufen, bearbeiten, exportieren und löschen kann. Diese Einwilligung gilt ergänzend zu den Datenschutzhinweisen unter /datenschutz (Datenschutzrichtlinie Version 1.1 vom 7. November 2026) und ersetzt diese nicht.
>
> Gespeichert werden: meine Bewerbungen mit Stellenbezug (jobId, Titel, Unternehmen, Ort, Quelle und URL), meine Anschreiben und Anschreiben-Versionen, der Dokumentstatus, der Bewerbungsstatus, Statusänderungen und der Statusverlauf, Verweise auf ausgewählte CV- und Suchprofile sowie Bewerbungsdatum und -kanal, Kontaktangaben, Notizen, Gehaltsvorstellung und -angebot, Wiedervorlagen und Verlaufsereignisse (Feedback, Interview, Notizen).
>
> Nicht gespeichert werden durch diese Einwilligung: PDF-Dateien, im Browser ausgelesene CV-Texte, KI-Prompts oder Provider-Nutzlasten. Verweise auf CV- und Suchprofile verweisen nur auf die jeweilige Ressource und enthalten keine Dokumentkopie.
>
> Ich willige ausdrücklich nach Art. 9 Abs. 2 lit. a DSGVO ein, dass besondere Kategorien personenbezogener Daten, die in meinen Bewerbungsunterlagen oder Bewerbungsdaten enthalten sind, gespeichert werden, soweit ich diese Angaben selbst bereitstelle. Das betrifft insbesondere Gesundheitsdaten, Angaben zu religiösen oder weltanschaulichen Überzeugungen, die Gewerkschaftszugehörigkeit, politische Meinungen, das Sexualleben und die sexuelle Orientierung, biometrische Daten, genetische Daten sowie Angaben zur rassischen oder ethnischen Herkunft. Diese ausdrückliche Einwilligung ist freiwillig, erfordert keine Zuordnung zu einer bestimmten Kategorie und keine Offenlegung, ob solche Daten überhaupt vorliegen, und kann jederzeit mit Wirkung für die Zukunft widerrufen werden; sie ist nicht Voraussetzung für die übrigen Bewerbungsfunktionen. Eine automatische Kategorisierung oder Ableitung von Geschlecht, Geschlechtsidentität oder sexueller Orientierung findet nicht statt.
>
> Der Zweck der Speicherung ist ausschließlich der spätere Abruf, die Änderung, der Export und die Löschung der ausgewählten Bewerbungsdaten durch mich.
>
> RIS ist der Speicherdienst; die Daten liegen in der bestehenden RIS-/AWS-Infrastruktur. Diese Einwilligung betrifft keine KI-Analyse und keine Übermittlung an KI- oder sonstige Provider. Eine Einwilligung in eine KI-Verarbeitung ist nicht Teil dieser Erklärung und wird durch sie nicht erteilt.
>
> Mit dieser Einwilligung wird die dauerhafte Speicherung der genannten Daten für mein angemeldetes Konto freigeschaltet. Ohne diese Einwilligung bleiben die abhängigen Speicherfunktionen gesperrt.
>
> Ich kann diese Einwilligung jederzeit mit Wirkung für die Zukunft widerrufen. Der Widerruf blockiert neue abhängige Schreibzugriffe. Bereits gespeicherte Daten bleiben im Rahmen der bestehenden Rechte lesbar, exportierbar und löschbar; der Widerruf ist nicht automatisch eine sofortige physische Löschung.
>
> Für ApplicationV1 ist derzeit keine pauschale Aufbewahrungsfrist freigegeben. Gespeicherte Bewerbungen bleiben bestehen, bis ich sie lösche. Sicherungen, Protokolle und gesetzliche Aufbewahrungspflichten können eine Löschung verzögern oder begrenzen.

**Approval:** approved 2026-11-08 by Betreiberin May's Job Matcher for the
**limited beta pilot only**, reference `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08`.
It is not `ACTIVE` and not a general rollout. v3/v2/v1 (`...-v3` hash
`696f…7668`, `...-v2` hash `232c…a0ca`, `...-v1` hash `2615…9953`) remain
historical/superseded and were never approved. The RIS backend stores the
explicit Art. 9 proof (`specialCategoriesConsent`, `specialCategories`,
`externalTextVersion`, `externalTextSha256`); an Art. 9 consent requires the
current v4 text pair (`422 EXTERNAL_TEXT_REQUIRED_FOR_SPECIAL_CATEGORIES` if
missing, `422 EXTERNAL_TEXT_NOT_ART9` for a historical text).

---

## 4. Purpose and data categories actually stored

**Purpose:** optional durable storage of applications in RIS so the user can
retrieve, change, export and delete them later — explicitly separate from AI
analysis and provider transmission.

ApplicationV1 fields (validated in `jobsearch/application_contract.py:274-300`):

| Field | Content | Personal-data note |
| --- | --- | --- |
| `job` | `jobId`, `source`, `title`, `company`, `location`, `url` | Usually not applicant personal data |
| `profileRef` | `id`, `version` | Reference only |
| `cvRef` | `id`, `version` | Reference only |
| `documents.coverLetterDraft` | free text (up to 100 000 chars) | **can contain personal/special-category data** |
| `documents.coverLetterVersions[]` | `versionId`, `jobId`, `createdAt`, `content`, `source`, `language`, `model` | **free text + model metadata** |
| `documents.cvReference` | `cvId`, optional `documentId`, `label` | Reference; **no PDF bytes/hash** |
| `documents.documentStatus` | `missing` / `draft` / `ready` | Metadata |
| `applicationDate`, `applicationChannel` | date; `online`/`email`/`portal`/`postal`/`other` | Application metadata |
| `contact` | contact fields | **third-party personal data possible** |
| `notes` | free text (up to 10 000 chars) | **can contain personal/special-category data** |
| `salary` | `expectation`/`offer` {amount, currency, period} | Personal data |
| `followUp` | `dueOn`, optional `note`, `status`, `completedAt` | Personal data |
| history events | `feedback`/`interview`/`note` text | **free text** |

Server-owned identity fields (`applicationId`, `ownerId`, `userId`, `tenantId`,
`partnerApplicationId`, `issuer`) are never accepted from the client.

**Not stored by this flow:** PDF file bytes, CV text extracted in the browser,
AI prompts/provider payloads. `documents.cvReference` is a reference, not a
document copy.

### 4.1 Candidate D text ↔ ApplicationV1 field mapping

| Candidate D phrase (verbatim) | ApplicationV1 field(s) | Note |
| --- | --- | --- |
| „meine Bewerbungen mit Stellenbezug (jobId, Titel, Unternehmen, Ort, Quelle und URL)“ | `job.jobId`, `job.source`, `job.title`, `job.company`, `job.location`, `job.url` | Exact job snapshot |
| „meine Anschreiben und Anschreiben-Versionen“ | `documents.coverLetterDraft`, `documents.coverLetterVersions[]` (`versionId`, `jobId`, `createdAt`, `content`, `source`, `language`, `model`) | Version content; `model` is stored metadata |
| „der Dokumentstatus“ | `documents.documentStatus` (`missing`/`draft`/`ready`) | Metadata |
| „der Bewerbungsstatus, Statusänderungen und der Statusverlauf“ | `status` (`DRAFT`/`READY`/`SUBMITTED`/`WITHDRAWN`/`ARCHIVED`), `statusHistory` | Now named explicitly in v2 |
| „Verweise auf ausgewählte CV- und Suchprofile“ | `documents.cvReference` (`cvId`, optional `documentId`, `label`); `cvRef`, `profileRef` (`id`, `version`) | References only; no PDF bytes/hash |
| „Bewerbungsdatum und -kanal“ | `applicationDate`, `applicationChannel` | Application metadata |
| „Kontaktangaben“ | `contact` | May contain third-party data |
| „Notizen“ | `notes`, history `note` | Free text |
| „Gehaltsvorstellung und -angebot“ | `salary.expectation`, `salary.offer` (`amount`, `currency`, `period`) | Personal data |
| „Wiedervorlagen“ | `followUp` (`dueOn`, `note`, `status`, `completedAt`) | Reminder data |
| „Verlaufsereignisse (Feedback, Interview, Notizen)“ | history events (`kind` `feedback`/`interview`/`note`, `text`, `scheduledAt`, `note`) | Append-only timeline |

Caveats for the operator:

- v4 adds an explicit Art. 9(2)(a) consent paragraph covering
  „Sexualleben und sexuelle Orientierung“, the `sex_life` category and an
  explicit no-inference statement; the stable set has nine codes. The RIS
  backend stores and validates that proof (`specialCategoriesConsent`,
  `specialCategories`, `externalTextVersion`, `externalTextSha256`); it does
  not infer it from the notice.
- v4 explicitly names „der Bewerbungsstatus, Statusänderungen und der
  Statusverlauf“, closing the earlier status/`statusHistory` wording gap.
- `documents.coverLetterVersions[].model` (model identifier) is part of
  „Anschreiben-Versionen“ metadata; explicit naming is a wording decision.
- `idempotencyKey`, cursors and other technical guard records are not consent
  data and are not part of the declaration; they are covered by the separate
  processing-purpose/retention review (P-08), which remains open.
- Server-owned identity fields (`applicationId`, `ownerId`, `userId`,
  `tenantId`, `partnerApplicationId`, `issuer`) are derived from the signed-in
  account and are covered by „für mein angemeldetes Konto“; they are never
  accepted from the client.

---

## 5. Withdrawal behavior (actual, code-backed)

- `POST /v1/partner/me/consents/withdraw` is possible in **every** notice state
  and does not consult `CONSENT_NOTICE_STATE_ENFORCED`
  (`jobsearch/consent_repository.py:185-235`).
- With `APPLICATION_CONSENT_ENFORCED=true`, a withdrawn consent blocks the five
  ApplicationV1 write paths: create, patch, status, history, cover-letter
  (`lambda/handler.py:774, 799, 810, 819, 825`) → `403 CONSENT_REQUIRED`.
- Reads, list, detail, metrics, export and delete remain available, so data
  subject rights stay usable.
- Withdrawal does **not** delete existing applications and does **not** rewrite
  stored consent versions. This matches policy §9/§10.
- Env fact: `APPLICATION_CONSENT_ENFORCED=false` today, so the write block is
  not yet active in deployment.

---

## 6. Actual retention rules (implementation facts, not approvals)

Source of truth: Terraform + repositories, cross-checked against
`docs/privacy/RIS-JOBSEARCH-RETENTION-POLICY-V1.md`.

| Resource | Actual technical behavior | Approved period |
| --- | --- | --- |
| Applications table (`...-applications`) | TTL is **enabled** on attribute `expiresAt`, but the application repository never writes `expiresAt` → **no automatic expiry**; records persist until explicit delete | **none** (policy has no ApplicationV1 row) |
| Application delete | owner-scoped API delete; no automatic purge of backups | **none** |
| Consents table (`...-consents`) | no TTL at all; current state + append-only history are retained indefinitely by design | **none** (open decision) |
| Consent history | append-only event rows, never updated/deleted by the module | **none** |
| Applications PITR | `r08_pitr_enabled` default `false` | n/a |
| Lambda logs | `log_retention_days` default `14` | not a data-subject retention approval |
| S3 documents | not used by this ApplicationV1 flow | n/a |
| Account-level erasure of applications | `ERASURE_APPLICATIONS_ENABLED=false` | **not enabled** |

Consequence: "retention" for ApplicationV1 is currently "until the user
deletes" with no approved clock, no TTL value and no approved backup rule.

---

## 7. Technical impact of the approval (what changes, what does not)

**The approval is applied locally as `APPROVED` (not `ACTIVE`):**

- `consent_contract.catalog_payload()` reports `noticeState=APPROVED`,
  `noticeApproved=true`, `grantableWhenEnforced=true`, and the approval ref;
  `acceptedForNewGrant` is `true`.
- The Jobsearch BFF gate can open once its own text mapping
  (`RIS_CONSENT_TEXT_STATE=APPROVED`) is set; the UI keeps the grant disabled
  until server notice and text approval agree.
- With `CONSENT_NOTICE_STATE_ENFORCED=true`, RIS accepts `APPROVED`/`ACTIVE`
  new grants and rejects `DRAFT`/`SUPERSEDED` with `422 NOTICE_NOT_ACTIVE`.
- Existing grants are unchanged; a version becoming `SUPERSEDED` does not
  rewrite them.
- No DynamoDB migration, no table change, no new route.
- Approval is local only. The Lambda source hash changes → bundle rebuild and
  a **new** Terraform plan/review are required before any pilot deployment.
  `APPLICATION_CONSENT_ENFORCED` and any environment change remain separate
  GO items.

---

## 8. Decision status (approval applied, open items)

Resolved by this approval (limited beta pilot):

| Item | Status |
| --- | --- |
| Exact declaration text | **APPROVED** — v4, hash `8722…43c7` |
| ApplicationV1 scope | **APPROVED** — applications, cover letters, versions, notes, contact, salary, history, status/statusHistory |
| Art. 9 text consent | **APPROVED** — separate consent, 9 categories incl. Sexualleben/sexuelle Orientierung, no self-categorisation/inference |
| RIS ↔ Jobsearch mapping | **APPROVED** — v4 ↔ RIS `1.0` |
| `legalApprovalRef` | **RECORDED** — `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08`, 2026-11-08, Betreiberin May's Job Matcher |

Still open (not falsely confirmed):

1. **Full account deletion** — `ERASURE_APPLICATIONS_ENABLED=false`; account-level
   erasure of applications is not enabled.
2. **Consent-history retention** — the consents table has no TTL; the retention
   clock/duration remains undecided.
3. **DPA / transfer checks** — recipients, AWS `eu-central-1`, Vercel and any
   further processors/transfers still require confirmation.
4. **ApplicationV1 retention rule** — clock event, duration, backup/PITR and
   deletion exceptions.
5. **Controller/processor roles** and the Art. 6(1) basis beyond the consent
   mechanism.
6. **Environment and audience** — pilot deployment, exact `ris-dev` allowlist
   and the separate GO for `CONSENT_NOTICE_STATE_ENFORCED=true` /
   `APPLICATION_CONSENT_ENFORCED=true`.

---

## 9. What this packet explicitly does not do

- It does **not** grant general availability: the notice is `APPROVED`, not
  `ACTIVE`, and the pilot is limited.
- It does **not** deploy, apply Terraform, change a flag/environment or claim
  live persistence.
- It does **not** confirm the open items in §8 (account deletion,
  consent-history retention, DPA/transfers, retention clock).
