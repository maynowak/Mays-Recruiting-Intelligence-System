# RIS-JOBSEARCH-LIVE-CONNECT-03 — Gateway bereitgestellt

- **Datum:** 2026-11-05
- **Modus:** kontrollierter Apply des freigegebenen Plans + Partner-Onboarding
- **Status:** **GATEWAY LIVE, PARTNER AKTIV** — E2E-Tokenpfad **BLOCKED**

---

## 1. Phase 1 — Gateway-Apply

### Gate-Prüfungen (alle PASS)

| Bedingung | Ergebnis |
|---|---|
| Account | `240571105849` ✅ |
| Region | `eu-central-1` ✅ |
| Workspace | `ris-dev` ✅ |
| Plan-SHA | `7ed69389…` vor Apply erneut geprüft ✅ |
| State | Lineage `9cec61e5…`, serial 39 vor Apply ✅ |
| Diff | 41 CREATE, 0 UPDATE, 0 DELETE, 0 REPLACE, 222 no-op ✅ |
| Schutzgüter | keine aktive Änderung an Cognito/CloudFront/ACM/DNS ✅ |
| Lambda-Permission | Source-ARN nur neue API ✅ |
| Secrets | nur ARN-Referenzen, keine Werte ✅ |

### Apply

`Apply complete! Resources: 41 added, 0 changed, 0 destroyed.`

| Element | Wert |
|---|---|
| Neue API | **`c7e9pdwe78`** (`ris-dev-jobsearch-api`) |
| Endpoint | `https://c7e9pdwe78.execute-api.eu-central-1.amazonaws.com` |
| Authorizer | `ris-dev-jobsearch-jwt`, Issuer `ZURSMpD2O`, Audience `5hb3…` |
| Routen | **36** |
| Stage | `$default` |
| Lambda-Permission | `arn:aws:execute-api:…:c7e9pdwe78/*/*` |
| State danach | serial **40**, 243 Ressourcenblöcke (36 Routen als `for_each`-Instanzen) |
| Folge-Plan | **0 aktive Änderungen** (263 no-op) |

### Bestand unverändert

Kernel-API `g6901and25` weiterhin erreichbar (Health **401**), Jobsearch-Pool/-Domain unverändert (`auth.mays-job-matcher.app`, DNS `dsv3el0c1dn2`), keine CloudFront-/ACM-Änderung.

---

## 2. Phase 2 — Partner-Onboarding

Trust-Anchor auf Tenant `mays-jobsearch` umgestellt (Datei bleibt 600, Principal `Mayaws`).

| Objekt | Wert |
|---|---|
| Partner | `mays-jobsearch` — **ACTIVE** |
| Tenant | `mays-jobsearch` |
| Client | `5hb3f6dj5ialg77jf4blur9g6g` |
| Reservation | `CLIENT#5hb3…` — RESERVED |
| APIProfile | `aprof_5197f49297884a94` — **ACTIVE** |
| Credential | `cred_5bf0c5b37e4e4b0d` — **ACTIVE**, gültig bis **2027-11-05** |
| Secret | `/tmp/opencode/mays-jobsearch-ris-api-key.json`, Modus **600**, Wert nie ausgegeben |

Kein Offer/Grant zugeordnet: die Partner-Routen benötigen für diesen Pfad kein Produkt-Entitlement; eine Offer-Zuordnung ist eine separate Produktentscheidung.

---

## 3. Phase 3 — BFF-Vorbereitung

**Nicht umgesetzt.** Im Jobsearch-Repo existiert kein RIS-Client/BFF; das Setzen von `RIS_API_BASE_URL` / `RIS_API_KEY` ohne Code wäre wirkungslos. Zudem wäre eine Vercel-Änderung separat freizugeben.

Vorgesehene Werte für die Testumgebung:

```text
RIS_API_BASE_URL = https://c7e9pdwe78.execute-api.eu-central-1.amazonaws.com
RIS_API_KEY      = <Secret aus geschützter Datei>
```

---

## 4. Phase 4 — E2E

### Durchgeführt (negativ)

| Test | Ergebnis |
|---|---|
| Edge-API ohne Token | **401** |
| RIS-Pool-Token gegen Jobsearch-Edge | **401** (Issuer/Audience-Isolation) |
| Unbekannte Route (`/health`) | **404** |
| Kernel-Health | **401** (unverändert) |

### BLOCKED

| Test | Grund |
|---|---|
| Jobsearch-Login → Access-Token | Client `5hb3…` erlaubt **keinen** non-interaktiven Flow (`ExplicitAuthFlows=null`, nur `code`) |
| Create/List/Patch/Export/Delete über Edge | setzt gültiges Jobsearch-Token voraus |
| `PARTNER_SURFACE_ENABLED` | weiterhin `false` (RG-09) |

Ein Token ist nur über den echten Hosted-UI-Login (Browser) oder einen BFF mit Session erhältlich. Der Client darf dafür nicht verändert werden.

---

## 5. Cleanup-Status

| Objekt | Zustand |
|---|---|
| Temporäre RIS-Pool-Testnutzer | gelöscht |
| Partner `mays-jobsearch` | bleibt ACTIVE (Zielzustand) |
| Credential | bleibt ACTIVE (Zielzustand), Secret nur in 600er-Datei |
| `PARTNER_SURFACE_ENABLED` | `false` |

---

## 6. Offene Freigaben

1. **Surface-Aktivierung** (`PARTNER_SURFACE_ENABLED=true`) erst nach RG-09 — derzeit liefert jeder Partner-Aufruf 503.
2. **BFF-Implementierung** in Jobsearch + Vercel-Test-Env (`RIS_API_BASE_URL`, `RIS_API_KEY`).
3. **Token-Beschaffung** für E2E: Browser-Login oder BFF-Session; keine Client-Änderung.
4. Offer/Grant-Zuordnung, falls produktseitig benötigt.

---

## 7. Ergebnis

Der separate Jobsearch-Gateway ist installiert, der Partner ist registriert und mit einem gültigen, einjährigen Credential ausgestattet. Die technische Anbindung ist für den autorisierten Test vorbereitet; der positive E2E scheitert derzeit ausschließlich an der fehlenden non-interaktiven Tokenquelle und am bewusst geschlossenen Surface-Flag.
