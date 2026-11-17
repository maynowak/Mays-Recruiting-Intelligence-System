# RIS-ATS-RESULT-TRANSPORT-GATE-01 — Managed Result-Transport (lokal)

**Status:** Lokale Verdrahtung, Audit und Terraform-Plan abgeschlossen.
**Kein AWS Apply, kein Deploy, kein Destroy, kein Rollback, kein Merge.**
**Datum:** 2026-11-17
**Branch:** `feature/ris-dev2-ats-agent-pinned-core-01`
**Konto / Region / Workspace:** `262370457690` / `eu-central-1` / `ris-dev2`
**Orders-Lifecycle:** `managed` (Tabelle `ris-dev2-mays-orders`)

## 1. Ergebnis

Die vorhandene Mays-Orders-Installation ist so verdrahtet, dass der
`ORDER_RESULT`-Forwarder aus `RIS-ATS-RESULT-LINK-01` im gleichen Konto eine
modul-eigene Result-Queue und ein HMAC-Secret nutzt. Der Plan ist clean:
**13 Add, 2 In-Place-Updates, 0 Destroy, 0 Replace**, keine Cognito-, CloudFront-,
DNS- oder ACM-Änderung, kein Secret-Wert im State oder Plan.

## 2. Commits

| Commit | Inhalt |
|---|---|
| `7888634` | `feat(transport): wire the managed Orders result queue and secret` — Builder-Outputs, RIS-Root/Lambda-Env+IAM, Installer, Projekt-Config-Abgleich, statische Tests |
| `2757ffc` | `fix(ats): separate delivered results from completed work and harden read-back` — Delivery-Marker, Decimal-Fix, Reader-Härtung, Tests |
| (folgt) | Bericht `docs/reports/RIS-ATS-RESULT-TRANSPORT-GATE-01.md` |

Vorgänger: `95dc5b3`, `8336168`, `a8264e3`, `3774648` (RIS-ATS-RESULT-LINK-01).

## 3. Phase A — Prüfergebnisse (4 Audits)

- **Orders-Modul:** Queue/DLQ/Secret existieren bereits in
  `modules/agent_transport`, sind aber default-off und werden vom
  generierten Modul-Root nicht exportiert. Das Modul wird bei jedem Build aus
  Pin `dad69ea…` neu erzeugt; Hand-Edits sterben. Secret ist container-only
  (kein `aws_secretsmanager_secret_version`).
- **RIS-Worker:** `COMPLETED` belegte nur die Persistenz, nicht die Zustellung.
  Re-Emit nach Crash war vorhanden, aber ohne Delivery-Marker; `Decimal` wurde
  auf dem Re-Emit-Pfad als String serialisiert.
- **Security:** Reader fail-closed, Owner-Key identisch, 404-Indistinguishability
  und Whitelist korrekt. Gefunden wurden: Listen-500 bei Agent-Orders,
  fehlende Owner-Bedingung im PATCH-Update, akzeptiertes fehlendes
  `token_use`, sowie die Zwei-Pool-Frage (siehe Blocker).
- **QA:** 2.777 Tests gesammelt, 4 vorbestehende Collection-Errors, 29
  vorbestehende Fehlschläge (Symlink/ACL, fehlende Profile/Tools). Keine
  dieser Fehler ist durch diesen Auftrag entstanden.

## 4. Phase B — Minimaler Integrationspatch

### 4.1 Orders-Seite (unverändert im Besitz des Moduls)

- `installer/build_mays_orders_module.py` injiziert **additiv** vor der
  Vertragsprüfung:
  - `results_queue_url`
  - `results_queue_arn`
  - `result_hmac_secret_arn`

  jeweils als `try(module.agent_transport[0].…, "")`. Bei deaktiviertem
  Transport ist der Wert `""`. Exportiert Upstream künftig einen der Namen
  selbst, bricht der Build fail-closed ab (keine Duplikate). Das generierte
  Modul hat jetzt 23 Outputs (20 Pflicht + 3).
