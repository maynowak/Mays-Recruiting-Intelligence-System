# RIS-DEV2-DRIFT-FORENSICS-01

**Datum:** 2026-11-25  
**Repository:** `maynowak/Mays-Recruiting-Intelligence-System`  
**Branch / HEAD:** `feature/ris-analysis-integration-07` / `ef8c12656f120e83fe4b67fa92fc4b3b425a830e`  
**Modus:** strictly read-only; no apply, no plan, no state write  
**Plan:** `C:\tmp\ris-dev2-correlation-fix.tfplan`  
**SHA-256:** `2bbf81424b9761712008ef698f5afe5bb6b5ac1db0eaa74220427e8f09b7facd`

## Ergebnis

**B — BLOCKED**

Der gespeicherte Plan enthält weiterhin exakt sieben Lambda-Code-Updates und
keine IAM-Änderungsaktion. Die drei `resource_drift`-Einträge sind erklärt:
zwei bestätigte externe, sicherheitsrelevante IAM-Berechtigungserweiterungen
gegenüber dem gespeicherten Backend-State sowie eine Provider-/State-Normalisierung
bei `layers`. Die Live-IAM-Dokumente stimmen mit dem im Plan deklarierten
Terraform-Soll überein, aber die Herkunft und separate Autorisierung der beiden
Erweiterungen sind nicht belegt. Die neuen Rechte sind daher nicht
„sicherheitsneutral“. Der alte Apply-Auftrag bleibt gesperrt; eine erneute
ausdrückliche Freigabe ist erforderlich.

## 1. Plan- und State-Identität

Read-only-Prüfungen:

| Prüfung | Nachweis |
| --- | --- |
| Branch / Git | erwarteter Feature-Branch; HEAD und `origin` beide `ef8c12656f120e83fe4b67fa92fc4b3b425a830e` |
| Plan SHA-256 | exakt `2bbf81424b9761712008ef698f5afe5bb6b5ac1db0eaa74220427e8f09b7facd` |
| Terraform | `terraform show -json`: 1.17.0; Planzeit `2026-11-25T07:07:04Z`; `applyable=true`, `complete=true`, `errored=false` |
| AWS | Konto `262370457690`; CLI-Region `eu-central-1` |
| Workspace / Backend | `ris-dev2`; S3 `ris-dev2-tf-state-dev`, Key `env:/ris-dev2/dev/terraform.tfstate`, Region `eu-central-1`, Lock-Tabelle `ris-dev2-tf-lock` |
| Aktueller State | read-only `terraform state pull`: Lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, Serial `69` |
| Aktuelles S3-Objekt | Version `21V4lPFLRfZO7YLrgBcxlVtFOZb5y8dW`; LastModified `2026-11-22T11:52:56Z`, vor Planzeit; ETag `1a10ed486eceb97c65b1d52eefd406e3` |
| Lock-Tabelle | zwei vorhandene `-md5`-Checksum-Einträge, beide ohne `Info`; kein aktiver Terraform-Lock-Eintrag festgestellt |

Das stimmt mit der dokumentierten Plan-Baseline (Lineage/Serial 69, S3-State
zuletzt am 22.11.2026 geändert) überein. Seit dem dokumentierten State-Stand
ist keine spätere S3-State-Version sichtbar.

### Öffentliches Plan-JSON und Lineage/Serial

Das öffentliche `terraform show -json`-Format gibt im Objekt `prior_state`
`format_version`, `terraform_version` und `values` aus, **nicht** die
Lineage- oder Serial-Metadaten. Es ist deshalb nicht möglich, Lineage/Serial
aus diesem JSON direkt gegen den aktuellen State zu vergleichen. Es wurden
keine internen/nicht dokumentierten Binärformate geparst.

Terraform prüft beim Anwenden eines gespeicherten Plans selbst, ob dessen
State-Basis noch aktuell ist; eine inkompatible State-Lineage bzw. ein
zwischenzeitlich fortgeschriebener Serial führt zur Ablehnung des veralteten
Plans, bevor Terraform die geplanten Ressourcenänderungen ausführt. Diese
automatische Stale-Plan-Sicherung ist eine zusätzliche technische Schranke,
aber weder ein Ersatz für die menschliche Drift-Entscheidung noch eine
Wiederaufnahme der früheren Apply-Freigabe.

### Ressourcenvergleich `prior_state` ↔ aktueller State

Der Plan-`prior_state` und der aktuelle `terraform state pull` enthalten jeweils
272 Managed-Resource-Instanzen. Die drei Seed-Items unterscheiden sich nur in
der Darstellung des String-`index_key` (JSON-Quotes); nach Kanonisierung sind
die Adressmengen gleich. 255 Instanzen sind wertgleich. Die übrigen 17
Abweichungen bestehen aus:

