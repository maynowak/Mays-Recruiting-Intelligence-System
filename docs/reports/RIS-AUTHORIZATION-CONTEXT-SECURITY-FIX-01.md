# RIS-AUTHORIZATION-CONTEXT-SECURITY-FIX-01 — Authorization-Context Fix

STATUS: **RED / HOLD** — **permissiver Staff-Pfad live nachgewiesen.** Gate-Anweisung: HARD STOP **vor** Codeänderung. Es wurde **kein** Code geändert.

- Datum: 2026-10-04 UTC
- Branch/HEAD: `main`, `75d8de7`
- Account/Region/Workspace: `240571105849` (`user/Mayaws`) / `eu-central-1` / `mays-ris`
- **AWS-Mutation: keine Produktmutation.** Nur 2 synthetische Cognito-Fixtures (angelegt, dann deaktiviert) und ein daraus entstandenes APIProfile in `mays-ris-dev-api-profiles`.

## 1. Root Cause (aus P19, kontrollierter A/B)

```
Cognito User -> cognito:groups = ["admins"]  (native Liste im Token)
             -> API Gateway JWT Authorizer
             -> requestContext.authorizer.jwt.claims  = "[admins]"   (STRING)
             -> _extract_user_context: split(",") statt json.loads
             -> groups = ["[admins]"]
             -> "admins" in groups == False
             -> _is_admin() == False  -> Admin-Zugriff faellt falsch fehl (404)
```

Gateway, Authorizer, Route, Lambda, Integration und Dispatch sind im P19-A/B als Ursache ausgeschlossen. Die Kette Token-Liste → Handler-String ist beidseitig belegt; zwischen API Gateway und Handler existiert kein weiterer Code, der den Claim verändern könnte.

## 2. Rollenmodell — Bestätigung

| Rolle | Quelle | Bedeutung |
|---|---|---|
| **RIS Product Admin** | Cognito-Gruppe `admins` | ausschließlich RIS-Produktadministration gemäß Product-Contract. **Keine** AWS-Rechte. |
| **RIS Owner/User** | normale Cognito-User ohne Gruppe | eigene, im Contract freigegebene Funktionen. **Keine** automatische Hochstufung. |
| **RIS Staff** | Cognito-Gruppe `Staff` | eingeschränkte Supportrolle. Keine allgemeine Administration, kein Create, **keine** AWS-Rechte. |
| **AWS-/Deployment-Administration** | Deployment-Kontext `mayaws` | **keine** RIS-Produktrolle. Administration ausschließlich über AWS Console, AWS IAM, Terraform, Installer. |

Vertraglich unverändert: `admins` = Product Admin, `Staff` = Staff, `Admin` = deprecated Alias (nicht verwendet), `mayaws` = AWS-Kontext. Keine neue Rolle, keine Cognito-Gruppe umbenannt oder angelegt, keine AWS-Rolle aus einer RIS-Gruppe abgeleitet.

**Die RIS Product API stellt keine AWS-Administrationsfunktion bereit und wird auch nach diesem Gate keine bereitstellen.**

## 3. Staff-Sicherheitsvorprüfung — ERGEBNIS: PERMISSIV

Fixtures: `p20-sec-staff` (Gruppe `Staff`), `p20-sec-owner` (keine Gruppe), identischer synthetischer Tenant, beide inzwischen deaktiviert.

Handler-Sicht auf den Claim: `GET /me` → `groups: []`. Der `Staff`-Claim erreicht den Handler also **ebenfalls** stringifiziert (`"[Staff]"` → `["[Staff]"]`), `_is_staff` ist damit `False`.

### 3.1 Gefundene permissive Pfade

| # | Staff-Versuch | Contract-Erwartung | **Tatsächlich** | Bewertung |
|---|---|---|---|---|
| 1 | `POST /v1/apiprofiles` | **403** | **201** + `apiProfileId` | 🔴 **PERMISSIV** |
| 4a | `GET` eigenes (unzulässig erstelltes) Profil ohne reason | verweigert | **200** | 🔴 **PERMISSIV** (Folge von 1) |

**Beleg für #1:** Profil `aprof_352e41330c42441b` wurde in DynamoDB **persistiert** (`name=p20-staff-should-not-exist`, `status=PENDING`, `createdBy.role=owner`).

