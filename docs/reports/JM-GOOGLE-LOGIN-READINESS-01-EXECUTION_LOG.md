# JM-GOOGLE-LOGIN-READINESS-01 — Execution Log

CHECKPOINT: 2026-10-31 21:48 UTC — Baseline / Audit gestartet (Branch: main, HEAD: c49eb2b37ab3d629eeee224084045a9659c59705)

- Current status: IN PROGRESS — read-only Readiness-Audit, noch keine Konfigurationsänderung.
- Audit date/time: 2026-10-31 21:48 UTC
- Current Git branch and HEAD: `main`, `c49eb2b37ab3d629eeee224084045a9659c59705`
- Audit scope: Bereitschaft des Google-Logins für `mays-job-matcher.app` prüfen: produktiver Jobsearch-Pool/-Client, Cognito Google IdP, Hosted UI/Custom Domain, OIDC-Codepfad, Callback/Logout, Vercel Production, Secrets/Google-Console-Abhängigkeiten und Browser-E2E-Gates. Keine Poolmigration und keine Mutation ohne separaten Auftrag.
- Completed audit sections: AI-Audit-Regeln und produktive Poolgrenze aus dem vorigen Task übernommen; Git-/Workspace-Baseline erfasst.
- Actual findings (nur verifizierte Fakten):
  - Produktive Auth-Grenze laut Abschluss des vorigen Tasks: Jobsearch-Pool `eu-central-1_ZURSMpD2O`, Client `5hb3f6dj5ialg77jf4blur9g6g`, Custom Domain `auth.mays-job-matcher.app`.
  - Der Arbeitsbaum enthält bestehende, noch nicht committete Änderungen aus dem vorigen Restore-Task sowie die fremde untracked Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md`; sie werden nicht überschrieben.
- Evidence / file references: `docs/AI_AUDITLOG.md`; `AGENTS.md`; `docs/reports/JM-RIS-AUTH-POOL-REPAIR-01-EXECUTION_LOG.md`; Git status.
- Classification: GRAY — Readiness noch nicht bewertet.
- Terraform checks actually executed and their results: Noch keine; dieser Audit ist zunächst read-only.
- Git status: siehe Baseline; dieser Execution Log ist die einzige neue Datei dieses Tasks.
- Files changed, if any: `docs/reports/JM-GOOGLE-LOGIN-READINESS-01-EXECUTION_LOG.md` neu.
- Explicit confirmation when no files were changed: Keine Source-, AWS-, Vercel- oder Google-Konfiguration geändert.
- Open questions: Existiert ein Google IdP am produktiven Pool? Ist er im produktiven App Client aktiviert? Sind Google OAuth Client/Secret und Redirect URI korrekt? Unterstützt der aktuelle UI-/OIDC-Pfad Provider-Auswahl und Callback vollständig?
- Risks: Verwechslung mit dem RIS-Kernelpool würde erneut eine produktive Auth-Grenze verletzen; Secrets dürfen nicht ausgegeben oder committet werden.
- Recommended next actions: Jobsearch-Code/-Docs und live Cognito/Vercel read-only prüfen; danach GREEN/YELLOW/RED mit konkreten Gates ausweisen.
- Current resume point: Source-/Live-Read-only-Prüfung.

CHECKPOINT: 2026-10-31 21:52 UTC — FINAL / Readiness bewertet (Branch: main, HEAD: c49eb2b37ab3d629eeee224084045a9659c59705)

- Current status: COMPLETE — Google Login ist aktuell **NOT READY**; keine Mutation durchgeführt.
- Audit date/time: 2026-10-31 21:52 UTC
- Current Git branch and HEAD: `main`, `c49eb2b37ab3d629eeee224084045a9659c59705`
- Audit scope: abgeschlossen; produktiver Jobsearch-Pool, Live-Cognito, Hosted UI, Code/Tests, Credential-Evidence und Architekturgrenzen geprüft.
- Completed audit sections:
  1. Produktive Vercel-/Pool-/Client-Grenze bestätigt.
  2. Cognito Domain, App Client, OAuth/PKCE, Callback/Logout live geprüft.
  3. Google-IdP-Liste beider Pools und Client-Provider live geprüft.
  4. Hosted-UI-Aufrufe mit und ohne `identity_provider=Google` geprüft.
  5. Jobsearch OIDC-/Login-/Callback-Code und Tests geprüft.
  6. RIS-Terraform-Google-Foundation und deren Pool-Eigentum geprüft.
  7. Secret-/Parameter-/Umgebungs-Evidence nur nach Namen geprüft, ohne Secret-Werte auszulesen.
  8. Build und gezielte Auth-Tests ausgeführt.
- Actual findings (nur verifizierte Fakten):
  - **Produktionsgrenze GREEN:** `mays-job-matcher.app` nutzt unverändert Pool `eu-central-1_ZURSMpD2O`, Client `5hb3f6dj5ialg77jf4blur9g6g` und Custom Domain `auth.mays-job-matcher.app` (`ACTIVE`).
  - **OAuth-Basis GREEN:** Public Client ohne nachgewiesenes Secret, Authorization Code Flow aktiv, Scopes `openid email profile`, Produktions-Callback `https://www.mays-job-matcher.app/auth/callback`, Logout-URL vorhanden. `oidc-client-ts`/`react-oidc-context` übernimmt PKCE und Callback.
  - **Google IdP RED:** `list-identity-providers` am produktiven Jobsearch-Pool liefert `[]`. Auch am RIS-Kernelpool existiert kein Google IdP.
  - **Client-Freigabe RED:** `SupportedIdentityProviders` des Jobsearch-Clients ist ausschließlich `["COGNITO"]`, nicht `["COGNITO", "Google"]`.
  - **Live-Verhalten RED:** Ein Authorization Request mit `identity_provider=Google` wird zur Login-Seite mit `errorMessage=Login option is not available. Please try another one` umgeleitet. Ein Google-Login kann derzeit nicht gestartet werden.
  - **Google-Console/Credentials GRAY/RED:** Keine Google-/Cognito-bezogenen Secret-Namen in der aktuellen Prozessumgebung, AWS Secrets Manager oder SSM Parameter Store (eu-central-1) gefunden. Das beweist nicht global, dass kein Google OAuth Client existiert, aber es gibt in den geprüften Systemen keinen deploybaren Credential-Nachweis. Google Consent Screen, Publishing/Test-User-Status und Authorized Redirect URI sind nicht verifiziert.
  - **Erforderliche Google Redirect URI:** Für Cognito Federation muss der Google OAuth Web Client mindestens `https://auth.mays-job-matcher.app/oauth2/idpresponse` erlauben. Diese Google-Console-Konfiguration ist OPEN.
  - **Frontend-Basis GREEN / UX YELLOW:** Der generische Login ruft `signinRedirect()` ohne Provider-Zwang auf. Nach korrekter Cognito-IdP-Aktivierung kann die Cognito Hosted UI einen Google-Button anbieten, ohne den Callback-Code umzubauen. Ein eigener sichtbarer „Mit Google anmelden“-Button bzw. `identity_provider=Google`-Pfad existiert nicht.
  - **Callback/Identität GREEN für Standard-OIDC:** `AuthCallback` verarbeitet den validierten Cognito-Flow; temporäre Identität wird sicher aus `iss + sub` gebildet, nicht aus E-Mail. Damit entsteht kein implizites E-Mail-Merge im Frontend.
  - **Account Linking YELLOW/OPEN:** Automatisches Linking nach E-Mail ist bewusst nicht implementiert. Ohne expliziten Linking-Flow kann dieselbe Person als Cognito-Passwortnutzer und Google-Federation-Nutzer zwei verschiedene `sub`-Identitäten erhalten. Das ist laut Architektur ein gewolltes Fail-Closed-Verhalten, aber produktseitig vor Freigabe zu entscheiden und zu testen.
  - **Profil/Tenant YELLOW/OPEN:** Google-Login erzeugt kein Anwendungsprofil automatisch. Attributmapping und Verhalten für `email`, `email_verified`, Namen, Gruppen und ggf. Tenant müssen am dedizierten Jobsearch-Pool verifiziert werden; `custom:tenant_id` darf nicht erfunden werden.
  - **IaC-Eigentum RED:** Die vorhandene Terraform-Google-Foundation (`identity_google_*`) konfiguriert ausschließlich den RIS-Kernelpool `ojbmoiYGM`. Sie darf **nicht** für Jobsearch aktiviert werden, weil der produktive Jobsearch-Pool dediziert `ZURSMpD2O` ist. Für Google Login fehlt ein dedizierter, pool-richtig gescopter IaC-/Ownership-Pfad.
  - **Branding YELLOW:** Managed Login verwendet Cognito-Defaultwerte; `branding-settings.json` dokumentiert nur `COGNITO`. Die Provideranzeige nach Aktivierung ist live zu prüfen.
