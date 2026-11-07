# RIS-JOBSEARCH-PARTNER-GATEWAY-02 — Plan Ready

- **Datum:** 2026-11-05
- **Entscheidung:** Variante B — separater API-Gateway-Zugang für Mays-Jobsearch
- **Status:** **PLAN READY** — 41 Creates, 0 Update/Delete/Replace
- **Apply/Provisionierung:** **nicht erfolgt**

---

## 1. Architektur

```
Jobsearch-Login (Pool ZURSMpD2O, Client 5hb3…)
        │ Access-Token
        ▼
ris-dev-jobsearch-api  (eigene HTTP API)
   JWT-Authorizer: Issuer ZURSMpD2O / Audience 5hb3…
        │ AWS_PROXY, payload 2.0
        ▼
ris-dev-dev-agent  (bestehende RIS-Lambda, unverändert)
        │ X-Api-Credential + Partner-Registry + Tenant
        ▼
ApplicationV1 / Profile / Privacy  (bestehende Logik)
```

Die Kernel-API `ris-dev-dev-api` (`g6901and25`) bleibt vollständig unverändert. Keine Geschäftslogik-Duplikation: dieselbe Lambda, derselbe Handler.

---

## 2. Terraform-Diff

Neues Modul `terraform/modules/partner_edge/`, im Root nur aktiv, wenn Issuer und Client gesetzt sind.

| Ressource | Anzahl |
|---|---:|
| `aws_apigatewayv2_api` (`ris-dev-jobsearch-api`) | 1 |
| `aws_apigatewayv2_authorizer` (JWT) | 1 |
| `aws_apigatewayv2_integration` (AWS_PROXY) | 1 |
| `aws_apigatewayv2_route` (36 Partner-Routen) | 36 |
| `aws_apigatewayv2_stage` (`$default`) | 1 |
| `aws_lambda_permission` (Source-ARN nur der neuen API) | 1 |
| **Summe** | **41** |

**Bestandsänderungen: 0 Updates, 0 Deletes, 0 Replacements.** Verifiziert im Plan-JSON (222 no-op, 41 create).

Konfiguration:
- Root-Variablen `jobsearch_cognito_issuer`, `jobsearch_cognito_client_id`, `jobsearch_edge_cors_origins`
- Overlay `installer/project-configs/ris-dev.json` (Werte: `ZURSMpD2O` / `5hb3…` / drei explizite Origins)
- Keine Secrets, keine neuen Pools

---

## 3. API-Routen (36, exakt aus dem RIS-Vertrag)

- 10 Applications (`GET/POST /v1/partner/me/applications`, `metrics`, Detail, `PATCH`, `status`, `history`, `cover-letter-versions`, `export`, `DELETE`)
- 8 CVs (`/v1/partner/me/cvs…`, inkl. `document/upload|complete|get`)
- 5 CV-Search-Profiles
- 5 ATS-Search-Profiles
- 5 Manual-Search-Profiles
- 2 Privacy (`inspect`, `export`)
- 1 Partner-Agent (`POST /v1/partner/agents/{agentId}/execute`)

Keine Kernel-Route (`/me`, `/agents`, `/platform`, `/health`, `/orders`, `/v1/apiprofiles`, …) ist enthalten.

---

## 4. JWT-Konfiguration

| Feld | Wert |
|---|---|
| Typ | NATIVE JWT (API Gateway) |
| Issuer | `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ZURSMpD2O` |
| Audience | `5hb3f6dj5ialg77jf4blur9g6g` |
| Identity Source | `$request.header.Authorization` |
| Signaturprüfung | AWS-nativ, kein eigener Krypto-Code |
| Access-Token | Handler verlangt `token_use=access` + `client_id`; API GW validiert `client_id` gegen Audience |

---

## 5. Unveränderte Bestandsressourcen

Jobsearch-Pool/Client/Login-Domain/Callbacks, RIS-Pool/Clients, Kernel-API und alle 70 Routen, CloudFront (`E1IP0DIEAXAZPY`, `E1R3BHTJNMC6XW`), OACs, ACM, DNS, DynamoDB-Daten, Mays-Orders. **0 aktive Änderungen im Plan.**

---

## 6. Partner-/Tenant-Vertrag (vorbereitet, nicht provisioniert)

| Feld | Vorgabe |
|---|---|
| Partner | `mays-jobsearch` |
| Tenant | `mays-jobsearch` |
| Client | `5hb3…` (Reservation `CLIENT#5hb3…`) |
| APIProfile | vorhandener Vertrag, ACTIVE |
| Credential | serverseitig, 1 Jahr, nie im Browser |
| Offer/Grant | nur benötigte Berechtigungen |

Provisionierung erst nach Plan-Apply, mit gültigem Trust-Anchor (`Mayaws`) und separater Freigabe.

---

## 7. Sicherheitsprüfungen (Plan-Ebene)

| Prüfung | Ergebnis |
|---|---|
| Payload-Format identisch | ✅ beide `2.0` |
| `requestContext.authorizer.jwt.claims` | ✅ JWT-Authorizer, gleiche Struktur |
| Route-Keys korrekt | ✅ 1:1 aus bestehendem Modul |
| Unbekannte Routen | ✅ keine `$default`-Catch-all-Route → 404 |
| Keine Kernel-Routen exponiert | ✅ 36 Partner-Routen, keine Kernel-Pfade |
| Access-Token-Validierung | ✅ AWS-nativ, Audience/Issuer exakt |
| Lambda-Permission | ✅ Source-ARN nur der neuen API |
| Tenant/Ownership | ✅ unverändert serverseitig (Registry) |
| Credential zwingend | ✅ Handler unverändert (`X-Api-Credential`) |
| CORS | ✅ explizite Origins, kein Wildcard |
| `PARTNER_SURFACE_ENABLED` | bleibt `false` bis RG-09 |

---

## 8. Plan

| Feld | Wert |
|---|---|
| Plan | `/tmp/opencode/ris-jobsearch-edge.tfplan` |
| JSON | `/tmp/opencode/edge-plan.json` |
| **SHA-256** | **`7ed69389323d3ead72e561a8d8435739dab5589cae1f2bf448de55bfc00c50c2`** |
| State | unverändert (nur gelesen) |
| Drift | 38 berechnete Einträge, keine geplante Änderung |

---

## 9. Offene Freigaben

1. Apply dieses Plans (Infrastruktur).
2. Partner/Credential-Provisionierung (Trust-Anchor, Tenant `mays-jobsearch`).
3. `RIS_API_KEY` in Vercel setzen.
4. `PARTNER_SURFACE_ENABLED=true` erst nach RG-09.

---

## 10. Testplan (nach Apply + Freigabe)

Jobsearch-Login → Access-Token an BFF → `X-Api-Credential` ergänzen → Aufruf über die **neue** Edge-API: Metrics, Create, List, Detail, Patch, Export, Delete, Fremdzugriff 401/403, Cleanup. Ausschließlich synthetische Daten.

**Kein Apply, keine Credentials, keine Provisionierung in diesem Schritt.**
