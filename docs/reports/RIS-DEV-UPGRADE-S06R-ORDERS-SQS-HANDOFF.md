# RIS-DEV-UPGRADE-S06R — Orders-SQS Handoff

**Empfänger:** Eigentümer des Mays-Orders-Moduls / der Queue `ris-dev-mays-orders-orders-queue`
**Erstellt:** 2026-11-03 · **Status:** offen, keine Änderung ausgeführt
**Grundlage:** S02–S06, Live-Policy (read-only, `mayaws`, `eu-central-1`)

---

## 1. Befund

Effektive Queue-Policy (Auszug, vollständig geprüft):

```json
{
  "Sid": "AllowAccessFromAccount",
  "Effect": "Allow",
  "Principal": "*",
  "Action": ["sqs:SendMessage", "sqs:ReceiveMessage",
             "sqs:DeleteMessage", "sqs:GetQueueAttributes"],
  "Resource": "arn:aws:sqs:eu-central-1:240571105849:ris-dev-mays-orders-orders-queue"
}
```

Quelle: generiertes Modul `terraform/modules/mays_orders/modules/sqs/main.tf:29-40`.

| Eigenschaft | Bewertung |
|---|---|
| Anonymer Internetzugriff | **nicht möglich** (SigV4 erforderlich) — nicht als „öffentlich“ darstellen |
| Cross-Account | **möglich**: jeder Principal mit eigener IAM-Erlaubnis |
| Conditions | **keine** (`aws:SourceAccount`, `aws:SourceArn` fehlen) |
| Kritischste Rechte | `ReceiveMessage` + `DeleteMessage` (Exfiltration, Löschung) |
| Queue-Eigentümer | RIS (`Project=ris-dev-mays-orders`) |
| Code-Eigentümer | Mays-Orders-Modul (generiert, nicht hand-editierbar) |

---

## 2. Tatsächliche Nutzer

| Rolle | Principal | Benötigte Aktionen |
|---|---|---|
| Producer | `arn:aws:iam::240571105849:role/ris-dev-dev-agent` (RIS-Agent sendet Aufträge) | `sqs:SendMessage` |
| Consumer | `arn:aws:iam::240571105849:role/ris-dev-mays-orders-sqs-worker-role` | `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` |
| Betreiber/Diagnose | Account-Root oder Monitoring-Rolle | `GetQueueAttributes` (optional) |

Kein nachgewiesener Cross-Account-Producer oder -Consumer. Die RIS-Queue ist eine RIS-Ressource; Mays-Orders betreibt parallel eigene Infrastruktur.

---

## 3. Vorgeschlagene Soll-Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ProducerSendOnly",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::240571105849:role/ris-dev-dev-agent"},
      "Action": "sqs:SendMessage",
      "Resource": "arn:aws:sqs:eu-central-1:240571105849:ris-dev-mays-orders-orders-queue",
      "Condition": {"StringEquals": {"aws:SourceAccount": "240571105849"}}
    },
    {
      "Sid": "ConsumerReceiveDelete",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::240571105849:role/ris-dev-mays-orders-sqs-worker-role"},
      "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"],
      "Resource": "arn:aws:sqs:eu-central-1:240571105849:ris-dev-mays-orders-orders-queue",
      "Condition": {"StringEquals": {"aws:SourceAccount": "240571105849"}}
    }
  ]
}
```

Änderungsumfang: 1 Ressource (`aws_sqs_queue_policy.orders`), keine Queue-Ersetzung, keine Nachrichtenänderung, keine Consumer-Unterbrechung bei korrekter Rollen-ARN.

---

## 4. Auswirkungen und Risiken

| Aspekt | Bewertung |
|---|---|
| Verengung auf zwei Rollen | bricht nur nicht dokumentierte Fremdzugriffe |
| `aws:SourceAccount` | verhindert Confused-Deputy über fremde Principals |
| Rollen-Umbenennung | würde Policy brechen → bei Rename Policy mitziehen |
| Fehlende Rolle | `SendMessage` schlägt fehl; sichtbar als 403 im Agent-Log |
| Rollback | alte Policy aus diesem Dokument wiederherstellen; keine Datenänderung |

---

## 5. Verifikation nach Änderung

1. `aws sqs get-queue-attributes` → Policy enthält keine `"*"`-Principal mehr.
2. Agent-Testauftrag → `SendMessage` erfolgreich.
3. Worker-Start → `ReceiveMessage`/`DeleteMessage` erfolgreich, keine DLQ-Explosion.
4. Negativtest mit fremder Rolle/Account → `AccessDenied`.
5. CloudWatch: keine neue `NumberOfMessagesSent`-Lücke, keine `ApproximateAgeOfOldestMessage`-Spitze.

---

## 6. Erforderliche Freigabe

- **Eigentümer:** Mays-Orders-/Plattform-Verantwortlicher (Policy-Code liegt im generierten Modul).
- **Betrieb:** RIS-On-Call für Rollen-ARN-Bestätigung.
- **Nachweis:** Screenshot/CLI-Output der neuen Policy + Negativtest.

Ohne diese Freigabe bleibt **RG-11 BLOCKED**; eine Risikoakzeptanz muss namentlich und schriftlich erfolgen.
