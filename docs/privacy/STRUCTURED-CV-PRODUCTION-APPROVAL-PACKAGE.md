# Structured CV Production Approval Package

**Purpose:** `cv-builder-profile-storage`

**Status:** DRAFT DECISION PACKAGE — **NOT LEGALLY APPROVED**

**Notice candidate:** `structured-cv-profile-storage-2026-11-12-draft-1`

**Legal approval reference:** none (`null`)

**Scope:** This package prepares human privacy/legal decisions. It does not
create a legal approval, activate a notice, grant consent or authorize
production processing.

## 1. Processing description

The feature stores an editable structured CV-builder profile for an
authenticated user:

- profile name;
- structured CV draft (personal details, experience, education, skills,
  projects, certificates, languages, links);
- selected template;
- optional import-review sidecar (original/corrected text, status, applied flag,
  page and section provenance);
- server-generated profile id, version, timestamps and tenant/partner/issuer
  ownership metadata.

It is **not** PDF storage, not an ATS score, not an AI request and not a search
profile. Storing a CV does not authorize any AI/provider transfer.

## 2. Roles and data flows

| Party | Proposed role | Decision needed |
|---|---|---|
| Jobsearch operator / customer | Controller for its account and CV workflow; exact role versus RIS requires contract review | `REVIEW_REQUIRED` |
| RIS operator | Processor or separate controller for the partner storage service; DPA/Art. 28 terms required | `REVIEW_REQUIRED` |
| AWS | Hosting sub-processor (DynamoDB, Lambda, API Gateway, CloudWatch); region and DPA must be confirmed | `REVIEW_REQUIRED` |
| AI providers | **No recipient for this purpose**; separate consent is required for AI processing | `REVIEW_REQUIRED` confirmation |

No existing PDF-storage, application-storage or search-profile consent is
equivalent to this purpose. A separate consent/notice mapping is required.

## 3. Article 6 and Article 9 assessment

### Article 6

Proposed lead option for human review: explicit consent under Art. 6(1)(a),
separate from other purposes, because the feature is optional and the user
chooses durable account storage. A contract/legitimate-interest alternative
must be assessed by the responsible legal/privacy owner; this package does not
select the final basis.

### Article 9

Free-text CV fields, education, health-related gaps, union membership, religious
or other special-category information may be entered by the user. The proposed
assessment is that explicit consent under Art. 9(2)(a) is required for this
purpose, with a clear warning that users should not enter special-category data
unless necessary.

Open legal questions:

- whether the purpose can be designed to avoid Art. 9 data entirely;
- whether a separate Art. 9 consent field is required (currently proposed:
  explicit notice + affirmative consent; final UI wording requires approval);
- whether the same consent can cover imported free text and review corrections;
- withdrawal consequences for data already stored.

## 4. Notice proposal (German, not approved)

> **Dauerhafte Speicherung deiner Lebenslauf-Profile**
>
> Wenn du diese Funktion ausdrücklich aktivierst, speichern wir die von dir
> erstellten strukturierten Lebenslauf-Profile (z. B. Name, Kontaktdaten,
> Berufserfahrung, Ausbildung, Kenntnisse, Projekte und die Prüfliste aus dem
> Import) dauerhaft in deinem Konto, damit du sie später wieder öffnen und
> bearbeiten kannst.
>
> Die Speicherung erfolgt in der RIS-Anwendung in der EU-Region
> `eu-central-1` bei unserem Auftragsverarbeiter AWS. Sie ist **keine
> Einwilligung in eine KI-Verarbeitung, keine PDF-Speicherung und keine
> Veröffentlichung deines Lebenslaufs**. Eine Übermittlung an einen
> KI-Anbieter findet für diese Speicherung nicht statt.
>
> Bitte trage keine besonderen Kategorien personenbezogener Daten (z. B.
> Gesundheitsdaten, Gewerkschafts- oder Religionsangaben) ein, wenn dies für
> deinen Lebenslauf nicht erforderlich ist. Soweit du solche Angaben
> ausdrücklich eingibst, umfasst deine Einwilligung auch deren Speicherung.
>
> Du kannst deine Einwilligung jederzeit mit Wirkung für die Zukunft
> widerrufen und einzelne Profile löschen. Die Löschung deines Kontos umfasst
> auch diese Profile, soweit keine gesetzlichen Aufbewahrungspflichten oder
> technischen Backup-Kopien entgegenstehen. Einzelheiten zu Aufbewahrung,
> Widerruf, Export und Löschung werden vor der Aktivierung verbindlich
> festgelegt.
>
> Verantwortlicher: [einzutragen]. Datenschutzkontakt:
> [einzutragen]. Weitere Informationen: [Datenschutzerklärung/Version].

