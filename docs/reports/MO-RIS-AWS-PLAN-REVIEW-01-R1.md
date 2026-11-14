# MO-RIS-AWS-PLAN-REVIEW-01 — R1 Discovery Report

**Datum:** 2026-11-14
**Modus:** READ-ONLY. Keine AWS-Mutation, kein Plan, kein Apply, kein Secret-Zugriff.
**Ergebnis:** **R1 DISCOVERY COMPLETE — R2 BLOCKED (AWS_ACCOUNT_IDENTITY_UNVERIFIED).**

## 1. Executive Summary

Alle lokalen Nachweise sind konsistent: Git-Baselines stimmen, Terraform-Code ist
default-off, beide Lambda-Artefakte existieren und enthalten die neuen Handler,
die erwartete Zahl von 18 Ressourcen ist aus dem Code bestätigt.

Der einzige harte Blocker ist der **fehlende AWS-Zugang zum Zielkonto
`240571105849`**: Auf diesem Rechner existiert genau ein Profil (`default`,
Entwickler-Testkonto `262370457690`). Ein autorisiertes Profil für das Zielkonto
gibt es nicht. Deshalb wurde **kein** `sts get-caller-identity` gegen das
Zielkonto ausgeführt und **kein** Remote-State gelesen.

## 2. Git-Baseline

| Repo | Branch | HEAD | Remote | Working Tree |
|---|---|---|---|---|
| RIS | `feature/ris-mo-addition-agent-e2e-01` | `a7cd516` | identisch | clean |
| Orders | `feature/mo-agent-order-body-01` | `c54467d` | identisch | clean |

Keine fremden Änderungen vorgefunden, keine bereinigt.

## 3. AWS-Profile und Identität

| Prüfung | Ergebnis |
|---|---|
| `aws configure list-profiles` | **nur `default`** |
| `~/.aws/config` | `[default]`, `region = eu-central-1` |
| Profil für `240571105849` | **nicht vorhanden** |
| STS-Aufruf gegen Zielkonto | **nicht ausgeführt** (kein autorisiertes Profil) |

Zur Einordnung: Die Identität des `default`-Profils wurde zu Beginn dieser
Arbeitssitzung mit ausdrücklicher Nutzerfreigabe geprüft
(`arn:aws:iam::262370457690:user/devnemo`). Das ist das Entwickler-Testkonto,
**nicht** das Zielkonto. In R1 wurde sie nicht erneut abgefragt, weil die
Vorgabe lautet, `default` nicht automatisch zu verwenden.

> **BLOCKED — AWS_ACCOUNT_IDENTITY_UNVERIFIED**

## 4. Account- und Region-Matrix

| System | Account | Region | Quelle | Status |
|---|---|---|---|---|
| Mays-Orders | `240571105849` | `eu-central-1` | `terraform/backend.tf` (Bucket-Name, Region) + Deployment-Reports (`mayaws`) | **dateibasiert** |
| RIS | `240571105849` | `eu-central-1` | RIS `AGENTS.md` (`ris-dev`, Account/Region) + Installer-Backend-Schema | **dateibasiert** |
| Entwickler-Testkonto | `262370457690` | `eu-central-1` | STS zu Sitzungsbeginn | live bestätigt, **nicht Ziel** |

**Same-Account-Annahme:** durch zwei unabhängige Dateiquellen gestützt, live
**nicht** bestätigt. Widersprüchliche Nachweise wurden nicht gefunden; es gibt
keine `provider`-, `account_id`- oder `assume_role`-Blöcke in den neuen Modulen.

## 5. Terraform State Ownership

| System | Backend | State-Key | Account | Region | Ownership |
|---|---|---|---|---|---|
| Orders | S3 `mays-orders-tfstate-central-240571105849` | `terraform.tfstate`, Prefix `env:` → `env:/<workspace>/terraform.tfstate` | `240571105849` | `eu-central-1` | Orders-Repo, Lock `mays-orders-terraform-locks` |
| RIS | S3 partial; Werte via `-backend-config` | `env:/<project>/<env>/terraform.tfstate` | `240571105849` (dateibasiert) | `eu-central-1` | RIS-Installer, Lock `<project>-tf-lock` |

Der RIS-Zielstate (`ris-dev`) wurde **nicht** gelesen: kein freigegebenes Profil.
Keine `terraform init`-Aufrufe gegen Remote-Backends in R1.

## 6. Bestehendes Ressourceninventar (dateibasiert)

| Bereich | Bestand |
|---|---|
| Orders Queues | `mays-orders-orders-queue` (Retail, visibility 30 s, retention 120 s, **keine DLQ**) |
| RIS Queues | `work`, `cv`, `ats`, `match`, `dlq` (visibility 300 s, DLQ 14 d) |
| RIS Lambdas | Agent-Worker (Bundle `terraform/lambda.zip`), Reader, Health |
| Orders Lambdas | HTTP-Handler, SQS-Worker |
| KMS | keiner in beiden Repos |
| Secrets Manager | nur IAM-Aktion `GetSecretValue` in RIS referenziert, **kein** Secret-Resource |

## 7. Geplante Verknüpfungen (Flag an)

