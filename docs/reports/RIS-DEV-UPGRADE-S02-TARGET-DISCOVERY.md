# RIS-DEV-UPGRADE-S02 — Target Discovery

- **Datum:** 2026-11-03
- **Modus:** READ-ONLY DISCOVERY — kein Terraform Plan/Apply/Destroy, keine AWS-Mutation
- **Zielinstallation:** `ris-dev` · **AWS-Profil:** `mayaws` · **Region:** `eu-central-1`
- **Erwarteter Account:** `240571105849`
- **Ergebnis:** **GREEN** — Account, State-Ownership und Schutzgrenzen sind eindeutig; Upgrade-Delta ist dokumentiert.

---

## 1. Executive Summary

`ris-dev` ist eine eigenständige, gesunde Installation im Account `240571105849`. Der Terraform-State ist eindeutig zuordenbar (Lineage `9cec61e5-c036-1ad5-6ae4-8b48a50122a4`, serial 36, 185 Ressourcen). Die Installation läuft auf dem Foundation-Stand **vor** den Partner-/ApplicationV1-Merges.

Der Upgrade-Delta ist **rein additiv und klar abgrenzbar**:

- **+7 DynamoDB-Tabellen** (Partner Profiles, CV/Search Profiles, Privacy-Receipts, Erasure-Operations, S3-Erasure-Phases, Upload-Ticket-Ledger, Upload-Cutover, Applications)
- **+33 API-Routen** (Applications, CVs, Search Profiles, Manual Profiles, Privacy Inspect/Export)
- **+1 IAM-Policy** und **+2 Lambda-Environment-Keys** (`APPLICATIONS_TABLE`, `RIS_CURSOR_SECRET`)
- **1 Lambda-Code-Update** (Agent-Bundle)

**Keine** Änderung ist an Cognito, CloudFront, ACM, DNS oder Mays-Orders zu erwarten. Diese Bereiche sind als geschützt inventarisiert.

**Kritischer Eigentumsnachweis:** Das ACM-Zertifikat `auth.mays-job-matcher.app` wird von einer CloudFront-Distribution im **fremden Account `590490809858`** benutzt. Die Domain ist ausschließlich Jobsearch-Eigentum und darf vom RIS-Upgrade nicht beansprucht werden.

**Blocker für S03:** keiner der Discovery. Offen bleiben die aus S01 bekannten fachlichen Punkte (Application-Erasure-Verdrahtung, `RIS_CURSOR_SECRET`-Bereitstellung, Orders-SQS-Policy).

---

## 2. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `main` |
| HEAD vor Auftrag | `64cc38f556e4b5724b700655f91585a6e06011ab` |
| Upstream | `origin/main` = `37782f8` (kein Divergenz-Commit) |
| Lokale Commits | 2 voraus: `4140fbc` (Auth-Schutz), `64cc38f` (S01-Evidence) |
| Merge-Basis | `37782f8` = PR #3 (ApplicationV1 Persistence) |
| Fremde Datei | `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` — unverändert, untracked, **nicht** committed |

Kein Reset, Clean, Rebase, Merge, Stash oder Push ausgeführt. Der S01-Bericht und der RIS-DEV-Handoff (`docs/reports/RIS-BRANCH-CONSOLIDATION-01D-RIS-DEV-HANDOFF.md`) wurden gelesen.

### Vorhandene Funktionen im Checkout (S02-A)

| Funktion | Code vorhanden | Beleg |
|---|---|---|
| ApplicationV1 | ✅ | `jobsearch/application_repository.py`, `docs/contracts/APPLICATION-V1.md` |
| Partnerprofile | ✅ | `jobsearch/partner_profile*`, 12 Treffer |
| CVDocument | ✅ | 5 Treffer, Terraform `cv_documents` |
| CVSearchProfile | ✅ | 4 Treffer |
| ATSSearchProfile | ✅ | 4 Treffer |
| ManualSearchProfile | ✅ | 1 Treffer |
| Privacy Inspect/Export | ✅ | `handler.py` Privacy-Routen |
| Application Erasure | ✅ (Code) | `agents/ecosystem/privacy_application_erasure.py` |
| API-Routen | ✅ 65 deklariert | `terraform/modules/api/main.tf` |
| Terraform-Module | ✅ | 13 Module inkl. `applications`-Tabelle |

---

## 3. S01-Evidence-Übernahme