- den zwei IAM-`inline_policy`-Drifts in §2;
- 15 Provider-/Schema-Repräsentationsunterschieden: `layers` (`null`/`[]`),
  CloudTrail `recursive_logging` und `evaluation_window` bei 13 Alarmen.

Die 15 Normalisierungen ändern keine IAM-Berechtigung, keine Layer-Anbindung
und keine der sieben geplanten Ressourcenaktionen. Sie sind getrennt von den
beiden echten Policy-Unterschieden ausgewiesen.

## 2. Die drei `resource_drift`-Einträge

### 2.1 Dispatch-Ingress-IAM-Rolle

| Feld | Nachweis |
| --- | --- |
| Adresse / Typ | `module.agent_transport[0].aws_iam_role.dispatch_ingress` / `aws_iam_role` |
| `resource_drift.change.actions` | `update` (Drift-/Refresh-Beschreibung) |
| Geändertes Attribut | `inline_policy` |
| Gleiche Adresse in `resource_changes` | `no-op`; keine Apply-IAM-Aktion |
| AWS API | `list-role-policies` + `get-role-policy` (read-only), Rolle `ris-dev2-dev-agent-dispatch-ingress` |
| Ursache | bestätigte externe Abweichung vom gespeicherten State; Herkunft nicht durch diese Diagnose feststellbar |

Der gespeicherte State/Drift-`before` enthält im Statement `ConsumeDispatchQueue`
keine Work-Queue-Sende-Berechtigung. Der Refresh-`after`, der aktuelle AWS-Wert
und der deklarierte Plan-Sollzustand enthalten zusätzlich:

```text
Sid: SendToWorkQueue
Effect: Allow
Action: sqs:SendMessage
Resource: arn:aws:sqs:eu-central-1:262370457690:ris-dev2-dev-work-queue
Condition: keine
Principal: keines (Identity Policy)
```

Struktureller Vergleich bestätigt eine echte zusätzliche Allow-Berechtigung,
keinen JSON-Formatierungs- oder Reihenfolgeunterschied. Die Resource ist auf
die konkrete Work-Queue begrenzt. Die Deklaration steht in
`terraform/modules/agent_transport/lambda.tf:159-163` und dient dem Dispatch
zur Work-Queue. Das ist eine Berechtigungserweiterung gegenüber State, auch
wenn sie eng auf eine Queue beschränkt ist. Die Live-Policy stimmt mit der
Konfiguration überein; `resource_changes` sieht die Rolle als No-op. CloudTrail
Lookup für `PutRolePolicy`/`DeleteRolePolicy` lieferte in der abgefragten
Event-History-Seite keinen passenden Role-Treffer; damit ist die Herkunft nicht
nachgewiesen.

### 2.2 Analysis-IAM-Rolle

| Feld | Nachweis |
| --- | --- |
| Adresse / Typ | `module.analysis_runtime.aws_iam_role.analysis` / `aws_iam_role` |
| `resource_drift.change.actions` | `update` (Drift-/Refresh-Beschreibung) |
| Geändertes Attribut | `inline_policy` |
| Gleiche Adresse in `resource_changes` | `no-op`; keine Apply-IAM-Aktion |
| AWS API | `list-role-policies` + `get-role-policy` (read-only), Rolle `ris-dev2-dev-analysis` |
| Ursache | bestätigte externe Abweichung vom gespeicherten State; Herkunft nicht durch diese Diagnose feststellbar |

State/Drift-`before` enthält keine Policy `ris-dev2-dev-analysis-runtime-data`.
Refresh-`after`, aktueller AWS-Wert und deklarierter Plan-Sollzustand enthalten
die zusätzliche Inline-Policy:

```text
Statement 1 — Sid OwnedPartnerProfiles
  Effect: Allow
  Action: dynamodb:GetItem, dynamodb:Query
  Resource: PartnerProfiles-Tabelle und alle Indexe (`index/*`)
  Condition: keine

Statement 2 — Sid SyntheticWorkItemReadback
  Effect: Allow
  Action: dynamodb:GetItem
  Resource: WorkItems-Tabelle
  Condition: keine
```

`Principal` ist keines (Identity Policy). Die Policy-Dokumente sind strukturell
verglichen; dies sind echte neue Rechte, keine Formatierungsunterschiede. Der
Soll steht in `terraform/modules/analysis_runtime/main.tf:216-240`.

Die Resource-ARNs sind konkret, aber die Sids erzwingen keine Subject- oder
Synthetic-Only-Grenze. Insbesondere erlaubt `GetItem` auf der WorkItems-Tabelle
den Zugriff auf beliebige Schlüssel dieser Tabelle; `GetItem`/`Query` auf
PartnerProfiles und `index/*` sind nicht durch `Condition`/`LeadingKeys`
begrenzt. Anwendungskontrollen können zusätzliche Schutzwirkung haben, ändern
aber den Umfang der IAM-Grants nicht. Das ist eine sicherheitsrelevante
Berechtigungserweiterung gegenüber dem gespeicherten State und keine
sicherheitsneutrale Drift. Die Live-Policy stimmt mit dem deklarierten
Sollzustand überein; die Rolle ist in `resource_changes` No-op. CloudTrail
Lookup ergab keinen passenden Treffer in der abgefragten Event-History-Seite;
die Herkunft bleibt ungeklärt.

### 2.3 Analysis-Lambda `layers`

| Feld | Nachweis |
| --- | --- |
| Adresse / Typ | `module.analysis_runtime.aws_lambda_function.analysis[0]` / `aws_lambda_function` |
| `resource_drift.change.actions` | `update` in der Drift-Darstellung |
| Geändertes Attribut | `layers` (`null` ↔ `[]`) |
| Gleiche Adresse in `resource_changes` | `update`, aber ausschließlich `source_code_hash` und berechnetes `last_modified` |
| AWS API | `lambda:GetFunctionConfiguration` (read-only): keine `Layers` zurückgegeben (`null`) |
| Ursache | Provider-/State-Normalisierung einer leeren Layer-Liste |

Der AWS-Read, gespeicherter State/Plan-Refresh und deklarierter Sollzustand
zeigen keine angehängte Layer. Es entsteht weder eine Layer-Änderung noch eine
Berechtigungsänderung.

## 3. Wirkung auf den gesperrten Plan

- `resource_changes`: **265 No-op / 7 Update / 0 Create / 0 Delete / 0 Replace**.
- Die sieben Updates sind ausschließlich Lambda-Funktionen; Attribute jeweils
  `source_code_hash` und berechnetes `last_modified`.
- Beide IAM-Rollen stehen als `no-op` in `resource_changes`. Der Apply würde
  nach diesem gespeicherten Plan keine IAM-Policy aktualisieren; die im
  Refresh beobachteten Live-Policy-Werte entsprechen dem deklarierten Soll.
- Das schließt die Erweiterungen nicht aus der Freigabeentscheidung aus: Sie
  sind bereits live und wurden nicht anhand einer nachgewiesenen separaten
  Autorisierung freigegeben. Die zwei IAM-Rollen sind Laufzeitrollen der
  geänderten `dispatch_ingress`- bzw. `analysis`-Lambda-Funktion. Die Rechte
  unterstützen deren Work-Queue-/Analysis-Datenpfade und sind damit funktional
  mit zwei der sieben Code-Updates verbunden.
- Kein Diff an Environment, Cognito, CloudFront, DNS, DynamoDB-Ressourcen,
  SQS-Ressourcen, Secrets oder Event-Source-Mappings im gespeicherten Plan.

**Vertrags-/Freigabebewertung:** Der gespeicherte Plan selbst weitet IAM nicht
aus. Der aktuelle AWS-Sicherheitszustand weicht jedoch in zwei Rollen vom
serialisierten State ab; die Abweichungen sind Allow-Erweiterungen mit
ressourcenweiter DynamoDB-Reichweite und nicht belegter Herkunft. Das erfüllt
nicht die Anforderung „alle Drift-Einträge sicherheitsneutral und vereinbar“.

## 4. Entscheidung und nächste Optionen

**B — BLOCKED.** Den gespeicherten Plan nicht anwenden und die alte Freigabe
nicht wiederaufnehmen.

Vor jeder neuen AWS-Mutation:

1. Autorisierte Herkunft der beiden IAM-Änderungen über vollständige,
   zugängliche CloudTrail-/Audit-Evidence oder Change Records belegen.
2. Datenzugriff der Analysis-Lambda explizit fachlich genehmigen und prüfen,
   ob `dynamodb:LeadingKeys`-/Subject-Grenzen erforderlich sind; die Sids
   allein stellen diese Grenzen nicht her.
3. Dispatch-Queue-Senderecht und Zielressource gegen den freigegebenen
   Transportvertrag bestätigen.
4. Danach eine neue, ausdrücklich geprüfte Release-Entscheidung treffen.
   Eine erforderliche Policy-Korrektur oder State-Neubaseline benötigt ihren
   eigenen Scope, Plan und menschliche Freigabe. Hier wurden keine Korrektur,
   State-Operation oder Ersatzplan ausgeführt.

## 5. Nicht ausgeführt

Kein Terraform-Apply (auch kein `-refresh-only`), kein neuer Plan, kein AWS-
Deployment, kein IAM-Update, kein Import/State-Write, kein Main-Merge und keine
Wiederaufnahme der vorherigen Apply-Freigabe. Der alte Plan bleibt gesperrt.
