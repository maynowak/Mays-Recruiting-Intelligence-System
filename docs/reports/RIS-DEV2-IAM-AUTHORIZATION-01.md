# RIS-DEV2-IAM-AUTHORIZATION-01

**Datum:** 2026-11-25  
**Repository:** `maynowak/Mays-Recruiting-Intelligence-System`  
**Branch / Baseline:** `feature/ris-analysis-integration-07` / `348055cea3d654e19b1bb8172ad050ec2eab3a5c`  
**Modus:** strictly read-only — kein Apply, kein State-Write, keine IAM-Änderung, kein Ersatzplan  
**Plan (weiter gesperrt):** `C:\tmp\ris-dev2-correlation-fix.tfplan`  
**SHA-256:** `2bbf81424b9761712008ef698f5afe5bb6b5ac1db0eaa74220427e8f09b7facd`

## Ergebnis

| Berechtigung | Rolle | Umfang | Bewertung |
| --- | --- | --- | --- |
| `SendToWorkQueue` | `ris-dev2-dev-agent-dispatch-ingress` | `sqs:SendMessage` auf `ris-dev2-dev-work-queue` | **AUTHORIZED / EVIDENCED** |
| `OwnedPartnerProfiles` | `ris-dev2-dev-analysis` | `dynamodb:GetItem`, `dynamodb:Query` auf `ris-dev2-dev-partner-profiles` + `index/*` | **REMEDIATION REQUIRED** (Query/Index ohne Runtime-Bedarf) |
| `SyntheticWorkItemReadback` | `ris-dev2-dev-analysis` | `dynamodb:GetItem` auf `ris-dev2-dev-work-items` | **REQUIRES HUMAN SECURITY ACCEPTANCE** |

Die Herkunft **beider** Grants ist AWS-seitig belegt: sie wurden mit dem am
2026-11-22 freigegebenen 16C2-Plan (`73934457…`) durch Terraform angewendet.
Damit ist die Drift aus `RIS-DEV2-DRIFT-FORENSICS-01` technisch erklärt. Das
ersetzt keine Least-Privilege-Freigabe: eine Berechtigung ist breiter als der
tatsächliche Codebedarf, eine weitere ist minimal, aber nur auf Anwendungsebene
eingegrenzt. **Der Plan bleibt gesperrt.**

## 1. Methode und Abgrenzung

Ausschließlich lesende Quellen:

- Git-Historie und Diffs der genannten Commits;
- Code-Pfade des analysis- und dispatch-Runtime;
- fokussierte Tests, Reports, Manifeste und Auditlog;
- AWS CloudTrail (`lookup-events`, vollständige Pagination) und Trail-Konfiguration;
- S3-Objekte der beiden Trails inkl. `validate-logs`;
- Live-IAM-Policies (`list-role-policies`, `get-role-policy`).

Keine Mutation, kein Apply, kein `import`/`state`-Kommando, kein Main-Merge.
Quell-IP und Identity-Details der aufrufenden Person werden nicht wiedergegeben.

## 2. Quellhistorie

| Commit | Datum | Fachlicher Inhalt | IAM-Delta |
| --- | --- | --- | --- |
| `89929c5` | 2026-11-20 18:45 +01:00 | Dediziertes Analysis-Compute, eigener Runner, gated Lambda, eigene Daten-Policy | Analysis-Rolle + Daten-Policy: WorkItems RW, Entitlements read, PartnerProfiles read |
| `f639611` | 2026-11-21 13:32 +01:00 | Dispatch persistiert WorkItem und enqueued in die bestehende Work-Queue; Worker-Claim; terminales `ORDER_FAILED` | Dispatch-Rolle: **+ `SendToWorkQueue`**; Analysis-Policy **reduziert** auf PartnerProfiles read (WorkItems-Write und Entitlements entfernt) |
| `c5fef5d` | 2026-11-21 17:45 +01:00 | Synthetic-Mode an persistiertes, vertrauenswürdiges WorkItem gebunden | Analysis-Policy: **+ `SyntheticWorkItemReadback`** (WorkItems `GetItem`) |

Netto existieren heute genau die zwei geprüften Blöcke. Die Reduktion in
`f639611` ist belegt: `tests/test_analysis_runtime_terraform.py` verbietet
`dynamodb:PutItem`/`UpdateItem` und den Entitlements-ARN im Daten-Policy-Block.

### Getrennte Bewertung der Nachweise

