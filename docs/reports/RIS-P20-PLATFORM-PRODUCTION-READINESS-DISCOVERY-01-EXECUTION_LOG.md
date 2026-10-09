# RIS-P20-PLATFORM-PRODUCTION-READINESS-DISCOVERY-01 — Execution Log

STATUS: **YELLOW (Discovery abgeschlossen, kein Implementierungsbedarf im Kern)** — Der funktionale Platform-Kern ist vollständig live belegt. Es existiert **kein** produktiver Blocker. Die offenen Befunde sind Vertrags-/Dokumentationsdrift (14 von 28 Routen), ein toter Health-Endpunkt und Retention-/Governance-Lücken. Empfehlung: **Option D**.

- Datum: 2026-10-05 UTC
- Git HEAD / origin/main: `631d5844dc160f12429926f152a2a9f26ea58194` (identisch)
- Account/Profil/Region/Workspace: `240571105849` / `mayaws` / `eu-central-1` / `mays-ris`
- **DISCOVERY-ONLY**: keine AWS-Mutation, keine Codeänderung, kein Commit, kein Push

---

## 1. Baseline

Als verbindliche Baseline verwendet (Commit-Historie + Live-Zustand):

| Gate | Commit | Status | Beitrag |
|---|---|---|---|
| Discovery-07 | `365b337`, `efc962e` | GREEN / HARD STOP | Optionsentscheidung D, Bestandsaufnahme Cognito/Catalog |
| B4 Catalog Writer | `40f56a4` | GREEN | Writer + Seeder (später ersetzt) |
| B4 Terraform Extension | `a8fec1b` | GREEN | Terraform = Source of Truth für `reference_agent` |
| B3 Machine Entry Point | `3551a92`, `01853ff` | GREEN | `verify_api_credential()` produktiv verdrahtet |
| B5 Entitlement Provisioning | `ca8e39f`, `a31abee` | GREEN | Foundation-Entitlement, Runtime read-only |
| P17 Credential Lifecycle E2E | `ebcbabf`, `631d584` | GREEN | Lifecycle inkl. Rotation/Disable/Revoke/Isolation |

Live-Zustand zum Discovery-Zeitpunkt (read-only):

| Ressource | Wert |
|---|---|
| Gateway | 28 Routen, 1 Authorizer (JWT, iss+aud, keine Scope-Prüfung) |
| Lambda | `mays-ris-dev-agent`, `VAj4iLO07i92oYiI64lbKQB8Erf2/xRR58SuowrGPuU=` |
| ESM | Enabled, Batch 5 |
| IAM Role Policies | 8 |
| Cognito User Pool | 14 User |
| `terraform plan` | **"No changes."** → kein Drift |

Die bestätigte Architektur wird **nicht in Frage gestellt**: Human → Cognito JWT → Human API und Machine → opaque `ris_` → APIProfile → Entitlement → Agent Catalog → Execution → COMPLETED. Discovery hat **keinen** konkreten Widerspruch dazu gefunden.

---

## 2. Platform Inventory

