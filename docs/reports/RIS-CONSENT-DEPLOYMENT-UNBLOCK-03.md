# RIS-CONSENT-DEPLOYMENT-UNBLOCK-03

**Status:** `C — ADDITIONAL DECISION REQUIRED`  
**Plan:** `0 add / 9 change / 0 destroy / 0 replace`  
**No Main merge, no Terraform apply, no deployment, no authenticated live verification.**

## 1. Ausgangslage

Der gemergte Consent-Fix (`application-storage/1.0 = APPROVED`) ist auf RIS
`main` vorhanden. Die laufende Lambda `ris-dev-dev-agent` wurde read-only
geprüft:

```text
Version:       $LATEST
State:         Active
LastModified:  2026-11-16T19:35:14Z
CodeSha256:    9p67rKjkp0h0DAFS6Kht/GN5tc7YImQjjAnXw56Ub8A=
Ausgelieferter Code:
  application-storage/1.0 = DRAFT
  noticeApproved = false
  legalApprovalRef = null
```

Die Live-Umgebung enthält außerdem nicht mehr die früheren Pilotwerte
(`CONSENT_NOTICE_STATE_ENFORCED`, `CONSENT_PILOT_ALLOWLIST`,
`CV_STORAGE_CONSENT_ENFORCED`, `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED`).
Diese Werte wurden in diesem Gate nicht verändert.

## 2. Ursache der 22 Destructions

Die Analyse des Plans und des States zeigte mehrere fehlende
Konfigurationsbindungen, nicht eine Änderung am Consent-Fix:

1. `enable_agent_transport` war im `ris-dev`-Overlay nicht gesetzt; der
   Root- und der Orders-Modul-Count fielen dadurch auf `0`.
2. `orders_producer_role_arns` und `ris_result_producer_role_arns` fehlten im
   Overlay; die bestehenden Queue-Policies wären ohne Principal neu geschrieben
   worden.
3. Die vorhandenen Mays-Orders Result-Queue-/Secret-Werte wurden nicht an die
   Agent-Lambda durchgereicht.
4. Die bestehende S3-CORS-Konfiguration des Documents-Buckets fehlte in der
   Dokumentenmodul-Konfiguration.
5. Zwei bestehende IAM-Policies (`order_result` und
   `order_result_transport`) waren nur im Live-State vorhanden.
6. Der Orders-Handler hatte die Altvariable `ORDER_DISPATCH_QUEUE_URL`, die
   das aktuelle generierte Orders-Modul nicht mehr emittiert.

## 3. Konfigurationskorrektur

Geändert auf `feature/ris-consent-deployment-unblock-03`:

- `installer/project-configs/ris-dev.json`
  - `enable_agent_transport=true`
  - bestehende Orders-Producer-Rolle
  - bestehende RIS-Result-Producer-Rollen
  - bestehende Result-Queue-URL und -ARN
  - bestehendes Result-Secret-ARN
- `installer/ris.py`: diese site-spezifischen Overlay-Keys erlaubt.
- Root-Module:
  - Aktiviert den bestehenden Agent-Transport.
  - Reicht bestehende Result-Transportwerte an Agent- und Lambda-Module durch.
  - Führt die bestehende Orders-Handler-Dispatch-Policy per `moved` vom
    veralteten verschachtelten Modulpfad auf einen Root-Policy-Pfad.
- `terraform/modules/agent_transport`: bestehende `order_result`-Policy und
  bestehende Result-Env-Variablen werden erhalten.
- `terraform/modules/lambda`: bestehende `order_result_transport`-Policy und
  Result-Env-Variablen werden erhalten.
- `terraform/modules/documents`: bestehende S3-CORS-Konfiguration wird
  wieder deklariert.
- Tests: `tests/test_terraform_consent_deployment_unblock.py` und eine
  eng begrenzte CORS-Ausnahme im bestehenden Terraform-Security-Diff-Test
  (CORS-Header-Wildcard ist kein IAM-/Resource-Wildcard).

Keine Änderung an Consent-Enforcement, Pilot-Allowlist, Cognito, CloudFront,
DNS, Providern oder AWS-Ressourcen.