| Dimension | `SendToWorkQueue` | Analysis-Policy |
| --- | --- | --- |
| Git-Commit | ja (`f639611`) | ja (`89929c5`, `f639611`, `c5fef5d`) |
| Code-Review | **nicht belegt** — kein PR, keine unabhängige Review-Spur; Commit-Autor ist die lokale Arbeitsidentität | **nicht belegt** — gleiche Lage |
| Deployment-Ausführung | **belegt** (Apply-Log, Manifest, CloudTrail) | **belegt** (dito) |
| Menschliche AWS-Freigabe | Referenz `RIS-ANALYSIS-16C2-A-2026-11-22`, an den exakten Plan-Hash gebunden, im Apply-Log protokolliert; **kein namentlicher Approver/Sign-off dokumentiert** | dito |

Der Apply-Log enthält:

```text
Saved-plan apply: approval=RIS-ANALYSIS-16C2-A-2026-11-22
sha256=7393445789d92bdb15ebcc9ea3ae85a9e98cb068c27ad84bc6fd982d3ba0f64a
state mirror: pre-apply snapshot serial=67 ...
$ terraform apply ...plan-final.out -> exit 0
```

Damit sind Ausführung und Planbindung belegt; die **Freigabe** ist als
Gate-Referenz dokumentiert, aber nicht personell attribuiert. Diese Lücke wird
nicht durch Annahmen geschlossen.

## 3. AWS-Herkunft

### Trail-Konfiguration

- `ris-dev2-trail` und `ris-agent-trail`: beide Multi-Region, Home
  `eu-central-1`, Log-File-Validation aktiv, jeweils eigenes S3-Ziel.
- Kein CloudTrail Lake / Event Data Store, keine CloudWatch-Logs-Zustellung.
- Event-History-Aufbewahrung: 90 Tage; die relevanten Ereignisse liegen darin.
- Archivierte Objekte beider Trails vorhanden und geprüft.

### Ereignisse (Fenster 2026-11-15 bis 2026-11-26, paginiert)

Neun `PutRolePolicy`-Ereignisse auf den beiden Rollen; **keine**
`DeleteRolePolicy`-, `AttachRolePolicy`- oder `DetachRolePolicy`-Ereignisse.
Die beiden entscheidenden Ereignisse:

| Zeit (UTC) | Ereignis | Rolle | Policy | Identität | Fehler | Event-ID |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-22T11:52:25Z | `PutRolePolicy` | `ris-dev2-dev-agent-dispatch-ingress` | `…-dispatch-ingress-policy` | IAM-User `devnemo` | keiner | `1d19db04-dba3-45d7-9d32-7163fcf0f363` |
| 2026-11-22T11:52:25Z | `PutRolePolicy` | `ris-dev2-dev-analysis` | `…-analysis-runtime-data` | IAM-User `devnemo` | keiner | `af46114a-56f0-4f22-a8e3-31e75373e125` |

Beide Ereignisse tragen den User-Agent des Terraform-AWS-Providers
(`Terraform/1.17.0`, `terraform-provider-aws/6.73.0`) und erscheinen
inhaltlich identisch in beiden Trail-Buckets. Die im Ereignis gespeicherten
Policy-Dokumente enthalten exakt die heute live sichtbaren Statements
(`SendToWorkQueue` bzw. `OwnedPartnerProfiles` + `SyntheticWorkItemReadback`).

### Korrelation mit dem Apply

| Zeitpunkt | Nachweis |
| --- | --- |
| 11:52:19Z | `state mirror: pre-apply snapshot serial=67` |
| 11:52:25Z | beide `PutRolePolicy` |
| 11:52:54Z | `terraform apply … -> exit 0` |
| 11:52:56Z | State-Objekt serial 69 geschrieben |

Die Ereignisse liegen damit im Apply-Fenster des freigegebenen 16C2-Plans; die
Policy-Inhalte stimmen mit dem dort dokumentierten Soll überein. Frühere
Ereignisse (18.11., 20.11.) betreffen ältere Fassungen derselben Rollen und
enthalten die beiden gegenständlichen Grants nicht.

### Integrität und Nachweislücken

- `validate-logs` 2026-11-22 11:00–13:00Z: `ris-dev2-trail` 3/3 Digests und
  26/26 Logdateien gültig; `ris-agent-trail` 3/3 und 27/27 gültig.