| Bereich | Komponente | Status | Evidenz |
|---|---|---|---|
| **Identity** | Cognito User Pool | GREEN | `eu-central-1_dgQXgwUbv`, 14 User, AutoVerified `email`, kein IdP, keine Hosted-UI-Domain |
| | Human JWT | GREEN | 26 Routen JWT-Autorisiert; `/me`, `/platform`, `/v1/introspection` 200 (P17-10) |
| | Groups | GREEN | 7 Gruppen; produktiv wirksam nur `admins` und `Staff`; 5 leer; **keine** Gruppe `Role`/`Precedence` |
| | UserProfile | GREEN | `POST /me/profile` 201, `GET` 200, `PUT` 200; TTL ENABLED; **kein** Auto-Provisioning bei Reads (Contract) |
| | Tenant | GREEN | `custom:tenant_id` im ID Token; `_check_tenant` erzwingt Grenze, cross-tenant nur Admin+`reason` |
| **APIProfile** | CRUD | GREEN | create 201, GET 200, PATCH 200; Name UNIQUE pro Owner; Idempotency-Key |
| | Lifecycle | GREEN | PENDING→ACTIVE→DISABLED→ACTIVE→REVOKED; `_ALLOWED[REVOKED]=frozenset()` |
| | Owner/Admin/Staff | GREEN | Staff darf **nicht** anlegen; nur Admin für andere; Owner-Felder clientRef/expiresAt werden ignoriert (Spoof-Immunität) |
| | Selection | GREEN | `resolve_selection` default/explicit; fremder Header löst nicht auf (404) |
| | Isolation | GREEN | Tenant-Pflicht; P17: 0 Cross-Tenant-Leak |
| **Credentials** | Issue | GREEN | `expiresAt` Pflicht; Server-Rollenkette |
| | List/Get | GREEN | 19 Safe-Metadata-Felder, **kein** Secret (P17-10) |
| | opaque Secret | GREEN | `ris_` + 47 Zeichen, SHA-256-Digest, einmalige Ausgabe, nicht rekonstruierbar |
| | Disable/Enable | GREEN | live 202→disable→403→enable→202 |
| | Revoke | GREEN | live →403; enable danach 409 (terminal) |
| | Rotate | GREEN | A→REVOKED, B→ACTIVE, `rotationOf`, gleiche Profilbindung; altes Secret unrekonstruierbar |
| | Expiry | GREEN | abgelaufen →403, Audit `credential.expired outcome=observed` |
| | Audit | GREEN | created/viewed/disabled/enabled/rotated/revoked/expired + verification authorized/forbidden |
| **Entitlements** | Schema | GREEN | PK `entitlementId`, GSI `gsi-user` + `gsi-agent`, TTL ENABLED |
| | Provisioning | GREEN | Terraform-managed Foundation (opt-in Variable), Default `{}` |
| | Zeitfenster | GREEN | `validFrom`/`validUntil`; live abgelaufen →403 |
| | Agent-Bindung | GREEN | `_row_matches` auf `agentId`; falscher Agent →403 |
| | Runtime Read | GREEN | `DynamoDBEntitlementResolver` Query `gsi-user`; IAM nur GetItem/Query/BatchGetItem |
| | Foundation Fixture | GREEN | `reference_agent`; Aufräumen nur per Terraform |
| **Agent Catalog** | Terraform SoT | GREEN | `aws_dynamodb_table_item.agent_catalog_seed`, keine Runtime-Schreiblogik (Test-Guard) |
| | Read Path | GREEN | `_init_catalog` + `CatalogAdapter`, fail-closed bei unbekanntem Status |
| | Status | GREEN | `normalize_agent_status` → unbekannt = **nicht** registriert |
| | Catalog/Registry-Trennung | GREEN | Registry In-Memory (Coldstart), Catalog persistent; Trennung im Code + Dokumentation explizit |
| **Machine API** | Entry Point | GREEN | `POST /v1/m2m/agents/{agentId}/execute`, `AuthorizationType NONE`, eigene Route, eigene Integration |
| | Credential Verification | GREEN | `verify_api_credential()` produktiv (handler.py:831); Schritt 13/14 live wirksam |
| | Agent Routing | GREEN | `agent_id` aus Pfad, nie geraten; `/v1/m2m/` erfasst keine Fremdpfade |
| | Execution | GREEN | 202 → WorkItem → SQS → `reference_agent` → **COMPLETED** (Worker-Log) |
| | Audit | GREEN | `action=verification outcome=authorized|forbidden` mit credentialId/apiProfileId/tenant |
| **Human API** | `/me`, `/platform`, `/agents`, `/v1/introspection` | GREEN | je 200 mit JWT (P17-10) |
| | `/health` | **RED** | **404** — Route deployed, kein Handler-Zweig (Befund H, §4) |

---

## 3. Authorization Matrix

Nur **implementierte** Semantik. Belege aus Code + Testnamen.

