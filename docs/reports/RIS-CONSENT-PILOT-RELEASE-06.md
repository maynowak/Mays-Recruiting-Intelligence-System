# RIS-CONSENT-PILOT-RELEASE-06

**Status:** `GO READY — LIMITED BETA PILOT`  
**Scope:** Vollständige Consent-Gate-Verdrahtung für den bestehenden
Limited-Beta-Pilot  
**No general production approval, no apply, no deployment, no Main-Merge.**

## 1. Ergebnis

Der bestehende Pilot ist technisch vollständig verdrahtet:

```text
Plan:        /tmp/opencode/ris-consent-pilot-06.tfplan
SHA-256:     e62370c0536af74b630a810585d95b12fba637a79ba428a13447b01ec07d1b68
State:       serial 80
Lineage:     9cec61e5-c036-1ad5-6ae4-8b48a50122a4
Changes:     1 Add / 5 Change / 0 Destroy / 0 Replace
```

Empfehlung:

```text
GO READY für den Limited-Beta-Pilot
```

Der Apply bleibt bis zu einem ausdrücklichen `GO APPLY` gesperrt.

## 2. Terraform-Wiring

Neu ergänzt und im Plan aktiviert:

```text
APPLICATION_CONSENT_ENFORCED=true
CV_STORAGE_CONSENT_ENFORCED=true
SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=true
CONSENT_NOTICE_STATE_ENFORCED=true
CONSENT_PILOT_ALLOWLIST=<existing pilot allowlist>
```

Die Variablen sind im Terraform-Main und im Lambda-Modul definiert:

```text
terraform/variables.tf
terraform/modules/lambda/variables.tf
terraform/main.tf
terraform/modules/lambda/main.tf
```

Defaults bleiben:

```text
cv_storage_consent_enforced             = false
search_profile_storage_consent_enforced = false
consent_notice_state_enforced           = false
consent_pilot_allowlist                 = ""
```

Nur der freigegebene Pilot-Plan setzt die Werte auf `true` und übergibt die
bestehende Allowlist. Es wurden keine Identitäten ergänzt oder Berechtigungen
erweitert.

## 3. Plan-Diff

### Add

```text
module.jobsearch_edge[0].aws_apigatewayv2_route.partner["POST /v1/partner/me/erasure"]
API: c7e9pdwe78 / Authorizer: e6inno / Target: integrations/anl98ns
```

### Change

| Ressource | Änderung |
|---|---|
| `module.lambda...aws_lambda_function.agent` | neuer Code-Hash; `APPLICATION_CONSENT_ENFORCED` false→true; vier Consent-Env-Keys hinzugefügt |
| `module.agent_transport...dispatch_ingress` | gleicher neuer Agent-Bundle-Code |
| `module.orders_reader...reader` | nur Artefaktpfad |
| `module.health_plane...health_writer` | nur Artefaktpfad |
| `module.health_plane...health_publisher` | nur Artefaktpfad |

Keine entfernten Lambda-Environment-Keys. Keine IAM-, Cognito-,
CloudFront-, DNS-, DynamoDB-, SQS-, S3- oder Secrets-Änderung. Kein Destroy,
kein Replace.

## 4. Freigaben und Fail-Closed-Verhalten

Bestehende, unveränderte Notices:

| Zweck | Freigabe |
|---|---|
| `application-storage/1.0` | `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` |
| `cv-storage/1.0` | `JM-CV-STORAGE-V1-BETA-2026-11-08` |
| `search-profile-storage/1.0` | `JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08` |

Die Freigaben gelten ausschließlich für den begrenzten Pilot. Es wurde keine
allgemeine Legal-/Produktionsfreigabe behauptet und keine neue Freigabe
erzeugt.

Fail-closed:

- ApplicationV1: globales `APPLICATION_CONSENT_ENFORCED=true`.
- CV-/Search-Profile: bestehende Allowlist; nicht gelistete Identitäten
  erhalten `403` statt Storage-Zugriff.
- Notice-State: nur freigegebene Notices werden für neue Grants akzeptiert.
- Reads/Downloads/Deletion bleiben gemäß bestehender Lifecycle-Regeln
  verfügbar; keine Datenlöschung durch diesen Plan.

## 5. Tests / Validierung

```text
Fokussiert Consent/Route:    65 PASS
Fokussiert Route/Privacy:     46 PASS / 318 Subtests
Vollständige RIS-Suite:      2828 PASS / 104 skipped / 18 bekannte Baseline-Fehler
terraform fmt -check:        PASS
terraform validate:          PASS
```

Keine neuen Fehler durch das Wiring.

## 6. Rollback

Der Plan enthält keine Destroys und keine Replacements. Vor einem Apply
müssen aktuelle Lambda-Code-Hashes und Environment-Werte als Rollback-
Referenz dokumentiert werden.

Rollback nach einem Apply:

1. Feature-Commit `a0f16a8` nicht weiterverwenden.
2. Einen neuen Plan aus dem vorherigen Stand erstellen.
3. Lambda-/Environment-Werte daraus wiederherstellen.
4. Die neu angelegte Erasure-Route nur über einen separaten, ausdrücklich
   freigegebenen Plan entfernen; kein State-Remove/Import.
5. Kein `-target`, kein State-Push, kein manuelles State-Editieren.

## 7. Plan-Organisation

Aktiv:

```text
/tmp/opencode/ris-consent-pilot-06.tfplan
SHA-256: e62370c0536af74b630a810585d95b12fba637a79ba428a13447b01ec07d1b68
```

SUPERSEDED:

```text
/tmp/opencode/ris-erasure-recovery-02.tfplan   (e9bc7157…)
/tmp/opencode/ris-consent-recovery-03.tfplan   (153d1212…)
```

Es wurde noch kein Apply ausgeführt. State-ETag und LastModified sind
unverändert.

Apply nur aus dem vorbereiteten Worktree mit dem aus dem gepinnten
Mays-Orders-Builder erzeugten `terraform/modules/mays_orders`; nicht aus
einem frischen Checkout ohne generiertes Modul.

## 8. Grenzen

- Nur bestehender Limited-Beta-Pilot; keine allgemeine Produktionsfreigabe.
- Keine neuen Testidentitäten.
- Keine Cognito-/CloudFront-/DNS-Änderungen.
- Kein Apply, Deployment oder Main-Merge.
- Keine echten Benutzerdaten verändert.
