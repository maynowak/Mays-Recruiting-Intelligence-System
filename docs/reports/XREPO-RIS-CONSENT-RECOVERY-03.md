# XREPO-RIS-CONSENT-RECOVERY-03

**Status:** `D — FIX MERGED / DEPLOYMENT PLAN TECHNICALLY CLEAN / APPLY NOT SAFE FOR COMPLETE CONSENT GATES`  
**Scope:** RIS Consent-Fix, Merge, Deployment-Plan und Vorbereitung des einmaligen
XRepo-Live-E2E  
**No Terraform Apply, no new Production deployment, no Cognito/CloudFront/DNS
change, no new test identity, no real applicant data.**

## 1. Ergebnis

1. RIS PR #15 wurde auf Umfang, Sicherheit und Mergefähigkeit geprüft.
2. Die Proof-Persistenz und die getrennten Zwecke `cv-storage` /
   `search-profile-storage` wurden auf dem gemergten Main verifiziert.
3. PR #15 wurde regulär nach Main gemergt.
4. Ein exakter Terraform-Plan gegen den aktuellen `ris-dev`-State wurde
   erstellt. Es wurde **kein Apply** ausgeführt.
5. Der Plan ist technisch unbedenklich (`0 add / 5 change / 0 destroy`), aber
   die vorhandenen Consent-Gates werden durch den aktuellen Terraform-Main
   **nicht aktiviert**. Deshalb ist der Apply als vollständiger
   Consent-Gate-Release derzeit **nicht freizugeben**.

## 2. PR-Review und Merge

| Punkt | Wert |
|---|---|
| Repository | `maynowak/Mays-Recruiting-Intelligence-System` |
| PR | #15 |
| Feature-Head | `fd02722dde89b30782da10ead3bfa175f7e85aa0` |
| Base | `b193b71` |
| Merge-SHA | `e95fe48573cb61151a84f448e9e6376f4a7833d6` |
| Merge-Art | regulärer Merge, kein Squash/Rebase, Branch nicht gelöscht |
| Merge-Status | `CLEAN` / `MERGEABLE`; keine automatischen CI-Checks gemeldet |

Scope des PR:

- `jobsearch/consent_contract.py`
- `jobsearch/consent_repository.py`
- `lambda/handler.py`
- 7 Consent-/Profile-Testdateien

Keine Terraform-, AWS-, Cognito-, CloudFront-, DNS- oder
Deployment-Änderung im PR.

### Proof-Persistenz

Der gemergte Code validiert und speichert:

- `specialCategoriesConsent`
- `specialCategories` in kanonischer Reihenfolge
- `externalTextVersion`
- `externalTextSha256`

`get()`/Status und History geben die Werte wieder aus. Der Handler reicht die
vier serverseitig validierten Felder an das Repository weiter. Tests decken
Grant, Reload/GET, Withdraw/Regrant, Idempotenz und `RECONSENT_REQUIRED` ab.

Verifikation auf dem gemergten Main `e95fe48`:

```text
RIS fokussiert (Proof, CV, Search, Profile): 77 PASS
RIS vollständig: 2823 PASS / 104 skipped / 19 identische Baseline-Fehler
Clean-Main-Baseline b193b71: 2746 PASS / 104 skipped / 19 identische Fehler
```

Die 19 Restfehler sind unverändert gegenüber Clean-Main (Wrapper-/Terraform-,
Composite-, Health-, Packaging- und Platform-Handler-Tests); der Fix führt
keine neuen Fehler ein.

## 3. Notice-/Textfreigaben

| Zweck | Notice | Textversion | SHA-256 | Freigabe |
|---|---|---|---|---|
| `application-storage` | `1.0`, `APPROVED` | `application-storage-consent-2026-11-07-v4` | `8722aed9…43c7` | `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` |
| `cv-storage` | `1.0`, `APPROVED` | `cv-storage-consent-2026-11-08-v1` | `2fe65fd1…d036` | `JM-CV-STORAGE-V1-BETA-2026-11-08` |
| `search-profile-storage` | `1.0`, `APPROVED` | `search-profile-storage-consent-2026-11-08-v2` | `75919c8b…ef6` | `JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08` |

Bewertung:

- Die Texte sind vollständig, versioniert und den jeweiligen Notices
  zugeordnet; die Hashes stimmen mit den Jobsearch-Textmodulen überein.
- CV- und Search-Freigaben sind ausdrücklich **Operator-Freigaben für den
  begrenzten Pilot**; eine allgemeine Legal-/Produktionsfreigabe ist daraus
  nicht ableitbar.
- Es wurden keine neuen Freigaben, Ref-IDs oder Textversionen erfunden.
- ApplicationV1 bleibt unverändert die bestehende v4-Limited-Beta-Freigabe.

## 4. Terraform-Plan

AWS-/State-Kontext (read-only geprüft):

```text
Profil:       mayaws
Account:      240571105849
Region:       eu-central-1
Workspace:    ris-dev
State:        mays-ris-tf-state-dev, env:/ris-dev/dev/terraform.tfstate
Serial:       80
Lineage:      9cec61e5-c036-1ad5-6ae4-8b48a50122a4
Resources:    271
State-ETag:   "abdb644e5d61cd023aefc294afb5df8d" (nach Plan; kein State-Write)
```

Der State wurde durch `state pull`/Plan nur gelesen; `LastModified` blieb beim
Release-05-Zeitpunkt `2026-11-17T13:35:44Z`.

Plan-Artefakt:

```text
/tmp/opencode/ris-consent-recovery-03.tfplan
SHA-256: 153d121260bf5340a63b4d091abe5541732e853891db2f00f6d8b1694baf312c
```

