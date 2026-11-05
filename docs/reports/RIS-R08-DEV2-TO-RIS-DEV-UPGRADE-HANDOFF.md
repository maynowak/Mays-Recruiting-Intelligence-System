# RIS-R08 DEV2 → RIS-DEV Upgrade Handoff

## Status

**R08 ist in `main` verfügbar. DEV2-Gateway-/JWT-/Partner-E2E ist belegt.
Der RIS-DEV-Upgrade-Plan ist vorbereitet; die Live-Inventur von
`ris-dev` ist mit den vorhandenen Credentials BLOCKED. Kein Apply.**

- GitHub `main`: `e0a3fe458b417eec22f87599f33d71dabb96dcba`
- PR #5: `merged` (Merge-Commit `e0a3fe4`)
- DEV2 Terraform State: Serial **30**
- DEV2 Lambda `CodeSha256`: `uGQX0tnPcIW0y1q6GtSaEPVEBjIDLqYrJzm2OX5wMEU=`
- `ris-dev`: **nicht verändert**
- Production: **BLOCKED**

## 1. GitHub-Commit-Baseline

```text
main (vor Merge):     b490824694005e5a51d51cc1d6062525dab9d933
PR #5 Head:           8124b6abc7b0553cbcebc44b1634ded5450bf46c
Merge-Commit:         e0a3fe458b417eec22f87599f33d71dabb96dcba
Merge-Parents:        b490824... + 8124b6a...
PR #5 Commits:        69
PR #5 Changed files:  159
```

Der Merge erfolgte als regulärer `--no-ff`-Merge ohne Force-Push. PR #5 ist
`closed`/`merged`; `main` enthält alle R08-Fixes, Reports und das E2E-Playbook.

## 2. R08-Änderungsübersicht

### Sicherheit / Privacy / Erasure

- WorkItem-Subject-Fence und atomare Admission/Retry-Begrenzung.
- Terminal-Failure-Behandlung und sichere Wiederaufnahme.
- ApplicationV1-Erasure-Integration in den öffentlichen Löschpfad.
- No-store-/Cache-Schutz für sensible Antworten.
- Durable Deletion-Ledger-Grundlage ohne TTL (Retention/legal hold offen).
- Privacy-Recovery-/Ledger-Verträge und Regressionstests.

### ApplicationV1 / Partner

- Decimal-Request-Fix: `salary.amount` wird verlustbewusst zu `Decimal`
  normalisiert; NaN/Infinity/negative Werte/Überpräzision werden abgelehnt.
- Decimal-Response-Fix: DynamoDB-`Decimal` wird als JSON-Zahl serialisiert;
  Serialisierungsfehler werden nicht mehr als 409 maskiert.
- Partner-Registry-Lifecycle: explizite, idempotente Reservation-Release mit
  Dependency-Check; historische Partnerrecords bleiben erhalten.
- Deterministischer ACTIVE-only-Resolver: Reservation ist autoritativ,
  Owner strongly consistent, Client/Tenant-Abgleich, sonst fail-closed.

### Infrastruktur

- `r08_pitr_enabled` als Opt-in (Default `false`) für R08-Recovery-Tabellen.
- Neue DynamoDB-Tabelle `deletion_ledger` mit GSI `gsi-operation`.
- Lambda-IAM-Policy für Ledger-Lesezugriff/-Schreiben.
- Lambda-Umgebung: `DELETION_LEDGER_TABLE` gesetzt,
  `DELETION_LEDGER_ENABLED=false`.
- Keine Löschung bestehender Ressourcen im Terraform-Diff.

### Admin / Betrieb

- `partner create` verwendet den bestehenden Admin-Trust-Anchor.
- Tenant-conditioned Partner-Deaktivierung.
- `partner deactivate --release-reservation`.
- Windows-Hinweis zum Read-only-Attribut des Trust Anchors.

## 3. DEV2 Live-Evidence

### Deployment

| Prüfung | Ergebnis |
|---|---|
| Plan | 0 add / 1 change / 0 destroy |
| Einzige Änderung | `module.lambda.aws_lambda_function.agent` |
| Lambda-Status | `Active` / `Successful` |
| `CodeSha256` | `uGQX0tnPcIW0y1q6GtSaEPVEBjIDLqYrJzm2OX5wMEU=` |
| State | Serial 29 → **30** |
| No-Changes-Plan | Exit 0 |
| Health | 200 |

### Echter Gateway-/JWT-/Partner-E2E

