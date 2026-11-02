# RIS-PARTNER-PROFILE-R07-FIX-04 — SECURE PAGINATION CURSORS

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| HEAD vor Fix | `d6393e3` (`fix(ris): handle legacy capacity counters without unsafe deletion`) |
| Tracked Working Tree | clean |
| Untracked Dateien | 39, unverändert |
| Scope | ausschließlich Mays-RIS |
| AWS-Mutation | keine |

## 2. F-6 — Ist-Zustand

Die drei paginierten Partner-Listen (ManualSearchProfile, CVSearchProfile,
ATSSearchProfile) kodierten `LastEvaluatedKey` wie folgt:

```python
base64.urlsafe_b64encode(json.dumps(last_evaluated_key).encode()).decode()
```

Synthetisches Beispiel (keine echten IDs):

```text
eyJyZXNvdXJjZUlkIjogImF0cy0xIiwgInBhcmVudElkIjogInNwLTEifQ==
```

Das ist reversibel und enthält die internen Schlüssel im Klartext. Es gab
weder eine Signatur, noch eine Identitäts-/Query-Bindung, noch eine
Ablaufzeit. Ein manipulierter Cursor führte zwar durch die normale
Identitätsfilterung nicht direkt zu Fremddaten, konnte aber Pagination
verschieben oder interne Schlüssel offenlegen.

## 3. Verfahrensentscheidung

### Geprüft: AES-256-GCM

AES-GCM wäre stateless und stark, scheitert aber an den vorhandenen
Randbedingungen:

- `lambda/build_zip.py` (`build_agent_bundle`) packt **nur Python-Quellen**
  aus `lambda/`, `agents/` und `jobsearch/`. Es werden keine Wheels oder
  `site-packages` eingezogen.
- `cryptography` ist weder in `requirements.txt` noch im Bundle; ein
  manylinux-Wheel mit `_cffi_backend`/OpenSSL müsste zusätzlich paketiert und
  die deterministische Bundle-Logik geändert werden. Das ist mit der
  bestehenden Lambda-Pipeline nicht nachgewiesen.
- Es gibt keine bestehende Cursor-Schlüsselverwaltung; ein neues Secret
  bräuchte Terraform-/Environment-Änderungen und einen Rotationspfad.

### Gewählt: serverseitiges Zufallstoken

Ein 256-Bit-Zufallstoken wird an den Client ausgegeben; der zugehörige
`LastEvaluatedKey` liegt **serverseitig** in der bestehenden
`partner_profiles`-Tabelle. Damit:

- keine native Krypto-Abhängigkeit, keine Packaging-Änderung,
- keine neue Tabelle, kein neues IAM-Recht, kein Secret,
- Vertraulichkeit: der Client sieht nur Zufallsbytes,
- Manipulationsschutz: der Server findet nur den exakten Token-Hash,
- Identitäts-/Query-Bindung und Ablauf werden serverseitig geprüft.

Trade-off: ein zusätzlicher `PutItem` pro Seite und ein strongly-consistent
`GetItem` pro Fortsetzung. Das ist für Partner-Listen mit max. 50 Einträgen
vertretbar; die bestehende Tabelle und TTL werden wiederverwendet.

## 4. Cursor-Format

Öffentlich:

```text
rp1_<43 Zeichen base64url aus 32 Zufallsbytes>
```

- Präfix `rp1_` = Version 1.
- Maximale Länge 256 Zeichen; längere/anders geformte Tokens werden abgelehnt.
- Keine lesbaren Keys, kein JSON, keine Base64-Darstellung des Keys.

Serverseitiges Item (`resourceId = cursor#<sha256(token)>`):

```json
{
  "resourceType": "CursorToken",
  "version": 1,
  "scope": "ats-search-profiles",
  "queryHash": "<sha256>",
  "lastEvaluatedKey": { "...": "..." },
  "userId": "...",
  "tenantId": "...",
  "partnerApplicationId": "...",
  "issuer": "...",
  "issuedAt": 0,
  "createdAt": "...",
  "updatedAt": "...",
  "expiresAt": 0
}
```