- **Keine Nachweislücke** für Ausführung, Zeitpunkt, Ziel und Policy-Inhalt.
- **Nachweislücke:** kein namentlicher menschlicher Approver, kein
  unabhängiger Code-Review, kein CI-/PR-Nachweis für diese Commits.
- **Beobachtung:** der Apply lief laut User-Agent mit Provider `6.73.0`; der
  aktuelle Lockfile pinnt `6.67.0`. Das ist Toolchain-Drift, keine
  Berechtigungsänderung, aber für Reproduzierbarkeit relevant.

## 4. Least-Privilege-Review

### 4.1 `SendToWorkQueue`

**Runtime-Operation:** `agents/runtime/work_queue.py::enqueue_work_item`
persistiert das WorkItem und ruft `sqs_client.send_message(QueueUrl=…)` mit
der Queue aus `WORK_QUEUE_URL` auf. `lambda/dispatch_ingress.py` nutzt genau
diesen Pfad; ein alternativer Queue-Zielpfad existiert nicht.

| Prüfung | Ergebnis |
| --- | --- |
| Benötigte Aktion | ausschließlich `sqs:SendMessage` |
| Ziel | ausschließlich `ris-dev2-dev-work-queue` (exakter ARN) |
| Weitere SQS-Rechte | keine (Empfang/Delete nur auf der Dispatch-Queue, unverändert) |
| Tests | `tests/test_work_queue.py` (Persist→Enqueue, Redelivery, terminaler Duplicate, Send-Fehler, Fail-closed) sowie Dispatch-Ingress-Tests |
| Zweck belegt | ja, Commit + Report + Manifest |
| Umfang minimal | ja |

**Bewertung: AUTHORIZED / EVIDENCED.** Die Berechtigung ist auf die eine
vorgesehene Queue begrenzt und deckt genau die eine Runtime-Operation ab.
Vorbehalt: personelle Freigabe und Review sind nicht dokumentiert (siehe §2).

### 4.2 `OwnedPartnerProfiles`

**Runtime-Operation:** `agents/analysis/cv_bridge.py::_resolve_stored` ruft
`PartnerProfileRepository.get(cv_id, user, tenant, partner_application_id,
issuer)` auf; `jobsearch/partner_profile_repository.py::get` verwendet
`table.get_item(Key={"resourceId": …}, ConsistentRead=True)`.

| Prüfung | Ergebnis |
| --- | --- |
| Tatsächlich gelesen | ein CV- bzw. Profil-Datensatz über `get_item` (Basis-Tabelle, Partitionsschlüssel `resourceId`) |
| Schlüsselherkunft | `cvId` aus dem Request; `userId`, `tenantId`, `partnerApplicationId`, `issuer` aus der verifizierten Identität |
| Owner-/Tenant-Isolation | **Anwendungsebene**: `_identity_ok` vergleicht gespeicherte `userId`/`tenantId` und – falls gesetzt – `partnerApplicationId`/`issuer`; Mismatch → `None` → `cv_not_found` |
| `Query` + `index/*` | **im Analysis-Runtime nicht verwendet** — `list_by_user`/`list_by_parent` werden nur von Jobsearch-Agent und Privacy-Erasure aufgerufen, nicht von diesem Lambda |
| IAM-Conditions | `dynamodb:LeadingKeys` gilt nicht für `GetItem`; `dynamodb:Attributes` begrenzt Attribute, nicht Items. Eine itemgenaue IAM-Grenze für `GetItem` ist nicht ausdrückbar |
| Tabellen-/Index-Notwendigkeit | Basis-Tabelle `GetItem`: ja. `Query`/`index/*`: nein, kein belegter Bedarf im Analysis-Pfad |

**Bewertung: REMEDIATION REQUIRED.** Der `GetItem`-Anteil ist durch Zweck,
Code, Tests und AWS-Ausführung belegt. `dynamodb:Query` auf der Tabelle und
`index/*` sind breiter als der tatsächliche Runtime-Bedarf und sollten entfernt
werden, sofern kein konkretes, dokumentiertes Analysis-Szenario sie benötigt.
Bis dahin ist die Berechtigung nicht least-privilege.

### 4.3 `SyntheticWorkItemReadback`

**Runtime-Operation:** `lambda/analysis_runner.py::_build_synthetic_verifier`
liest mit `table.get_item(Key={"workId": …}, ConsistentRead=True)` genau einen
WorkItem und akzeptiert die synthetische Identität nur, wenn `status=RUNNING`
und `tenantId`, `userId`, `partnerApplicationId`, `issuer` exakt dem
konfigurierten Testprofil entsprechen.

