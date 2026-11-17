# RIS-CONSENT-RELEASE-05

**Status:** `READY FOR CONTROLLED APPLY`  
**No Terraform apply, no deployment, no authenticated live verification.**

## 1. Main-Merge

| Punkt | Wert |
|---|---|
| Repository | `maynowak/Mays-Recruiting-Intelligence-System` |
| PR | #12 |
| Base vor Merge | `0eb3fe96a7e506e5c08e53816b7cc1c27b4e48f3` |
| Feature-Head | `d3b4de818648467409a9838ec7ea450329a242f5` |
| Merge-SHA | `00363977ede1417c4992933b2639ac442a70a4b0` |
| Merge-Art | regulärer Merge, keine Force-/History-Änderung |
| Feature-Tree == Main-Tree | ja |

Der Consent-Fix aus PR #10 ist weiterhin in Main enthalten. Es wurden keine
Jobsearch- oder andere Repositories geändert.

## 2. CI

Für PR #12 waren **keine CI-Checks konfiguriert/gemeldet** (`no checks
reported`). Der Merge war `CLEAN`/`MERGEABLE`. Die Prüfung erfolgte über die
lokale RIS-Suite und Terraform-Gates.

## 3. AWS-/State-Identität

```text
Profil:       mayaws
Account:      240571105849
Region:       eu-central-1
Workspace:    ris-dev
State-Bucket: mays-ris-tf-state-dev
State-Key:    env:/ris-dev/dev/terraform.tfstate
Serial:       78
Lineage:      9cec61e5-c036-1ad5-6ae4-8b48a50122a4
Resources:    273
State-ETag:   "a7d6a2155823ec8605585c68f38cca95"
```

Der State wurde nicht geschrieben; ETag/VersionId blieben unverändert.

## 4. Endgültiger Plan

Referenzplan `b56bb49f…` war semantisch `0/8/0`, aber die lokalen
Health-Bundles fehlten im Arbeitsbaum. Für den endgültigen Plan wurden die
bereits live ausgerollten Health-Bundles read-only kopiert; dadurch ist ein
neuer, exakt zum gemergten Main passender Plan erforderlich.

```text
/tmp/opencode/ris-consent-release-05.tfplan
SHA-256: 512532f73b7feb6563eeea9ac4bc84e1bb713b90365c87e2f65849e4404bd09c
```

Plan:

```text
0 Add
8 Change
0 Destroy
0 Replace
```

Keine IAM-Policy-Änderung, keine Cognito-/CloudFront-/DNS-Änderung, keine
Änderung an Consent-Enforcement oder Pilot-Allowlist. Keine verlorenen
Lambda-Umgebungsvariablen.

## 5. Acht Lambda-Updates

| Funktion | Änderung |
|---|---|
| `ris-dev-dev-agent` | Agent-Bundle-Update, enthält Consent-Fix |
| `ris-dev-dev-agent-dispatch-ingress` | Agent/Core-Bundle-Update |
| `ris-dev-dev-orders-reader` | Orders-Reader-Bundle-Update |
| `ris-dev-mays-orders-handler` | Orders-Handler-Bundle-Update |
| `ris-dev-mays-orders-sqs-worker` | Orders-Worker-Bundle-Update |
| `ris-dev-mays-orders-agent-result-consumer` | Orders-Result-Consumer-Update |
| `ris-dev-dev-health-writer` | Health-Writer-Bundle-Update |
| `ris-dev-dev-health-publisher` | Health-Publisher-Bundle-Update |

Die Health-Bundles wurden unverändert aus den aktuell live ausgerollten
Artefakten übernommen; es findet keine Health-Code-Änderung statt.

## 6. Bundle-Hashes

```text
agent:            710166684455859d1c8eba9c8a8fe4cda0f964907bd644b4b1aeef078bc96dd5
orders-reader:    e405858718101db34a8d5c1237e36d41a47b7dceb8e0ebff8b01bd86d1c366e5
health-writer:    1694053be023628ee8b233b3fdc735fcabf535cde7a397b32da314b585ca4ee7
health-publisher: 152b1c987c4d7ce00a9ffe0dcdec0cdf72c1b6d69425082cf82398bd1ce55994
orders-module:    fa5b75a5960a8180e513ae90f6aaed34d6b07f379b6256df95ce07595c72025d
```

Der Agent-Bundle enthält nachweislich:

```text
application-storage/1.0 = APPROVED
legalApprovalRef = JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08
```

## 7. Erhaltener Vertrag

- Agent- und Order-Result-Transport bleiben vollständig erhalten.
- `ORDER_DISPATCH_QUEUE_URL` bleibt über den reproduzierbaren
  Builder-Kompatibilitätsadapter erhalten.
- Bestehende Queues und Secrets bleiben erhalten.
- Bestehende IAM-Policies bleiben erhalten; die Legacy-Orders-Dispatch-Policy
  wird nur per `moved` migriert.
- S3-CORS bleibt erhalten.
- Keine Änderungen an Cognito, CloudFront, DNS, Consent-Enforcement oder
  Pilot-Allowlist.

## 8. Tests

```text
Fokussiert Terraform/Security: 58 PASS / 8 skipped
Full RIS:                     2629 PASS / 104 skipped / 5 bekannte Baseline-Fehler
terraform fmt -check:          PASS
terraform validate:            PASS
```

Bekannte Baseline-Fehler:

- `test_composite_lifecycle` (3)
- `test_health_plane_integration` (1)
- `test_platform_handlers` (1)

Auf einem sauberen `origin/main`-Worktree wurden zusätzlich die bekannten
sechs Baseline-Fehler inklusive `test_lambda_packaging` reproduziert.

## 9. Rollback

Der Plan enthält ausschließlich Lambda-Bundle-Updates, keine
Ressourcenlöschung oder -ersetzung. Ein Rollback vor einem späteren Apply ist
durch erneutes Ausrollen der vorherigen Lambda-Bundles möglich; keine
State-Reparatur erforderlich.

## 10. Freigabegrenzen

- Kein Terraform Apply ohne separate ausdrückliche Freigabe.
- Kein Deployment.
- Keine State-Manipulation, kein `-target`, keine Umgehung.
- Authentifizierter Live-E2E bleibt ein separates Gate.
- Keine Production-Wiederherstellung behauptet.

## 11. Offene Risiken

- Die authentifizierte Limited-Beta-Testidentität fehlt weiterhin; der
  Live-E2E ist blockiert.
- Die Health-Bundles sind unveränderte Live-Artefakte und müssen vor einem
  Apply aus demselben Arbeitsbaum verfügbar sein; sie sind nicht als neue
  Quellcode-Änderung zu verstehen.
- Der ursprüngliche Referenzplan `b56bb49f…` ist wegen der fehlenden
  Health-Artefakte nicht mehr der exakte finale Plan; der neue Plan
  `512532f7…` ist maßgeblich.
