# RIS-APPLICATION-DECIMAL-SERIALIZATION-FIX-21

## Ergebnis

**HTTP-422-Ursache behoben und getestet. Keine Änderung an Dual-Auth,
Tenant-Isolation oder Persistenz.**

Der Fix ist im Repository implementiert, aber **nicht deployt**. Ein Deploy
setzt Paketierung und eine separat freigegebene AWS-Operation voraus.

## 1. Ursache

`jobsearch/application_repository.py::ApplicationRepository._public()` reicht
DynamoDB-Werte unverändert weiter. DynamoDB liefert Zahlen als `Decimal`
(`schemaVersion`, `version`, Salary-Beträge usw.).

`lambda/handler.py::_application_response()` rief bislang

```python
json.dumps(body, ensure_ascii=False)
```

ohne Decimal-Encoder auf. Dadurch wurde nach erfolgreichem Lesen bzw. nach
einem bereits erfolgten Patch-Schreibvorgang ein `TypeError` ausgelöst und als
`422 VALIDATION_ERROR` zurückgegeben.

Besonders sichtbar: Beim Patch war die DynamoDB-Mutation bereits erfolgreich
(`version=2`), nur die HTTP-Antwort scheiterte.

## 2. Fix

In `lambda/handler.py`:

```python
from decimal import Decimal

def _application_json_default(value):
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    raise TypeError(
        'Object of type %s is not JSON serializable' % type(value).__name__)
```

`_application_response()` nutzt jetzt:

```python
json.dumps(body, ensure_ascii=False, default=_application_json_default)
```

Eigenschaften:

* **Persistenz unverändert:** `Decimal` bleibt im Repository-/DynamoDB-Pfad.
* **Nur HTTP-Projektion:** Integralwerte werden `int`, Bruchwerte `float`.
* **Fail-closed:** Unbekannte, nicht serialisierbare Typen lösen weiterhin
  einen `TypeError` aus und werden nicht stillschweigend entfernt.
* **Gleicher Response-Vertrag:** `Cache-Control: no-store, private` bleibt.
* **Gleiche Auth:** `_application_ctx` und `_partner_profile_context` wurden
  nicht verändert.

Der zentrale Response-Helper deckt damit auch Status-, History- und
Cover-Letter-Antworten ab, sofern sie Zahlen aus DynamoDB enthalten.

## 3. Tests

Neue Datei:

```text
tests/test_application_decimal_serialization.py
```

Abgedeckt:

* List mit `Decimal`-Feldern;
* Detail;
* Patch-Antwort nach bereits erfolgter Mutation;
* Export mit verschachtelten `Decimal`-Werten;
* Integral- und Bruchwerte;
* unbekannter Typ bleibt fail-closed.

Ergebnis der gesamten ApplicationV1-Gruppe:

```text
58 passed
```

Ausgeführt wurden unter anderem:

```text
test_application_api_security.py
test_application_auth_boundary.py
test_application_contract.py
test_application_e2e_harness.py
test_application_erasure.py
test_application_handoff_fixture.py
test_application_metrics.py
test_application_privacy_contract.py
test_application_repository.py
test_application_status_model.py
test_application_decimal_serialization.py
test_public_application_erasure.py
```

## 4. Nicht geändert

| Bereich | Status |
|---|---|
| Dual-Auth / JWT / `X-Api-Credential` | unverändert |
| Tenant- und Partner-Isolation | unverändert |
| DynamoDB-Schreiblogik / Versionierung | unverändert |
| ApplicationV1-Routen | unverändert |
| Cognito / CloudFront / DNS / ACM | nicht berührt |
| Terraform | nicht ausgeführt |
| `ris-dev` | nicht berührt |
| Secrets | keine |

## 5. Verbleibende Schritte

1. Paketierung und Deployment des Lambda-Bundles nach separater Freigabe.
2. Danach DEV2-E2E mit einem synthetischen Cognito-Benutzer und echtem
   Access-JWT wiederholen; der frühere Test lief am deployten
   Lambda-Vertrag mit authorizer-äquivalenten Claims.
3. Erst dann kann Gate B für ApplicationV1 als bestanden bewertet werden.

Bis zum Deploy liefert die live deployte Lambda für List/Detail/Patch/Export
weiterhin `422`, sobald echte Items mit `Decimal`-Werten existieren.
