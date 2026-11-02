# RIS-R08-G0 — PRIVACY CAPABILITY & USER EVIDENCE RECONCILIATION

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| HEAD | `61475f3` (`docs(ris): prepare isolated AWS partner profile E2E gate`) |
| Tracked Working Tree | clean |
| Untracked Dateien | 39, unverändert |
| AWS-Zugriffe/-Mutation | keine |
| Neue Privacy-API / Erasure-Code | nein (nur Contract + Tests + Doku) |

## 2. Mays-Orders-AWS Privacy-Funktionsmatrix

Quelle: `maynowak/mays-order-aws@086a8be` (read-only geprüft), Abgleich mit dem
lokalen Builder-Clone.

| Funktion | Implementiert | Verhalten | Grenzen |
|---|---|---|---|
| `inspect_subject(subject, context)` | ja | GSI2 `subjectId`, Order-Referenzen, Datenkategorien; Fehler → `BLOCKED`, nie leeres „erfolgreich" | **keine Pagination** (1-MB-Grenze möglich); nur Order-Daten |
| `export_subject` | ja | GSI2, vollständige Pagination, JSON v1, Decimal-sicher; Fehler → `BLOCKED` | keine persistierte Operation; kein User-API; PII im Export |
| `erase_subject` | ja | GSI2, Pagination, `PREVIEW`/`EXECUTE`, Policies `ERASE`/`ANONYMIZE`/`RETAIN`, Conditional Writes | keine Receipts, keine Operation-Status-Persistenz; Backups/PITR/S3 nicht erfasst |
| Interne Autorisierung | ja | Projektname, `authorized`, `privacy_inspect/export/erase`, `PRIVACY_INTERNAL_SECRET` (constant-time) | Secret war ephemer; keine dauerhafte Secrets-Manager-Rotation |
| Subject-Isolation | ja | GSI2 pro `subjectId`, Projektkontext | **kein Tenant-Dimension**; Projekt-Isolation statt Mandanten-Isolation |
| Projekt-Isolation | ja | `ORDERS_PROJECT_NAME` + Kontext | kein Cross-Projekt-Test in RIS |
| Preview/Execute | ja | expliziter Modus; `EXECUTE` verlangt Policy | keine gespeicherte Preview-ID/Operation |
| Partial Completion | ja | `PARTIALLY_COMPLETED` bei Fehlern/Retention | keine Wiederaufnahme über Operation-ID |
| Idempotenz | teilweise | erneute Query; gelöschte/anonymisierte Items verschwinden | keine formale Idempotenz-/Ledger-Semantik |
| Backups/Audit | dokumentiert | PITR/Backups bleiben; CloudTrail/CloudWatch | keine Erasure-Evidenz, keine Restore-Reconciliation |
| Öffentliche API | **nein** | nur direkter Lambda-Invoke (`internalAction`) | kein Gateway-Endpoint |

**Deployment-Realität:** Der `086a8be`-Abschlussbericht sagt
„DESTROY NOT EXECUTED"; ein späterer lokaler Destroy-Report meldet einen
erfolgreichen 37-Delete-Destroy. Diese Evidenz ist widersprüchlich. Es wird
**keine laufende Privacy-Instanz** angenommen; die Funktionen sind Code +
historische Testnachweise, keine derzeit verifizierte Infrastruktur.

## 3. RIS-Privacy-Istzustand

`POST /me/erasure` (G5, `agents/ecosystem/privacy_erasure.py`) macht:

1. Credentials revoken (zuerst)
2. API-Profile revoken
3. Nicht-terminale Work-Items auf `CANCELLED`
4. S3-Objekte über `delete_all_for_user` löschen (nur **aktuelle** Objekte)
5. UserProfile-Zeile löschen

Nicht erfasst:

- Cognito-Benutzer/Sessions
- ManualSearchProfile, CVSearchProfile, ATSSearchProfile, CVDocument-Metadaten
- S3-Objektversionen/Delete-Marker
- Cursor-, Idempotenz-, Capacity-, Lifecycle-Records
- Partner-Registry/Entitlements (Credentials/Profile werden revoict, Registry bleibt)
- terminale Work-Items (bewusst retained)
- Work-Item-Pagination: `_cancel_work` queryt nur eine Seite (kein
  `LastEvaluatedKey`-Loop); große Bestände können teilweise ungecancelt bleiben