- Keine neue Queue, kein neues DLQ, kein zweiter Vertrag. Queue
  `ris-dev2-mays-orders-agent-results`, DLQ
  `ris-dev2-mays-orders-agent-results-dlq`, Secret
  `ris-dev2-mays-orders-agent-result-hmac` entstehen ausschließlich im
  Modul.

### 4.2 RIS-Seite

- Neue Root-Variable `orders_agent_result_enabled` (Default `false`),
  bewusst getrennt von `enable_agent_transport` (RIS-Dispatch-Queue).
- `module.mays_orders` erhält:
  - `enable_agent_transport = local.orders_agent_result_enabled`
  - `ris_result_producer_role_arns = [module.lambda.lambda_role_arn]`
- Root-Locals beziehen Queue-URL, Queue-ARN und Secret-ARN aus den
  Modul-Outputs.
- Worker-Lambda:
  - Env `ORDER_RESULT_QUEUE_URL`, `ORDER_RESULT_SECRET_ARN`
  - IAM count-gated auf den **planbaren** Bool:
    `sqs:SendMessage` nur auf die Result-Queue,
    `secretsmanager:GetSecretValue` nur auf das Result-Secret.
    Kein `ReceiveMessage`, kein Wildcard, keine Fremd-Ressource.
  - Beide Policies stehen in `depends_on` der Lambda.
- Root-Output `lambda_role_arn` (Worker-Rolle). Wichtig: `iam_role_arn` ist
  die Health-Plane-Rolle und wäre der falsche Producer.
- Installer: die drei Result-Outputs sind als „nicht per `-var` übergeben"
  markiert, damit der Dry-Run sie nicht raten muss;
  `orders_agent_result_enabled` ist ein erlaubter Overlay-Key.
- Projekt-Config `ris-dev2.json` wurde an den **Live-Zustand** angeglichen:
  `orders_lifecycle=managed`, `identity_m2m_enabled=true`,
  `identity_oauth_enabled=false`. Vorher hätte ein Installer-Apply das
  Cognito-M2M-Paar zerstört und OAuth aktiviert.

### 4.3 Delivery-Semantik

- Nach dem konditionalen Result-Write schreibt der Worker
  `orderResultDelivery` auf die Work-Row:
  - `SENT` (SQS angenommen, mit `messageId`)
  - `NOT_CONFIGURED` (kein Queue/Secret)
  - `SKIPPED` (`missing_correlation`, `missing_api_profile`)
  - `REJECTED` (permanenter `TransportError`, z. B. Size/Secret/Shape)
  - `RETRYING` (Sender-/Secret-Fehler, Exception wird erneut geworfen)
- Marker-Schreiben ist best effort: ein Marker-Fehler macht aus einem
  erfolgreichen Send keine Redelivery.
- Crash-Fenster zwischen Persistenz und Send bleibt durch den
  deterministischen Re-Emit auf `COMPLETED`-Duplikaten abgedeckt
  (gleiche `messageId`/`idempotencyKey`; Orders dedupliziert).
- `COMPLETED` allein gilt nicht mehr als zugestellt; die API-Doku nennt das
  explizit. Ein gespeichertes Result erhöht nie den fachlichen Order-Status
  (MO-Handoff-Test pinnt das).

### 4.4 Reader-Härtung (im selben Pfad benötigt)

- `PATCH` bindet `ownerKey` jetzt in der Conditional-Update-Bedingung.
- `token_use` ist Pflicht (`id`/`access`).
- `GET /orders` projiziert Agent-Orders ohne Retail-Felder statt `KeyError`
  → 500.
- Zurückgehaltene Payloads loggen nur den Feldpfad, nie den Wert.

## 5. Phase C — Infrastructure Readiness

