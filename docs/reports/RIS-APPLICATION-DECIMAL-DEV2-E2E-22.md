# RIS-APPLICATION-DECIMAL-DEV2-E2E-22

## Ergebnis

**Deployment PASS. Reservation-Release PASS. Voller ApplicationV1-E2E BLOCKED
durch einen neuen Exklusivitätskonflikt im Partner-Registry.**

Der Decimal-Fix ist live auf `ris-dev2-dev-agent`. Die anschließende
Partner-Provisionierung erzeugte jedoch zwei Partner-Records für denselben
Cognito-Client; `resolve_partner_application()` liefert weiterhin den alten
INACTIVE-Record. Der positive Gateway-/JWT-E2E konnte deshalb nicht laufen.

Keine Cognito-, CloudFront-, DNS- oder `ris-dev`-Änderung.

## 22A — Preflight

| Prüfung | Ergebnis |
|---|---|
| HEAD | `7afbe8138a1ce639c22fe9a0c3aec43b0d417f4f` |
| AWS profile / account | `default` / `262370457690` |
| Region | `eu-central-1` |
| Workspace | `ris-dev2` |
| State vor Deploy | Serial 27, Lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Agent-Bundle | 81 Dateien, SHA-256 `6D7193C37D56E13D40E932A250356BD346D89D12AE3948939501444BE382FF8E` |

### Plan-Verwerfung

Der erste Plan enthielt neben dem Agent-Lambda **6 ungewollte PITR-Änderungen**
(`true → false`) an R08-Tabellen, weil `r08_pitr_enabled` im Plan-Input fehlte.
Dieser Plan wurde gemäß STOP-Regel verworfen:

```text
Plan SHA-256 2E35E4EA52D5274232D23C20E5793EF801CF927A00329801C6B9DF69B6503D27
0 add / 7 change / 0 destroy
```

### Freigegebener Plan

Mit dem aktuell deployten PITR-Wert `true` blieb genau eine Änderung:

```text
Plan SHA-256 E1BB4B34DA6977B2EA203BA87AB931856DA9721CECFB56BDE79443376B14DEAD
0 add / 1 change / 0 destroy
```

Einzige Änderung:

```text
module.lambda.aws_lambda_function.agent
source_code_hash oLlFKL4VTIGK/vDW3zXIK3aq9J4peYKE8UCFOfC58CI=
              -> bXGTw31W4T1A6TKiUDVr00bYnRKuOUiTlQFES+OC/44=
```

Keine Cognito-, CloudFront-, DNS-, IAM-, SQS-, PITR- oder Orders-Änderung.

### Decimal-Präzision

Nur `salary.amount` kann gebrochen sein; `version` und `schemaVersion` sind
Ganzzahlen. Es gibt keine Geldarithmetik in ApplicationV1. `Decimal` bleibt
unverändert im Storage; nur die HTTP-Projektion wird `int`/`float`. Kein
Datenverlust im persistierten Zustand.

## 22B — Begrenzter Deploy

Nach separater Bestätigung des konkreten Plans:

```text
terraform apply -input=false -no-color <gespeicherter Plan>
Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

Nachprüfung:

| Prüfung | Ergebnis |
|---|---|
| Lambda `State` | `Active` |
| `LastUpdateStatus` | `Successful` |
| `CodeSha256` | `bXGTw31W4T1A6TKiUDVr00bYnRKuOUiTlQFES+OC/44=` |
| Lokaler Zip-Hash | identisch |
| State nach Apply | Serial 28, Lineage unverändert |
| No-Changes-Plan | Exit 0, keine Unterschiede |
| Lambda-Health | 200, `{"status":"ok",...}` |

Der Deploy hat ausschließlich den Agent-Lambda-Code geändert.

## 22C — Reservation-Release

Freigegeben und ausgeführt wurde genau ein konditioniertes `DeleteItem`:

```text
Key:  CLIENT#21j28p71vogg0m41tcue0ib3l4
Condition: reservedForApplicationId = partner-r08-20
           AND cognitoClientId = 21j28p71vogg0m41tcue0ib3l4
           AND #status = RESERVED