- Evidence / file references:
  - Live AWS: `list-identity-providers`, `describe-user-pool-client`, `describe-user-pool-domain`, `describe-managed-login-branding-by-client` (Profil `mayaws`, Account `240571105849`, Region `eu-central-1`).
  - Live HTTP: `/oauth2/authorize` default und mit `identity_provider=Google`.
  - Jobsearch: `src/lib/oidcConfig.ts`, `src/lib/authFlow.ts`, `src/components/LoginForm.tsx`, `src/components/AuthCallback.tsx`, `src/lib/authIdentity.ts`, `branding-settings.json`.
  - RIS: `terraform/modules/cognito/main.tf`, `terraform/modules/cognito/variables.tf`, `terraform/variables.tf`, `docs/architecture/SYSTEM-ARCHITECTURE.md`.
- Classification: **RED — NOT READY**. Die sichere OIDC-Basis ist vorhanden, aber der Google IdP, Client-Freigabe, Credentials/Google-Console-Konfiguration, dediziertes IaC-Eigentum und Live-E2E fehlen.
- Terraform checks actually executed and their results: Kein Terraform-Plan/Apply erforderlich oder ausgeführt; Audit war read-only. Bestehende Google-Terraform-Foundation statisch geprüft und als falscher Pool-Scope für Jobsearch bewertet.
- Git status: Dieser Report ist die einzige neue Datei dieses Tasks. Bestehende Änderungen aus dem vorherigen Restore-Task und fremde untracked Dateien wurden nicht verändert. Im Jobsearch-Repo waren bereits fremde untracked Dateien vorhanden; keine davon wurde geändert.
- Files changed, if any: nur `docs/reports/JM-GOOGLE-LOGIN-READINESS-01-EXECUTION_LOG.md` (plus späterer Indexeintrag in `docs/AI_AUDITLOG.md`).
- Explicit confirmation when no files were changed: Keine AWS-, Cognito-, Google-, Vercel-, Terraform- oder Jobsearch-Code-Konfiguration geändert.
- Open questions:
  1. Existiert bereits ein Google Cloud OAuth Web Client außerhalb der geprüften Stores, und wer ist Owner?
  2. Soll Google nur über die Hosted UI angeboten werden oder zusätzlich als direkter App-Button?
  3. Wie soll explizites Account Linking zwischen bestehendem Passwortkonto und Google-Konto produktseitig erfolgen?
  4. Welche Tenant-/Profilinitialisierung gilt für neue Google-Federation-Identitäten?
