# RIS-AUTHORIZATION-LIVE-ROLE-VALIDATION-03 — Live Rollen-Nachweis

STATUS: **GREEN** — alle Live-Rollenbeweise bestanden. Staff-Privilege-Escalation ist **geschlossen**.

- Datum: 2026-10-05 UTC
- Git HEAD: `3b81d96` (Forensik-Report; Fix weiterhin `70de2b1`)
- Account/Profil/Region/Workspace: `240571105849` / `mayaws` / `eu-central-1` / `mays-ris`
- **LIVE VALIDATION ONLY** — keine Infrastrukturmutation

## 1. AWS-/Git-Kontext und Fix-Integrität

| Prüfung | Wert | Soll | Match |
|---|---|---|---|
| AWS Profile | `mayaws` | `mayaws` | ✅ |
| Account | `240571105849` | `240571105849` | ✅ |
| Region | `eu-central-1` | `eu-central-1` | ✅ |
| Workspace | `mays-ris` | `mays-ris` | ✅ |
| Branch / HEAD | `main` / `3b81d96` | — | ✅ |
| Working Tree (vor Gate) | 0 tracked Änderungen | clean | ✅ |
| Lambda `CodeSha256` | `ECemCxwAOv0fNo3OeAkxjpT3Eg+Xyl9LZB61h3R4VvQ=` | FIX-02-Deploy | ✅ identisch |
| Lambda `LastModified` | `2026-10-05T10:07:55Z` | FIX-02-Apply | ✅ kein neuer Deploy |
| Gateway-Routen | 27, Soll-Set vollständig | 27 | ✅ |
| Agent Role-Policies | 8 | 8 | ✅ unverändert seit Forensik |
| Cognito `AutoVerifiedAttributes` | `["email"]` | `["email"]` | ✅ |

**Eigener Messfehler, korrigiert:** Eine erste Routenmessung ergab erneut „25" — ein Shell-Quoting-Artefakt bei `--query 'length(Items)'`. Die JSON-geparste Messung ergab 27 mit exakt passendem Set. Ich prüfe Routenbestände inzwischen immer doppelt.

## 2. Test-Fixtures

Alle 8 vorhandenen Fixtures waren deaktiviert und ihre Passwörter vernichtet — Wiederverwendung unmöglich, daher drei neue synthetische Fixtures (vom Gate ausdrücklich erlaubt):

| Fixture | Cognito-Gruppe | `cognito:groups` im Token | Status nach Test |
|---|---|---|---|
| `v3-owner-synth` | keine | nicht vorhanden | `Enabled=false` |
| `v3-admin-synth` | `admins` | `["admins"]` | `Enabled=false` |
| `v3-staff-synth` | `Staff` | `["Staff"]` | `Enabled=false` |

Alle drei: identischer synthetischer Tenant, `.invalid`-E-Mail, keine realen Personendaten. Passwörter und Tokens ausschließlich in einer tmp-Datei (Mode 700), nie ausgegeben, mit `shred -u` vernichtet.

**Eigener Fixture-Fehler, korrigiert:** Ich erzeugte die Tokens **vor** der Gruppenzuweisung. Der `/me`-Check zeigte deshalb zunächst `[]` für alle drei — das war meine Sequenzierung, kein Produktdefekt. Nach Re-Auth zeigte sich der korrekte Claim. Dokumentiert, weil die erste Messung sonst als Fehlschlag gewertet worden wäre.

## 3. Nachweis 7 — Claim-Normalisierung am Handler-Grenzpunkt

| Fixture | `/me` → `groups` | Vor FIX (P19) |
|---|---|---|
| `v3-owner-synth` | `[]` | `[]` |
| `v3-admin-synth` | **`["admins"]`** | `["[admins]"]` ← defekt |
| `v3-staff-synth` | **`["Staff"]`** | `[]` ← defekt |

Der String-Claim wird jetzt semantisch korrekt aufgelöst. Owner bleibt `[]`.

## 4. A — Owner-Regression

