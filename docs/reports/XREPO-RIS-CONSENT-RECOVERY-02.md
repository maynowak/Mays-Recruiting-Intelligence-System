# XREPO-RIS-CONSENT-RECOVERY-02

**Status:** `B — BLOCKED BY AWS PLAN`  
**Zusätzliches Gate:** `C — AUTHENTICATED LIVE E2E REQUIRED`  
**No Main deployment / no Terraform apply / no production verification.**

## 1. Integration

| Punkt | Ergebnis |
|---|---|
| RIS Main vor Integration | `ae08267c3871d7bb85b7aa7ed2aed07a75385584` |
| RIS PR #10 | `MERGED` |
| Merge-Commit | `0eb3fe96a7e506e5c08e53816b7cc1c27b4e48f3` |
| Aktueller RIS Main | `0eb3fe96a7e506e5c08e53816b7cc1c27b4e48f3` |
| PR-Inhalt | bestehende Pilot-Freigabe + v4-Mapping + Tests + Doku |
| Neue Rechtsfreigabe | **keine** |

PR #10 war gegen den damaligen Main `CLEAN`/`MERGEABLE`. Es wurden nur
bestehende, bereits dokumentierte Pilotwerte wiederhergestellt:

- `application-storage/1.0 -> APPROVED`
- `legalApprovalRef = JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08`
- `application-storage-consent-2026-11-07-v4 -> 1.0`

## 2. Tatsächlicher Live-Lambda-Stand

Read-only AWS-Prüfung, Konto `240571105849`, Region `eu-central-1`,
Profil `mayaws`:

| Feld | Live-Wert |
|---|---|
| Funktion | `ris-dev-dev-agent` |
| Version | `$LATEST` |
| State | `Active` |
| LastModified | `2026-11-16T19:35:14.000+0000` |
| CodeSha256 | `9p67rKjkp0h0DAFS6Kht/GN5tc7YImQjjAnXw56Ub8A=` |
| Runtime | `python3.14` |
| Ausgelieferter Code | `application-storage/1.0 = DRAFT`, `legalApprovalRef = null` |
| `CONSENT_NOTICE_STATE_ENFORCED` | **nicht gesetzt** |
| `CONSENT_PILOT_ALLOWLIST` | **nicht gesetzt** |
| `APPLICATION_CONSENT_ENFORCED` | `false` |
| `CV_STORAGE_CONSENT_ENFORCED` | **nicht gesetzt** |
| `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED` | **nicht gesetzt** |
| `CONSENTS_TABLE` | gesetzt |
| `PARTNER_SURFACE_ENABLED` | gesetzt |

Der ausgelieferte Lambda-Code ist damit nachweislich der alte Main-Stand ohne
die Pilot-Freigabe. Das erklärt den deaktivierten Consent-Button und den
fail-closed BFF-Zustand (`grantAllowed=false`, `notice_not_active`).

Der Live-Stand unterscheidet sich zusätzlich vom früheren Pilotstand: Die
Consent-/CV-/Search-Enforcement-Flags und die RIS-Pilot-Allowlist fehlen.
Das ist eine bestehende Konfigurationsdrift und wird in diesem Gate **nicht
verändert**.

## 3. Deployment-Ziel und State

| Feld | Wert |
|---|---|
| Umgebung | `ris-dev` (Limited-Beta) |
| AWS Account | `240571105849` |
| Region | `eu-central-1` |
| Profil | `mayaws` |
| Workspace | `ris-dev` |
| State-Bucket | `mays-ris-tf-state-dev` |
| State-Key | `env:/ris-dev/dev/terraform.tfstate` |
| Lock-Tabelle | `mays-ris-tf-lock` |
| State serial | `78` |
| State lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| State resources | 273 |

## 4. Deployment-Plan

Der Plan wurde mit der aktuellen `main`-Konfiguration und dem neu gebauten
Agent-Bundle erzeugt. Es wurde **kein Apply** ausgeführt.

### Plan-Datei

```text
/tmp/opencode/ris-consent-recovery-02.tfplan
SHA-256: 88aef7470bdacbaa286525e2382af807a1034fafd4ee25be76125c352c1a4a43
```

### Plan-Ergebnis

```text
Plan: 0 to add, 6 to change, 22 to destroy.
```

Das ist ein **STOP-Gate**. Der Plan ist nicht freigabefähig.

Wesentliche Änderungen:

- `module.agent_transport[0]`: mehrere Ressourcen werden zerstört, weil das
  Modul in der aktuellen Konfiguration nicht mehr enthalten ist.
- `module.mays_orders[0].module.agent_transport[0]`: mehrere
  Dispatch-/Result-Transport-Ressourcen werden zerstört.
- `module.lambda.aws_iam_role_policy.order_result_transport[0]` wird zerstört.
- `module.mays_orders[0].module.iam.aws_iam_role_policy.agent_dispatch[0]`
  wird zerstört.
- Die Agent-Lambda würde zusätzlich die Env-Variablen
  `ORDER_RESULT_QUEUE_URL` und `ORDER_RESULT_SECRET_ARN` verlieren.
- `module.lambda.aws_lambda_function.agent`, Reader, Health und Orders-Lambdas
  würden aktualisiert.

Der Consent-Fix selbst ist nur ein Lambda-Code-Update. Die Zerstörungen
stammen aus der Drift zwischen aktuellem `main`-Terraform und dem Live-State,
nicht aus der Notice-Freigabe. Eine gezielte Umgehung per `-target`, State-
Manipulation oder Ignore-Regel ist nicht zulässig.

## 5. Tests

RIS fokussiert nach der Integration:

```text
tests/test_consent_notice_lifecycle.py
tests/test_consent_e2e_joint.py
tests/test_consent_repository.py
tests/test_consent_gate.py
# 27 passed
```

RIS Gesamtsuite auf dem gemergten Main:

```text
2620 passed
104 skipped
6 failed
```

Die sechs Fehler wurden auf einem sauberen `origin/main`-Worktree erneut
reproduziert:

- `test_composite_lifecycle` (3)
- `test_health_plane_integration` (1)
- `test_lambda_packaging` (1)
- `test_platform_handlers` (1)

Sie sind unabhängig vom Consent-Fix.

Jobsearch fokussiert:

```text
tests/api/ris-consents.test.mjs
src/components/StorageConsentLive.test.tsx
src/components/StorageConsentSection.active.test.tsx
src/lib/storageConsent.test.ts
# 63 passed
```

Kein Jobsearch-Produktcode geändert.

## 6. Authentifizierte Verifikation

**BLOCKED — AUTHENTICATED LIVE E2E REQUIRED.**

- Der vorhandene Operator-Session-Refresh-Token lieferte `invalid_grant`.
- Es ist keine gültige autorisierte Testidentität/kein gültiger Test-Token
  verfügbar.
- Es wurden keine Tokens, Passwörter, personenbezogenen Daten oder
  Consent-Historien protokolliert.
- Es wurde kein Auth- oder Consent-Gate umgangen.

Nach Freigabe eines nicht-destruktiven Plans ist ein authentifizierter
Live-Test erforderlich:

1. `GET /api/ris/consents` → `noticeState=APPROVED`,
   `noticeApproved=true`, `grantAllowed=true`.
2. POST Grant → `GRANTED`, v4-Textnachweis vorhanden.
3. Reload → Status bleibt erhalten.
4. Withdraw → `WITHDRAWN`.
5. Regrant nur nach neuer ausdrücklicher Einwilligung.
6. Keine Cross-Tenant-/Cross-User-Zugriffe.

## 7. Erforderliche Operator-Aktionen

1. **Terraform-Drift bereinigen:** aktuellen `main`-Terraformstand mit dem
   Live-State für die Agent-Transport-/Order-Result-Ressourcen
   zusammenführen. Kein `-target`, keine State-Manipulation.
2. Neuen Plan erstellen; Akzeptanzkriterium: **0 Delete / 0 Replace** und
   keine unerwarteten Env-Verluste. Der Plan muss separat freigegeben werden.
3. Entscheidung über die fehlenden Live-Pilot-Flags/Allowlist treffen. In
   diesem Gate wurden sie bewusst nicht verändert.
4. Autorisierte Testidentität oder gültigen Test-Token für den Live-E2E
   bereitstellen.
5. Erst nach Plan-Freigabe, Apply und erfolgreichem Live-E2E darf der
   Production-Status als wiederhergestellt gemeldet werden.

## 8. Freigabegrenzen

- Kein Terraform Apply.
- Kein Production-Deployment.
- Keine Cognito-/CloudFront-/DNS-Änderung.
- Keine Änderung an Consent-Enforcement oder Allowlist.
- Keine neuen Provider, Secrets oder externen Dienste.
- Keine allgemeine Rechtsfreigabe und kein allgemeiner Rollout.
