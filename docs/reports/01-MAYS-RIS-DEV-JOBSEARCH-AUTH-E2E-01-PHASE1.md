# MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01 — Phase 1: RIS Development (2026-10-20)

**Ziel:** Dauerhafte RIS-Development-Installation `ris-development` (Environment `dev`)
ohne neuen Parallel-Teststack, mit sauberer Ownership und reproduzierbarem Plan/Apply.

**Task:** MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01, Phase 1
**Workspace:** `ris-development` · **project_name:** `ris-development` · **environment:** `dev`
**Backend:** `s3://mays-ris-tf-state-dev`, Lock `mays-ris-tf-lock`, Region `eu-central-1`
**Ausführungs-Log:** [01-01-…-EXECUTION_LOG.md](01-01-MAYS-RIS-DEV-JOBSEARCH-AUTH-E2E-01-EXECUTION_LOG.md)

## Ausgangslage

| Prüfung | Befund |
|---|---|
| Workspace `ris-development` | existierte **nicht** (`default`, `mays-ris-test-e2e-01`, `ris-a`, `ris-b`) |
| Root-`terraform.tfstate` (Default-WS) | vorhanden, serial 13, **0 Ressourcen** |
| AWS-Ressourcen `ris-development*` | keine (Lambda/DynamoDB/SQS/S3 leer) |
| Lambda-Zips | `orders-reader.zip`, `health-writer.zip`, `health-publisher.zip` vorhanden |

**Fallstrick im vorgegebenen Plan-Befehl:** `terraform workspace select ris-development >/dev/null 2>&1`
wäre still fehlgeschlagen und hätte im Default-Workspace geplant (Root-State). Deshalb
`terraform workspace select -or-create ris-development` verwendet. Der Apply-Befehl nutzte
zudem `TF_DATA_DIR=/tmp/tfS3`, der Plan aber `/tmp/tfris-development`; für den Apply wurde
konsequent derselbe `TF_DATA_DIR` verwendet.

## Plan

```
terraform plan -out=/tmp/ris-development.tfplan \
  -var="filename=$PWD/../lambda/dist/orders-reader.zip" \
  -var="health_writer_zip_path=$PWD/../lambda/dist/health-writer.zip" \
  -var="health_publisher_zip_path=$PWD/../lambda/dist/health-publisher.zip" \
  -var="project_name=ris-development" -var="environment=dev"
```

| Prüfung | Erwartung | Ist | Status |
|---|---|---|---|
| Actions | 169 add (167 + 2 Log-Groups) | `169 to add, 0 to change, 0 to destroy` | ✅ |
| Fremde Präfixe | 0 | `grep -c mays-ris-dev` = **0** | ✅ |
| Namensraum | nur `ris-development*` | 78 eindeutige Namen, alle `ris-development*` | ✅ |
| Data-Sources | read-only | 6 × `read` | ✅ |
| Lambda-Pfade | `$PWD/../lambda/dist/*.zip` | alle drei aufgelöst | ✅ |

## Apply

```
terraform apply -input=false -auto-approve /tmp/ris-development.tfplan
```

**Ergebnis:** `Apply complete! Resources: 169 added, 0 changed, 0 destroyed.` — Exit **0**, keine Errors.

## Post-Apply-Smoke-Tests

| Prüfung | Erwartung | Ist | Status |
|---|---|---|---|
| Workspace | `ris-development` | `ris-development` | ✅ |
| State (Nicht-Data) | 169 | **169** | ✅ |
| API-Endpoint | vorhanden | `https://klklimekab.execute-api.eu-central-1.amazonaws.com` | ✅ |
| `/health` ohne JWT | 401 | **401** | ✅ |
| `/me` ohne JWT | 401 | **401** | ✅ |
| `/platform` ohne JWT | 401 | **401** | ✅ |
| `/agents` ohne JWT | 401 | **401** | ✅ |
| CloudFront health-public | Deployed | `d319t78i6lv8la.cloudfront.net`, **Deployed** | ✅ |
| Cognito RIS-Pool | vorhanden | `ris-development-dev-users` (`eu-central-1_7QCp09XEZ`) | ✅ |
| `custom:tenant_id` | vorhanden | vorhanden (nicht required) | ✅ |
| Lambdas | 4 RIS + 2 Orders | 6 (agent, orders-reader, health-writer, health-publisher, handler, sqs-worker) | ✅ |
| DynamoDB | 11 | **11** | ✅ |
| SQS | 6 | **6** | ✅ |

## Befunde für Phase 2/3

1. **OAuth ist am RIS-Client AUS.** `ris-development-dev-client` ist public
   (`generate_secret=false`), aber `AllowedOAuthFlowsUserPoolClient=false`, keine
   Callback-/Logout-URLs. Der Hosted-UI-Code-Flow ist damit noch nicht nutzbar.
2. **Custom-Domain-Zertifikat existiert bereits:** ACM `auth.mays-job-matcher.app`,
   Region **us-east-1**, Status `ISSUED`, SAN exakt die Domain, `InUseBy=[]`.
   AWS-Doku (verifiziert): Cognito-Custom-Domains verlangen us-east-1, unabhängig
   von der Pool-Region → Zertifikat ist wiederverwendbar.
3. **DNS:** `auth.mays-job-matcher.app` hat **keinen** Record. Apex zeigt auf
   `216.198.79.1` (Vercel), Nameserver `ns.checkdomain.de` / `ns2.checkdomain.de`.
   Der Cognito-Alias-Record muss bei **checkdomain.de** gesetzt werden (extern).
4. **Zwei Cognito-Pools:** RIS-Pool `ris-development-dev-users` und der im
   `module.mays_orders` eingebettete Pool `ris-development-users`. Für Jobsearch
   ist ausschließlich der RIS-Pool zu verwenden.
5. **Jobsearch-Login ist ein Platzhalter:** `LoginForm.tsx`/`RegisterForm.tsx`
   haben kein `fetch`, kein Cognito, keine Session. Phase 3 ist eine echte
   Implementierung, keine „Vervollständigung“ vorhandener Auth-Logik.

## Risiken / offene Punkte

- `terraform/modules/mays_orders/` ist im RIS-Repo **untracked**, wird aber von
  `terraform/main.tf` referenziert → frische Clones können den 169-Plan nicht bauen.
- DNS liegt extern bei checkdomain.de; Alias-Target ist ein manueller Schritt.
- Zwei Pools im Stack erhöhen das Risiko, das Frontend an den falschen Pool zu binden.
- Callback-URLs für Vercel-Preview, Token-Storage und Managed-Login-Version sind
  noch zu entscheiden.

## Nächste Schritte (Freigabe-Gates)

1. **Phase 2a:** Cognito-Modul um OAuth Code + PKCE, Callback-/Logout-URLs und
   `aws_cognito_user_pool_domain.custom` (`auth.mays-job-matcher.app`) erweitern.
2. **Plan vorlegen**, Apply erst nach expliziter Freigabe.
3. **Phase 2b:** Alias-Target auslesen, CNAME `auth` bei checkdomain.de setzen
   (DNS-Mutation, Freigabe nötig), `/.well-known/openid-configuration` verifizieren.
4. **Phase 3:** PKCE-Login im Jobsearch-Repo implementieren.
5. **Phase 4:** E2E Login → Callback → `/me` → Profil → Logout → ungültiges JWT.

**Klassifikation:** Phase 1 **GREEN**; Gesamtaufgabe **YELLOW** (Phase 2–4 offen).
