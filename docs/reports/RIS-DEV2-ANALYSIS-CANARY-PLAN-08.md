# RIS-DEV2-ANALYSIS-CANARY-PLAN-08

**Datum:** 2026-11-25
**Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `5e215819f4016fbde24d9b7330c6ff15dd50f3f6`
**AWS:** `262370457690` / `eu-central-1` / `ris-dev2`
**Status:** **READY FOR CANARY APPLY APPROVAL**
**Modus:** Planvorbereitung; kein Apply, kein Order-Create, keine Aktivierung, kein Cleanup

## 1. Preflight (live geprüft)

| Prüfung | Ergebnis |
| --- | --- |
| Base-Apply-06 | Katalog `analysis-agent` ACTIVE, Binding-Route JWT, IAM nur `GetItem` |
| Bootstrap-07 | User `CONFIRMED`, `sub`/Tenant korrekt; Profil ACTIVE; Partner ACTIVE; Bindung gesetzt |
| Entitlement | `ent_bf0c8123844e47bb` gültig, Ablauf `1795714828` = **2026-11-26T17:40:28Z** |
| Synthetic-Modus vor Plan | `false` |
| State | Serial **71**, S3-Version `9Q1_MK4…` (`2026-11-25T17:25:44Z`), kein Lock |
| Identität | ausschließlich die vorhandene `ris-dev2-canary-07`; keine neue angelegt |

## 2. Canary-Plan

Erzeugt mit `C:\tmp\ris-dev2.auto.tfvars` (Basis) und
`C:\tmp\ris-dev2-canary-07\canary.tfvars` (echte Identität, keine Platzhalter).

| Feld | Wert |
| --- | --- |
| Datei | `C:\tmp\ris-dev2-canary-08.tfplan` |
| Größe | 253 537 Bytes |
| SHA-256 | `996864c10b77ed8ced23c5f01e55036caab6676752a38f0c4b0e7f904bb94096` |
| Terraform | 1.17.0; `applyable/complete`, kein Fehler |
| Diff | **0 Add / 1 Change / 0 Destroy / 0 Replace** |
| Betroffene Ressource | `module.analysis_runtime.aws_lambda_function.analysis[0]` |
| Geändertes Attribut | `environment` (Code-Hash unverändert) |

Environment nach Plan:

```text
ANALYSIS_SYNTHETIC_MODE                    = true
ANALYSIS_SYNTHETIC_INSTALLATION            = ris-dev2
ANALYSIS_SYNTHETIC_TENANT_ID               = ris-dev2-canary-07
ANALYSIS_SYNTHETIC_USER_ID                 = a39458b2-7001-701a-c509-47c424d653e5
ANALYSIS_SYNTHETIC_PARTNER_APPLICATION_ID  = ris-dev2-canary-07
ANALYSIS_SYNTHETIC_ISSUER                  = https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_OYN9QiHc5
ANALYSIS_SYNTHETIC_ENTITLEMENTS            = parse.cv,parse.job,analyze.job,compare.tags
ANALYSIS_SYNTHETIC_EXPIRES_AT              = 2026-11-26T17:40:28Z
```

`ANALYSIS_CONSENT=false`, `ANALYSIS_NOTICE_APPROVED=false`; keine weiteren
Ressourcen, keine IAM-/Cognito-/SQS-/DynamoDB-Änderung.

### Drift (erklärt, keine Planänderung)

| Eintrag | Ursache |
| --- | --- |
| `analysis` IAM-Rolle `inline_policy` | bekannter Aggregat-/Normalisierungseintrag (Rolle im Plan No-op) |
| `apiprofiles_binding` Route `authorization_scopes`/`request_models` | Provider-Normalisierung `null` ↔ `[]`/`{}`; AuthorizationType bleibt JWT |
| API-Stage `deployment_id` | neuer Route-Eintrag aus Base-Apply-06 (API-Redeploy), berechnet |
| Cognito `estimated_number_of_users` | 0 → 1 durch den freigegebenen Bootstrap-07 |