| Verbindung | Quelle → Ziel |
|---|---|
| Dispatch-Queue | RIS-eigen, Policy erlaubt `var.orders_producer_role_arns` |
| Dispatch-Ingress | RIS-Lambda `dispatch_ingress.handler` ← ESM Batch 5, `ReportBatchItemFailures` |
| Result-Queue | Orders-eigen, Policy erlaubt `var.ris_result_producer_role_arns` |
| Result-Consumer | Orders-Lambda `result_consumer.handler` ← ESM Batch 10 |
| Secret | Orders-Container; Consumer liest eigenes Secret; RIS-Rollen optional per Policy |
| IAM | 2 eigene Rollen, keine Agent-/HTTP-Rollen-Wiederverwendung |

## 8. Feature-Flags und Artefakte

| Prüfung | Ergebnis |
|---|---|
| RIS `enable_agent_transport` Default | `false` |
| Orders `enable_agent_transport` Default | `false` |
| Modul-Gate | `count = var.enable_agent_transport ? 1 : 0` (beide) |
| RIS Ressourcen im Modul | **8** |
| Orders Ressourcen im Modul | **11** (davon KMS-Policy `count = 0` → **10 aktiv**) |
| **Summe aktiv bei Flag an** | **18 Creates**, 0 Updates, 0 Deletes |
| RIS ZIP | vorhanden, 301 632 B, `sha256 6d77ed97…`, 91 Dateien, `dispatch_ingress.py` enthalten |
| Orders ZIP | vorhanden, 29 531 B, `sha256 010feb64…`, 13 Module, `result_consumer.py` enthalten |
| Handler | `dispatch_ingress.handler`, `result_consumer.handler` |
| Runtime | `python3.14` (Variable, Default) |

**L04-Regression geprüft:** Das Orders-ZIP enthält alle 13 Module. Der frühere
Fehler (fest verdrahtete Sieben-Modul-Liste) ist behoben und bleibt durch
`build_zip.py`-Auto-Discovery + Tests abgesichert.

## 9. Sicherheits- und Datenschutzbefunde

| Nachweis | Status |
|---|---|
| RIS-Key ist keine Orders-Identität | bestätigt (kein Key im Transport, A05/A07) |
| Owner aus verifizierter Cognito-Identität | bestätigt (`identity.py`, `iss`+`sub`) |
| Service-Rollen ohne Benutzerrechte | bestätigt (Consumer: nur Get/Update auf Orders-Tabelle) |
| Queue-Nachricht ≠ Autorisierung | bestätigt (HMAC + `expectedWorkId`) |
| Ergebnisbindung über Order-/WorkId | bestätigt (A06 `work_mismatch`) |
| Secret-Mechanismus | Secrets Manager vorgesehen, Wert out-of-band |
| Keine Secretwerte in Git/Reports/Tests | bestätigt (nur ARN-Referenzen) |
| Kein RIS-Zugriff auf Orders-DynamoDB | bestätigt (keine Policy) |
| Keine Cognito/CloudFront/DNS-Änderung | bestätigt (Module enthalten keine solchen Ressourcen) |
| Keine Wildcard-Ressource für DynamoDB/SQS | bestätigt (statischer Test) |

## 10. IST / SOLL / GAP

| # | Element | SOLL | IST | GAP |
|---|---|---|---|---|
| 1 | Git-Baselines | `a7cd516` / `c54467d` | identisch, clean | — |
| 2 | Same-Account | 240571105849 | dateibasiert bestätigt | **live unbestätigt** |
| 3 | State-Ownership | dokumentiert | dokumentiert | RIS-State nicht gelesen |
| 4 | Queues | beide neu | default-off | — |
| 5 | Lambdas | beide verdrahtet | verdrahtet | — |
| 6 | IAM | Least Privilege | zwei eigene Rollen | — |
| 7 | Secret | Secrets Manager | Container, Wert fehlt | Wert provisionieren |
| 8 | Artefakte | vorhanden, vollständig | vorhanden, geprüft | — |
| 9 | Plan | gegen freigegebenen State | **nicht erstellt** | R2 nötig |

## 11. Blocker

| # | Blocker | Wirkung |
|---|---|---|
| B1 | **Kein Profil für `240571105849`** | Kein STS-Nachweis, kein State-Lesezugriff, kein Plan |
| B2 | Secret-Wert nicht provisioniert | Consumer fail-closed im Betrieb |
| B3 | RIS-State-Ownership nur dateibasiert | State-Serial/Workspace nicht bestätigt |
| B4 | ZIP nicht versioniert (gitignored) | Vor jedem Plan neu bauen (bestehender Contract) |

## 12. Voraussetzungen für R2

1. Freigegebenes **read-only** Profil für `240571105849` (Name vom Betreiber).
2. Bestätigung der Accounts durch `sts get-caller-identity`.
3. Lesender Zugriff auf die State-Buckets (`mays-orders-tfstate-central-240571105849`, RIS-Bucket) zur Serial-/Workspace-Prüfung.
4. Gebaute ZIPs (beide) zum Plan-Zeitpunkt.
5. Entscheidung, ob R2 nur `plan` oder auch `plan -out` mit Review erzeugt.

## 13. Freigabeempfehlung

> **R1: DISCOVERY COMPLETE.**
> **R2: BLOCKED — `AWS_ACCOUNT_IDENTITY_UNVERIFIED`.**

Die fachliche und technische Grundlage ist vollständig: Code, Verträge,
Artefakte und Flag-Verhalten sind geprüft. Was fehlt, ist ausschließlich der
Zugang zum Zielkonto. Ein Plan gegen ein anderes Konto wäre irreführend und
wurde deshalb nicht erzeugt.
