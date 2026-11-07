# RIS-PARTNER-MULTI-ISSUER-DESIGN-01 — Architekturentscheidung

- **Datum:** 2026-11-05
- **Modus:** Analyse/Design, **keine AWS-Mutation, kein Apply, keine Provisionierung**
- **Ergebnis:** **Variante B (separater Gateway-Zugang) empfohlen**

---

## 1. Anforderung

RIS ist eine zentrale Plattform für mehrere unabhängige Partner mit eigenen Cognito-Pools. Die 36 Partner-Routen dürfen nicht an einen einzelnen Partner-Issuer gebunden werden. Gleichzeitig muss Mays-Jobsearch (Pool `ZURSMpD2O`, Client `5hb3…`) sicher angebunden werden, ohne den bestehenden RIS-Pool (`ojbmoiYGM`, Client `7ldh…`) zu verlieren.

---

## 2. Ist-Zustand (verifiziert)

| Element | Befund |
|---|---|
| API | `g6901and25` (`ris-dev-dev-api`), 70 Routen |
| Authorizer | 2 JWT-Authorizer: Human (`7ldh…`/`ojbmoiYGM`), M2M (`82ji…`/`ojbmoiYGM`) |
| Routenbindung | 65 Routen am Human-Authorizer, 1 am M2M |
| Partner-Routen | 36 Blöcke: 24 `partner_*`, 10 `applications_*`, 2 `privacy_*` |
| Handler | `_partner_profile_context` verlangt `token_use=access`, `client_id`, ACTIVE-Partner, Profil- und Tenant-Gleichheit, gültiges `X-Api-Credential` |
| Tenant-Auflösung | Registry `client_id → tenantId`, fail-closed, kein Default |
| JWT-Verifikation im Code | **keine** — ausschließlich API-Gateway; `requirements.txt` enthält keine JWT-/Krypto-Bibliothek |
| Surface-Gate | `PARTNER_SURFACE_ENABLED=false` (503) |

Wichtig: API Gateway erlaubt **pro Authorizer genau einen Issuer**. Mehrere Partner-Pools lassen sich mit JWT-Authorizern daher nicht in einem Authorizer abbilden.

---

## 3. Variante A — gemeinsamer Multi-Issuer-Lambda-Authorizer

### Architektur

Ein Lambda-Authorizer (REQUEST) vor den Partner-Routen:

1. Bearer-Token aus `Authorization` lesen.
2. `iss` gegen eine **explizite Trust-Registry** prüfen (Issuer → erlaubte Audiences, Tenant-Familie).
3. JWKS des Issuers laden (HTTPS, `kid`-basiert), Signatur **RS256** verifizieren.
4. `exp`, `nbf`, `token_use=access`, `client_id`/`aud` prüfen.
5. IAM-Policy mit Context (`sub`, `client_id`, `tenant`, `iss`) zurückgeben.
6. Fail-closed bei jedem Fehler; kein „unknown issuer = allow".

### Bewertung

| Kriterium | Ergebnis |
|---|---|
| Erweiterbarkeit | **hoch** — neue Partner = Registry-Eintrag |
| Sicherheit | **hoch, aber eigenverantwortlich** — Krypto, JWKS-Caching, Rotation und Trust-Registry müssen selbst korrekt sein |
| Implementierungsaufwand | **hoch** — neue Lambda, IAM, Trust-Store, JWKS-Cache, Policy-Output, Tests, Rotation |
| Terraform-Diff | +Authorizer-Lambda, +IAM-Rolle, +Trust-Store (DDB/SSM), **Änderung aller 36 Partner-Routen** (Authorizer-Wechsel), ggf. Handler-Anpassung |
| Rückwärtskompatibilität | **mittel** — bestehende Routen werden umgebunden; ein Fehler betrifft alle Partner |
| Betrieb | Authorizer-Cache, Schlüsselrotation, Incident-Flächen, eigene Krypto-Verantwortung |
| Abhängigkeiten | `rsa`/`pyjwt` nicht vorhanden; `cryptography` ist kompiliert und laut Randbedingungen unzulässig → eigene RS256-Verifikation oder neue Dependency |

**Hauptrisiko:** Der Handler liest Claims heute aus `requestContext.authorizer.jwt.claims`. Ein Lambda-Authorizer liefert `requestContext.authorizer.<context>` — jede Route bräuchte eine Anpassung, sonst brechen Auth/Tenant-Auflösung.

---

## 4. Variante B — separater Gateway-Zugang für Jobsearch

### Architektur

Zweite HTTP-API (`ris-dev-jobsearch-api`) mit eigenem JWT-Authorizer:

- Issuer `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ZURSMpD2O`
- Audience `5hb3f6dj5ialg77jf4blur9g6g`
- **gleiche** Lambda-Integration (`ris-dev-dev-agent`), **gleicher** Handler, **gleiche** Partner-Logik
- nur die 36 Partner-Routen, eigener `$default`-Stage, eigenes `aws_lambda_permission`
- bestehende API `g6901and25` bleibt **unverändert**

### Bewertung

