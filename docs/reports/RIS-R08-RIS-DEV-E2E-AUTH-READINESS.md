# RIS-R08-RIS-DEV-E2E-AUTH-READINESS-01

- **Datum:** 2026-11-05
- **Modus:** Read-only Readiness-Prüfung; **keine AWS-Mutation, kein Apply, kein Flag-Update, kein Credential-Issue**
- **Ergebnis:** **READY** — eine Betreiberkonvention offen (Env-Variable)

---

## 1. Baseline (tatsächlich vs. Auftragstext)

| Feld | Auftragstext | Tatsächlich |
|---|---|---|
| Git-HEAD | `5ebefbd` | **`abd1fb0`** (`main`) |
| State | Serial 39 / 237 | **Serial 41 / 243** |
| Lineage | — | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Workspace | `ris-dev` | `ris-dev` |
| `PARTNER_SURFACE_ENABLED` | `false` | **`true`** (dauerhaft, seit M-RIS-LIVE-E2E-04) |

Die Abweichungen sind erwartbar: seit dem genannten Stand wurden der Partner-Gateway (`c7e9pdwe78`) und die dauerhafte Surface-Aktivierung umgesetzt und dokumentiert.

---

## 2. STS-Principal

```text
Account: 240571105849
ARN:     arn:aws:iam::240571105849:user/Mayaws
UserId:  AIDATQAZHYI4SUCNIJNJR
```

Profil `mayaws`, Region `eu-central-1`.

---

## 3. Admin-Trust-Anchor

| Prüfung | Ergebnis |
|---|---|
| Datei | `/home/dci-student/.ris/admin-authorization-dev2.json` |
| Rechte | `600`, Eigentümer `dci-student` ✅ |
| Struktur | `principals → <ARN> → { role, tenantId }` ✅ |
| Mapping | `arn:aws:iam::240571105849:user/Mayaws` → `admin` → **`mays-jobsearch`** ✅ |
| Env-Variable `RIS_ADMIN_AUTHORIZATION_FILE` | **nicht gesetzt** in der aktuellen Shell |
| Resolver | exakter Principal-Match, Rolle ∈ {admin,staff,owner}, Tenant Pflicht, fail-closed (`tools/ris_admin/credentials.py:64-125`) |

Der CLI-Lifecycle akzeptiert die Datei alternativ per `--authorization-file`; die Env-Variable ist Konvention, nicht die einzige Quelle.

---

## 4. Partner-/Credential-Bestand (E2E-Bereitschaft)

| Objekt | Zustand |
|---|---|
| Partner `mays-jobsearch` | **ACTIVE**, Tenant `mays-jobsearch`, Client `5hb3…` |
| Reservation `CLIENT#5hb3…` | RESERVED |
| APIProfile `aprof_5197f49297884a94` | **ACTIVE** |
| Credential `cred_5bf0c5b37e4e4b0d` | **ACTIVE**, gültig bis 2027-11-05 |
| Alt-Partner `ris-dev-e2e-20261105` | INACTIVE, Credential REVOKED |

---

## 5. Partner-Surface-Sicherheit

Live-Wert ist `true`. Der Auftrag verlangt den Nachweis, dass `false` personenbezogene Funktionen sperrt — lokal verifiziert:

```
tests/test_partner_surface_gate.py .... 4 passed
```

Belegt:

- Ohne Flag → jeder `/v1/partner/me/*`-Pfad liefert **503** `Partner surface not activated`.
- Bestehende RIS-Routen (`/me`, `/agents`, `/platform`) bleiben unberührt.
- Aktivierung nur bei explizitem `true`.

Live-Gegenprobe: Edge-API ohne Token **401**, Kernel-Health **401**.

Zusätzlich gilt weiterhin: `ERASURE_APPLICATIONS_ENABLED=false`, `DELETION_LEDGER_ENABLED=false`.

**Wirkungsbereich der Aktivierung:** nur Partner mit ACTIVE-Registry **und** ACTIVE-Credential; aktuell ausschließlich `mays-jobsearch`. Kein anonymer oder fremder Partnerzugriff.

---

## 6. Schutzgüter (unverändert)

| Ressource | Wert |
|---|---|
| RIS-Pool | `ojbmoiYGM`, Domain `ris-dev-dev`, keine Custom Domain |
| Jobsearch-Pool | `ZURSMpD2O`, Custom Domain `auth.mays-job-matcher.app` |
| CloudFront | `E1IP0DIEAXAZPY`, `E1R3BHTJNMC6XW` |
| OACs | `E29OZUCWF2PIIJ`, `E1AEAL7JW5EP6Q` |
| ACM | `ISSUED` |
| DNS | `auth → dsv3el0c1dn2.cloudfront.net` |
| Kernel-API | `g6901and25` Health **401** |

---

## 7. E2E-Umfang (bereits definiert, wiederverwendbar)

1. Synthetischer Jobsearch-Nutzer (Pool `ZURSMpD2O`), Login via Authorization-Code + PKCE.
2. Access-Token (kein ID-Token) an den BFF.
3. BFF setzt `X-Api-Credential` serverseitig, ruft `https://c7e9pdwe78…` auf.
4. Create → List → Detail → Patch (Version) → Reload → Export → Delete.
5. Negative Fälle: kein Token (401), ungültiges Token (401), fremder Issuer (401), fremder Tenant/Client (403).
6. Revocation-Test: Credential widerrufen → 401.
7. Cleanup: Applications löschen, Testnutzer löschen, Secret-Dateien entfernen.
8. Rückstellung: keine nötig für Surface (dauerhaft aktiv); Erasure-/Ledger-Flags bleiben `false`.

Dieser Umfang wurde in `M-RIS-LIVE-E2E-04` bereits erfolgreich durchlaufen (201/200/200/200/200/200, Decimal `50000.5` / `60000.75`, Cleanup 0 Applications).

---

## 8. Pflichtausgabe

| Gate | Ergebnis | Nachweis |
|---|---|---|
| AWS-Identität | **PASS** | STS `240571105849` / `Mayaws` |
| State | **PASS** | Serial 41, 243 Ressourcen, Lineage unverändert |
| STS-Principal | **PASS** | `arn:aws:iam::240571105849:user/Mayaws` |
| Admin-Trust-Anchor | **PASS** (Datei) — Env-Variable nicht gesetzt | `600`, Mapping admin/`mays-jobsearch` |
| Tenant-Autorisierung | **PASS** | `mays-jobsearch` im Anchor + Partner ACTIVE |
| Partner-Surface-Sicherheit | **PASS** | 4 Gate-Tests; Live 401 ohne Token |
| CloudFront/Cognito/DNS | **PASS** | unverändert (Snapshot §6) |
| E2E-Bereitschaft | **PASS (lokal)** — Vercel-Test-Env offen | `M-RIS-LIVE-E2E-04` |

---

## 9. Genau eine offene Betreiberhandlung

**Setze `RIS_ADMIN_AUTHORIZATION_FILE` im Ausführungskontext** (oder bestätige die Verwendung von `--authorization-file`):

```bash
export RIS_ADMIN_AUTHORIZATION_FILE=/home/dci-student/.ris/admin-authorization-dev2.json
```

Die Datei selbst ist gültig und autorisiert `Mayaws` für Tenant `mays-jobsearch`. Ohne diese Konvention greifen CLI-Aufrufe ohne explizites Flag fail-closed.

**STOP nach der Readiness-Prüfung.**
