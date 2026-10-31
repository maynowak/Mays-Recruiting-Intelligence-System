# RIS-PARTNER-PROFILE-R04 — CV METADATA & SECURE DOCUMENT LIFECYCLE

## Git-Ausgangsstand

- Branch: `feature/ris-partner-profile-persistence-v1`
- Basis: `9de6a14` (R03)
- 39 untracked Dateien unverändert.

## Tatsächliche CV-/S3-Architektur

- Bucket: `terraform/modules/documents` — privat, SSE-S3, Versionierung **enabled**,
  PAB. Kein neuer Bucket in R04.
- Key-Schema (server-seitig): `tenant/{tenantId}/users/{userId}/documents/{docId}`.
- `lambda/documents.py`: `presign_upload`, `presign_download`, `delete_document`,
  `delete_all_for_user`.
- Lambda-IAM: `s3:PutObject/GetObject/DeleteObject` auf `tenant/*`,
  `s3:ListBucket` auf dem Bucket. `HeadObject` wird über `s3:GetObject`
  autorisiert.
- Bestehende `/me/documents`-Routen sind **nicht Terraform-managed**
  (OPEN-3, `IMPERATIVE_ONLY_ROUTES`); sie bleiben unverändert.

## Implementierte Endpunkte

| Methode | Pfad | Erfolg |
|---|---|---|
| GET | `/v1/partner/me/cvs` | 200 |
| POST | `/v1/partner/me/cvs` | 201 |
| GET | `/v1/partner/me/cvs/{cvId}` | 200 |
| PATCH | `/v1/partner/me/cvs/{cvId}` | 200 |
| DELETE | `/v1/partner/me/cvs/{cvId}` | 200 |
| POST | `/v1/partner/me/cvs/{cvId}/document/upload` | 200 (Ticket) |
| POST | `/v1/partner/me/cvs/{cvId}/document/complete` | 200 (READY) |
| GET | `/v1/partner/me/cvs/{cvId}/document` | 200 (Download-URL) |

Alle Routen sind explizit in Terraform, mit dem bestehenden Human-JWT-Authorizer
und der bestehenden Lambda-Proxy-Integration. Kein Wildcard-Proxy.

## Statusmaschine

```
pending ──upload ticket──> upload_pending ──complete (S3 bestätigt)──> ready
                                  │
                                  └── retry ticket (gleiche documentId)
```

- `pending`: Metadaten existieren, kein Dokument zugeordnet.
- `upload_pending`: serverseitige `documentId` reserviert, Ticket ausgestellt.
- `ready`: **nur** nach `HeadObject` mit `ContentLength > 0`.
- `delete_failed` / `error`: reserviert; R04 nutzt `delete_failed` nicht
  automatisch (Löschfehler behalten die Metadaten und melden 502).
- Kein Re-Upload nach `ready` (409) → kein unbeabsichtigter S3-Overwrite.

## Eigentümer- und Partnerisolation

- Dual-Auth wiederverwendet: Cognito JWT + `X-Api-Credential` + Partner-Registry
  + L03-Tenant-Auflösung.
- `userId` = JWT `sub`, `tenantId` = serverseitig aufgelöst,
  `partnerApplicationId` = Registry-`applicationId`, `issuer` = JWT `iss`.
- Cross-User → 404, Cross-Tenant → 403, Cross-Partner → 403, Cross-Issuer → 404.
- Manipulierte Identity-Felder im Body → 400 (`CLIENT_IDENTITY_FORBIDDEN`).
- **default-Tenant-Fallback:** `documents.build_key` behält den historischen
  `default`-Fallback für `/me/documents`. Partner-CVs übergeben
  `require_tenant=True`; der Partner-Kontext weist einen nicht auflösbaren
  Tenant bereits mit 403 ab, bevor S3 berührt wird. Kein Partner-CV kann im
  `default`-Bucket landen.

## Datenkonsistenz

