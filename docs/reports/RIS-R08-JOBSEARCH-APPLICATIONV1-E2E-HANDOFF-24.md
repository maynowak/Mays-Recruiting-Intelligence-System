# RIS-R08 Jobsearch ApplicationV1 E2E Handoff 24

## Zweck

Dieser Handoff beschreibt den **tatsächlich getesteten** RIS-DEV2-Vertrag für
ApplicationV1, den ein serverseitiger Jobsearch-BFF-Adapter nutzen kann.
Es sind keine Tokens, Secrets oder echten Bewerberdaten enthalten.

## 1. Getestete Umgebung

```text
Environment:  ris-dev2
Account:      262370457690
Region:       eu-central-1
API base:     https://8apxb6fgne.execute-api.eu-central-1.amazonaws.com
Lambda:       ris-dev2-dev-agent
JWT issuer:   https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_K3dkdSipZ
JWT audience: 21j28p71vogg0m41tcue0ib3l4
Tenant:       ris-dev2-e2e-20261105 (synthetischer Test)
```

## 2. Authentifizierungsvertrag

Jeder Partner-Request benötigt **beide** Header:

```http
Authorization: Bearer <Cognito ACCESS token>
X-Api-Credential: <opakes RIS-Credential>
```

Verifiziert:

* `token_use = access` (kein ID-Token);
* `client_id` entspricht dem registrierten Partner-Client;
* `sub` ist vorhanden;
* das Access-Token muss **kein** `custom:tenant_id` enthalten — der Tenant
  wird serverseitig aus Credential und Registry aufgelöst;
* ein vorhandener, widersprüchlicher Tenant-Claim wird abgelehnt;
* das RIS-Credential ist ein opakes `ris_...`-Secret und bleibt serverseitig;
* ein ungültiges oder widerrufenes Credential wird abgelehnt.

## 3. Live getestete Endpunkte

| Funktion | Methode / Pfad | Ergebnis |
|---|---|---:|
| Metrics | `GET /v1/partner/me/applications/metrics` | 200 |
| Create | `POST /v1/partner/me/applications` | 201 |
| List | `GET /v1/partner/me/applications` | 200 |
| Detail | `GET /v1/partner/me/applications/{applicationId}` | 200 |
| Patch | `PATCH /v1/partner/me/applications/{applicationId}` | 200 |
| Export | `GET /v1/partner/me/applications/{applicationId}/export` | 200 |
| Delete | `DELETE /v1/partner/me/applications/{applicationId}` | 204 |

Zusätzlich verifiziert: Metrics nach Create `total=1`; nach Delete `total=0`;
List nach Delete `0` Items.

## 4. Versionierung und Fehlersemantik

* Create setzt `version=1`.
* Patch verlangt `expectedVersion` und erhöht bei Erfolg auf die nächste
  Version (im Test `1 → 2`).
* Detail nach Patch bestätigte die geänderten Notes und `version=2`.
* Ein veralteter `expectedVersion`-Wert bleibt ein echter
  **409 `VERSION_CONFLICT`**.
* Delete verlangt ebenfalls `expectedVersion`.
* Ungültiger Credential-Key: **401**.
* Fremder Tenant oder unbekannter Client: **403**.
* Contract-/Serialisierungsfehler: **422**, nicht 409.
* Store-Ausfall: **503**.
* Application-Antworten setzen `Cache-Control: no-store, private`.

## 5. Synthetische Beispiele

### Create Request

```json
{
  "job": {
    "jobId": "synthetic-job-1",
    "source": "synthetic",
    "title": "Synthetic Application",
    "company": "Synthetic Test Co",
    "location": "Remote"
  },
  "salary": {
    "expectation": {"amount": 50000, "currency": "EUR", "period": "year"}
  },
  "applicationChannel": "online",
  "notes": "Synthetic handoff example.",
  "idempotencyKey": "jobsearch-example-1"
}
```

### Create Response (201, gekürzt)

```json
{
  "application": {
    "applicationId": "00000000-0000-0000-0000-000000000000",
    "schemaVersion": 1,
    "version": 1,
    "status": "DRAFT",
    "stage": "draft",
    "job": {"jobId": "synthetic-job-1"},
    "salary": {"expectation": {"amount": 50000, "currency": "EUR", "period": "year"}}
  }
}
```

