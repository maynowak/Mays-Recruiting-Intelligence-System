# JM-RIS-CONSENT-RECONCILIATION-01 — Umsetzung

- **Datum:** 2026-11-06
- **Modus:** Analyse + Implementierung + lokale Tests + Doku. **Kein AWS-Zugriff, kein Terraform-Apply, kein Deployment.**
- **Ergebnis:** `GO — TECHNICAL CONSENT INTEGRATION`, `NO GO — AUTOMATIC LEGAL APPROVAL OF NOTICE VERSION 1.0`

---

## 1. Ausgangslage

Die RIS-Consent-Implementierung aus `RIS-PARTNER-USER-CONSENT-01` (Commit
`133d6eb`, Doku `9ced10e`) ist vorhanden und lokal verifiziert: Vertrag
`application-storage`, Grant/Withdraw/Regrant, Status-/History-API,
DynamoDB-Repository, versionierte Ereignisse, Tenant-/Partner-/Benutzer-Isolation
und ein serverseitiges Gate für fünf ApplicationV1-Schreibpfade
(`APPLICATION_CONSENT_ENFORCED`, Default `false`).

Offen waren laut Arbeitsauftrag zwei Punkte:

1. **Erklärungsversionen sind nicht gleichwertig.** RIS spricht von
   `noticeVersion=1.0`, Jobsearch von `2026-11-04-draft-1`. Beide sind Entwürfe;
   es gibt keine belegte rechtliche Freigabe.
2. **Technische Zustände fehlten.** Es gab keine Unterscheidung zwischen
   `DRAFT`, `APPROVED`, `ACTIVE`, `SUPERSEDED`. `1.0` war einfach „akzeptiert“.

Zusätzlich waren die vier Consent-Routen zwar live, aber nicht im kanonischen
OpenAPI-Dokument (`docs/api/openapi-platform.yaml`) beschrieben. Drei
Contract-Governance-Tests schlugen deshalb bereits auf `main` fehl.

---

## 2. Analyse der Versionszuordnung

| Quelle | Kennung | Bedeutung | Abbildung auf RIS |
|---|---|---|---|
| RIS | `purpose=application-storage`, `noticeVersion=1.0` | technischer Entwurf | — |
| Jobsearch | `STORAGE_CONSENT_TEXT_VERSION=2026-11-04-draft-1` | Anzeigetext-Entwurf | **keine** |
| Jobsearch | `STORAGE_CONSENT_PRIVACY_NOTICE_VERSION=2026-11-04-draft-1` | Datenschutzhinweis-Entwurf | **keine** |

`2026-11-04-draft-1` ist eine **Jobsearch-Kennung** und darf nicht als
RIS-`noticeVersion` akzeptiert werden. Eine Gleichsetzung mit `1.0` entsteht
nicht durch Umbenennen, sondern nur durch eine dokumentierte rechtliche
Freigabe. Beide Kennungen bleiben `DRAFT`.

---

## 3. Umgesetzte Änderungen

### 3.1 Notice-Version-Lebenszyklus (`jobsearch/consent_contract.py`)

- Zustände `DRAFT`, `APPROVED`, `ACTIVE`, `SUPERSEDED`.
- `NoticeVersion`-Registry (`NOTICE_REGISTRY`) mit `legalApprovalRef`,
  `supersedes` und `externalRefs`.
- `application-storage/1.0` ist als **`DRAFT`** registriert, ohne
  Rechtsfreigabe (`legalApprovalRef = null`).
- `EXTERNAL_NOTICE_REFS` kennt `2026-11-04-draft-1` (Quelle
  `mays-jobsearch`) als Entwurf, **ohne** Zuordnung (`noticeVersion: null`).
- `CONSENT_NOTICE_STATE_ENFORCED` (Default `false`):
  - `false`: bekannte Versionen sind technisch grantbar (synthetische/
    technische Läufe).
  - `true`: nur `APPROVED`/`ACTIVE` sind grantbar; sonst
    `422 NOTICE_NOT_ACTIVE`.
- `status_payload` liefert zusätzlich `noticeState`, `noticeApproved`,
  `acceptedForNewGrant`.
- `catalog_payload` / `external_refs_payload` liefern den Katalog für die API.

### 3.2 Repository (`jobsearch/consent_repository.py`)

- Ein **neuer** Grant (oder Regrant) wird bei aktiver State-Enforcement gegen
  den Lifecycle geprüft.
