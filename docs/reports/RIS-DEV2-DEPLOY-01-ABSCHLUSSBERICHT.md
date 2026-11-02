# RIS-DEV2-DEPLOY-01 — Abschlussbericht

**Stand:** 2026-11-02  
**Status:** DEPLOYED / FOUNDATION VERIFIED (gemäß übermitteltem Ausführungsbericht)  
**Quelle:** `docs/reports/RIS-DEV2-DEPLOY-01-EXECUTION.md`, Abschluss-Commit `35800ed0dec86fb0c2c05835ecf1e184436bf596`  
**Evidenzgrad:** Vom ausführenden Entwicklungsagenten berichtet; keine unabhängige AWS-Abfrage durch diesen Bericht.

## 1. Ziel und Abgrenzung

Kontrollierte Bereitstellung einer eigenständigen RIS-Foundation in `ris-dev2`, ohne bestehende Cognito-, Jobsearch-, CloudFront-, DNS-, ACM- und OAuth-Ressourcen zu verändern. Die neue, ausschließlich für den öffentlichen RIS-Health-Endpunkt vorgesehene CloudFront-Distribution war im Plan ausdrücklich als Create-Ausnahme erlaubt. Der Vorgang ist ein **Foundation-Bootstrap**, kein Nachweis eines In-Place-Upgrades auf einer bereits betriebenen RIS-Foundation.

## 2. Zielumgebung

| Parameter | Wert |
|---|---|
| Projekt/Workspace | `ris-dev2` |
| AWS-Account | `262370457690` |
| AWS-Profil | `default` |
| Region | `eu-central-1` |
| Terraform-Version beim Plan | `1.17.0` |
| Terraform-State vor Apply | Serial `17`, 0 Ressourcen |
| Terraform-State nach Apply | Serial `23`, Lineage unverändert (gemeldet) |
| State-Lineage vor Apply | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| API-Basis-URL | `https://8apxb6fgne.execute-api.eu-central-1.amazonaws.com` |
| Health-CloudFront-ID | `E1IZKHFPZ5X7SN` |
| Abschluss-Commit | `35800ed0dec86fb0c2c05835ecf1e184436bf596` |

## 3. Plan, Freigabe und Durchführung

Der gespeicherte und geprüfte R1-Plan lautete:

- Datei: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-foundation-r1.tfplan`
- SHA-256: `FC30B406F16DB860203539D079730B8B9A27A4A359505B8430AAF0A9F40F431D`
- Plan: **153 Create, 0 Update, 0 Delete, 0 Replace, 3 Read**.
- Ergebnis nach freigegebenem Apply: **153 added, 0 changed, 0 destroyed**.

Im Plan wurden exakt zwei neue CloudFront-bezogene Ressourcen zugelassen:

1. `module.health_public.aws_cloudfront_distribution.health_public`
2. `module.health_public.aws_cloudfront_origin_access_control.health_public`

Beide ausschließlich als **Create**; Health-Origin `S3-health-public`, keine bestehenden Domain-Aliase, kein ACM-Zertifikat, keine Route53-Records, OAC SigV4 und S3 Public Access Block. Eine allgemeine CloudFront-Änderungsfreigabe wurde nicht erteilt.

## 4. Verifikation nach Apply

| Prüfung | Berichtetes Ergebnis | Aussagegrenze |
|---|---|---|
| Terraform Apply | PASS — 153 added / 0 changed / 0 destroyed | Keine Änderungen an zuvor verwalteten Ressourcen im Apply |
| Lambda | Active, Python 3.14, Update Successful | Laufzeit-/Deploy-Status; kein umfassender Funktionstest |
| Öffentlicher Health-Endpunkt | HTTP 200 | Health-Ressource erreichbar |
| API `/health` ohne JWT | HTTP 401 (erwartet) | Auth-Grenze aktiv; kein vollständiger Login-E2E |
| Human-/M2M-Authorizer | Externer Issuer und Audiences verifiziert | Konfiguration bestätigt; kein produktiver Token-Flow belegt |
| Privacy-/Erasure-Flags | Alle `false` | Keine Aktivierung der geplanten Privacy-/Erasure-Abläufe |
| Cognito-/DNS-/ACM-Ressourcen | Unverändert; keine `ris-dev2` Cognito-Pools erstellt | Gemäß Report und Plan-/Nachprüfung |
| Terraform-State | Serial 23; Lineage erhalten | Weiterhin bestehender State, jetzt mit Foundation-Ressourcen |

## 5. Vorgeschichte und Qualitätssicherung

- G2C-6 implementierte `identity_mode=managed|external` und `orders_lifecycle=managed|external|disabled`.
- G2C-7 stellte offline die Modulauflösung und Installer-Regression wieder her; Installer/Runner/Pinning: **95 passed**, direkter gepinnter Builder: PASS; historischer breiter Wrapper-Test: Timeout, **nicht PASS**.
- G2C-7D bestätigte das Konto `262370457690` und bereitete den geschützten Bootstrap-Vertrag vor.
- G2C-7D-2B implementierte `external_cognito_account_id` und Cross-Account-Vertragsvalidierung. Die referenzierte externe Identity wird **nicht von `ris-dev2` verwaltet**.
- R1-Plan-Guard und relevante Regressionen: **24 passed**; Python `py_compile` und `git diff --check`: PASS.
- Vor Apply waren Orders-Builder, Lambda-Bundles, Terraform `init` und `validate` PASS; im vorherigen regulären Schritt außerdem 19 relevante Tests PASS.

## 6. Infrastruktur- und Ownership-Regeln

**Geschützt und unverändert:** Bestehende Cognito User Pools, Benutzer, Human-/M2M-App-Clients, OAuth-Domains, Jobsearch-CloudFront-/DNS-/ACM-Ressourcen. Die `ris-dev2`-Foundation darf diese Ressourcen nicht importieren, ersetzen oder verändern.

**Von `ris-dev2` neu erstellt:** Die 153 genehmigten Foundation-Ressourcen, einschließlich einer *eigenen* Health-CloudFront-Distribution samt OAC. Die neue Health-Distribution ist kein Ersatz für die bestehende Auth-/Jobsearch-Distribution.

## 7. Git- und Artefaktschutz

- Bericht im Repository: `docs/reports/RIS-DEV2-DEPLOY-01-EXECUTION.md`.
- Abschluss-Commit: `35800ed0dec86fb0c2c05835ecf1e184436bf596`.
- Die **39 ursprünglich untracked Dateien** wurden erhalten.
- Die vorbestehende Löschung `terraform/modules/mays_orders/variables.tf` wurde erhalten.
- Keine Bereinigung fremder Arbeitsdateien, kein Push/Merge im dokumentierten Verlauf.

## 8. Restpunkte und nächste Nachweise

1. **No-op-Drift-Prüfung** auf der installierten `ris-dev2`-Foundation mit passender State-/Account-Identität. Eine solche Prüfung ist bislang noch nicht belegt.
2. **In-Place-Upgrade-Nachweis:** Gezielte RIS-Backend-Änderung planen und anwenden, während Cognito, Auth-CloudFront, DNS und ACM unverändert bleiben. Das erfolgreiche Erst-Deployment allein belegt diesen Upgrade-Fall nicht.
3. **Authentifizierter E2E-Test:** Ein 401 ohne JWT bestätigt die Sperre, nicht den vollständigen Human- oder M2M-Login-Flow.
4. **Historischer Wrapper-Timeout** bleibt als separater Regressionseintrag offen.
5. **Bestehende generierte Modul-/Working-Tree-Besonderheiten** beim nächsten Build berücksichtigen; nicht pauschal bereinigen.
6. **Nachlaufende Kosten/Monitoring/Alarme** der 153 Ressourcen prüfen, sofern noch nicht dokumentiert.

## 9. Abschlussurteil

**FOUNDATION DEPLOYED — GO.** Die kontrollierte Neuinstallation von `ris-dev2` gelang dem gemeldeten Apply zufolge mit 153 neuen Ressourcen, ohne Updates oder Löschungen. Health und Basisauthentifizierung reagierten erwartungsgemäß; geschützte Cognito-/DNS-/ACM-Ressourcen wurden laut Abschlussbericht nicht verändert. **IN-PLACE UPGRADE VERIFIED — NO**, da ein späteres Upgrade einer bereits vorhandenen Foundation noch nicht durchgeführt wurde.
