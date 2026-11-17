# RIS-CONSENT-DEPLOYMENT-UNBLOCK-04

**Status:** `A — SAFE PLAN READY`  
**No Main merge / no Terraform apply / no deployment / no authenticated live verification.**

## 1. Preflight

- RIS Main: `0eb3fe96a7e506e5c08e53816b7cc1c27b4e48f3` (PR #10 merged).
- Branch: `feature/ris-consent-deployment-unblock-03`.
- AWS account verified via STS: `240571105849` (`mayaws`).
- Region: `eu-central-1`.
- Workspace: `ris-dev`.
- Backend: `mays-ris-tf-state-dev`, key `env:/ris-dev/dev/terraform.tfstate`,
  lock table `mays-ris-tf-lock`.
- State baseline: serial `78`, lineage
  `9cec61e5-c036-1ad5-6ae4-8b48a50122a4`, 273 resources.
- State was not written.

Live Lambda baseline:

```text
ris-dev-dev-agent
Version:       $LATEST
State:         Active
LastModified:  2026-11-16T19:35:14Z
CodeSha256:    9p67rKjkp0h0DAFS6Kht/GN5tc7YImQjjAnXw56Ub8A=

application-storage/1.0 = DRAFT
noticeApproved = false
legalApprovalRef = null
```

## 2. Umsetzung Variante B

`ORDER_DISPATCH_QUEUE_URL` wird über die bestehende generierte
Orders-Konfiguration reproduzierbar erhalten:

- `installer/build_mays_orders_module.py`: deterministischer Build-Adapter
  ergänzt eine optionale Orders-Variable und setzt die Handler-Env nur, wenn
  die RIS-Konfiguration einen Dispatch-Queue-URL liefert.
- `installer/project-configs/ris-dev.json`: bestehender
  `ris-dev-dev-agent-dispatch`-URL wird als `order_dispatch_queue_url`
  hinterlegt.
- `installer/ris.py`: der site-spezifische Overlay-Key ist erlaubt.
- `terraform/variables.tf` und `terraform/main.tf`: bestehende URL wird an das
  generated Orders-Modul durchgereicht.
- Keine Orders-Geschäftslogik, keine neue Ressource, keine neue Architektur.

Zusätzlich werden bestehende Transport-/IAM-/CORS-Ressourcen erhalten:

- Agent-Result-Policy und Agent-Result-Env bleiben erhalten.
- Bestehende Dispatch-Ingress-Tabellen-/Index-Berechtigungen bleiben erhalten.
- Legacy-Orders-Dispatch-Policy wird per `moved` auf den Root-Pfad überführt.
- Bestehende S3-CORS-Konfiguration wird deklariert.
- Consent-Enforcement, Pilot-Allowlist, Cognito, CloudFront und DNS bleiben
  unverändert.

## 3. Plan

Plan-Datei:

```text
/tmp/opencode/ris-consent-unblock-04-final.tfplan
SHA-256: b56bb49f122186ed1d64b002bff0ee59bebffbbefc24fc7150ae5aeb9d844fb6
```

Ergebnis:

```text
Plan: 0 to add, 8 to change, 0 to destroy.
```

- **0 Destroy**
- **0 Replace**
- Keine IAM-Policy-Änderung im finalen Plan (die Legacy-Policy wird nur
  verschoben).
- Keine verlorenen Lambda-Umgebungsvariablen; insbesondere bleibt
  `ORDER_DISPATCH_QUEUE_URL` erhalten.
- Keine Cognito-/CloudFront-/DNS-Änderung.
- Die 8 Änderungen sind erwartete Lambda-Bundle-Updates:
  Agent, Dispatch-Ingress, Orders-Handler, Orders-Result-Consumer,
  Orders-Worker, Orders-Reader, Health-Publisher und Health-Writer.

Das Agent-Bundle enthält nachweislich den wiederhergestellten
Consent-Stand:

```text
application-storage/1.0 = APPROVED
legalApprovalRef = JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08
```

## 4. Tests

```text
Fokussiert Terraform/Security:
58 passed / 8 skipped

terraform fmt -check: PASS
terraform validate:   PASS

Full RIS:
2629 passed / 104 skipped / 5 failed
```

Die fünf Fehler sind bekannte Baseline-Fehler:

- `test_composite_lifecycle` (3)
- `test_health_plane_integration` (1)
- `test_platform_handlers` (1)

Auf einem sauberen `origin/main`-Worktree wurden die bekannten sechs
Baseline-Fehler inklusive `test_lambda_packaging` reproduziert.

## 5. Rollback

Der Plan enthält ausschließlich Lambda-Code-Updates und keine
Ressourcenlöschung/-ersetzung. Rollback vor einem späteren Apply:
erneutes Ausrollen der vorherigen Lambda-Bundles (insbesondere
`terraform/lambda.zip` und die drei Orders-Bundles); keine State-Reparatur
erforderlich. Der Plan selbst wurde nicht angewendet.

## 6. Freigabegrenzen

- Kein Main-Merge.
- Kein Terraform Apply.
- Kein Production-Deployment.
- Keine AWS-/State-Manipulation.
- Keine Änderung an Consent-Enforcement oder Pilot-Allowlist.
- Keine Änderung an Cognito, CloudFront oder DNS.

## 7. Authentifizierte Verifikation

Weiterhin **BLOCKED — AUTHENTICATED LIVE E2E REQUIRED**:

- keine gültige autorisierte Testidentität / kein gültiger Test-Token
- Operator-Refresh-Token: `invalid_grant`
- keine Tokens, Passwörter, personenbezogenen Daten oder Consent-Historien
  protokolliert
- keine Auth- oder Consent-Gate-Umgehung

Der Plan ist damit **ready for deployment approval**, aber die Production-
Wiederherstellung ist nicht behauptet.

## 8. Nächste Operator-Aktion

1. Plan `b56bb49f...` separat reviewen und freigeben.
2. Apply nur nach ausdrücklicher separater Freigabe.
3. Autorisierte Testidentität für den anschließenden Live-E2E bereitstellen.
4. Live prüfen: `noticeState=APPROVED`, `grantAllowed=true`, Grant/Reload/
   Withdraw/Regrant und Owner-Isolation.
