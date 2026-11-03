# RIS-DEV-UPGRADE-DEC01 — Cursor Secret Provisioning

- **Datum:** 2026-11-03
- **Modus:** autorisierte AWS-Schreiboperation (nur Secrets Manager) + Plan-only
- **Ziel:** `ris-dev` · `mayaws` · `240571105849` · `eu-central-1`
- **Ergebnis:** **RG-07 PARTIAL** — Secret existiert und ist verdrahtet; IAM-Grant und Lambda-Nutzung sind noch nicht angewendet.

---

## 1. Freigabenachweis

| Feld | Inhalt |
|---|---|
| Freigabe erteilt durch | Benutzer (Auftragsgeber) |
| Zeitpunkt | 2026-11-03, vor der Schreiboperation |
| Umfang | genau ein Secret, Account `240571105849`, `eu-central-1` |
| Ausgeschlossen | Cognito, CloudFront, DNS, ACM, Orders, Datenbanken, Lambda, PITR, Rotation |

Ohne diese Freigabe wurde keine Schreiboperation ausgeführt.

---

## 2. Baseline

| Prüfung | Wert |
|---|---|
| Branch / HEAD bei Beginn | `main` / `30fa171` ✅ |
| Working Tree | sauber bis auf geschützte fremde Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` |
| STS | `240571105849`, `arn:aws:iam::240571105849:user/Mayaws` ✅ |
| Vorzustand Secret | nicht vorhanden (`ResourceNotFoundException`) |
| Namenskollision | keine (nur `github-token-xxxxx`) |
| State | serial 36, Version `3tey8lIH…` (unverändert) |

---

## 3. Secret

| Feld | Wert |
|---|---|
| Name | `ris-dev/applications/cursor-hmac` |
| ARN | `arn:aws:secretsmanager:eu-central-1:240571105849:secret:ris-dev/applications/cursor-hmac-cuHjQ8` |
| Typ | `SecretString` |
| Länge | 64 Zeichen (URL-safe Base64, ~48 Byte Entropie) |
| Whitespace | keiner |
| KMS | AWS-managed (`KmsKeyId = null`) → keine zusätzlichen `kms`-Rechte |
| Rotation | nicht aktiviert (`RotationEnabled = null`) |
| Tags | `Project=ris-dev`, `Purpose=applications-cursor-hmac` |
| Erstellt | 2026-11-03 21:45:04 +01:00 |

**Der Wert wurde nie ausgegeben, nie in Argumente, Dateien, Logs oder Git geschrieben.** Erzeugung und Schreiben erfolgten im selben Prozess (`secrets.token_urlsafe(48)` → `create_secret`).

---

## 4. Durchgeführte AWS-Aktionen

| Aktion | Anzahl | Ziel |
|---|---:|---|
| `secretsmanager:CreateSecret` | 1 | `ris-dev/applications/cursor-hmac` |
| `secretsmanager:DescribeSecret` | 1 | Metadaten |
| `secretsmanager:GetSecretValue` | 1 | Längen-/Formatprüfung, lokal |

Keine weitere AWS-Ressource verändert. Keine Rotation, keine Policy, kein Lambda-Update.

---

## 5. Verifikation

| Prüfung | Ergebnis |
|---|---|
| Secret im richtigen Account/Region | ✅ |
| ARN stimmt mit Konfiguration überein | ✅ |
| Format entspricht Runtime-Vertrag (String → HMAC-Key) | ✅ 64 Zeichen, keine Whitespaces |
| Wert nicht offengelegt | ✅ |
| Lokaler Cursor-Roundtrip über ARN-Pfad | ✅ `issue → resolve` identisch, Token 255 Zeichen |
| Manipulierter Cursor | ✅ `ValueError` |
| Fremder Tenant | ✅ `ValueError` |
| Fremder User | ✅ `ValueError` |
| Autorisierter Zugriff eng begrenzt | ⚠️ lokal mit `mayaws` (Admin) getestet; Lambda-Rolle erhält Grant erst mit Apply |
| Unberechtigte Zugriffe verweigert | ⚠️ nicht mit fremder Rolle getestet (auftragsgemäß keine Fremdrolle verwendet); Containment über Policy-Scope dokumentiert |
| Runtime-Test in Lambda | ❌ **BLOCKED** bis Deployment |

---

## 6. IAM-Bewertung

Geplante Policy (`module.lambda.aws_iam_role_policy.lambda_cursor_secret[0]`):

- Rolle: ausschließlich `ris-dev-dev-agent`-Execution-Role
- Aktion: ausschließlich `secretsmanager:GetSecretValue`
- Ressource: ausschließlich der obige ARN
- Kein Wildcard, kein `kms:Decrypt` nötig (AWS-managed Key)

Bis zum Apply hat die Lambda-Rolle **keinen** Zugriff → Pagination bleibt fail-closed (503). Das ist beabsichtigt.

---

## 7. Terraform-Integration

| Feld | Wert |
|---|---|
| Konfigurationsreferenz | `applications_cursor_secret_arn` (Overlay `installer/project-configs/ris-dev.json`) |
| Env-Variable | `RIS_CURSOR_SECRET_ARN` (nur ARN) |
| Klartext im State | **nein** |
| Plan | `/tmp/opencode/ris-dev-dec01.tfplan` |
| Plan-JSON | `/tmp/opencode/ris-dev-dec01-plan.json` |
| **SHA-256** | **`f779d778a104d6b5bf54a6fab5b4a884daef409cd20262552718e5f54577668b`** |
| State nach Plan | serial 36, unverändert |

| Aktion | Anzahl |
|---|---:|
| CREATE | **49** (48 + `lambda_cursor_secret[0]`) |
| UPDATE | 3 |
| DELETE | 0 |
| REPLACE | 0 |
| MOVE | 54 |
| Drift | 1 (berechnetes Cognito-`domain`) |

Erwartete zusätzliche Berechtigung wurde einzeln bestätigt: **genau eine** neue IAM-Policy, keine weiteren Ressourcen.

Overlay-Guard angepasst: `_arn`-Referenzen sind erlaubt (Adresse, kein Geheimwert); werttragende Schlüssel wie `cursor_secret_value` bleiben verboten. 60 Tests PASS.

---

## 8. Rotation und Cache

- Neue Version → `AWSCURRENT`; Cache pro Prozess und ARN ohne TTL.
- Rotation wirkt beim nächsten Cold Start; bestehende Cursor werden ungültig und Clients beginnen die Liste neu (fail-safe, kein Datenverlust).
- Unterbrechungsfreie Rotation über zweiten ARN ist bewusst **nicht** implementiert (DEC-02, PROPOSED).

---

## 9. Offene Tests

| Test | Status |
|---|---|
| Lambda-Rolle darf `GetSecretValue` | BLOCKED bis Apply |
| Lambda erhält `RIS_CURSOR_SECRET_ARN` | BLOCKED bis Apply |
| End-to-End-Pagination im Deployment | BLOCKED bis Apply |
| Negativtest mit unberechtigter Rolle | nicht durchgeführt (keine Fremdrolle) |

---

## 10. Gate-Status

**RG-07: PARTIAL.**

Erfüllt: Secret existiert, ARN korrekt, Format gültig, Wert geheim, Konfiguration vorbereitet, Plan enthält genau die erwartete IAM-Policy.

Nicht erfüllt: IAM-Grant ist nicht angewendet, Lambda kennt den ARN noch nicht, Runtime-Verifikation fehlt.

**PASS** erst nach Apply der IAM-Policy und erfolgreichem Runtime-Test.

---

## 11. Nächste Schritte (nicht autorisiert)

1. Apply des freigegebenen Plans (separater Auftrag) → Policy + Env aktiv.
2. Runtime-Test: Cursor-Liste mit Pagination, 401/403-Negativtest.
3. Danach RG-07 auf PASS setzen.
4. DEC-02 (Rotation) entscheiden.

**STOP nach DEC-01. Kein Apply, keine weiteren AWS-Änderungen.**
