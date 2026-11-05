# RIS-R08-DEV2-PARTNER-COLLISION-23

## Status

**READ-ONLY ANALYSIS COMPLETE — NO DELETION — APPROVALS REQUIRED**

Es wurde kein Registry-Eintrag gelöscht oder geändert, keine Cognito-Mutation,
kein Terraform-Apply und kein Lambda-Deployment ausgeführt.

## A1 — Auditlog

Der letzte Stand ist `RIS-APPLICATION-DECIMAL-DEV2-E2E-22`: Decimal-Fix live,
Reservation für `partner-r08-20` kontrolliert gelöscht, danach neue
Partner-Provisionierung, die wegen doppelter Client-Bindung mit 403 endete.

## A2 — Exakte Registry-Datensätze

Tabelle `ris-dev2-dev-partner-applications`, drei Items:

| Vollständiger Key `applicationId` | `tenantId` | `cognitoClientId` | `apiProfileId` | Status |
|---|---|---|---|---|
| `partner-r08-20` | `ris-dev2-e2e-20261105` | `21j28p71vogg0m41tcue0ib3l4` | `aprof_21794823992c4faf` | `INACTIVE` |
| `partner-r08-22` | `ris-dev2-e2e-20261105` | `21j28p71vogg0m41tcue0ib3l4` | `aprof_beb47092354b4d4d` | `INACTIVE` |
| `CLIENT#21j28p71vogg0m41tcue0ib3l4` | — | `21j28p71vogg0m41tcue0ib3l4` | — | `RESERVED` |

Reservation:

```text
reservedForApplicationId = partner-r08-22
status                   = RESERVED
cognitoClientId          = 21j28p71vogg0m41tcue0ib3l4
```

Damit hält **`partner-r08-22`** die aktuelle Reservation, nicht mehr
`partner-r08-20`.

## A3 — Zugehörigkeit zum synthetischen Test

| Record | Evidenz |
|---|---|
| `partner-r08-20` | Phase 20: synthetischer Partner, Tenant `ris-dev2-e2e-20261105`, Profil `aprof_21794823992c4faf`, Credential `cred_d198d98ff4b5459f` |
| `partner-r08-22` | Phase 22: synthetischer Partner, gleicher Tenant, Profil `aprof_beb47092354b4d4d`, Credential `cred_1f82e42f1cd84574` |
| Reservation | durch Phase 22 beim Anlegen von `partner-r08-22` erzeugt |

Beide Partner gehören ausschließlich den dokumentierten synthetischen
R08-Tests. Owner ist jeweils `arn:aws:iam::262370457690:user/devnemo`.

## A4 — Verbleibende Abhängigkeiten

| Tabelle | Anzahl | Bezug |
|---|---:|---|
| `ris-dev2-dev-api-profiles` | 2 | beide synthetisch, beide `REVOKED` |
| `ris-dev2-dev-credentials` | 2 | beide synthetisch, beide `REVOKED`, digest-only |
| `ris-dev2-dev-applications` | 0 | keine Anwendungsdaten |
| `ris-dev2-dev-user-profile` | 0 | keine Nutzerprofile |
| `ris-dev2-dev-partner-profiles` | 0 | keine Partnerprofile |
| `ris-dev2-dev-entitlements` | 0 | keine Berechtigungen |
| `ris-dev2-dev-offers` | 0 | keine Offers |

Es existieren **keine** Entitlement-, Offer-, Application- oder
Profil-Referenzen auf die beiden Partner oder Profile.

## A5 — Reservation

`partner-r08-22` hält die Reservation. `partner-r08-20` hält keine Reservation
mehr. Die Reservation ist derzeit der einzige Schutz gegen eine dritte
Client-Bindung, verhindert aber nicht die bestehende Doppelung der beiden
Partner-Records.

## A6 — Kein aktiver Partner, keine realen Nutzerdaten

