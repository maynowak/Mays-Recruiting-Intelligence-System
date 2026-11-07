# RIS-PARTNER-USER-CONSENT-01 — Implemented / Verified Local / Deployment Pending

- **Datum:** 2026-11-06
- **Modus:** Implementierung + lokale Tests + Plan; **kein Apply, keine AWS-Mutation**
- **Ergebnis:** **IMPLEMENTED / VERIFIED LOCAL / DEPLOYMENT PENDING**

---

## 1. Ausgangsstand

Kein Consent-Modell, keine Consent-Tabellen, keine Consent-Routen. Vorhanden waren Partner-Registry, APIProfile, Credentials, ApplicationV1, Privacy-Receipts, Deletion-Ledger, Inspect/Export/Erasure.

| Komponente | Vorhanden | Wiederverwendbar | Fehlende Funktion |
|---|---|---|---|
| Consent-Modell | ❌ | — | Zweck-/Status-/Historienvertrag |
| Consent-Persistenz | ❌ | DynamoDB-Muster, bedingte Writes | eigene Tabelle |
| Consent-API | ❌ | Partner-Dual-Auth, Route-Muster | 4 Routen |
| Consent-Audit | ❌ | append-only-Muster (Receipts) | Ereignishistorie |
| Consent-Gate | ❌ | Handler-/Repo-Struktur | Schreibpfad-Gate |
| Privacy-Integration | teilweise | Inspect/Export/Erasure | Consent-Export/-Löschung offen |

`privacy_receipts` wurde **nicht** als Consent-Tabelle umgedeutet (anderer Vertrag: unveränderliche Nachweise, andere Schlüssel).

---

## 2. Vertrag

`jobsearch/consent_contract.py`

- Identität: `tenantId|partnerApplicationId|issuer|subject` (serverseitig), `purpose`
- Zweck-Katalog: `application-storage` → `noticeVersion` `1.0`
- Zustände: `NOT_GRANTED` (virtuell) → `GRANTED` → `WITHDRAWN` → `GRANTED` (Ereignis `REGRANTED`)
- Unbekannter Zweck → 404, erfundene Version → 422

---

## 3. Persistenz

`jobsearch/consent_repository.py`, Tabelle `consents`:

| Item | Schlüssel | Inhalt |
|---|---|---|
| aktueller Zustand | `scopeKey` / `PURPOSE#<purpose>` | status, noticeVersion, grantedAt, withdrawnAt, version |
| Ereignis | `scopeKey` / `EVENT#<purpose>#<ts>#<id>` | event, status, noticeVersion, occurredAt, subject, identityRef |

- `scopeKey = tenant|partner|issuer|subject` → Tenant-/Partner-/Issuer-/User-Isolation ohne GSI.
- Zustandswechsel: `TransactWriteItems` mit `version = :expected` plus append-only Event.
- Wiederholtes Grant ist idempotent (kein neues Event).
- Konflikt → `409 CONFLICT`; keine stillen Teilerfolge.
- Keine E-Mails, keine Tokens, keine CV-Inhalte, keine Erklärungsvolltexte pro Ereignis.
- Kein TTL — Aufbewahrung ist **offen** (keine stillschweigende Unendlichkeit als Freigabe).

---

## 4. API

Vier Routen, identisch auf Kernel-API und Jobsearch-Edge:

| Methode | Route |
|---|---|
| GET | `/v1/partner/me/consents` |
| POST | `/v1/partner/me/consents` |
| POST | `/v1/partner/me/consents/withdraw` |
| GET | `/v1/partner/me/consents/history` |

Dual-Auth bleibt zwingend (JWT + `X-Api-Credential` + ACTIVE Partner/Profil/Tenant). Vertrag: `docs/contracts/CONSENT-V1.md`.

---

## 5. ApplicationV1-Consent-Gate

`_application_consent_error(ctx)` in `lambda/handler.py`, aktiv bei `APPLICATION_CONSENT_ENFORCED=true`:

| Operation | Gate |
|---|---|
| Create, Patch, Status, History, Anschreiben | **ja** → `403 CONSENT_REQUIRED` |
| Liste, Detail, Export, Delete | **nein** |

- Fail-closed: Store nicht erreichbar → 403.
- Kein simuliertes Consent, kein stiller Fallback.
- Rollout-Default `false`, damit die bereits verifizierte Jobsearch-Anbindung nicht bricht. Aktivierung erst, wenn Jobsearch den Consent-Dialog ausliefert.

---

## 6. Privacy-Integration

- Geteilte Identität wie ApplicationV1 (`iss+sub`, Tenant/Partner).
- Keine JWTs/Keys/E-Mails in Consent-Datensätzen.
- Inspect/Export/Erasure um Consent-Erweiterung **offen** — bewusst nicht in V1, weil Aufbewahrung/Löschung von Einwilligungsnachweisen eine Rechtsentscheidung ist.
- Widerruf blockiert keine Datenschutzrechte (Lesen/Export/Löschen bleiben frei).

---

## 7. Tests

| Lauf | Ergebnis |
|---|---|
| `tests/test_consent_repository.py` | **7 passed** (Grant/Withdraw/Regrant/History/Idempotenz/Isolation/Konflikt/ungültige Zwecke) |
| `tests/test_consent_gate.py` | **7 passed** (403 ohne Consent, 200 mit, inaktiv ohne Rollout, fail-closed, 5 Schreibpfade, Routen/Terraform) |
| Auth-/Contract-/P20-/Application-Set | **41 passed** |
| `terraform fmt` / `validate` | PASS |

Keine Tests entfernt; zwei bestehende Tests wurden an die neuen Routen/Env angepasst (Route-Zähler, Surface-Gate in Boundary-Tests).

---

## 8. Terraform-Diff (nicht angewendet)

| Aktion | Anzahl |
|---|---:|
| CREATE | **10** (1 Tabelle `consents`, 4 Kernel-Routen, 4 Edge-Routen, 1 IAM-Policy) |
| UPDATE | **1** (`module.lambda.aws_lambda_function.agent`: `CONSENTS_TABLE`, `APPLICATION_CONSENT_ENFORCED`) |
| DELETE / REPLACE | 0 / 0 |
| Geschützte Ressourcen | 0 Änderungen |

Plan-SHA-256: `94a8086dd94929ec81a82c181044b033ec4dbf9892bfa4543b0341a496b9f217`. Kein Apply.

---

## 9. Offene rechtliche/operative Entscheidungen

1. **Erklärungstext + noticeVersion-Inhalt** (Rechtsgrundlage, Widerrufsfolgen) — Recht.
2. **Aufbewahrung** von Consent-Nachweisen und Ereignissen — Recht (deshalb kein TTL).
3. **Consent in Inspect/Export/Erasure** aufnehmen — nach Aufbewahrungsentscheidung.
4. **Rollout**: `APPLICATION_CONSENT_ENFORCED=true` erst nach Jobsearch-Consent-UI.
5. **Widerruf vs. bestehende Daten**: aktuell keine automatische Löschung; Löschzusage muss kommuniziert werden.

---

## 10. Jobsearch-Handoff

`docs/contracts/CONSENT-V1.md` (Endpunkte, Schemas, Fehler, Auth, Zustände, Rollout, Migration). Keine Änderungen im Jobsearch-Repo in diesem Auftrag.

---

## 11. Deployment-Readiness

**Lokal verifiziert, nicht deployt.** Erforderlich vor Deployment:

1. Apply des Plans (10 Creates, 1 Update).
2. Jobsearch-Consent-UI + BFF-Routen (`/consents`).
3. Erst dann `APPLICATION_CONSENT_ENFORCED=true` setzen.
4. Rechtliche Freigabe für Erklärungstext/Aufbewahrung.

**Keine rechtliche Freigabe durch dieses Arbeitspaket.**