- Der Roh-Token wird nicht gespeichert, nur sein SHA256 als Item-Key.
- `expiresAt` ist ein Epoch-Wert und nutzt das bereits aktivierte
  Tabellen-TTL (`expiresAt`).
- `CursorToken` ist ein System-Item und wird aus allen Profil-Listen
  ausgeschlossen (`_from_item`/`attribute_exists(payload)`).

## 5. Identitäts- und Query-Bindung

Identität (exakt, serverseitig verglichen):

- `userId`
- `tenantId`
- `partnerApplicationId` (leer = nicht gesetzt)
- `issuer`

Query-Digest (SHA256 über kanonisches JSON):

- `scope` (z. B. `manual-search-profiles`, `cv-search-profiles`,
  `ats-search-profiles`)
- `resourceType`
- `parentId` (bei Parent-Listen)

Die Seitengröße ist bewusst **nicht** gebunden: der `LastEvaluatedKey` bleibt
für dieselbe Query gültig, und Clients dürfen `limit` bei der Fortsetzung
weglassen. Scope/ResourceType/Parent verhindern Cross-List- und
Cross-Parent-Nutzung. Filter, die die Query verändern, sind nicht Teil der
aktuellen Listen-API; neue Filter müssen künftig in den Digest aufgenommen
werden.

Ein Cursor ersetzt **keine** Autorisierung: der Handler prüft weiterhin
JWT/Credential/Partner/Tenant/Issuer und das Repository filtert die Identität.

## 6. Ablauf und Schlüssel

- Gültigkeit: **15 Minuten** (`CURSOR_TTL_SECONDS = 900`). Begründung: kurze
  Partner-Pagination, aber genug Zeit für mehrere Seiten; begrenzt die
  Lebensdauer eines weitergegebenen Tokens.
- `issuedAt`/`expiresAt` werden ausschließlich serverseitig gesetzt.
- Ablauf wird explizit bei jedem Resolve geprüft (`expiresAt <= now`), nicht
  dem asynchronen TTL überlassen. Abgelaufene Items werden best-effort
  gelöscht.
- Kein Secret, kein Schlüssel im Repo, keine Wiederverwendung von JWT- oder
  Partner-Credentials. Bei nicht erreichbarem Cursor-Store → 5xx.
- Eine Key-ID/Rotation ist nicht erforderlich; bei Bedarf kann später ein
  neues Token-Präfix (`rp2_`) eingeführt werden.

## 7. Legacy-Cursor

Alte Base64-JSON-Cursor werden **nicht** akzeptiert:

- kein `rp1_`-Präfix → `CursorError` → **400 `Invalid cursor`**.
- Keine automatische Rückkonvertierung, kein stilles Weiterreichen.
- Da R07-B noch nicht deployt ist, ist die saubere Umstellung bevorzugt;
  Clients starten die Pagination bei Bedarf ab Seite 1.

## 8. API-Fehlervertrag

| Situation | Status |
|---|---|
| Gültiger Cursor | normale 200-Seite |
| Fehlend/leer | keine Cursor-Verwendung (erste Seite) |
| Falsches Format / Legacy-Base64 | 400 `Invalid cursor` |
| Manipulierter Token / unbekanntes Item | 400 |
| Abgelaufen | 400 |
| Unbekannte Version | 400 |
| Falscher User/Tenant/Partner/Issuer | 400 |
| Falscher Parent/ResourceType/Scope | 400 |
| Zu großer Token | 400 |
| Cursor-Store-Lesefehler | 500 `Internal error` |
| Cursor-Store-Schreibfehler | 500 `Internal error` |
| DynamoDB-Listenfehler | 500 (bestehend) |

Fehlerantworten enthalten nur `Invalid cursor` bzw. `Internal error`, keine
Token-, Key- oder Identitätsdetails.

## 9. Pagination unverändert

- weiterhin `Query` mit `KeyConditionExpression`, `Limit`,
  `ExclusiveStartKey`, `LastEvaluatedKey`
- weiterhin `gsi-user`/`gsi-parent`, eventual consistent
- kein Table-Scan im normalen Listenpfad
- kein Fallback auf unvollständige Benutzerlisten
- Seiten über mehrere Requests sind weiterhin **kein transaktionaler
  Snapshot** des Datenbestands