Ergebnis:

```text
0 Add
5 Change
0 Destroy
0 Replace
```

Reproduktion: Der Plan verwendet den gepinnten Mays-Orders-Builder
`122ec65ac7ab5a044d2b2576ae6b7e4c325246b8` sowie die unveränderten
Health-/Reader-Bundles mit den oben genannten Hashes. Die lokale
Plan-Variablendatei enthält keine Secrets und wird nicht committet.

### Änderungen

| Ressource | Änderung |
|---|---|
| `module.lambda.aws_lambda_function.agent` | Lambda-Code `cQFmaERV…` → `RZDUre/S…`; enthält PR-#15-Consent-Fix |
| `module.agent_transport[0].aws_lambda_function.dispatch_ingress` | gleicher Agent-Bundle-Code |
| `module.health_plane.aws_lambda_function.health_writer` | nur Pfad-/`filename`-Metadaten; Health-Bundle unverändert |
| `module.health_plane.aws_lambda_function.health_publisher` | nur Pfad-/`filename`-Metadaten; Health-Bundle unverändert |
| `module.orders_reader[0].aws_lambda_function.reader` | nur Pfad-/`filename`-Metadaten; Reader-Bundle unverändert (`e4058587…`) |

Keine Änderung an:

- IAM-Policies oder Rollen
- Cognito, API Gateway, CloudFront, DNS, ACM
- DynamoDB, S3, SQS, Secrets
- Lambda-Umgebungsvariablen (keine entfernten oder hinzugefügten Keys im Agent)
- Consent-Enforcement oder Pilot-Allowlist

Das Agent-Bundle enthält nachweislich:

```text
application-storage/1.0 = APPROVED
cv-storage/1.0          = APPROVED
search-profile-storage/1.0 = APPROVED
specialCategoriesConsent / externalTextVersion / externalTextSha256
```

## 5. Release-Blocker: Gates nicht verdrahtet

Der aktuelle Terraform-Main verdrahtet nur:

```text
APPLICATION_CONSENT_ENFORCED
CONSENTS_TABLE
```

Nicht vorhanden sind im Terraform-Main:

```text
CV_STORAGE_CONSENT_ENFORCED
SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED
CONSENT_NOTICE_STATE_ENFORCED
CONSENT_PILOT_ALLOWLIST
```

Der Live-State enthält diese Variablen ebenfalls nicht; der Plan fügt sie
deshalb nicht hinzu. Die neue Lambda liest die Gates fail-closed, aber ohne
Environment-Wiring bleiben die Gates faktisch **inaktiv**.

Damit gilt:

- Der Plan ist technisch sicher und rückrollbar (nur Lambda-Updates; keine
  Zerstörung).
- Er stellt die CV-/Search-Consent-APIs und die persistierten Proof-Felder
  wieder her.
- Er aktiviert aber **nicht** die serverseitige CV-/Search-Gate-Durchsetzung
  und nicht die Pilot-Allowlist.
- Für einen vollständigen Consent-Gate-Release ist eine separate,
  ausdrücklich freigegebene Terraform-Wiring-/Aktivierungsänderung nötig.
- Es wurde nichts abgeschwächt: Die aktuellen Gates sind bereits nicht
  aktiv; der Plan fügt keine Abschwächung hinzu.

**Entscheidung:** `NO APPLY` für einen vollständigen Consent-Gate-Release.
Ein technisch begrenzter Lambda-Apply wäre möglich, wird aber ohne separate
Gate-Aktivierungsfreigabe nicht empfohlen und hier nicht ausgeführt.

## 6. Live-E2E-Planung

Die vorhandene autorisierte Pilot-Session bleibt für den einmaligen E2E
vorgesehen. Es wird keine neue Testidentität angelegt und keine realen
Bewerberdaten verwendet.

Nach einer separat freigegebenen Apply-/Aktivierungsrunde:

1. ApplicationV1: Withdraw, Art.-9-Checkbox, Regrant, Reload.
   Erwartung: `specialCategoriesConsent=true`, `externalTextVersion`
   `application-storage-consent-2026-11-07-v4`, Hash `8722aed9…`.
2. CV: Grant, synthetische PDF, Upload, Reload, Download, Cleanup/404.
3. Search-Profile: Grant/Withdraw/Regrant gegen den getrennten Zweck; keine
   Vermischung mit CV.
4. Alle synthetischen Datensätze löschen; keine echten Bewerberdaten.

Der Live-E2E wurde **nicht** ausgeführt, weil kein Apply und keine
Gate-Aktivierung freigegeben wurden.

## 7. Jobsearch

Kein Jobsearch-Produktcode geändert. Die vorhandene BFF-/Consent-/UI-Lib-
Prüfung bleibt grün:

```text
Jobsearch BFF/Consent/UI-Libs: 53 PASS
```

Production bleibt `92ca1fc`; keine neue Jobsearch-Deployment-Aktion.

## 8. Freigaben / nächste Schritte

1. Review des Plans `153d1212…` und Entscheidung über den Lambda-only-Umfang.
2. Separates Terraform-Wiring für die vier fehlenden Consent-Variablen
   vorbereiten und freigeben, falls die Gates aktiv sein sollen.
3. Danach neuen Plan erstellen (nicht diesen Plan wiederverwenden), SHA
   dokumentieren und explizit `GO APPLY` erteilen.
4. Erst danach den geplanten Live-E2E mit der bestehenden Pilot-Session
   ausführen.

Kein Terraform Apply, kein Deployment, keine State-Manipulation, kein
`-target`, keine Cognito-/CloudFront-/DNS-Änderung.
