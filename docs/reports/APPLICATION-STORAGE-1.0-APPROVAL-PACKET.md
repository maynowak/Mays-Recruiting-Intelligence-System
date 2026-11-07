# APPLICATION-STORAGE-1.0 — APPROVAL PACKET

**Status:** `DRAFT — NOT AN APPROVAL, NOT LEGALLY REVIEWED`
**Date:** 2026-11-07
**Purpose:** collect the existing texts, identifiers, data categories, retention
facts and open decisions so a legal/operator approval of the RIS consent notice
`application-storage/1.0` can be requested and recorded.
**Owner of the decision:** RIS operator + legal reviewer (not the engineering
agents).

**Repositories / baselines**

| Side | Branch | Commit |
| --- | --- | --- |
| RIS | `feature/jm-ris-storage-activation-01` | `7032e82` |
| Jobsearch | `feature/jm-ris-storage-activation-01` | code `9eecf83` (v3 text; docs include the same commit) |

> This packet does **not** approve anything. No notice state is changed, no
> `legalApprovalRef` is set, no flag is enabled, nothing is deployed.

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
3. **A complete candidate declaration now exists, but no operator/legal
   approval, `legalApprovalRef`, or RIS `1.0` mapping exists.** Candidate D
   (§3.4, Jobsearch `src/lib/applicationStorageConsent.ts` /
   `api/_lib/ris/consentText.mjs`, commit `9eecf83`) is a full first-person
   declaration for ApplicationV1 (v3), including an explicit Art. 9
   special-category consent. It is labelled `DRAFT`, is not approved and is not
   mapped to RIS notice `1.0`. The previous v2/v1 texts are historical and
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
| RIS notice version | `application-storage` / `1.0` | `DRAFT`, `legalApprovalRef = null` | — |
| Jobsearch ApplicationV1 text version | `application-storage-consent-2026-11-07-v3` | `DRAFT` (candidate, §3.4) | **none** |
| Jobsearch ApplicationV1 text SHA-256 | `696f9e66d8098b2dce56a93418ba598145b669934662e2b52d9a332731517668` | — | — |
| Jobsearch historical text version (v2) | `application-storage-consent-2026-11-07-v2` | `DRAFT`, superseded by v3 | **none** |
| Jobsearch historical text version (v1) | `application-storage-consent-2026-11-07-v1` | `DRAFT`, superseded by v2 | **none** |
| Jobsearch legacy text version | `STORAGE_CONSENT_TEXT_VERSION = "2026-11-04-draft-1"` | DRAFT | **none** |
| Jobsearch legacy privacy-notice version | `STORAGE_CONSENT_PRIVACY_NOTICE_VERSION = "2026-11-04-draft-1"` | DRAFT | **none** |

Sources: `jobsearch/consent_contract.py` (`NOTICE_REGISTRY`,
`EXTERNAL_NOTICE_REFS`); Jobsearch `src/lib/applicationStorageConsent.ts` and
`api/_lib/ris/consentText.mjs` at commit `9eecf83`.

`application-storage-consent-2026-11-07-v3` is current. The earlier
`application-storage-consent-2026-11-07-v2` and `...-v1` remain
historical/superseded, and `2026-11-04-draft-1` remains a legacy draft. All are
known to RIS as external references but are never accepted as a
`noticeVersion`. Renaming an identifier, or matching a hash, is not an approval.
A mapping to `1.0` requires a separate, documented operator/legal decision.

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
`9eecf83` (v3); the grant button is the affirmative act after the declaration.
Candidates A–C remain supporting/context material. v2/v1 are historical and
superseded.

### 3.4 Candidate D — complete ApplicationV1 declaration (candidate, v3)

Source: `src/lib/applicationStorageConsent.ts` (Jobsearch commit `9eecf83`),
canonical text = the nine paragraphs below joined with `\n\n` (UTF-8).

| Field | Value |
| --- | --- |
| Text version | `application-storage-consent-2026-11-07-v3` |
| SHA-256 | `696f9e66d8098b2dce56a93418ba598145b669934662e2b52d9a332731517668` |
| Supersedes | `...-v2` and `...-v1` (historical, never approved) |
| Intended RIS notice | `application-storage` / `1.0` |
| State | **`DRAFT` — not approved** |
| `legalApprovalRef` | **none** (RIS notice `1.0` still `null`) |
| RIS ↔ Jobsearch mapping | **none** |
| Art. 9 categories | `health`, `religious_or_philosophical_beliefs`, `trade_union_membership`, `political_opinions`, `sexual_orientation`, `biometric_data`, `genetic_data`, `racial_or_ethnic_origin` |
| Stored proof (RIS) | `specialCategoriesConsent`, `specialCategories`, `externalTextVersion`, `externalTextSha256` |
| Privacy-policy reference inside text | v1.1, 7 November 2026 |
| BFF gate | `RIS_CONSENT_TEXT_VERSION` / `RIS_CONSENT_TEXT_SHA256` / `RIS_CONSENT_TEXT_STATE`; only exact version+hash with `APPROVED` opens a grant |

