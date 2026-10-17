# Composite-Lifecycle TODO

Offene Punkte der RIS↔Orders-Komponenten-Integration. Jeder Eintrag trägt
seinen **Belegstatus** und seine **Quelle** — ein Punkt ohne Beleg ist eine
Vermutung und als solche markiert.

**Belegstatus** (Sprache aus `MO AGENTS.md`, damit beide Seiten vergleichbar
bleiben): `VERIFIED` = gemessen · `TESTED` = durch Test abgesichert ·
`IMPLEMENTED` = gebaut, Endabnahme fehlt · `PLANNED` = entschieden, nicht
gebaut · `NOT TESTED` = Behauptung ungeprüft · `BLOCKED` = wartet auf Entscheidung.

**Regel für dieses Dokument:** Ein Punkt wird geschlossen, wenn die Messung da
ist, die ihn schließt — nicht wenn der Code „fertig aussieht". Drei Punkte
unten sind genau deshalb noch offen, obwohl Code existiert.

Stand: 2026-10-18 · Baseline `9892b41`

---

## A · Der Plan, den wir gerade gemacht haben

Reihenfolge ist Abhängigkeit, nicht Priorität. A1 ist Voraussetzung für A2;
ohne A1 ist A2 nicht sauber lösbar, aber A1 allein ändert Verhalten, ohne den
offiziellen Zustand unterscheidbar zu machen.

| # | Punkt | Status | Quelle |
|---|---|---|---|
| **A1** | **Phasen als erste Klasse** statt eines Booleans. `ctx.dry_run` ist heute *ein* Schalter für *alle* Mutationen — deshalb ist „Order ja, RIS nein" nicht ausdrückbar, und deshalb behandelt `validate_orders_binding` einen legitimen Stopp wie einen Defekt. | `PLANNED` | `MAYS-RIS-DRYRUN-FULL-CHAIN-01` |
| **A2** | **Die zwei Zustände unterscheiden.** RIS ungebunden *bewusst gestoppt* → warnen. RIS ungebunden *Binding kaputt* → fail-closed. | `PLANNED` | `MAYS-RIS-DRYRUN-FULL-CHAIN-01` |
| **A3** | **Phasenreihenfolge korrigieren.** Ausführung ist heute `A, C, B, D, E` — die Buchstaben passen nicht einmal zur Reihenfolge. Soll: `package → bootstrap → orders validate → orders plan → RIS plan → orders deploy → RIS apply`, also alle read-only zuerst und Mutationen zuletzt. | `PLANNED` | `_cmd_install`-Docstring |
| **A4** | **Packaging-Fehler lässt Orders deployed zurück.** Wenn Phase D fehlschlägt, ist Orders schon live und wird *nicht* zurückgerollt. Bei A3 ist das entschärft, weil D vor dem Deploy käme — der Punkt ist also eine Folge von A3, kein eigener Fix. | `PLANNED` | `_cmd_install`-Docstring |
| **A5** | **Doppelte Arbeit pro Lauf.** `validate_aws_context()` läuft inline *und* in `_cmd_preflight()`; Orders-`validate` läuft in preflight *und* in `_run_orders_component()`. Ergebnis: zwei STS-Calls und zwei komplette MO-Validierdurchläufe. | `PLANNED` | `_cmd_install`-Docstring |
| **A6** | **Phase `test` existiert nicht.** Die Phasenfolge endet bei `apply`. Es gibt keine Verifikationsphase, die nach dem Deploy prüft, ob RIS und Orders wirklich zusammenspielen. | `NOT STARTED` | Phasenliste, gemessen |
| **A7** | **Vorhergesagte ARNs gegen echte prüfen.** Der Dry-Run leitet die Tabellen-ARN ab (Terraform kennt sie vor dem Create nicht). Beim echten Apply werden die echten Outputs gelesen — aber **nicht verglichen**. Empfohlen, bewusst nicht gebaut, weil es zu A1 gehört. | `PLANNED` | `MAYS-RIS-DRYRUN-FULL-CHAIN-01` |

### Belegt, was A1 überhaupt möglich macht

`terraform validate` auf RIS **ohne** jede Orders-Bindung: `Success!` — gemessen.
Die fail-closed-Bindung schlägt erst beim `plan` (`Invalid value for variable`,
Modul-Ebene). Deshalb können RIS-`init` und RIS-`validate` **vor** dem
Orders-Deploy laufen, und deshalb ist Ihre Phasenfolge ausführbar.

---

## B · Zustand und Umbenennung im Konto

| # | Punkt | Status | Quelle |
|---|---|---|---|
| **B1** | **Serial-45-State: migrieren oder als Ist-Aufnahme lassen?** Der autoritative State liegt auf einem verschachtelten Legacy-Pfad. Entscheidung steht aus; Read-only-Backup mit MANIFEST ist vorbereitet, aber nicht ausgeführt. | `BLOCKED` | `26a83fb`, `MAYS-RIS-STATE-PATH-UNIQUE-01` |
| **B2** | **2 verbliebene Legacy-Nested-Objekte entfernen** (`env:/mays-ris/env:/mays-ris/…`). Erst nach B1, sonst wird möglicherweise der Falsche gelöscht. | `BLOCKED` (B1) | `MAYS-RIS-STATE-PATH-UNIQUE-01` |
| **B3** | **Flat State eines Composite** (`env:/mays-ris-composite-a-mays-orders/dev/terraform.tfstate`) liegt außerhalb des neuen `orders/`-Bereichs. Migrationskandidat, wird von `discover` bewusst nicht gelistet. | `PLANNED` | `MAYS-RIS-COMPONENT-STATE-CONSOLIDATION-01` |
| **B4** | **`mays-orders-ci-artifacts-dev`** — weder Team besitzt es laut MO-Handoff-Report. Kein State bekannt. Gehört MO. | `BLOCKED` (fremd) | MO-Report, `D4` |
| **B5** | **Adoptions-Reihenfolge D1**: Composite deployen, *dann* alten `mays-orders`-Satz abbauen. Destroy war durch die RIS-seitige Rebindung blockiert. | `BLOCKED` | `MAYS-RIS-ORDERS-A-CLEANUP-COMPLETE-01` |

