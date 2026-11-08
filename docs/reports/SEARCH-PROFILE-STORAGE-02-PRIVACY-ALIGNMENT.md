# SEARCH-PROFILE-STORAGE-02 — Privacy Alignment Review

**Status:** `READY FOR NOTICE APPROVAL — 3 OPERATOR DECISIONS REQUIRED`
**Date:** 2026-11-08
**Candidate text:** `search-profile-storage-consent-2026-11-08-v1`
**SHA-256:** `926d1b9bbeefac4b97a5c51e3b6e6c1ed33a3affc3698e07456132be39b0f0f8`

This is a targeted comparison, not a new general privacy assessment. It checks
only the candidate text against:

- `public/legal/datenschutz.md` / `public/legal/datenschutz.html` (v1.1,
  2026-11-07);
- the live RIS-DEV storage and deletion semantics for
  `ris-dev-dev-partner-profiles`;
- the implemented consent gate and per-profile deletion paths.

## 1. Findings

### P1 — Privacy policy still frames search profiles under ApplicationV1

**Concrete conflict.**

Datenschutzerklärung §9 is titled
`OPTIONALE DAUERHAFTE SPEICHERUNG VON BEWERBUNGEN (APPLICATIONV1)` and says:

> „Nach ausdrücklicher Freigabe und Einwilligung können insbesondere
> Bewerbungen, Anschreiben, Dokumentversionen, ausgewählte CV- und
> Suchprofile sowie zugehörige Metadaten in der vorgesehenen RIS-/AWS-
> Infrastruktur gespeichert werden.“

The new candidate declares a **separate** purpose
`search-profile-storage`, a separate consent, and explicitly says it is
separate from ApplicationV1. A reader of the policy can currently conclude that
search profiles are covered by the ApplicationV1 consent. That is not the
implemented contract.

**Required before notice approval:** add one clarifying sentence to §9 (and the
HTML mirror), or record an explicit operator/legal decision that the separate
consent is the controlling layered notice. Proposed wording:

> „Die dauerhafte Speicherung manueller Suchprofile, CV-Suchprofile und
> ATS-Profile ist ein eigener, von ApplicationV1 und der CV-Speicherung
> getrennter Zweck. Sie ist nur nach einer gesonderten, versionierten
> Einwilligung aktiv; die ApplicationV1-Einwilligung umfasst sie nicht.“

This is a policy/notice decision; no code change is implied.

### P2 — “keine … sonstige Anbieter” is too broad for the AWS processor

**Concrete wording contradiction / ambiguity.**

The candidate says:

> „Die Speicherung erfolgt in der bestehenden RIS-Infrastruktur. Sie löst keine
> KI-Anfrage aus und übermittelt keine Profilinhalte an KI- oder sonstige
> Anbieter.“

The implemented storage is DynamoDB in the RIS/AWS infrastructure. AWS is a
processor, even though the RIS partner surface is the controller-facing
service. “Sonstige Anbieter” can be read as “no processor at all”, which is not
accurate. The Datenschutzerklärung §15 already names AWS/DynamoDB as a
recipient category.

**Required clarification before approval, or an explicit legal acceptance of
the current wording.** Proposed replacement:

> „Die Speicherung erfolgt in der bestehenden RIS-/AWS-Infrastruktur
> (DynamoDB); die dort eingesetzten Dienstleister sind in den
> Datenschutzhinweisen genannt. Die Speicherung löst keine KI-Anfrage aus und
> übermittelt keine Profilinhalte an KI-Anbieter.“

If this replacement is adopted, the text version and SHA-256 change; the RIS
notice mapping, Jobsearch server mapping, tests and approval packet must be
updated. It must not be edited silently under the current v1 hash.

### P3 — Account deletion does not currently include search profiles

**Concrete erasure gap; not a promise in the candidate text.**

Implemented today:

- per-profile `DELETE` hard-deletes the DynamoDB profile item;
- CV search profile deletion is refused while ATS children exist;
- consent withdrawal blocks new writes but does not delete existing profiles;
- the account-erasure path (`PrivacyErasure`) covers credentials, API
  profiles, work, applications and user profile, but **not**
  `partner_profiles` search profiles. The profile-only erasure executor exists
  in `agents/ecosystem/privacy_profile_erasure.py` but is not wired into the
  live `PrivacyErasure` path.

The candidate text does **not** promise account-level deletion; it only
promises per-profile deletion and says withdrawal is not immediate physical
deletion. Therefore there is no direct text contradiction. However,
Datenschutzerklärung §16 refers to a controlled account-deletion process, and
an operator could reasonably expect search profiles to be included. Before a
real-user rollout, choose one:

1. wire `ProfileOnlyErasureExecutor` for `manualSearchProfiles`,
   `cvSearchProfiles` and `atsSearchProfiles` into account erasure and test it;
   or
2. add an explicit limitation to the policy/notice that account deletion does
   not automatically remove search profiles and they must be deleted
   separately.

No code was changed in this review; option 1 is a separate implementation
decision.

### P4 — Verified storage semantics (no text change required)

Live read-only evidence for `ris-dev-dev-partner-profiles`:

| Property | Actual |
| --- | --- |
| Item count | 3 |
| Billing | PAY_PER_REQUEST |
| Deletion protection | `false` |
| TTL | enabled on `expiresAt`; used only for technical/idempotency records |
| PITR | `DISABLED` |
| On-demand backups | none listed |
| Per-profile delete | transactional hard delete of the DynamoDB item |
| Consent table TTL / PITR | TTL disabled / PITR disabled |

The candidate says backups/logs “können” delay or limit deletion. That is not
false, but the current profile table has **no PITR and no listed backup**. If
the operator wants the notice to describe the current state precisely, it
should say “derzeit sind für die Profiltabelle keine PITR/Backups
konfiguriert; Logs können eigene Fristen haben.” This is optional, not a
blocking contradiction.

### P5 — Free-text descriptions and Art. 9 (residual)

`description` fields are free text. The purpose is ordinary professional
search-profile data and the implementation does not request Art. 9 consent.
If users may enter special-category data in descriptions, add a short UI hint
(“Bitte keine besonderen Kategorien personenbezogener Daten”) or filter the
field. This is a product/UX decision, not a contradiction in the current text.

## 2. Result

**No new general privacy analysis was performed.**

**Ready for notice approval only after P1 and P2 are decided.** P3 is required
before a real-user rollout, not before the DRAFT/synthetic path. P4 and P5 are
recorded for transparency and do not block the synthetic E2E.

The candidate remains unchanged at version
`search-profile-storage-consent-2026-11-08-v1`, SHA-256
`926d1b9bbeefac4b97a5c51e3b6e6c1ed33a3affc3698e07456132be39b0f0f8`.

No notice state, legal reference, AWS resource, Vercel setting or user data was
changed.
