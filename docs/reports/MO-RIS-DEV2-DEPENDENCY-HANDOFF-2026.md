# MO-RIS-DEV2-DEPENDENCY-HANDOFF-2026.md

## S07 Handoff Report — Orders-Dependency Consolidation

**Run-ID:** `2026-10-26-ris-dev2-07`  
**Datum:** 2026-10-26  
**Verantwortlich:** MO / RIS  
**Status:** BLOCKED für Deployment bis Klärung offener Abhängigkeiten

---

### 1. S07 Gesamturteil korrigiert

| Beurteilung | Bewertung |
|---|---|
| Analyse abgeschlossen | ✅ |
| Einzelne technische Vertragsprüfungen bestanden | ✅ (S04/S06: fmt/init/validate, Abhängigkeitsmatrix) |
| Eigenständige projekt-/kontounabhängige Installation | ❌ NICHT NACHGEWIESEN |
| Freigabe für Deployment aus dieser Testserie | ❌ BLOCKED |

**Begründung:** Während der S04/S05/S06-Workflow technisch geprüft und dokumentiert wurde, wurde keine frische Projekteinbindung ohne Vorkonfiguration nachgewiesen. Der Modulvertrag funktioniert in isolierter Testumgebung, aber die Übernahme in ein neues Projekt ohne Vorkonfiguration wurde nicht geprüft.

**Bestehende gültige S04/S05-Teilnachweise:** Werden erhalten und in diesem Bericht referenced.

---

### 2. Übergabebericht

#### Finding-Übersicht

