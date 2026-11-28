# RIS-DEV2-SYNTHETIC-LIVE-CANARY-01

**Datum:** 2026-11-25
**RIS-Branch:** `feature/ris-analysis-integration-07`
**Baseline:** `723677524344655d4023f869ca2a7698e67483cd`
**MO-Pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`
**Modus:** Vorbereitung + Tests; **kein Apply, kein AWS-Write, kein State-Write, kein Main-Merge**

## Ergebnis

**BLOCKED** — die Vorbereitung ist abgeschlossen, aber ein positiver Live-Canary
kann mit dem aktuellen DEV2-Datenstand nicht erfolgreich sein:

- **0** Entitlements für `analysis-agent` (vorhanden: 1× `ats-agent`, 1× `addition_agent`),
- **4/4** API-Profile sind `REVOKED` (keine ACTIVE),
- **0** Analysis-WorkItems (12 WorkItems gesamt: 10 `COMPLETED`, 2 `DEAD_LETTER`).

Der Order-Create verlangt ein ACTIVE, eigentümergebundenes API-Profil **und**
ein gültiges `analysis-agent`-Entitlement; der Worker prüft das Entitlement vor
der Ausführung erneut. Ohne beides entsteht kein WorkItem und damit kein
`RUNNING`-Nachweis. Diese Provisionierung wäre ein AWS-Write und ist in diesem
Gate nicht freigegeben.

Der Terraform-Kandidat und der Rückweg sind vorbereitet; der Canary-Plan ist
allerdings eine **Vorlage mit Platzhalter-Identitäten** und darf so nicht
angewendet werden.

## 1. Vorbereitete Synthetic-Konfiguration

Neue Terraform-Variablen (Modul + Root), **Defaults deny**:

| Variable | Default |
| --- | --- |
| `analysis_synthetic_mode` | `false` |
| `analysis_synthetic_installation` | `ris-dev2` |
| `analysis_synthetic_tenant_id` / `_user_id` / `_partner_application_id` | `""` |
| `analysis_synthetic_issuer` | `""` (nur `https://` erlaubt, falls gesetzt) |
| `analysis_synthetic_entitlements` | `""` |
| `analysis_synthetic_expires_at` | `""` |

Die Analysis-Lambda erhält diese acht Werte als Environment. `ANALYSIS_CONSENT`
und `ANALYSIS_NOTICE_APPROVED` bleiben unverändert `false`; es wird keine
produktive Consent-Regel gelockert.

Canary-Var-Datei (nicht committet):
`C:\tmp\ris-dev2-synthetic-canary.tfvars` — Platzhalter
`tenant-ris-canary-01`, `user-ris-canary-01`,
`ris-internal-analysis-canary-01`, `https://issuer.invalid/synthetic-ris-canary-01`,
Entitlements `parse.cv,parse.job,analyze.job,compare.tags`, Ablauf
`2026-11-27T18:00:00Z`.

## 2. Pläne (nicht angewendet)

| | P1 — Mode off (sicherer Baseline-/Rückweg-Kandidat) | P2 — Canary-Vorlage |
| --- | --- | --- |
| Datei | `C:\tmp\ris-dev2-synthetic-prep-mode-off.tfplan` | `C:\tmp\ris-dev2-synthetic-canary-01.tfplan` |
| Größe | 251 247 Bytes | 252 218 Bytes |
| SHA-256 | `bac9af1cb9eb37bfd20cd0be22a4cc14ab049fca24e044c0a59dd15580f566a9` | `7ecb0da66905de9e8288a7e7d4fa7ab45d68178761459a15d3f0ea351b4ac55e` |
| Summary | **0 Add / 8 Change / 0 Destroy / 0 Replace** | **0 Add / 8 Change / 0 Destroy / 0 Replace** |
| Analysis-Env | `ANALYSIS_SYNTHETIC_MODE=false`, Identitäten leer | `=true`, Identitäten + Entitlements + Ablauf gesetzt |
| Consent/Notice | `false` / `false` | `false` / `false` |

Beide Pläne enthalten unverändert:

1–7. die sieben Lambda-Code-Updates (`source_code_hash`, `last_modified`),
8. die einschränkende IAM-Policy (`OwnedPartnerProfiles` nur `GetItem`,
   `SyntheticWorkItemReadback` `GetItem`).

Keine Änderung an Role-Trust, Cognito, CloudFront, DNS, ACM, DynamoDB-
Ressourcen, SQS-Ressourcen, Secrets oder Event-Source-Mappings. State:
`ris-dev2`, Lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, Serial 69.

**P2 ist nicht ausführbar für einen positiven Test**, weil die Platzhalter-
Identitäten nicht zum realen Dispatch-Kontext passen. Vor einer Freigabe müssen
Tenant/User/Partner/Issuer aus dem autorisierten synthetischen Order-Kontext
übernommen und der Plan neu erzeugt werden.

## 3. Tests