| Request | HTTP | Bewertung |
|---|---|---|
| `GET /me` | 200 | ✅ |
| `GET /me/profile` | 404 | ✅ korrekt (`API-STANDARD.md:25-26`: kein Auto-Provisioning) |
| `GET /platform` | 200 | ✅ |
| `GET /agents` | 200 | ✅ |
| `POST /v1/apiprofiles` | **201**, `status=PENDING`, `createdBy.role=owner` | ✅ Owner-Contract intakt |
| `GET` eigenes Profil | 200 | ✅ |
| `PATCH` eigenes Profil | 200 | ✅ |
| `POST …/status {"status":"ACTIVE"}` | **404** | ✅ **keine** Admin-Rechte |

**Owner bleibt Owner.** Keine Admin-, keine Staff-Rechte.

## 5. B — Product Admin (`admins`)

| Request | HTTP | Erwartung | Ergebnis |
|---|---|---|---|
| `/me` → `groups` | `["admins"]` | erkannt | ✅ |
| `GET /platform` | 200 | 200 | ✅ |
| `GET` **fremdes** Owner-Profil | **200** (`status`, `name` sichtbar) | 200 | ✅ **vorher 404** |
| `POST …/status {"status":"ACTIVE"}` | **200**, `status=ACTIVE`, `updatedBy.role=admin` | 200 | ✅ **vorher 404 — der in P19 blockierte Pfad** |
| `PATCH` fremdes Profil | 200 | 200 | ✅ |
| `POST` mit `targetOwner` | 201, `createdBy.role=admin`, `ownerUserId` = Ziel | 201 | ✅ |

**Mindestens eine zuvor blockierte Admin-Aktion läuft live erfolgreich durch:** der Admin-only-Statuspfad `PENDING → ACTIVE` sowie der Admin-Read auf fremde Profile. Erwartungskriterium 3 erfüllt.

## 6. C — Product Staff (`Staff`)

### Negativ (unerlaubt)

| Request | HTTP | Persistenzwirkung | Bewertung |
|---|---|---|---|
| `POST /v1/apiprofiles` | **403** `{"error":"Forbidden"}` | **keine** — `apiProfileId` nicht returned, Count 7 → 7 | ✅ **vorher 201 mit Persistierung** |
| `PATCH` fremdes Profil | 404 | keine | ✅ |
| `POST …/status {"status":"REVOKED"}` | **403** | keine | ✅ admin-only, verweigert |
| `GET` fremdes Profil **ohne** reason | 404 | — | ✅ kein Support ohne Reason |
| `GET /v1/apiprofiles` (List) | 200, `items: []` | — | ✅ contract-konform |
| `POST …/status {"status":"ACTIVE"}` | **409** | keine | ✅ `ACTIVE → ACTIVE` ist keine erlaubte Transition |

### Positiv (erlaubte Support-Funktion)

| Request | HTTP | Ergebnis |
|---|---|---|
| `GET` fremdes Profil **mit** `reason` | **200** (`status=ACTIVE`, `name` sichtbar) | ✅ **vorher 404 — Funktion war defekt und ist wiederhergestellt** |

**Staff erhält weder Owner- noch Admin-Rechte:** kein Create, keine Mutation fremder Profile, kein Revoke, keine Aktivierung. Die erlaubte Support-Support-Funktion funktioniert.

### Korrektur meiner eigenen Testetikettierung

Ich hatte `POST …/status {"status":"DISABLED","reason":"…"}` als Negativfall geführt. Das war **falsch**: der Domain-Code erlaubt Staff das explizit (`api_profiles.py:477-481`: `if not (admin or staff or own): raise`). Der Request ergab **200** und setzte das Profil auf `DISABLED`. Das ist **contract-konform**, keine Verletzung — aber eine reale Staff-Kompetenz, die ich benennen muss, statt sie als „verweigert" zu verbuchen.

Folge: Ich habe den Testzustand mit dem Admin-Pfad wiederhergestellt (`DISABLED → ACTIVE`, HTTP 200, `updatedBy.role=admin`). Der Zustand ist damit wie vorgefunden.

## 7. D — Cross-Role / Privilege Separation

Live-Ergebnismatrix:

| Rolle | Aktion | Ergebnis | Erwartung |
|---|---|---|---|
| OWNER | Create eigenes Profil | 201 | ✅ |
| OWNER | fremdes Profil lesen | 404 | ✅ |
| OWNER | `PENDING → ACTIVE` | 404 | ✅ keine Admin-Rechte |
| ADMIN | fremdes Profil lesen | 200 | ✅ |
| ADMIN | `PENDING → ACTIVE` | 200 | ✅ |
| ADMIN | Create für `targetOwner` | 201 | ✅ |
| STAFF | Create | 403 | ✅ keine Owner-Rechte |
| STAFF | fremdes Profil mutieren | 404 | ✅ |
| STAFF | REVOKE | 403 | ✅ keine Admin-Rechte |
| STAFF | Support-Read mit Reason | 200 | ✅ erlaubte Kompetenz |

`OWNER ≠ STAFF`, `OWNER ≠ ADMIN`, `STAFF ≠ ADMIN` — live belegt.

**ADMIN ≠ AWS ADMIN (Punkt 8):**

- Der einzige `iam.`-Treffer in `lambda/handler.py:357` ist das Wort „provisio**n**ed" in einem Kommentar — kein Code.
- **Keine** IAM-/STS-/CloudFormation-Client-Instanz im Produktivcode. Es gibt `boto3.client("sts")` in `agents/source_connectivity.py:152,227,260`, das ist **Sitzungs-/Identitätsauflösung für externe Quellen**, keine Administration.
- **Keine** Gateway-Route mit IAM-/Role-/Terraform-/AWS-/Admin-Bezug im Pfad.
- Der Deployment-Kontext `mayaws` ist **keine** Produktrolle: Er wurde in diesem Gate ausschließlich für AWS-Reads verwendet.

**Malformed/unknown Group:** online in diesem Gate **nicht** getestet — es hätte eine weitere Fixture-Mutation bedeutet. In FIX-02 lokal exhaustiv abgedeckt (10 Formen, 10 Fehlwerte, 0 privilegierte Fallbacks). Diese Lücke bleibt benannt.

## 8. E — Persistence-Checks

| Prüfung | Ergebnis |
|---|---|
| `api_profiles` Count über den Staff-Test | **7 → 7**, keine unerlaubte Persistenz |
| Staff-Create | kein `apiProfileId` in der Response, nichts in DynamoDB |
| Status des Testprofils nach Restore | `ACTIVE` (Ausgangszustand) |
| `mays-ris-dev-credentials` | **0** — keine Credential-Erzeugung |
| `mays-ris-dev-entitlements` | **0** — keine Entitlement-Änderung |

Keine direkten DynamoDB-Writes durchgeführt; alle Leseprüfungen read-only.

## 9. F — Audit-Beobachtung (nur lesend)

8 `apiprofile-audit`-Zeilen im Fenster: 7× `outcome=success`, 1× `outcome=denied`.

Erfolgreich auditiert:

| Aktion | Ergebnis |
|---|---|
| `profile-create` (Owner) | ✅ |
| `profile-update` (Owner, Admin) | ✅ |
| `profile-transition to=ACTIVE` (Admin) | ✅ |
| `profile-transition to=DISABLED` (Staff, mit Reason) | ✅ |
| `profile-transition to=ACTIVE` (Admin, Restore) | ✅ |

**Wesentlicher Befund:** Der Staff-Create-Versuch wird jetzt korrekt protokolliert:

```
action=profile-create outcome=denied actor=<staff> reason=staff-no-create
```

Das ist **genau der in Gate 01 dokumentierte Befund, der sich nicht mehr reproduziert.** Vor dem Fix erschien der Missbrauch als `outcome=success` mit `createdBy.role=owner`. Der Audit-Integritätsmangel ist auf diesem Pfad damit **behoben** — als Folge der Rollen-Erkennung, nicht durch eine Audit-Änderung.

**Keine Secrets im Audit:** Pattern-Scan über alle Audit-Zeilen auf `eyJ…`-JWTs, `Bearer`, Passwort-/Secret-Begriffe → **kein Treffer**.

Die weiterhin offene Audit-Design-Frage (Schema, fehlende Violation-Events, `createdBy.role`-Semantik) bleibt **separat OPEN** und wurde nicht berührt.

## 10. G — AWS-Mutation (Scope-Einhaltung)