- Risks: Falsches Aktivieren der RIS-Variablen würde Google am Kernelpool statt am produktiven Jobsearch-Pool konfigurieren. Auto-Linking per E-Mail wäre Account-Takeover-/Merge-Risiko und bleibt verboten. Secret-Werte dürfen nicht in Git, Shell-Logs oder Reports gelangen.
- Recommended next actions (Reihenfolge):
  1. Explizite Produkt-/Security-Freigabe für Google Login, Linking-Verhalten und dedizierten Pool bestätigen.
  2. Google OAuth Web Client/Consent Screen mit Redirect `https://auth.mays-job-matcher.app/oauth2/idpresponse` und kontrolliertem Testkonto bereitstellen; Secret in freigegebenem Secret Store halten.
  3. Dedizierten IaC-Pfad für Pool `ZURSMpD2O` schaffen/importieren; nie die RIS-Kernel-Variablen dafür missbrauchen.
  4. Google IdP mit Scopes `openid email profile` und geprüftem Mapping anlegen; App Client atomar auf `["COGNITO", "Google"]` erweitern, ohne Callback/Logout/Flow zu verlieren.
  5. Hosted-UI-Providerdarstellung testen; bei gewünschtem Direktbutton explizite UX + Tests implementieren.
  6. E2E mit Testkonto: Google → Cognito → `/auth/callback` → validiertes Cognito JWT (`iss`, `aud/client_id`, `sub`, `email`, `email_verified`) → Profilverhalten; Logout/Re-Login und Fehlerpfade prüfen.
  7. Erst nach E2E und Linking-/Profilentscheidung Produktionsfreigabe auf GREEN setzen.
- Current resume point: Audit abgeschlossen; keine Implementierung autorisiert oder durchgeführt.

## Test results

- Gezielte Auth-Suite: **13 passed** (`oidcConfig`, `authFlow`, `LoginForm`, `AuthIntegration`).
- `npm run build`: PASS (`tsc -b && vite build`), nur bestehende Chunk-Size-Warnung.
- Live Google-Startprobe: erwartungsgemäß FAIL/NOT AVAILABLE (Konfigurationsbefund, kein Testdefekt).