- Nutzt `PartnerProfileRepository` (R02) für CV-Metadaten.
- Atomare 10-CV-Kapazität (`TransactWriteItems`-Zähler, R02-R2).
- Bedingte Creates/Updates/Deletes; `version` für optimistisches Locking → 409.
- `cvId` (Metadaten-ID) und `documentId` (S3-Key-Bestandteil) sind getrennt;
  die API gibt beide separat zurück.
- Keine Browser-File-Objekte, keine CV-Rohtexte, keine Presigned-URLs in
  DynamoDB (per Test geprüft).
- Upload-Ticket ist idempotent bei `upload_pending` (gleiche `documentId`).

## Löschen und Versionierung

- DELETE löscht die **aktuelle** Objektversion (`DeleteObject`) und danach die
  Metadaten. Auf dem versionierten Bucket entsteht ein **Delete-Marker**.
- Die Antwort klassifiziert: `document.existed`, `document.deleteMarker`,
  `document.physicalPurge=false`, `physicalPurge=false`.
- Physische Löschung **aller** Versionen (`DeleteObjectVersion`) ist **nicht**
  implementiert (eigenes Gate).

## Auswirkungen auf den bestehenden Erasure-Lifecycle

- `delete_all_for_user` (G5) bleibt unverändert und löscht weiterhin über das
  Präfix `/users/{userId}/documents/`.
- Partner-CV-Metadaten werden über `DELETE /me/profile`/Erasure **nicht**
  automatisch mitgelöscht; das ist ein offener Punkt für einen späteren
  Erasure-Gate (siehe unten).

## Tests

- Neu: `tests/test_partner_cv_document_api.py` — 29/29 PASS
  (CRUD, Kapazität 10, parallele Creates, Version, Upload/Complete/Download,
  S3-Objekt fehlt/leer, Retry, Re-Upload-Sperre, Löschfehler, Versioned-Delete,
  keine Presigned-URL persistiert, Cross-User/-Tenant/-Partner/-Issuer,
  fehlender Tenant, gefälschte Identity, kein Agent-/Modellaufruf).
- R01–R03 + OpenAPI gesamt: 273/273 PASS.
- Bestehende Dokumenten-Tests: 11/11 PASS.
- R04-relevant gesamt: **284/284 PASS**.

## Terraform / OpenAPI

- 8 explizite Routen in `terraform/modules/api/main.tf`.
- `docs/api/API-STANDARD.md` und `docs/api/openapi-platform.yaml` ergänzt
  (`PartnerCvV1`, `PartnerCvInput`, `PartnerCvUploadTicket`,
  `PartnerCvDownload`, `PartnerCvDeleteResult`).
- `terraform fmt -check` (versionierte Dateien): PASS; `validate`: PASS
  (vorbestehende Deprecation-Warnings).
- OpenAPI-Konsistenz: 47/47 PASS.

## Abgrenzung

- **IMPLEMENTED:** 8 Endpunkte, Statusmaschine, Contract-Erweiterung
  (`documentId`, `processingStatus`, `contentType`, `etag`, `uploadedAt`),
  S3-Helfer (`head_document`, `delete_document_report`, `require_tenant`),
  Terraform-Routen, OpenAPI, Tests, Report.
- **VERIFIED:** 284/284 R04-relevante Tests PASS; Terraform fmt/validate PASS;
  OpenAPI-Konsistenz PASS.
- **NOT RUN:** echte S3-/DynamoDB-Integration (kein AWS-Aufruf); volle
  `tests/`-Suite bleibt wegen fehlendem boto3 / präexistenten
  Windows-/Installer-Fehlern unvollständig lauffähig.
- **NOT DEPLOYED:** kein Apply/Destroy/Deploy, kein Push/PR/Merge.

## Offene Punkte

1. **Physische Löschung aller S3-Versionen** (`DeleteObjectVersion`, Lifecycle)
   — separates Privacy-/Retention-Gate.
2. **Erasure-Integration:** Partner-CV-Metadaten + S3-Objekte beim
   `DELETE /me/profile`/Erasure mitlöschen.
3. **Live-E2E** gegen echtes API Gateway/S3/DynamoDB (R07/E2E-Gate).
4. **CV-/ATS-Suchprofile** über HTTP bleiben außerhalb von R04.
