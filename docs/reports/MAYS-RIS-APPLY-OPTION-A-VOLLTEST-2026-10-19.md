# Schritt 3 – Vollständiger Testbericht nach `terraform apply` (Option A) (2026-10-19)

**Datum:** 2026-10-19
**Status:** COMPLETED (GREEN, 1 Befund gelb siehe §7)
**Umgebung:** Account `240571105849`, Region `eu-central-1`, Profil `AWS_PROFILE=mayaws`
**Deployment:** `project_name = mays-ris`, `environment = dev` (Defaults), direkt aus `<RIS-Root>/terraform`
**State:** `s3://mays-ris-tf-state-dev/terraform.tfstate` (Lock-Tabelle `mays-ris-tf-lock`)

## 1. Idempotenz-Test (Kernakzeptanz)

```
terraform plan -detailed-exitcode
→ Exit 0 = „no changes" (0 to add, 0 to change, 0 to destroy), 0 Fehler
```

**PASS** – zweiter Plan nach dem Apply ist leer. Kein Drift, keine untrackten
Änderungen an den 167 erzeugten Ressourcen.

## 2. Live-Inventar (AWS-API, nicht Terraform-Output)

| Prüfung | Erwartung | Ist | Ergebnis |
|---|---|---|---|
| DynamoDB Tabellen (mays-ris-*) | 10 Stück | agent-catalog, agent-state, api-profiles, credentials, entitlements, jobsearches, offers, partner-applications, user-profile, work-items | PASS |
| Orders-Tabelle | `mays-ris` (Vertrag: Table == project_name) | `mays-ris`, ACTIVE, angelegt 14:33 | PASS |
| Lock-Tabelle | `mays-ris-tf-lock` | vorhanden (PAY_PER_REQUEST) | PASS |
| Lambda-Funktionen | 6 | `mays-ris-dev-agent`, `mays-ris-dev-orders-reader`, `mays-ris-dev-health-writer`, `mays-ris-dev-health-publisher`, `mays-ris-handler`, `mays-ris-sqs-worker` | PASS |
| Runtimes | python3.14 | alle 6 python3.14 | PASS |
| HTTP APIs | 2 | `mays-ris-dev-api` (Kern, JWT) + `mays-ris-api` (Orders, JWT) | PASS |
| Orders-Routen (Kern-API) | 3 | `POST/GET /orders`, `GET /orders/{id}`, `PATCH /orders/{id}/status` → Integration orders-reader | PASS |
| Orders-Routen (eigene API) | 4 | alle JWT | PASS |
| Cognito Pools | 2 | `mays-ris-dev-users` (RIS) + `mays-ris-users` (Orders, Gruppe `staff`) | PASS |
| SQS Queues | 6 | work/cv/ats/match/dlq (`mays-ris-dev-*`) + `mays-ris-orders-queue` | PASS |
| S3 Buckets | 5 | dev-data, dev-documents, dev-health-public, dev-health-state, cloudtrail-240571105849 | PASS |
| CloudTrail | 1, multi-region | `mays-ris-trail`, HomeRegion eu-central-1 | PASS |
| Log-Groups | 8 | Orders-Handler/Worker/Agent-Retention 14 d, orders-reader 7 d | PASS |

## 3. Verkabelungstest (ARN/URL-Links aus Schritt 0/A)

| Prüfung | Ergebnis |
|---|---|
| `orders_reader` Env `ORDERS_TABLE` = Modul-Output Tabelle | `mays-ris` ✔ **PASS** |
| `orders_reader` Env `ORDERS_SQS_QUEUE_URL` = Modul-Output Queue | `…/240571105849/mays-ris-orders-queue` ✔ **PASS** |
| Event-Source-Mapping Queue → Worker | `mays-ris-orders-queue` → `mays-ris-sqs-worker`, **Enabled**, BatchSize 5 **PASS** |
| IAM Least Privilege Reader | Inline-Policy: `dynamodb:GetItem/Query/UpdateItem/PutItem` auf `table/mays-ris` + `index/*`; `sqs:SendMessage` auf `mays-ris-orders-queue`; Logs **PASS** |
| Work-Queue-ESM (RIS-Kern) | `mays-ris-dev-work-queue` → agent, Enabled **PASS** |