Zulässig und erfolgt: **ausschließlich** Anlage, Attribut-/Gruppenzuweisung und Deaktivierung der drei synthetischen Cognito-Fixtures.

Unverändert nachgewiesen:

| Bereich | Befund |
|---|---|
| Lambda `CodeSha256` | `ECemCxwAOv0fNo3OeAkxjpT3Eg+Xyl9LZB61h3R4VvQ=` — identisch |
| Agent Role-Policies | 8 |
| ESM | UUID `7cc946b9…`, `Enabled`, Batch 5 — ESM-Tags unangetastet |
| Gateway | 27 Routen |
| Cognito Config | `AutoVerifiedAttributes ["email"]`, Gruppenstruktur unverändert |
| `mays-ris-lambda-policy` | **nicht angefasst** |
| Terraform | nur `plan -lock=false` (read-only) → `No changes.`; **kein** Apply |
| IAM / SQS / DynamoDB / S3 | keine Mutation |

## 11. H — Cleanup und bestehendes Profil

| Punkt | Status |
|---|---|
| `v3-owner-synth`, `v3-admin-synth`, `v3-staff-synth` | `CONFIRMED`, `Enabled=false` |
| Passwörter / Tokens | `shred -u`, tmp-Verzeichnis gelöscht |
| `aprof_352e4133…` | **nicht gelöscht**, wie angewiesen |
| Bereinigung des Testprofils | über den **Admin-Produktpfad** wiederhergestellt (`ACTIVE`), keine DDB-Löschung |

## 12. Erfolgskriterien

| # | Kriterium | Status |
|---|---|---|
| 1 | Owner funktioniert | ✅ |
| 2 | Product Admin (`admins`) korrekt erkannt | ✅ |
| 3 | Zuvor blockierte Admin-Aktion funktioniert live | ✅ `PENDING → ACTIVE` = 200 |
| 4 | Staff (`Staff`) korrekt erkannt | ✅ |
| 5 | Staff kann **keinen** APIProfile-Create | ✅ 403, keine Persistenz |
| 6 | Staff kann keine unzulässige Owner/Admin-Aktion | ✅ |
| 7 | Erlaubte Staff-Support-Funktion funktioniert | ✅ Read mit Reason = 200 |
| 8 | Keine unerlaubte Persistenz | ✅ Count 7 → 7 |
| 9 | Keine unerlaubte Entitlement-/Credential-Änderung | ✅ beide 0 |
| 10 | Keine AWS-Adminrechte aus RIS-Rollen | ✅ |
| 11 | Audit ohne Secrets | ✅ |
| 12 | Authorization-Fix unverändert | ✅ Hash identisch |
| 13 | Keine Infrastrukturmutation | ✅ nur Cognito-Fixtures |
| 14 | Fixtures bereinigt | ✅ alle deaktiviert, Secrets vernichtet |

**14/14 erfüllt → GREEN.**

## 13. Offene Punkte

1. **403 vs. 404 bleibt formal OPEN**, liefert aber einen neuen Befund: korrekt erkannter Staff erhält beim Create **403** (vorher 404, weil er als Owner galt). Die Anti-Oracle-Semantik wurde **nicht** geändert — die Änderung ist eine *Folge* der korrekten Rollen-Erkennung. Die Gate-Vorgabe wurde eingehalten.
2. **Staff kann fremde Profile mit Reason deaktivieren** — contract-konform (`api_profiles.py:477-481`), aber eine reale Kompetenz, die bewusst zu dokumentieren ist.
3. **Malformed/unknown Group online ungetestet** (lokale Abdeckung in FIX-02 vorhanden). Für einen Live-Nachweis wäre ein weiterer Fixture mit kaputtem Group nötig — nicht ohne neue Mutation möglich.
4. **Audit-Design-Frage** bleibt offen. Der Staff-Deny wird jetzt korrekt auditiert, das Schema ist aber unverändert.
5. **`aprof_352e4133…`** bleibt stehen — die Bereinigung ist jetzt über den funktionierenden Admin-Pfad **möglich** und sollte in einem separaten Cleanup-Gate erfolgen.
6. **Security-Fix-02** ist mit diesem Gate GREEN abgeschlossen.
