# RIS-ERASURE-RECOVERY-02

**Status:** `PLAN READY — NO APPLY`  
**Scope:** Wiederherstellung der Partner-Erasure-Route und gemeinsamer
Consent-/Erasure-Deployment-Plan  
**No Terraform Apply, State-Import, State-Remove, Deployment, Cognito/
CloudFront/DNS change or real user data change.**

## 1. Ergebnis

Die gelöschte Partner-Route ist in der Terraform-Konfiguration wieder
enthalten, der bestehende Handler-Pfad ist wieder erreichbar, und ein neuer
Plan wurde erstellt:

```text
/tmp/opencode/ris-erasure-recovery-02.tfplan
SHA-256: e9bc7157b451287248bc08fb2035e52249cbf94aaff4539c5a267cada9988822
```

Plan gegen State-Serial 80:

```text
1 Add / 5 Change / 0 Destroy / 0 Replace
```

Der einzige neue AWS-Ressourceneintrag ist:

```text
module.jobsearch_edge[0].aws_apigatewayv2_route.partner["POST /v1/partner/me/erasure"]
API:            c7e9pdwe78
Authorizer:     e6inno
Target:         integrations/anl98ns
Authorization:  JWT
```

## 2. Änderungen

### Terraform

`terraform/modules/partner_edge/main.tf` enthält wieder:

```text
POST /v1/partner/me/erasure
```

Es wurde keine neue Integration, kein neuer Authorizer und keine neue IAM-
Policy angelegt. Die Route verwendet die bestehende Partner-API,
JWT-Authorizer und Lambda-Integration.

### Handler

`lambda/handler.py` dispatcht `POST /v1/partner/me/erasure` über den
bestehenden Partner-Kontext und die bestehende Kernel-Erasure:

```text
_partner_profile_context(event)
  -> _handle_me_erasure(event, context)
```

Es wurde keine zweite Löscharchitektur und kein neues Löschverfahren
eingeführt. Die Route verwendet die vorhandene `PrivacyErasure`-Lifecycle-
Funktion.

### Tests

Neu/angepasst:

- `tests/test_partner_erasure_route.py`: Dispatch und Kontext-Denial.
- `tests/test_partner_surface_gate.py`: Erasure-Route bleibt bei
  `PARTNER_SURFACE_ENABLED=false` geschlossen.
- `tests/test_p20_api_contract_consistency.py`: unveränderter bestehender
  Route-Inventarvertrag; die Partner-Edge-Route wird im dedizierten Test
  geprüft.

Ergebnisse:

```text
Fokussiert Route/Privacy: 46 PASS / 318 Subtests
Fokussiert Erasure/Consent: 143 PASS / 318 Subtests
Vollständige RIS-Suite: 2827 PASS / 104 skipped / 18 bekannte Baseline-Fehler
terraform fmt -check: PASS
terraform validate: PASS
```

Die 18 Restfehler sind die bekannten Wrapper-/Terraform-/Composite-/Health-/
Platform-Baseline-Fehler; keine neuen Fehler durch diese Änderung.

## 3. Consent-Fix

Der Plan enthält weiterhin den gemergten Consent-Fix aus PR #15:

- ApplicationV1 Art.-9-/Text-Proof
- `cv-storage` und `search-profile-storage` als getrennte Zwecke
- bestehende CV-/Search-Consent-Gates im Lambda-Code

Es wurden **keine neuen rechtlichen Freigaben** erzeugt und **keine
Consent-Gates aktiviert**. Die bestehenden Freigaben bleiben auf den
begrenzten Pilot beschränkt.

Der Terraform-Main verdrahtet weiterhin nicht:

```text
CV_STORAGE_CONSENT_ENFORCED
SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED
CONSENT_NOTICE_STATE_ENFORCED
CONSENT_PILOT_ALLOWLIST
```

Der Plan fügt keine dieser Variablen hinzu und ändert keine Lambda-
Environment-Keys. Damit bleibt die serverseitige Gate-Aktivierung ein
separater Freigabeschritt.

## 4. Vollständiger Ressourcendiff

| Adresse | Aktion |
|---|---|
| `module.jobsearch_edge[0].aws_apigatewayv2_route.partner["POST /v1/partner/me/erasure"]` | **create** |
| `module.lambda.aws_lambda_function.agent` | update (Consent-/Erasure-Bundle) |
| `module.agent_transport[0].aws_lambda_function.dispatch_ingress` | update (gleicher Agent-Bundle-Code) |
| `module.orders_reader[0].aws_lambda_function.reader` | update (Pfad/Artefakt) |
| `module.health_plane.aws_lambda_function.health_writer` | update (nur Pfad/Artefakt) |
| `module.health_plane.aws_lambda_function.health_publisher` | update (nur Pfad/Artefakt) |

Keine Änderung an IAM, Cognito, API Gateway außer der neuen Route,
CloudFront, DNS, DynamoDB, SQS, S3, Secrets oder Lambda-Environment-Keys.
Kein Destroy, kein Replace.

## 5. State

```text
Bucket:      mays-ris-tf-state-dev
Key:         env:/ris-dev/dev/terraform.tfstate
Workspace:   ris-dev
Serial:      80
Lineage:     9cec61e5-c036-1ad5-6ae4-8b48a50122a4
Resources:   271 Blöcke / 311 Instanzen
State-ETag:  "abdb644e5d61cd023aefc294afb5df8d" (unverändert)
```

Der State wurde nicht geschrieben. Der Plan ist an Serial 80 gebunden.

## 6. Alter Plan

Der bisherige Plan:

```text
/tmp/opencode/ris-consent-recovery-03.tfplan
SHA-256: 153d121260bf5340a63b4d091abe5541732e853891db2f00f6d8b1694baf312c
```

ist **SUPERSEDED**. Er enthält keine Wiederherstellung der gelöschten Route
und darf nicht angewendet werden.

Der neue aktive Plan ist:

```text
/tmp/opencode/ris-erasure-recovery-02.tfplan
SHA-256: e9bc7157b451287248bc08fb2035e52249cbf94aaff4539c5a267cada9988822
```

## 7. Freigabe / nächster Schritt

Vor einem Apply sind erforderlich:

1. Review des Feature-Branches `feature/ris-erasure-recovery-02`
   (`70a9fb9`).
2. Prüfung des neuen Plans `e9bc7157…` und seiner 1/5/0-Bilanz.
3. Entscheidung über die separate Consent-Gate-Aktivierung; sie ist in
   diesem Plan nicht enthalten.
4. Ausdrückliches `GO APPLY`; kein Apply in dieser Runde.

Danach kann die Partner-Erasure-Route live geprüft werden, ohne echte
Benutzerdaten zu verändern.

Kein Terraform Apply, kein State-Push, kein Import, kein Remove, kein
Deployment.