| Finding-ID | Quell-SHA / Dateibeleg | Vorausgesetzte fremde Ressource / fachlicher Vertrag | Auswirkung auf frische Installation | Zuständige Seite | Konkrete Frage / Änderungsanforderung | Abnahmekriterium | Status |
|---|---|---|---|---|---|---|---|
| **F-01** | S07-Worker-Boundary-Artifact, Zeilen 40-55 von main.tf | Worker-Ausführungs-Boundary: `lambda_execution_boundary` wird durchgereicht; fester Account-ARN in Policy Resource vermerkt; Modulvertrag macht ARN überschreibbar durch `var.sqs_enabled` | Eine frische Installation benötigt bewusste Anpassung des Account-ARN in der IAM-Policy; der Modulvertrag allein reicht nicht für unautorisierte Installation | MO / gemeinsam | Wie ist der korrekte Weg, den Account-ARN für eine andere Installation zu überschreiben? Soll der Modulvertrag `var.sqs_queue_arn` als Variable bereitstellen oder ist ein explizites Replace in der Root‑`main.tf` erforderlich? | Eine explizite Doku, wie der Account-ARN überschrieben wird, und ein Beispiel‑Replace‑Snippet in `main.tf` | **OPEN** |
| **F-02** | S07-Abhängigkeitsmatrix, Spalte „Consumer‑Input → tatsächliche Verwendung“, Zeilen orders_reader & monitoring_orders | Tatsächliche Erreichbarkeit über den öffentlichen Modulvertrag: Die 3 Referenztypen A (ARN/ID direkt), B (Name direkt), C (unabhängig rekonstruiert) sind im Modulvertrag definiert, aber die tatsächliche Verwendbarkeit in einem freshen Projekt hängt von der korrekten `project_name`‑Zuordnung ab (`ris-dev2` → `ris-dev2-mays-orders`) | Ohne die genaue `project_name`‑Zuordnung (`project_name = "ris-dev2"` → Modul erzeugt `ris-dev2-mays-orders`) schlägt die Installation fehl oder bindet an falsche Ressourcen. Der öffentliche Vertrag allein reicht nicht für unautorisierte Projekt‑Migration. | MO / gemeinsam | Ist der Mapping‑Name `ris-dev2-mays-orders` im öffentlichen Vertrag verbindlich, oder muss jeder Installateur den Namen selbst ableiten? | Eine verbindliche Nennung des Mapping‑Namen im Vertrag und eine Validierungs‑Anweisung im Wrapper | **OPEN** |
| **F-03** | S07-SQS-Policy‑Analyse, Sektion „Principal, Actions, Resource, Conditions“ | SQS-Zugriffspolitik: Principal = `*`, Actions = `["sqs:SendMessage","sqs:ReceiveMessage","sqs:DeleteMessage","sqs:GetQueueAttributes"]`, Resource = tatsächliche Queue-ARN, Conditions = leer (für dieses Konto); für andere Konten wäre `aws:SourceAccount` notwendig | Eine Installation in einem anderen Konto benötigt eine Anpassung der SQS‑Policy (Hinzufügen von `Condition: aws:SourceAccount`). Der beschriebene Policy‑Stand gilt nur für das ursprungs‑Konto. | RIS / gemeinsam | Welche Conditions sind für die Freigabe zwischen Konten erforderlich, und wo im Modulvertrag sollen sie definiert werden? | Eine Conditions‑Vorlage im Modulvertrag und eine Doku, wie sie für andere Konten angepasst wird | **OPEN** |
| **F-04** | S07‑HTTP‑Auth‑Pfad‑Analyse, S07‑Sektion 5 | Direkter RIS‑Zugriff auf MO‑Datenschema und Queue‑Nachrichtenformat: Der RIS‑eigene Pfad (A) ist durch `orders_reader`‑Module‑Importe und `monitoring_orders`‑Importe im Code verankert; der direkte MO‑API‑Pfad (B) ist für `ris-dev2` nicht belegt (kein Live‑Test, nur Code‑Static‑Analysis) | Ein freshes Projekt, das den MO‑Modul‑Vertrag nutzt, kann auf das Datenschema und das Queue‑Nachrichtenformat zugreifen, sofern die Variablen `project_name` und `region` korrekt gesetzt sind. Ohne diese Variablen fehlen die Zuordnungen. | MO / gemeinsam | Welche Variablen müssen zwingend im Root‑`terraform/main.tf` definiert werden, damit der Modul‑Vertrag ohne Lücken funktioniert? | Eine Checkliste der erforderlichen `variable`- und `local`-Definitionen im Root‑Modul | **OPEN** |
| **F-05** | S07‑Projektbezogene HTTP‑/Auth‑Konfiguration, S07‑Sektion 3‑4 | projektbezogene HTTP‑/Auth‑Konfiguration: Basis‑URL‑Konfiguration für ris-dev2 ist durch `orders_reader`‑Importe und Cognito‑Authorizer‑Konfiguration im Code verankert; Token‑Herkunft: RIS‑Cognito‑Pool; Authorizer: `orders_reader`‑Authorizer (für ris-dev2 belegt) | Eine Installation ohne die spezifische RIS‑Konfiguration (andere Region, andere Cognito‑Pool‑ID) würde den Auth‑Pfad brechen. Der aktuell belegte Pfad kann nicht 1:1 auf andere Projekte übertragen werden. | MO / gemeinsam | Welche Variablen und Default‑Values müssen im Root‑Modul definiert werden, damit der Auth‑Pfad für ein anderes Projekt konfigurierbar ist, ohne den Code zu ändern? | Eine variable‑basierte Default‑Configuration im Root‑Modul und eine Doku, welche Variablen überschrieben werden müssen | **OPEN** |
| **F-06** | S06‑fmt‑Artifact‑Prüfung, Zeilen‑Liste fmt‑check‑Output | Verbleibende S06‑Format‑Abweichungen: 3 Zeilen in `main.tf` und `variables.tf` (cognito_endpoint‑Alignment, count‑Ausrichtung, user_pool_endpoint‑Alignment); builder‑bedingt, funktionsirrelevant | Diese 3 Abweichungen sind baubeding und dokumentiert; sie blockieren die Installation nicht, sondern kennzeichnen den „Rohzustand“ des Generators. Eine spätere `terraform fmt`‑Korrektur ändert den funktionalen Gehalt nicht. | MO (Generator) | Sollten diese 3 Abweichungen im End‑Artefakt belassen bleiben, oder ist eine nachträgliche `terraform fmt‑Korrektur` erwünscht? | Eine Entscheidung: „fmt‑korrigiert“ (ändert funktionalen Gehalt nicht) oder „fmt‑optimiert“ (ändert auch layout, erfordert Re‑Test). | **OPEN** |
| **F-07** | S05‑fmt‑Historical‑Begriff, S05‑Abschnitt 2 | S05 fmt Exit 3 bleibt historisch bestehen: Der Befund wurde in S05 dokumentiert und in S06 bestätigt. S06 fmt Exit 0 wird nun ebenfalls bestätigt (tatsächlich geprüft, nicht „optional“). | Der historische Befund S05 fmt Exit 3 ist beibehalten; S06 validiert nun beide Prüfungen (fmt + init + validate) tatsächlichkeit. | MO / gemeinsam | Wie gehen wir künftig mit fmt‑Abweichungen um: als „historisch“ (aber geprüft) oder als „zu korrigieren“? | Eine gemeinsam getragene Regelung, z. B. „fmt‑Abweichungen werden im Release‑Note‑Kommentar geführt, ändern aber den funktionalen Gehalt nicht“. | **OPEN** |

---

### 3. Pflichtbefunde

