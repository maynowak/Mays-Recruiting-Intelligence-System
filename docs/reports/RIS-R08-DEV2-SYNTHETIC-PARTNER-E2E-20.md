# RIS-R08-DEV2-SYNTHETIC-PARTNER-E2E-20

## Ergebnis

**Autorisierung akzeptiert. Synthetischer Partner, APIProfile und Credential
provisioniert, getestet, widerrufen und terminiert. ApplicationV1-Leseendpunkte
scheitern an einem bestehenden Decimal-Serialisierungsfehler im deployten
Lambda-Code.**

Keine Cognito-, CloudFront-, DNS-, Terraform- oder `ris-dev`-Änderung.
Kein Secret in Git, Report, Log oder Chat.

## 1. Autorisierung

Genutzt wurden ausschließlich:

```text
AWS profile: default
Account:     262370457690
Region:      eu-central-1
Principal:   arn:aws:iam::262370457690:user/devnemo
Tenant:      ris-dev2-e2e-20261105
Role:        admin
```

Die bereitgestellte Datei
`%USERPROFILE%\.ris\admin-authorization-dev2.json` enthielt exakt diese
Zuordnung. Die Windows-ACL wurde auf den aufrufenden Benutzer reduziert.
Zusätzlich wurde das Read-only-Attribut gesetzt, damit der bestehende
`os.stat()`-Guard keine Schreibbits mehr sieht. Inhalt und Vertrag blieben
unverändert; `resolve_admin_authorization()` lieferte:

```text
{'actor_role': 'admin', 'actor_id': 'arn:aws:iam::262370457690:user/devnemo',
 'actor_tenant': 'ris-dev2-e2e-20261105'}
```

Der Check wurde nicht abgeschaltet und es wurde keine Genehmigung erfunden.

## 2. Provisionierung

Vorher waren alle drei DEV2-Tabellen leer. Angelegt wurden genau:

| Ressource | Kennung | Endstatus |
|---|---|---|
| APIProfile | `aprof_21794823992c4faf` | `REVOKED` |
| Partner Application | `partner-r08-20` | `INACTIVE` |
| Credential | `cred_d198d98ff4b5459f` | `REVOKED` |

Bindung:

```text
Cognito client: 21j28p71vogg0m41tcue0ib3l4
Issuer:         https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_K3dkdSipZ
Tenant:         ris-dev2-e2e-20261105
API base:       https://8apxb6fgne.execute-api.eu-central-1.amazonaws.com
Lambda:         ris-dev2-dev-agent
```

Das Credential wurde über den bestehenden Lifecycle (`generate_secret` →
SHA-256-Digest → once-only Datei) ausgestellt. Die Secret-Datei war 47 Zeichen
lang, owner-only und wurde nach der Revocation gelöscht.

## 3. Live-Gateway-Grenzen (ohne JWT)

| Request | Ergebnis |
|---|---:|
| `GET /health` ohne JWT | 401 |
| `GET /v1/partner/me/applications/metrics` ohne Header | 401 |
| dieselbe Route nur mit gültigem `X-Api-Credential` | 401 |
| dieselbe Route mit malformed Credential | 401 |

Der Gateway-JWT-Authorizer lehnt fehlende oder ungültige Tokens vor der Lambda
ab. Das ist erwartetes Fail-closed-Verhalten.

## 4. Dual-Auth- und ApplicationV1-Test am deployten Lambda

Der Cognito-Pool enthält aktuell **keine Benutzer**. Ein echter Login-JWT war
ohne Cognito-Mutation nicht erhältlich; Cognito-Änderungen waren ausdrücklich
ausgeschlossen. Der Test wurde deshalb am deployten `ris-dev2-dev-agent` mit
exakt den Claims ausgeführt, die der Gateway-Authorizer nach erfolgreicher
Prüfung liefert (`sub`, `client_id`, `token_use=access`, `iss`,
`custom:tenant_id`). Das ist ein Lambda-Vertragstest, **kein** HTTPS-Login.