---

## C · Grenzen, die gemessen offen sind

Diese Punkte sind **nicht** bequem, aber ehrlich: jeder wurde gemessen und
trotzdem nicht behoben.

| # | Punkt | Status | Quelle |
|---|---|---|---|
| **C1** | **Echter Gleichzeitigkeitstest fehlt.** Belegt ist nur sequentielles Interleaving. Zwei wirklich gleichzeitige Prozesse könnten auch um das **geteilte Backend-Lock** rennen — die zweite Hälfte des Problems, ungetestet. | `NOT TESTED` | `MAYS-RIS-TF-WORKSPACE-CONSOLIDATION-01` |
| **C2** | **MO-eigene Läufe im gemeinsamen Klon rennen weiter untereinander.** Von RIS aus nicht lösbar. Gehört upstream ans MO-Team. | `NOT FIXABLE HERE` | `MAYS-RIS-TF-WORKSPACE-CONSOLIDATION-01` |
| **C3** | **Collision-Scan ist blind für Composite-Namen.** Der Scan ist substring-basiert: die Probe `mays-orders` findet 9 Treffer, die Probe auf den Composite-Namen findet 0. Ein grüner Preflight heißt also **nicht** „keine andere Orders-Installation". | `IMPLEMENTED` (zu schwach) | `MAYS-RIS-TF-WORKSPACE-CONSOLIDATION-01` |
| **C4** | **Cognito-Backup-Bucket überschreitet 63 Zeichen** bei langen Composite-Namen. `ORDERS_ENABLE_COGNITO_BACKUP=False` umgeht es, aber der Name selbst wird nicht modelliert. `ORDERS_PROJECT_NAME_MAX_LENGTH=39` ist am CloudTrail-Limit ausgerichtet, nicht an der tatsächlichen Bindung. | `IMPLEMENTED` (Workaround) | `D3` |
| **C5** | **`enable_cognito_backup=false` ist nur ein CLI-Var und persistiert nicht.** Nach dem G3-Präzedenzfall geht die Konfiguration beim nächsten ungepinnten Lauf verloren. | `PLANNED` | `D2`, `G3-COGNITO-CONFIG-PERSISTENCE-01` |

---

## D · Entscheidungen, die außerhalb liegen

Nicht von uns zu entscheiden. Hier nur festgehalten, damit sie nicht
untergehen.

| # | Punkt | Status |
|---|---|---|
| **D1** | **MO-Stufe A freigeben?** MO hat „Module Builder" vorgeschlagen (Stufe A: Ganz-Stack als ein Meta-Modul, 2–3 PT; Stufe B: Baukasten, 7–10 PT; Stufe C: Registry, 3–5 PT). Status dort: `DECISION PENDING`, eigene Rückmeldung „klingt gut" + **„stop"**. Kein Start ohne ausdrückliche Freigabe. | `BLOCKED` |
| **D2** | **MO-Pin:** gepinnt auf `5cf50a0`. Team-Stand hat 4 Commits darüber, darunter der Handoff-Report und die Module-Builder-Assessments. Upgrade nur nach dem Verfahren in `installer/mays-orders-clone.pinned.json` (Backup, Checkout, Lifecycle erneut, Plan-Diff, erst dann deploy). | `PLANNED` |
| **D3** | **Tabellen-Direktzugriff durch Konsumenten:** MO schließt ihn per Governance-Regel aus („GATE-6-Bypass darf sich nicht wiederholen"). Unser `orders-reader` spricht die DDB-Tabelle direkt an. Bewertung steht aus, gehört an beide Teams. | `BLOCKED` |

---

## E · Absichtlich nicht getan

Damit niemand diese Punkte später für einen Fund hält. Jeder ist eine
bewusste Entscheidung, keine offene Lücke.

| Punkt | Warum nicht |
|---|---|
| `TF_CLI_ARGS_init` zur Umleitung der Komponenten-Bucket | Umgehung der eigenen Gates der Komponente. Nicht verwendet. |
| `TERRAFORM_WORKSPACE` als Workspace-Wähler für die Komponente | wirkungslos: MOs CLI überschreibt ihn mit `project_name` (`main.py:386`). |
| `TF_WORKSPACE` für die Komponente | bricht deren eigene Workspace-Routine (`workspace select`), gemessen exit 0 → exit 1. |
| Ableitung der ARN aus dem Namen „reicht" | reicht für die **Probe**, nie für ein laufendes System. Siehe A7. |
| Komponenten-Routine ändern, damit sie den Override verträgt | Mays-Orders-AWS ist out of bounds — und wäre der Konsument, der der Komponente diktiert. |
| ARN-Identitätslücke in `validate_orders_binding` „beheben" | nicht erreichbar: beide Table-Outputs stammen aus derselben Ressource. Bleibt als Defence in Depth. |

---

## Wie ein Punkt hier schließt

1. Messung durchführen, die den Punkt beweist — nicht der Code, nicht der Test.
2. Gegenprobe: den Fix zurücknehmen und **sehen**, dass der Test fällt.
   Ein grüner Test ohne gefallene Gegenprobe gilt hier als nicht geliefert;
   drei Punkte in dieser Sitzung waren genau so grün.
3. `AI_AUDITLOG.md`-Eintrag anhängen, dann lokaler Commit.
4. Hier streichen und den Belegstatus nennen — nicht einfach löschen.
