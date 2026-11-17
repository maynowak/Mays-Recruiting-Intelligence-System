# RIS-ATS-PRODUCT-READINESS-07

**Status:** Preflight und Release-Reconciliation abgeschlossen. **Kein AWS
Apply, Secret-Write, Benutzeranlage, Deployment, Merge oder Push.**
**Datum:** 2026-11-17
**RIS-Baseline:** `feature/ris-dev2-ats-agent-pinned-core-01` @ `0a5c4a5`
**Orders-Pin:** `016cdfd6ac62565dcec9a2fee78cb898fb919e59`

## 1. Plan und Ressourcenvergleich

| Prüfung | Wert |
|---|---|
| STS | `arn:aws:iam::262370457690:user/devnemo` |
| Workspace | `ris-dev2` |
| Backend / Key | `ris-dev2-tf-state-dev` / `env:/ris-dev2/dev/terraform.tfstate` |
| Lock | `ris-dev2-tf-lock`, nur MD5-Digests, keine aktive Lock |
| Lineage / Serial | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` / **58** |
| Pin / Clone / Manifest | `016cdfd` / clean / `source.commit=016cdfd`, Zip `48ddd5e5…`, 23 Outputs |
| Bundles | Agent `5258c99e…`, Reader `55366e35…` (zweiter Build identisch) |
| **Plan-SHA-256** | **`E11732AD9F31C1874E43231DA43987A2E7F1D607ADE41A571D91DB0F922AC70D`** |
| Aktionen | **24 add / 4 change / 0 destroy / 0 replace** |

**24 Adds:** 13 aus dem bisherigen Transportplan (Catalog-Seed `ats-agent`,
2 Worker-IAM-Policies, 10 Orders-Result-Ressourcen) + 10 RIS-Dispatch-
Ressourcen (Queue, DLQ, Queue-Policy, Ingress-Log-Group/Rolle/Policy,
Result-Send-/Secret-Policy, Ingress-Lambda, ESM) + 1 Reader-IAM-Policy.

**4 Changes:** RIS-Agent (Bundle/Env), RIS-Reader (Bundle/Env), Orders-HTTP-
Handler und Orders-SQS-Worker (jeweils nur `source_code_hash`).

Keine Cognito-, CloudFront-, Route53/DNS-, ACM- oder S3-Änderung; kein
`secret_version`; State/ETag unverändert.

## 2. Lokale Korrekturen aus dem Preflight

1. **Dispatch-Ingress-Entitlement-IAM:** `Query` deckt jetzt auch
   `${entitlements_table_arn}/index/*` ab. Ohne diese Korrektur würde der
   erste Canary am `gsi-user`-Query mit `AccessDenied` scheitern und in die
   Dispatch-DLQ laufen.
2. **ATS-Endpunkt explizit:** `ats_api_base_url` ist eine nicht-leere
   HTTPS-Variable (Default `https://mays-jobsearch.vercel.app`) und wird an
   Worker **und** Dispatch-Ingress als `ATS_API_BASE_URL` übergeben. Ein
   leerer Wert ist per Validierung ausgeschlossen (der Agent würde sonst
   relative URLs aufrufen).

## 3. Aktivierungsverfahren (jeweils separate Freigabe)

1. **Infrastruktur-Apply** nach separater Plan-/Apply-Freigabe:
   `orders_agent_result_enabled=true` und `enable_agent_transport=true` nur
   über den freigegebenen Plan-Input. `enable_agent_transport` ist kein
   erlaubter Overlay-Key; Defaults sind bewusst `false`.
2. **HMAC-Secret** nach separater Freigabe, im selben Betriebsfenster:
   Container existiert nach dem Apply ohne Version; 32 Byte CSPRNG → 64
   lowercase Hex, `put-secret-value --secret-string file://…`, Datei sofort
   löschen; genau eine `AWSCURRENT`, kein `AWSPENDING`, `keys=1`.
3. **Testidentität/Profil/Entitlement** nach separater Freigabe:
   - RIS-Pool `eu-central-1_OYN9QiHc5`, Client `5jgjivk9k9rrjos62so1qhq8o3`;
     `USER_PASSWORD_AUTH` ist bereits erlaubt (keine Cognito-Konfigänderung).
   - Benutzer `ris-dev2-e2e-<runid>@example.invalid`, keine Gruppen,
     `CONFIRMED`; Passwort nur out-of-band.
   - API-Profil: `apiProfileId`, `status=ACTIVE`, `ownerUserId=<sub>`,
     `tenantId`; Anlage über den bestehenden Admin-Pfad, kein direktes
     DDB-Seeding.
   - Entitlement: `userId=<sub>`, `agentId=ats-agent`, `tenantId`,
     gültiges Zeitfenster, **ohne** `apiProfileId` (user-wide).
4. **Isolierter Canary** nach separater Freigabe: eine synthetische
   Agent-Order über `POST /orders` mit ATS-Target und synthetischem
   Job/Profil; `201`, `dispatch=SENT`.
5. **Verifikation:** Work-Row `COMPLETED` + `orderResultDelivery=SENT` +
   gebundene `workId`; Orders `processing.status=COMPLETED`,
   `processing.result.bodyVersion=2.0`, Score numerisch, Order-`status`
   unverändert; Owner-Read 200, fremder Owner 404, fremder Issuer 401.
6. **Partner-Traffic** erst nach separater Entscheidung und nur, wenn Secret,
   Identität und Canary verifiziert sind.

## 4. Identitäts- und Infrastrukturvoraussetzungen

- Kein Cognito-Pool-/Client-/Domain-/Authorizer-Wechsel nötig.
- Live fehlen: 0 Benutzer, 0 API-Profile; bestehende Entitlements sind
  fremd/abgelaufen.
- Der order-korrelierte Pfad ist die RIS-Fassade (`POST /orders`) plus
  Dispatch; der direkte Partner-Execute-Pfad erzeugt weiterhin WorkItems ohne
  `orderId` und ist nicht Teil dieses Canaries.
- Ergebnis-Queue/Secret und Dispatch-Queue/Ingress entstehen erst mit dem
  Plan; ein Secret-Wert vor dem Apply ist nicht möglich (Container fehlt).

## 5. Verbleibende Betriebsrisiken

1. **ATS nur Produktionshost:** Es existiert kein Non-Prod-Endpunkt im Repo.
   Ein Canary ist nur gegen den verifizierten Vertrags-Host mit synthetischen
   Daten zulässig; ein hermetic Canary ist blockiert.
2. **Timeout-Headroom:** ATS-Client 30 s = Lambda-Timeout 30 s; langsame
   Antworten können die Invocation beenden.
3. **Result-Visibility 60 s** vs. Consumer-Timeout 30 s.
4. **Keine DLQ-Alarme/SNS-Actions** für Dispatch-/Result-Queues; permanente
   Rejects werden nur geloggt.
5. **Kein `ORDER_FAILED`:** fehlgeschlagene/abgelehnte Agenten hinterlassen
   keine Orders-Spur.
6. **Keine Request-Idempotenz** im Reader-POST: ein Retry erzeugt eine neue
   Order und WorkId.
7. **Inline-Ausführung:** Dispatch-Ingress führt die Pipeline im 30-s-Lambda
   aus; Timeout + `RUNNING`-Row kann zu `WORK_ADMISSION_STATE_UNSAFE`/DLQ
   führen.
8. **State-Hijack:** Der Bucket enthält einen leeren Legacy-State
   `env/ris-dev2/dev/terraform.tfstate`; `init` muss exakt
   Bucket/Key/Workspace-Prefix/Lock/Workspace treffen.
9. **Secret-Cache ohne TTL:** Rotation erfordert Recycling beider Lambdas.

## 6. Tests und Auditnachweise

| Suite | Ergebnis |
|---|---|
| Neuer lokaler Agent-Order-E2E | 6 passed |
| Reader / Dispatch-Ingress | 35 / 16 passed |
| Cross-Repo gezielt (E2E, Bridge, MO-Contract, Handoff, Transport, Worker, ATS, Reader, Packaging, Static) | 192 passed, 2 skipped |
| Orders-Lambda | 225 passed |
| Volle RIS-Suite ohne MO-Env | 2654 passed / 134 skipped / 434 subtests; 29 vorbestehende Fehler, 4 Collection-Errors |
| Terraform | `fmt -check` exit 0, `validate` erfolgreich |

## 7. GO/NO-GO

**GO (bedingt) für den Infrastruktur-Apply:** Plan ist nicht destruktiv, enthält
keine geschützten Ressourcen oder Secret-Werte, und die zwei Canary-Blocker
(IAM-Index, ATS-Endpunkt) sind lokal behoben. Bedingungen: Plan gegen den
freigegebenen Commit neu erzeugen und `24/4/0/0` bestätigen; Secret und
Identität/Profil/Entitlement nur über die separaten Gates.

**NO-GO für Canary/Produkt-Traffic**, bis Benutzer, API-Profil, Entitlement
und Secret provisioniert und verifiziert sind.

**HARD STOP vor jedem AWS Apply und jeder Secret-/Benutzer-Mutation.**
