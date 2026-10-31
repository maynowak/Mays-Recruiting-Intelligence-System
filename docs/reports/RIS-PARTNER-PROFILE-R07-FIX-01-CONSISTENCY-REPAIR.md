# RIS-PARTNER-PROFILE-R07-FIX-01 — CONSISTENCY & QUERY FAIL-CLOSED REPAIR

## 1. Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| HEAD vor Fix | `c7aa9da` (`test(ris): prepare partner profile integration harness`) |
| Tracked Working Tree | clean |
| Untracked Dateien | 39, unverändert |
| Scope | ausschließlich Mays-RIS |
| AWS-Mutation | keine |

Behoben werden die R07-G0-Blocker **F-1 (HIGH)** und **F-7 (MEDIUM)**.

## 2. F-1 — Autoritative Reads

### Änderungen

Alle drei `GetItem`-Aufrufe des Repositories lesen jetzt aus der Basistabelle mit
`ConsistentRead=True`:

| Stelle | Zweck | Vorher | Jetzt |
|---|---|---|---|
| `get()` | Einzelressource, Parent-Auflösung, API-Response | eventual | `ConsistentRead=True` |
| `_get_raw()` | Update/Delete-Version, Lifecycle-Guard, Idempotenz-Replay | eventual | `ConsistentRead=True` |
| `_ensure_counter()` | Counter-Existenz vor der Transaktion | eventual | `ConsistentRead=True` |

GSI-Queries (`list_by_user`, `list_by_parent`) bleiben bewusst
eventual-consistent; `ConsistentRead` ist dort weder erlaubt noch sinnvoll.

### Fehler statt 404/409

Neu: `PartnerProfileReadError`.

- `get()` und `_get_raw()` liefern `None` **nur** bei einem wirklich fehlenden
  Item.
- Ein DynamoDB-Lesefehler wird als `PartnerProfileReadError` weitergereicht.
- Ein gespeichertes, aber nicht parsebares Item wird ebenfalls als
  `PartnerProfileReadError` behandelt („unreadable“), nicht als 404 und nicht
  als unvollständige Ressource.
- `list_by_user`/`list_by_parent` liefern keine leere Liste mehr, wenn die
  Query fehlschlägt, sondern werfen `PartnerProfileReadError`.

### API-Mapping

- `_partner_storage_guard` umschließt die vier Partner-Dispatcher (Manual, CV,
  Search-Profile/ATS) und mappt `PartnerProfileReadError` auf **500
  `Internal error`**.
- Bestehende Handler, die bereits `except Exception → 500` nutzen, bleiben
  unverändert korrekt.
- `_ats_parent` fängt nicht mehr pauschal alle Exceptions und gibt 404 zurück;
  nur ein tatsächlich fehlender/falscher Parent führt zu 404.

### Keine `version: null` nach Writes

Alle Create-/Update-/Complete-Pfade verwendeten zuvor `stored or <in-memory>`.
Der In-Memory-Fall hat kein autoritatives `version`-Attribut und konnte
`version: null` emittieren.

Jetzt gilt zentral:

```python
def _post_write_response(stored, response, status=200):
    if stored is None:
        return _storage_error()   # 500
    return response(stored, status)
```

Betroffene Pfade: Manual Create/Update, CV Create/Update/Complete, CVSP
Create/Update, ATS Create/Update. Ein erfolgreicher Write ohne unmittelbar
lesbaren Datensatz wird **nicht** als unvollständige Ressource ausgegeben.

### Unverändert

- Optimistisches Locking (`version = :v`) bleibt erhalten.
- Keine neuen Tabellen, Indizes, IAM-Rechte oder Retry-Schleifen.
- Die Idempotenz-Semantik (24 h, Digest, Payload-Hash) ist unverändert; der
  Replay-Read ist jetzt stark konsistent.

## 3. F-7 — Kein Fallback mehr

`list_by_parent` hatte bei einem Query-Fehler auf
`list_by_user(limit=1000)` zurückgegriffen und `None` als Cursor geliefert.
Das konnte Seiten still abschneiden und die Pagination brechen.

Jetzt:

- kein Fallback,
- keine clientseitige Filterung,
- `PartnerProfileReadError` bei Query-Fehler,
- API-Listenpfade antworten mit 500 statt einer leeren/verkürzten 200-Seite,
- Cursor-Pagination und `LastEvaluatedKey` bleiben unverändert.

## 4. Tests

Neu: `tests/test_partner_profile_consistency_repair.py` — **20 Tests PASS**.

| Bereich | Fälle |
|---|---|
| ConsistentRead | alle `GetItem`-Aufrufe `True`; GSI-Queries ohne `ConsistentRead` |
| Fehlerklassifikation | Read-Fehler ≠ `None`, ≠ 404, ≠ 409, ≠ Capacity-Konflikt |
| API | ATS/Manual/CV-GET → 500; ATS-List-Query-Fehler → 500 statt leerer Seite |
| Post-Write | fehlender Read nach Create → 500, kein `version: null` |
| Statik | kein `stored or` mehr; Guard und zentraler Helper vorhanden |
| Idempotenz | Replay-Read-Fehler → `PartnerProfileReadError`, kein 409 |
| Optimistik | stale Update weiterhin 409 |
| F-7 | kein `list_by_user`-Fallback; normale Pagination unverändert |
| Datenintegrität | nicht parsebares Item → `PartnerProfileReadError` |

Angepasst:

- `tests/test_partner_manual_profiles_api.py`: Fake `get_item` akzeptiert
  `ConsistentRead`.
- `tests/unit/jobsearch/test_partner_profile_repository.py`: Fake-`get_item`
  akzeptiert `ConsistentRead`.
- `tests/test_partner_profile_integration_harness.py`: Dispatcher-Assertion
  folgt dem neuen Guard-Aufruf.

## 5. Regression

| Suite | Ergebnis |
|---|---|
| Neue Repair-Tests | **20 passed** |
| R01–R07-G0 + Repair | **493 passed, 23 skipped, 256 subtests passed** |
| DynamoDB-Local-Suite | 23 skipped (Toolchain weiterhin nicht installiert) |

Keine echte DynamoDB-/S3-Operation, kein AWS-Apply, kein Deploy.

## 6. Verbleibende Befunde

| ID | Status |
|---|---|
| F-1 | **CLOSED** (R07-FIX-01) |
| F-7 | **CLOSED** (R07-FIX-01) |
| F-2 GSI eventual consistency | unverändert, bewusst |
| F-3 TTL asynchron | unverändert, Logik korrekt |
| F-4 `TransactionConflict` ohne Retry | OPEN (R07-A) |
| F-5 Delete setzt Counter voraus | OPEN (R07-A/Legacy) |
| F-6 Cursor base64/reversibel | OPEN (Hardening) |
| P1-1 CVDocument-Naming/Status | OPEN, kein Blocker |

R07-A bleibt **BLOCKED** durch fehlendes boto3/botocore, Java und
DynamoDB Local. Die 23 Integrations-Tests sind unverändert vorbereitet.
R07-B wurde nicht gestartet.

## 7. Status

- **IMPLEMENTED:** ConsistentRead, `PartnerProfileReadError`, 500-Mapping,
  fail-closed Listen, Post-Write-Guard.
- **VERIFIED:** 20 neue Tests, 493 Regressionstests.
- **OPEN:** F-4, F-5, F-6, P1-1.
- **NOT RUN:** echte DynamoDB-/S3-Integration, R07-B.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.