> Ich willige ein, dass der RIS-Speicherdienst meine Bewerbungsdaten im nachfolgend beschriebenen Umfang dauerhaft speichert, damit ich sie später abrufen, bearbeiten, exportieren und löschen kann. Diese Einwilligung gilt ergänzend zu den Datenschutzhinweisen unter /datenschutz (Datenschutzrichtlinie Version 1.1 vom 7. November 2026) und ersetzt diese nicht.
>
> Gespeichert werden: meine Bewerbungen mit Stellenbezug (jobId, Titel, Unternehmen, Ort, Quelle und URL), meine Anschreiben und Anschreiben-Versionen, der Dokumentstatus, der Bewerbungsstatus, Statusänderungen und der Statusverlauf, Verweise auf ausgewählte CV- und Suchprofile sowie Bewerbungsdatum und -kanal, Kontaktangaben, Notizen, Gehaltsvorstellung und -angebot, Wiedervorlagen und Verlaufsereignisse (Feedback, Interview, Notizen).
>
> Nicht gespeichert werden durch diese Einwilligung: PDF-Dateien, im Browser ausgelesene CV-Texte, KI-Prompts oder Provider-Nutzlasten. Verweise auf CV- und Suchprofile verweisen nur auf die jeweilige Ressource und enthalten keine Dokumentkopie.
>
> Ich willige ausdrücklich nach Art. 9 Abs. 2 lit. a DSGVO ein, dass besondere Kategorien personenbezogener Daten, die in meinen Bewerbungsunterlagen oder Bewerbungsdaten enthalten sind, gespeichert werden, soweit ich diese Angaben selbst bereitstelle. Das betrifft insbesondere Gesundheitsdaten, Angaben zu religiösen oder weltanschaulichen Überzeugungen, die Gewerkschaftszugehörigkeit, politische Meinungen, die sexuelle Orientierung, biometrische Daten, genetische Daten sowie Angaben zur rassischen oder ethnischen Herkunft. Diese ausdrückliche Einwilligung ist freiwillig und kann jederzeit mit Wirkung für die Zukunft widerrufen werden; sie ist nicht Voraussetzung für die übrigen Bewerbungsfunktionen.
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

**Note:** This is a candidate. It is not approved, not mapped to RIS `1.0`
and must not be presented as approved until an operator/legal approval records
the text, the mapping and a real `legalApprovalRef`. v2/v1 (`...-v2` hash
`232c…a0ca`, `...-v1` hash `2615…9953`) remain historical/superseded and were
never approved. The RIS backend stores the explicit Art. 9 proof
(`specialCategoriesConsent`, `specialCategories`, `externalTextVersion`,
`externalTextSha256`) and rejects missing, unknown or mismatched proof.

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

- v3 adds an explicit Art. 9(2)(a) consent paragraph and the eight stable
  category codes. The RIS backend stores and validates that proof
  (`specialCategoriesConsent`, `specialCategories`, `externalTextVersion`,
  `externalTextSha256`); it does not infer it from the notice.
- v3 explicitly names „der Bewerbungsstatus, Statusänderungen und der
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

## 7. Technical impact of an approval (what changes, what does not)

**If the notice is approved and set to `APPROVED`/`ACTIVE` with a real
`legalApprovalRef`:**

- `consent_contract.catalog_payload()` reports `noticeState`,
  `noticeApproved=true`, `grantableWhenEnforced=true`;
  `acceptedForNewGrant` is already `true` while enforcement is off.
- The Jobsearch BFF gate opens (it requires state + both flags) and the UI
  enables the grant button.
- With `CONSENT_NOTICE_STATE_ENFORCED=true`, RIS accepts new grants and rejects
  `DRAFT`/`SUPERSEDED` with `422 NOTICE_NOT_ACTIVE`.
- Existing grants are unchanged; a version becoming `SUPERSEDED` does not
  rewrite them.
- No DynamoDB migration, no table change, no new route.
- The Lambda source hash changes → bundle rebuild and a **new** Terraform plan
  are required before any deployment.

**If the notice is not approved:** nothing changes; the Jobsearch gate stays
closed and no real write can be granted.

---

## 8. Missing decisions (must be resolved before approval)

1. **Consent declaration text.** Approve an exact, complete first-person
   declaration for application storage. Candidates A/B/C above are the only
   existing texts; none is an approved declaration.
2. **Scope of the notice.** Confirm that ApplicationV1 (applications, cover
   letters, document versions, notes, contact, salary, history) is covered —
   the RIS draft is written for profile/CV/search-profile data.
3. **Controller/processor roles** and the Art. 6(1) basis (consent vs requested
   service) for application storage.
4. **Art. 9 assessment** for cover-letter/notes/contact free text.
5. **RIS ↔ Jobsearch mapping**: approve that Jobsearch
   `2026-11-04-draft-1` corresponds to RIS `application-storage/1.0`, or define
   a successor mapping. Today the mapping is explicitly **none**.
6. **`legalApprovalRef`**: approve the exact approval record identifier, owner,
   date and which body approved it. No format is defined yet.
7. **Retention rule for ApplicationV1**: clock event, duration, backup/PITR
   treatment, deletion exceptions. Also decide consent-state/history retention
   (no TTL today).
8. **Account-level erasure**: decide whether `ERASURE_APPLICATIONS_ENABLED`
   must be part of approval or explicitly excluded.
9. **Recipients/transfers**: confirm AWS region `eu-central-1`, Vercel and any
   further processors for this flow.
10. **Withdrawal semantics**: confirm that withdrawal blocks new writes without
    deleting existing applications.
11. **Environment and audience**: dedicated pilot workspace vs `ris-dev`
    (shared with the Jobsearch partner edge), and the exact synthetic test
    identity allowlist.
12. **Ordering approval**: separate GO for `CONSENT_NOTICE_STATE_ENFORCED=true`
    and `APPLICATION_CONSENT_ENFORCED=true`.

---

## 9. What this packet explicitly does not do

- It does not approve, publish or activate notice `1.0`.
- It does not set `legalApprovalRef`, change `NOTICE_REGISTRY`, or change any
  flag, environment, Terraform value or deployment.
- It does not claim that candidate A, B, C or D is legally sufficient.
- It does not claim live persistence; all technical statements are repository
  and local-test facts.
