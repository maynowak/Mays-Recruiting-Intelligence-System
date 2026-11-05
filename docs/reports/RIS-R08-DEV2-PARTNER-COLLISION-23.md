# RIS-R08-DEV2-PARTNER-COLLISION-23

## Status

**COLLISION RESOLVED — REAL GATEWAY/JWT E2E PASS — FLOAT-INPUT DEFECT FOUND**

Die historische Client-Kollision wurde nach separater Freigabe atomar
bereinigt. Danach wurden ein neuer synthetischer Partner, ein aktives
APIProfile und ein temporäres Credential provisioniert. Mit genau einem
temporären Cognito-Benutzer und einem echten Access-JWT lief die vollständige
HTTP-Testmatrix erfolgreich, einschließlich Patch mit korrekter Version.

Kein Terraform-Apply, kein Lambda-Deployment, keine Cognito-Konfigurations-
änderung und keine `ris-dev`-Änderung in diesem Schritt.

## A — Kollisionsanalyse (read-only)

Drei Registry-Items in `ris-dev2-dev-partner-applications`:

| Key | Tenant | Client | APIProfile | Status |
|---|---|---|---|---|
| `partner-r08-20` | `ris-dev2-e2e-20261105` | `21j28p71vogg0m41tcue0ib3l4` | `aprof_21794823992c4faf` | `INACTIVE` |
| `partner-r08-22` | `ris-dev2-e2e-20261105` | `21j28p71vogg0m41tcue0ib3l4` | `aprof_beb47092354b4d4d` | `INACTIVE` |
| `CLIENT#21j28p71vogg0m41tcue0ib3l4` | — | `21j28p71vogg0m41tcue0ib3l4` | — | `RESERVED` für `partner-r08-22` |

Beide Profile und beide Credentials waren `REVOKED`. Applications,
User-Profile, Partner-Profile, Entitlements und Offers waren **0**. Cognito
hatte **0 Benutzer**. `resolve_partner_application()` lieferte weiterhin
`partner-r08-20` (`INACTIVE`) und damit 403.

## B — Bereinigte Kollision

Nach ausdrücklicher Freigabe wurde genau eine atomare
`TransactWriteItems`-Operation mit drei konditionierten Deletes ausgeführt:

1. `partner-r08-20`
   Bedingungen: `tenantId`, `cognitoClientId`, `apiProfileId`, `status=INACTIVE`.
2. `partner-r08-22`
   Bedingungen: `tenantId`, `cognitoClientId`, `apiProfileId`, `status=INACTIVE`.
3. `CLIENT#21j28p71vogg0m41tcue0ib3l4`
   Bedingungen: `reservedForApplicationId=partner-r08-22`,
   `cognitoClientId`, `status=RESERVED`.

Ergebnis:

```text
delete_transaction=SUCCESS
registry_after_count=0
registry_after=EMPTY
```

Keine anderen Tabellen oder Records wurden gelöscht oder verändert.

## C — Neuer synthetischer Partner

Über den regulären CLI-/Domain-Lifecycle provisioniert:

| Ressource | Kennung |
|---|---|
| APIProfile | `aprof_49fabe2e870e4f3c` |
| Partner | `partner-r08-23` |
| Credential | `cred_551b0e5f1ecd49ff` |
| Tenant | `ris-dev2-e2e-20261105` |
| Cognito-Client | `21j28p71vogg0m41tcue0ib3l4` |

`resolve_partner_application()` lieferte danach eindeutig:

```json
{
  "applicationId": "partner-r08-23",
  "status": "ACTIVE",
  "tenantId": "ris-dev2-e2e-20261105",
  "apiProfileId": "aprof_49fabe2e870e4f3c",
  "cognitoClientId": "21j28p71vogg0m41tcue0ib3l4"
}
```

## D — Temporäre Cognito-Testidentität

Nach separater Freigabe wurde **genau ein** temporärer synthetischer Benutzer
im bestehenden Pool `eu-central-1_K3dkdSipZ` angelegt:

* Präfix `ris-dev2-e2e-23-`;
* `@example.invalid`;
* `MessageAction=SUPPRESS`;
* permanentes Zufallspasswort nur im Speicher;
* keine Pool-, Client-, Domain- oder Authorizer-Konfiguration geändert.

Der echte Access-JWT hatte:

```text
token_use      = access
client_id      = 21j28p71vogg0m41tcue0ib3l4
sub            = vorhanden
tenant claim   = nicht im Access-Token enthalten
```

Das Fehlen des Tenant-Claims ist erwartet: L03 löst den Tenant serverseitig
aus Credential und Registry auf und verlangt nur bei vorhandenem Claim
Übereinstimmung.

