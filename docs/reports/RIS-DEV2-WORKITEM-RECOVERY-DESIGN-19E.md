# RIS-DEV2-WORKITEM-RECOVERY-DESIGN-19E

**Datum:** 2026-11-26

**Ausführung:** lokales Design-/Review, Source-/Artifact-Lesen und lokale Tests; keine Live-Verifikation

**RIS-Baseline:** `feature/ris-analysis-integration-07`, Start-HEAD/Remote `4e19726bf733e6d4f2f75fae0e083c8e0bd906b5`

**Historische Canary:** Order `ord_a566f415ef9d77720cd97cd4`, WorkItem `work-2c26e835ee8fee7c`, Correlation `corr-canary-07-02`

## Entscheidung in Kürze

- **`RECOVERY_DESIGN=READY_FOR_REVIEW`** — Vertragslücken und kontrollierbare Entscheidungspunkte sind dokumentiert; es liegt ausdrücklich kein ausführbarer Recovery-Vertrag und keine Ausführungsfreigabe vor.
- **`RECOVERY_PATH=ALTERNATIVE_CANARY`** für den Upgrade-Funktionsnachweis. **`NATIVE` ist nicht vorhanden; historische Recovery ist derzeit `UNAVAILABLE`.** Eine alternative, isolierte funktionale Baseline kann das Upgrade-Gate ersetzen, wenn sie separat autorisiert, entitlement-/context-gültig, reproduzierbar und kompatibel mit dem Upgrade-Ziel ist.
- **`HISTORICAL_RECOVERY_REQUIRED=NO`** als technische Voraussetzung des Mays-Orders-Upgrades. Historische Recovery ist ein eigenes Incident-Ziel, nicht ein notwendiger Bestandteil des Worker-Fixes oder eines kompatiblen Modul-Upgrades. Ein ausdrückliches Release-/Risk-Gate könnte dennoch einen historischen Abschluss verlangen; das wäre eine Governance-Entscheidung, kein technischer Contract-Zwang.
- **`WORKER_DEPLOYMENT_INDEPENDENT=CONDITIONAL`** — der RIS Worker-Fix kann unabhängig vom Mays-Orders-Modul ausgerollt werden, sofern ein separat genehmigter Plan exakt Agent-Worker + Dispatch-Ingress und keine unbeabsichtigten Ressourcenänderungen zeigt. Dieser Designauftrag erstellt keinen Plan.
- **`XREPO_CONTRACT_CHANGE_REQUIRED=NO`** für den begrenzten RIS-seitigen Recovery-Entwurf. Ein neuer Result-/Order-Lifecycle-Vertrag oder eine Änderung an Mays-Orders wäre nur erforderlich, wenn die derzeitigen Work-/Result-Korrelationen nicht genügen oder der Consumer atomare Attempt-/Recovery-Koordination übernehmen soll. Das wird nicht empfohlen.
- **Mays-Orders-Upgrade readiness: BLOCKED / CONDITIONAL** auf die separat offenen RC4-Create-Validator-/Transport-HMAC-/Pin-Provenienz- und Upgrade-QA-Gates. Die Incident-Recovery ist nicht die Blockade.
- **Empfehlung:** zuerst 19F (reproduzierbare vollständige QA), danach 19G (read-only Deployment-Plan für den RIS Worker-Kandidaten). Keine automatische Fortsetzung.

## 1. Evidenzabgleich (Step A)

