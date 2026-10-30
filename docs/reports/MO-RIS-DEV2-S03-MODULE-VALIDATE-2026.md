# MO-RIS-DEV2-S03-MODULE-VALIDATE-2026 — Terraform-Prüfung des unveränderten S02-Moduls

**Datum (tatsächliche Ausführung):** 2026-10-25
**Run-ID:** `2026-10-25-ris-dev2-04`
**Status:** COMPLETE — `fmt`/`init`/`validate` lokal ausgeführt; **kein** Plan, kein Apply, kein AWS-Aufruf
**Eingang:** `docs/reports/MO-RIS-DEV2-S02-BUILD-CONTRACT-2026.md` (Commit `ea35b8c518c46a1a5543d0eb1e8c33227306ef54`)

---

## 1. Ausgangslage

### 1.1 Repository-Stände

| Repo | Branch | Voller HEAD | Arbeitsbaum |
|---|---|---|---|
| RIS | `feature/mo-module-installer-ris-dev2-2026` | `ea35b8c518c46a1a5543d0eb1e8c33227306ef54` | clean (vor Beginn) |
| MO (nur lesend) | `main` | `2d5cf2de08a05109452e88964a8b1a4d6940afcf` | clean (vor und nach allen Schritten) |

### 1.2 S02-Artefakt gefunden (keine Neugenerierung nötig)

| Prüfung | Ergebnis |
|---|---|
| S02-Buildziel vorhanden | ja (`<TEMP>\mo-ris-dev2-s02-2026-10-25\orders-module`) |
| Dateianzahl | 34 (unverändert) |
| Hashvergleich gegen `evidence/MO-RIS-DEV2-S02-2026/files-sha256.txt` | **0 Unterschiede** |
| `.terraform` / `.terraform.lock.hcl` im Rohziel | nicht vorhanden (S02-Stand unberührt) |

Damit ist das geprüfte Material **exakt** das S02-Artefakt; eine Neugenerierung war nicht erforderlich
und wurde nicht durchgeführt. Der Manifest-Zeitstempel wird **nicht** als Identitätsmerkmal verwendet.

---

## 2. Terraform-Constraints und Toolbereitstellung

### 2.1 Tatsächliche Constraints (aus dem generierten Stand gelesen)

| Quelle | Constraint |
|---|---|
| `versions.tf:2` | `required_version = ">= 1.5.0"` |
| `versions.tf:6-7` | `hashicorp/aws`, `>= 6.0` |
| `versions.tf:9-11` | `hashicorp/time`, `~> 0.11` |
| Child-Module (`modules/*/`) | **keine** eigenen `required_version`/`required_providers` — es gilt ausschließlich das Root-`versions.tf` |

Es wurde also **nicht** pauschal „>= 1.6" vorausgesetzt, sondern die tatsächliche Untergrenze 1.5.0
gelesen; die Auswahl fiel auf die aktuelle stabile Version.

### 2.2 Bereitstellung (isoliert, geprüft)