| Schritt | Ergebnis |
|---|---:|
| Metrics vor Anlage | 200, `total=0` |
| Liste vor Anlage | 200, 0 Items |
| Application create | 201, `version=1` |
| Metrics nach Anlage | 200, `total=1`, `drafts=1` |
| Liste mit vorhandenem Item | **422 `VALIDATION_ERROR`** |
| Detail | **422 `VALIDATION_ERROR`** |
| Patch | **422**, Mutation wurde dennoch angewendet (`version=2`) |
| Export | **422 `VALIDATION_ERROR`** |
| Ungültiges Credential | 401 |
| Fremder Tenant-Claim | 403 |
| Unbekannter Client | 403 |
| Application delete | 204 |
| Liste nach Delete | 200, 0 Items |
| Metrics nach Delete | 200, `total=0` |
| Roh-Scan `ownerKey` | 0 Items |

Zusätzlich wurde derselbe Fehler im lokalen Handler reproduziert. Ein direkter
Repository-Aufruf liefert die gespeicherten Werte als `Decimal`
(`schemaVersion`, `version`); `_application_response()` ruft
`json.dumps()` ohne Decimal-Encoder auf und wird deshalb als
`TypeError`/422 abgebildet.

**Befund:** `ApplicationRepository._public()` reicht DynamoDB-`Decimal`-Werte
unverändert weiter. Metrics ist nicht betroffen, weil es nur Zähler liefert.
Liste, Detail, Patch-Antwort und Export scheitern, sobald echte Items existieren.
Der Fehler ist im deployten Code vorhanden und wurde **nicht** behoben oder
deployt, weil Lambda-/Terraform-Änderungen außerhalb des freigegebenen Scopes
lagen.

## 5. Revocation

| Prüfung | Ergebnis |
|---|---:|
| Credential-Status nach Revoke | `REVOKED` |
| Aufruf mit widerrufenem Credential | 403 `Forbidden` |
| Partner-Status nach Deactivate | `INACTIVE` |
| APIProfile-Status nach Cleanup | `REVOKED` |

Die Revocation wirkt sofort; der zuvor gültige Key wird abgewiesen.

## 6. Cleanup

* Application-Datensatz über den regulären `DELETE`-Pfad entfernt (204).
* Owner-Key-Scan: 0 Items.
* Credential terminal widerrufen.
* Partner deaktiviert (tenant-conditioned).
* APIProfile terminal widerrufen.
* Secret-Datei gelöscht; Abwesenheit verifiziert.
* Temporäre Testskripte gelöscht.
* Keine ACTIVE-Ressource aus diesem Test bleibt zurück.

Die Datensätze selbst bleiben als terminale Audit-Spur (`REVOKED`/`INACTIVE`)
erhalten; der bestehende Lifecycle sieht keine Hard-Delete-Operation vor.
Es wurde kein direkter DynamoDB-Schreibzugriff verwendet.

## 7. Grenzen

| Bereich | Status |
|---|---|
| AWS-Profil / Principal | unverändert |
| `ris-dev` | nicht berührt |
| Cognito | keine Änderung, keine Benutzeranlage |
| CloudFront / DNS / ACM | nicht berührt |
| Terraform | nicht ausgeführt |
| Secrets in Git/Report/Log/Chat | keine |
| Jobsearch / Vercel | nicht verändert |

## 8. Offene Folgearbeit

1. **ApplicationV1-Serialisierung korrigieren** (Decimal → JSON in
   `_public`/Response), mit Tests für Liste, Detail, Patch und Export.
2. Erst nach separater Freigabe paketieren und deployen; danach echten
   HTTPS-E2E mit einem synthetischen Cognito-Benutzer und gültigem Access-JWT
   wiederholen.
3. Jobsearch-BFF: `RIS_API_KEY` server-side, `Authorization` +
   `X-Api-Credential` weiterreichen, 422 nicht als leere Liste interpretieren.
4. Für echte Live-Positivtests muss die Betreiberin die Cognito-Testidentität
   separat freigeben; der Trust Anchor allein autorisiert keine Cognito-Anlage.

## 9. Abschlussstatus

```text
Authorization accepted:        YES
Synthetic provisioning:        YES (one partner/profile/credential)
Metrics at Lambda boundary:    PASS
ApplicationV1 create/delete:   PASS
ApplicationV1 read endpoints:  FAIL (deployed Decimal bug)
Unauthorized combinations:     DENIED (401/403)
Credential revoked:            YES (403 afterwards)
Cleanup:                       COMPLETE (no ACTIVE test resources)
Gate B:                        STILL NO-GO (read endpoints broken)
```