Der Benutzer wurde nach dem Test gelöscht; der Pool ist wieder bei **0
Benutzern**.

## E — Live-HTTP-Testmatrix

Basis: `https://8apxb6fgne.execute-api.eu-central-1.amazonaws.com`

| Test | Ergebnis |
|---|---:|
| Gateway + gültiger JWT + gültiger Partner-Key (Metrics) | **200** |
| Metrics vor Create | **200** |
| Application Create | **201** |
| List | **200**, 1 Item |
| Detail | **200** |
| Patch | **200**, Version 1 → 2 |
| Detail nach Patch | **200**, geänderte Notes, Version 2 |
| Export | **200** |
| Metrics nach Create | **200**, `total=1`, `drafts=1` |
| Delete | **204** |
| List nach Delete | **200**, 0 Items |
| Metrics nach Delete | **200**, `total=0` |
| Ungültiger Credential-Key | **401** |
| Fremder Tenant (deployed-Lambda-Grenze) | **403** |
| Unbekannter Client (deployed-Lambda-Grenze) | **403** |
| Credential-Status nach Revoke | **REVOKED** |

Die List-Antwort enthielt `schemaVersion`, `version` und `salary.amount` als
JSON-Zahlen (`int`), nicht als Strings oder Serialisierungsfehler. Der frühere
422-Pfad ist damit live behoben.

**Einschränkung:** Der Aufruf mit dem widerrufenen Key konnte nach dem Löschen
der Secret-Datei nicht mehr mit genau diesem Key wiederholt werden. Die
Revocation-Semantik (403 bei widerrufenem Credential) ist aus Phase 20 belegt;
hier wurde der terminale `REVOKED`-Status verifiziert.

## F — Zusätzlicher Fund: Float-Salary-Input

Ein erster Create-Versuch mit `salary.amount = 50000.5` lieferte **409
CONFLICT**. Ursache ist nicht der Response-Fix, sondern die Request-Seite:

* der Contract akzeptiert `int | float`;
* `ApplicationRepository._transact()` übergibt den Float an
  `boto3.TypeSerializer`;
* boto3 lehnt Float ab (`Float types are not supported. Use Decimal types instead.`);
* der `TypeError` wird als generischer `ApplicationConflict` (409) maskiert.

Damit ist ein contract-konformer gebrochener Salary-Wert derzeit nicht
speicherbar. Der E2E wurde mit einem ganzzahligen Salary erfolgreich
abgeschlossen. Der Float-Input-Fix ist **nicht** Teil dieses Auftrags und wurde
wegen des Verbots weiterer Deployments nicht umgesetzt.

## G — Cleanup

| Prüfung | Ergebnis |
|---|---|
| Application-Daten | 0 |
| Cognito-Benutzer | 0 |
| Secret-Datei | gelöscht, Abwesenheit verifiziert |
| Credential | `REVOKED` |
| APIProfile | `REVOKED` |
| Partner | `INACTIVE` |
| Aktive Testberechtigung | keine |
| `ris-dev` | unberührt |

Residual: Der inaktive Record `partner-r08-23` und die interne Reservation
`CLIENT#21j28p71vogg0m41tcue0ib3l4` (RESERVED für `partner-r08-23`) bleiben als
terminale Audit-Spur bestehen. Der bestehende Lifecycle sieht keinen
Hard-Delete vor. Vor einem weiteren Test mit demselben Client ist eine erneute
gezielte Cleanup-Freigabe erforderlich.

## H — Offene Folgearbeit

1. Float-Salary-Input im Repository auf `Decimal` konvertieren und mit Tests
   absichern; separater Deploy erforderlich.
2. Residual-Partner/-Reservation vor dem nächsten Test gezielt bereinigen.
3. Jobsearch-BFF weiterhin server-side; `X-Api-Credential` nie im Browser.
4. Gate B und Produktion bleiben bis zur gesonderten Abnahme **NO-GO**.

## Statusübersicht

```text
Collision cleanup:             PASS (3 exact records, atomic)
New synthetic partner:         PASS (resolved uniquely)
Real JWT authenticated call:   PASS
ApplicationV1 create/list/detail/patch/export/delete: PASS
Version semantics:             PASS (1 -> 2)
Tenant/client isolation:       PASS (deployed-Lambda boundary)
Invalid credential:            PASS (401)
Credential revocation:         PASS (status REVOKED)
Float salary input:            FAIL (409; separate defect, not fixed)
Cognito config changes:        NONE
Terraform / Lambda deploy:     NONE in this step
Cleanup:                       COMPLETE for active resources
ris-dev:                       UNTOUCHED
Gate B:                        NO-GO
```