Aus S01 übernommen und hier nur gegengeprüft:

- Kein belegtes In-Place-Upgrade (DEV2 = Greenfield in `262370457690`).
- DEV2-Reports bleiben historische Evidence; keine Zielwerte übernommen.
- ApplicationV1 ist additiv; Erasure-, Cursor- und Delete-Lücken bestehen im Code weiter.
- `orders_lifecycle` Default `managed`; DEV2 nutzte `disabled`.
- Domain-Konflikt im Overlay wurde in `4140fbc` behoben (`identity_custom_domain_enabled=false`).

**Neu in S02:** Der Live-Zustand bestätigt die S01-Prognose vollständig — die Partner-/Application-Routen und -Tabellen fehlen tatsächlich.

---

## 4. AWS-Identität (S02-B)

| Feld | Wert |
|---|---|
| Profil | `mayaws` |
| Account | **`240571105849`** ✅ erwartet |
| Caller-ARN | `arn:aws:iam::240571105849:user/Mayaws` |
| UserId | `AIDATQAZHYI4SUCNIJNJR` |
| Region | `eu-central-1` ✅ |
| Zeitpunkt | 2026-11-03, Discovery-Lauf |

Account- und Regio-Guard bestanden. Kein Wechsel auf `default`; `default` zeigt historisch auf `262370457690` und wurde nicht verwendet.

---

## 5. Terraform-State-Baseline (S02-C)

| Feld | Wert |
|---|---|
| Backend-Bucket | `mays-ris-tf-state-dev` |
| State-Key | `env:/ris-dev/dev/terraform.tfstate` |
| Lock-Table | `mays-ris-tf-lock` |
| Objekt-Version | `3tey8lIHFnMBSsaWeFErDer8a2BucoCK` |
| Objekt-Stand | 2026-10-31 21:16:27 UTC |
| State-Größe | 453.342 Bytes |
| Versionen im Bucket | 36 |
| Lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Serial | **36** |
| Terraform-Version im State | 1.16.1 |
| Ressourcen | **185** |
| Outputs | 28 |

**Ownership bestätigt:** Lineage, Key und Workspace (`ris-dev`) passen eindeutig zur permanenten Installation. Kein zweiter State im Bucket (nur dieser Key). Keine State-Migration, kein Import, kein Restore durchgeführt.

Ressourcenverteilung (Modul → Anzahl): `api` 38, `health_plane` 18, `lambda` 14, `cognito` 12, `dynamodb` 11, `orders_reader` 11, `cloudtrail` 9, `mays_orders.*` 32, `monitoring` 8, `monitoring_orders` 7, `health_public` 7, `iam` 5, `sqs` 5, `documents` 4, `root` 4.

---

## 6. RIS-Ressourceninventar (S02-F)

### API Gateway

| API | ID | Routen | Auth |
|---|---|---|---|
| `ris-dev-dev-api` | `g6901and25` | **35 live** | alle JWT; 33× Authorizer `3hy7kc` (Human), 1× `p14vbj` (M2M) |
| `ris-dev-mays-orders-api` | `zf8tc0k2r2` | Orders-Routen (Modul) | JWT |

JWT-Audience/Issuer:

- Human: Audience `7ldhihlpdgsgcl3puvu4oi7ksv`, Issuer `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ojbmoiYGM`
- M2M: Audience `82ji073smu1b3fsvj96sonso`, gleicher Issuer

### Lambda

| Funktion | Runtime | Code-SHA256 (gekürzt) | Stand |
|---|---|---|---|
| `ris-dev-dev-agent` | python3.14 | `XjpbDjxp…` | 2026-10-31 21:05 |
| `ris-dev-dev-orders-reader` | python3.14 | `5AWFhxgQ…` | 2026-10-31 21:04 |
| `ris-dev-dev-health-writer` | python3.14 | `FpQFO+Aj…` | 2026-10-31 21:02 |
| `ris-dev-dev-health-publisher` | python3.14 | `FSscmHxN…` | 2026-10-31 21:03 |
| `ris-dev-mays-orders-handler` | python3.14 | `sQGKO9A0…` | 2026-10-31 21:04 |
| `ris-dev-mays-orders-sqs-worker` | python3.14 | `sQGKO9A0…` | 2026-10-31 21:03 |
| `devmemo-permission-test` (fremd) | python3.14 | `R6fL2f5y…` | 2026-10-25 |