- Jobsearches
- Backups/PITR/CloudTrail/CloudWatch
- Jobsearch-Browser-/Cache-Daten
- externe AI-Provider
- Receipts/Operation-IDs (G5 liefert nur ein synchrones Ergebnis)

`delete_all_for_user` listet aktuelle Objekte und ruft `delete_object` ohne
`VersionId`; bei Versioning entstehen Delete-Marker, alte Versionen bleiben.
Das ist **keine physische Löschung**.

## 4. Speicherdomänen und Verantwortlichkeiten

| Domäne | Verantwortung | Privacy-Rolle |
|---|---|---|
| Cognito | RIS-Installation | Identität; Löschung separat |
| RIS DynamoDB (UserProfile, WorkItems, Jobsearches, Entitlements, PartnerProfiles) | RIS | Controller/Processor |
| RIS S3 documents/data | RIS | Controller; Versionen separat |
| RIS Credentials/APIProfiles/Registry | RIS | Authentifizierung/Partner |
| RIS Cursor/Idempotenz/Capacity/Guards | RIS | technische Metadaten |
| Mays-Orders DynamoDB | Mays-Orders-AWS | eigener Controller/Processor |
| Jobsearch Browser/UI | Jobsearch | separate Grenze |
| AI-Provider | extern | Processor, falls tatsächlich aufgerufen |
| CloudTrail/CloudWatch/Backups | AWS/RIS | Audit/Recovery |

## 5. PrivacyReceiptV1

Implementiert: `agents/ecosystem/privacy_receipt.py` (rein, ohne Storage/API).
Dokumentiert: `docs/privacy/PRIVACY_RECEIPT_V1.md`.

Kern:

- `schemaVersion: 1`, `receiptId`, `subjectRef`, `tenantRef`,
  `partnerApplicationRef`, `issuerRef`
- `eventType`, `purpose`, `legalBasisRef`, `privacyNoticeVersion`,
  `privacyNoticeDigest`, `dataCategories`, `processingDomain`
- `operationRef`, `recordedAt`, `status`, `retentionPolicyRef`,
  `evidenceLevel`
- Ereignisse: `PRIVACY_NOTICE_PRESENTED`, `CONSENT_GRANTED`,
  `CONSENT_WITHDRAWN`, `CV_STORAGE_CONFIRMED`, `PROFILE_CREATED`,
  `PROFILE_UPDATED`, `AI_TRANSFER_REQUESTED`, `AI_TRANSFER_CONFIRMED`,
  `DATA_EXPORT_COMPLETED`, `ERASURE_REQUESTED`,
  `ERASURE_PARTIALLY_COMPLETED`, `ERASURE_COMPLETED`
- Evidence: `server_verified`, `third_party_confirmed`, `client_reported`,
  `requested`, `not_provable`
- `AI_TRANSFER_CONFIRMED` und `ERASURE_COMPLETED` akzeptieren **keine**
  client-reported/requested/not-provable Evidenz.
- Verbotene Felder/Werte: CV-Text, Prompts, Authorization/Bearer, Presigned
  URLs, Secrets, Tokens, private Keys; 8-KiB-Limit.
- Identitätsbindung: exakte Gleichheit von subject/tenant/partner/issuer.
- Zeitstempel: ISO-8601 mit Timezone; Zukunft >5 min abgelehnt.
- Unbekannte Felder, Events, Kategorien und Status werden strikt abgelehnt.

## 6. Rechtsgrundlagen-/Consent-Trennung

- Ein Receipt belegt ein **Ereignis**, nicht die rechtliche Wirksamkeit.
- `CONSENT_GRANTED` ist server-verifiziert als empfangene Handlung; die
  Einwilligung bleibt `REVIEW REQUIRED`.
- `legalBasisRef`/`retentionPolicyRef` sind Referenzen; `REVIEW_REQUIRED` ist
  der ausdrückliche Platzhalter.
- Ein Button-Klick oder allgemeine AGB sind kein automatischer
  Einwilligungsnachweis.