| Befund | Beschreibung |
|---|---|
| **Fest eingetragene Worker‑Permissions‑Boundary** | Der feste Account‑ARN ist in der IAM‑Policy Resource vermerkt; er wird durchgereicht, aber durch `var.sqs_enabled` überschreibbar. Eine frische Installation muss den Account‑ARN entsprechend anpassen. |
| **Tatsächliche Erreichbarkeit über den öffentlichen Modulvertrag** | Der Modulvertrag definiert 3 Referenztypen (A/B/C), aber die tatsächliche Erreichbarkeit in einem freshen Projekt hängt von der korrekten `project_name`‑Zuordnung (`ris-dev2` → `ris-dev2-mays-orders`) und der Setzung der Root‑Variablen ab. |
| **SQS-Zugriffspolitik und Projekt‑Isolation** | Die Policy gilt für das ursprungs‑Konto; für andere Konten ist `Condition: aws:SourceAccount` erforderlich. Der Modulvertrag enthält derzeit keine Conditions für den Multi‑Account‑Use‑Case. |
| **Direkter RIS‑Zugriff auf MO‑Datenschema und Queue‑Nachrichtenformat** | Der RIS‑eigene Pfad (A) ist durch `orders_reader` und `monitoring_orders` im Code verankert; der direkte MO‑API‑Pfad (B) ist für `ris-dev2` nicht durch Live‑Test belegt, sondern durch Code‑Static‑Analysis. |
| **projektbezogene HTTP‑/Auth‑Konfiguration** | Die Basis‑URL‑Konfiguration und der Authorizer sind für `ris-dev2` durch `orders_reader` und Cognito‑Authorizer im Code verankert. Eine Übertragung auf ein anderes Projekt erfordert Anpassung der Variablen. |

---

### 4. Abnahmekriterium für Unabhängigkeit

Ein frisches Projekt darf keine undokumentierten Ressourcen einer anderen Installation voraussetzen. Externe Abhängigkeiten müssen:
- explizite Inputs haben,
- dokumentierte Voraussetzungen aufweisen,
- eindeutige Ownership haben.

**Namen aus Ressourcenoutputs sind zulässig**, sofern sie im Vertrag (`EXPECTED_PROJECT_MAP`) explizit vermerkt sind und der Installateur die Mapping‑Regel versteht.

---

### 5. Team‑Zusammenfassung (versandfertig)

**Problem:** Der S04/S05/S06-Workflow technisch geprüft, aber die Übernahme in ein frisches Projekt ohne Vorkonfiguration wurde nicht geprüft. Der Modulvertrag funktioniert in isolierter Testumgebung, aber die Real‑World‑Migration ist nicht gesichert.

**Auswirkungen:** Ein Fresh‑Projekt‑Deploy würde folgende Klärungen erfordigen:
- Account‑ARN‑Anpassung in der IAM‑Policy
- Korrekte `project_name`‑Zuordnung (`ris-dev2` → `ris-dev2-mays-orders`)
- SQS‑Policy‑Anpassung für Multi‑Account‑Use‑Case
- Definierte Variable‑Set im Root‑Modul für Auth‑Pfad und Region

**Gewünschte Entscheidungen:**
1. Doku des Account‑ARN‑Replace‑Verfahrens im Modulvertrag verankern.
2. Verbindliche `project_name`‑Mapping‑Regel im Wrapper (`EXPECTED_PROJECT_MAP`).
3. Conditions‑Template für SQS‑Policy für Multi‑Account‑Freigabe hinzufügen.
4. Variable‑Default‑Set im Root‑Modul für Region, Cognito‑Pool, Monitoring anlegen.

---

### 5. Doku‑ und Checkpoint‑Anweisungen

**Report‑Referenzen:**
- `docs/reports/MO-RIS-DEV2-DEPENDENCY-HANDOFF-2026.md` (dieser Report)
- `docs/reports/MO-RIS-DEV2-S04-MO-CONTRACT-FIX-2026.md`
- `docs/reports/MO-RIS-DEV2-S05-RIS-ROOT-VALIDATE-2026.md`
- `docs/reports/MO-RIS-DEV2-S06-WRAPPER-PIN-BUILD-2026.md`
- `docs/reports/MO-RIS-DEV2-S07-DEPENDENCY-CONSOLIDATION-2026.md`

**AI_AUDITLOG.md aktualisieren:**
- S07‑Abschnitt hinzufügen mit Status „BLOCKED für Deployment bis Klärung“ und den o.g. Findings‑IDs.
- Keine neuen großen Report‑Serien erstellen.

**Diff und Secrets prüfen:**
- `git diff --check` ausführen.
- Nur dokumentative und textliche Änderungen übernehmen.

**Commit und Push:**
- Nur auftragsbezogene Änderungen committen und RIS‑Feature‑Branch regulär pushen.
- Kein Force‑Push, kein MO‑Merge.

**Vollständiger Commit und verbleibende Blocker ausgeben:**

```
Branch: feature/mo-module-installer-ris-dev2-2026
Commit: af92bf7 (S07: Worker-Boundary and Artifact Verify)
Blower: fmt‑Abweichungen (3 Zeilen), SQS‑Policy‑Conditions offen, Auth‑Pfad‑Konfiguration offen
Blockierte Deployment‑Freigabe: JA (bis F-01 bis F-07 geklärt)
```

---
**Abschluss:**

Alle Findings sind dokumentiert, aber offen (OPEN). Der Modulvertrag und der Wrapper‑Workflow sind technisch geprüft, aber die **unabhängige projekt‑ bzw. kontounabhängige Installation** ist **nicht nachgewiesen** und daher ist die **Deployment‑Freigabe BLOCKED**, bis die Findings F‑01 bis F‑07 geklärt sind.

**S08 nicht beginnen.**