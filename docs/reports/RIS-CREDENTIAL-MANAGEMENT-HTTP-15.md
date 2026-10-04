# RIS-CREDENTIAL-MANAGEMENT-HTTP-15 — Credential Management HTTP API

STATUS: GREEN (implementiert + getestet; KEIN GW, KEIN TF, KEIN AWS)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, 03d5171 (+ uncommitted: Handler-Layer + P14-Correlation + 1 Test + diese Reports)
- Basis (verbindlich): P14-Service (alle Entscheidungen) + P10-Profile + P09-Verify + Handler-Konventionen (401/403/404, JSON-Bodies, Pfad-Parsing, Spoof-Ignoranz).
- Scope: NUR HTTP-Schicht (7 Routen-Dispatch, Actor-Mapping, Syntax-Validation, Error-Mapping, Hygiene, Audit-Weitergabe). NICHT: M2M-Usage/Authorizer, OAuth/mTLS, neue Permission-Engine/Domain, Offer/Entitlement/APIProfile-CRUD, Sandboxing, Cognito-Migration, Provisionierung, TF/AWS.
- Classification: GREEN (42 Tests + Suite ohne Regression).
- AWS/Terraform/Migration: NONE (verifiziert). Secrets: NONE (Tests + Scan).
- Git: nur P15-Dateien (s. Commit).
- Next: GW-Verdrahtung (Human-Pfad), Management-Endpoints-Ausbau, Offer-Anzeige -> HARD STOP.

## 1. Repository-Befund ZS2 (gelesen, nicht geaendert)

- Handler-Routing (Pfad+Methode, manuelles Segment-Parsing wie Documents-Routen; KEINE Introspection-Dispatch-Aenderung noetig).
- Fehler: `{statusCode, body:{error}}`-Huelle; 400 "Request body must be valid JSON" (wiederverwendet).
- KEINE Idempotency-Key-/X-Correlation-Id-/Pagination-Konvention im Bestand -> Standard-Namen neu, dokumentiert (`Idempotency-Key`, `X-Correlation-Id` passthrough, KEINE Pagination wie Bestand).
- pathParameters-Muster existiert, greift ohne GW-Routen nicht -> Pfad-Segment-Parsing im Handler (wie Documents-Fallback).
- Rollen aus JWT-`groups` ableitbar (`admins`/`Staff`, sonst Owner); Tenant aus Claim; KEINE Rollenmatrix im Handler noetig (P14 entscheidet).

## 2. Route Contract (logisch, KEINE GW-Aenderung)

`POST|GET /v1/apiprofiles/{pid}/credentials`, `GET .../{cid}`, `POST .../{cid}/{rotate,disable,enable,revoke}`. Unbekannte Pfade/Methoden -> 404 (Bestandskonvention, kein 405).

## 3. Auth Boundary (Human JWT only)

Alle Routen: JWT-Kontext Pflicht (401 sonst); KEIN `Authorization: Bearer ris_...`-Pfad hier (M2M bleibt Folge-Gate). Rollen-Mapping: admins->admin, Staff->staff, sonst owner (IDs verifiziert P14-seitig).

## 4. Path Binding (UNTRUSTED, neutral)

apiProfileId/credentialId aus Pfad: Existenz/Ownership/Tenant/Status PRUEFT P14 (Handler vertraut nichts). Fremdes Profil (Owner) -> 404; fremde Credential -> 404; Cross-Profile-cid (A-credential unter B-Pfad) -> 404 VOR Mutation (Pre-Read, keine Seiteneffekte). X-Api-Profile != Pfad -> 400 + Warnung (Header ueberschreibt NIE).

## 5. Endpoints (Ergebnisse, getestet)

- Issue 201 (+secret EINMALIG, inkl. alle §7-Felder) / Replay 200 (secret null, duplicate true); clientRef-Body wird IGNORIERT (Profil-Spiegel gewinnt, Spoof-Konvention).
- List 200 (`{items}` ohne Secret/Digest) / Get 200 / 404 neutral.
- Rotate 201 (neu + Secret, alt REVOKED) / Replay 200 (null).
- Disable/Enable/Revoke 200 (Metadaten, nie Secret/Digest); Enable abgelaufen -> 409; REVOKED-enable -> 409.
- Reason: optional ueber Body (POST) / Query (GET); vorhanden = nicht-leer (400 sonst); fachliche Pflicht in P14.

## 6. Rollen/Audit/Correlation (keine Zweit-Matrix)

Rollen NUR gemappt, nie entschieden (P14 autoritativ: Owner-Self/ Admin/Cross-Tenant-mit-Reason/Staff-Support + Admin-Lock-Unumgehbarkeit). correlationId (X-Correlation-Id oder GW-RequestId) wird an ALLE P14-Aufrufe durchgereicht (additive `correlation_id`-Parameter, abwaertskompatibel; Audit-Felder ergaenzt).

## 7. Error Mapping / Validation / Hygiene (getestet)

401 (kein JWT) / 403 (bekannt-unberechtigt; Owner-Fremd -> 404 neutral) / 404 (unbekannt/fremd/inkonsistent) / 409 (Conflict + StateConflict) / 400 (Syntax/Blind-Merge-Schutz/Allowlist) / 503 (Stores unkonfiguriert/Store-Ausfall) / 500 neutral (unerwartet, geloggt). Handler validiert NUR Syntax (JSON/Objekt/Allowlist/Pflicht/Typen/Parsbarkeit/nicht-leer); Fachlogik 100% P14. Secret-Hygiene: Secret NUR in frischen 201-Issue/Rotate-Bodies; nie in List/Get/Errors/Logs/Audit (Tests 1-15); keine JWT-/Header-Spiegelung.

## 8. Tests (42, ALLE GRUEN)

Route-Matrix je Operation (200/201/400/401/403/404/409/503 wo semantisch moeglich) + Header-Match/Mismatch + Rollen-Matrix (Owner/Admin/Cross-Tenant±Reason/Staff-Support/Cross-Profile-404) + Lifecycle + Idempotency (Key/Replay/Mismatch/Rotation) + Hygiene 1-15 + Integration (Issue->AUTHORIZED->Disable->403->Enable->AUTHORIZED->Revoke->403, KEINE neue Verify-Logik).

## 9. Regression / IAM+AWS+TF / Folge-Punkte

- Suite: 699 passed (657 + 42), 8 skipped; 15 failed + 1 ERROR Hash-IDENTISCH zur P14-Baseline (pre-existing).
- IAM/TF/AWS/Migration: NONE (keine Tabellen/Rollen/Routen/Deploys; Handler nutzt lazy Stores mit 503-Degradation).
- Offen: GW-Verdrahtung (Human-Pfad) · Credential-Management-Endpoints-Ausbau · Offer-Anzeige · Scope-Vokabular · Provisionierung · Default-Policy · B3-Fix · Sandboxing · Admin-Migration. Hinweis: Spec-Beispiel `"credentialType": "opaque_bearer"` vs. verbindlich P09 `"opaque-bearer-v1"` (versioniert) — P09-Vertrag gilt (Beispiel illustration, kein Widerspruch).

**HARD STOP (keine Implementierung ueber diesen Contract hinaus, keine Mutation).**
