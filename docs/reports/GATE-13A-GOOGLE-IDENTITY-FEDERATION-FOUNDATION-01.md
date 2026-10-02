# GATE-13A — Google Identity Federation Foundation (optional)

STATUS: YELLOW (Foundation konfiguriert + Versuchspfade belegt; Live-Google-Login NOT PROVEN — kein Test-Account)

- Date/Time: 2026-10-02 UTC
- Branch + HEAD (RIS): main + Gate-13A-Commits (s. Git)
- MO-Stand: 0 Änderungen. Gates 5–12 unangetastet (nur TF-Config + Docs + Guards).
- Scope: optionale Federations-Foundation (TF + Vertrag + Guards). KEIN React-Button, KEIN Linking, KEIN Auto-Merge, KEINE Tokens in DDB, KEINE Secrets in Git, KEIN ATS/Domain-Ausbau.
- Sections: Bestand, Umsetzung, E2E, Security, Tests, Docs unten
- Findings: IdP-Ressource + Mapping + Client-Anbindung optional verdrahtet (Default AUS = No-Change belegt); Password-Login intakt; kein IdP live
- Evidence: 4 Guard-Tests, TF-Pläne (No-Change + Create-Vorschau mit Fake-ID, NICHT applied), Cognito-Reads, Suite 338
- Classification: YELLOW (Live-Google-Login ohne Test-Account nicht beweisbar — ehrlich)
- Terraform/AWS Checks: validate GREEN; Live-Plan No-Changes (Optionalität); Fake-ID-Plan zeigt Create (nicht applied); 0 destroys
- Git Status (RIS): Commits pro Bereich (s. Git); mays-jobs-matcher unberührt
- Files Changed: TF (cognito main/vars, root vars/main), `tests/test_google_foundation.py` (neu), Docs (Architektur), Reports
- Open Questions: Test-Account + Redirect-URI (Frontend-Entscheid) für Gate 13B; SES-Modus (keine Domain); lambda.zip-Lücke
- Risks: keine neuen (keine Credentials erzeugt/gespeichert; Temp-User gelöscht)
- Next Actions: Commits → KEIN 13B (HARD STOP)
- Resume Point: nach Commit HARD STOP

## Bestand

Client: nur USER_PASSWORD_AUTH+Refresh, KEIN OAuth (Providers/Flows/Scopes/Callbacks null), KEINE IdPs. TF-Modul ohne OAuth-Felder (konsistent, kein Drift). Password-Login Hauptweg (Gate 10/11/12 + Re-Probe Gate 13A: Bearer OK).

## Umsetzung (Foundation)

- `aws_cognito_identity_provider.google` (count = client_id != "" ? 1 : 0; Typ Google; Details client_id/secret + `authorize_scopes="openid email profile"`; Mapping email/given_name/family_name/name — username-Mapping bewusst NICHT (unverifiziert)).
- Client OAuth-Felder NULL wenn deaktiviert (kein Diff), sonst Code-Flow + Scopes + Redirect-Listen (leer = Apply-Fehler, fail-closed).
- Root-Vars `identity_google_*` (Defaults = aus; secret `sensitive`); Installer braucht KEINE neuen Flags (--var-Mechanismus Gate 11 reicht; dokumentiert).
- Secrets-Regel: nur per --var beim Apply, nie Git/Logs/Reports; State-Backend verschlüsselt (Bestand).

## Linking-Vertrag (nur Definition, kein Code)

- KEIN automatisches Linking (weder E-Mail noch Name noch Attribut) — Guard-Test scannt Repo (0 Treffer).
- Später NUR: authentifizierter RIS-User steuert explizit OAuth-Abschluss; gleiche E-Mail ≠ Beweis.
- Identity ≠ Profil bleibt (Google-User ohne Profil → 404; kein Auto-Provision).
- Google liefert höchstens initiale Profilwerte, nie Wahrheit; keine Tokens in DDB (Guard-Test auf Profil-Schema).

## E2E / Live

- Plan Defaults + Live-Werte: `No changes` (Optionalität belegt).
- Fake-ID-Plan: IdP-Create + Client-Update VORGESCHLAGEN, NICHT applied (kein Dummy-Deploy).
- Live: 0 IdPs; Client-Provider unverändert; Password-Login (Temp-User, danach gelöscht) OK.
- Google-Login E2E: NOT PROVEN (kein Test-Account, keine Redirect-URI) → YELLOW-Decke.
- Tenant: keine Änderung (JWT/Authorizer/Guards intakt); keine Google-Tenant-Bestimmung möglich (kein Feld, kein Codepfad).

## Security

Siehe Guards (4 Tests) + Live-Prüfung: kein Secret-Literal, kein Link-Code, keine Token-Felder, Pool/User-Stand unverändert, Temp-Artefakte vernichtet.

## Tests

Neu 4 (Guards). Suite **338 passed** (334 + 4), 4 pre-existing + 1 Collection klassifiziert. TF validate GREEN (beide Wege).

## Docs

SYSTEM-ARCHITECTURE (Google-Absatz), diese Reports. Keine alten Reports angerührt.

## Checkpoint

| Bereich | Ergebnis |
|---|---|
| Cognito Foundation | GREEN |
| Google Federation | YELLOW (konfiguriert, nicht live) |
| OAuth Configuration | GREEN (Code-Flow, Scopes, Redirect-Vars) |
| Attribute Mapping | GREEN |
| Optionality | GREEN (No-Change belegt) |
| Identity Linking Foundation | GREEN (Vertrag, kein Code) |
| Profile Boundary | GREEN |
| Tenant Isolation | GREEN |
| IAM/Security | GREEN |
| Tests | GREEN (4 + 338) |
| AWS E2E | YELLOW (kein Test-Account) |
| Installer/Terraform | GREEN |
| Documentation | GREEN |
| Git | GREEN (folgt) |

**YELLOW** (Gesamt). Explizit: "Automatic account linking by email is not implemented." / "Google account linking is prepared but not activated in Gate 13A." Reports: `GATE-13A-GOOGLE-IDENTITY-FEDERATION-FOUNDATION-01.md` (+ Log). Commits: s. Git. Offen: Test-Account/Redirect-URI, SES, lambda.zip. KEIN 13B.

**DANN HARD STOP.**
