# RIS-CONSENT-PILOT-APPLY-07

**Status:** `PILOT LIVE PARTIAL — CV DELETE/CLEANUP BLOCKED`
**Apply:** exakt der freigegebene Plan `e62370c0…` wurde angewendet.
**No general production approval, no Main-Merge, no Cognito/CloudFront/DNS
change.**

## 1. Apply

```text
Plan:        /tmp/opencode/ris-consent-pilot-06.tfplan
SHA-256:     e62370c0536af74b630a810585d95b12fba637a79ba428a13447b01ec07d1b68
State vor:   serial 80 / lineage 9cec61e5-c036-1ad5-6ae4-8b48a50122a4
Ergebnis:    1 added / 5 changed / 0 destroyed
State nach:  serial 82 / lineage unverändert
```

Die Erasure-Route wurde angelegt:

```text
POST /v1/partner/me/erasure
API: c7e9pdwe78 / Route: tbxgu4e / Authorizer: e6inno
```

Ungeschützter Aufruf:

```text
HTTP 401 Unauthorized
```

Live-Environment des Agenten:

```text
APPLICATION_CONSENT_ENFORCED            = true
CV_STORAGE_CONSENT_ENFORCED             = true
SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED = true
CONSENT_NOTICE_STATE_ENFORCED           = true
CONSENT_PILOT_ALLOWLIST                 = bestehende 2 Einträge
```

Post-Apply-Plan:

```text
No changes. Your infrastructure matches the configuration.
Plan: /tmp/opencode/ris-consent-pilot-06-post.tfplan
SHA-256: 6b714e052f32bbed616d809868ba2363b719c705e6429e7e2226ae4720b46e3d
```

## 2. XRepo-Live-E2E

Autorisierte, bereits vorhandene Pilot-Session; keine neue Identität. Es
wurden keine Tokens oder Allowlist-Werte protokolliert.

Erfolgreich:

- ApplicationV1: Withdraw → Regrant → Reload
  - Status `GRANTED`
  - `specialCategoriesConsent=true`
  - 9 Kategorien
  - Text `application-storage-consent-2026-11-07-v4`
  - Hash vorhanden
- CV-Consent: Withdraw → Regrant → Reload
  - Status `GRANTED`
  - `specialCategoriesConsent=true`
  - Text `cv-storage-consent-2026-11-08-v1`
- Search-Profile-Consent: Withdraw → Regrant → Reload
  - Status `GRANTED`
  - Text `search-profile-storage-consent-2026-11-08-v2`
- CV Create: `201`
- Upload-Ticket: `200`
- S3 Upload: `200`
- Complete: `200`, Status `ready`
- List/Reload: CV gefunden
- PDF-Download: `200`, 13.569 Bytes, `%PDF`

## 3. Konkreter Fehler

CV Delete schlägt fehl:

```text
DELETE /api/ris/cvs?id=<synthetic-cv>
HTTP 500
code=internal_error
RIS-Log: cv delete reservation failed
```

Der synthetische CV ist deshalb **noch nicht bereinigt**.

Ursache ist bestätigt:

```text
IAM-Aktion: dynamodb:ConditionCheckItem
Rolle:      ris-dev-dev-agent
Ressource:  ris-dev-dev-partner-profiles
Ergebnis:   implicitDeny
```

Die Aktion fehlt in `ris-dev-dev-lambda-dynamodb-partner-profiles`; der
CV-Delete-Reservation-Pfad benötigt sie für `TransactWriteItems`. Es wurde
keine echte Benutzerdatei angelegt; der verbleibende Datensatz ist synthetisch.

## 4. Vorbereiteter IAM-Fix

Minimaler Fix im Feature-Branch:

```text
Branch: feature/ris-erasure-recovery-02
Commit: 773d212
```

Der neue Plan ist noch **nicht angewendet**:

```text
/tmp/opencode/ris-consent-pilot-07-iam.tfplan
SHA-256: c30d9c1928e60332be040d2a2453b5b357c9c14e699404238dddc623077be4e8
State: serial 82
0 Add / 1 Change / 0 Destroy / 0 Replace
```

Einzige Änderung: `dynamodb:ConditionCheckItem` in der bestehenden
Partner-Profile-IAM-Policy. Keine Ressourcen-, Route-, Environment- oder
State-Änderung.

## 5. Nächster Schritt

Erforderlich ist eine neue ausdrückliche Freigabe:

```text
GO APPLY c30d9c1928e60332be040d2a2453b5b357c9c14e699404238dddc623077be4e8
```

Nach diesem Apply:

1. CV-Delete erneut ausführen und den synthetischen CV entfernen.
2. List/404 und Post-Apply-Plan prüfen.
3. XRepo-E2E-Abschlussstatus dokumentieren.

Bis dahin bleibt der Status **PILOT LIVE PARTIAL**, nicht `PILOT LIVE VERIFIED`.

## 6. Grenzen

- Kein weiterer Apply in dieser Runde.
- Keine Cognito-/CloudFront-/DNS-Änderung.
- Keine allgemeine Benutzerfreigabe.
- Kein Main-Merge.
- Keine echten Benutzerdaten verändert.