**Ursache:** `_is_staff` ist `False`, der Staff-User wird als normaler Owner behandelt, und `create_profile` nimmt damit den Owner-Pfad (`api_profiles.py:272-275`: `if _is_staff(actor) and not _is_admin(actor)` greift nie).

### 3.2 Audit-Integrität — zusätzlicher Befund

Der Staff-Create wurde auditiert als:

```
apiprofile-audit … action=profile-create outcome=success owner=<staff-sub> profile=aprof_352e4133…
```

`outcome=success`, **kein** `denied`-Eintrag, und `createdBy.role=owner` statt `staff`. **Die Vertragsverletzung ist im Audit-Trail nicht als solche erkennbar** — sie erscheint als regulärer Owner-Create. Eine nachträgliche forensische Auswertung des Audit-Logs allein würde den Befund nicht zeigen.

### 3.3 Nicht-permissive Pfade (durch denselben Defekt *verweigert*)

| # | Staff-Versuch | Erwartung | Tatsächlich | Bewertung |
|---|---|---|---|---|
| 2a | `GET` fremdes Profil (ohne reason) | verweigert | 404 | ✅ keine Leckage |
| 2b | `GET` fremdes Profil **mit** reason | erlaubte Support-Funktion | **404** | 🔴 **ZU ENG** |
| 2c | `PATCH` fremdes Profil | verweigert | 404 | ✅ |
| 3a | `POST status=DISABLED` fremd | 403 | 404 | ✅ (404 statt 403, neutral) |
| 3b | `POST status=ACTIVE` fremd | 403 | 404 | ✅ |
| 3c | `POST status=REVOKED` fremd | 403 | 404 | ✅ |

### 3.4 Bewertung

Der Defekt wirkt **bidirektional**:

- **Permissiv:** Staff kann APIProfile anlegen, obwohl der Contract es verbietet — mitpersistierter Wirkung und unauffälligem Audit-Eintrag.
- **Zu eng:** Die im Contract vorgesehene Staff-Supportfunktion (Lesen mit Reason) ist **nicht erreichbar**, weil Staff nicht erkannt wird.

Damit ist die Gate-Bedingung erfüllt:

> „Wenn ein permissiver Staff-Pfad gefunden wird: RED/HOLD und HARD STOP vor Codeänderung."

**Es wurde keine Codeänderung vorgenommen.** `git status` ist tracked clean.

## 4. Codeänderung — KEINE

Der Fix in `_extract_user_context` (JSON-Parsing des `cognito:groups`-Claims, Behandlung der Formen `None`, `[]`, `["admins"]`, `"[admins]"`, Mehrfachgruppen, leerer String, unerwarteter Typ, ohne permissive Fallback-Rolle) ist **analysiert, aber nicht ausgeführt**.

Die Gate-Anweisung ist eindeutig: der Staff-Befund muss **vor** der Änderung dokumentiert sein. Grund: eine Korrektur verschiebt das Verhalten in die sichere Richtung und macht den permissiven Zustand **nicht mehr reproduzierbar** — die Vorher-Evidenz wäre verloren. Zusätzlich betrifft derselbe Codepunkt live Credential-Routen (P16) und Introspection.

### Erwartete Wirkung des Fixes (nicht ausgeführt)

| Vorher | Nachher (erwartet) |
|---|---|
| Staff Create → 201 | 403 (vertragskonform) |
| Staff Read mit Reason → 404 | 200 (Supportfunktion erreichbar) |
| Product Admin → 404 auf alle Admin-Pfade | korrekte Admin-Rechte gemäß Contract |
| Owner → unverändert funktionsfähig | unverändert |

## 5. Tests

**Keine neuen Tests in diesem Gate** — Codeänderung unterblieben. Kein Testfile angefasst, keine RegressionSuite ausgelöst (kein Code geändert).

## 6. Regressionsprüfung

**Nicht durchgeführt** (kein Code geändert). Bei der späteren Umsetzung sind zu prüfen: `/me`, `/me/profile`, `/platform`, `/agents`, APIProfile-Management, Credential-Management, Introspection sowie alle übrigen Aufrufer von `_extract_user_context`. Ausdrücklich zu bestätigen: eine korrigierte Product-Admin-Identität darf **nicht** als M2M-Credential akzeptiert werden — Human-JWT und opaker Bearer-Credential bleiben strikt getrennt.

## 7. Live-Testmatrix