- Ein **wiederholter** Grant derselben Version bleibt idempotent, auch wenn
  die Version inzwischen `SUPERSEDED` ist (kein neues Ereignis, keine neue
  Einwilligung).
- **Widerruf bleibt immer möglich**, unabhängig vom Lifecycle-State.
- Bestehende Grants werden nie umgeschrieben oder rückdatiert.

### 3.3 API (`lambda/handler.py`)

`GET /v1/partner/me/consents` liefert additiv:

```json
{ "items": [...], "catalog": [...], "externalRefs": [...] }
```

Keine neue Route, keine Änderung der Auth- oder Tenant-Grenze. `NOTICE_NOT_ACTIVE`
wird über den bestehenden `ConsentContractError`-Pfad als `422` ausgegeben.

### 3.4 Kanonisches OpenAPI (`docs/api/openapi-platform.yaml`)

Die vier Consent-Routen sind jetzt dokumentiert
(`terraform-managed`, `ApiCredential`, Fehlercodes). Damit sind die drei
vorher fehlschlagenden Contract-Governance-Tests grün.

### 3.5 Doku

- `docs/contracts/CONSENT-V1.md`: Lifecycle-Tabelle, Katalogantwort,
  Jobsearch↔RIS-Zuordnung, Aktivierungs-Gates, Migrationsschritte.
- `docs/api/API-STANDARD.md`: Statusantwort um `catalog`/`externalRefs`
  ergänzt, `NOTICE_NOT_ACTIVE` dokumentiert.

---

## 4. Synthetischer E2E (lokal, ohne AWS)

`tests/consent_e2e_harness.py` und `tests/test_consent_e2e_joint.py` bilden den
Acht-Schritt-Auftrag aus §8 ab, gegen die echten Repositories **und** das echte
Handler-Gate:

| # | Schritt | Ergebnis |
|---|---|---|
| 1 | Kein Consent → Schreibzugriff verweigert | PASS (Repository + Handler `403 CONSENT_REQUIRED`) |
| 2 | Zustimmung → Grant gespeichert | PASS (`GRANTED`, version 1, `noticeState=DRAFT`) |
| 3 | Bewerbung erstellen → erfolgreich | PASS |
| 4 | Widerruf → Withdraw gespeichert | PASS (`WITHDRAWN`, version 2) |
| 5 | Bewerbung ändern → verweigert | PASS (Gate erneut `403`) |
| 6 | Lesen/Export/Löschen weiterhin möglich | PASS |
| 7 | Erneute Zustimmung → Regrant gespeichert | PASS (`REGRANTED`, version 3) |
| 8 | Historie vollständig | PASS (`REGRANTED`, `WITHDRAWN`, `GRANTED`) |

Zusätzlich: Isolationstest — ein fremder Benutzer und ein fremder Tenant haben
keinen Consent und werden blockiert.

Das Jobsearch-BFF selbst ist nicht Teil dieses Repositories
(`installer/projects/mays_jobsearch` ist ein ignorierter externer Clone). Der
E2E simuliert die BFF-Aufrufe am RIS-Repository-Seam; die reale
Jobsearch-Anbindung bleibt offen.

---

## 5. Tests

| Lauf | Ergebnis |
|---|---|
| `tests/test_consent_notice_lifecycle.py` | 8 passed |
| `tests/test_consent_e2e_joint.py` | 2 passed |
| Consent + Application + Auth + P20 + OpenAPI (fokussiert) | 96 passed |
| Volle Suite `tests/` | **2424 passed**, 56 skipped, 2 failed (vorbestehend, s. u.) |

Vorbestehende, nicht durch diese Änderung verursachte Fehler (im sauberen
`HEAD`-Worktree reproduziert, beide umgebungsabhängig):

- `tests/test_health_plane_integration.py::TestPipelineEmitsHealthEvents::test_entitlement_denial_is_not_a_degradation`
- `tests/test_platform_handlers.py::TestAgentAPI::test_execute_agent`
  („durable subject fence store is not configured“)

`tests/test_credential_verification.py::TestGenerationDigest::test_secret_opaque_random`
ist zufallsbasiert und flaky (nicht durch diese Änderung beeinflusst).

Die drei zuvor roten OpenAPI-Governance-Tests sind durch die Dokumentation der
Consent-Routen jetzt grün.

---

## 6. Terraform / Deployment

**Kein Apply, keine AWS-Mutation.** Es wurden keine Terraform-Dateien
geändert; die Ressourcen-Topologie bleibt unverändert.