- `AI_TRANSFER_CONFIRMED` nur mit `third_party_confirmed` oder
  `server_verified`; ein Browser-Event bleibt `client_reported`.
- Keine pauschale DSGVO-Konformitätsaussage.

## 7. Dateninventar und Retention-Gaps

Vollständig: `docs/privacy/RIS_PRIVACY_DATA_INVENTORY_V1.md`.

Wesentliche Lücken:

- Partner-Profile-Items haben **kein TTL**; Löschung nur explizit (R08-C).
- Cursor 15 min / Idempotenz 24 h: TTL ist Cleanup, keine sofortige Löschung.
- Capacity-/Lifecycle-Records haben keinen User-Index; Erasure muss Keys aus
  Ressourcen ableiten.
- S3-Versionen/Delete-Marker überleben aktuelles Objekt-Delete.
- Backups/PITR werden nicht durch G5/R08-C gelöscht.
- Logs/CloudTrail/CloudWatch sind retention-, nicht subject-basiert.
- Kein Deletion-Ledger; Receipt-Journal ist erst spezifiziert.
- Cognito-Löschung ist nicht Teil von G5.
- Jobsearch-Browser/Cache und AI-Provider sind außerhalb der RIS-Kontrolle.

## 8. Erasure-Scope (R08-C)

Geplant, nicht implementiert:

1. Processing stoppen, Credentials/API-Profile/Sessions revoken.
2. ATS → CVSP → Manual → CV-Metadaten intern/guarded löschen; der öffentliche
   Parent-409 darf den autorisierten Lifecycle nicht dauerhaft blockieren.
3. S3 **alle Versionen + Delete-Marker** löschen und Leere verifizieren.
4. Cursor/Idempotenz/Capacity/Guards des Subjects/Ressourcen löschen.
5. Work-Items nach expliziter Retention entscheiden; terminale ggf. behalten.
6. UserProfile löschen.
7. Cognito-Löschung/Session-Revocation separat autorisiert.
8. `ERASURE_REQUESTED`/`PARTIALLY_COMPLETED`/`COMPLETED` mit Evidenz; keine
   Backup-/Provider-/physische Löschbehauptung ohne Nachweis.

Partial Completion und Wiederaufnahme sind Pflicht. Keine ungesicherte
Kaskade, kein öffentlicher Admin-Endpunkt ohne Freigabe.

## 9. Provider-Nachweisgrenzen

- Kein RIS-serverseitiger AI-Provider-Aufruf im Repo gefunden; AI-Transfer
  ist damit derzeit höchstens client-/drittanbieter-gemeldet.
- Browser-Event ≠ Provider-Erhalt/Löschung.
- Jobsearch kann Browser-/Cache-Daten halten; RIS kann sie nicht löschen.
- Mays-Orders-Privacy ist intern und projektisoliert; RIS darf nur bei
  tatsächlicher Order-Subject-Zuordnung aufrufen, keine CV-Daten kopieren.

## 10. Privacy-API-Entwurf (später)

`privacy.inspect`, `privacy.export`, `privacy.erase`, `privacy.receipts`,
`privacy.request_status`; Kontext ausschließlich aus verifizierter
JWT/Credential/Registry/Issuer-Kette. Self-only; Admin nur separater Scope.
Keine öffentliche Orders-Privacy-API. Details:
`docs/privacy/RIS_PRIVACY_CAPABILITY_CONTRACT.md`,
`docs/privacy/USER_PRIVACY_VIEW_SPEC.md`.

## 11. Tests

Neu: `tests/test_privacy_receipt_contract.py` — **30/30 PASS**:

- Schema/Roundtrip, unbekannte Felder/Events/Kategorien/Status
- Identitätsbindung, E-Mail-Ablehnung, Kontext-Mismatch
- Notice-Version/Digest, Consent-Ereignis vs. rechtliche Gültigkeit
- AI-Transfer-Evidenz (client-reported abgelehnt)
- Erasure-Evidenz/Status/Partial
- keine CV-/Prompt-/Token-/Presigned-/Secret-Inhalte
- Zeitstempel/Timezone/Zukunft
- Immutability, kanonisches JSON, Größenlimit
- Capability-Operations