```

Vor dem Delete verifiziert:

* vollständiger Schlüssel, nicht die abgekürzte Referenz;
* `reservedForApplicationId = partner-r08-20`;
* Besitzer-Partner `INACTIVE`;
* Besitzer-Tenant `ris-dev2-e2e-20261105`;
* Besitzer-Profil `REVOKED`;
* keine ACTIVE-Credentials für das Profil;
* keine ACTIVE-Partnerrecords.

Ergebnis:

```text
delete=SUCCESS
reservation_after=ABSENT
registry_others_unchanged=YES
```

## 22D — Neuer Exklusivitätskonflikt

Nach der Freigabe wurden über den regulären CLI-Pfad angelegt:

| Ressource | Kennung | Status |
|---|---|---|
| APIProfile | `aprof_beb47092354b4d4d` | zunächst ACTIVE, jetzt `REVOKED` |
| Partner | `partner-r08-22` | zunächst ACTIVE, jetzt `INACTIVE` |
| Credential | `cred_1f82e42f1cd84574` | `REVOKED` |

Die Provisionierung selbst war erfolgreich. Der anschließende Aufruf am
deployten Lambda mit dem neuen Credential lieferte jedoch `403 Forbidden`.

Ursache:

* `partner-r08-20` (alt, `INACTIVE`) und `partner-r08-22` (neu, damals
  `ACTIVE`) teilen denselben `cognitoClientId`.
* `resolve_partner_application()` liefert den ersten GSI-Treffer und
  revalidiert ihn an der Basistabelle. Es erhielt `partner-r08-20`
  (`INACTIVE`) statt `partner-r08-22`.
* Dadurch schlägt die Partner-Bindung fail-closed fehl.

Die Reservation zeigt aktuell wieder auf `partner-r08-22`; beide Partner sind
inzwischen `INACTIVE`.

**Der positive ApplicationV1-E2E wurde nicht ausgeführt.** Es wurden keine
Application-Daten angelegt (`applications_count=0`).

## 22E — Cleanup des neuen Versuchs

* Credential `cred_1f82e42f1cd84574` terminal widerrufen;
* Partner `partner-r08-22` deaktiviert;
* APIProfile `aprof_beb47092354b4d4d` terminal widerrufen;
* Secret-Datei gelöscht und Abwesenheit verifiziert;
* keine ACTIVE-Partner, -Profile oder -Credentials aus diesem Versuch;
* `ris-dev` unberührt.

## 22F — Nicht ausgeführte Teile

| Schritt | Status |
|---|---|
| Echter Cognito-Login-JWT | **nicht erstellt** — Cognito-Änderungen waren ausdrücklich verboten; Pool hat 0 Benutzer |
| API-Gateway-Positivtest | **BLOCKED** — kein gültiger JWT und doppelte Client-Bindung |
| Application Create/List/Detail/Patch/Export/Metrics | **nicht ausgeführt** |
| Tenant-/Client-Isolation live | **nicht ausgeführt** |
| Credential-Revocation-Nachweis | **PASS** (Credential ist `REVOKED`) |

## 22G — Erforderliche nächste Freigabe

Für den vollständigen E2E sind zwei getrennte Entscheidungen nötig:

1. **Registry-Bereinigung:** Löschung des alten synthetischen
   `partner-r08-20` und der aktuellen Reservation, danach neue
   Partner-Provisionierung. Alternativ eine guarded Lifecycle-Delete/Rebind-
   Operation mit Code, Tests und separatem Deploy.
2. **Testidentität:** Ohne temporäre Cognito-Testidentität ist kein echter
   JWT-Positivtest möglich. Dafür wäre eine ausdrückliche Cognito-Freigabe
   nötig; der Trust Anchor allein autorisiert keine Benutzeranlage.

## 22H — Status

```text
Decimal-Fix deployed:          YES
Lambda code hash verified:     YES
No-changes plan:               YES
Health smoke:                  YES
Reservation release:           YES (conditional, single delete)
Partner/profile/credential:    provisioned then revoked/inactivated
ApplicationV1 positive E2E:    BLOCKED (duplicate client binding)
Real Cognito JWT:              NOT CREATED (Cognito changes forbidden)
Cleanup of new resources:      COMPLETE
ris-dev:                       UNTOUCHED
Gate B:                        NO-GO
```
