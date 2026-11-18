# RIS Agent Installation 08 — Handoff für ris-dev

**Status:** Test-Deployment auf `ris-dev2` abgeschlossen, Live-E2E **PASS**.
**Datum:** 2026-11-18
**Maschinenlesbar:** `docs/releases/ris-agent-installation-08.json`

## 1. Was wurde neu gebaut?

- ATS-Agent-Order-Pfad live auf `ris-dev2`: RIS-Fassade → ORDER_DISPATCH →
  Dispatch-Ingress → WorkItem → ATS → ORDER_RESULT → Mays-Orders-Consumer →
  persistierte Order → Owner-Read-back.
- Neue/aktualisierte Ressourcen: Dispatch-Queue + DLQ + Ingress-Lambda,
  Result-Queue + DLQ + Consumer, HMAC-Secret (Container), Reader-Env/IAM,
  Worker-Result-Env/IAM, Catalog-Seed `ats-agent`, gemeinsamer Orders-Bundle-
  Update.
- Timeout-Härtung: Worker und Dispatch-Ingress 60 s (ATS-Client 30 s).
- Agent-Installationspakete und ein minimaler Orchestrator
  (`installer/agent_install.py`).

## 2. Verfügbare Agenten

| Agent | Capability | Version | Status |
|---|---|---|---|
| `ats-agent` | `analyze.job` | 1.0.0 | live getestet |
| `addition_agent` | `math.add` | 1.0.0 | Referenz, lokal getestet |

## 3. Freigegebene Source-Pins

- RIS: `f0c707c6e80638a6489194b3be98374718a6a522`
- Orders: `016cdfd6ac62565dcec9a2fee78cb898fb919e59`
- Bundles: Agent `5258c99e…`, Reader `55366e35…`, Orders `48ddd5e5…`

## 4. Benötigte Ressourcen

- AWS-Konto `262370457690`, Region `eu-central-1`, Workspace `ris-dev2`,
  Orders-Lifecycle `managed`.
- Dispatch-Queue/-DLQ/-Ingress (60 s, Batch 5, ReportBatchItemFailures).
- Result-Queue/-DLQ/-Consumer (30 s, Batch 10), Secret-Container.
- Reader-Env `RIS_DISPATCH_QUEUE_URL`, `API_PROFILES_TABLE`,
  `ORDERS_COGNITO_ISSUER/CLIENT_ID`; Worker-Env `ORDER_RESULT_*`,
  `ATS_API_BASE_URL`.
- Identität: RIS-Pool-Benutzer, ACTIVE API-Profil (`ownerUserId=sub`,
  `tenantId`), user-weites `ats-agent`-Entitlement.

## 5. Unangetastet

Cognito-Pools/-Clients/-Domain/-Authorizer, CloudFront, Route53/DNS, ACM,
bestehende Benutzer und Nicht-Test-Daten. Kein `ris-dev`-/Production-Change.

## 6. Risiken und Betriebsfolgen

- ATS läuft gegen den Produktions-Vertragshost; kein Non-Prod-Endpunkt. Nur
  synthetische Daten verwenden.
- Result-Visibility 60 s vs. Consumer-Timeout 30 s.
- Keine DLQ-Alarme/SNS-Actions; permanente Rejects nur im Log.
- Kein `ORDER_FAILED`: fehlgeschlagene Agenten hinterlassen keine Orders-Spur.
- Reader-POST ohne Request-Idempotenz.
- Dispatch-Ingress führt inline aus; 60 s Timeout.
- Orders-`main` hat einen anderen Consumer-Vertrag; Pin nicht ohne
  Producer-Anpassung Richtung `main` bewegen.

## 7. Tests

Lokal: E2E 6, Reader 35, Dispatch-Ingress 16, Cross-Repo 192, Orders 225,
volle RIS-Suite 2654 passed / 134 skipped (29 bekannte Fehler), Orchestrator 5.

Live: Order `ord_0d23d52e98fb4c557e7aa920`, WorkItem
`work-a818f56a2f5ec0d0`, Work `COMPLETED`, `orderResultDelivery=SENT`, Orders
`processing=COMPLETED`, `bodyVersion=2.0`, Score 67, Order-Status `PENDING`;
Owner 200, fremder Owner 404, ungültiges Token 401; Duplikat ohne zweiten
Write (Version 2 unverändert); Retail 201/200; Queues/DLQs 0; Logs ohne
`ownerKey`, `ris_`, synthetische E-Mail oder `invalid service signature`.

## 8. Installieren / Deaktivieren / Aktualisieren / Wiederherstellen

- **Installieren:** Paket validieren (`python -m installer.agent_install
  --agent ats-agent --stage validate`), Bundles/Modul bauen, Plan prüfen
  (`orders_agent_result_enabled=true`, `enable_agent_transport=true`), Plan
  anwenden, Secret (bare 64-hex) setzen, Identität/Profil/Entitlement
  provisionieren, Canary.
- **Deaktivieren:** Traffic stoppen, Plan mit beiden Flags `false`, Testdaten
  widerrufen; Secret nur über einen separaten Reviewed-Schritt löschen.
- **Aktualisieren:** neuen Agent-SHA im Manifest pinnen, lokale Tests,
  `agent_install`-Stages, Plan/Diff, Canary; nie ungeprüft deployen.
- **Wiederherstellen:** vorherigen Lambda-Bundle-Plan anwenden; Queues bleiben
  bei deaktivierten Flags nicht bestehen; Secret-Version `AWSPREVIOUS`
  erlaubt Rollback nach Recycling beider Lambdas.

## 9. Offene Entscheidungen für ris-dev

1. Partner-Traffic freigeben oder weiter sperren.
2. DLQ-Alarme/SNS vor Produktbetrieb ergänzen.
3. `ORDER_FAILED`-Semantik entscheiden.
4. Result-Visibility erhöhen oder 2×-Verhältnis akzeptieren.
5. Non-Prod-ATS-Endpunkt bereitstellen (hermetischer Canary).
6. Umgang mit den synthetischen Evidence-Orders/Work-Rows festlegen.

## 10. Orchestrator

`python -m installer.agent_install --root agent-installations [--agent <id>
--stage <stage> --status-file <path>]`

Stages: DISCOVER → ANALYZE → COMPATIBILITY → RISK REVIEW → PACKAGE →
VALIDATE → PLAN → APPLY → E2E → HANDOFF. Status ist idempotent/resumierbar;
`APPLY` verweigert ohne `--execute --allow-apply --yes`. Das Anlegen eines
Pakets aktiviert keinen Agenten und ändert keine anderen Agenten.