| Lauf | Ergebnis |
| --- | --- |
| MO-Lambda-Suite (Pin `db4f9e7`) | **240 Tests OK**, 0 failures/errors/skips |
| RIS-Cross-Repo mit `MO_ORDERS_SRC` (Dispatch-Handoff, Agent-Order-E2E, Work-Queue, Synthetic-Profil, Analysis-Terraform) | **61 passed**, 0 skipped |
| Parser-/Analysis-Agent-Set (8 Dateien) | **109 passed** |
| Synthetic positiv/negativ inkl. abgelaufenem Profil | in den 61 enthalten; PASS |
| `terraform fmt -check`, `terraform validate` | PASS (nur vorbestehende `hash_key`-Warnungen) |
| Bundles | unverändert `d767a198…` / `e268b028…` |

**Vorbestehender Alt-Test:** `tests/test_analysis_fresh_plan_16c1.py` pinnt den
16C1-Worker-Bundle `85775f68…`; der reviewed Correlation-Fix hat ihn auf
`d767a198…` neu gebaut (vor dieser Baseline). Der Test ist damit historisch
stale, nicht durch dieses Gate verursacht, und wurde als Evidenzdatei nicht
verändert. `test_analysis_ecosystem_wiring.py` wurde auf die aktuellen,
reviewten Bundle-Hashes aktualisiert; die Stale-Plan-Assertion bleibt erhalten.

## 4. Gate-Analyse: Entitlement und Consent

- **Consent:** Der synthetische Pfad erzeugt intern `consent=True`, aber
  `synthetic=True` und `consent_notice_approved=False`. `ANALYSIS_CONSENT`
  bleibt `false`. Es wird keine echte Einwilligung behauptet oder erteilt.
- **Entitlement (Order-Create):** `orders_reader` verlangt ACTIVE-Profil,
  Eigentümerbindung, Tenant und ein gültiges Entitlement für `analysis-agent`.
  Aktuell: keine ACTIVE-Profile, kein `analysis-agent`-Entitlement → **403
  `AGENT_ORDER_REJECTED`**.
- **Entitlement (Worker):** Der Worker prüft das Entitlement erneut vor der
  Ausführung. Die Synthetic-Entitlements der Analysis-Lambda ersetzen diese
  Prüfung **nicht**.
- **WorkItem-Verifikation:** unverändert zwingend `status=RUNNING` plus exakter
  Vergleich von Tenant, User, PartnerApplicationId und Issuer.

## 5. Live-Testplan (nur nach gesonderter Freigabe)

Voraussetzungen (separate AWS-Write-Freigabe nötig):

1. Synthetisches ACTIVE-API-Profil für den Testuser, mit Tenant und
   PartnerApplicationId.
2. Gültiges `analysis-agent`-Entitlement für User/Tenant/Profil.
3. Bindung der vier Synthetic-Werte an diesen Kontext; P2 neu erzeugen und
   Ablauf kurz vor dem Testfenster setzen.

Ablauf nach Apply-Freigabe:

1. Exakt freigegebenen Plan anwenden; Env der Analysis-Lambda verifizieren.
2. Synthetische Order mit gültiger AgentOrder V1 in `orderDescription` anlegen.
3. Dispatch und WorkItem prüfen: persistiert, `RUNNING`, Identität vollständig.
4. Analysis-Agent mit gültiger synthetischer Identität ausführen.
5. Echtes Analysis-Ergebnis prüfen (Parser-Ausgabe, keine CV-Inhalte in Logs).
6. ORDER_RESULT über den MO-Consumer zuordnen (Korrelation/Signatur).
7. Ergebnis über autorisierten Order-GET lesen; fremder Owner → 404.
8. Negativfälle: fremder Tenant/User/Partner/Issuer, falsche WorkId, Replay →
   keine Autorisierung, kein Ergebnis.
9. Testdaten nach freigegebenem Verfahren bereinigen; Synthetic-Modus
   deaktivieren (P1-Konfiguration, neuer Plan, neue Freigabe).

Rückweg: Var-Datei auf `analysis_synthetic_mode=false` (bzw. entfernen), neuen
Plan erzeugen, Diff prüfen (nur Env-Rückführung), freigeben, anwenden,
Env verifizieren. Ein bereits angewendeter P2-Plan kann nicht erneut
angewendet werden; der Rückweg braucht einen neuen, geprüften Plan.

## 6. Entscheidung

**BLOCKED** — konkret:

1. Kein ACTIVE-API-Profil (4/4 `REVOKED`) und kein `analysis-agent`-
   Entitlement; ohne diese ist kein synthetischer Order-Create und kein
   `RUNNING`-WorkItem möglich.
2. Die Provisionierung ist ein AWS-Write und nicht Teil dieses Gates.
3. P2 enthält Platzhalter-Identitäten und ist daher keine ausführbare
   Positiv-Konfiguration.
4. Die negativen Pfade sind vorbereitet und getestet; der positive Nachweis
   bleibt offen.

Vorbereitet und geprüft sind: Terraform-Parameterisierung mit Deny-Defaults,
P1/P2-Pläne mit Hashes, vollständige Testläufe, Rollback und Runbook.

## 7. Nicht ausgeführt

Kein `terraform apply`, keine AWS-Mutation, kein State-Write, kein Main-Merge,
keine Änderung an MO-Code oder am bestehenden Plan `279a530f…`. Die Zählungen
in §„Ergebnis“ stammen aus lesenden `Scan`-Aufrufen (nur Counts/Aggregate).
