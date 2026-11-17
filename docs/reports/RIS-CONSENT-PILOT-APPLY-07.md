# RIS-CONSENT-PILOT-APPLY-07

**Status:** `PREPARED — AWAITING EXPLICIT GO APPLY`  
**Scope:** Controlled apply of the existing Limited-Beta-Pilot plan  
**No Apply, Deployment, Main-Merge, State mutation or real user data change.**

## 1. Freigabegegenstand

```text
Plan:        /tmp/opencode/ris-consent-pilot-06.tfplan
SHA-256:     e62370c0536af74b630a810585d95b12fba637a79ba428a13447b01ec07d1b68
State:       ris-dev
Serial:      80
Lineage:     9cec61e5-c036-1ad5-6ae4-8b48a50122a4
Resources:   271 Blöcke / 311 Instanzen
State-ETag:  "abdb644e5d61cd023aefc294afb5df8d"
```

## 2. Planprüfung

```text
1 Add / 5 Change / 0 Destroy / 0 Replace
```

**Add:**

```text
module.jobsearch_edge[0].aws_apigatewayv2_route.partner["POST /v1/partner/me/erasure"]
API: c7e9pdwe78 / Authorizer: e6inno / Target: integrations/anl98ns
```

**Change:**

- Agent-Lambda: neuer Code-Hash; `APPLICATION_CONSENT_ENFORCED=false` → `true`;
  vier Consent-Environment-Keys werden hinzugefügt.
- Dispatch-Ingress: gleicher Agent-Bundle-Code.
- Orders-Reader, Health-Writer, Health-Publisher: nur Artefaktpfade.
- Keine entfernten Environment-Keys.
- Keine IAM-, Cognito-, CloudFront-, DNS-, DynamoDB-, SQS-, S3- oder
  Secrets-Änderung.
- Kein Destroy/Replace.

## 3. Pilotfreigaben

Notices sind unverändert und für den begrenzten Pilot freigegeben:

```text
application-storage/1.0        JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08
cv-storage/1.0                 JM-CV-STORAGE-V1-BETA-2026-11-08
search-profile-storage/1.0     JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08
```

Die Plan-Allowlist stimmt mit der bestehenden Pilot-Allowlist überein
(`2` bestehende Einträge); es wurden keine Identitäten ergänzt. Die Werte
werden nicht in diesem Report ausgegeben.

## 4. Gates im Plan

```text
APPLICATION_CONSENT_ENFORCED            false -> true
CV_STORAGE_CONSENT_ENFORCED             (new) -> true
SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED (new) -> true
CONSENT_NOTICE_STATE_ENFORCED           (new) -> true
CONSENT_PILOT_ALLOWLIST                 (new) -> bestehende Allowlist
```

Damit ist die serverseitige Consent-Prüfung für alle drei Speicherzwecke
konsistent aktiviert. Nicht gelistete CV-/Search-Identitäten werden
fail-closed behandelt; ApplicationV1 wird global geprüft.

## 5. Noch nicht ausgeführt

- Kein Terraform Apply.
- Kein Post-Apply-Plan.
- Keine Live-Verifikation der Erasure-Route.
- Kein XRepo-Live-E2E.
- Keine Datenänderung.

Der State ist unverändert; ETag und LastModified blieben gleich.

## 6. Apply-Gate

Der Apply darf **erst** nach ausdrücklicher Bestätigung ausgeführt werden:

```text
GO APPLY e62370c0536af74b630a810585d95b12fba637a79ba428a13447b01ec07d1b68
```

Nach GO wird exakt dieser gespeicherte Plan angewendet; kein neuer Plan,
kein `-target`, keine State-Manipulation.

## 7. Nach dem Apply geplant

1. Post-Apply-Plan auf `No changes` prüfen.
2. Erasure-Route live prüfen.
3. Consent-Gates für ApplicationV1, CV und Search verifizieren.
4. Einmaligen XRepo-E2E mit der vorhandenen autorisierten Pilot-Session
   durchführen:
   - Grant
   - Reload
   - Withdraw/Regrant
   - CV-Speicherung
   - PDF-Download
   - Suchprofil-Consent
5. Reports/Auditlogs in beiden Repositories aktualisieren.

## 8. Rollback

Der Plan enthält keine Destroys/Replacements. Vor dem Apply sind aktuelle
Lambda-Code-Hashes und Environment-Werte als Rollback-Referenz zu sichern.
Ein Rollback nach Apply erfolgt über einen neuen Plan; die Route wird nur
über einen separaten, freigegebenen Plan entfernt. Kein State-Push/Import.