Agent-Environment-Keys: `AGENT_CATALOG_TABLE`, `API_PROFILES_TABLE`, `CREDENTIALS_TABLE`, `DOCUMENTS_BUCKET`, `ENTITLEMENTS_TABLE`, `JOBSEARCH_TABLE`, `LOG_LEVEL`, `OFFERS_TABLE`, `RIS_PARTNER_APPLICATIONS_TABLE`, `USER_PROFILE_TABLE`, `WORK_ITEMS_TABLE`, `WORK_QUEUE_URL`.

**Nicht vorhanden:** `APPLICATIONS_TABLE`, `RIS_CURSOR_SECRET`.

### DynamoDB (11 live)

`ris-dev-dev-agent-catalog` (2 Items, GSI `gsi-status`), `agent-state`, `api-profiles` (GSI `gsi-owner`), `credentials` (GSI `gsi-digest`, `gsi-owner`), `entitlements` (`gsi-user`, `gsi-agent`), `jobsearches` (`gsi-user`, `gsi-status`), `offers`, `partner-applications` (`gsi-client`), `user-profile` (`gsi-tenant`), `work-items` (`gsi-user`, `gsi-status`), `ris-dev-mays-orders` (`pk`/`sk`, `gsi1`, `gsi2`).

PITR: auf `partner-applications`, `user-profile`, `jobsearches`, `work-items` **DISABLED**. Keine personenbezogenen Datensätze gelesen (nur `ItemCount`-Metadaten).

### SQS

6 Queues: `ris-dev-dev-{ats,cv,match,work,dlq}`, `ris-dev-mays-orders-orders-queue`.
Event-Source-Mappings: `ris-dev-dev-agent` ← `work-queue` (Enabled), `ris-dev-mays-orders-sqs-worker` ← `orders-queue` (Enabled), **fremd/orphan**: `mays-ris-b-dev-agent` ← `mays-ris-b-dev-work-queue` (**Disabled**). Keine Nachricht gelesen/gesendet/gelöscht.

### Mays-Orders

Vollständig eingebunden (`orders_lifecycle=managed`, effektiv): 32 State-Ressourcen, eigene API `zf8tc0k2r2`, eigene Tabelle, eigene Queue, eigene Cognito-Ressourcen. Orders-Routen `POST /orders`, `GET /orders`, `GET /orders/{id}`, `PATCH /orders/{id}/status` sind live und **nicht** im Kernel-Routenmodul deklariert (separates `orders_reader`-Modul). Keine Orders-Ressource verändert.

---

## 7. Cognito-/Jobsearch-Ownership (S02-D)

### RIS-Identity (geschützt, Terraform-verwaltet)

| Objekt | ID | Details |
|---|---|---|
| RIS-Pool | `eu-central-1_ojbmoiYGM` | `ris-dev-dev-users` |
| Human-Client | `7ldhihlpdgsgcl3puvu4oi7ksv` | Code-Flow, Scopes `openid email profile`, 3 Callbacks, kein Secret |
| M2M-Client | `82ji073smu1b3fsvj96sonso` | `client_credentials`, kein Secret |
| RIS-Domain | `ris-dev-dev` | Prefix-Domain, ACTIVE, CF `d5cxcejge1ybj.cloudfront.net` |
| Identity Provider | — | **keine** (`[]`) |

### Jobsearch-Identity (extern, nicht RIS-eigentümerschaft)

| Objekt | ID | Details |
|---|---|---|
| Jobsearch-Pool | `eu-central-1_ZURSMpD2O` | `ris-dev-jobsearch-dev-users` |
| Jobsearch-Client | `5hb3f6dj5ialg77jf4blur9g6g` | `ris-dev-jobsearch-dev-client` |
| Custom Domain | `auth.mays-job-matcher.app` | **ACTIVE**, Pool `ZURSMpD2O`, CF `dsv3el0c1dn2.cloudfront.net` |
| Prefix-Domain | `ris-dev-jobsearch-dev` | ACTIVE, Pool `ZURSMpD2O` |

### Orders-Identity (Terraform-verwaltet, eigener Pool)

`eu-central-1_cmJWXujnb` = `ris-dev-mays-orders-users`.

