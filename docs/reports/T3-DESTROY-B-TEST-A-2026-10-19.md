# T-3: Destroy B, dann Test A — „was testet der Test?" (2026-10-19)

**Ziele:** B muss weg sein, A muss unversehrt und funktionsfähig sein
**Runner:** `scripts/parallel_tests.sh destroy-check ris-b` + `scripts/parallel_tests.sh ris-a`

## Was dieser Test testet
1. **Vollständigkeit des Abbaus** — ist von `ris-b` *nichts* mehr übrig?
2. **Unversehrtheit von A** — alle A-Zählwerte identisch zu T-1?
3. **Funktion von A weiterhin** — A-API antwortet weiterhin 401 (geschützt)?
4. **Idempotenz von A** — kein Drift nach B-Zerstörung?
5. **Backend erhalten** — tf-lock + tf-state noch da, fremde e2e-Ressourcen da?

## Destroy-B Durchführung
```
Durchlauf 1: rc=1, BucketNotEmpty (ris-b-cloudtrail, ris-b-dev-health-public)
  → beide Buckets inkl. Versionen geleert
Durchlauf 2: Destroy complete! Resources: 2 destroyed (rc=0)
State ris-b: 0 Ressourcen
```

## Ergebnis: 13 bestanden, 0 fehlgeschlagen (+ PyTest 37)

| # | Was wir testen | Erwartung | Ist | Ergebnis |
|---|---|---|---|---|
| T3.1 | `ris-b`-Lambda/Tables/APIs/Dashboards/Queues | 0/0/0/0/0 | 0/0/0/0/0 | PASS |
| T3.2 | A-Lambdas/Tables/APIs | 6/11/2 | 6/11/2 | PASS |
| T3.3 | A `/health` | 401 | 401 | PASS |
| T3.4 | A-Idempotenz | Exit 0 | Exit 0 (0/0/0) | PASS |
| T3.4 | A-Env unverändert | `ris-a` | `ris-a` + `ris-a-orders-queue` | PASS |
| T3.4 | A-Dashboards | je 1 | je 1 | PASS |
| T3.4 | A-ESM | Enabled/5 | Enabled/5 | PASS |
| T3.5 | Backend `mays-ris-tf-lock` | ACTIVE | ACTIVE | PASS |
| T3.5 | Backend `mays-ris-tf-state-dev` | existiert | existiert | PASS |
| T3.5 | fremde e2e-Distribution | existiert | existiert | PASS |
| T3.4 | PyTest health / credentials | 12 / 25 | 12 / 25 | PASS |

## Fund während des Tests (wichtiger als der Test selbst)
Der erste Idempotenz-Lauf lief im **falschen Workspace (`ris-b`)** → „167 to add", Exit 2.
Ursache: nach Destroy B blieb `ris-b` selektiert.
Bewertung: **Kein Infra-Defekt**, aber exakt der Bedienfehler, den die Manifeste als
Fallstricke #1/#Ownership vorsehen.

**Regel (jetzt verbindlich dokumentiert):** Vor **jedem** Terraform-Lauf
`terraform workspace show` ausführen und das Ergebnis gegen das erwartete Ziel halten.
In `scripts/parallel_tests.sh` ist das Prüfen des Ziels eingebaut (nur Read-Operationen).
