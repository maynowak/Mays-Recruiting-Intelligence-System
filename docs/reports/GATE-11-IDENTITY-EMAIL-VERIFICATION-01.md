# GATE-11 — Identity Email Verification & Installer Mail Configuration

STATUS: YELLOW (Versandversuch belegt; Inbox-Eingabe NOT PROVEN — kein Postfach verfügbar)

- Date/Time: 2026-10-02 UTC
- Branch + HEAD (RIS): main, + Gate-11-Änderungen (s. Git)
- MO-Stand: 0 Änderungen. Gates 5–10 unangetastet (nur Installer/TF-Config + Docs).
- Scope: Installer-Mail-Config + Cognito-Verifikation + E2E soweit ohne Inbox möglich. Kein SMTP/Token-Eigenbau, keine Domain-Erfinderung, keine Jobsuche.
- Sections: Bestand, Contract, E2E, Security, Regression, Docs unten
- Findings: --var-Mechanismus (MO-Muster) + Apply-Weitergabe; Template + Versand live; Delivery-Attempt belegt; Re-Run konvergent (No changes)
- Evidence: Unit-Tests (2 neu), API-Responses, Cognito-CLI (CodeDeliveryDetails), TF-State/Pläne, Suite 329
- Classification: YELLOW (E2E ohne Inbox unvollständig — ehrlich, kein GREEN)
- Terraform/AWS Checks: validate GREEN; gezielt Pool-Update (0/1/0); Re-Plan leer; 0 destroys
- Git Status (RIS): Commits pro Bereich (s. Git); mays-jobs-matcher unberührt (andere Repo-Historie)
- Files Changed: `installer/ris.py` (--var/parse/forward), `terraform_runner.py` (apply), `tests/test_ris_installer.py` (+2), TF (4 Dateien: Vars + Template), Docs (Architektur/API/Status), Reports
- Open Questions: Inbox-Nachweis (braucht lesbares Postfach); SES-Modus (keine Domain); Full-Plan-lambda.zip (bekannt)
- Risks: keine neuen (keine Secrets — Betreff/Text öffentlich; Temp-User gelöscht)
- Next Actions: Commits → Folgetor (Inbox-Test bei Postfach-Verfügbarkeit)
- Resume Point: nach Commit HARD STOP

## 1. Bestand / Installer

Config-Wege: nur CLI-Flags (kein --var, kein Manifest; Run-Artefakte ignoriert); Reconciliation = TF-State nativ; Secrets: keine Ablage nötig (keine Secrets im Scope). App-Identity: Pool/Client/Tenant-Claim (keine Domain-Erkennung — nie so gebaut). Pool-Stand: keine AutoVerify, COGNITO_DEFAULT, Confirmation blockiert (Gate 10).

## 2. Application Identity

Registrierungsweg = RIS-Pool + Client (Kontext), nicht E-Mail-Domain. Mechanismus vorhanden (preferred_username, Tenant-Claim, Gruppen); nichts Neues gebaut.

## 3. Cognito Email Verification (live)

`auto_verified_attributes=["email"]`, Template CONFIRM_WITH_CODE, Betreff/Text gemäss Vorgabe (Platzhalter {####} live verifiziert). Pool: `AutoVerified=[email]` live.

## 4. Sender Configuration

Modus A (COGNITO_DEFAULT): keine Domain, keine Adresse zu erfinden — umgesetzt. Modus B (SES): keine verifizierte Identität → `sender_mode`-Validierung weist alles ausser `cognito_default` ab (fail-closed, kein neues Infra). Installierbar in beliebigem Account (keine Account-Literale).

## 5. Configuration Contract

TF-Vars `identity_email_verification_enabled` (bool, default false = Vorverhalten), `identity_email_subject/message` (Vorgabetexte), `identity_sender_mode` (default cognito_default). Installer: `--var KEY=VALUE` (MO-Muster) → plan+apply (Apply-Weitergabe neu, vorher Defaults-only — Befund). Identität schützt: project_name/environment nie per --var überschreibbar (Unit-belegt).

## 6. Re-Run

TF-State trägt Config: Zweit-Plan nach Apply = `No changes` (belegt). Config-Wechsel (z. B. Betreff) → neuer Plan → Apply konvergiert. Installer: `install --yes` bootstrapt + plant + applied mit Vars (apply-Pfad jetzt var-treu).

## 7. Echter E2E Flow

1. SignUp synthetisch (@example.com, kein Postfach) → 2. Delivery-Attempt BELEGT (`CodeDeliveryDetails: EMAIL an g***@e***`) → 3. Code-Eingabe NOT PROVEN (kein Postfach — ehrlich) → 4.–9. per Admin-Confirm (Test-Ersatz): CONFIRMED, Login-Block vorher belegt, Login→JWT→/me 200→Provision 201→GET 200 → 10. Cleanup (User + Profil gelöscht, Pool leer, Tabelle 0, Secrets geschreddert).

## 8. Security

Kein Code persistiert (Cognito-verwaltet); kein Passwort in RIS; keine Tokens/Adress-Codes in Logs/Reports (nur maskierte Destination); Pool leer nach Test.

## 9. Regression

Suite **329 passed** (327 + 2 neu), 4 pre-existing deselected + 1 Collection (klassifiziert). Identitäts-Kette (SignUp/Confirm/Login/JWT/me/Provision) via obigem E2E intakt.

## 10. Documentation

SYSTEM-ARCHITECTURE (Identity-Absatz aktualisiert), API-STANDARD (Registrierungs-Contract aktualisiert), PROJECT_STATUS (+Gates 10/11), diese Reports. Keine Domain-Erfinderung.

## 14. Abschluss

| Bereich | Ergebnis |
|---|---|
| Installer Configuration | GREEN |
| Application Identity | GREEN |
| Cognito Email Verification | GREEN (konfiguriert) |
| Sender Configuration | GREEN (Modus A; B fail-closed) |
| Configuration Re-Run | GREEN (No-changes belegt) |
| Registration | GREEN |
| Confirmation | YELLOW (Versuch belegt, Eingabe NOT PROVEN) |
| Login / JWT | GREEN |
| Profile | GREEN |
| Security | GREEN |
| Regression Tests | GREEN (329) |
| Live E2E | YELLOW (ohne Inbox unvollständig) |
| Documentation / Git | GREEN |

**YELLOW** (Gesamt — Versand konfiguriert + Versuch belegt; Inbox-Nachweis offen). Reports: `GATE-11-IDENTITY-EMAIL-VERIFICATION-01.md` (+ Log). Commits: s. Git. Offen: lesbares Test-Postfach, SES-Modus, lambda.zip-Lücke. Nächstes Gate: Inbox-Test oder Domain-Vertiefung.

**DANN HARD STOP.**