Der Agent-Bundle wurde deterministisch neu gebaut, weil sich
`jobsearch/consent_contract.py`, `consent_repository.py` und `lambda/handler.py`
geändert haben:

- `terraform/lambda.zip`: 83 Dateien,
  SHA-256 `efcdcf25a846801006712ddc6f077b48d85ce68e5140d2a9969f7f440c44122a`
- `lambda/dist/orders-reader.zip`: SHA-256
  `e405858718101db34a8d5c1237e36d41a47b7dceb8e0ebff8b01bd86d1c366e5`

Konsequenz: Der in `RIS-PARTNER-USER-CONSENT-01` dokumentierte Plan
(SHA-256 `94a8086dd94929ec81a82c181044b033ec4dbf9892bfa4543b0341a496b9f217`,
10 CREATE / 1 UPDATE) ist **nicht mehr gültig**, weil sich der
Lambda-Source-Hash ändert. Vor einem Deployment ist ein **neuer** Plan zu
erzeugen, zu prüfen und gesondert freizugeben. Die erwartete Topologie bleibt
10 CREATE / 1 UPDATE / 0 DELETE / 0 REPLACE; das ist zu verifizieren, nicht
anzunehmen.

Aktivierungsreihenfolge unverändert:

1. neuer Plan, Review, explizite Apply-Freigabe;
2. Jobsearch-BFF an die Consent-Endpunkte anbinden;
3. Erklärungsversion rechtlich freigeben und zuordnen;
4. synthetischer Grant/Withdraw/Regrant gegen die erreichbare API;
5. `APPLICATION_CONSENT_ENFORCED=true` gesondert freigeben.

---

## 7. Statusmatrix (fortgeschrieben)

| Bereich | Status |
|---|---|
| RIS-Consent-Implementierung | IMPLEMENTED |
| RIS-Consent-Tests | VERIFIED LOCAL |
| Notice-Version-Lifecycle (DRAFT/APPROVED/ACTIVE/SUPERSEDED) | IMPLEMENTED |
| Jobsearch-Draft `2026-11-04-draft-1` | DRAFT, **nicht** akzeptiert |
| Rechtliche Freigabe als `1.0` | NICHT NACHGEWIESEN |
| RIS-Consent-Deployment | PENDING (neuer Plan erforderlich) |
| Jobsearch-Einwilligungsoberfläche | VORHANDEN (externes Repo) |
| Jobsearch-RIS-Consent-Anbindung | PENDING (Vertrag geliefert) |
| Serverseitiges Consent-Gate | IMPLEMENTED, NICHT AKTIV |
| Synthetischer Integrations-E2E | PASS LOCAL / PENDING LIVE |
| Produktive Verarbeitung auf dieser Grundlage | NICHT FREIGEGEBEN |

---

## 8. Offene Punkte

1. Neuer Terraform-Plan nach Bundle-Neubau (kein Apply ohne Freigabe).
2. Jobsearch-BFF-Implementierung im externen Repo (Status/Grant/Withdraw/History).
3. Rechtliche Freigabe des Erklärungstexts und der Zuordnung zu `1.0`.
4. Aufbewahrungsentscheidung für Consent-Nachweise (weiterhin kein TTL).
5. Consent in Privacy-Inspect/Export/Erasure aufnehmen (Folgearbeit).
6. Zwei vorbestehende, umgebungsabhängige Testfehler (Health-Plane, Agent-Fence).

---

## 9. Evidence / Dateireferenzen

- `jobsearch/consent_contract.py` — Lifecycle, Registry, Katalog
- `jobsearch/consent_repository.py` — Grant/Withdraw-Enforcement
- `lambda/handler.py` — Statusantwort mit `catalog`/`externalRefs`
- `docs/contracts/CONSENT-V1.md` — Vertrag §9/§9a/§9b/§12
- `docs/api/API-STANDARD.md`, `docs/api/openapi-platform.yaml`
- `tests/test_consent_notice_lifecycle.py`
- `tests/test_consent_e2e_joint.py`, `tests/consent_e2e_harness.py`
- `tests/test_consent_repository.py`, `tests/test_consent_gate.py`
- `docs/AI_AUDITLOG.md`

Keine Secrets, keine Tokens, keine AWS-Ressourcen-ID-Änderung, keine
Cognito-/CloudFront-/DNS-/ACM-Mutation.
