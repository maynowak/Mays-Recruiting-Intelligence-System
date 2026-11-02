# RIS-DEV2-DEPLOY-01 — Hands-on / Betrieb und Wiederholung

**Stand:** 2026-11-02  
**Charakter:** Reproduzierbares Vorgehen und Prüfliste auf Grundlage des erfolgreich gemeldeten Deployments. **Nicht blind erneut ausführen:** `ris-dev2` ist bereits provisioniert. Ein neuer Plan kann andere Aktionen erzeugen.

## 1. Ausgangspunkt und Sicherheitsgrenzen

- AWS Account: `262370457690`; Region: `eu-central-1`; Profil: `default`.
- Terraform-Workspace: `ris-dev2`; aktueller State nach Apply laut Bericht Serial `23`, Lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`.
- Bestehende Cognito-/OAuth-/Jobsearch-CloudFront-/DNS-/ACM-Ressourcen **nicht verändern**.
- `identity_mode=external`; `orders_lifecycle=disabled` für die dokumentierte Installation.
- Privacy-/Erasure-/Freeze-/Cutover-Ausführungsflags **false**.
- Keine `-target`, `-replace`, Imports, State-Recovery oder ungeprüften Destroy-Aktionen.
- `ris-dev` und andere AWS-Accounts vollständig außerhalb des Scopes.

## 2. Vorbereitende Checks (PowerShell)

```powershell
$env:AWS_PROFILE = 'default'
$env:AWS_DEFAULT_REGION = 'eu-central-1'
aws sts get-caller-identity --profile default
aws configure get region --profile default
terraform version

git branch --show-current
git rev-parse HEAD
git status --short
```

**Gate:** STS muss Account `262370457690` ergeben. Prüfe zusätzlich den erwarteten Principal und das tatsächlich gewählte Terraform-Backend. Keine Ausführung, wenn das Profil, der Workspace oder der State nicht eindeutig dem Projekt zugeordnet ist.

## 3. Build und Validate

Arbeit im **tatsächlichen** lokalen RIS-Checkout. Modul-Builder nur über den bestehenden gepinnten Ablauf ausführen; exakter lokaler Befehl ist aus dem Repository-Runbook abzulesen, nicht aus diesem Bericht zu erfinden.

```powershell
# Im Terraform-Root des RIS-Repositorys:
terraform fmt -check
terraform init -backend=false
terraform validate

# Separate, bekannte Regressionen nach dem Runbook ausführen.
```

**Achtung:** `terraform init -backend=false` ist ausschließlich eine lokale Strukturprüfung. Für Plan/Apply muss die autorisierte Remote-Backend-Konfiguration und der korrekte Workspace bereits sicher ausgewählt sein. Nicht einfach `terraform init -backend=false` als Vorbereitung für ein Remote-Apply missverstehen.

Die ursprünglich untracked 39 Dateien und die vorbestehende Löschung `terraform/modules/mays_orders/variables.tf` sind zu schützen. Fehlendes generiertes Orders-Modul nur durch den vorgesehenen gepinnten Build-Prozess erzeugen.

## 4. Kontrollierter Plan

1. Remote-Backend-Konfiguration, Workspace `ris-dev2`, State-Lineage, Account und aktuelle Resource-Ownership **read-only** prüfen.
2. Externe Pool-/Human-/M2M-Client-/Issuer-Referenzen und Flags prüfen.
3. Einen **neuen** gespeicherten Terraform-Plan nur im dafür autorisierten Arbeitsgang erzeugen. Der bei der Erstinstallation benutzte R1-Plan ist nach Apply **verbraucht und darf nicht wieder angewendet werden**.
4. `terraform show -json <gespeicherter-plan>` maschinell auswerten; `resource_changes[*].change.actions` vollständig prüfen.
5. Ändern sich geschützte Cognito-/CloudFront-/DNS-/ACM-/OAuth-Ressourcen, **STOP**. Eine separate Health-CloudFront darf nur dann als Create erscheinen, wenn sie **noch nicht existiert**, exakt dem freigegebenen Scope entspricht und speziell genehmigt wurde.
6. Gesamtdiff, IAM-Änderungen, Risiken, Plan-Hash (SHA-256) und State-Evidence protokollieren.

Prüfbeispiel für eine bereits existierende gespeicherte Plandatei:

```powershell
Get-FileHash -Algorithm SHA256 -Path '<absolute-path-to-current-plan>'
terraform show -json '<absolute-path-to-current-plan>' | Out-File -Encoding utf8 '<absolute-path-to-plan-json>'
```

**Keine allgemeine CloudFront-Ausnahme.** Die zwei bei der Erstinstallation erlaubten Adressen waren:

- `module.health_public.aws_cloudfront_distribution.health_public`
- `module.health_public.aws_cloudfront_origin_access_control.health_public`

Bei einem späteren No-op- oder Upgrade-Plan sind diese Ressourcen **bereits vorhanden und geschützt**; ihre Änderung oder Ersetzung ist nicht automatisch erlaubt.

## 5. Apply nur mit neuer konkreter Planfreigabe

Vor Apply Account, Workspace, State-Lineage und SHA-256 erneut abgleichen. Nur nach ausdrücklicher Freigabe für den **aktuellen** gespeicherten Plan:

```powershell
terraform apply '<absolute-path-to-approved-current-plan>'
```

**STOP** bei Abweichung, unerwarteten Aktionen oder Fehlern. Keine automatische Wiederholung und kein `destroy` zur Fehlerbereinigung.

**Erstinstallations-Evidence (nicht wiederverwenden):**

- R1-Pfad: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-foundation-r1.tfplan`
- R1-SHA-256: `FC30B406F16DB860203539D079730B8B9A27A4A359505B8430AAF0A9F40F431D`
- Plan: 153 Create, 0 Update/Delete/Replace, 3 Read.
- Apply: 153 added, 0 changed, 0 destroyed.

