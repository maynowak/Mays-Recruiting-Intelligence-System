# MO-RIS-AWS-PLAN-REVIEW-02 — R2 Results: RIS-dev2 Plans

**Datum:** 2026-11-14
**Modus:** Read-only Planung. **Kein Apply, kein Destroy, kein Deployment.**
**Ergebnis:** RIS-Seite **PLAN REVIEW READY** · Orders-Seite **BLOCKED**.

## 1. Identität (mit `default`, wie vom Auftraggeber klargestellt)

```
aws sts get-caller-identity
→ Account 262370457690
  arn:aws:iam::262370457690:user/devnemo
Region eu-central-1
```

Das ist **nicht** das in R1 erwartete `240571105849`. Die Klarstellung des
Auftraggebers („das ist der default auf diesem pc, ris-dev2") löst den
Widerspruch auf: **RIS-dev2 liegt in `262370457690`**, Orders in
`240571105849`. Die Integration ist damit **Cross-Account**.

## 2. RIS-dev2 State (gelesen, nur Metadaten)

| Feld | Wert |
|---|---|
| Backend | S3 `ris-dev2-tf-state-dev` |
| Key | `env:/ris-dev2/dev/terraform.tfstate` |
| Workspace | `ris-dev2` |
| Lock | `ris-dev2-tf-lock` |
| State-Objekt | 5 406 B, zuletzt 2026-11-09 08:37 UTC |
| **Serial** | **36** |
| Lineage | vorhanden |
| terraform_version | 1.17.0 |
| **Ressourcen** | **0** |
| Outputs | keine |

Bestätigt den Destroy-Bericht: `ris-dev2` ist ein leerer, aber intakter
Workspace. Live existiert nur die Lock-Tabelle `ris-dev2-tf-lock`.

## 3. Pläne

| Plan | Creates | Reads | Updates | Deletes | Integration |
|---|---|---|---|---|---|
| **default-off** | **183** | 3 | 0 | 0 | **0** |
| **enabled** (`enable_agent_transport=true`) | **191** | 3 | 0 | 0 | **8** |
| **Differenz** | **+8** | — | 0 | 0 | +8 |

SHA-256:

```
ris-dev2-default.tfplan  08ecbd3da81fe2f30f20b191267ed3459a88d78e50193cedceceaaa769bce67f
ris-dev2-enabled.tfplan  779dbc92256ff54d99fbab3b2bce98ab907cb7fb283abd73958d68e43cd2867c
```

Die 3 Reads sind Datensources (`aws_iam_policy_document`, `aws_region`).

## 4. Die 8 Integrationsressourcen (enabled)

```
module.agent_transport[0].aws_sqs_queue.dispatch
module.agent_transport[0].aws_sqs_queue.dispatch_dlq
module.agent_transport[0].aws_sqs_queue_policy.dispatch
module.agent_transport[0].aws_cloudwatch_log_group.dispatch_ingress
module.agent_transport[0].aws_iam_role.dispatch_ingress
module.agent_transport[0].aws_iam_role_policy.dispatch_ingress
module.agent_transport[0].aws_lambda_function.dispatch_ingress
module.agent_transport[0].aws_lambda_event_source_mapping.dispatch
```

Alle `create`. **Keine** Updates, Replacements oder Deletes.

## 5. Kritischer Befund: der Plan ist ein Vollaufbau

Weil `ris-dev2` **0 Ressourcen** hat, plant auch der Default-off-Lauf **183
Creates** — die komplette RIS-Plattform (Cognito, API, 66 Routen, Lambdas,
DynamoDB, SQS, CloudFront, CloudTrail, Health).

Mit aktivierter Integration sind es **191**. Das sind **nicht** „18 Creates",
sondern „183 Bestand neu + 8 Integration". Ein Apply würde `ris-dev2` vollständig
neu errichten.

## 6. Orders-Seite — BLOCKED

| Prüfung | Ergebnis |
|---|---|
| Orders-State-Bucket `mays-orders-tfstate-central-240571105849` | **403 Forbidden** |
| Orders-Tabellen/Buckets in `262370457690` | **keine** |
| Orders-Plan möglich | **nein** |

Grund: Orders liegt in `240571105849`; `default` hat dort keinen Zugriff.
Damit sind von den erwarteten 18 Ressourcen nur **8 (RIS)** verifiziert;
**10 (Orders)** sind unbestätigt.

## 7. Topologie-Korrektur zu PLAN-02

PLAN-02 hatte „same account" angenommen. Das war falsch für `ris-dev2`:

| System | Account | Region |
|---|---|---|
| RIS `ris-dev2` | **262370457690** | eu-central-1 |
| Mays-Orders | **240571105849** | eu-central-1 |

**Konsequenz:** Die Queue-Policy im RIS-Modul muss den **Cross-Account-Rollen-ARN**
der Orders-Producer-Rolle enthalten. Das Modul unterstützt das über
`orders_producer_role_arns` bereits — es ist kein Architekturbruch, aber der Wert
muss aus `240571105849` kommen. Gleiches gilt spiegelbildlich für
`ris_result_producer_role_arns` in Orders.

## 8. Risiken

| # | Risiko | Wirkung |
|---|---|---|
| 1 | Apply = Vollaufbau von `ris-dev2` (191 Ressourcen) | bewusste Neuinstallation nötig, kein „nur Integration" |
| 2 | Cross-Account-Policies noch nicht parametriert | Plan zeigt `Principal: []`, Apply würde eine ungültige Policy erzeugen |
| 3 | Orders-Plan fehlt (403) | 10 von 18 Ressourcen unbestätigt |
| 4 | Secret-Wert fehlt | Consumer fail-closed |
| 5 | Plan-Dateien sind an State-Serial 36 gebunden | nach jeder State-Änderung neu planen |

## 9. Empfehlung

**RIS: READY FOR PLAN REVIEW.** Die 8 Integrationsressourcen sind vollständig,
ohne Update/Delete, und der Default-off-Lauf bleibt bei 0 Integration.

**Orders: BLOCKED.** Ohne Zugang zu `240571105849` gibt es keinen belastbaren
Plan.

Vor einem Apply sind zwei Entscheidungen nötig:

1. **Ist der Vollaufbau von `ris-dev2` gewollt?** (183 Bestand + 8 Integration)
   Falls nein: die Integration auf einer bereits laufenden Installation planen
   (z. B. `ris-agent`, 185 Ressourcen, drift 0).
2. **Cross-Account-ARNs** für `orders_producer_role_arns` (RIS) und
   `ris_result_producer_role_arns` (Orders) festlegen.

Kein Apply, kein Destroy, kein Deployment, keine Secrets gelesen.
