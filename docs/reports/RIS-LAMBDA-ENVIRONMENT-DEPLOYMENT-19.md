# RIS-LAMBDA-ENVIRONMENT-DEPLOYMENT-19 — Lambda Env / Code Deployment

STATUS: GREEN (Code + 3 Environment-Variablen live; 0 add / 0 change / 0 destroy für die P19-Ressource)

- Datum: 2026-10-04 UTC
- Branch/HEAD: `main`, `3a4d027` (P18B-Commit)
- Account/Region/Workspace: `240571105849` (`arn:aws:iam::240571105849:user/Mayaws`) / `eu-central-1` / `mays-ris`
- Lambda: `mays-ris-dev-agent`
- Basis: P18B GREEN (State/Live-Parity der Platform-Tabellen)

## 1. Kontext-Gate (Schritt 1)

| Prüfung | Ergebnis |
|---|---|
| Branch / HEAD | `main` / `3a4d027` |
| `git status --short` | nur 9 vorbestehende untracked Reports + `terraform/.terraform.lock.hcl`; keine tracked Änderung |
| `AWS_PROFILE` | `mayaws` (für **alle** AWS-/Terraform-Kommandos gesetzt) |
| Account | `240571105849`, Identity `user/Mayaws` — passt zum RIS-Dev-Kontext |
| Region | `eu-central-1` |
| Workspace | `mays-ris` |
| Lambda vorhanden | `mays-ris-dev-agent`, State `Active`, `StateReason` leer |
| CodeSha256 (alt) | `zSt29/mH4DADAJz8yXvETWOH8Yvnbpy0P02k+SQM16I=` |
| Env (alt) | 8 Variablen; **0/3** der benötigten vorhanden |

Zusätzlich erfasst (unverändert nach Deploy): Runtime `python3.14`, Handler `handler.lambda_handler`, Timeout `30`, Memory `128`, Arch `x86_64`, Role `mays-ris-dev-agent`, `VpcConfig` null, `Layers` null, `DeadLetterConfig` null, KMS null, Tracing `PassThrough`.

## 2. Code / Packaging (Schritt 2)

Bestehender Lifecycle, **keine neue ZIP-Logik**: `lambda/build_zip.py --bundle agent` (`lambda/build_zip.py:186-197`, deterministischer Writer `:165-183`). Der Installer-Wrapper `installer/ris.py:162-193` delegiert genau dorthin. Der veraltete generische `--source/--output`-Pfad (`:15-48`, fehlerhaft: ohne `agents/`) wurde **nicht** verwendet.

Determinismus belegt: zwei aufeinanderfolgende Builds ergaben identische Bytes.

- Dateien: **52**, keine Verzeichnis-Einträge, alle `.py`
- Inhalt: `handler.py`, `documents.py`, `agents/**`, `jobsearch/**` (Präfix `lambda/` entfernt) → Handler `handler.lambda_handler`
- Ausschlüsse: nur `.py`; kein `__pycache__`, `.git`, `.pytest_cache`, `.DS_Store`, `.pyc`, `.pyo`; keine Tests/Docs/Terraform-Artefakte
- sha256 hex: `c9a297bd2b71fe8fccfd71d4880d35775f1c143a22df93cc70089b7aab9b6477`
- sha256 base64 (= Terraform `source_code_hash`): **`yaKXvStx/o/M/XHUiA01d18cFDoi35PMcAibequbZHc=`**

Bundle-Hygiene: Pattern-Scan über alle 52 Entries auf Secrets/Private Keys/Tokens ohne Treffer; keine `.env`, `.pem`, `.key`, kein Terraform-State, keine Cache-Verzeichnisse im Paket.