| Thema | Befund in Reports / lokalem Source | Abgleich |
|---|---|---|
| Root Cause | 19B gleicht deployed ZIP und lokalen Source ab; korrelierter Agent-Trace zeigt erfolgreichen Agent-Resolve, `QUEUED → RUNNING`, danach fälschlichen FAILED-only Retry-Claim und Rückkehr vor Engine-Aufruf. `analysis-agent` wurde nicht ausgeführt. | `VERIFIED / CLAIM_WITHOUT_EXECUTION`; kein Widerspruch in 19C/19D. 19A war die frühere Zwischenklassifikation `INSUFFICIENT_EVIDENCE`, durch 19B mit Artefakt-/Trace-Nachweis superseded. |
| Worker-Fix | `agents/runtime/pipeline.py`: nach erfolgreichem QUEUED-Claim geht der Lauf direkt weiter; `_start_retry_attempt` liegt ausschließlich im FAILED-Zweig. | `c6e996a` entspricht dem minimalen Fix; keine pauschale RUNNING-Wiederaufnahme. |
| Duplicate-Schutz | Bereits RUNNING wird ohne Write als duplicate/suppressed zurückgegeben; verlorener QUEUED-/FAILED-CAS führt nicht zur Ausführung. Result terminal writes prüfen RUNNING + Attempt. | Unverändert durch Fix; das ist Schutz vor Doppelausführung, aber auch der Grund, warum stale RUNNING nicht von selbst heilt. |
| Tests | 19D: Worker 25 pass; breiter gefilterter Lauf 3.077 pass, 169 skipped, 446 subtests; vollständige Collection damals wegen fehlender `moto`/`requests` nicht möglich. | 19E hat Worker **25/25** erneut ausgeführt. Cross-repo RIS/Mays-Orders-Bridge mit lokalem Mays-Orders-Source-Fixture **22/22** erneut ausgeführt. Das behebt die Umgebungslücken nicht. |
| Lokaler synthetischer Roundtrip | 19D berichtet lokale Order → Dispatch → RIS Worker → Result Consumer Kette, mit Testdoubles; kein AWS. | 19E wiederholte die verfügbaren Bridge-/Consumer-/Contract-Tests; weiterhin kein Live-Nachweis. |
| Deployment-Scope | `terraform/main.tf` und Module verwenden das gemeinsame `terraform/lambda.zip` bei Agent-Worker und Dispatch-Ingress; Analysis hat separates ZIP/Runtime. | Der Worker-Fix benötigt nach bisheriger Wiring-Evidenz kein neues Analysis-Bundle. Shared-bundle Hash kann den Dispatch-Ingress ebenfalls aktualisieren, obwohl dessen Handler den Worker-Pipeline-Fix nicht ausführt. |
| Historische WorkItem-Wirkung | RUNNING-Items werden unterdrückt; Recovery nur aus FAILED ist implementiert. | Fix 19C allein stellt das historische Item nicht wieder her. Letzter Live-Status bleibt ausschließlich der historische Snapshot aus 19A/19B/18; keine Live-Revalidierung in 19E. |

Keine inhaltliche Abweichung gefunden. Ein Scope-Hinweis: der neue Bundle-Pin ist ein lokaler Kandidat, kein Deployment-Beleg. Die Entitlement-Grenze `2026-11-26T17:40:28Z` ist historisch dokumentiert; ihre heutige Live-Gültigkeit wurde nicht geprüft. Sie darf nicht als fortbestehende Autorisierung angenommen werden.

## 2. Ownership, Lifecycle und Conditional Contracts (Step B)

### Ownership-Matrix

| Objekt / Entscheidung | Owner | Relevante lokale Verträge |
|---|---|---|
| Generische Order, Owner, fachlicher Orderstatus, Result Consumer und Ergebnisabruf | Mays-Orders | lokale `order_service.py`, `state_machine.py`, `result_handler.py`, `result_envelope.py` |
| Agent Order Dispatch-Bindung (`expectedWorkId`, Dispatch-PENDING/SENT) | Mays-Orders | `bind_agent_order_work`, `dispatch_envelope`, `mark_dispatch_sent`; CAS verhindert Bindungswechsel bzw. widersprüchliche Send-Marker |
| Transport V1 / Envelope / Signaturberechnung auf RIS-Seite | RIS Transport | `agents/transport/order_transport.py`, `order_result_sender.py` |
| Kanonisches WorkItem, Work queue, Claim, Attempt, Retry, Resultpersistenz und DLQ | RIS Runtime/Worker | `work_item.py`, `work_queue.py`, `pipeline.py`, shared handler |
| Domain-Ausführung / Remote Analysis | RIS Agent/Analysis Runtime | Agent `process_work`, `remote_agent.py`, separate `analysis_runner.py` |
| Entitlement / Subject / Tenant / Profile-Zulassung | RIS Security/Authorization | Worker entitlement recheck, verified `ContextRef`, Subject Fence |
| Generated Mays-Orders Terraform module | RIS Builder erzeugt; Mays-Orders liefert Quellvertrag | patch-free `db4f9e7`-Contract gemäß RIS `AGENTS.md`: Outputs plus `additional_environment`; generierte Dateien werden nicht manuell geändert |

### Lifecycle-/Transition-Matrix