**Bewertung:** Die Domain-Zuordnung wurde live bestätigt, nicht aus Reports übernommen. `auth.mays-job-matcher.app` gehört Jobsearch. Der RIS-Pool hat eine eigene Prefix-Domain. Ein RIS-Plan darf weder `domain.custom` erzeugen noch die Jobsearch-Domain umhängen. `identity_custom_domain_enabled=false` im Overlay ist korrekt.

Keine Cognito-Mutation, keine Client-Änderung, keine Domain-Erstellung, keine Benutzermigration.

---

## 8. CloudFront-/DNS-/ACM-Schutzmatrix (S02-E)

| Ressource | Live-ID | Eigentümer | Terraform-Ownership | Schutzstatus |
|---|---|---|---|---|
| RIS Cognito-Pool | `eu-central-1_ojbmoiYGM` | RIS | `module.cognito.aws_cognito_user_pool.users` | **HARD STOP** |
| Jobsearch Cognito-Pool | `eu-central-1_ZURSMpD2O` | Jobsearch | extern / out-of-band | **HARD STOP** |
| Human Client | `7ldhihlpdgsgcl3puvu4oi7ksv` | RIS | TF (Cognito-Modul) | **HARD STOP** |
| M2M Client | `82ji073smu1b3fsvj96sonso` | RIS | TF (Cognito-Modul) | **HARD STOP** |
| Auth-Domain | `auth.mays-job-matcher.app` | Jobsearch | extern | **HARD STOP** |
| RIS-Prefix-Domain | `ris-dev-dev` | RIS | `aws_cognito_user_pool_domain.domain[0]` | geschützt |
| Health-CloudFront | `E1IP0DIEAXAZPY` (`d4bhhpftk2blt.cloudfront.net`) | RIS | `module.health_public` | geschützt, keine Aliases |
| Health-OAC | `E29OZUCWF2PIIJ` (`ris-dev-dev-health-oac`) | RIS | `module.health_public` | geschützt |
| E2E-CloudFront (fremd) | `E1R3BHTJNMC6XW` (`d2tam2y14qwnpq.cloudfront.net`) | fremd | nicht im Repo | **nie anfassen** |
| E2E-OAC (fremd) | `E1AEAL7JW5EP6Q` (`mays-ris-e2e-test-test-health-oac`) | fremd | nicht im Repo | **nie anfassen** |
| ACM-Zertifikat | `…certificate/0bfb2603-a919-4b06-b4b9-da246c4edf75` | external | Referenz only | **HARD STOP** |
| DNS | `mays-job-matcher.app` bei Checkdomain (`ns.checkdomain.de`) | extern | keine Route53-Zone | **HARD STOP** |

**ACM-Eigentumsnachweis:** `Status=ISSUED`, `NotAfter=2027-04-25`, `InUseBy = arn:aws:cloudfront::590490809858:distribution/E13K7HSK6ZHXP2` — also von einer Distribution in **Account `590490809858`** benutzt. Dieser Account ist nicht der RIS-Account; Zugriff besteht nicht. Die Zuordnung wurde daher als **extern / NOT VERIFIED (fremder Account)** klassifiziert, nicht als fehlend.

Route53: **keine Hosted Zone** im Account. DNS liegt extern bei Checkdomain. RIS erzeugt keine Route53-Ressource.

---

## 9. ApplicationV1- und Profil-Readiness (S02-G)

| Funktion | Code in `main` | In RIS-DEV vorhanden | Upgrade erforderlich |
|---|---|---|---|
| Partnerprofile | ✅ | ❌ Tabelle fehlt | **JA** |
| CVDocument | ✅ | ❌ Tabelle fehlt | **JA** |
| CVSearchProfile | ✅ | ❌ Tabelle fehlt | **JA** |
| ATSSearchProfile | ✅ | ❌ Tabelle fehlt | **JA** |
| ManualSearchProfile | ✅ | ❌ Tabelle fehlt | **JA** |
| ApplicationV1 | ✅ | ❌ Tabelle fehlt | **JA** |
| ApplicationV1 GSI | ✅ `gsi-owner` | ❌ | **JA** |
| ApplicationV1 API | ✅ 9 Routen | ❌ 0 live | **JA** |
| Lambda IAM | ✅ `lambda_dynamodb_applications` | ❌ | **JA** |
| Lambda Packaging | ✅ | Bundle vom 2026-10-31, ohne Applications | **JA (Rebuild)** |
| Privacy Inspect/Export | ✅ | ❌ Routen fehlen | **JA** |
| Application Erasure | ✅ Code, ⚠️ nicht verdrahtet | ❌ | **JA + Entscheidung** |
| Cursor Signing | ✅ Code | ❌ `RIS_CURSOR_SECRET` fehlt | **JA (Secret)** |

