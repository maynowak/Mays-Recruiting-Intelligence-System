# Mays-Orders-Version in `ris-dev2`

**Stand:** 2026-11-15
**Geltungsbereich:** RIS-Integration (`feature/ris-mo-addition-agent-e2e-01`)
**Zweck:** Eine Frage, drei Ebenen — damit „welche Version?" nicht mehr
missverstanden werden kann.

---

## Kurzfassung

In `ris-dev2` läuft **aktuell keine Mays-Orders-Instanz**. Der Terraform-State
ist leer. Die RIS-Konfiguration baut das Orders-Modul aus der Linie
**`v0.5.0-rc.2` + additive Integration**, gepinnt auf Commit
`122ec65ac7ab5a044d2b2576ae6b7e4c325246b8`.

---

## Die drei Ebenen

| Ebene | Stand | Beleg |
|---|---|---|
| **1. Live in AWS** | **nichts** — 0 Ressourcen | State `s3://ris-dev2-tf-state-dev/env:/ris-dev2/dev/terraform.tfstate`, `serial 36`, `lineage a0bd361d-…`, `resources: 0` |
| **2. Dokumentierter Modul-/Clone-Pin** | `5cf50a0` = Tag **`v0.5.0-rc.2`** | `installer/mays-orders-clone.pinned.json` |
| **3. Aktuell gebaute Modulquelle** | `122ec65` auf `feature/mo-agent-order-body-01` (ungetaggt) | `installer/mays-orders-builder.pinned.json`, `installer/build_mays_orders_module.py` (`PINNED_COMMIT`) |

`ris-dev2` wurde am **2026-11-09** kontrolliert abgebaut. Der leere State ist
reconciled; ein Plan mit 191 Creates wäre eine **Neuinstallation der gesamten
RIS-Plattform** und ist nicht freigegeben.

---

## Commit-Linie

```
v0.5.0-rc.2 (5cf50a0)  →  Entwicklungsbasis 9627eb2  →  122ec65
        ANCESTOR                    ANCESTOR
```

| Prüfung | Ergebnis |
|---|---|
| `git diff 5cf50a0 9627eb2 -- lambda/src` | **leer** — Basis ist lambda-identisch zu RC2 |
| `git merge-base --is-ancestor 5cf50a0 9627eb2` | ANCESTOR |
| `git merge-base --is-ancestor 9627eb2 122ec65` | ANCESTOR |
| Löschungen im Feature-Diff | keine (`--diff-filter=D` leer) |
| RC3/RC4 oder Orders-main-Upgrade | **nicht** verwendet |

`122ec65` enthält zusätzlich zu A04–A07 die Builder-Korrekturen
(Lambda-ZIP aus der Quelle, voller SHA im Manifest, `agent_transport`,
deterministisches ZIP).

---

## Was das Modul ausliefert

| Element | Wert |
|---|---|
| Preset | `orders-service` |
| Module | 8 (`agent_transport`, `api`, `cognito`, `dynamodb`, `iam`, `lambda`, `sqs`, `sqs_worker`) |
| Lambda-ZIP | 13 Dateien |
| ZIP-SHA-256 | `1801e9fbe0d8d7dd70f8cc46699ff2eae6d44c2c590c5472804e022854ead222` |
| Manifest `source.commit` | `122ec65ac7ab5a044d2b2576ae6b7e4c325246b8` |
| `enable_agent_transport` | Default `false` (Integration vorhanden, nicht aktiv) |

Das generierte Modul liegt **nicht** im Repository (Build-Artefakt). Es wird aus
dem Pin reproduziert; Details und Testnachweise stehen in
[`docs/reports/MO-RIS-ORDERS-MODULE-REBUILD-01.md`](../reports/MO-RIS-ORDERS-MODULE-REBUILD-01.md).

---

## Wie man den Stand prüft

```powershell
# Pin
Get-Content installer/mays-orders-builder.pinned.json

# Live-State (nur lesen)
aws s3 cp "s3://ris-dev2-tf-state-dev/env:/ris-dev2/dev/terraform.tfstate" - `
  --profile default | ConvertFrom-Json | Select-Object serial, resources

# Modul bauen und Manifest prüfen
python -m module_builder build --preset orders-service `
  --project-name ris-dev2-mays-orders --source <mays-order-aws> --target <dir>
Get-Content <dir>/module-builder.manifest.json
```

---

## Abgrenzung

- **Stufe 1 (lokal) und 2 (generiertes Modul)** sind belegt.
- **Stufe 3 (AWS-Plan)** ist für RIS belegt, für das Orders-Konto
  `240571105849` **nicht** (403 auf den Orders-State).
- **Stufe 4 (Live-E2E)** ist **nicht** erfolgt.

Aus diesem Dokument folgt **keine AWS-Freigabe**.

---

## Verwandte Dokumente

- [`docs/reports/MO-RIS-ORDERS-MODULE-REBUILD-01.md`](../reports/MO-RIS-ORDERS-MODULE-REBUILD-01.md) — Modul-Rebuild, Hashes, Tests
- [`docs/reports/MO-RIS-TESTED-MODULE-RECONCILIATION-01.md`](../reports/MO-RIS-TESTED-MODULE-RECONCILIATION-01.md) — vorheriger Blocker-Befund
- [`docs/roadmap/ROADMAP.md`](../roadmap/ROADMAP.md) — Gate-Stand