### Patch Request

```json
{
  "notes": "Updated synthetic note.",
  "expectedVersion": 1
}
```

### Patch Response (200, gekürzt)

```json
{
  "application": {
    "applicationId": "00000000-0000-0000-0000-000000000000",
    "version": 2,
    "notes": "Updated synthetic note."
  }
}
```

### Metrics Response

```json
{
  "metrics": {
    "total": 1,
    "drafts": 1,
    "submitted": 0,
    "interviews": 0,
    "openFollowUps": 0,
    "overdueFollowUps": 0
  }
}
```

## 6. Salary-Input-Stand

Der echte DEV2-Test mit **ganzzahligem** Salary war erfolgreich. Ein
gebrochener Wert (`50000.5`) lieferte vor dem Fix **409**, weil boto3 Float
ablehnt und der Fehler als Conflict maskiert wurde.

Der lokale Fix `67cd6fc`:

* konvertiert `salary.amount` verlustbewusst via `Decimal(str(value))`;
* lehnt Bool, Strings, NaN, Infinity, negative/Null-Werte und mehr als 38
  signifikante Stellen ab;
* verhindert binäre Float-Artefakte in DynamoDB;
* trennt Serialisierungsfehler (422) von echten Versionskonflikten (409).

**Dieser Fix ist noch nicht deployt.** Bis zum freigegebenen DEV2-Deploy
sollte Jobsearch keine gebrochenen Salary-Werte an RIS senden; ganzzahlige
Werte funktionieren live.

## 7. Anforderungen an den Vercel-BFF-Adapter

1. `RIS_API_KEY`/Credential ausschließlich als serverseitiges Vercel-Secret
   halten; niemals `VITE_*`, `NEXT_PUBLIC_*`, Browser-Storage oder Logs.
2. Der Browser ruft nur den BFF auf. Der BFF setzt
   `Authorization: Bearer <User-Access-JWT>` und
   `X-Api-Credential: <RIS-Secret>`.
3. Kein Credential in Request-Payloads, URLs, Fehlermeldungen oder Telemetrie.
4. `expectedVersion` und Cursor unverändert weiterreichen; keine clientseitige
   Neuerzeugung.
5. 401/403/409/422/503 unterscheiden und an die UI weitergeben; keinen
   erfolgreichen Transfer vortäuschen.
6. Bei 409 die aktuelle Version neu laden, nicht automatisch überschreiben.
7. Bei 503/Netzfehler den lokalen Draft behalten.
8. Tenant/Client nie aus dem Browser wählen lassen; RIS löst beides
   serverseitig auf.
9. CSRF-/Session-Schutz und Redaction im BFF vorsehen.

## 8. Was Jobsearch jetzt integrieren kann

Live verifiziert und mit einem server-side Credential nutzbar:

* Metrics lesen;
* Application Create;
* Application List;
* Application Detail;
* Application Patch mit Versionsprüfung;
* Export;
* Delete mit Versionsprüfung.

Voraussetzung: ein eigener, von RIS freigegebener Partner-/APIProfile-/
Credential-Satz für Jobsearch. Die synthetischen Testrecords aus diesem Lauf
sind inaktiv und nicht für Jobsearch bestimmt.

## 9. Noch nicht live verifiziert

* Pagination-Cursor über mehrere Seiten (Endpunkt vorhanden, im E2E nicht
  ausgeschöpft);
* Status-/Stage-Übergänge;
* History- und Cover-Letter-Versionen;
* Privacy-Inspect/Export;
* CV-, Profil- und Suchprofil-Routen;
* Token-Refresh, Rotation und MFA;
* Produktionsumgebung.

Diese Funktionen dürfen nicht als live bestätigt bezeichnet werden.

## 10. Phase-25-Update — Apply und Fractional Salary

Der Plan `8B16A3F50321952A9BE674DD89DAA9755ADF8363388053D1C5A235905A7FE8C2`
wurde angewendet:

```text
Apply:        0 added / 1 changed / 0 destroyed
Lambda:       ris-dev2-dev-agent
CodeSha256:   Q0o8VSGDONl44u4q33FRpG/u+4SMJhG6iNtU157hKno=
```

Am deployten Lambda live verifiziert:

| Test | Ergebnis |
|---|---:|
| Create mit `salary.amount = 50000.5` | 201 |
| Gespeicherter Wert | `Decimal("50000.5")`, exakt |
| Patch mit `salary.amount = 60000.75` | 200 |
| Version nach Patch | 1 → 2 |
| Gespeicherter Wert nach Patch | `Decimal("60000.75")`, exakt |
| List / Detail / Export / Metrics / Delete | 200/200/200/200/204 |
| Ungültiges Credential | 401 |
| Fremder Tenant / unbekannter Client | 403 |

Einschränkung: Dieser Bruchwert-Test lief am **deployten Lambda** mit
Authorizer-äquivalenten Claims, nicht über einen echten Cognito-Login. Der
echte Gateway-/JWT-Positivtest mit Bruchwert ist weiterhin durch die
historische Real-Client-GSI-Kollision blockiert; der letzte echte
Gateway-Positivtest mit ganzzahligem Salary stammt aus Phase 23.

Der Resolver-Fix, der bei mehreren historischen Records den Reservation-Owner
oder den eindeutigen ACTIVE-Record bevorzugt, benötigt einen separaten Plan
und Deploy. Bis dahin sollte Jobsearch den Bruchwert-Gateway-Pfad als **nicht
live verifiziert** behandeln.

Registry-Release und Client-Reuse wurden für einen synthetischen Client live
bestätigt; die echte-Client-Auflösung bleibt offen.

## 11. Phase-26-Update — Deterministischer Partner-Resolver

Der Resolver-Fix ist implementiert und getestet, aber noch **nicht deployt**:

* die Client-Reservation ist autoritativ;
* der Reservation-Owner wird strongly consistent gelesen;
* nur ein ACTIVER Owner mit passendem Client/Tenant wird aufgelöst;
* ohne Reservation ist genau ein ACTIVER Record erforderlich;
* mehrere ACTIVE-Records oder Reservation-/Tenant-Widersprüche führen zu
  fail-closed `None`;
* historische INACTIVE-Records werden ignoriert, nicht gelöscht.

Bis zum freigegebenen Deploy bleibt der echte Gateway-Positivtest mit
Bruchwert blockiert. Jobsearch sollte in dieser Zeit keine neue Bindung auf
denselben Client stützen und den Bruchwert-Gateway-Pfad weiterhin als nicht
live verifiziert behandeln.

## 12. Phase-27-Update — Echter Gateway-E2E erfolgreich

Der Resolver-Fix wurde deployt (`CodeSha256` `uGQX0tnPcIW0y1q6GtSaEPVEBjIDLqYrJzm2OX5wMEU=`)
und der echte Gateway-/JWT-/Partner-E2E ist vollständig bestanden:

| Test | Ergebnis |
|---|---:|
| Metrics | 200 |
| Create `salary.amount=50000.5` | 201 |
| List / Detail | 200 / 200 |
| Patch `salary.amount=60000.75` | 200, Version 1 → 2 |
| Export | 200 |
| Delete | 204 |
| Metrics nach Create / Delete | 1 / 0 |
| Ungültiger Key | 401 |
| Widerrufenes Credential | 403 |

Die DynamoDB-Werte wurden exakt als `Decimal("50000.5")` und
`Decimal("60000.75")` persistiert. Drei historische INACTIVE-Partner
blockierten die neue ACTIVE-Bindung nicht. Release und anschließende
Real-Client-Reuse wurden live bestätigt.

**Jobsearch kann damit folgende Funktionen gegen RIS integrieren:**

* Metrics lesen;
* Application Create mit Dezimalgehältern;
* List und Detail;
* Patch mit `expectedVersion` und Dezimalgehältern;
* Export;
* Delete mit `expectedVersion`.

Weiterhin **nicht live verifiziert**: mehrseitige Pagination, Status-/Stage-
Übergänge, History/Cover-Letter-Versionen, Privacy-Inspect/Export, CV-/Profil-
Routen, Token-Refresh/Rotation/MFA und Produktion.

Der BFF muss `RIS_API_KEY` serverseitig halten, JWT und `X-Api-Credential`
weiterreichen, `expectedVersion`/Cursor unverändert übernehmen und
401/403/409/422/503 korrekt behandeln.
