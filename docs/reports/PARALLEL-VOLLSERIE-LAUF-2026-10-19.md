# Vollserie-Lauf: A → A+B → Destroy B → A → Destroy A (2026-10-19)

**Ziel:** Nicht mehr 12–13 Stichproben, sondern die dokumentierte Vollbatterie
(VOLLTEST 34 + TRUE-Paralleltest-Gates + Regression) je Installation.
**Runner:** `scripts/parallel_tests.sh <ris-a|ris-b|both|destroy-check|static>`
**Vorheriger Fix:** `PARALLEL-HEALTH-LOGGROUP-FIX-2026-10-19.md` (+2 Log-Groups, 167→169)

## Ablauf und Ergebnisse

| # | Schritt | Ergebnis | Checks |
|---|---|---|---|
| 0 | **Static** (fmt, validate, Unit-Tests, Bundles) | fmt/validate sauber, 3 Kontrakt-Suiten grün, 4 Bundles vorhanden | **9 PASS, 1 WARN** |
| 1 | **Install A** (`project_name=ris-a`, ws `ris-a`) | `169 added, 0 changed, 0 destroyed`, Exit 0 | — |
| 2 | **Vollserie A (allein)** | 0 Fremd-Namen im State/Plan, kein Drift, Vollinventar | **63 PASS, 1 WARN** |
| 3 | **Install B** (`project_name=ris-b`, ws `ris-b`) | `169 added`, Exit 0, 0 × `mays-ris-dev`, 0 echte A-Präfixe | — |
| 4 | **Vollserie B (A+B live)** | eigener State frei von A-Namen, Reader zeigt auf `ris-b` | **63 PASS, 1 WARN** |
| 5 | **Parallelserie both** | 0 Namensüberschneidung, kein Cross-Talk, beide State getrennt | **22 PASS** |
| 6 | **Destroy B** | Lauf 1 `BucketNotEmpty` → geleert, Lauf 2 Exit 0, State 0 | — |
| 7 | **destroy-check B** | alles 0, **LogGroups → 0** (Fix verifiziert) | **16 PASS** |
| 8 | **Vollserie A nach B-Zerstörung** | A unverändert, idempotent | **63 PASS, 1 WARN** |
| 9 | **Destroy A** | Lauf 1 `BucketNotEmpty` → geleert, Lauf 2 Exit 0, State 0 | — |
| 10 | **destroy-check A** | alles 0 inkl. Log-Groups/Trail/OAC/IAM | **16 PASS** |

**Summe: 252 Prüfungen bestanden, 0 fehlgeschlagen, 4 Warnungen**
(4× dieselben 2 dokumentierten Baseline-Defekte in `tests/test_ris_installer.py`).

## Konto-Endbestand

```
Lambdas 0 · APIs 0 · SQS 0 · Dashboards 0 · Alarme 0 · Log-Groups 0 · Cognito 0
Tabellen: nur mays-ris-tf-lock (Backend)
Buckets:  nur mays-ris-tf-state-dev (Backend)
CloudFront: E1R3BHTJNMC6XW + mays-ris-e2e-test-test-health-oac  (fremd, unberührt)
```

## Was der Lauf an echten Signalen erzeugt hat

1. **Log-Groups überlebten Destroy** (je 2 pro Installation) → Modul-Fix, siehe eigener
   Report; verifiziert durch `destroy-check … LogGroups → 0`.
2. **`filename`-Pfad erzeugt Schein-Drift:** `terraform/../lambda/dist/x.zip` (Apply)
   vs `lambda/dist/x.zip` (Test) → Plan meldete `3 to change`. Der Runner nutzt jetzt
   exakt die Apply-Pfade; sonst hätte die Vollserie dauerhaft falschen Drift gemeldet.
3. **Der Workspace-Guard hat live gegriffen:** ein A-Lauf bei selektiertem `ris-b`
   brach mit `FAIL [S1.1] … ist='ris-b'` ab statt falsch zu grünen — genau der Fehler
   aus T-3, jetzt maschinell verhindert.

## Was der Lauf an Runner-Fehlern aufgedeckt hat (korrigiert)

| ID | Fehler | Fix |
|---|---|---|
| S1.2 | Data-Sources heißen `module.x.data.y`, Filter `^data\.` zählte sie mit | Filter `(^|\.)data\.`, Erwartung 169 |
| S2.6 | `email` steht am RIS-Pool, nicht am Orders-Pool | Prüfung auf `${P}-dev-users` |
| S3.3 | `length(...)` wird pro Paginierungs-Seite ausgegeben (`0\n0`) | Zählung über Route-Keys |
| S4.3 | Suchpattern enthielt ein Anführungszeichen | Pattern `:table/$P` |
| S1.3/S1.4 | `ris-a` matchte Substring in `ris-api` (Cognito-Resource-Server) | Wortgrenzen-Matcher (`ris-api` ≠ `ris-a`) |
| S5.2 | B-Suite verlangte „A existiert nicht" — im Parallelbetrieb falsch | Zustand „Parallelbetrieb": andere Installation vollständig + eigener Reader |
| S6.1 | Baseline-Defekte wurden als FAIL gewertet | WARN, nur wenn alle Fehlschläge zur bekannten Baseline gehören |

## Einordnung der Warnung (kein Fehler dieses Laufs)

`tests/test_ris_installer.py`: 2 failed / 35 passed
(`test_install_dry_run_performs_no_mutation`, `test_validate_skips_workspace_without_backend`).
Teil der in `AGENTS.md` Z.39 dokumentierten 5 Baseline-Defekte. Der Runner meldet sie
sichtbar als WARN, verschweigt sie aber nicht und lässt sie die Parallel-Suite nicht
verfälschen.