**Routen-Differenz:** 65 im Terraform deklariert, 35 live. **33 deklarierte Routen fehlen live** — 9 Applications, 12 CVs, 5 Search-Profiles, 5 Manual-Profiles, 2 Privacy. **4 Live-Routen** (`/orders*`) stammen aus dem `orders_reader`-Modul und sind kein Delta.

**Tabellen-Differenz:** 17 deklariert, 10 Kernel-Tabellen live (plus Orders-Tabelle). Fehlend:

`ris-dev-dev-partner-profiles`, `-privacy-receipts`, `-erasure-operations`, `-s3-erasure-phases`, `-upload-ticket-ledger`, `-upload-cutover`, `-applications`.

**Statusbewertung:**

- ApplicationV1: **IMPLEMENTED** (Code), **LOCALLY VERIFIED** (33 Tests), **NOT DEPLOYED**, **AWS VERIFIED = NO**.
- Application Erasure: **IMPLEMENTED**, **LOCALLY VERIFIED**, aber Produktionsaufrufer fehlt → **BLOCKED für Datenschutzfreigabe**.
- Cursor Signing: **IMPLEMENTED**, Secret **nicht bereitgestellt** → Pagination wäre **BLOCKED**.

Keine Erasure-, Freeze- oder Cutover-Funktion aktiviert.

---

## 10. Infrastruktur-Differenzmatrix (S02-H)

| AWS-Komponente | RIS-DEV IST | MAIN SOLL | Erwartete Änderung | Risiko |
|---|---|---|---|---|
| API Gateway | `g6901and25`, 35 Routen | 65 Routen deklariert | **+33 Routen** (additiv) | niedrig |
| Lambda | Agent ohne Applications-Env | Code + 2 Env-Keys | **Code-Update + `APPLICATIONS_TABLE`, `RIS_CURSOR_SECRET`** | mittel (Secret fehlt) |
| DynamoDB | 10 Kernel-Tabellen | 17 Tabellen | **+7 Tabellen** (additiv) | niedrig |
| IAM | keine Applications-Policy | 1 Inline-Policy | **+1 Policy** | niedrig |
| SQS | 6 Queues | unverändert | **NONE** | — |
| Cognito | RIS-Pool + Clients + Prefix-Domain | unverändert | **NONE** | **PROTECTED** |
| CloudFront | Health-Distribution ohne Alias | unverändert | **NONE** | **PROTECTED** |
| DNS | Checkdomain, extern | unverändert | **NONE** | **PROTECTED** |
| ACM | extern benutzt (`590490809858`) | unverändert | **NONE** | **PROTECTED** |
| Mays-Orders | vollständig deployed | unverändert | **NONE** | **PROTECTED** |

**Prognose, kein Plan.** Erwartet wird ein überwiegend additives Ergebnis. Jede `replace`- oder `delete`-Adresse im späteren Plan ist ein Stop und muss einzeln begründet werden.

**Besondere Prüfungen:**

- `orders_lifecycle=disabled`: Der State enthält bereits alle Orders-Module. Ein Wechsel auf `disabled` würde Orders **entfernen** → für das Upgrade **nicht** setzen. Empfehlung: `managed` beibehalten oder das Delta bewusst akzeptieren.
- `identity_custom_domain_enabled=false`: korrekt; verhindert Domain-Konflikt.
- Keine Zielwerte aus `ris-dev2` übernommen.
- Keine Datenbank-Ersetzung, keine neue CloudFront-Distribution.

**Konfigurationsabweichung als Finding:** `terraform/variables.tf` setzt `orders_lifecycle` default `managed`, AGENTS.md empfiehlt `disabled`. Für `ris-dev` ist der Default der Realität entsprechend; ein pauschales `disabled` wäre destruktiv.

---

## 11. Blocker und Risiken