Bestehende Privacy-Tests: **46/46 PASS** (G5 Lifecycle + Erasure Security,
venv mit boto3). Gesamtregression: **684 passed, 6 skipped** (inkl. 33
DynamoDB Local, R01–R07, Cursor, TransactionConflict, Legacy). Die 6 Skips
sind die geplanten R08-A/B/C-Abnahmetests in
`tests/test_privacy_capability_planned.py`; sie sind ausdrücklich nicht PASS.
Ohne boto3 schlagen 6 G5-Tests fehl, weil der Fake
`boto3.dynamodb.conditions.Key` nutzt; das ist eine
Testumgebungs-Abhängigkeit, kein R08-Regressionsbefund.

## 12. R08-Roadmap

- **R08-A** Benutzer-Nachweisjournal: append-only Receipt-Storage,
  Emission an Write-Points, `privacy.receipts`/`request_status`, Tests.
- **R08-B** Inspect/Export + „Mein Datenschutz": JSON/PDF, Nutzeransicht.
- **R08-C** Erasure: Partner-Profile, S3-Versionen, Cursor/Idempotenz,
  Cognito, Partial/Resume.
- **R08-D** Cross-Domain: Mays-Orders-Invoke, Provider-Evidenz,
  Jobsearch/Browser-Grenze, Legal/DPIA/Retention.

Details: `docs/privacy/R08_ROADMAP.md`.

## 13. Offene Release-Blocker

1. **Recht:** Legal basis, Art. 9, Art. 28, Art. 35, Retention und
   Notice-Wortlaut sind REVIEW REQUIRED.
2. **Erasure:** R07-Partnerprofile, S3-Versionen, Cursor/Idempotenz,
   Cognito, Jobsearches, terminale Work-Items nicht abgedeckt.
3. **Receipt-Storage/API:** nicht implementiert (R08-A/B).
4. **Backup/Restore:** kein Deletion-Ledger/Reconciliation.
5. **Provider/Jobsearch:** keine belastbare Lösch-Evidenz.
6. **R07-B:** weiterhin BLOCKED (IAM `Scan`, Orders-Kopplung, Testidentität);
   unabhängig von R08-A, aber Teil der Produktfreigabe.

## 14. Abschlussfrage

**Ist der gemeinsame Privacy-Vertrag belastbar genug, um R08-A —
Benutzer-Nachweisjournal — zu implementieren?**

**GO für R08-A (technische Implementierung), mit Auflagen.**

Evidence:

- `PrivacyReceiptV1` ist versioniert, strikt validiert, identitätsgebunden,
  größenbegrenzt und ohne CV-/Prompt-/Token-Inhalte (30 Contract-Tests).
- Ereignis-/Evidenzregeln verhindern, dass Client-Events als verifizierte
  Provider-/Erasure-Fakten erscheinen.
- 46 bestehende Privacy-Tests und 684 Gesamttests belegen die
  Nicht-Regression.

Auflagen vor einem **produktiven** Journal/Release:

1. Notice-Wortlaut, Version/Digest und Consent-UX rechtlich freigeben.
2. Retention-/Legal-Basis-Referenzen entscheiden (keine erfundenen Werte).
3. Receipt-Storage (append-only, Retention, Zugriff) und Emission-Punkte
   implementieren; keine CV-Rohdaten.
4. R08-C/D und Backup-/Provider-Grenzen abschließen.
5. Keine Produktivfreigabe, bevor R08-C Erasure und R07-B-Klärung stehen.

**R08-A: GO (technical), R08 production privacy release: BLOCKED by legal and
erasure gaps.**

## 15. Status

- **IMPLEMENTED:** `PrivacyReceiptV1` contract, context binding, validator.
- **VERIFIED LOCALLY:** 30 receipt tests, 46 privacy tests, 684 total.
- **SPECIFIED:** capability API, data inventory, legal matrix, user view,
  erasure scope, R08-A/B/C/D roadmap.
- **OPEN:** legal review, R08-A storage, R08-B export, R08-C erasure,
  R08-D cross-domain, backup reconciliation.
- **NOT RUN:** AWS/Mays-Orders live privacy calls.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.