| Funktion | Owner | Staff | RIS Product Admin | Machine (`ris_`) | Evidenz |
|---|---|---|---|---|---|
| eigenes Profil lesen | ✅ | ✅ | ✅ | n/a | `test_03_owner_reads_own`, `test_03_admin_own` |
| eigenes Profil anlegen | ✅ | ❌ **verboten** | ✅ | n/a | `test_01_owner_own_profile`, `test_02_staff_create_denied` |
| fremdes Profil lesen | ❌ 404 | ⚠️ nur mit `reason` | ✅ (cross-tenant nur mit `reason`) | n/a | `test_13_read_foreign`, `test_17_foreign_profile_denied` |
| fremdes Profil anlegen | ❌ | ❌ | ✅ | n/a | „only admin creates for others" |
| eigenes Profil ändern | ✅ (nur Name/Description) | ✅ | ✅ | n/a | `test_05_owner_updates_name`; clientRef/expiresAt ignoriert |
| Credential ausstellen | ✅ (eigenes Profil) | ❌ **nie** | ✅ | n/a | `test_05_staff_issue_denied`, P14 `_owner_self` |
| Credential listen/lesen | ✅ (eigenes) | ✅ | ✅ | n/a | `test_get_404_cross_profile` |
| fremdes Credential | ❌ 404 | ❌ 404 | ✅ | n/a | `test_404_owner_foreign` |
| Credential disable/enable | ✅ eigenes | ✅ eigenes (disable mit `reason`) | ✅ | n/a | `test_staff_disable_with_reason`, `test_staff_no_revoke` |
| Credential revoken | ✅ eigenes | ❌ **nie** | ✅ | n/a | `test_staff_no_revoke` |
| Credential rotieren | ✅ eigenes | ✅ eigenes | ✅ | n/a | `test_rotate_201_revokes_old` |
| **Machine Execute** | ❌ (401, JWT ist kein Credential) | ❌ | ❌ | ✅ | live 401 / live 202 (P17-10) |
| Entitlement nutzen | n/a | n/a | n/a | ✅ nur wenn Entitlement für user+tenant+agent | live 403 ohne, 202 mit |
| Agent nutzen | ❌ | ❌ | ❌ | ✅ nur `ACTIVE` im Catalog | live `agent-not-executable` |

**Rollenabgrenzung (explizit, wie gefordert):**
- **RIS Product Admin** = Cognito-Gruppe `admins` (`ADMIN_GROUP`, `api_profiles.py:38`). Rein produktrechtlich.
- **AWS Administrator / `mayaws`** = IAM-Berechtigung. **Keine** Produktrolle. Wird in diesem Gate ausschließlich als Betriebs-/Discovery-Kontext verwendet.
- **Staff** = Cognito-Gruppe `Staff`, bewusst **eingeschränkter** als Admin (kein Anlegen, kein Revoke, kein Issue).

---

## 4. API Contract Findings

### 4.1 Schichtenabgleich

| Schicht | Befund |
|---|---|
| **Terraform → Gateway** | ✅ **vollständig konsistent.** 21 Routen im `api`-Modul + 4 im `orders_reader`-Modul = 25; live 28. Differenz exakt die 2 `NONE`-Routen der nachfolgenden Gates (`/health` ist im api-Modul, `/v1/m2m/...` ebenfalls). **Keine in Terraform fehlende und keine verwaiste Live-Route.** |
| **Gateway → Handler** | ⚠️ orders-Routen bedienen korrekt die **zweite** Lambda (`reader`-Integration) — kein Defekt. Agent-Routen alle erreichbar. |
| **Gateway → Doku** | 🔴 **Befund G (neu):** `docs/api/API-STANDARD.md` §1 listet nur /health, /platform, /me, /me/profile, /agents, /orders*, /me/documents*. **14 von 28 Live-Routen sind nicht dokumentiert** — darunter die **gesamte** `/v1/apiprofiles`-Familie (11 Routen), `/v1/introspection` und die **Machine-Route**. |
| **Statuscodes** | ✅ Stichprobe deckungsgleich (`POST /me/profile` 201, `PUT /me/profile` 200, `GET /agents` 200). |

### 4.2 Befund H (neu): `/health` ist deployed, aber nicht implementiert

| Nachweis | Ergebnis |
|---|---|
| Terraform | `terraform/modules/api/main.tf:44-47` — `route_key = "GET /health"`, `target` = **agent**-Integration, `authorization_type = "NONE"` |
| Handler | `grep -in "health" lambda/handler.py` → **0 Treffer**. Kein Zweig. |
| Live | **HTTP 404** `{"error": "Not found"}`, dreifach reproduziert |
| Ursprung | Der Request kommt an: CloudWatch-Log zeigt `API request: GET /health`; der Handler fällt in seinen generischen 404 |
| Doku | `API-STANDARD.md` §1 verspricht `GET /health | agent | 200 (NONE)` |

**Klassifikation: Betriebsdefekt + Doku-Widerspruch.** Ein `/health`-Pfad auf einem Infrastruktur-Health-Check-Pfad, der 404 liefert, ist für einen Load Balancer/ECS-Target-Group **deployment-blockierend** (ungesundes Target). Aktuell wird kein solcher Health-Probe verwendet, deshalb ist es heute kein Ausfall, sondern eine latente Falle.

