# RIS-DEV2-CANARY-FORENSICS-19B — Trace- und Artefakt-Reconciliation

**Datum:** 2026-11-26

**Ausführung:** Read-only; keine Queue-Reads, Lambda-Aufrufe oder AWS-Mutationen

**Baseline:** Account `262370457690`, `eu-central-1`, Workspace `ris-dev2`, State Serial `75`, Lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`

**Git:** Branch `feature/ris-analysis-integration-07`, HEAD/Remote bei Start `d7dfe455a5715e47d8acf34458c362c79af05d76`

## Ergebnis

**Root cause: `ROOT_CAUSE_VERIFIED` — `CLAIM_WITHOUT_EXECUTION`.**

Der Work Processor hat die Canary-Nachricht bis zur Agent-Auswahl verarbeitet und `analysis-agent` erfolgreich ausgewählt. Danach wurde das WorkItem auf `RUNNING` geclaimt, aber aufgrund eines Control-Flow-Fehlers unmittelbar als verlorener Retry-Claim behandelt. Der Worker kehrte deshalb mit `RUNNING` zurück, ohne die Agent-Ausführung zu starten. Die Analysis-Lambda wurde im relevanten Zeitfenster nicht aufgerufen. Das erklärt sowohl den Zustand als auch die fehlenden Analysis-/Result-Ereignisse.

Die Folgebeobachtung `RUNNING` ist zusätzlich durch die Idempotenzlogik festgehalten: Weitere Zustellungen eines bereits `RUNNING` WorkItems werden als Duplikat unterdrückt. Damit wird der ursprüngliche Fehler nicht automatisch behoben. Der einmalige Redrive bleibt verbraucht; es wurde keine Recovery versucht.

## 1. Baseline und Artefaktbeweis

- Branch, HEAD, Remote und sauberer Worktree wurden geprüft; AWS Account/Region und Terraform Workspace/State stimmten mit der erwarteten Baseline überein.
- Read-only `GetFunction` lieferte die Agent-, Dispatch-Ingress- und Analysis-Code-Pakete. Die heruntergeladenen ZIPs wurden ausschließlich lokal in `%LOCALAPPDATA%\Temp\opencode\` abgelegt.
- Agent ZIP: SHA-256 `8ec50a61408d28efb2b85ff6c83b05dd0ee6075b9b46081ef16d649793cc6383`; Base64 entspricht Live `CodeSha256=jsUKYUCNKO+yuF/2yDsF3Q7mB1ubRgge8W1kl5PMY4M=`. Das lokale offizielle `terraform/lambda.zip` ist byteidentisch mit dem heruntergeladenen Live-ZIP (gleiche ZIP-Einträge, keine abweichenden Dateien).
- In der Agent-Konfiguration: `$LATEST`, `LastModified=2026-11-26T11:04:51Z`, `State=Active`, `LastUpdateStatus=Successful`. Analysis `CodeSha256=J2tORCAnIWfdMsWQ1tur7UAIckpwkeTYZQTVRE/iaxA=`.
- Somit ist der relevante Pipeline-Code gegen das tatsächlich deployte Artefakt abgeglichen; die Ursache lässt sich nicht mit einer lokalen/deployten Source-Abweichung erklären.

## 2. Vollständige Invocation-Timeline (UTC)

Nur Events im Canary-Zeitfenster `12:21:00Z–12:22:00Z` wurden ausgewertet.

| UTC | Komponente / RequestId | Beobachtung |
|---|---|---|
| 12:21:22.387–12:21:26.736 | Dispatch ingress, `881441d6-9f4a-593d-baea-2254b93a3004` | `START`, `END`, `REPORT`; 4,348 ms; kein Lambda-Fehler. Keine fachlichen Logzeilen in diesem Handler. |
| 12:21:26.801 | Agent Init | Runtime Python 3.14 initialisiert. |
| 12:21:27.011 | Agent, `131b883a-898e-517f-9771-ebb8aff5ef3f` | `START`; `Processing request`; Verarbeitung des exakten WorkIds `work-2c26e835ee8fee7c`. |
| 12:21:32.445–12:21:35.302 | Derselbe Agent-Request | Registry initialisiert; `analysis-agent` registriert. Envelope erstellt; ein Kandidat gefunden, 1 eligible / 0 rejected; `analysis-agent` mit Grund `Specific agent requested` ausgewählt. |
| 12:21:36.104731 | WorkItem DynamoDB | `updatedAt`; final `RUNNING`, `attempt_no=1`; `execution_id`, `attempt_id`, `result_reference`, `error` fehlen. |
| 12:21:36.246 | Agent, derselbe Request | `Work item ... processed: RUNNING`. |
| 12:21:36.305 | Agent, derselbe Request | `END` und `REPORT`; 9,293.35 ms, 99 MB Maximum von 128 MB, kein Lambda-Fehler. |
| 12:21:00–12:22:00 | Analysis / Result Consumer | Keine CloudWatch-Events. CloudWatch `AWS/Lambda Invocations` lieferte für `ris-dev2-dev-analysis` keinen Datenpunkt in der Minute; Agent und Dispatch-Ingress jeweils genau eine Invocation. |

Der Zustand wurde erneut konsistent gelesen: WorkItem weiter `RUNNING`, `attempt_no=1`, `attempt="0"` (Legacy), kein Ergebnis/Fehler/Execution-Feld; Order `PENDING`. CloudTrail-Trails sind aktiv, aber ihre Event Selector haben `DataResources=[]`; historische DynamoDB Data Events/Item-Level-Schreibnachweise sind darüber nicht verfügbar. Es gab daher keinen CloudTrail-Beleg des einzelnen Conditional Writes.

## 3. Verifizierter Codepfad des Fehlers

Das Live-ZIP enthält denselben Code wie die geprüfte RIS-Quelle. In `agents/runtime/pipeline.py` geschieht:

1. `process_record()` löst Registry/Eligibility auf und wählt `analysis-agent` — direkt durch die korrelierten Logs belegt.
2. `_register_processing(... require_fence=True)` versucht einen conditional `Put` des WorkItems. Das Item war durch Dispatch-Ingress bereits vorhanden; die Bedingung `attribute_not_exists(workId)` schlägt fehl. Der Code liest den vorhandenen Eintrag und liefert bei vorhandenem Eintrag `(existing, True)` zurück.
3. Für den vorhandenen Status `QUEUED` ruft der Duplicate-Zweig `_claim_queued_work()` auf. Der Claim setzt per Bedingung `status=QUEUED` den Status `RUNNING`, `attempt_no=1` und `updatedAt`; er setzt kein `execution_id`. Das entspricht den Persistenzfeldern und dem beobachteten Zeitpunkt.
4. **Fehler:** Nach erfolgreichem Claim fällt der Kontrollfluss in den anschließend stehenden `_start_retry_attempt(table, item)`-Aufruf. Dieser Retry-Claim ist ausschließlich für `status=FAILED` implementiert (`ConditionExpression` in `_start_retry_attempt`). Das frisch geclaimte Item ist `RUNNING`, daher schlägt diese Bedingung erwartungsgemäß fehl.
5. `_RetryClaimLost` wird abgefangen und als `{"status":"RUNNING", "duplicate":true, "suppressed":true}` zurückgegeben. Der Aufruf kehrt damit vor der nachfolgenden Entitlement-/Fence-Ausführung und vor `ExecutionEngine.execute_from_decision(...)` zurück.
6. `lambda/handler.py` loggt den Rückgabestatus als `Work item ... processed: RUNNING`; genau dieses Log steht im selben RequestId. Da die Engine nicht erreicht wird, erfolgt kein synchroner Aufruf von `ris-dev2-dev-analysis`, kein Analysis-Ergebnis und kein Result-Transport.

Das ist kein bloß möglicher stale-WorkItem-Race: Die Control-Flow-Reihenfolge, das definierte FAILED-only Retry-Kriterium, das vollständige Runtime-Log, das auf `RUNNING` endende Invocation-REPORT und der finale WorkItem-Datensatz stimmen zusammen. Damit ist `CLAIM_WITHOUT_EXECUTION` für diese Canary **VERIFIED**.

## 4. Ursachenklassifikation

| Kategorie | Status | Beleg |
|---|---|---|
| `CLAIM_WITHOUT_EXECUTION` | **VERIFIED — Root Cause** | Control-Flow-Fehler nach QUEUED-Claim; deployed ZIP exakt identisch; korrelierter Agent-Request endet mit RUNNING; Analysis Invocation fehlt; WorkItem-Felder/Zeiten passen. |
| `AGENT_RESOLUTION_FAILURE` | Ausgeschlossen für diesen Lauf | `analysis-agent` registriert, ein Kandidat eligible, explizit ausgewählt. |
| `ANALYSIS_EXECUTION_FAILURE` | Nicht Ursache dieses Laufs | Execution Engine wird vor dem Aufruf verlassen; kein Analysis-Aufruf/Log/Metrik-Datenpunkt. |
| `RUNTIME_TIMEOUT` | Ausgeschlossen für diesen Worker-Aufruf | Worker endete nach 9,293 ms mit REPORT ohne Lambda-Fehler; Timeout 60 s. |
| `CONTEXT_RESOLUTION_FAILURE` | Nicht ursächlich für den beobachteten Abbruch | Die Verarbeitung kommt bis zur Kandidatenauswahl; keine Context-Fehlermeldung. Ein fachlicher Context-Load fand danach nicht statt. |
| `RESULT_SERIALIZATION_FAILURE`, `RESULT_SIGNING_FAILURE`, `RESULT_PUBLICATION_FAILURE` | Nicht erreicht | Kein Agent-Result, daher kein Result-Encoding, HMAC oder SQS-Publish. |
| `RESULT_CONSUMER_FAILURE` | Nicht erreicht | Keine Result-Nachricht; Consumer ohne Invocation/Log im Canary-Fenster. |
| `STATUS_TRANSITION_FAILURE` | Nicht Root Cause | Der QUEUED→RUNNING-Claim gelingt; danach fehlt die Execution/Terminal-Transition durch den Control-Flow-Bug. |
| `IDEMPOTENCY_OR_LEASE_BLOCKER` | **VERIFIED — Folgeeffekt** | Spätere Zustellungen im Status RUNNING werden als duplicate/suppressed behandelt; kein stale-RUNNING-Resume. Verstetigt den Stall, löst den ersten Fehler aber nicht aus. |
| `CROSS_REPOSITORY_CONTRACT_MISMATCH` | Nicht ursächlich | Der Fehler tritt innerhalb des RIS Workers vor Result-Transport und Mays-Orders Consumer auf. |

## 5. Nächste Orchestrierung — keine automatische Fortsetzung

Die Ursache ist diagnostiziert, aber der Auftrag war read-only. Deshalb **kein Fix, kein Retry, kein Redrive, keine Statuskorrektur, kein Apply und kein Upgrade**.

Empfohlene getrennte Folgeaufträge:

1. **RIS-Lokal-Fix + Regression (ohne AWS):** Korrigierten Kontrollfluss entwickeln, so dass ein erfolgreich geclaimtes `QUEUED` Item direkt in den gemeinsamen Ausführungspfad eintritt und nur bereits `FAILED` Items den Retry-Claim verwenden. Tests für Conditional Put/Claim, parallele Duplikate, FAILED-Retry und Execution-Nachweis; außerdem Lifecycle-Tests für verwaistes RUNNING. Keine Änderung am alten Canary-Datensatz.
2. **Unabhängige Review und Release-Gate:** Paket-/Source-Diff, Regression, Idempotenz-/Fencing-Review, Result-Contract-Tests. Erst danach ein eigener, explizit freigegebener Deployment-Auftrag mit neu verifiziertem Konto/State/Plan und separatem AWS-Mutationsmodus.
3. **Recovery-Entscheidung separat:** Nach deployed Fix zunächst Design/Review einer eng begrenzten sicheren Recovery für das bestehende Item; kein pauschaler Redrive. Alte Work-DLQ und Canary-Order bleiben unangetastet, bis ein eigener Auftrag und Freigabe genau diese Objekte benennen.
4. **Mays-Orders Upgrade unabhängig weiterführen:** RC4 ist nicht Ursache und kein Fix für diesen RIS Control-Flow-Bug. Pin-/Manifest-Provenienz sowie dokumentierte Create-/HMAC-Gates bleiben separate Upgrade-Gates.

Dieser Folgeauftrag hat keine Commit-/Push-Freigabe erteilt: Bericht und Auditlog-Ergänzung liegen lokal; nicht committed und nicht gepusht.

## 6. Schutz- und Änderungsnachweis

- AWS-Mutationen: **0**. Es wurden nur Baseline-/Konfigurations-/Log-/Metrik-/Code-Download-/DynamoDB-Get-Leseoperationen verwendet.
- `ReceiveMessage`, Lambda `Invoke`, Queue-Send/Delete, DDB Update/Delete, Terraform Apply/State-Write: **0**.
- Source-Code-Änderungen: **0**. Nur Bericht/Auditlog lokal ergänzt.
- Entitlement nicht verlängert; MODE nicht geändert. Keine Secrets-Werte abgerufen.
- Old Order, WorkItem, DLQs, Queue-Nachrichten, externe Identity, Secrets, Terraform State und andere Environments unverändert.
