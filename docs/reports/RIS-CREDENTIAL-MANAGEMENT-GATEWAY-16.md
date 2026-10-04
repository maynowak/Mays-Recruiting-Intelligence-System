# RIS-CREDENTIAL-MANAGEMENT-GATEWAY-16 — Gateway-Verdrahtung Credential Management (P16)

STATUS: YELLOW (TF vorbereitet, validiert, geplant — KEIN Apply; Live-Aktivierung offen)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, e0b95ff (+ uncommitted: TF-Routen + diese Reports)
- Scope: AUSSCHLIESSLICH Gateway-Verdrahtung (7 Routen, Human JWT, bestehender Authorizer + Integration, Terraform only). KEIN neuer Authorizer/Lambda-Authorizer/M2M/OAuth/mTLS, KEINE Cognito-/CRUD-/Offer-/Entitlement-/Tabellen-/IAM-/Lambda-/Worker-Aenderung, KEIN $default-/ANY-/Greedy-Ersatz.
- Basis: P15-Commit e0b95ff (verifiziert) + P13-Gateway-Muster f010c5d + GW-Bestand.
- Classification: GREEN (TF/Tests) / YELLOW (Live: Routen weder live noch im State).
- AWS: NUR Reads (sts, init, plan) + State-Lock waehrend Plan. KEIN Apply, KEINE Mutation (verifiziert).
- Git: nur P16-Dateien (s. Commit).
- Next: Apply-Entscheid (Optionen §5) -> HARD STOP.

## 1. Ausgangszustand (gelesen, nicht geaendert — ausser P16-Diff)

- HEAD = e0b95ff (P15) verifiziert; tracked tree clean.
- GW-Modul: HTTP API + `$default` (auto_deploy) + JWT-Authorizer (`9ghezn`, Audience/Issuer) + EINE Proxy-Integration + Einzel-Routen-Muster + Permission `/*/*`.
- Handler P15-Dispatch + P12-Introspection-Route (P13, NOCH NICHT applied — korrekt weiter im Plan).

## 2. P16-Routen (7, minimal, konventionsgetreu)

POST/GET `/v1/apiprofiles/{apiProfileId}/credentials` + GET `/{credentialId}` + POST `.../{credentialId}/{rotate,disable,enable,revoke}` — je eigene Ressource (explizite Pfade mit {Parametern}, KEIN Greedy/ANY/$default-Ersatz), `authorization_type = JWT`, `authorizer_id` = bestehend, `target` = bestehende Integration. KEINE andere Architekturaenderung (kein Authorizer/Integration/Permission/Tabelle/Rolle/Lambda-Code).

## 3. fmt/validate/Plan (mayaws, dev-Workspace mays-ris, Backend S3+Lock, KEIN Apply)

- `fmt -check modules/api/main.tf`: clean (Exit 0).
- `validate`: Success (nur bekannte deprecated-range_key-Warnings).
- Voll-Plan (/tmp/p16.tfplan): **16 to add, 2 to change, 0 to destroy**.
- Davon P16-eigen: GENAU 7 (alle 7 Routen; Sample verifiziert: JWT + Authorizer `9ghezn` + API `aboqolpm0f`).
- P13-pending: 1 (introspection — korrekt weiter offen nach P13-Entscheid C).
- Fremd/Drift (PRE-EXISTING, NICHT P16, NICHT anwenden ohne separates Gate): 6 CLI-Routen-Adds (live-existent, state-fremd aus Gates 10/12) + SQS-Mapping/IAM-Policy-Adds (live-existent) + Pool-Update (VAR-ARTEFAKT ohne `--var`-Flags) + Lambda-Update (echter Code-Drift, ausserhalb Scope).
- STOP/OPEN-Pruefung: KEINE Lambda-Codeaenderung (TF-seitig) · KEINE Cognito-Aenderung (ausser bekanntem Var-Artefakt) · KEINE IAM-Aenderung (ausser Drift-Add) · KEIN neuer Authorizer (alle 7 nutzen `9ghezn`) · KEINE Tabellen · KEIN Destroy · KEIN unerwartetes Delete. ALLE Fremdposten = dokumentierter Bestand (P13-identisch + 7 P16-Adds).

## 4. Suite / Live-Status

- Suite: 699 passed, 8 skipped; 15 failed + 1 ERROR IDENTISCH zur P15-Baseline (P16 enthaelt KEINE Python-Aenderung — Erwartung bestaetigt).
- Live: KEINE der 7 Routen vorhanden (zu erwarten); auto_deploy wuerde bei Apply SOFORT scharf schalten (dokumentiert).

## 5. Apply-Optionen (Entscheid OFFEN — KEIN Apply erfolgt)

- A) Voll-Apply: ABGELEHNT (Route-Konflikte + Pool/Lambda-Seiteneffekte).
- B) Gezielt (NUR 7 P16-Routen, ggf. gemeinsam mit P13-Introspection-Route, nach Lambda-Deploy-Entscheid + Smoke-Test): EMPFOHLENER Pfad, braucht EXPLIZITE Freigabe (Handler-Code P15 ist im aktuellen Lambda-Stand NICHT deployed — Routen ohne Code-Deploy antworten 404 des ALTEN Stands).
- C) Kein Apply (vorbereitet liegen lassen): gueltiger Zwischenstand.
- Naechstes Gate bei B: koordinierter Deployment-Lauf (Lambda-Deploy + gezielte Route-Applies + JWT-Smoke inkl. Secret-Einmaligkeit live) — NICHT in P16.

**HARD STOP (kein Apply ohne Entscheid; warte auf Freigabe).**