| Prüfung | Ergebnis |
|---|---|
| AWS-Identität | `arn:aws:iam::262370457690:user/devnemo`, Konto korrekt. **Profilname `devnemo` existiert nicht**; der Default-Profil-User ist `devnemo`. Kein Profil wurde angelegt. |
| Region | `eu-central-1` |
| Workspace | `ris-dev2` (aktiver Workspace) |
| Backend-Bucket | `ris-dev2-tf-state-dev` |
| Backend-Key | `env:/ris-dev2/dev/terraform.tfstate` |
| Lock-Tabelle | `ris-dev2-tf-lock` (aktiv, keine aktive Lock) |
| State-Lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| State-Serial vor/nach Plan | `58` / `58` (ETag unverändert) |
| Modul-Source-Pin | Builder `dad69ea28e8b952a8e76e9dfb4fb163f7a979b52`; Arbeitsbaum des Pins sauber |
| Bundles | Agent `8462e5de6abb65b2…`, Reader `417e5b5f583e4f37…`; zweiter Build identisch |
| IAM/Secret-Grenzen | Nur Queue-Send bzw. Secret-Read, je eine Ressource; Secret container-only |
| Plan | `13 add / 2 change / 0 destroy / 0 replace`; Plan-SHA-256 `C6EFB189F0F161304186E20E28A2BAA074CF5AED213B03CF4DA32C2BFE22FE1F` |

**Die 2 Änderungen** sind ausschließlich:
`module.lambda.aws_lambda_function.agent` (Code + Env) und
`module.orders_reader[0].aws_lambda_function.reader` (Code + Cognito-Env).

**Die 13 Adds** sind:
1 Catalog-Seed (`ats-agent`), 2 Worker-IAM-Policies, 10 Result-Transport-
Ressourcen (Queue, DLQ, Queue-Policy, Secret, Secret-Policy, Consumer-Rolle,
Consumer-Rollen-Policy, Log-Group, Consumer-Lambda, Event-Source-Mapping).

**Nicht im Plan:** `aws_secretsmanager_secret_version`, Secret-String,
KMS-Custom-Key, Cognito-, CloudFront-, DNS- oder ACM-Ressourcen.

**Hinweis zum Plan:** Die Worker-Env erscheint als `(known after apply)`, weil
`ORDER_RESULT_SECRET_ARN` erst beim Apply entsteht. Die Bindung ist über die
Terraform-Konfiguration und den statischen Test belegt; der Plan kann den
unbekannten ARN nicht anzeigen.

## 6. Tests

| Suite | Ergebnis |
|---|---|
| Statische Terraform-/Wiring-Verträge (13 Dateien) | 297 passed, 11 skipped, 85 subtests |
| Neu: `tests/test_orders_result_transport.py` | 13 passed |
| Worker/Transport/Reader/Link | 194 passed, 318 subtests |
| MO-Consumer (`MO_ORDERS_SRC`) | 24 passed |
| Volle Suite | **2638 passed / 128 skipped / 434 subtests**, 29 vorbestehende Fehlschläge, 4 vorbestehende Collection-Errors |
| Terraform | `fmt -check` exit 0, `init -backend=false` + `validate` erfolgreich (Warnungen) |

Gegenüber der Baseline (`29 failed / 4 errors`) ist keine neue Regression
entstanden; die zuvor fehlschlagenden Reader-POST-Tests sind jetzt grün.

## 7. Modul-Outputs (generiert, 23)

Pflicht (20) unverändert, zusätzlich:

| Output | Wert bei deaktiviertem Transport |
|---|---|
| `results_queue_url` | `""` |
| `results_queue_arn` | `""` |
| `result_hmac_secret_arn` | `""` |

Bei aktiviertem Transport liefert das Modul die echten Werte aus
`modules/agent_transport`.

## 8. Risiken und verbleibende Blocker

1. **Secret-Wert fehlt (Apply-Voraussetzung).** Das Secret wird nur als
   Container angelegt. Ohne `put-secret-value` schlägt `GetSecretValue` fehl,
   der Sender wirft, SQS wiederholt bis zur DLQ. Der Wert muss **ein roher
   Hex-String** sein (kein Rotations-JSON `{"current":…,"previous":…}`),
   sonst signiert RIS den JSON-Text und jede Signatur scheitert.