| Feld | Wert |
|---|---|
| Ausgangslage | Terraform **nicht** im PATH, keine vorhandene Installation |
| Version | `1.17.0` (stabil, nicht `rc`) |
| Quelle | `https://releases.hashicorp.com/terraform/1.17.0/terraform_1.17.0_windows_amd64.zip` |
| Prüfsummenquelle | `https://releases.hashicorp.com/terraform/1.17.0/terraform_1.17.0_SHA256SUMS` |
| Erwartete SHA-256 | `2948dd7f77dec0f562ec29000103e0441d915be5e5f1a02c1ce23681951cfb19` |
| Tatsächliche SHA-256 | `2948dd7f77dec0f562ec29000103e0441d915be5e5f1a02c1ce23681951cfb19` — **MATCH** |
| Ablage | `<TEMP>\mo-ris-dev2-s03-2026-10-25\tools\terraform-1.17.0\` |
| Systemweit? | **nein**; PATH unverändert, `terraform` bleibt außerhalb des PATH |
| Überschreiben? | keine vorhandene Version (es gab keine) |

Evidence: `evidence/MO-RIS-DEV2-S03-2026/terraform-version.txt`.

---

## 3. Unveränderter Rohstand und Prüffassungen

| Fassung | Herkunft | Zweck |
|---|---|---|
| **Rohziel (S02)** | `<TEMP>\...\s02...\orders-module` | Referenz, **nicht** verändert (34 Dateien, hashes unverändert) |
| **A-rohstand** | 1:1-Kopie des Rohziels | fmt-Prüfung, init, validate auf unverändertem Inhalt |
| **B-formatiert** | 1:1-Kopie des Rohziels, danach **nur** `terraform fmt -recursive` | Nachweis, dass Formatierung allein fmt-konform macht |

- Vor jeder Terraform-Aktion wurden 34 SHA-256-Werte der Kopie A erfasst
  (`sha256-rohstand-vorher.txt`).
- `TF_DATA_DIR` lag für A und B **außerhalb** der Modulordner (`<TEMP>\...\tfdata-A|B`, je ~828 MB
  Provider) — im Modulordner entstand nur die Lockdatei.
- Nach `init`+`validate`: alle **23 `.tf`-Dateien** in A hashgleich, Unterschiede **0**
  (`rohstand-tf-nachher.txt`).
- Von Terraform erzeugte Hilfsdateien (getrennt ausgewiesen, **nicht** versioniert):
  `.terraform.lock.hcl` in A und B, Provider-Binaries ausschließlich im `TF_DATA_DIR`.
- Keine `*.tfstate`, keine `*.tfplan`, kein `.terraform`-Verzeichnis in A, B oder im Rohziel.

### 3.1 Statische Vorprüfung des Rohstands

| ID | Erwartung | Befehl/Quelle | Ergebnis | Urteil |
|---|---|---|---|---|
| S-01 | Kein Backend | `Select-String '^\s*backend\s+"'` über alle `.tf` | 0 Treffer | MATCH |
| S-02 | Keine eigene AWS-Provider-Konfiguration | `^provider "` über alle `.tf` | 0 Treffer | MATCH |
| S-03 | Keine externen Modulquellen | `source =` in `main.tf` | 7× lokal (`./modules/...`), 0 extern | MATCH |
| S-04 | Keine State-/Plan-Reste | Dateisuche | 0 | MATCH |
| S-05 | Provider-Binaries nicht im Modul | Suche nach `terraform-provider-*.exe` | 0 im Modulbaum | MATCH |

---

## 4. Formatierung (A: Rohstand, B: formatierte Prüffassung)

| ID | Fassung | Befehl | Exitcode | Ergebnis | Urteil |
|---|---|---|---|---|---|
| F-01 | **A (Rohstand)** | `terraform -chdir=<A> fmt -check -recursive -no-color` | **3** | `main.tf`, `variables.tf` nicht fmt-konform | **FAIL** (Rohstand) |
| F-02 | **B** | `terraform -chdir=<B> fmt -recursive -no-color` | 0 | `main.tf`, `variables.tf` umformatiert | PASS (nur Formatierung) |
| F-03 | **B** | `terraform -chdir=<B> fmt -check -recursive -no-color` | **0** | keine Abweichung mehr | PASS |

**Betroffene Stellen (3 Zeilen, ausschließlich Ausrichtung):**

| Datei | Änderung |
|---|---|
| `main.tf:14` | `cognito_endpoint` → `cognito_endpoint  ` (Ausrichtung auf `cognito_client_id`) |
| `main.tf:65` | `count =` → `count        =` (Ausrichtung im `module "cognito"`-Block) |
| `variables.tf:49` | `user_pool_endpoint =` → `user_pool_endpoint  =` (Ausrichtung im `object`-Typ) |

**Funktionale Gleichheit:** Alle 23 `.tf`-Dateien wurden zusätzlich whitespace-normalisiert
verglichen (alle Whitespace-Zeichen entfernt) — **0 funktionale Abweichungen**.
Der vollständige Diff liegt als `fmt-diff-A-B.patch` bei (UTF-8, relative Pfade, 2 Dateien).

**Wichtig:** B belegt **nicht**, dass A bereits fmt-konform war. Der Rohstand ist formatiert **FAIL**;
die formatierte Fassung ist **PASS**. Der Unterschied ist rein kosmetisch.

---

## 5. Init und Validate

| ID | Fassung | Befehl | Exitcode | Ergebnis |
|---|---|---|---|---|
| I-01 | A | `terraform -chdir=<A> init -backend=false -input=false -no-color` | **0** | 7 Module, Provider installiert, Lockdatei erzeugt |
| V-01 | A | `terraform -chdir=<A> validate -no-color` | **0** | `Success! The configuration is valid.` |
| I-02 | B | `terraform -chdir=<B> init -backend=false -input=false -no-color` | **0** | identisch |
| V-02 | B | `terraform -chdir=<B> validate -no-color` | **0** | `Success! The configuration is valid.` |

**Aufgelöste Provider (beide Fassungen identisch):**

| Provider | Version | Signatur |
|---|---|---|
| `registry.terraform.io/hashicorp/aws` | `6.70.0` | signed by HashiCorp |
| `registry.terraform.io/hashicorp/time` | `0.14.2` | signed by HashiCorp |

