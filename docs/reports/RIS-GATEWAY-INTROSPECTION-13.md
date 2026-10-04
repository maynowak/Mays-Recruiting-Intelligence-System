# RIS-GATEWAY-INTROSPECTION-13 — Gateway-Verdrahtung der Introspection (P13)

STATUS: YELLOW (TF + Handler vorbereitet, validiert, geplant — KEIN Apply; Live-Aktivierung offen)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, b86e98a (+ uncommitted: TF-Route + Dispatch + 3 Tests + diese Reports)
- Scope (festgelegt per Rückfrage VOR Start): TF NUR Gateway-Routen (keine Tabellen/IAM/ Lambdas/TF-Configs); KEIN Apply ohne separaten Entscheid (Plan zeigen, dann fragen); Pfade Human + X-Api-Profile (KEIN Machine-Pfad, KEIN neuer Authorizer).
- Basis: P12 (`_handle_introspection` + `_build_introspection_sources`, ohne Dispatch/Route) + GW-Bestand (HTTP API, $default auto-deploy, JWT-Authorizer, Proxy-Integration, `/*/*`-Invoke-Recht).
- Classification: GREEN (Code/TF/Tests) / YELLOW (Live: Route existiert weder live noch im State; Aktivierung = Folge-Entscheid).
- AWS: NUR Reads (sts, get-apis/routes, init, plan) + State-Lock waehrend Plan. KEIN Apply, KEINE Mutation (verifiziert).
- Git: nur P13-Dateien (s. Commit).
- Next: Apply-Entscheid (Optionen §5) -> HARD STOP.

## 1. Bestand (gelesen, nicht geaendert — ausser P13-Diff)

- GW-Modul (`terraform/modules/api/main.tf`): HTTP API + `$default`-Stage (auto_deploy) + JWT-Authorizer (Audience/Issuer) + EINE Proxy-Integration (Payload 2.0) + Einzel-Routen-Ressourcen (Muster) + Lambda-Permission `execution_arn/*/*` (deckt neue Routen OHNE Aenderung ab).
- Handler-Dispatch (`_handle_api_event`): Methode+Pfad-Verzweigung; NEU: `GET /v1/introspection` -> `_handle_introspection` (P12-Funktion, inkl. X-Api-Profile-Header-Read + 401/403/404/503-Semantik).
- Live-API `aboqolpm0f` (Read): orders×4, documents×3, me/profile×3, me, health. NICHT live: /platform, /agents, /jobsearches*, /api/agents*, /v1/introspection.

## 2. P13-Diff (minimal, konventionsgetreu)

- TF: `aws_apigatewayv2_route.introspection` (GET /v1/introspection, JWT-Authorizer, bestehende Proxy-Integration; Kommentar mit Scope-Grenze). KEINE neue Integration/Authorizer/Permission/Stage.
- Handler: 1 Dispatch-Zweig (3 Zeilen + Kommentar). KEINE Logik-Aenderung an P12-Funktion.
- Tests: +3 Dispatch-Tests (Delegation inkl. Header-Weitergabe; 401 ohne JWT; 503 ohne Sources).

## 3. Validierung

- `terraform validate`: Success (nur bekannte deprecated-range_key-Warnings).
- `terraform fmt -check modules/api/main.tf`: clean (Exit 0).
- Suite: 596 passed (593 + 3), 8 skipped; 15 failed + 1 ERROR Hash-IDENTISCH zur P12-Baseline (pre-existing).

## 4. Plan-Ergebnis (mayaws, dev-Workspace mays-ris, Backend S3+Lock, KEIN Apply)

- Voll-Plan: **9 to add, 2 to change, 0 to destroy** (Planfile /tmp/p13.tfplan).
- Davon P13-eigen: GENAU 1 (`module.api...route.introspection`).
- Rest = PRE-EXISTING Drift + Plan-Artefakte (NICHT P13, NICHT anwenden ohne separates Gate):
  - 6 Routen-Adds (agents/me/platform/profile×3): existieren LIVE (per CLI in Gates 10/12 erstellt, nie in State importiert) — Apply wuerde auf RouteExists-Konflikte laufen.
  - SQS-Mapping-Add + IAM-Policy-Add: live-existent, state-fremd (gleiches Muster).
  - Pool-Update (auto_verified_attributes-Entfernung): VAR-ARTEFAKT (Plan ohne Installer-`--var`-Flags; live per Gate-11-Vars applied) — KEIN echter Drift.
  - Lambda-Update (source_code_hash-Differenz + filename-Pfad-Artefakt): ECHTER Code-Drift (Deployments vs. deterministischer Rebuild-Stand) — ausserhalb P13-Scope.
- Targeted-Plan (`-target=introspection`): 1 Add + dieselben 2 Changes (TF wertet Abhaengigkeiten/Refresh mit aus) — auch gezielt NICHT ohne Re-Plan mit Vars + Lambda-Entscheid anwenden.

## 5. Apply-Optionen (Entscheid OFFEN — KEIN Apply erfolgt)

- A) Voll-Apply: ABGELEHNT (Route-Konflikte + Pool/Lambda-Seiteneffekte ausserhalb Scope).
- B) Gezielt (NUR Introspection-Route, nach Re-Plan MIT Installer-Vars + Lambda-Deploy-Entscheid, danach Smoke-Test): EMPFOHLENER Pfad, braucht EXPLIZITE Freigabe (Lambda-Code-Deploy ist Voraussetzung — sonst antwortet die Route mit 404 des ALTEN Handler-Stands; auto_deploy wuerde sofort scharf schalten).
- C) Kein Apply (vorbereitet liegen lassen): gueltiger Zwischenstand (TF + Handler committet, validiert, geplant).
- Naechstes Gate bei B: koordinierter Deployment-Lauf (Lambda-Deploy + gezielter Route-Apply + JWT-Smoke inkl. X-Api-Profile) — NICHT in P13.

**HARD STOP (kein Apply ohne Entscheid).**