## 4. Neuer Plan

Ziel:

```text
Account:      240571105849
Profil:       mayaws
Region:       eu-central-1
Workspace:    ris-dev
State:        mays-ris-tf-state-dev
Key:          env:/ris-dev/dev/terraform.tfstate
Serial:       78
Lineage:      9cec61e5-c036-1ad5-6ae4-8b48a50122a4
```

Plan-Datei:

```text
/tmp/opencode/ris-consent-unblock-03-final.tfplan
SHA-256: aa7ec40ee2ccaa79942ba3c573c7c7c2d8e7e03c16d8dcab3725cca6d1433eb5
```

Ergebnis:

```text
Plan: 0 to add, 9 to change, 0 to destroy.
```

Keine Replacements. Die 9 Änderungen sind Lambda-Code-Updates und die
notwendige IAM-Policy-Anpassung; die bestehenden Transport-Ressourcen,
Queues, Secrets und S3-CORS bleiben erhalten.

### Ein verbleibender Konflikt

Die Orders-Handler-Lambda würde weiterhin folgende bestehende Altvariable
verlieren:

```text
ORDER_DISPATCH_QUEUE_URL
```

Der aktuelle generierte Orders-Modulstand emittiert diese Variable nicht.
Sie wird im aktuellen Handler-Code nicht gelesen, ist aber im Live-State
vorhanden. Das Gate verlangt „keine verlorenen Lambda-Umgebungsvariablen“;
deshalb ist der Plan **nicht als safe-ready freigegeben**. Erforderlich ist
eine Entscheidung:

- **A:** Altvariable als bewusst nicht mehr benötigt freigeben und Entfernung
  akzeptieren, oder
- **B:** den generierten Orders-Modulvertrag erweitern, damit die Variable
  reproduzierbar erhalten bleibt.

Ohne diese Entscheidung kein Apply.

## 5. Tests

Fokussiert:

```text
tests/test_terraform_consent_deployment_unblock.py
tests/test_terraform_agent_transport.py
tests/test_generated_module_artifact.py
tests/test_entitlement_provisioning.py
# 57 passed / 8 skipped
```

Terraform:

```text
terraform fmt -check: PASS
terraform validate: PASS
```

Vollsuite:

```text
2628 passed
104 skipped
5 failed
```

Die bekannten Baseline-Fehler bleiben unabhängig:

- `test_composite_lifecycle` (3)
- `test_health_plane_integration` (1)
- `test_platform_handlers` (1)

Auf einem sauberen `origin/main`-Worktree wurden zusätzlich die bekannten
sechs Baseline-Fehler inklusive `test_lambda_packaging` reproduziert; der
Packaging-Test ist in diesem Worktree wegen der erzeugten Bundles grün.

## 6. Authentifizierte Verifikation

Weiterhin **BLOCKED — AUTHENTICATED LIVE E2E REQUIRED**:

- kein gültiger autorisierter Test-Token / keine Testidentität verfügbar
- Operator-Refresh-Token liefert `invalid_grant`
- keine Tokens, Passwörter, personenbezogenen Daten oder Consent-Historien
  protokolliert
- keine Umgehung von Auth- oder Consent-Gates

## 7. Freigabegrenzen

- Kein Apply.
- Kein Deployment.
- Kein Main-Merge.
- Keine AWS-/Terraform-State-Manipulation.
- Keine Cognito-/CloudFront-/DNS-Änderung.
- Keine Änderung an Consent-Enforcement oder Allowlist.
- Keine Production-Wiederherstellung behauptet.

## 8. Erforderliche Operator-Aktion

1. Entscheidung zu `ORDER_DISPATCH_QUEUE_URL` treffen (behalten oder bewusst
   entfernen).
2. Danach neuen Plan erzeugen; Akzeptanz weiterhin 0 Destroy / 0 Replace und
   keine unerwarteten Env-Verluste.
3. Plan separat freigeben.
4. Autorisierte Testidentität für den anschließenden Live-E2E bereitstellen.
