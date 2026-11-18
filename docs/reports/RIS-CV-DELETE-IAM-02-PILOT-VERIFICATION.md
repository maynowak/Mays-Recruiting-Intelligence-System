# RIS-CV-DELETE-IAM-02 — CONTROLLED APPLY & PILOT VERIFICATION

**Status:** `PILOT LIVE VERIFIED — CV CREATE / DOWNLOAD / DELETE`  
**Target:** `ris-dev` limited pilot  
**Frontend dependency:** Jobsearch `feature/jm-cv-ux-07-persistence-delete-editor-return` (`0d1a17f`)  
**No extra Infrastructure apply, no Main merge, no Jobsearch product change.**

## 1. Apply

Freigegebener Plan:

```text
Plan:        /tmp/opencode/ris-cv-delete-iam-01.tfplan
SHA-256:     754770b44e4f63d386f962a12e6701e04e3b1c94a53cbc3d2858b9e871afbf5d
State vor:   82
State nach:  83
Lineage:     9cec61e5-c036-1ad5-6ae4-8b48a50122a4
```

Apply-Ergebnis:

```text
0 added / 1 changed / 0 destroyed
```

Einzige Änderung:

```text
module.lambda.aws_iam_role_policy.lambda_dynamodb_partner_profiles
+ dynamodb:ConditionCheckItem
```

Keine neuen Ressourcen, Rollen, Tabellen, Lambdas, Cognito-/CloudFront-/DNS-
Änderungen oder Jobsearch-Änderungen.

## 2. Post-Apply

IAM-Policy der Rolle `ris-dev-dev-agent` enthält jetzt:

```text
dynamodb:PutItem
dynamodb:GetItem
dynamodb:Query
dynamodb:DeleteItem
dynamodb:UpdateItem
dynamodb:TransactWriteItems
dynamodb:ConditionCheckItem
```

IAM-Simulation:

```text
dynamodb:ConditionCheckItem
auf ris-dev-dev-partner-profiles
= allowed
```

Post-Apply-Plan:

```text
No changes.
/tmp/opencode/ris-cv-delete-iam-01-post.tfplan
SHA-256: bd6640add39bba92032b4a7f9497af35b59518342e144ea691e6206f54a64b2b
```

State-ETag nach Apply: `"254bafab2fcecc8c58905e86d9585634"`.

## 3. Synthetic CV E2E

Ausgeführt mit der vorhandenen autorisierten Production-Session. Keine
Tokens oder echten Benutzerdaten protokolliert.

Getestete Schritte:

```text
alter synthetischer Rest    DELETE 200, deleted=true
neuer synthetischer CV      POST 201
Upload-Ticket               POST 200
S3 Upload                   PUT 200
Complete                    POST 200, processingStatus=ready
Liste vor Delete            CV gefunden
Download                    GET 200, 13.569 Bytes, %PDF
Delete                      DELETE 200, deleted=true
Liste nach Delete           CV nicht mehr gefunden
GET nach Delete             HTTP 404, code=not_found
Document nach Delete        HTTP 404, code=not_found
```

Delete-Antwort für PDF und Metadaten:

```text
documentId:     7db047b6701c49a5
existed:        true
deleted:        true
deleteMarker:   true
physicalPurge:  false
```

Damit ist das S3-Objekt über einen Delete-Marker entfernt und nicht mehr
abrufbar; eine physische Purge/Version-Löschung wird nicht behauptet.
Die Metadatenzeile ist aus der Liste verschwunden und der Detail-/Download-
Endpunkt liefert 404.

Nur die zwei synthetischen IDs wurden angefasst:

```text
72a2c3c7155144fcbef376d8f5c5f6d4  (alter synthetischer Rest)
6759db8f11584939b32ac1919aa9f5dc  (neuer synthetischer CV)
```

Keine anderen CVs wurden gelöscht.

## 4. Tests

```text
Fokussiert IAM/Consent/Profile: 46 PASS
Vollständige RIS-Suite:         2829 PASS / 104 skipped / 18 Baseline-Fehler
terraform fmt -check:           PASS
terraform validate:             PASS
Live CV Delete E2E:             PASS
```

Keine zusätzlichen Consent-Regressionstests in diesem Auftrag.

## 5. Git

- RIS IAM-Commit: `773d212`
- RIS Preflight-Docs: `73f9fbf`
- Jobsearch Frontend-Fix: `0d1a17f` (separater Branch, nicht Production-deployed)
- Kein Main-Merge, kein weiteres Deployment.
- Keine Änderung an Jobsearch-Produktcode in diesem RIS-Auftrag.

## 6. Datenschutz / Grenzen

- Nur synthetische CV-Daten.
- Keine echten Benutzer-CVs gelöscht.
- Keine Tokens oder Accountdaten in Report/Screenshots.
- Keine Änderung an RIS-Auth, Cognito, CloudFront, Terraform außer dem
  freigegebenen IAM-Diff.
- Keine automatische Kaskadenlöschung.

## 7. Ergebnis

```text
PILOT LIVE VERIFIED — CV CREATE / DOWNLOAD / DELETE
```