**Terraform:** `1.17.0`, `windows_amd64`, `terraform_outdated: false`.
`-upgrade` wurde **nicht** verwendet. Warnungen: **keine** (Wortsuche in den Logs; der einzige
„error"-Treffer war der Dateiname `errors.py` in einer Hashliste).
AWS-Aufrufe: **keine**; es wurden keine AWS-Schlüssel bereitgestellt oder benötigt.

**Beobachtung:** `validate` ist **formatierungsunabhängig** — A besteht trotz `fmt -check`-Fehler.
Ein `validate`-PASS sagt daher nichts über Formatkonformität aus (und umgekehrt).

---

## 6. Bewertung (getrennt)

| Dimension | Urteil | Begründung |
|---|---|---|
| **Formatierung Rohstand (A)** | **FAIL** | 2 von 23 `.tf`-Dateien nicht fmt-konform (Exit 3) |
| **Formatierung formatierte Fassung (B)** | **PASS** | `fmt -check -recursive` Exit 0; nur Ausrichtung geändert |
| **Init** | **PASS** | Exit 0, alle 7 Child-Module lokal aufgelöst, Provider geprüft/signiert |
| **Modul-Validate** | **PASS** | Exit 0 für Rohstand **und** formatierte Fassung |
| **RIS-Vertragskompatibilität** | **FAIL (unverändert)** | siehe §7 — `validate` erkennt diese Lücken strukturell nicht |
| **Fresh-Plan / RIS-Root / AWS / E2E** | **NOT VERIFIED** | nicht Gegenstand dieses Auftrags |

---

## 7. Verbleibende Vertragslücken (durch validate **nicht** entdeckt)

| ID | Lücke | Warum validate das nicht zeigt | Zuständigkeit |
|---|---|---|---|
| GAP-02 | `sqs_queue_name` fehlt als Modul-Output | Das Modul selbst konsumiert den Output nicht; der Bedarf entsteht erst im RIS-Root (`monitoring_orders`) | MO primär |
| GAP-06 | IAM-`count` an `var.sqs_queue_arn` gebunden, kein plan-stabiles Gate | `validate` prüft nur Typen/Referenzen, keine Plan-Zeit-Bekanntheit von `count` | MO / RIS |
| GAP-01 | Projektname doppelt gesetzt (Wrapper vs. Terraform) | rein organisatorisch, kein Terraform-Fehler | RIS |
| GAP-03 | Kein wirksames Pinning; Manifest nur kurzer SHA | außerhalb Terraform | RIS |
| CONFLICT-02 | MANAGED-Cognito vs. RIS-`idToken` | Authentifizierung ist keine Terraform-Validierungsfrage | RIS (Entscheidung) |
| — | Formatierung des Generator-Outputs | Builder ruft `terraform fmt` nur bei vorhandenem Terraform auf (`builder.py:1021-1025`) | MO (Generator) |

**MANAGED/EXTERNAL:** Beide Varianten teilen denselben Code; `validate` prüft **beide Zweige
gleichzeitig** (der `count`-Ausdruck und die `one(...)`-Splats sind gültig). Ein Nachweis, dass die
Varianten **einzeln** funktionieren, ist damit **nicht** erbracht.

---

## 8. Aussagegrenzen

1. **Kein Plan:** Es wurde kein `terraform plan` ausgeführt; Aussagen über `count`-Bekanntheit,
   Provider-Verhalten oder Ressourcen-Erzeugung sind **nicht** belegt.
2. **Kein AWS:** keine Credentials, keine Region-Auflösung, keine API-/Cognito-Interaktion.
3. **Kein Backend:** `init -backend=false`; State, Workspace und Lock-Bucket bleiben offen.
4. **Kein RIS-Root:** Das Modul wurde **nicht** in `terraform/modules/mays_orders` installiert; die
   RIS-Root-Validierung ist damit nicht Teil dieses Nachweises.
5. **Keine Formatkorrektur am Rohstand:** Der S02-Rohstand bleibt unformatiert; die formatierte
   Fassung B ist ausschließlich Prüfmaterial.
6. **Lockdatei:** `.terraform.lock.hcl` ist Prüfartefakt und wurde **nicht** in den RIS-Root übernommen.

---

## 9. Nächste Änderungsaufträge

| Prio | Auftrag | Zuständigkeit | Kleinste Änderung | Blockiert |
|---|---|---|---|---|
| 1 | `output "sqs_queue_name"` ergänzen | MO | ein Output in `terraform/outputs.tf` | RIS-Root-Validate/-Plan |
| 2 | IAM-Gate plan-stabil (`sqs_enabled`) + Validierung „Gate an ⇒ ARN gesetzt" | MO | Gate-Ausdruck + `validation` | Fresh-Plan |
| 3 | Generator ruft `terraform fmt` verpflichtend auf bzw. dokumentiert den Verzicht | MO | `builder.py:1021-1025` | fmt-Konformität des Rohstands |
| 4 | Namensableitung + Namensprüfung im Wrapper | RIS | GAP-01/GAP-05 | reproduzierbarer Build |
| 5 | Vollständiger SHA im Manifest + erzwungener Checkout | MO/RIS | GAP-03 | Reproduzierbarkeit |
| 6 | Token-/Cognito-Entscheidung (EXTERNAL vs. M2M vs. Pfad B) | RIS | CONFLICT-02 | E2E |

**Konkreter nächster Schritt S04:** `MO-GAP-02/06-FIX-AUFTRAG` in einem **separaten** MO-Branch
(nicht Teil dieses Nachweises) — danach `S05-RIS-ROOT-VALIDATE` (Modul in RIS einbinden,
`terraform validate` des RIS-Roots, noch ohne AWS). Ein RIS-Root-Validate **vor** GAP-02 würde
deterministisch an `module.mays_orders.sqs_queue_name` scheitern; dieser Nachweis ist bewusst
vertagt, um keinen bekannt fehlerhaften Zwischenstand zu installieren.

---

## 10. Prüfmatrix (Zusammenfassung)

| ID | Erwartung | Befehl/Quelle | Ist | Exitcode | Evidence | Urteil |
|---|---|---|---|---|---|---|
| P-01 | S02-Artefakt unverändert | Hashvergleich 34 Dateien | 0 Unterschiede | 0 | `sha256-rohstand-vorher.txt` | MATCH |
| P-02 | Terraform-Version erfüllt `>= 1.5.0` | `terraform version` | 1.17.0 | 0 | `terraform-version.txt` | MATCH |
| P-03 | Offizielles Artefakt, Prüfsumme korrekt | SHA256SUMS vs. ZIP | identisch | — | `terraform-version.txt` | MATCH |
| P-04 | Kein Backend / keine Provider-Konfiguration | statische Suche | 0 Treffer | — | §3.1 | MATCH |
| P-05 | Nur lokale Modulquellen | `main.tf` | 7× `./modules/...` | — | §3.1 | MATCH |
| P-06 | Rohstand fmt-konform | `fmt -check -recursive` | 2 Dateien abweichend | **3** | `fmt-check-rohstand.txt` | **FAIL** |
| P-07 | Formatierte Fassung fmt-konform | `fmt -check -recursive` | keine Abweichung | 0 | `fmt-check-formatiert.txt` | PASS |
| P-08 | Änderung nur Formatierung | whitespace-normalisierter Vergleich | 0 funktionale Diffs | — | `fmt-diff-A-B.patch` | MATCH |
| P-09 | Init ohne Backend | `init -backend=false -input=false` | erfolgreich | 0 | `init-validate-rohstand.txt` | MATCH |
| P-10 | Modul valide (Rohstand) | `validate -no-color` | Success | 0 | `init-validate-rohstand.txt` | MATCH |
| P-11 | Modul valide (formatiert) | `validate -no-color` | Success | 0 | `init-validate-formatiert.txt` | MATCH |
| P-12 | Provider geprüft | `version -json` + Lockdatei | aws 6.70.0, time 0.14.2 | 0 | `provider-lock.txt` | MATCH |
| P-13 | `.tf` durch init/validate unverändert | Hashvergleich | 0 Unterschiede | — | `rohstand-tf-nachher.txt` | MATCH |
| P-14 | RIS-Vertrag vollständig | S01/S02-Gaps | GAP-02/06/01/03, CONFLICT-02 offen | — | §7 | **FAIL** |
| P-15 | Plan/AWS/E2E | — | nicht ausgeführt | — | §8 | NOT VERIFIED |

---

## 11. Checkpoint

| Prüfung | Ergebnis |
|---|---|
| Quell-SHAs dokumentiert | RIS `ea35b8c…`, MO `2d5cf2de…` (§1.1) |
| Rohziel unverändert | 34 Dateien, hashes identisch zu S02-Evidence |
| MO unverändert | `HEAD 2d5cf2de…`, `git status` leer |
| Terraform-Binaries/Provider/ZIPs/State im Repo | **keine** (nur Text-Evidence) |
| `git diff --check` / Secret-Prüfung | siehe Chat-Abschluss |
| Commit/Push | siehe Chat-Abschluss (kein Force-Push) |
