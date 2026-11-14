# MO-RIS-RISDEV2-STATE-FORENSIC-01 — Read-only State Reconciliation

**Datum:** 2026-11-14
**Modus:** READ-ONLY. Kein Apply, kein State-Restore, keine Migration.
**Ergebnis:** **STATE RECONCILED** — keine unerklärte Abweichung.

## 1. F01 — Historische Deployment-Evidence

| Nachweis | Quelle | Wert |
|---|---|---|
| Konto / Profil / Region | Auditlog (`RIS-DEV2-…`), R2-STS | `262370457690` / `default` (`devnemo`) / `eu-central-1` |
| Workspace | Auditlog | `ris-dev2` |
| State-Key | Destroy-Report + R2 | `env:/ris-dev2/dev/terraform.tfstate` |
| **Lineage** | Auditlog (Serial 24) | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Serial (2026-10) | Auditlog | 24 |
| Serial vor Abbau | Destroy-Report | 30 → 36 |
| Bestand vor Abbau | Destroy-Report | **177 Ressourcen** |
| Apply-/E2E-Nachweise | `RIS-R08-DEV2-*`, `RIS-DEV2-DEPLOY-01-*` | erfolgreiche Deployments, Consumer-Acceptance, Live-Tests |

## 2. F02 — Aktueller State (gelesen, nur Metadaten)

| Feld | Wert |
|---|---|
| Backend | S3 `ris-dev2-tf-state-dev` |
| Key | `env:/ris-dev2/dev/terraform.tfstate` |
| Workspace | `ris-dev2` |
| **Lineage** | **`a0bd361d-5cd1-a207-a8c0-e6888f0be082`** — identisch |
| **Serial** | **36** |
| Ressourcen | **0** |
| Outputs | keine |
| terraform_version | 1.17.0 |

**State-Versionshistorie** (S3 Object Versions, lesend):

| Zeitpunkt | Größe | Bedeutung |
|---|---|---|
| bis 2026-11-05 | 559 263 B | vollständiger Stack |
| 2026-11-09 08:34:11 | 126 026 B | Abbau beginnt |
| 2026-11-09 08:34:37 | 48 257 B | … |
| 2026-11-09 08:35:00 | 11 564 B | … |
| 2026-11-09 08:35:43 | 9 639 B | … |
| 2026-11-09 08:37:14 | 4 343 B | … |
| 2026-11-09 08:37:15 | **5 406 B** | **leer, serial 36** |

Die Lineage ist unverändert. Es gab **keinen** Backend-Wechsel und **keine**
State-Migration — derselbe State wurde abgebaut.

## 3. F03 — AWS-Ressourcenabgleich (read-only, `262370457690`)

| Kategorie | Befund |
|---|---|
| SQS `ris-dev2-*` | **keine** |
| API Gateway `ris-dev2-*` | **keine** |
| Cognito Pools `ris-dev2-*` | **keine** |
| CloudTrail `ris-dev2-*` | **keine** |
| IAM-Rollen `ris-dev2-*` | **keine** |
| CloudWatch Log-Groups `/aws/lambda/ris-dev2-*` | **keine** |
| CloudFront mit `ris-dev2`-Origin | **keine** |
| S3-Buckets `ris-dev2-*` | nur **`ris-dev2-tf-state-dev`** (Bootstrap) |
| DynamoDB | nur **`ris-dev2-tf-lock`** (Bootstrap) |

Einordnung nach Auftrag:

1. **Existiert und vom richtigen State verwaltet:** nichts.
2. **Existiert, aber nicht im State:** nichts gefunden.
3. **Nachweislich gelöscht:** alle 177, dokumentiert (`RIS-DEV2-STACK-DESTROY-01`).
4. **Nicht zuordenbar:** nichts.

## 4. Erklärung der Abweichung

Der „Widerspruch" ist keiner: `ris-dev2` wurde am **2026-11-09** nach
ausdrücklicher Betreiberfreigabe **vollständig abgebaut**
(177 Ressourcen, Plan `E72A5505…`). Der Bootstrap (State-Bucket, Lock-Tabelle)
blieb bewusst erhalten. Die Lineage blieb gleich, der Serial stieg auf 36.

Damit ist der R2-Befund (183 Creates im Default-off-Plan) **erwartet**, nicht
fehlerhaft: Es gibt keinen Bestand mehr, der Plan ist ein Vollaufbau.

## 5. F04 — Cross-Account-Vertrag

| Punkt | Feststellung |
|---|---|
| RIS-Konto | `262370457690` (STS bestätigt) |
| Orders-Konto | `240571105849` (Datei-Evidenz, nicht zugreifbar) |
| Regionen | beide `eu-central-1` |
| Dispatch-Queue | gehört **RIS**, Consumer ist RIS |
| Result-Queue | gehört **Orders**, Consumer ist Orders |
| Sender-Rollen | ARNs **unbekannt** — kein Zugriff auf Orders-Konto |
| Empfänger-Rollen | im RIS-Konto erst mit dem Apply erzeugt |
| Queue-Policies | benötigen **Cross-Account-Prinzipale**; aktuell leere Liste → inert |
| KMS | keiner; SSE-SQS auf beiden Queues |

**Fail-closed:** Solange die Orders-Rollen-ARNs nicht bekannt sind, bleibt
`Principal: []` korrekt — eine leere Policy erlaubt nichts. Es wurde kein ARN
erfunden.

## 6. F05 — Zielumgebung

Ziel bleibt **`ris-dev2`**. `ris-agent` wurde nur als bestehende Alternative
dokumentiert (185 Ressourcen, drift 0) und **nicht** als Ersatz verwendet.
`ris-dev` wurde nicht angefasst.

## 7. F06 — Vergleichstabelle

| Eigenschaft | Früheres Deployment | Aktueller Befund | Bewertung |
|---|---|---|---|
| AWS-Konto | `262370457690` | `262370457690` | identisch |
| Profil | `default` / `devnemo` | `default` / `devnemo` | identisch |
| Region | `eu-central-1` | `eu-central-1` | identisch |
| Backend | `ris-dev2-tf-state-dev` | dito | identisch |
| Workspace | `ris-dev2` | `ris-dev2` | identisch |
| State-Key | `env:/ris-dev2/dev/terraform.tfstate` | dito | identisch |
| Lineage | `a0bd361d-…` | `a0bd361d-…` | **identisch** |
| Serial | 24 → 30 (vor Abbau) | **36** | erklärt (Destroy) |
| Ressourcen | 177 | **0** | erklärt (Destroy) |

Keine Zeile ist ungeklärt.

## 8. Konsequenz für R2

Der Plan ist korrekt: **183 Creates (Default-off) / 191 (Integration)**. Ein
Apply würde `ris-dev2` vollständig neu aufbauen. Das ist eine bewusste
Neuinstallation, keine inkrementelle Integration — und muss als solche
freigegeben werden.

Für die Cross-Account-Policies fehlen weiterhin die Orders-Rollen-ARNs aus
`240571105849`.

## 9. STOP

Kein Apply, kein Destroy, kein State Push/Import/Restore, keine
Backend-Migration, keine neue Installation, kein Wechsel auf `ris-agent`,
keine Cognito-/CloudFront-/DNS-Änderung.

**Status: STATE RECONCILED.**