## 3. Rollback

Nach einem Canary-Apply wird der Rückweg **neu** geplant (kein alter Plan):

```text
terraform plan -var-file=C:\tmp\ris-dev2.auto.tfvars \
  -out=C:\tmp\ris-dev2-canary-08-rollback.tfplan
```

Erwartet: genau eine Änderung an der Analysis-Environment zurück auf
`MODE=false` und leere Identitäten. Apply erst nach eigener Freigabe; danach
Environment verifizieren. Der Basis-Plan (`9b1e5a66…`) und der Canary-Plan
(`996864c1…`) sind danach nicht wiederverwendbar.

## 4. Live-E2E (nach separater Apply-/Canary-Freigabe)

1. Order mit gültiger AgentOrder V1 in `orderDescription` als der synthetische
   User anlegen (`POST /orders`, JWT).
2. ORDER_DISPATCH beobachten; WorkItem muss persistiert und `RUNNING` sein,
   Identität vollständig (Tenant/User/Partner/Issuer).
3. Analysis-Agent führt aus; Parser-Ergebnis (CV/Job/ATS) entsteht.
4. ORDER_RESULT wird signiert an den MO-Consumer zugestellt und akzeptiert;
   `processing.status=COMPLETED`.
5. Owner-GET liefert das Ergebnis; fremder Owner erhält 404.
6. Negativfälle: falsche WorkId/Korrelation, ungültige Signatur, Replay,
   fremder Tenant/User/Partner/Issuer → keine Autorisierung/kein Ergebnis.
7. CloudWatch auf Fehler prüfen; DLQs müssen leer bleiben.

## 5. Cleanup (vorbereitet, nicht ausgeführt)

Neue reguläre CLI-Pfade (Commit `d420a02`, Domain-Funktionen, keine
DynamoDB-Bypasses):

```text
ris_admin offer withdraw --entitlementId ent_bf0c8123844e47bb --reason cleanup
ris_admin offer status  --offerId off_4b4f0843057c4a91 --status INACTIVE --reason cleanup
ris_admin apiprofile revoke --apiProfileId aprof_cdbd3b6f803744bf --reason cleanup
ris_admin partner deactivate ris-dev2-canary-07 --release-reservation --reason cleanup
aws cognito-idp delete-user-pool-client ... 5ianq5p5ahofqnej6dpu3no7ip
aws cognito-idp admin-delete-user ... ris-dev2-canary-07
```

Danach synthetische Order/WorkItems nach dem bestehenden freigegebenen
Verfahren bereinigen (die DEV2-Orders haben keinen `gsi2`-Subject-Index; der
Order-Cleanup erfolgt daher über den dokumentierten Order-Pfad, nicht über
einen erfundenen Direkt-Delete). Abschließend `MODE=false` per neuem Plan
anwenden und Environment verifizieren. Alle Cleanup-Writes benötigen eine
eigene Freigabe.

## 6. Zeitfenster

Synthetic-Profil und Entitlement enden **2026-11-26T17:40:28Z**. Der Canary
muss davor laufen; danach sind ein neuer Grant und ein neuer Plan nötig.
Ein Apply nach Ablauf ist fail-closed und würde den Test nicht bestehen.

## 7. Grenzen eingehalten

Kein Terraform-Apply, keine AWS-Ressourcenänderung, kein Order-Create, keine
Canary-Aktivierung, kein Cleanup, kein Main-Merge. Die Planerstellung war
read-only (Refresh); State blieb Serial 71.

## 8. Entscheidung

**READY FOR CANARY APPLY APPROVAL** — für exakt
`996864c10b77ed8ced23c5f01e55036caab6676752a38f0c4b0e7f904bb94096`
(0/1/0), Workspace `ris-dev2`, Serial 71, gültig bis 2026-11-26T17:40:28Z.