| Phase / Zustand | Bestehender erlaubter Mechanismus | Owner / Bedingung | Recovery-Aussage |
|---|---|---|---|
| Order `PENDING` → Bindung/Dispatch | Order bindet genau eine `expectedWorkId`; Dispatch-Marker ist separat `PENDING`/`SENT`; erneute Bindung gibt vorhandene ID zurück. | Mays-Orders; bedingte `attribute_not_exists(expectedWorkId)` und Bindung an gespeicherte Order. | Keine neue Order-/Work-Bindung für das historische Item aus Recovery-Code ableiten; bestehende Bindung muss erhalten bleiben. |
| RIS WorkItem `QUEUED` → `RUNNING` initial | `_claim_queued_work` conditional auf `status=QUEUED`, setzt `attempt_no=1`. Ingress erzeugt QUEUED vor Enqueue. | RIS Worker. | Genau diesen Pfad deckt 19C; er beansprucht nicht bestehende RUNNING-Items. |
| RIS WorkItem `FAILED` → `RUNNING` retry | `_start_retry_attempt`: CAS `status=FAILED AND attempt_no=:expectedAttempt`, erhöht Attempt, setzt neue `execution_id`/`attempt_id`, entfernt error. | RIS Worker / vorhandene Retry-Semantik. | Ist keine RUNNING-Recovery und darf nicht durch blindes FAILED-Schreiben simuliert werden. |
| RIS WorkItem `RUNNING` | Keine Lease-/Owner-Übernahme; weitere Zustellung wird duplicate/suppressed. | RIS Worker; Terminalwrite anschließend bedingt auf RUNNING + Attempt. | Keine native Stale-Erkennung, Zeitgrenze oder sichere Resume-API gefunden. |
| RIS WorkItem `RUNNING` → `COMPLETED` | Ergebnispersistenz conditional auf RUNNING + Attempt; speichert Result und stabile Referenz. Danach ORDER_RESULT senden. | RIS Worker / Result Transport. | Crashfenster zwischen Agent-Side-Effect, Persistenz und Send bleibt relevant; at-least-once, kein Exactly-once über Systeme hinweg. |
| RIS WorkItem `RUNNING` → `FAILED`/`DEAD_LETTER` | Fehlerpersistenz conditional auf RUNNING + Attempt; permanente Fehler bzw. Retry-/Queue-Regeln bleiben getrennt. | RIS Worker. | Kein dokumentierter Operator-Übergang von RUNNING nach FAILED. |
| Mays-Orders Result anwenden | Verifiziert HMAC und Envelope; Order-/Correlation-/Work-Bindung prüfen. `processing`-Write conditional auf fehlendes Feld; gleicher terminaler Idempotency-Key wird wiedererkannt, Konflikt wird abgewiesen. | Mays-Orders; Work-/Attempt-/Idempotency-Validierung gegen gespeicherte Order. Fachlicher `status` wird durch Processing-Result nicht neu interpretiert. | Schutz gegen wiederholten identischen Commit existiert; keine Koordination mit RIS-Laufzeit-Lease oder Re-Execution. |
| Mays-Orders Order Lifecycle | Die lokale State Machine kennt `PENDING → CONFIRMED/CANCELLED`, `CONFIRMED → PROCESSING/CANCELLED`, dann SHIPPED/DELIVERED. Result wird im separaten `processing`-Feld abgelegt; Cancel ist terminal. | Ausschließlich Mays-Orders. | Recovery darf nicht eigenmächtig `PENDING` in `PROCESSING`/`CONFIRMED` umdeuten oder `CANCELLED` wiederbeleben. |

### Identität, Attempt und Cross-System-Verträge

- **Work ownership:** WorkItem liegt im RIS-Work-Items-Store. Mays-Orders besitzt die autoritative Order mit gespeicherter `expectedWorkId`, Owner und Agent-Order-Fingerprint. Ergebnis muss zu gespeicherter Order-ID, Correlation und Work-ID passen.
- **Conditional writes:** RIS-Initialclaim ist QUEUED-CAS; Retry ist FAILED+expectedAttempt-CAS; Terminalwrite ist RUNNING+attempt-CAS. Mays-Orders Dispatch-Bindung ist einmalig und Resultpersistenz nur bei fehlendem `processing`. Diese Guards erhalten, nicht lockern.
- **Claim ownership / Lease:** Das RIS-WorkItem speichert keinen verifizierten Worker-Owner-/Lease-Token mit expiry/fencing; die Initial-QUEUED-Claim-Transition setzt auch nicht die vom FAILED-Retry erzeugte neue `execution_id`/`attempt_id`. Ein `updatedAt` ist kein Lease. **`CONTRACT_GAP: CLAIM_OWNER_AND_FENCED_LEASE`.**
- **Attempt/version:** RIS bindet Terminal-Updates an `attempt_no`; Retry erhöht Attempt atomar. Mays-Orders speichert Result-Attempt und lehnt ältere Attempt-Ergebnisse ab; es besteht keine gemeinsame monotone Version über beide Systeme. **`CONTRACT_GAP: CROSS_SYSTEM_RECOVERY_GENERATION`.**
- **ContextRef:** Dispatch enthält Referenz, RIS löst trusted Context serverseitig auf und WorkItem hält `apiProfileId`, Tenant, Partner-App und Issuer. Das historische ContextRef belegt nicht, dass Profil/Owner/Grant heute noch aktiv oder zulässig ist. **`CONTRACT_GAP: HISTORICAL_CONTEXT_REAUTHORIZATION_AND_EXPIRY_POLICY`** für Recovery; niemals Claims aus Dispatch als Autorisierung nutzen.
- **Idempotency:** Dispatch hat order/work-spezifischen Dispatch-Key; WorkItem hat Payload-/Work-Idempotency; `ORDER_RESULT` hat deterministische Message-ID und order/work/type Idempotency. Das schützt Persistenz/Consumer-Dedupe, beweist aber nicht, dass ein erneuter externer Analysis-Aufruf fachlich folgenlos ist. **`CONTRACT_GAP: ANALYSIS_EFFECT_IDEMPOTENCY_BOUND_TO_RECOVERY_ATTEMPT`**.
- **Entitlement:** Worker prüft den entschiedenen Agenten zur Ausführungszeit frisch; fehlender Resolver ist nur Test/Harness. Recovery darf diesen Recheck nicht überspringen. Die historische Grenze ist kein dauerhafter Grant. Neuer Entitlement-/Consent-Nachweis muss separat autorisiert sein; kein Write in 19E.
- **HMAC / Result:** RIS signiert `HMAC-SHA256(secret, messageId + "\n" + serialized body)` als SQS-Attribut. Mays-Orders verifiziert fail-closed; invalid/terminal contract rejections werden konsumiert, technische Fehler selektiv retried. Secret-Rotation ist `current`/`previous`-fähig im Consumer. Message-Type, schema, correlation, workId, attempt und Signatur müssen unverändert vertragskonform sein.
- **ContextRef/Idempotency weder Recovery-Token noch Berechtigungsnachweis:** Diese Werte binden den ursprünglichen Vertrag; sie gewähren keine Ausführungsfreigabe und legitimieren keine neue Verarbeitung nach Entitlement-Ende.

