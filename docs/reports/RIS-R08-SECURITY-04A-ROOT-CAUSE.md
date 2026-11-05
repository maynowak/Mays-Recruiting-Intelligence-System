# RIS-R08-SECURITY-04A — Root Cause and Remediation Matrix

| ID | Ursache | Fix | Negativtest | Regression | Status | Commit |
|---|---|---|---|---|---|---|
| FIX-01 | Fehlende Work-Item-Zeile wird bedingungslos neu registriert; keine dauerhafte Subject-Fence im Produktionsaufruf | Optionaler Admission-Fence-Seam vorhanden, aber nicht produktiv verdrahtet; keine unbewiesene Tombstone-Architektur ergänzt | Fence vor Registrierung, Missing-row-Szenario bleibt als Gate offen | Worker suite PASS; Produktionspfad nicht geschlossen | **BLOCKED** | — |
| FIX-02 | Kein letzter Status-/Freeze-Check vor Agent-Ausführung | Letzter Work-Status-Check plus injizierbarer Erasure-Admission-Callback vor Execution | Freeze-Callback unterdrückt Execution | PASS lokal | **LOCAL PASS / LIVE WIRING OPEN** | `096d69c` |
| FIX-03 | Retry-Update war unconditional | Conditional `FAILED` + erwarteter Attempt; Claim-Loser wird unterdrückt | Retry-/Claim-Fake und Regression | PASS lokal | **PASS LOCAL** | `096d69c` |
| FIX-04 | Permanente Fehler blieben `FAILED` und retrybar | Terminalstatus `DEAD_LETTER`; Terminal-Duplikate werden unterdrückt | Permanent `CONFLICT` redelivery | PASS | **PASS LOCAL** | `096d69c`, `05f116f` |
| FIX-05 | Resume filterte `IN_PROGRESS` aus | Application-Erasure listet mit `include_deleting=True` | Resume contract test | PASS | **PASS LOCAL** | `b4fa79f`, `6fd985c` |
| FIX-06 | Reduced scope war öffentlich callable | Nicht-serialisierbares Synthetic-Capability-Token erforderlich | Reduced scope ohne Token | PASS | **PASS LOCAL** | `b4fa79f` |
| FIX-07 | Early API errors umgingen Metrics-Response-Header | Zentraler personal API response finalizer | 401/503/exception helper tests; Health unchanged | PASS lokal | **PASS LOCAL / Orders reader separate** | `efd4b3f` |

Gate B bleibt NO-GO. FIX-01 und die produktive Verdrahtung von FIX-02 sind
bewusst nicht als abgeschlossen behauptet.