### 4.3 Doku-Drift im Selbstbericht der Doku

`API-STANDARD.md` §1-Titel behauptet „**JWT ausser /health**" — live gibt es **zwei** `NONE`-Routen (`/health`, `/v1/m2m/agents/{agentId}/execute`).
`API-STANDARD.md` §6 behauptet „API-Doc vs Runtime: keine Widersprüche festgestellt (Codes/Routen/Claims code-geprüft)" — das ist seit B3-08 überholt.

---

## 5. Security Findings

Nur produktive Pfade, kein erneutes IAM-Vollaudit.

| # | Befund | Status |
|---|---|---|
| S1 | **Human/Machine-Auth-Boundary sauber getrennt.** Machine-Route `AuthorizationType NONE` (live verifiziert, `AuthorizerId: null`), JWT-frei; 26 Human-Routen JWT-geschützt. Live: Machine-Route mit JWT → 401, `/me` ohne Auth → 401. **GREEN.** |
| S2 | **APIProfile-Isolation:** Tenant-Pflicht persistiert, cross-tenant nur Admin + `reason`, fremd → 404 (neutral, kein Orakel). **GREEN.** |
| S3 | **Tenant-Isolation:** P17-10 belegte 0 fremde credentialId, 0 Secret, 0 fremde Profile. **GREEN.** |
| S4 | **Revocation wirkt per Request:** disable/enable/revoke jeweils im nächsten Request beobachtet; kein Cache liefert alten Positivzustand. **GREEN.** |
| S5 | **Entitlement + Catalog-Prüfung beide wirksam:** je ein Glied entfernen → denial (Test `test_authorization_requires_the_whole_chain`). **GREEN.** |
| S6 | **Audit vorhanden und secret-frei:** 553 Logzeilen Scan → 0 Treffer für `ris_`, `Authorization`, `Bearer`, JWT-Muster, `password/secret/token`. **GREEN.** |
| S7 | **Secret-Handling:** einmalige Ausgabe, Digest-Lookup, nicht rekonstruierbar, auch nach Rotation. **GREEN.** |
| S8 | **IAM Least Privilege:** Runtime auf entitlements nur GetItem/Query/BatchGetItem; Provisionierung ausschließlich über Terraform-Identity; keine Wildcards in den Diff-Gates. **GREEN.** |
| S9 | **Error-Semantik:** 401/403/503 getrennt und korrekt; Store-Ausfall nie als 401/403. **GREEN.** |
| S10 | **Inkonsistente Auth-Oberfläche:** §1-Doku vs. 2×`NONE` (siehe 4.3). **YELLOW (Doku).** |
| S11 | **`/health` 404** (siehe 4.2). **RED (Betrieb).** |

**Kein offener Autorisierungs- oder Sicherheitsbefund, der produktive Nutzung verhindert.**

---

## 6. Privacy / Retention Findings

Keine Rechtsfristen erfunden. Faktische Bestandsaufnahme.

| Data | Zweck | Actor/Owner | Storage | Retention | Deletion | Evidenz | Status |
|---|---|---|---|---|---|---|---|
| UserProfile | Bewerberprofil | Human (`sub`) | DDB `user-profile`, TTL `expiresAt` ENABLED | TTL vorhanden | kein Prod-Löschpfad | 1 Restzeile aus Gate 03 (synthetische E-Mail) | **TBD** |
| APIProfile | Maschinenprofil-Zugriff | Owner (`ownerUserId`+`tenantId`, pseudonym) | DDB `api-profiles`, **TTL DISABLED** | **unbegrenzt** | **kein Löschpfad** | 17 Zeilen, 10 REVOKED aus Testgates | **OFF** |
| Credentials | M2M-Zugang | Owner/Profil gebunden, Secret nur als Digest | DDB `credentials`, **TTL DISABLED** | **unbegrenzt** | **kein Löschpfad** | 28 Zeilen, 28 REVOKED | **OFF** |
| Entitlements | Agent-Berechtigung | Nutzer (`userId`+`tenantId`) | DDB `entitlements`, TTL ENABLED | TTL + Terraform-Lifecycle | `delete_entitlement` existiert, **0 Aufrufer** | 0 Zeilen | **TBD** |
| AgentCatalog | Plattform-Metadaten | Plattform | DDB `agent-catalog`, TTL ENABLED | Terraform SoT | Terraform destroy | 1 Zeile (`reference_agent`) | **GREEN** |
| WorkItems | Ausführungsbeleg | Maschine + Profil | DDB `work-items`, TTL ENABLED | 30 Tage (`expiresAt`) | TTL | 14 Zeilen | **GREEN** |
| Offers | nicht genutzt | — | DDB `offers`, TTL DISABLED | n/a | — | 0 Zeilen | **n/a** |
| Audit (CloudWatch) | Nachvollziehbarkeit | Plattform | CW Logs | 14 Tage (Lambda) / 7 Tage (Reader) | automatisch | live verifiziert | **GREEN** |