| Test | Ergebnis |
|---|---:|
| Metrics | 200 |
| Create mit `salary.amount=50000.5` | 201 |
| List / Detail | 200 / 200 |
| Patch `salary.amount=60000.75` | 200, Version 1 → 2 |
| Export | 200 |
| Delete | 204 |
| Metrics nach Create / Delete | 1 / 0 |
| Ungültiger Partner-Key | 401 |
| Widerrufenes Credential | 403 |

DynamoDB persistierte exakt:

```text
Decimal("50000.5")
Decimal("60000.75")
```

### Resolver / Reservation / Reuse

- Drei historische INACTIVE-Partner blockierten die ACTIVE-Bindung nicht.
- Release: `partner-r08-27` → INACTIVE, Reservation entfernt.
- Real-Client-Reuse: `partner-r08-27-reuse` wurde mit demselben
  Cognito-Client angelegt und deterministisch als ACTIVE aufgelöst.
- Cleanup: 6 Partner INACTIVE, 8 APIProfiles REVOKED, 6 Credentials REVOKED,
  0 Reservations, 0 Applications, 0 Cognito-User, 0 Secret-Dateien.

## 4. PITR und Ledger

### PITR

- DEV2-Plan verwendet `r08_pitr_enabled=true`.
- PITR ist für die R08-Recovery-Tabellen und `deletion_ledger` aktiviert:
  `erasure_operations`, `privacy_receipts`, `s3_erasure_phases`,
  `upload_cutover`, `upload_ticket_ledger`, `deletion_ledger`.
- Im Terraform ist **kein** explizites `recovery_period_in_days` gesetzt.
  Damit gilt der AWS-Default (35 Tage); live zu bestätigen.
- PITR ist ein Opt-in und defaultmäßig `false`; der Wert muss pro Umgebung
  bewusst gesetzt werden.

### Ledger

- Tabelle `ris-dev2-dev-deletion-ledger` ist ACTIVE.
- IAM-Policy erlaubt `GetItem`, `PutItem`, `Query` auf Tabelle und Index.
- Lambda erhält `DELETION_LEDGER_TABLE`, aber
  `DELETION_LEDGER_ENABLED=false`.
- Kein TTL, bis Retention/Legal-Hold freigegeben ist.
- Durable-Ledger-Code ist in `main`, aber der produktive Pfad bleibt
  deaktiviert (RG-10 BLOCKED).

## 5. E2E-Playbook

`docs/testing/RIS-DEV2-PARTNER-GATEWAY-E2E-PLAYBOOK.md`

Enthält Preflight, Schutzgrenzen, Testpartner-/Credential-Lifecycle,
Gateway-/JWT-Matrix, ApplicationV1 inkl. Decimal, Negativmatrix,
Release/Reuse/Cleanup, Troubleshooting, Reportvorlage und Jobsearch-Handoff.

## 6. RIS-DEV dokumentierte Baseline

Live-AWS-Zugriff war in diesem Lauf **nicht möglich**: lokal existiert nur
das Profil `default` (Konto `262370457690`, `arn:aws:iam::262370457690:user/devnemo`).
Ein `mayaws`-/`ris-dev`-Profil ist nicht vorhanden. Die folgenden Werte sind
dokumentierte Reports, **nicht** in diesem Lauf live verifiziert:

| Element | Dokumentierter Stand |
|---|---|
| Account | `240571105849` |
| Principal | `arn:aws:iam::240571105849:user/Mayaws` |
| Region | `eu-central-1` |
| Backend | `s3://mays-ris-tf-state-dev` |
| Lock | `mays-ris-tf-lock` |
| Key | `dev/terraform.tfstate` |
| Workspace-Prefix | `env:` |
| Workspace | `ris-dev` |
| State-Key | `env:/ris-dev/dev/terraform.tfstate` |
| Ressourcen | ca. 169 (Stand 2026-10-21) |
| Cognito-Pool | `eu-central-1_ojbmoiYGM` |
| Human-Client | `7ldhihlpdgsgcl3puvu4oi7ksv` (public) |
| API | `ris-dev-dev-api` / `g6901and25` |
| ACM | `arn:aws:acm:us-east-1:240571105849:certificate/0bfb2603-a919-4b06-b4b9-da246c4edf75` |
| Identity-Modus | dokumentiert `external` (nicht managed) |

## 7. Unterschiede DEV2 ↔ RIS-DEV

| Bereich | DEV2 | RIS-DEV |
|---|---|---|
| Account | `262370457690` | `240571105849` |
| Backend | `ris-dev2-tf-state-dev` | `mays-ris-tf-state-dev` |
| Workspace | `ris-dev2` | `ris-dev` |
| State Serial | 30 | live zu ermitteln |
| Cognito | managed, Pool `K3dkdSipZ` | dokumentiert external, Pool `ojbmoiYGM` |
| API | `8apxb6fgne` | `g6901and25` |
| Custom Domain/ACM | deaktiviert | dokumentiert vorhanden |
| Orders | `disabled` | live zu prüfen |
| R08 PITR/Ledger | aktiviert (PITR), Runtime disabled | Plan muss Opt-in bewusst setzen |