| Prüfung | Ergebnis |
| --- | --- |
| Aktion | ausschließlich `dynamodb:GetItem` (kein Write, kein Query) |
| Ziel | `ris-dev2-dev-work-items`, Basis-Tabelle |
| Schlüsselherkunft | `workId` aus dem Event; Identitätsfelder werden gegen die **persistierte** Zeile geprüft, nicht aus dem Payload übernommen |
| Aktivierungszustand | synthetischer Modus ist derzeit `false`; der Pfad ist ruhend |
| IAM-Conditions | keine itemgenaue Einschränkung möglich (`LeadingKeys` nicht für `GetItem`); der SID benennt nur den Zweck, keine Grenze |
| Isolation | ausschließlich Anwendungsebene (exakter Feldvergleich); die IAM-Berechtigung erlaubt `GetItem` auf **jeden** `workId`-Schlüssel der Tabelle |

**Bewertung: REQUIRES HUMAN SECURITY ACCEPTANCE.** Die Berechtigung ist
minimal (nur `GetItem`, nur eine Tabelle) und der Zweck ist belegt. Sie ist
aber nicht durch IAM auf synthetische Zeilen begrenzbar; die Grenze entsteht
erst im Code. Ob diese Restrisiko-Akzeptanz getragen wird, ist eine menschliche
Sicherheitsentscheidung und wird hier nicht vorweggenommen.

### 4.4 Beobachtung ohne Berechtigungswirkung

Die Analysis-Lambda hat `ENTITLEMENTS_TABLE` gesetzt, aber seit `f639611`
keine Entitlements-IAM-Rechte mehr. Der `DynamoDBEntitlementResolver` würde
beim Query scheitern und fail-closed in `DEAD_LETTER` laufen. Das ist **keine**
Berechtigungsausweitung, sondern eine funktionale Lücke im deny-by-default-
Zustand und gehört in ein separates Funktionsgate.

## 5. Exakter Berechtigungsumfang zur Entscheidung

```text
Rolle: ris-dev2-dev-agent-dispatch-ingress
  Allow sqs:SendMessage
    Resource: arn:aws:sqs:eu-central-1:262370457690:ris-dev2-dev-work-queue
    Condition: keine
    Status: erforderlich, belegt, minimal

Rolle: ris-dev2-dev-analysis  (Policy ris-dev2-dev-analysis-runtime-data)
  Allow dynamodb:GetItem, dynamodb:Query
    Resource: arn:aws:dynamodb:eu-central-1:262370457690:table/ris-dev2-dev-partner-profiles
              arn:aws:dynamodb:eu-central-1:262370457690:table/ris-dev2-dev-partner-profiles/index/*
    Condition: keine
    Status: GetItem erforderlich; Query/Index nicht belegt → Remediation

  Allow dynamodb:GetItem
    Resource: arn:aws:dynamodb:eu-central-1:262370457690:table/ris-dev2-dev-work-items
    Condition: keine
    Status: minimal, aber itemgenau nicht per IAM begrenzbar → Acceptance nötig
```

## 6. Entscheidung

1. **`SendToWorkQueue`:** AUTHORIZED / EVIDENCED. Keine Änderung nötig.
2. **`OwnedPartnerProfiles`:** REMEDIATION REQUIRED. `Query` und `index/*`
   entfernen oder einen konkreten Analysis-Bedarf nachweisen; danach neuer
   Plan und neue Freigabe. Alternativ ausdrückliche Risikoakzeptanz für den
   breiteren Umfang.
3. **`SyntheticWorkItemReadback`:** REQUIRES HUMAN SECURITY ACCEPTANCE.
   Minimal, ruhend, aber IAM-seitig nicht auf synthetische Zeilen begrenzbar.
   Entscheidung über die verbleibende Tabellenweite erforderlich.

**Der Plan `2bbf8142…` bleibt bis zu einer neuen ausdrücklichen Freigabe
gesperrt.** Es wurde keine Berechtigung eigenmächtig genehmigt, entfernt oder
geändert.

## 7. Nicht ausgeführt

Kein Terraform-Apply, kein `-refresh-only`-Apply, kein State-Write, kein
`import`/`state mv`/`state rm`/`state push`, kein Ersatzplan, kein IAM-Update,
kein Deployment, kein Main-Merge. Die vorherige Apply-Freigabe wird nicht
automatisch wiederaufgenommen.