### Explizite CONTRACT_GAPs

1. `CLAIM_OWNER_AND_FENCED_LEASE`: atomarer Owner/lease/fencing-token, Renewal, expiry and stale takeover semantics.
2. `STALE_RUNNING_RECOVERY_TRANSITION`: auditierbare CAS-Transition für exakt identifiziertes RUNNING-Item, ohne aktive Worker zu überholen.
3. `ANALYSIS_EFFECT_IDEMPOTENCY_BOUND_TO_RECOVERY_ATTEMPT`: Nachweis, ob der Remote-Analysis-Aufruf vor dem Crash stattfand und wie eine Wiederholung denselben fachlichen Effekt verhindert.
4. `CROSS_SYSTEM_RECOVERY_GENERATION`: ein Result mit alter/neuer Generation darf weder einen neueren Attempt überschreiben noch Mays-Orders in einen unzulässigen Zustand bringen.
5. `HISTORICAL_CONTEXT_REAUTHORIZATION_AND_EXPIRY_POLICY`: erneute autoritative Validierung von owner/tenant/profile/context/consent/entitlement und Umgang mit abgelaufenen historischen Refs.
6. `RECOVERY_AUDIT_AND_OPERATOR_AUTHORIZATION`: unveränderliche, least-privilege autorisierte Freigabe mit Begründung, Objekt-Allowlist, before/after image hashes/versions und Ergebnis.
7. `ABORT_AND_PARTIAL_FAILURE_PROTOCOL`: Verhalten bei Timeout/unklarem Analysis-Ausgang, Prozessabbruch zwischen Side-Effect und Persistenz sowie Result-Send nach Completed-Persistenz.

Diese Lücken sind Designbefunde, keine Aufforderung, sie im Rahmen 19E zu implementieren.

## 3. Recovery Safety Invariants (Step D)