This text is a **candidate**; legal/privacy must approve final wording, legal
basis, controller details, retention and contact information. It must not be
published as APPROVED/ACTIVE by an agent.

## 5. Retention and withdrawal decision template

| Decision | Proposal for approval | Status |
|---|---|---|
| Active profile retention | Until user deletion or verified account erasure; no indefinite silent retention | `REVIEW_REQUIRED` |
| Withdrawal: writes | Block new writes immediately | `REVIEW_REQUIRED` |
| Withdrawal: reads | Allow read/export during a defined grace period; no normal product access after expiry | `REVIEW_REQUIRED` |
| Withdrawal: delete | Schedule deletion after grace; exact period not decided | `REVIEW_REQUIRED` |
| Proposed grace period | 30 days (proposal only, not approved) | `REVIEW_REQUIRED` |
| Regrant | Does not restore deleted data; previous deletion wins | `REVIEW_REQUIRED` |
| Single-profile delete | Hard delete profile + embedded review; 404 on repeat | `REVIEW_REQUIRED` |
| Account erasure | Include structured profiles and reviews in existing erasure flow | `REVIEW_REQUIRED` |
| Export | Include full structured draft and review provenance | `REVIEW_REQUIRED` |

The 30-day figure is an operational proposal, not a legal requirement. No
agent may switch the notice or feature on based on this table.

## 6. Backups and PITR

- DynamoDB PITR/backup retention is not yet configured/verified for the
  partner-profile table.
- Restore can reintroduce deleted profiles until the backup window expires.
- A deletion ledger/replay or post-restore reconciliation is required before
  claiming complete account erasure.
- Technical deletion removes the live item but cannot prove physical removal
  from immutable backups.
- Responsibilities for restore approval and post-restore cleanup must be named
  by operations/privacy.

**No complete physical-purge claim is permitted.**

## 7. Data-subject rights and operational controls

- Inspect: owner-scoped metadata category.
- Export: full structured JSON including review provenance; part of account
  privacy export.
- Delete: single profile and embedded review.
- Account erasure: existing `PrivacyErasure` step, idempotent/resumable.
- Authentication: verified subject, tenant, partner and issuer; no client owner
  fields.
- Consent: server authoritative; DRAFT notice fails closed; no client-invented
  version.
- Audit: no profile content in technical logs/receipts.

## 8. Approval matrix

| Decision | Proposal | Responsible approval | Required evidence | Status |
|---|---|---|---|---|
| Art. 6 legal basis | Consent lead option; legal alternative review | Privacy/Legal owner | Signed decision memo | REVIEW_REQUIRED |
| Art. 9 basis | Explicit consent; minimization review | Privacy/Legal owner | Art. 9 assessment | REVIEW_REQUIRED |
| Controller/processor roles | DPA/Art. 28 review | Legal/Procurement | Signed DPA/role matrix | REVIEW_REQUIRED |
| Notice text | Candidate above | Privacy/Legal + product | Approved text/version/hash | REVIEW_REQUIRED |
| Retention | Active-until-delete; grace proposal | Privacy + Operations | Retention schedule | REVIEW_REQUIRED |
| Withdrawal/read/export | Grace-period proposal | Privacy/Legal | Policy decision | REVIEW_REQUIRED |
| Backup/PITR | PITR + restore reconciliation | Operations + Privacy | Runbook/restore test | REVIEW_REQUIRED |
| Consent activation | Only after all above | Release Owner + Privacy | Flags/notice/consent evidence | REVIEW_REQUIRED |

## 9. Required human approvals

This package is ready for review, not approval. The following must be provided
by qualified humans outside this agent run:

1. final Art. 6 and Art. 9 legal basis;
2. controller/processor/DPA determination;
3. approved notice text, version and legal approval reference;
4. retention, withdrawal, read/export and deletion policy;
5. backup/PITR and restore reconciliation policy;
6. Release Owner approval for any consent/feature activation.