| # | Blocker/Risiko | Schwere | Auswirkung |
|---|---|---|---|
| 1 | `RIS_CURSOR_SECRET` fehlt | ORANGE | Pagination/Cursor → 503 nach Deployment |
| 2 | Application-Erasure nicht verdrahtet | RED (fachlich) | Konto-Erasure lässt Applications zurück |
| 3 | Orders-SQS `Principal="*"` (S01, extern) | RED (extern) | unverändert offen, nicht Teil des Upgrades |
| 4 | PITR auf Kerntabellen deaktiviert | YELLOW | kein Wiederherstellungsschutz |
| 5 | Fremde/verwaiste Ressourcen im Account: `devmemo-permission-test` (Lambda), `mays-ris-b-dev-agent`-ESM (Disabled), E2E-CloudFront/OAC | YELLOW | dürfen nicht angefasst werden; Ownership unklar |
| 6 | ACM-Zertifikat in fremdem Account `590490809858` benutzt | INFO/PROTECTED | bestätigt externe Domain-Ownership |
| 7 | `terraform/modules/mays_orders` generiert | INFO | Rebuild könnte Drift erzeugen; vor Plan einfrieren |
| 8 | Lambda-`depends_on` ohne Applications-Policy (S01) | YELLOW | kurzes Fenster beim ersten Apply |

Kein Ownership-Blocker: Account, State und Schutzgüter sind eindeutig.

---

## 12. Empfehlungen für S03 und S04

**S03 (Upgrade-Plan, weiterhin ohne Apply):**

1. Bundles bauen und hashen (`python lambda/build_zip.py --bundle all`); 0-Byte-Artefakte ausschließen.
2. `RIS_CURSOR_SECRET` bereitstellen (Secret Manager/SSM) und als Env-Key verdrahten — Entscheidung vor Plan.
3. Neuen Plan mit `project_name=ris-dev`, `environment=dev`, `identity_custom_domain_enabled=false`, `orders_lifecycle=managed` erzeugen.
4. Plan auf **ausschließlich additive** Änderungen prüfen: 7 Tabellen, 33 Routen, 1 IAM-Policy, 1–2 Env-Keys, 1 Lambda-Update.
5. Jede `replace`/`delete`-Adresse einzeln begründen; Cognito/CloudFront/DNS/ACM/Orders müssen `no-op` bleiben.
6. Plan-SHA256 dokumentieren und Review abwarten.
7. Kein `-target`, kein `-replace`, kein `-refresh=false`.

**S04 (Apply-Gate):**

1. Freigabe für Plan-Hash und Änderungsumfang.
2. Apply nur mit dem gereviewten Plan.
3. Danach Read-only-Verifikation: 7 Tabellen ACTIVE, 68 Routen live, IAM-Policy vorhanden, Env-Keys vorhanden, JWT-Negativtest 401.
4. Application-Erasure-Entscheidung dokumentieren; bis dahin keine Datenschutzfreigabe.

---

## 13. Abschlussentscheidung

| Gate | Prüfung | Ergebnis |
|---|---|---|
| S02-G01 | Git Main Baseline | **PASS** — `main` @ `64cc38f`, PR #3 enthalten, 2 lokale Commits, keine fremde Änderung |
| S02-G02 | AWS Account Guard | **PASS** — `240571105849`, `eu-central-1`, Profil `mayaws` |
| S02-G03 | Terraform State Ownership | **PASS** — Lineage `9cec61e5…`, serial 36, 185 Ressourcen, eindeutig `ris-dev` |
| S02-G04 | Cognito Protection | **PASS** — RIS/Jobsearch/Orders getrennt; keine Mutation |
| S02-G05 | CloudFront/DNS Protection | **PASS** — 2 CF (1 fremd), 2 OAC, 1 ACM extern benutzt, keine Route53 |
| S02-G06 | Runtime Inventory | **PASS** — API/Lambda/DynamoDB/SQS vollständig erfasst |
| S02-G07 | ApplicationV1 Readiness | **PASS** — Delta vollständig identifiziert (7 Tabellen, 33 Routen, IAM, Env) |
| S02-G08 | Upgrade Delta | **PASS** — additiv prognostiziert, Schutzbereiche `NONE` |
| S02-G09 | Auditlog/Git | **PASS** — Report + Auditlog committed, fremde Datei unberührt |

**Gesamt: GREEN.** Keine kritischen unbekannten Ownership-Grenzen. Offene fachliche Blocker sind benannt und S03 zugeordnet.

**STOP nach S02 — kein Terraform Plan, kein Apply, keine AWS-Mutation.**