**Wichtiger Befund:** `terraform/lambda.zip` war **stale** (`193ad881…`, aus P17, dort ausdrücklich „NICHT deployed"). Der Quellcode ist seitdem durch B3 (`028a24d`, `worker_authorization.py`) und `handler.py` weitergegangen. Der frische Build `c9a297bd…` ist die korrekte, aktuelle Quelle — genau die Vertragswirkung „geänderte Quelle → anderer Hash → Lambda-Update".

## 3. Terraform Plan (Schritt 3)

Gezielter Plan auf `module.lambda.aws_lambda_function.agent` (kein Full Apply).

**`Plan: 0 to add, 1 to change, 0 to destroy.`** — 0 Replacement-Marker, 0 Destroy.

Geänderte Attribute **ausschließlich**:

| Attribut | vorher | nachher |
|---|---|---|
| `source_code_hash` | `cgveMknpjTT7VDoyBTZ1ihKP/1B6DKCqtG2TVk982Vo=` | `yaKXvStx/o/M/XHUiA01d18cFDoi35PMcAibequbZHc=` |
| `environment` | 8 Vars | 11 Vars (+3) |
| `filename` | absoluter Pfad | `lambda.zip` (relativ, CWD-Vertrag) |
| `last_modified` | `2026-10-03T10:38:23Z` | known after apply |

Unverändert im Plan: Role, Runtime, Handler, Timeout, Memory, VPC, Layers, Event Source Mapping, IAM-Policies, alle Tabellen, SQS, S3, Cognito (nur als no-op gelistet).

Die drei neuen Werte zeigen exakt auf die P18B-reconcilierten Tabellen:
`API_PROFILES_TABLE=mays-ris-dev-api-profiles`, `OFFERS_TABLE=mays-ris-dev-offers`, `CREDENTIALS_TABLE=mays-ris-dev-credentials`.

Der Code liest diese Namen in `lambda/handler.py:650-651,661-666` (Stack-Build) und `:762-769` (Credential-Pfad) — die Env-Variablen sind damit funktional verdrahtet.

Nebenbefund, ohne Plan-Wirkung: `terraform fmt -check main.tf` meldete Formatierung in den `module "lambda"`/`module "orders_reader"`/`module "monitoring"`-Blöcken. Ursache ist eine **reine Whitespace-Ausrichtung** (`git diff -w` ergibt keinen Unterschied), semantisch identisch, im vorliegenden Plan nicht wirksam. Die Arbeitskopie wurde auf HEAD zurückgesetzt, damit `git status` clean bleibt; `modules/lambda/main.tf` ist fmt-clean.

## 4. Freigabe (Schritt 4)

Plan dem Benutzer als `0 add / 1 change / 0 destroy`, ausschließlich Code + 3 Env-Variablen, vorgelegt. **Explizite Freigabe erhalten** für den gezielten Apply auf `module.lambda.aws_lambda_function.agent`.

## 5. Mutation (Schritt 5)

Vor Apply erneut verifiziert: Account `240571105849`, Region `eu-central-1`, Workspace `mays-ris`.

```
terraform apply -input=false -auto-approve /tmp/p19.tfplan
→ Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

## 6. Live Readback (Schritt 6)

| # | Prüfung | Ergebnis |
|---|---|---|
| 1 | Lambda existiert / ACTIVE | `Active`, `StateReason` leer, `LastUpdateStatus` `Successful` |
| 2 | CodeSha256 = gebautes Artefakt | `yaKXvStx/o/M/XHUiA01d18cFDoi35PMcAibequbZHc=` — **identisch** mit lokalem Build und Plan |
| 3 | `API_PROFILES_TABLE` | `mays-ris-dev-api-profiles` |
| 4 | `OFFERS_TABLE` | `mays-ris-dev-offers` |
| 5 | `CREDENTIALS_TABLE` | `mays-ris-dev-credentials` |
| 6 | keine Secrets in Env | 11 Variablen, kein Key mit `SECRET`/`TOKEN`/`PASSWORD`/`KEY`/`CREDENTIAL_` |
| 7 | SQS/ESM unverändert | UUID `7cc946b9-…`, Queue `mays-ris-dev-work-queue`, Batch `5`, State `Enabled` — nur gelesen |
| 8 | IAM Role unverändert | `AROATQAZHYI46SVUSFZUN`, `CreateDate` 2026-09-30, 8 Role-Policies inkl. `…-lambda-dynamodb-product` — keine Änderung |
| 9 | State ↔ Live konsistent | `source_code_hash` und `last_modified` identisch; 3 Env-Werte identisch |
| 10 | kein unerwarteter Drift | Delta vs. P18B-Plan: **ausschließlich** `agent: update → no-op`; keine Adresse hinzugefügt/entfernt |

`LastModified` live: `2026-10-04T11:44:08Z` (vorher `2026-10-03T10:38:23Z`).

## 7. Tests (Schritt 7)

- Packaging: `41 passed, 2 skipped` (`tests/test_lambda_packaging.py`, `tests/test_ris_installer.py`). Die beiden Skips sind credential-abhängige Live-Tests.
- Domain (P10/P11/P09/P14-HTTP/Introspection) + Packaging zusammen: **286 passed**.
- `terraform validate`: Success (nur bekannte `range_key`-Deprecation-Warnungen).
- Gesamtsuite: `15 failed, 709 passed, 8 skipped, 231 warnings, 1 error` — Fehlerliste-MD5 `d0efae4dba6d8af196593535a46c3e57`, **identisch zur P18/P18B-Baseline**. Keine Python-Änderung in P19.
- Kein Credential-E2E, kein P17, kein Gateway-Test — wie gefordert.

## 8. Fresh Plan (Schritt 7)

**`Plan: 16 to add, 1 to change, 0 to destroy`** (vorher 16/2/0).

- **P19-Ressource `module.lambda.aws_lambda_function.agent`: `no-op`** → 0 add / 0 change / 0 destroy ✔
- Verbleibend ausschließlich der vorbestehende, in P18 klassifizierte Fremd-Drift: 14 API-Gateway-Routen (P16=7, P13=1, CLI=6), `module.iam…lambda_policy`, `module.lambda…sqs_mapping`, Cognito-Update. Nicht angefasst.
- Maschineller Vergleich gegen `/tmp/p18b.json`: keine Adresse nur in einem der beiden Pläne; einziger Aktionswechsel `agent update → no-op`. **Erklärbar**, kein Rest-Change an P19.

## 9. Git

- Commit `0198ae2` (`feat(platform): deploy lambda environment and code 19`): **nur** die beiden P19-Reports, 211 Zeilen. **Kein** Terraform-Code geändert.
- `terraform/lambda.zip` ist git-ignoriert (`.gitignore:64-66`) und wurde nicht committet.
- `terraform/main.tf` wurde auf HEAD zurückgesetzt (reine Whitespace-Ausrichtung aus §3, semantisch neutral) → `git status --short` ist clean.


## 10. Offene Punkte

1. Gateway-Routen für Profile/Credentials/Offers/Introspection sind **nicht** aktiviert (P16/P13 bewusst offen) — die Endpunkte bleiben bis dahin nicht erreichbar.
2. Entitlements-IAM (`TransactWriteItems`) fehlt weiterhin — Gate vor Grant-E2E.
3. `terraform fmt -check main.tf` meldet weiterhin eine Ausrichtungs-Abweichung in `module "lambda"`/`"orders_reader"`/`"monitoring"` (reine Whitespace, ohne semantische Wirkung). Nicht committet, da außerhalb P19-Scope; `modules/lambda/main.tf` ist clean.
4. CI baut weiterhin kein Lambda-Bundle (`ci-cd.yml`) — dokumentiert offen.
5. Kein Credential-Management-E2E und kein P17 in diesem Gate — beabsichtigt.