## 6. Verify nach jedem zukünftigen Apply

```powershell
aws sts get-caller-identity --profile default
aws lambda list-functions --region eu-central-1 --profile default
# Für HTTP-Checks nur bekannte, autorisierte Endpunkte verwenden.
```

Zielprüfungen:

| Prüfung | Soll / Vorgehen |
|---|---|
| Health | HTTP 200 am dokumentierten öffentlichen Health-Endpunkt |
| API ohne JWT | HTTP 401 für geschützten `/health`-Pfad |
| Authenticated Human/M2M | Nur freigegebene Test-Tokens/Accounts; Issuer, Audience und Berechtigungen prüfen |
| Lambda | Active; erfolgreicher Update-Status |
| State | Erwartete Workspace-/Lineage-Konstanz; geplante Änderungen im State |
| Cognito | Pool-ID, Client-IDs, Konfiguration und Benutzerbestand unverändert |
| CloudFront | Bestehende Auth-Distribution unverändert; Health-Distribution-ID `E1IZKHFPZ5X7SN` erhalten |
| DNS/ACM | Bestehende Alias-/TLS-Zuordnung unverändert |
| Privacy/Erasure | Alle Ausführungsflags `false` |
| Monitoring | Logs, Alarme und Fehler prüfen |

Wenn vor/nach dem Apply ein Vergleich nicht belastbar möglich ist, `UNKNOWN` berichten, nicht `UNCHANGED` behaupten.

## 7. Clean und Git

- Nur eindeutig von **diesem Lauf** erzeugte, entbehrliche temporäre Dateien entfernen; vorab klassifizieren.
- Keine AWS-Ressourcen, Terraform-States, State-Historie oder fremde Worktree-Dateien löschen.
- Keine `git clean`, kein `reset --hard`, kein pauschaler Ordner-Cleanup.
- Fertige Reports und beabsichtigte Codeänderungen separat sauber committen; kein Push ohne Auftrag.

## 8. Operatives Ergebnis vom 2026-11-02

| Check | Resultat laut Abschlussmeldung |
|---|---|
| Apply | PASS, 153 added / 0 changed / 0 destroyed |
| API | `https://8apxb6fgne.execute-api.eu-central-1.amazonaws.com` |
| Lambda | Active, Python 3.14 |
| Health CloudFront | `E1IZKHFPZ5X7SN` |
| Health | HTTP 200 |
| API ohne JWT | HTTP 401, erwartet |
| Issuer / Audiences | Human und M2M konfigurationsseitig verifiziert |
| Cognito / DNS / ACM | Unverändert laut Ausführungsreport |
| Git | `35800ed0dec86fb0c2c05835ecf1e184436bf596` |

## 9. Der nächste praktische Nachweis

**No-op-Plan:** Für die bereits installierte Foundation einen neuen Plan erstellen, ein vollständiges No-op prüfen und die geschützten Ressourcen unverändert bestätigen. Falls der Plan unerwartete Änderungen enthält, Ursachen behandeln statt Apply.

**In-Place-Upgrade-Test:** Anschließend eine bewusst begrenzte RIS-Backend-Änderung implementieren; erneutes Validate → Plan → Schutzprüfung → Freigabe → Apply → Verify → Clean. Erst dieses Ergebnis belegt die gewünschte Upgrade-Stabilität von bestehendem Cognito, CloudFront und DNS.

## 10. Referenz

`docs/reports/RIS-DEV2-DEPLOY-01-EXECUTION.md` (Abschluss-Commit `35800ed0dec86fb0c2c05835ecf1e184436bf596`). Dieses Hands-on beschreibt das gemeldete Deployment und schreibt keine erneute Ausführung vor.
