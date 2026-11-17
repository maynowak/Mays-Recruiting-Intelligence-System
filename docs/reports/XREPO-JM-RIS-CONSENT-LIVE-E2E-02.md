# XREPO-JM-RIS-CONSENT-LIVE-E2E-02

**Status:** `B — AUTH ACCESS ACTION REQUIRED`  
**Scope:** Jobsearch ↔ RIS limited-beta application-storage and CV-storage consent  
**No new Production deployment, Main merge, Terraform apply, AWS/Cognito change or real applicant data.**

## 1. Ausgangsstand

| Komponente | Stand |
|---|---|
| Jobsearch Main / Production | `92ca1fc690adcb1c6db3b392f710b3456c324e04` |
| Jobsearch Build | `92ca1fc` |
| Jobsearch Deployments | `dpl_F9wqvv56CutqLxQpQcbMFYFLNVze`, `dpl_GARYDrYPdJJP1AFPg7UnG22ujTk6` |
| RIS Code-Main | `00363977ede1417c4992933b2639ac442a70a4b0` |
| RIS Docs-Main | `b193b716a508ac6835185b76e6a3173dc7c740c4` |
| RIS State | serial `80`, lineage `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| RIS Live Agent | `ris-dev-dev-agent`, Code `cQFmaERVhZ0cjrqcio/kzaD5ZJB71kS0sa7vB4vJbdU=` |
| RIS Post-Apply Plan | no changes, SHA-256 `30c4a15c…` |

## 2. Auth-Pfad

Jobsearch:

- Cognito/OIDC-Pool `eu-central-1_ZURSMpD2O`, Client
  `5hb3f6dj5ialg77jf4blur9g6g`, Domain
  `https://auth.mays-job-matcher.app`.
- `react-oidc-context` liefert den Access-Token; `StorageConsentLive` reicht
  ihn ausschließlich an den server-side BFF `/api/ris/consents` weiter.
- Der BFF prüft Signatur, `iss`, Client/`aud`, `token_use=access`, `sub` und
  Ablaufzeit über `api/_lib/ris/auth.mjs`.
- Danach prüft `RIS_TEST_USER_ALLOWLIST` die Kombination `iss|sub` zusätzlich
  zur RIS-Partner-Autorisierung. Empty/missing denies.

RIS:

- Die Partneroberfläche akzeptiert denselben Jobsearch-Issuer/Client, die
  RIS-Partner-Credential bleibt ausschließlich serverseitig.
- Der Grant-Schreibpfad prüft Notice- und Textzustand vor dem Speichern.

## 3. Warum keine Session verfügbar ist

Geprüfte lokale Artefakte, ohne Werte oder Tokens zu protokollieren:

| Artefakt | Befund |
|---|---|
| `/tmp/opencode/e2e_idtoken` | abgelaufen; Issuer `eu-central-1_cmJWXujnb` (RIS-Kernel-Pool), nicht der produktive Jobsearch-Pool `ZURSMpD2O` |
| `/tmp/opencode/jm-operator-session.json` | Access-/ID-Token abgelaufen; Refresh-Token liefert `invalid_grant`; keine synthetische Session |
| `/tmp/opencode/jm-e2e-user.json` | fehlt; `jm-login-pkce.mjs` kann damit keine neue Session erzeugen |
| Chrome-Profile `mays-live-e2e-profile`, `e2e-profile`, `e2e-profile2`, `actual-restore` | keine `oidc.user`-Session, keine `#dashboard-v2-title`-Ansicht |
| `jm-e2e-token.json` | fehlt |

Damit liegt primär **kein gültiger Token** vor; zusätzlich sind vorhandene
Tokens abgelaufen bzw. der alte ID-Token gehört zum falschen Pool. Es ist
**keine** XRepo-Vertrags- oder Allowlist-Abweichung nachgewiesen. Es wurde
nichts umgangen und keine Testidentität angelegt.

## 4. Vertragsstand

Bereits verifiziert, nicht erneut live ausgeführt:

- `grantAllowed` wird serverseitig aus Notice- und Textzustand berechnet.
- `specialCategoriesConsent=true` wird im POST übertragen und serverseitig
  geprüft.
- RIS `application-storage/1.0` ist `APPROVED` mit
  `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08`.
- Textversion `application-storage-consent-2026-11-07-v4` und SHA-256 stimmen.
- Reload, Withdraw/Regrant und persistierter Status sind über BFF/RIS-Tests
  abgedeckt.
- CV-Consent `cv-storage` bleibt getrennt von ApplicationV1.
- CV-404 wird nicht-destruktiv behandelt; kein Löschen/Migrieren.

Tests:

```text
Jobsearch BFF consent: 40 PASS
RIS consent focused:   27 PASS
Jobsearch full:        1952 PASS / 11 skipped
RIS full:              2629 PASS / 104 skipped / 5 bekannte Baseline-Fehler
```

## 5. Authentifizierter Live-E2E

**Nicht ausgeführt.**

Nicht behauptet:

- ApplicationV1-Grant im angemeldeten Live-Konto
- Reload-/Withdraw-/Regrant-Live-E2E
- CV-Grant, CV-Persistenz, PDF-Download oder CV-404 mit angemeldeten Daten

Es wurden keine echten Bewerbungsdaten verändert und keine Tokens/Consent-
Historien ausgegeben.

## 6. Genau eine Operator-Aktion

Einmalig in einer sichtbaren Chrome-Session mit dem bereits autorisierten
synthetischen Limited-Beta-Konto anmelden:

```bash
cd /home/dci-student/projects/mays-xrepo-orchestration/worktrees/jobsearch-xrepo-consent-final-01
npm run test:e2e:live-browser -- open
```

Im geöffneten Chrome-Fenster:

- **nur einmal** mit der vorhandenen autorisierten synthetischen Testidentität
  anmelden,
- keine Zugangsdaten oder Tokens in Chat/Terminal eingeben,
- nach sichtbarer Profilseite die Session stehen lassen.

Erwartete Wirkung: eine gültige kurzlebige Access-Session im
`/tmp/opencode/mays-live-e2e-profile`-Profil. Danach können die automatisierten
Consent-/CV-Prüfungen über CDP ausgeführt werden; eine manuelle
Button-Testaufforderung ist nicht erforderlich.

## 7. Verbleibende Gates

- gültige synthetische Session/Allowlist-Identität
- ApplicationV1 Grant/Reload/Withdraw/Regrant
- CV-Grant und synthetischer CV-PDF-Download/404
- kontrollierte Testdaten-Bereinigung

Kein Main-Merge, kein neues Deployment, kein Terraform/AWS/Cognito/CloudFront/
DNS-Eingriff.