| Kriterium | Ergebnis |
|---|---|
| Erweiterbarkeit | **linear** — je Partner-Pool eine Edge-API; jede isoliert, keine Querbeeinflussung |
| Sicherheit | **hoch** — AWS-native JWT-Validierung (Signatur/Issuer/Audience), kein eigener Krypto-Code |
| Implementierungsaufwand | **mittel** — rein deklarativ, keine Handler-Änderung |
| Terraform-Diff | **+~42 Creates, 0 Update/Delete/Replace** an bestehenden Ressourcen |
| Rückwärtskompatibilität | **vollständig** — bestehende API und alle RIS-Nutzer unberührt |
| Betrieb | Standard-API-GW; kein Authorizer-Cache-Risiko, keine Rotation im Code |
| Duplikation | nur Routendeklarationen (per `for_each` minimierbar), **keine** Geschäftslogik |

**Kosten:** zusätzliche API (geringe Grundkosten, pay-per-request), 36 deklarative Routen.

---

## 5. Vergleich

| Kriterium | A Multi-Issuer-Lambda | B Separater Zugang |
|---|---|---|
| Bestehende Routen unverändert | ❌ (alle umgebunden) | ✅ |
| Handler-Änderung nötig | ✅ wahrscheinlich | ❌ |
| Eigener Krypto-Code | ✅ | ❌ |
| Neue Partner ohne Codeänderung | ✅ (Registry) | ⚠️ (neue Edge-API je Pool) |
| Risiko für Bestandspartner | hoch | **kein** |
| Terraform-Änderung an Bestand | 36 Routen | **0** |
| Zeit bis Jobsearch-Key | Wochen | Tage |
| Betriebsfläche | Authorizer + Trust-Store | eine zusätzliche API |

---

## 6. Entscheidung

**Variante B wird umgesetzt.**

Begründung:

1. Null Risiko für bestehende Partner und den RIS-Pool.
2. AWS-native Validierung statt eigener Kryptografie.
3. Keine Verdoppelung von Geschäftslogik — derselbe Lambda-Handler.
4. Erfüllt die Anforderung „mehrere unabhängige Partner": jeder Pool erhält einen eigenen, isolierten Zugang. A bleibt der spätere Pfad, wenn die Partnerzahl einen gemeinsamen Endpoint rechtfertigt (dann mit dediziertem Trust-Store und eigenen Krypto-Tests).

---

## 7. Minimaler Umsetzungsvorschlag (B)

### Terraform (neues Modul `partner_edge` oder inline)

| Ressource | Anzahl | Anmerkung |
|---|---:|---|
| `aws_apigatewayv2_api` | 1 | `ris-dev-jobsearch-api`, CORS wie bestehend |
| `aws_apigatewayv2_authorizer` | 1 | JWT, Issuer/Audience aus Variablen |
| `aws_apigatewayv2_integration` | 1 | AWS_PROXY auf `ris-dev-dev-agent` |
| `aws_apigatewayv2_route` | 36 | `for_each` über bestehende Route-Definitionen |
| `aws_apigatewayv2_stage` | 1 | `$default`, auto_deploy |
| `aws_lambda_permission` | 1 | Source-ARN der neuen API |
| **Summe** | **~41** | **0 Änderungen an bestehenden Ressourcen** |

Variablen: `jobsearch_cognito_issuer`, `jobsearch_cognito_client_id`, `partner_edge_cors_origins`. Keine Secrets, keine Pool-Erstellung.

### Nach dem Plan (separate Freigaben)

1. Terraform-Plan reviewen (nur Creates).
2. Partner `mays-jobsearch` an Client `5hb3…` binden, Tenant `mays-jobsearch`.
3. Credential mit 1 Jahr Laufzeit erzeugen; Wert in Vercel `RIS_API_KEY` (Production + Development).
4. `PARTNER_SURFACE_ENABLED` erst nach RG-09 auf `true` — besser als Terraform-Variable statt hartkodiert.
5. E2E über die neue Edge-API mit Jobsearch-Token + `X-Api-Credential`.

### Nicht enthalten

- keine neuen Cognito-Pools, keine RIS-Benutzeränderung
- keine CloudFront-/DNS-/ACM-Änderung
- kein Apply, keine Provisionierung ohne Trust-Anchor

---

## 8. Sicherheitsanforderungen (gelten für beide Varianten)

- Trust nur über explizite Issuer-/Audience-Allowlist, nie über ungeprüfte Claims.
- Signatur, `iss`, `aud`/`client_id`, `exp`, `nbf`, `token_use` prüfen.
- Tenant ausschließlich serverseitig (Registry `client_id → tenantId`), kein Default.
- Credential-Digest, Profilstatus, Partnerstatus und Tenant müssen übereinstimmen.
- Kein Wildcard-CORS, keine Secrets im Browser, kein `VITE_*`.
- Surface-Gate bleibt bis zur Datenschutzfreigabe geschlossen.

---

## 9. Offene Punkte

1. Name/Umfang der Edge-API (`jobsearch` vs. generisch `partner-edge`).
2. Ob weitere Partner-Pools kurz- oder mittelfristig angebunden werden (Entscheidung A vs. B langfristig).
3. RG-09-Freigabe für die Surface-Aktivierung.
4. Rotation und Ablauf des 1-Jahres-Credentials.

**Keine Umsetzung in diesem Schritt. Nächster Schritt: Terraform-Plan für Variante B zur Freigabe.**
