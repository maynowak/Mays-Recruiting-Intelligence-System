# Schritt 4+5 – Befund-Fixes und vollständiger `terraform destroy` (2026-10-19)

**Datum:** 2026-10-19
**Status:** COMPLETED (GREEN)
**Umgebung:** Account `240571105849`, Region `eu-central-1`, Profil `AWS_PROFILE=mayaws`
**Ausführung:** direkt aus `<RIS-Root>/terraform` (kein Installer), State `s3://mays-ris-tf-state-dev/terraform.tfstate`

## 1. Befund-Fixes (Volltest-Report §7)

| §7 | Aktion | Ergebnis |
|---|---|---|
| 7.1 Doku-Widerspruch | `AGENTS.md` Z.49 korrigiert: `/health` ist **nicht** unauthentifiziert, sondern JWT-geschützt (401 ohne Token), verifiziert live und gemäß `docs/api/API-STANDARD.md` Z.62 | PASS |
| 7.2 Log-Groups | `/aws/lambda/mays-orders-cognito-backup-lambda`, `/aws/lambda/mays-ris-parallel-b-test-health-publisher` gelöscht | PASS |
| 7.2 Verwaister ESM | `6deb8bf4-…` (Queue `mays-orders-orders-queue` existierte nicht mehr) → `delete-event-source-mapping`, Zustand `Deleting`→gelöscht | PASS |
| 7.2 Bucket `mays-orders-ci-artifacts-dev` | ~300 CI-Artefakte (source/plan/deploy/validate_out) geleert, Bucket gelöscht | PASS |
| 7.2 Bucket `mays-ris-parallel-b-tf-state-test` | versioniert: 13 Versionen/DeleteMarker gepurgt, Bucket gelöscht | PASS |
| 7.3/7.4 | waren bereits GRÜN (Lock-Tabelle bootstrap, Zähler-Korrektur) – keine Aktion nötig | PASS |

## 2. Destroy – Durchlauf 1 (Exit 1, BucketNotEmpty)

```
terraform destroy -auto-approve (mit denselben -var-Werten, echter S3-State, Lock aktiv)
→ 165/167 zerstört; 2 Fehler:
   - BucketNotEmpty: mays-ris-dev-health-public   (Health-Publisher schreibt laufend Objekte)
   - BucketNotEmpty: mays-ris-cloudtrail-240571105849 (Trail-Logs)
```

**Bewertung:** Kein Defekt — Race zwischen Destroy und laufenden Writes
(Health-Publisher, CloudTrail-Delivery). Bekanntes S3-Muster; Lösung: leeren, erneut destroy.

## 3. Destroy – Durchlauf 2 (Exit 0)

Bucket-Inhalte inkl. Versionen/DeleteMarker geleert (1 bzw. 14 Objekte), dann:

```
terraform destroy -auto-approve
→ Destroy complete! Resources: 2 destroyed.   (Exit 0)
```

## 4. Post-Destroy-Verifikation (Live, AWS CLI)

| Prüfung | Ist | Ergebnis |
|---|---|---|
| DynamoDB | nur `mays-ris-tf-lock` (Backend) | PASS |
| Lambda | keine | PASS |
| API Gateway | keine | PASS |
| SQS | keine | PASS |
| S3 (mays-ris-*) | nur `mays-ris-tf-state-dev` (Backend) | PASS |
| Cognito Pools | keine | PASS |
| Dashboards / Alarme / ESM | 0 / 0 / 0 | PASS |
| State-Objekt in S3 | Serial 13, `resources: 0` | PASS |

**Fazit:** 167/167 Ressourcen zerstört, Konto vollständig aufgeräumt. Verblieben
bewusst: **nur Backend-Infrastruktur** (State-Bucket `mays-ris-tf-state-dev` +
Lock-Tabelle `mays-ris-tf-lock`) — Voraussetzung für künftige Applys.

**Lehre für künftige Destroy-Runs:** Bucket mit laufenden Writern
(Health-State, CloudTrail) vor dem Destroy leeren oder Destroy einfach
zweimal ausführen (Exit 1 + BucketNotEmpty ist dann kein Fehler).