**Kernaussage:** Aktuell ist **kein echtes Personendaten-Privacy-Risiko** akut — die Plattform enthält ausschließlich synthetische Daten, und das einzige Feld mit Klarnamen (`email`, `firstName`, `lastName`) liegt in einer einzelnen Restzeile eines deaktivierten Testusers. **Aber:** APIProfile und Credentials wachsen unbegrenzt (TTL `DISABLED`), haben keinen Löschpfad und akkumulieren bei jedem Testgate (jetzt 45 REVOKED-Objekte aus 8 Gates). Das ist die einzige Lücke mit **wachsendem** Trend.

---

## 7. AWS / Terraform State (read-only)

| Ressource | Wert | Bewertung |
|---|---|---|
| `terraform plan` | **"No changes."** | kein Drift |
| Tabellen | 7 (siehe §2 Inventar) | — |
| Gateway | 28 Routen / 1 Authorizer | konsistent mit Terraform |
| Lambda | 1 Agent + 1 Reader | Hash unverändert seit B3-08 |
| IAM | 8 Policies | unverändert |
| SQS/ESM | ESM Enabled Batch 5 | unverändert |
| Cognito | 14 User, `LastModifiedDate 2026-10-02T18:31:08+02:00` | unverändert |

**Keine Mutation durchgeführt.**

---

## 8. Test Baseline

| Kennzahl | Wert |
|---|---|
| Gesamtsuite `tests/` | **8 failed, 890 passed, 8 skipped, 1 error** |
| Baseline-Identität | identisch zu P17-10 (8 failed, 865 passed) — Difference +25 neue P17-Tests, Fehlerlisten unverändert |
| Collection-Errors `installer/**` | 6 (getrenntes Projekt, eigene Importpfade: `installer.core`, `index`, `errors`, `state_machine`) |

**Bekannte Baseline-Fehler (nicht von diesem Gate verursacht, nicht verändert):**
- `test_agent_invocation`: `test_contract_mode_validation`, `test_contract_validation`
- `test_platform_handlers`: 5 (Entitlement-Validierung ×2, `test_me_extracts_groups`, `test_platform_with_custom_env`, `test_sqs_event_returns_200`)
- `test_reference_agent`: `test_valid_work_item`
- `test_processing_chain::test_handler` (Error) — Log: `Missing required field: tenantId`

Diese 9 Fehler sind **Altlasten seit Gate 01/02** und bestehen über alle Gates hinweg unverändert. Sie betreffen ausschließlich **Human-/Worker-Testpfade**, nicht die Machine-Chain (B3/B5/P17). Kein Test wurde verändert.

---

## 9. Open Issues — vollständige Klassifikation der bekannten Befunde