| Invariant | notwendiger Nachweis / derzeitiger Status |
|---|---|
| Keine konkurrierende Ausführung desselben WorkItems | Nur mit atomarem Fencing/Owner-CAS und Nachweis, dass alter Worker nicht mehr schreiben/Seiteneffekte auslösen kann. **Gap.** RUNNING-Duplicate-Guard schützt derzeit gegen erneute Ausführung, aber nicht gegen kontrolliertes Takeover. |
| Keine unkontrollierte Wiederholung von Analysis | Belege, dass Analysis nicht aufgerufen wurde, oder idempotente/fenced Wiederholung mit Attempt-Bindung. 19B beweist für den historischen ursprünglichen Invocation-Pfad „nicht aufgerufen“; nachfolgende externe Aktivitäten wurden nicht neu live geprüft. Fresh current state wäre vor jedem Recovery-Auftrag nötig. |
| Keine doppelte Ergebnisübernahme | Stabile ORDER_RESULT-ID/Idempotency, HMAC, Work-/Correlation-Binding; Mays Consumer akzeptiert identisches terminales Idempotency-Ergebnis idempotent und verwirft Konflikte. Kein Exactly-once für den gesamten verteilten Ablauf behaupten. |
| Keine unzulässige Order-Statusänderung | Result darf nur `processing` füllen. Generische State Machine bleibt bei Mays-Orders; PENDING wird nicht durch RIS auf PROCESSING o.ä. gesetzt. |
| Kein Tenant-/Owner-Wechsel | Erneut trusted Context auflösen und mit gespeicherter Order-/WorkItem-Identität vergleichen; kein Envelope-Claim als Quelle. |
| Entitlement nicht umgehen | Execution-Time-Entitlement-/Consent-Check frisch durchführen; historische Ablaufgrenze nicht verlängern oder interpretieren. |
| Kein pauschales RUNNING-Reset | Exakte WorkId/OrderId allowlist, konsistente Versionen, status/attempt/identity guards; keine Batch-/wildcard-Operation. |
| Audit-Evidenz bleibt erhalten | Append-only Recovery-Ereignis und unveränderte Originalfelder/Reports; keine Überschreibung oder Bereinigung der historischen Trace-Evidenz. |
| Keine Mutation anderer WorkItems | Item-exakte Schlüssel und pre/post condition; zusätzlicher Guard gegen WorkId/OrderId-Mismatch. |
| Alte Canary/Work-DLQ unangetastet | 19E und Folge-Design/QA/Plan ändern weder Canary-State noch DLQ; Recovery/Redrive später nur in separat freigegebenem Schritt. |
| Späte Ergebnisse sicher behandeln | Generation/attempt/fencing prüfen; alte Ergebnisse dürfen neuere Recovery nicht überholen. Result Consumer kann terminale Konflikte abweisen, aber gemeinsame Recovery-Generation fehlt. |
| Timeout/Abbruch zwischen Seiteneffekt und Persistenz | Unknown outcome ist kein Beweis für „nicht ausgeführt“. Fail-closed halten, keine blinde Wiederholung. Idempotency-/reconciliation contract fehlt. |

Es gibt keine verifizierte Exactly-once-Garantie. Bestehende Garantiegrenze bleibt at-least-once plus bedingte WorkItem-Updates und deduplizierte terminale Result-Übernahme.

## 4. Optionen A–E und Decision Matrix (Steps C/G)

| Option | Technische Machbarkeit / Voraussetzungen | Fehlende Fähigkeiten und Risiken | Betroffene Komponenten / Aufwand | Freigaben / Tests | Upgrade-Auswirkung / Entscheidung |
|---|---|---|---|---|---|
| **A — Native Recovery** | Source und Reports zeigen keine dokumentierte Recovery-API, stale lease, owner takeover oder RUNNING resume. Retry ist FAILED-only. | Native path nicht vorhanden. Ein regulärer SQS redelivery bleibt bei RUNNING suppression hängen. | RIS runtime/worker; wäre ohne Änderung nicht machbar. | Kein Ausführungsweg zu testen; read-only source audit genügt für Design. | `UNAVAILABLE`; nicht verwenden, keine Mutation. |
| **B — Controlled administrative recovery** | Als zukünftiger, eng begrenzter RIS-runtime-Vertrag denkbar: exact object allowlist; consistent read; verified order/work/context/attempt; proof of no active worker; fresh entitlement; item-level CAS + fencing token/new generation; immutable audit record; existing normal worker path; existing result idempotency. | Heute fehlen owner lease/fencing, recovery generation, external Analysis effect idempotency, current context policy and abort protocol. Ein direct DynamoDB status write wäre gerade keine sichere Implementierung. 19B beweist die ursprüngliche fehlende Analysis-Aufrufspur, aber keine heutige Live-Zustands-/Entitlement-Validität. | RIS Runtime/worker + authorization/audit. Mays-Orders contract kann unverändert bleiben, wenn bestehende `workId`/attempt result checks ausreichen und keine Consumer-ownership-Erweiterung eingeführt wird. Minimaler künftiger Custom-Mechanismus; mittel/hoch (design + implementation + race/failure tests). | Neue Implementierungsfreigabe, Security/owner approval, execution authorization for exact order/work, separate recovery permission, fresh state evidence. Race, stale worker, concurrent takeover, timeout, late result, HMAC, consumer duplicate/conflict, tenant isolation, DLQ non-interference tests. | Für incident recovery nur falls historische Completion explizit gefordert ist. **Heute nicht ausführbar**; nicht prerequisite für upgrade. |
| **C — Generic stale-lease recovery** | Möglich als allgemeine runtime platform, aber erst nach lease/renewal/heartbeat/fencing and operation semantics design. | False-stale bei pausiertem/langem Worker, timeout/clock skew, process crash, external side-effect ambiguity, late results and noisy-neighbor/batch takeover; lease alone doesn't prove safe re-execution. Large semantics surface. | RIS runtime, all worker types, persistence/schema, observability, authorization, possibly DLQ/operator tooling; high effort. | Full concurrency/chaos/time injection and cross-agent regression, result race tests, operational metrics/alarms/runbook. | Nicht automatisch Teil von Mays-Orders-Upgrade empfehlen. Defer unless broader runtime reliability requirement exists. |
| **D — Isolate historical state; separately authorized new canary** | Keep old order/work/DLQ unchanged. A new synthetic isolated functional baseline can exercise corrected worker, Transport V1 and Mays consumer. Existing contract tests already show local mock path; deployed E2E would require new business objects and active valid permissions. | Not authorization to create an order. Need isolate tenant/order/profile/payload, ensure no shared workId/idempotency collision, establish current entitlements/context and cleanup/retention policy; resource/queue/secret/consumer/environment compatibility. Does not resolve the historic incident. | Primarily RIS worker/ingress, existing Mays-Orders dispatch/result contracts, approved synthetic identity/entitlement. No contract change implied. | Separate order creation + live E2E authorization; no reuse of old DLQ message; exact synthetic payload and owner; read-only evidence gates; no real applicant data. Current historical entitlement deadline cannot be reused. | **Preferred alternative functional baseline** for upgrade if accepted by release owner. No order is created in 19E. |
| **E — Keep upgrade blocked** | Always safe and technically available if no approved functional alternative or if RC4 gates remain unresolved. | Delays upgrade; does not cure old RUNNING incident. | No code mutation; governance decision only. | Require explicit blocker owner and exit criteria. | Fall back if D not authorized/available or required acceptance explicitly demands historic order completion. Current Mays-Orders RC4 gate is independently blocked. |