## 10. Tests

Neu: `tests/test_partner_profile_cursor_security.py` — **31 Tests PASS**:

- Issue/Resolve-Roundtrip mit echtem `CursorStore`
- keine lesbaren Keys im Token
- Nonce-/Token-Eindeutigkeit
- TTL/Version/QueryHash im Item
- veränderter Token, fehlendes Item, ungültiges Format, zu groß
- Legacy-Base64
- Ablauf (inkl. Löschung)
- unbekannte Version
- falscher User/Tenant/Partner/Issuer/Parent/ResourceType/Scope
- fremder Store
- Store-Lesefehler → Infrastrukturfehler (kein 400)
- leerer/zu großer `LastEvaluatedKey`
- keine Logs/`print` mit Tokenmaterial
- API: zwei Seiten, Fortsetzung ohne `limit`, manipuliert/fremd/falscher
  Parent/Legacy/abgelaufen → 400, Store-Fehler → 500
- Manual-List-Cursor-Roundtrip und Legacy-Ablehnung

DynamoDB Local (`tests/integration/test_partner_profile_dynamodb_local.py`)
wurde um **4 Cursor-Tests** erweitert (jetzt **33** lokale Tests):

- echte `LastEvaluatedKey`-Rückgabe und Fortsetzung
- Cursor-Item mit `CursorToken`/`expiresAt`
- Identitäts-/Tenant-/Partner-/Issuer-/Parent-/Scope-Ablehnung
- manipuliert/Legacy/abgelaufen
- fremder Benutzer erhält keine Daten

## 11. Regression

| Umgebung | Ergebnis |
|---|---|
| System-Python ohne boto3/Endpoint | **575 passed, 29 skipped, 256 subtests** |
| Venv + DynamoDB Local 3.3.2 (`127.0.0.1:18000`) | **608 passed, 0 skipped, 256 subtests** |
| DynamoDB-Local-Suite | **33/33 PASS** |
| OpenAPI-Konsistenz | PASS (Cursor war bereits als „opaque“ dokumentiert) |
| Terraform | nicht betroffen |
| `git diff --check` | PASS |

Der lokale Server wurde nach dem Lauf gestoppt; keine Testtabelle blieb
zurück. Keine AWS-Verbindung.

## 12. Lambda-Packaging / Deployment

- Neues Modul `jobsearch/partner_profile_cursor.py` ist reines Python und wird
  vom bestehenden `build_agent_bundle` automatisch aufgenommen.
- Keine neue Dependency, kein natives Wheel, keine Änderung an
  `lambda/build_zip.py`.
- Keine neue Tabelle, kein neues IAM-Recht, keine neue Environment-Variable.
- Voraussetzung im Zielsystem: TTL auf `expiresAt` ist aktiv (Terraform
  `partner_profiles` bereits `enabled = true`); IAM erlaubt bereits
  `PutItem`/`GetItem`/`DeleteItem` auf Tabelle/Index.
- OpenAPI-Schema unverändert; Cursor ist weiterhin opaque.
- Kein Deployment in diesem Gate.

## 13. Andere Findings

| ID | Status |
|---|---|
| F-5 | **PARTIAL** – Legacy-Delete sicher; Counter-Backfill/Reconciliation offen |
| P1-1 CVDocument-Naming/Status | OPEN, unverändert |
| R08 S3-Version-Purge/Erasure | OPEN, unverändert |
| R07-B AWS E2E | NOT RUN |

## 14. Status

- **IMPLEMENTED:** serverseitiger Cursor-Store, 15-min-TTL, Identitäts-/Query-
  Bindung, Legacy-Ablehnung, 400/500-Mapping.
- **VERIFIED:** 31 Cursor-Tests, 33 Local-Tests, 608 Gesamttests.
- **PARTIAL:** F-5 (nur Counter-Reconciliation).
- **OPEN:** P1-1, R08.
- **NOT RUN:** R07-B AWS E2E.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.

**R07-B-G0 bereit: GO** (Cursor-Store nutzt ausschließlich die bestehende
Tabelle/TTL/IAM; im AWS-E2E sind TTL-Cleanup und reale Store-Latenz zu
beobachten).
