# RIS-DEV2-OPERATOR-AUTHORIZATION-20

## Ergebnis

**BLOCKED before local authorization-file creation.**

Die erforderliche Out-of-band-Genehmigung für einen synthetischen DEV2-Tenant
liegt nicht vor. Deshalb wurden keine Datei, keine Signatur und keine
Provisionierungsressource erstellt.

## Read-only evidence

| Prüfung | Ergebnis |
|---|---|
| AWS account | `262370457690` |
| AWS region | `eu-central-1` |
| STS principal | `arn:aws:iam::262370457690:user/devnemo` |
| `RIS_ADMIN_AUTHORIZATION_FILE` | nicht gesetzt |
| dokumentierter lokaler Kandidatenpfad | nicht vorhanden |
| genehmigte synthetische `tenantId` | nicht vorgelegt |
| AWS/Cognito/Terraform/Registry/Credential | unverändert |

Die vorhandene Implementierung in
`tools/ris_admin/credentials.py:64-122` bleibt unverändert maßgeblich:
exakte STS-Principal-Bindung, Rolle, verpflichtender Tenant-Scope und
owner-only lokale Datei. AWS-IAM-Berechtigungen allein ersetzen diese
RIS-Genehmigung nicht.

## Konkrete fehlende Betreiberaktion

Die berechtigte RIS-Betreiberin muss über das bestehende Out-of-band-Verfahren
eine kurzlebige Genehmigung für genau diesen Scope erteilen und den genehmigten
Tenant mitteilen:

```text
Account:     262370457690
Region:      eu-central-1
Umgebung:    ris-dev2
Principal:   arn:aws:iam::262370457690:user/devnemo
Scope:       ein temporärer synthetischer Partner, ein APIProfile,
             ein Test-Credential, Metrics/ApplicationV1-E2E, Revocation/Cleanup
Tenant:      <von der Betreiberin zu genehmigen>
Expiry:      <von der Betreiberin festzulegen>
```

Erst danach darf die genehmigte owner-only JSON-Datei lokal außerhalb des
Repositories bereitgestellt, geprüft und als `RIS_ADMIN_AUTHORIZATION_FILE`
gesetzt werden. Bis dahin bleiben Phase 17/19D und Gate B blockiert.

Keine Provisionierung, kein Credential, keine Testidentität und kein CLI-Dry-Run
mit einer behaupteten Autorisierung wurden ausgeführt.