| Bereich | Ergebnis |
|---|---|
| A) Owner | nicht erneut gefahren (in P19 vollständig grün, §9 dort) |
| B) Product Admin | **nicht verifizierbar** — Admin-Rolle nicht erkannt (P19-Befund) |
| C) Staff | **durchgeführt, permissiver Pfad gefunden** (§3) |
| D) Unbekannte/fehlerhafte Gruppe | nicht durchgeführt — wird erst nach dem Fix sinnvoll prüfbar |

## 8. AWS Mutation

| Art | Umfang |
|---|---|
| Produktcode / Lambda / Gateway / IAM / Cognito-Config / Terraform | **keine** |
| Cognito Fixtures | 2 synthetische User angelegt, **beide deaktiviert** |
| Daten | 1 durch Staff **unzulässig erzeugtes** Profil (`aprof_352e4133…`, PENDING) |
| Secrets | Passwörter und Tokens `shred -u`; tmp-Verzeichnis gelöscht |

## 9. Cleanup / offener Zustand

| Punkt | Status |
|---|---|
| `p20-sec-staff`, `p20-sec-owner` | `CONFIRMED`, `Enabled: false` — nicht gelöscht |
| `aprof_352e41330c42441b` (Staff-Missbrauch) | **PENDING, bleibt stehen.** Cleanup per API unmöglich: `DELETE` ist nicht implementiert, `REVOKE`/`DISABLED` erfordern die Admin-Rolle, die derzeit nicht funktioniert; ein direkter DDB-Write wäre ein Eingriff außerhalb des Gates. |
| `api_profiles` Count | 5 — 4 aus P19 (A/B + E2E), 1 aus diesem Gate |
| Weitere P19-Profile | `aprof_31f3fa09…` (ACTIVE), `aprof_1bbc0fffe66c4f66`, `aprof_49e8837e…`, `aprof_f64dc640…` (PENDING) |

**Sicherheitsbewertung des Rückstands:** alle 5 Profile sind synthetisch, gehören deaktivierten Usern und sind tenant-gebunden. Das risikoreichste ist `aprof_352e4133…`, weil es durch einen Contract-Verstoß entstanden ist — jedoch `PENDING` (nicht `ACTIVE`), also nicht nutzbar und ohne Credential-Bindung. Kein akutes Risiko, aber ein sichtbarer Beleg, dass der Fix überfällig ist.

## 10. Offene Punkte

1. **PERMISSIVER STAFF-PFAD (blockierend).** Staff kann APIProfile anlegen. Fix ausstehend.
2. **Audit-Integrität:** Contract-Verletzungen erscheinen als `outcome=success`. Ein detektierender Audit-Hinweis wäre zu erwägen (eigene Aufgabe, nicht in diesem Gate).
3. **Staff-Supportfunktion unerreichbar** (Read mit Reason → 404). Wird durch denselben Fix mitbehoben.
4. **Product Admin live nicht verifizierbar** — gleiche Ursache.
5. **Rollenverwechslung ausgeschlossen:** Der Deployment-Kontext `mayaws` ist im Test ausschließlich für AWS-Reads verwendet worden. Es wurde **keine** AWS-Rolle, IAM-Berechtigung oder Infrastruktur-Funktion aus einer RIS-Gruppe abgeleitet. Die RIS Product API bietet keine AWS-Administration.
6. **403 vs. 404:** Bei Rollenverletzungen liefert der neutrale Pfad durchgängig 404 statt 403. Das ist die etablierte Anti-Oracle-Konvention; die Gate-Tabelle nennt 403. Bewertung als konsistent, aber die Gate-Erwartung „403" ist damit nicht literal erfüllt — bei einem Staff, der korrekt erkannt würde, liefert `create_profile` weiterhin 404 (neutral), nicht 403. **Diese Diskrepanz ist vor dem Fix zu entscheiden**, sonst bleibt sie bestehen.
7. **Kein P17-Rerun, kein P20-Start** in diesem Gate.

## 11. Status

**RED / HOLD.** Der Gate-Stoppzustand ist eingetreten: ein permissiver Staff-Pfad wurde live nachgewiesen, die Codekorrektur ist bewusst unterblieben. `admins` wird weiterhin nicht als RIS Product Admin erkannt; Owner funktioniert unverändert; Staff erhält unzulässige Rechte; aus einer RIS-Rolle entsteht keine AWS-Administration.