### Priorisierte Entscheidungen

1. Preserve historic order, WorkItem, original payload/context binding, DLQs, and evidence. Do not “repair” by writing status FAILED/QUEUED or re-sending the old message.
2. For the upgrade’s functional proof, prefer **D** (a separately authorized isolated synthetic canary) over implementing a recovery platform solely to clear this incident.
3. Keep **B** as a separately scoped incident-recovery design/implementation only if the business owner needs the historical order completed; it is not native today.
4. Do not build **C** under this Mays-Orders upgrade unless an independent platform-level reliability decision requires it.
5. Use **E** if fresh entitlement/context or an alternative canary cannot be authorized, or if the release owner makes historical completion an explicit non-waivable gate.

## 5. Cross-Repository contract impact (Step E)

| Contract | Local findings | Recovery impact |
|---|---|---|
| Order lifecycle/ownership | Mays-Orders owns order/owner/status; result consumer stores technical result under `processing`. RIS has no authority to change order status. | A RIS-only recovery may complete the same bound WorkItem, but must not alter Mays Order state machine or resurrect CANCELLED. |
| Dispatch | ORDER_DISPATCH V1 binds `orderId`, `correlationId`, `idempotencyKey`, `identity.contextRef`, and `execution.workId`; Mays binds `expectedWorkId` once. RIS maps verified server-side Context to WorkItem. | Do not mint/rebind a new workId for historical order; never treat original ContextRef as current authorization. |
| WorkItem ownership | RIS owns canonical WorkItem lifecycle; Mays stores correlation/expectedWorkId and does not own RIS retry. | Controlled recovery is primarily RIS-side. |
| Result envelope / attempt | RIS creates deterministic message ID and `orderId:workId:type` idempotency, includes execution attempt; Mays validates order/work, rejects stale attempts and conflicting terminal results. | Existing contract likely supports the same work’s result without MO change, subject to local tests; no result can be accepted for a different workId. |
| HMAC | RIS producer HMAC-SHA256 over `messageId + newline + body`; Mays verifier uses constant-time comparison and accepts configured rotation keys. | Keep exact transport V1; no recovery-specific signature bypass. RC4 `APP_MANAGED` privacy HMAC is not a replacement for this service-signature contract. |
| ContextRef / owner | RIS verifies ContextRef server-side and copies verified tenant/owner/profile binding; Mays result verifies stored order/correlation/work binding. | Reauthorization needs RIS-side security policy. No cross-repository mutation required unless product chooses a new shared recovery field/protocol. |
| Installer/generated module | Local RIS builder contract is patch-free for Mays source `db4f9e7`: module outputs result queue URL/ARN/secret ARN and accepts `additional_environment` for dispatch URL. | No module change required for a narrowly RIS-owned recovery; no Mays source was changed. Revalidate exact target pin/manifest before later upgrade. |
| Target upgrade version | Historical RC4 report names `v0.6.0-rc.1` / `5bc154e`; it records an `agentOrder` create-validator gap and a different APP_MANAGED HMAC contract. Later deployed/generated module provenance in 19A cites `db4f9e7`, while old clone pin metadata disagreed. | Upgrade target and provenance must be reconciled. RC4 is not a recovery mechanism and may require Mays-Orders contract work for its independent create/HMAC gaps. 19E does not alter pins or generated module. |

**Conclusion:** a bounded recovery mechanism can be RIS-only if it uses existing dispatch/work/result contracts and does not add new Order states or Result message types. A generic protocol involving a new shared recovery generation, changed order lifecycle, or Consumer-side coordination would require a separately reviewed cross-repository contract change; that is not currently justified.