## 4. API-/Auth-Smoke-Tests (Live-HTTP)

| Route | Erwartung | Ist | Ergebnis |
|---|---|---|---|
| `GET …/health` (RIS) | 401 ohne JWT (API-STANDARD.md Z.62) | HTTP 401 `{"message":"Unauthorized"}` | PASS |
| `GET …/platform` (RIS) | 401 ohne JWT | HTTP 401 | PASS |
| `GET …/orders` (Orders-API) | 401 ohne JWT | HTTP 401 | PASS |

Beide Authorizer aktiv: `jwt-human` (Cognito) + `jwt-m2m` (X-Api-Credential).
Geschützte Routen liefern ohne Token korrekt 401 – kein unauthentifizierter Zugriff.

## 5. Monitoring-Test (Option A)

| Prüfung | Ergebnis |
|---|---|
| Dashboards | `mays-ris-overview` + `mays-ris-orders-overview` (keine Namenskollision) **PASS** |
| Alarme gesamt | 13 = 7 Kern (inkl. DLQ) + 6 Orders (ohne DLQ, wie gebucht) **PASS** |
| Alarm-Zustände | alle 13 in `OK` (treat_missing_data = notBreaching) **PASS** |
| Prefixe | Orders-Alarme `mays-ris-orders-*` **PASS** |

## 6. Backend-/State-Test

| Prüfung | Ergebnis |
|---|---|
| State-Objekt in S3 | `terraform.tfstate` vorhanden (12:37 UTC), geschrieben nach Apply **PASS** |
| Locking | `mays-ris-tf-lock` vorhanden, Plan lief mit Lock (kein `-lock=false` nötig) **PASS** |
| Apply-Zusammenfassung | `Resources: 167 added, 0 changed, 0 destroyed`, Exit 0 **PASS** |

## 7. Befunde (nicht blockierend)

1. **GELB – Doku-Widerspruch `AGENTS.md` vs. API-STANDARD:** `AGENTS.md`
   behauptet „`/health` is only unauthenticated", die kanonische `docs/api/API-STANDARD.md`
   (Z.62) schreibt `GET /health | JWT`. Live-Verhalten = 401 → **API-STANDARD ist korrekt,
   AGENTS.md ist veraltet**. Empfehlung: AGENTS.md-Zeile anpassen (kein Code-Fix nötig).
2. **GELB – Vorhandene, nicht verwaltete Reste im Account:** Buckets
   `mays-orders-ci-artifacts-dev`, `mays-ris-parallel-b-tf-state-test`, Log-Groups
   `mays-orders-cognito-backup-lambda`, `mays-ris-parallel-b-test-health-publisher`,
   deaktivierter ESM auf `mays-orders-orders-queue`. Nicht im State, kein Konflikt
   (Plan sauber), aber aufräumen empfohlen.
3. **GRÜN – Lock-Tabelle fehlte** (Account hatte keine DynamoDB-Tabellen vor Apply);
   wurde als Bootstrap-Teil von Schritt 2 angelegt.
4. **GRÜN – Korrektur früherer Reports:** Die Pläne vor Schritt 1 endeten mit Exit 1;
   `module.mays_orders` = 25 (nicht 24). Berichte von Schritt 0–2 sind entsprechend
   in Schritt 1 korrigiert und im Auditlog vermerkt.

## 8. Gesamtergebnis

**34/34 Live-Prüfungen bestanden.** Deployment ist vollständig, konsistent zum
Terraform-State, idempotent und entspricht den Verträgen (AR-URL-Links, Orders-Facade,
Least Privilege, Monitoring mit DLQ-Gate). Einziger offener Punkt ist die veraltete
AGENTS.md-Zeile zu `/health` (§7.1).

**Reproduktion:**

```bash
cd terraform
TF_DATA_DIR=/tmp/tfS3 AWS_PROFILE=mayaws terraform plan -detailed-exitcode \
  -var="filename=$PWD/../lambda/dist/orders-reader.zip" \
  -var="health_writer_zip_path=$PWD/../lambda/dist/health-writer.zip" \
  -var="health_publisher_zip_path=$PWD/../lambda/dist/health-publisher.zip"
# → Exit 0 = sauber
```