Alle Unterschiede sind vor einem ris-dev-Plan live read-only zu bestätigen.

## 8. RIS-DEV Upgrade-Plan (kein Apply)

### Phase 0 — Zugang und Read-only-Preflight

1. Separaten ris-dev-Credential-Zugang bereitstellen (`mayaws` oder
   äquivalentes Profil); keine Credentials in Git/Logs.
2. STS: Account `240571105849`, Principal und Region `eu-central-1` bestätigen.
3. Terraform-Workspace `ris-dev` und Backend explizit verifizieren; keine
   Workspace-Neuerstellung, kein State-Move/Import.
4. `terraform state pull` → Serial, Lineage, Ressourcenzahl, SHA-256
   dokumentieren; State-Backup erstellen.

### Phase 1 — Inventur

Read-only prüfen:

- Cognito-Pool/Client/Domain/OAuth unverändert;
- API Gateway, Authorizer, Routen;
- CloudFront/OAC, Route53/DNS, ACM;
- Lambda, SQS/Event-Mappings, DynamoDB-Tabellen, S3-Buckets;
- bestehende IAM-Rollen/-Policies;
- Orders-Lifecycle und externe Identitätskonfiguration.

### Phase 2 — Plan

1. Agent-Bundle reproduzierbar bauen; Hash protokollieren.
2. `terraform init` mit ris-dev-Backend; `workspace select ris-dev`.
3. Plan mit ris-dev-Variablen, `r08_pitr_enabled` bewusst setzen.
4. Erwartete R08-Änderungen: `deletion_ledger`-Tabelle, PITR auf sechs
   Tabellen, Lambda-Code/-Umgebung, Ledger-IAM-Policy.
5. STOP bei:
   - Cognito-/CloudFront-/DNS-/ACM-Änderungen oder Replacements;
   - Deletes bestehender Ressourcen;
   - IAM-Wildcards oder fremden Ressourcen;
   - PITR-Änderungen außerhalb des freigegebenen Sets;
   - State-Lineage-/Serial-Abweichung.
6. Gespeicherten Plan, vollständigen Diff und SHA-256 zur separaten Freigabe
   vorlegen.

### Phase 3 — Apply (nur nach Freigabe)

1. Genau den geprüften Plan anwenden; kein Replan, kein `-target`.
2. Post-Apply: Lambda-Code-Hash, `No Changes`, Health, State-Serial/Lineage.
3. Keine Änderung an `ris-dev`-Cognito/CloudFront/DNS/ACM/SQS außerhalb des
   freigegebenen Plans.

### Schutzgüter

Cognito-Pool/-Client/-Domain, CloudFront/OAC, Route53/DNS, ACM,
bestehende Lambda/API, SQS/Event-Mappings, DynamoDB-Daten, S3-Dokumente/
Health-Buckets, Mays-Orders und Produktionsdaten.

## 9. Bekannte Risiken und offene Prüfungen

- PR #5 hatte **keine CI-Statuses und keine Reviews**; Merge erfolgte auf
  ausdrückliche Betreiberfreigabe.
- Full-Suite-Report nennt 29 Failures (dokumentierte Umgebungs-/Legacy-Fixtures).
- Gate B: **NO-GO**.
- RG-09 Legal/Privacy: **OPEN**.
- RG-10 PITR/Restore/Deletion-Ledger: **BLOCKED**.
- RG-11 SQS/DLQ-Live-Evidence: **OPEN/BLOCKED**.
- Produktive R08-C-Erasure: **BLOCKED**.
- RIS-DEV-Live-Inventur: **BLOCKED** (kein ris-dev-Credential).
- PITR-Retention ist AWS-Default 35 Tage, nicht explizit im Code gepinnt.
- Jobsearch-Vercel-BFF und echter `RIS_API_KEY` sind durch den synthetischen
  RIS-Test nicht geprüft.

## 10. Gate-Tabelle

| Prüfung | Ergebnis |
|---|---|
| PR #5 Readiness | **PASS** |
| Merge nach main | **PASS** |
| R08 in main | **VERIFIED** |
| RIS-DEV Handoff | **COMPLETE** |
| RIS-DEV Upgrade-Plan | **READY (Live-Inventur BLOCKED)** |
| RIS-DEV Apply | **NOT AUTHORIZED** |
| Gate B | **NO-GO** |
| Production | **BLOCKED** |
