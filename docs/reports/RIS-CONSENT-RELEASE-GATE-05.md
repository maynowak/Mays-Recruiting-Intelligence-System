# RIS-CONSENT-RELEASE-GATE-05

**Status:** `BLOCKED — Plan technisch sauber, Consent-Gate-Aktivierung fehlt`  
**Recommendation:** `BLOCKED` für sicheren Live-Betrieb  
**No Apply, Deployment, Main-Merge, State-Import/Remove or real user data change.**

## 1. Planprüfung

Geprüfter Plan, unverändert:

```text
/tmp/opencode/ris-erasure-recovery-02.tfplan
SHA-256: e9bc7157b451287248bc08fb2035e52249cbf94aaff4539c5a267cada9988822
State-Serial: 80
Lineage: 9cec61e5-c036-1ad5-6ae4-8b48a50122a4
```

```text
1 Add / 5 Change / 0 Destroy / 0 Replace
```

Die erwartete Route ist der einzige Add:

```text
module.jobsearch_edge[0].aws_apigatewayv2_route.partner["POST /v1/partner/me/erasure"]
API:        c7e9pdwe78
Authorizer: e6inno
Target:     integrations/anl98ns
Auth:       JWT
```

## 2. Fünf Lambda-Änderungen

| Adresse | Änderung | Bewertung |
|---|---|---|
| `module.lambda...aws_lambda_function.agent` | `source_code_hash` `cQFmaERV…` → `UCdPXzMR…` | erwartetes Consent-/Erasure-Bundle |
| `module.agent_transport...dispatch_ingress` | gleicher neuer Agent-Bundle-Code | erwartet |
| `module.orders_reader...reader` | nur `filename`; Source-Hash `5AWFhxg…` unverändert | Artefaktpfad, kein Code |
| `module.health_plane...health_writer` | nur `filename` | Artefaktpfad, kein Code |
| `module.health_plane...health_publisher` | nur `filename` | Artefaktpfad, kein Code |

Geprüft:

- Keine entfernten oder hinzugefügten Lambda-Environment-Keys.
- Keine IAM-/Rollen-/Policy-Änderung.
- Keine Cognito-, CloudFront-, DNS-, DynamoDB-, SQS-, S3- oder Secrets-Änderung.
- Kein Destroy, kein Replace, keine unbekannte Ressource.

Damit ist der Plan **ressourcentechnisch GO-fähig**, aber noch kein
vollständiger Consent-Release.

## 3. Consent-Notice-Freigaben

| Zweck | Notice/Text | Freigabe |
|---|---|---|
| `application-storage` | `1.0` / `application-storage-consent-2026-11-07-v4` | `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` |
| `cv-storage` | `1.0` / `cv-storage-consent-2026-11-08-v1` | `JM-CV-STORAGE-V1-BETA-2026-11-08` |
| `search-profile-storage` | `1.0` / `search-profile-storage-consent-2026-11-08-v2` | `JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08` |

Die Texte und Hashes sind vollständig und konsistent. Die Freigaben sind
ausdrücklich **Operator-Freigaben für den begrenzten Pilot**; eine allgemeine
Legal-/Produktionsfreigabe ist daraus nicht ableitbar.

## 4. Terraform-Gates

Der aktuelle Terraform-Main verdrahtet weiterhin nicht:

```text
CV_STORAGE_CONSENT_ENFORCED
SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED
CONSENT_NOTICE_STATE_ENFORCED
CONSENT_PILOT_ALLOWLIST
```

Der Live-State enthält beim Agenten nur:

```text
APPLICATION_CONSENT_ENFORCED = "false"
```

Der geprüfte Plan fügt **keine** dieser Variablen und **keine**
Lambda-Environment-Keys hinzu. Die Gates bleiben daher inaktiv.

Es wurden keine fehlenden Freigaben erfunden und keine Gates abgeschwächt.
Eine Aktivierung ist ohne separate, nachweislich belastbare Freigabe und
separates Terraform-Wiring nicht zulässig.

## 5. Technische Prüfung

- Plan gegen State-Serial 80 gültig.
- State unverändert; ETag/LastModified unverändert.
- Agent-Bundle enthält:
  - `cv-storage/1.0`
  - `search-profile-storage/1.0`
  - Art.-9-/External-Text-Proof
  - Partner-Erasure-Dispatch
- Fokussierte Route-/Privacy-Tests: **46 PASS / 318 Subtests**
- Fokussierte Erasure-/Consent-Tests: **143 PASS / 318 Subtests**
- Vollständige RIS-Suite: **2827 PASS / 104 skipped / 18 bekannte
  Baseline-Fehler**
- `terraform fmt -check`: PASS
- `terraform validate`: PASS

## 6. Superseded-Plan

Der alte Consent-Plan ist bereits **SUPERSEDED**:

```text
/tmp/opencode/ris-consent-recovery-03.tfplan
SHA-256: 153d121260bf5340a63b4d091abe5541732e853891db2f00f6d8b1694baf312c
```

Es wurde **kein neuer Plan** erstellt, weil in dieser Prüfung weder Code
noch Terraform geändert wurden.

## 7. Empfehlung

**BLOCKED** für einen sicheren Live-Consent-Betrieb.

Konkrete Ursache:

1. CV-/Search-/Notice-/Pilot-Gates sind im Terraform-Main und im Live-State
   nicht verdrahtet.
2. Der Plan aktiviert diese Gates nicht.
3. Es liegt nur eine begrenzte Pilotfreigabe vor; eine allgemeine
   Legal-Freigabe ist nicht nachgewiesen.
4. Eine eigenmächtige Gate-Aktivierung ist daher untersagt.

Der Plan kann nach separater Entscheidung für einen **begrenzten
Code-/Routen-Apply** verwendet werden. Für einen vollständigen
Consent-Gate-Release bleibt er blockiert.

Kein Apply, kein Deployment, kein Main-Merge.