## 6. Upgrade dependency decision (Step G)

### Is the historical Recovery required?

**No, not as a technical prerequisite.** A corrected worker artifact can be reviewed and deployed without completing the old order. Upgrade functional acceptance can instead rely on a separately authorized, isolated synthetic canary exercising the current supported contracts. The acceptance authority must explicitly approve this substitution and the evidence must prove the upgrade-relevant Mays-Orders contract, not merely a local mock test.

If the business goal is specifically to demonstrate that the *same historic order* produced a result, only a controlled recovery or an explicitly accepted alternative disposition can close that incident. No prior redrive permission carries forward.

### Independent worker deployment?

**Conditional yes.** RIS worker fix is in the common artifact; deployment candidate scope from 19D is Agent Worker + Dispatch Ingress. Analysis artifact is separate and has no code change required by the claim fix. Since ingress shares the ZIP, it may receive a code hash update even though its execution path is unchanged. A fresh 19G plan must prove exact in-place updates and no unexpected module/state changes. Deploying it is not authorization to mutate the Canary or execute a new order.

### What blocks the Mays-Orders upgrade now?

- RC4's `agentOrder` create validator incompatibility is recorded in `RIS-MO-RC4-BUILDER-UPGRADE-06.md`.
- RC4 `APP_MANAGED` privacy HMAC is not Transport V1's service-signature HMAC; preserve existing sender/consumer contract.
- Builder pin / generated module / deployed source provenance needs reconciliation (`19A` cites generated/deployed `db4f9e7`; old pin metadata differed; target RC4 is an older candidate).
- 19D broad test suite was not fully collectable and has known unrelated failures (see 19F).
- Any actual upgrade requires separate plan/apply approval, target version approval, and current identity/entitlement/consent gates. Existing reports are historical, not current live state.

These blockers are independent of whether the historical Canary is recovered. Mays-Orders is **not upgrade-ready for apply** based on this design review.

## 7. QA completion plan and proposed 19F (Step F)

### Reconciled 19D test constraints

- Repository-required dependencies are declared in RIS `requirements.txt`: `moto[s3,dynamodb,sqs]>=5.0.0` and `requests>=2.31.0`, plus pytest plugins. They were not installed by 19D.
- Unfiltered `python -m pytest tests/ -q` failed during collection: `mock_aws` was `None` because Moto was unavailable; `tests/test_http_e2e_integration.py` could not import `requests`.
- Broad 19D run excluded six files: `test_durable_deletion_ledger.py`, `test_http_e2e_integration.py`, `test_analysis_fresh_plan_16c1.py`, `test_composite_lifecycle.py`, `test_consent_special_categories.py`, `test_platform_openapi_contract.py`. Reported result was 3,077 passed / 169 skipped / 446 subtests. Do not describe it as a clean full-suite pass.
- 19D also documented unrelated failures when collection was unblocked: historical bundle hash pin in `test_analysis_fresh_plan_16c1`, unavailable `mayaws` profile, NameErrors in consent-category tests, and an undocumented API route assertion. Their exact current status is **not revalidated** in 19E.
- Re-run in this task: worker pipeline **25 passed**; cross-repository bridge/consumer/contract tests **22 passed** with `MO_ORDERS_SRC` set only for the local test process to the ignored local clone `lambda/src`. No live endpoints or credentials used.

### QA Completion — 19F assignment (not started)

**Name:** `RIS-DEV2-QA-COMPLETION-19F`
**Goal:** reproducibly collect and classify the full RIS test suite and provide deployment-candidate QA evidence, without changing test contracts, dependencies, runtime config, AWS, or Mays-Orders source.

1. Verify branch/HEAD and clean worktree; read AGENTS and existing reports. Confirm Python version and installed package versions without installation. Use an already provisioned, isolated test environment if available; otherwise stop and report the missing dependencies rather than altering requirements or downloading/installing packages without authorization.
2. With approved test environment, run `python -m pytest tests/ --collect-only -q`, record exact collected count and every collection error. Then run full `python -m pytest tests/ -q`; do not silently ignore modules. If unrelated known failures remain, classify exact failure and owner, preserve them, and provide both all-suite result and focused worker/transport/security regressions.
3. Run target suites: Worker lifecycle/claim; analysis adapter/runtime; dispatch ingress/work queue; Transport V1/result sender; Mays-Orders local bridge/consumer and owner/tenant security; packaging/artifact hash. Use local `MO_ORDERS_SRC` only as a process-scoped test variable. No live test mode.
4. Build agent and analysis bundles using existing builder, hash outputs, check bundle manifests and confirm Analysis bundle unchanged by worker fix. Do not upload artifacts.
5. Run static compile/import and local Terraform validation only if prerequisites are present (`terraform init -backend=false`, `validate`, `fmt -check -recursive`); no backend/state access, plan, apply, or environment-variable alteration.
6. Deliver immutable test command/output summary, exact pass/fail/skip/subtest/collection counts, versions, skip reasons, known failure ownership and final secret/worktree audit. Commit/push documentation only if the task explicitly retains that boundary.