2. **Zwei Cognito-Pools (Produkt-Read-back).** Der RIS-Reader pinnt den
   RIS-Pool (`eu-central-1_OYN9QiHc5`); das generierte Orders-Modul besitzt
   einen eigenen Pool (`eu-central-1_GInnOix9P`). Die ATS-Kette nutzt die
   RIS-eigene Orders-Fassade, daher ist der Owner-Key dort konsistent. Orders,
   die direkt über die Orders-API entstehen, tragen jedoch den Orders-Pool und
   liefern im RIS-Reader `404`. Eine Angleichung wäre eine Cognito-/Authorizer-
   Änderung und ist in diesem Auftrag bewusst **nicht** enthalten.
3. **Veralteter Orders-Adapter-Default.** `RealMaysOrdersAdapter.DEFAULT_BASE_URL`
   zeigt auf `aboqolpm0f`, diese API existiert live nicht mehr (live:
   `r95qvhg2p3`). `ORDERS_BASE_URL` ist nicht gesetzt. Betrifft den
   `orders.*`-Adapterpfad, nicht den ATS-Result-Transport; vor einer
   Produktnutzung zu korrigieren.
4. **Visibility-Timeout des Consumers.** Result-Queue 60 s gegen Lambda-Timeout
   30 s (Empfehlung ≥ 6×). Bei langsamen Batches drohen unnötige
   Redeliveries/DLQ. Modul-seitig, nicht in diesem Auftrag geändert.
5. **Kein `ORDER_FAILED`.** Der Forwarder sendet nur Erfolg; dauerhaft
   fehlgeschlagene Agenten hinterlassen Orders ohne `processing`. Kein neuer
   Vertrag in diesem Auftrag.
6. **Generiertes Modul.** `terraform/modules/mays_orders/` ist gitignored,
   aber `variables.tf` ist historisch getrackt. Vor jedem Plan muss das Modul
   neu gebaut werden (`python -m installer.build_mays_orders_module
   --project-name ris-dev2 --force`); der getrackte Stub wird nicht committet.
7. **Profilname.** `devnemo` existiert nicht als AWS-Profil; die Identität ist
   über das `default`-Profil als User `devnemo` belegt. Ein Apply-Gate muss
   den Profilnamen explizit bestätigen.
8. **Xrepo/Merge** unverändert: keine Issues/Dispatch, kein Merge nach `main`.

## 9. Empfehlung für das separate Apply-Gate

**GO nur mit den folgenden Vorbedingungen**, sonst NO-GO:

1. Freigegebener Commit und sauberer Tree; Plan-SHA
   `C6EFB189F0F161304186E20E28A2BAA074CF5AED213B03CF4DA32C2BFE22FE1F`
   gegen genau diesen Commit neu erzeugen.
2. Secret-Wert **vor** dem Enable setzen:
   `put-secret-value` auf `ris-dev2-mays-orders-agent-result-hmac` mit einem
   rohen Hex-String, außerhalb von Terraform/State/Git.
3. `orders_agent_result_enabled=true` nur über den freigegebenen Plan.
4. Plan erneut prüfen: 13/2/0/0, keine Deletes/Replaces, keine Cognito-,
   CloudFront-, DNS- oder ACM-Änderung, kein `secret_version`.
5. Nach dem Apply read-only verifizieren: `202` beim ATS-Execute, Work-Row
   `COMPLETED` **und** `orderResultDelivery.status=SENT`, Orders
   `processing.result.bodyVersion=2.0`, Owner-Read `200`, fremder Owner `404`,
   fremder Issuer `401`, fehlende Reader-Env `503`.
6. Rollback-Grenze: Modul-Flag zurück auf `false` entfernt Queue/Secret/
   Consumer wieder; der Secret-Wert ist out-of-band zu löschen.

**HARD STOP vor jedem AWS Apply.**
