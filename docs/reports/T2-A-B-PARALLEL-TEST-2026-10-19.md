# T-2: Test A + B gleichzeitig — „was testet der Test?" (2026-10-19)

**Ziele:** `ris-a` (project_name=ris-a) und `ris-b` (project_name=ris-b), beide live gleichzeitig
**Vorbedingung:** A apply → 167 added; B apply → 167 added (beide Exit 0)
**Runner:** `scripts/parallel_tests.sh ris-b` + `scripts/parallel_tests.sh both`

## Was dieser Test testet
1. **Koexistenz** — leben beide Installationen gleichzeitig nebeneinander?
2. **Vollständigkeit je Installation** — je 6 Lambdas + 11 Tables unter eigenem Präfix?
3. **Kein Cross-Talk** — zeigt B-Reader auf `ris-b` (nicht auf A) und umgekehrt?
4. **Namenseindeutigkeit** — existiert kein Ressourcenname in beiden Installationen?
5. **Eigenständiges Monitoring** — beide Dashboard-Sätze vorhanden, keiner überschrieben?
6. **Stabilität von A** — bleibt A idempotent, solange B existiert?

## Ergebnis: 11 bestanden, 0 fehlgeschlagen

| # | Was wir testen | Erwartung | Ist | Ergebnis |
|---|---|---|---|---|
| T2.1 | `ris-a-dev-api` `/health` | 401 | 401 | PASS |
| T2.1 | `ris-b-dev-api` `/health` | 401 | 401 | PASS |
| T2.2 | A-Lambdas | ≥6 | 6 | PASS |
| T2.2 | B-Lambdas | ≥6 | 6 | PASS |
| T2.2 | A-Tables / B-Tables | ≥11 / ≥11 | 11 / 11 | PASS |
| T2.3 | A-Reader Env | `ORDERS_TABLE=ris-a`, Queue `ris-a-orders-queue` | identisch | PASS |
| T2.2b | B-Reader Env | `ORDERS_TABLE=ris-b` | `ris-b` | PASS |
| T2.4 | Namensüberschneidungen A∩B | 0 | 0 | PASS |
| T2.5 | `ris-a-overview` + `ris-b-overview` | je 1 | je 1 | PASS |
| T2.6 | A-Idempotenz während B läuft | Exit 0 (0/0/0) | Exit 0 | PASS |

## Beleg (Auszug)
```
A-Reader: ORDERS_TABLE=ris-a  ORDERS_SQS_QUEUE_URL=…/ris-a-orders-queue
B-Reader: ORDERS_TABLE=ris-b
Plan A bei laufendem B: Exit 0 (kein Drift)
Namensüberschneidungen: 0
```

## Schlussfolgerung
Parallele Installationen sind sauber trennbar, **sofern** `project_name` unterschiedlich ist.
Getrennt über: Workspace (State `env:/ris-a|ris-b/terraform.tfstate`) + Ressourcenpräfix.
Die Verkabelung bleibt je Installation intern (Module-Outputs), kein Cross-Talk.