* Beide Partner: `INACTIVE`.
* Beide Profile: `REVOKED`.
* Beide Credentials: `REVOKED`.
* Keine Application-/User-/Partner-Profil-/Entitlement-/Offer-Daten.
* Cognito-Pool: **0 Benutzer**.

Es ist keine aktive Berechtigung und kein reales Nutzerdatum betroffen.

## A7 — Tatsächliches Resolver-Verhalten

`resolve_partner_application('21j28p71vogg0m41tcue0ib3l4')` liefert:

```json
{
  "applicationId": "partner-r08-20",
  "status": "INACTIVE",
  "tenantId": "ris-dev2-e2e-20261105",
  "apiProfileId": "aprof_21794823992c4faf",
  "cognitoClientId": "21j28p71vogg0m41tcue0ib3l4"
}
```

Die GSI-Abfrage `gsi-client` liefert beide Partner-Records. Der Resolver nimmt
den ersten Nicht-Reservation-Treffer (`partner-r08-20`) und revalidiert ihn an
der Basistabelle. Die Reservation von `partner-r08-22` wird dabei nicht zur
Disambiguierung genutzt. Deshalb bleibt der alte `INACTIVE`-Record
ausschlaggebend und die Partnerroute antwortet fail-closed mit 403.

## A8 — Löschung

**Nicht ausgeführt.** Dieser Auftrag gibt die Löschung von `partner-r08-20`
ausdrücklich noch nicht frei.

## Vorgeschlagene Bereinigung (nur nach Freigabe)

Um die Exklusivität wiederherzustellen und eine neue Bindung zu ermöglichen,
müssen voraussichtlich **drei** exakt identifizierte Records entfernt werden:

1. `partner-r08-20`
   Bedingung: `tenantId = ris-dev2-e2e-20261105`,
   `cognitoClientId = 21j28p71vogg0m41tcue0ib3l4`,
   `apiProfileId = aprof_21794823992c4faf`, `status = INACTIVE`.

2. `partner-r08-22`
   Bedingung: gleicher Tenant/Client,
   `apiProfileId = aprof_beb47092354b4d4d`, `status = INACTIVE`.

3. `CLIENT#21j28p71vogg0m41tcue0ib3l4`
   Bedingung: `reservedForApplicationId = partner-r08-22`,
   `cognitoClientId = 21j28p71vogg0m41tcue0ib3l4`, `status = RESERVED`.

Warum beide Partner? Beide sind inaktiv und teilen denselben Client. Würde nur
`partner-r08-20` entfernt, bliebe `partner-r08-22` als historischer Record
zurück; die Reservation müsste trotzdem für eine neue Bindung frei werden.
Eine Reaktivierung von `partner-r08-22` ist über den bestehenden Lifecycle
nicht vorgesehen.

Alternative: eine guarded Lifecycle-Delete/Rebind-Operation. Das würde eine
Code-Änderung und ein weiteres Deployment erfordern — beides ist durch diesen
Auftrag ausgeschlossen.

Nach der Bereinigung: neue synthetische Provisionierung über den regulären
CLI-Pfad und erneute Resolver-Prüfung.

## Erforderliche getrennte Freigaben

1. **Registry-Bereinigung:** Löschung der drei oben genannten Records mit den
   genannten Bedingungen (oder ausdrückliche Entscheidung für einen späteren
   Lifecycle-Fix).
2. **Cognito-Testidentität:** Separate Freigabe für genau einen temporären
   synthetischen Benutzer im bestehenden Pool, falls ein echter
   Gateway-/JWT-Positivtest erforderlich ist. Ohne diese Freigabe ist nur der
   deployte-Lambda-Test mit Authorizer-äquivalenten Claims möglich.

## Statusübersicht

```text
Phase A collision analysis:     PASS
Registry deletion:              NOT EXECUTED (not approved)
Cognito changes:                NONE (pool still 0 users)
Terraform / Lambda deploy:      NONE
ApplicationV1 live E2E:         NOT EXECUTED
Active partner/credential:      NONE
Real user data:                 NONE
ris-dev:                        UNTOUCHED
Gate B:                         NO-GO
```
