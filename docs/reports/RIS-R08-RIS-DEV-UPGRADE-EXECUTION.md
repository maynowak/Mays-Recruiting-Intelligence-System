# RIS-R08 — RIS-DEV Upgrade Execution (Plan & Gate)

- **Datum:** 2026-11-05
- **Modus:** Git-Merge + lokale Gating-Korrektur + Plan; **kein Apply**
- **Ziel:** `ris-dev` · `240571105849` · `eu-central-1`
- **Status:** **PLAN VERIFIED — APPLY AWAITING EXPLICIT APPROVAL**

---

## 1. Git-Baseline

| Feld | Wert |
|---|---|
| Branch | `main` |
| HEAD bei Beginn | `0b1e5fa` (23 lokal voraus, 72 hinter `origin/main`) |
| `origin/main` | `c28c668` (R08-Merge `e0a3fe4`, PR #5 merged) |
| Merge | `1cb4fcc` (Merge origin/main) |
| Gating-Fix | `e609059` (Partner-Surface-Gate) |
| Konflikt | **nur** `terraform/.terraform.lock.hcl` (zwei gültige `h1`-Hashes, beide behalten) |
| Verlorene Arbeit | keine — `userKey`, `gsi-user`, Erasure-Resume, Metrics, Cursor-ARN, 54 Moves, Feature-Gates, Auth-Schutz alle erhalten |

Hinweis: Der Working Tree stand zu Beginn auf `feature/ris-storage-consent-core-01` (unabhängige Arbeit). Dieser Branch wurde nicht verändert; die Arbeit erfolgte auf `main`.

Zuvor benannte Reports existierten nach dem Merge vollständig: R08-Handoff, Main-Consolidation-02, Resolver-E2E-27, Application-Apply-E2E-25, Gateway-E2E-Playbook.

---

## 2. AWS-/State-Baseline

| Feld | Wert |
|---|---|
| STS | `240571105849`, `Mayaws` ✅ |
| Workspace | `ris-dev` |
| Backend | `mays-ris-tf-state-dev`, `env:/ris-dev/dev/terraform.tfstate` |
| Lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` ✅ |
| Serial | 36 ✅ |
| Ressourcen | 185 ✅ |
| State-Version | `3tey8lIH…` (nach Plan unverändert) |

---

## 3. CloudFront-/Cognito-Preservation-Snapshot

| Ressource | Wert |
|---|---|
| RIS-Pool | `eu-central-1_ojbmoiYGM` (`ris-dev-dev-users`), Domain `ris-dev-dev` |
| Jobsearch-Pool | `eu-central-1_ZURSMpD2O`, Custom Domain `auth.mays-job-matcher.app`, Client `5hb3…` |
| Orders-Pool | `eu-central-1_cmJWXujnb` |
| CloudFront | `E1IP0DIEAXAZPY`, `E1R3BHTJNMC6XW` (beide `Deployed`) |
| OAC | `E29OZUCWF2PIIJ`, `E1AEAL7JW5EP6Q` |
| ACM | `0bfb2603…`, `ISSUED` |
| DNS | `auth → dsv3el0c1dn2.cloudfront.net` |
| Endpunkte | Jobsearch 302, RIS-Health 401 |

Plan-Prüfung: **0 aktive Änderungen** an Cognito, CloudFront, OAC, DNS, ACM, Orders.

---

## 4. Aktivierungs-Gate (S07-Blocker)

**Befund:** R08 bringt keine Aktivierungsgrenze für die Partner-Oberfläche. `_handle_personal_api_boundary` setzt nur `Cache-Control`-Header; die 35 Routen wären sofort erreichbar.

**Kleinste Korrektur (`e609059`):**

- Neue Prüfung `_partner_surface_enabled()`.
- Jeder Pfad unter `/v1/partner/me/*` → **503** `Partner surface not activated`, solange `PARTNER_SURFACE_ENABLED != "true"`.
- Terraform setzt `PARTNER_SURFACE_ENABLED = "false"`.
- Bestehende RIS-Routen (`/me`, `/me/profile`, `/agents`, `/platform`, Dokumente, Orders) unverändert.
- 4 neue Tests; 25 fokussierte Tests PASS.

Damit aktiviert der Infrastruktur-Apply **keine** neue personenbezogene Verarbeitung: Tabellen entstehen leer, Routen sind geschlossen, Privacy-/Erasure-Flags bleiben `false`.

---

## 5. R08-Komponentenübernahme

| Komponente | Status im Plan |
|---|---|
| ApplicationV1 (userKey, gsi-user, Metrics, History, Decimal) | CREATE Tabelle + Routen (geschlossen) |
| Partner-Resolver / ACTIVE-only / Release-Reuse | Code in `main`, nicht deployt |
| Decimal-Serialisierung | Code + Tests in `main` |
| Subject-Fence / Admission | Code, nutzt bestehende Work-Items-Tabelle |
| Deletion-Ledger | CREATE Tabelle + IAM, Flag `false` |
| PITR (`r08_pitr_enabled`) | Default `false`, keine Änderung |
| Privacy-Flags | alle `false` |

---

## 6. Terraform-Plan

| Feld | Wert |
|---|---|
| Plan | `/tmp/opencode/ris-dev-r08.tfplan` |
| JSON | `/tmp/opencode/ris-dev-r08-plan.json` |
| **SHA-256** | **`449bf43b195dda5a4bd58b119b6e310ad13ed25d706873b4b5f2c0a6a0691759`** |
| Git-HEAD bei Plan | `e609059` |

| Aktion | Anzahl |
|---|---:|
| CREATE | **52** |
| UPDATE | **4** |
| DELETE | **0** |
| REPLACE | **0** |
| MOVE | 54 |
| no-op | 166 |
| DRIFT | 2 |

### Creates (52)

- **8 DynamoDB-Tabellen:** applications, deletion-ledger, erasure-operations, partner-profiles, privacy-receipts, s3-erasure-phases, upload-cutover, upload-ticket-ledger
- **35 API-Routen:** 10 Applications (inkl. metrics), 8 CVs, 5 CV-Search-Profiles, 5 ATS-Profiles, 5 Manual-Profiles, 2 Privacy
- **9 IAM-Policies:** 8 Tabellen-/Secret-Policies + Subject-Fence-Work-Policy

### Updates (4)

`lambda_function.agent` (Code + Env) sowie `lambda_documents`, `lambda_dynamodb_platform`, `lambda_dynamodb_work` (neue Tabellen-ARNs).

### Drift (2)

Berechnete Attribute; keine geplanten Änderungen daraus.

---

## 7. Deployment-Gate

**Gate A erreicht:** Der Plan ist rein additiv, Schutzgüter unverändert, personenbezogene Oberfläche geschlossen, keine destruktive Erasure aktiv, keine PITR-/Ledger-Aktivierung.

**Es fehlt ausschließlich die ausdrückliche Betreiberfreigabe für exakt diesen Plan-Hash.** Ohne sie: kein Apply.

Bekannte, nicht blockierende Abweichungen: zwei vorbestehende Testfehler auf `origin/main` (`test_execute_agent`, `test_entitlement_denial_is_not_a_degradation`) — nicht durch den Merge verursacht (im separaten Worktree reproduziert).

---

## 8. Statusmatrix

| Bereich | Status |
|---|---|
| Git-Merge R08 | IMPLEMENTED |
| Gating-Fix | IMPLEMENTED · VERIFIED LOCALLY (4 Tests) |
| Terraform-Plan | VERIFIED (52/4/0/0/54) |
| Apply | **NOT EXECUTED — AWAITING APPROVAL** |
| ApplicationV1 auf ris-dev | NOT DEPLOYED |
| Partner-Surface | NOT ACTIVATED (503) |
| Privacy/Erasure/DELETION_LEDGER | NOT ACTIVATED |
| PITR | NOT CHANGED (default false) |
| Cognito/CloudFront/DNS/ACM/Orders | UNCHANGED |
| E2E auf ris-dev | BLOCKED bis Apply |
| RG-09/10/11 | weiterhin BLOCKED |

---

## 9. E2E-Plan nach Apply (Playbook)

`docs/testing/RIS-DEV2-PARTNER-GATEWAY-E2E-PLAYBOOK.md`: Preflight, Schutzgrenzen, synthetischer Partner/Credential, Create/List/Detail/Patch/Metrics/Export/Delete, Decimal `50000.5`/`60000.75`, Fremd-Tenant/-Client, widerrufenes Credential, ACTIVE/INACTIVE, Release/Reuse, Cursor, Cleanup.

Voraussetzung für E2E: temporäre, freigegebene Aktivierung von `PARTNER_SURFACE_ENABLED` **nur** im Testfenster und mit synthetischen Daten — separate Freigabe.

---

## 10. Nächster Schritt

1. Betreiberfreigabe für Plan-SHA `449bf43b…` (Account, Workspace, Änderungsliste).
2. Apply ausschließlich dieses Artefakts.
3. Post-Apply: Preservation-Vergleich, Health, State-Serial.
4. E2E mit synthetischen Daten, danach Cleanup und Gate-Rückstellung.

**STOP — kein Apply ohne Freigabe.**