| ID | Befund | Klassifikation | Produktrelevant für P20? |
|---|---|---|---|
| **H** (neu) | `/health` deployed, nicht implementiert (404); Doku verspricht 200 | **Betriebsdefekt + API Contract** | **JA** — deployment-relevant (LB-Health-Check) |
| **G** (neu) | 14 von 28 Routen undokumentiert; §1-Titel „JWT ausser /health" falsch; §6 behauptet Widerspruchsfreiheit | **API Contract / Dokumentation** | **JA** — Integratoren haben keinen Vertrag für die Machine-API |
| **F** | Retention/Deletion für `api-profiles` und `credentials` nicht geregelt (TTL DISABLED, kein Löschpfad); 45 REVOKED-Objekte akkumuliert | **Governance / Hardening** | **JA, aber nicht als Blocker** — kein echtes Personenbezug-Risiko heute, wachsend |
| **A** | Produktweg erlaubt Issue mit `expiresAt` < now (201); Verification lehnt korrekt ab | **Product Policy** (fail-safe) | nein — Entscheidung, keine Lücke |
| **B** | `GET fremdes Profil/credentials` → 200 `{"items": []}`; Item/Profil → 404. Leak-Prüfung: 0 fremde IDs, 0 Secrets | **Anti-Oracle / API Contract** (fail-safe, inkonsistent) | nein — Konsistenz-Frage |
| **C** | `agent_version` liest aus `sources["catalog"]` (agentId→status-Map); `isinstance(catalog_item, dict)` ist für einen String immer `False` → toter Zweig, Default `1.0.0` greift immer | **Technical Debt** (harmlos) | nein |
| **D** | `grant_offer` / `withdraw_entitlement` / `put_entitlements_batch` ohne produktiven Aufrufer; keine Offer-Route; offers leer | **Future Feature** | nein — Kern funktioniert ohne |
| **E** | Offer-System (`create_offer`, `list_offers`) vollständig im Code, aber ohne Route/Provisionierung | **Future Feature** | nein |
| **I** (neu) | 6 **aktive** Baseline-Testprofile aus Gate 03/05 (`v3-owner-profile`, `p19-e2e-renamed` u. a.) bestehen weiter; alle 28 Credentials REVOKED | **Governance / Hardening** | Teil von **F** |
| — | 9 Baseline-Testfehler + 6 Collection-Errors | **Pre-existing Tech Debt** | nein — betreffen nicht die Machine-Chain |

---

## 10. Classification — Production Readiness je Komponente

| Komponente | Status | Begründung |
|---|---|---|
| Identity (Cognito, JWT, Groups, Tenant) | **GREEN** | produktiv, live belegt |
| UserProfile | **GREEN** | produktiv, live belegt, kein Auto-Provisioning |
| APIProfile | **GREEN** | CRUD + Lifecycle + Rollen + Isolation live belegt |
| Credential | **GREEN** | vollständiger Lifecycle live belegt (P17-10) |
| Entitlement | **GREEN** | Schema, Provisioning, Fenster, Bindung, Runtime-Read live belegt |
| Agent Catalog | **GREEN** | Terraform SoT, Read Path fail-closed |
| Machine API | **GREEN** | Entry Point, Verification, Routing, Execution bis COMPLETED |
| Human API | **GREEN** | alle geprüften Routen 200 |
| `/health` | **RED** | 404 trotz deployter Route (Befund H) |
| API Contract/Doku | **YELLOW** | 14/28 Routen undokumentiert, Titel + Selbstbericht veraltet (Befund G) |
| Privacy/Retention | **YELLOW** | Governance-Lücke bei den zwei wachsenden Tabellen (Befund F) |
| Build/CI | **DEFERRED** | CI prüft ausschließlich Terraform, kein pytest, kein Linter |

**Platform-Kern (§9):** Identity + UserProfile + APIProfile + Credential + Entitlement + Agent Catalog + Machine Execution + Human API = **vollständig funktionsfähig und live belegt**. Es fehlt kein Baustein für ein tragfähiges Produkt. Ich erfinde daher **keine** neuen Features für P20.

---

## 11. Empfehlung — genau ein P20-Schritt

### Option D — P20 API Contract / Documentation Gate

**Begründung, priorisiert:**

1. **`/health` ist der einzige Befund mit unmittelbarer Betriebswirkung.** Ein 404 auf einem Health-Check-Pfad macht ein LB/ECS-Target als „ungesund". Es ist klein (~ein Handler-Zweig), gehört aber in denselben Durchgang wie die Vertragsaufnahme: die Frage „was exponiert die Plattform wirklich?" ist genau die Frage, die beide Befunde aufwerfen.
2. **14 von 28 Routen sind undokumentiert — einschließlich der gesamten Machine-API, die P17 gerade validiert hat.** Ein Integrator hat derzeit keinen Vertrag für genau die Fläche, die B3/B5/P17 live bewiesen. Das ist kein Kosmetik-Thema: `API-STANDARD.md` §6 behauptet sogar Widerspruchsfreiheit, während sie real gegen die Doku driftet.
3. **Retention (F) ist wichtig, aber nicht der akute Blocker.** Es gibt heute kein echtes Personenbezug-Risiko (alle Daten synthetisch, ein einziger `user-profile`-Rest). Die Lücke wächst aber monoton (+45 REVOKED-Objekte über 8 Gates) und wird kritisch, sobald echte Bewerberdaten einziehen. Das ist ein **eigenes, bewusst terminiertes** Governance-Gate — nicht etwas, das man beiläufig in ein Doku-Gate mischt.