**Required deployment QA after 19F:** 19G must independently validate candidate artifact hashes, worker+ingress wiring, current state/lineage by an approved read-only process, Terraform plan guard and exact action scope. Post-apply verification needs a separately approved 19H; this 19E task authorizes neither.

## 8. Updated orchestration (Step H)

| Step | Purpose / gate | Decision / ordering |
|---|---|---|
| **19F — QA Completion** | Full test collection, dependency/environment reconciliation, no test weakening. | **Next.** |
| **19G — Worker Deployment Plan** | Read-only plan for corrected shared bundle; expected Agent Worker + Dispatch Ingress only. | After 19F; independent of historical recovery and Mays upgrade. Stop on extra changes/replacements/drift. |
| **19H — Controlled Apply** | Exact separately approved apply of reviewed 19G plan. | Human authorization required; separate from this task. Follow with deployment verification; no canary execution implicit. |
| **20A — Recovery Implementation** | Build a minimal controlled B path only if business requires historic completion. | **Conditional / may be omitted** if alternative baseline accepted and incident can remain isolated. Must close CONTRACT_GAPs first. |
| **20B — Recovery QA** | Race, timeout, side-effect, entitlement, result-dedupe and audit regression. | Only if 20A exists. |
| **20C — Controlled Recovery or Alternative Canary** | Separately authorized historical operation or new synthetic functional baseline. | For upgrade evidence, prefer isolated alternative Canary D. New Order and recovery both require fresh explicit authorizations; 20C is not pre-approved. |
| **21 — Cross-Repository Contract Audit** | Reconcile exact target Mays source/manifest/pin, create, dispatch, HMAC/result, installer outputs. | Required before changing/upgrading Mays module; can run before or parallel to independent 19G only if read-only and independently assigned. No source change implied. |
| **22 — Local Upgrade Integration** | Build generated module against approved exact target; local contract integration only. | After 21; resolve RC4 validator/HMAC/provenance gaps first, else stop. No Mays repository mutation. |
| **23 — Upgrade QA** | Full local integration/regression, builder and generated output comparisons. | After 22 and 19F. |
| **24 — Upgrade Plan** | Read-only Terraform plan; verify workspace/state/lineage, artifact hashes, policy guard, exact add/change/destroy/replacement scope. | After 23. |
| **25 — Separately Approved Upgrade Apply** | Apply only exact separately approved saved plan. | Human approval required; no inferred authorization. |
| **26 — Live E2E** | Approved synthetic functional order with current entitlement/context; result HMAC/consumer/owner readback; avoid real data. | After 25 and separate synthetic/identity approval. This may substitute for historic recovery as functional upgrade evidence if release owner accepts. |
| **27 — Release Gate** | Evidence, residual risk, operational/rollback gates, authorized release decision. | Last; no production release implied. |

Steps **20A/20B** are not on the default upgrade critical path unless historical recovery is explicitly required. Step **20C** can use an approved alternative canary without a recovery implementation. **19H and 25** are distinct approvals and must not be combined. No step is automatically started by 19E.

## 9. Boundaries and final safety record

- Local source/artifact reads only; no Mays-Orders repository changes.
- Local tests run: 25 worker tests; 22 synthetic cross-repository bridge/consumer/contract tests.
- No source-code or runtime-configuration changes; no new Runtime environment modes; `MODE=true` left untouched.
- No AWS reads or writes, live Lambda invocation, queue receive/send/delete, redrive, Terraform plan/apply/state operation, new order, WorkItem repair, entitlement write, cleanup, deployment, or upgrade.
- The original recovery approval remains consumed; no approval is inferred for future actions.

**Final gates:**

```text
RECOVERY_DESIGN=READY_FOR_REVIEW
RECOVERY_PATH=ALTERNATIVE_CANARY (historical native/custom execution unavailable today)
HISTORICAL_RECOVERY_REQUIRED=NO (unless release owner imposes it as a separate business gate)
WORKER_DEPLOYMENT_INDEPENDENT=CONDITIONAL
QA_COMPLETION_REQUIRED=19F
XREPO_CONTRACT_CHANGE_REQUIRED=NO for minimal RIS-only recovery; conditional if shared generation/lifecycle contract changes
MAYS_ORDERS_UPGRADE_READINESS=BLOCKED / CONDITIONAL
RECOMMENDED_NEXT_STEP=19F — QA Completion
AWS_MUTATIONS=0
LIVE_INVOCATIONS=0
REDRIVES=0
SOURCE_CODE_CHANGES=0
```