**Ausdrücklich verworfen:**
- **Option A (Implementation):** es existiert kein produktiver Blocker. Der Kern ist vollständig.
- **Option B (Hardening):** enthielte Retention und `/health` — aber die Dokumentationslücke bliebe und die Priorität wäre falsch gesetzt.
- **Option C (Privacy/Retention):** wird zum **unmittelbar folgenden** Gate empfohlen, sobald echte Daten erwartet werden. Heute der falsche erste Schritt.
- **Option E (Complete):** es existieren zwei belastbare, live verifizierte Befunde.

**Arbeitsumfang des empfohlenen Gates (nur als Empfehlung, hier nicht ausgeführt):** `/health` implementieren oder Doku berichtigen (Entscheidung dokumentieren); `API-STANDARD.md` auf alle 28 Routen inkl. Machine-Plane und korrekter Auth-Matrix bringen; §1-Titel und §6-Selbstbericht korrigieren; optional die Statuscode-Tabelle um `/v1/m2m` ergänzen. Kein Archrukturwechsel.

---

## 12. Bewusst nicht angefasste Punkte

- **Keine AWS-Mutation** — kein apply, kein DDB-Write, kein IAM, kein Cognito, kein Lambda, kein Gateway.
- **Keine Codeänderung**, kein Test verändert, kein Test geschrieben.
- **Kein Commit, kein Push** — Gate §12.
- **Keine Retention-/Delete-Implementierung**, keine Fristen erfunden.
- **Keine Entitlement-Management-Route**, kein Offer-Ausbau.
- **Keine Preis-/Billing-Logik.**
- **Keine Bewertung der 9 Baseline-Testfehler** über „sie sind alt" hinaus — sie bleiben als Pre-existing Tech Debt dokumentiert.

---

## 13. AI Audit

- `docs/AI_AUDITLOG.md` befolgt: Log **vor** der Analyse angelegt, Pflichtfelder vollständig, nur verifizierte Fakten, Evidence-Referenzen auf jede Aussage.
- **Eigene Werkzeugfehler, transparent:** mein erster Terraform↔Gateway-Vergleich meldete 5 Live-Routen „ohne Handler-Zweig" — das war ein zu grober Matcher; die orders-Routen bedienen korrekt eine zweite Lambda. Und die erste Regex-Suche nach einer OpenAPI-Spezifikation meldete „keine Datei", obwohl `jobsearch/openapi.yaml` existiert (fuer den externen Jobsearch-Dienst, nicht für die RIS-Platform — die inhaltliche Aussage blieb richtig, die Begründung war ungenau).
- **Befunde wurden gegen den Code und die Live-Runtime verifiziert**, nicht aus früheren Berichten übernommen: `/health` dreifach live getestet und im Lambda-Log bestätigt; die 14 undokumentierten Routen aus dem Gateway-Inventar abgeleitet; TTL-Status je Tabelle live abgefragt.
- **Keine Behauptung ohne Evidenz**: Jede Klassifikation in §9 nennt den konkreten Nachweis.

---

## 14. Entscheidung

**STATUS: YELLOW** — Discovery abgeschlossen. Kein produktiver Blocker; zwei belastbare Vertrags-/Betriebsbefunde, eine Governance-Lücke.

**Empfehlung: Option D — P20 API Contract / Documentation Gate.**
Begründung in einem Satz: Der Platform-Kern funktioniert vollständig, aber der einzige Health-Endpunkt der Plattform antwortet 404 (deployment-relevant für Load Balancer), und 14 der 28 exponierten Routen — die gesamte Machine-API — sind im kanonischen Vertragsdokument nicht beschrieben, dessen Selbstbericht dabei Widerspruchsfreiheit behauptet.

**Empfohlene Folge:** unmittelbar danach ein separates **Privacy/Retention-Gate** für `api-profiles` und `credentials` (TTL + Löschpfad), sobald echte Daten zu erwarten sind.

**HARD STOP** — keine Implementierung, keine AWS-Mutation, kein weiteres Gate.