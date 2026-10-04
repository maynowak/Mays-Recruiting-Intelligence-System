# RIS-PLATFORM-TABLES-IAM-DEPLOYMENT-18 — Platform Tables / IAM Deployment Gate

STATUS: YELLOW (TF vorbereitet, validiert, geplant — KEIN Apply; Live-Aktivierung offen)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, 028a24d (+ uncommitted: TF-Tabellen/IAM/Verdrahtung + diese Reports)
- Scope: NUR api-profiles/offers/credentials-Tabellen + Least-Privilege-IAM + Lambda-Env/Verdrahtung. KEIN Cognito/Gateway/SQS/Lambda-Code/Worker/Agent/Katalog/MO, KEINE B3-Folgeaenderung (bereits GREEN).
- Basis: P17-Blocker-B (3 Tabellen fehlen live — je ResourceNotFound belegt) + P10/P11/P09-Feldvertraege + TF-Konventionen (Namen/Billing/GSI-ALL/Tags/Lease-Privilege-Muster).
- Classification: GREEN (TF/Code-Konvention) / YELLOW (Live: Tabellen fehlen weiter).
- AWS: NUR Reads (sts/describe/get/plan) + State-Lock waehrend Plan. KEIN Apply, KEINE Mutation (verifiziert).
- Git: nur P18-Dateien (s. Commit).
- Next: Apply-Entscheid (Optionen §7) -> HARD STOP.

## 1. Ausgangszustand (read-only verifiziert)

- HEAD 028a24d (B3 GREEN), tree clean; Account/Region/Workspace (mayaws-Projektstandard/eu-central-1/mays-ris).
- Live: api-profiles/offers/credentials = 3x ResourceNotFound; `entitlements` provisioniert (PK entitlementId + gsi-user/gsi-agent).
- Code-Bestand: P10-Profile (CRUD/Selection/effective_status), P11-Offer/Grant (transaktional), P09/P14-Credentials (Digest-Lookup GSI-Bedarf), P12-Handler-Builder (Env-Namen API_PROFILES_TABLE/CREDENTIALS_TABLE/OFFERS_TABLE — exakt diese liefert P18).

## 2. Tabellen (Contract-aus-Code, KEINE Erfindung)

| Tabelle | PK | GSIs | TTL | Billing/SSE/Tags |
|---|---|---|---|---|
| `mays-ris-dev-api-profiles` | apiProfileId (S) | gsi-owner HASH ownerUserId, ALL (list_by_owner — einzige Listen-Abfrage) | KEINS (EXPIRED-Saetze bleiben fuers Audit; Loeschung nur explizit-admin) | PAY_PER_REQUEST / AWS-owned default / Project-Merge (Konvention) |
| `mays-ris-dev-offers` | offerId (S) | KEINE (Get-by-id + Full-List-Scan; Name-Unique in Service; KEINE unnoetigen GSIs) | KEINS (Offers leben bis Admin-Akt) | dto. |
| `mays-ris-dev-credentials` | credentialId (S) | gsi-digest HASH digest, ALL (Lookup JE Verify — ohne Index Vollscan pro Request) | KEINS (expiresAt ist ISO-String, kein Epoch-TTA; Ablauf prueft Code) | dto. |

- Feldabgleich: P10-11-Felder / P11-agentIds+offerId+grantId / P09-Metadaten (digest, KEIN Secret-Feld — Secret-Spalte existiert NICHT, Rekonstruktion unmoeglich).
- Entitlement-Attribute (apiProfileId/offerId/grantId): schemalos, KEIN TF noetig (DDB-Eigenschaft).

## 3. Key Schemas / GSIs / Encryption (Plan-verifiziert)

- Plan-Auszug bestaetigt: Namen, PAY_PER_REQUEST, Hash-Keys, gsi-owner (ownerUserId) + gsi-digest (digest), Project-Tags (+ Provider-Default-Tags).
- Encryption: AWS-owned default (KEIN eigenes SSE-Block — Konvention hat keines; Regel "nur wenn im Vertrag vorgesehen" eingehalten). KEIN PITR (Konvention kennt keines). KEINE oeffentlichen Pfade (DDB privat per Default; Zugriff NUR via Lambda-Rolle).

## 4. IAM Least Privilege (geprueft: NUR Code-Bedarf, KEIN `dynamodb:*`)

- Neue Policy `...-lambda-dynamodb-product` an EXISTIERENDER Agent-Execution-Rolle (KEINE neue Rolle — Gewaehrung nur wo noetig):
  - api-profiles: GetItem/Query/PutItem/UpdateItem (Get/List-by-owner/Create/Full-Update) auf Tabelle + `/index/*`.
  - offers: GetItem/Scan/PutItem/UpdateItem (Get/List/Create/Update; KEIN Query — kein Index noetig).
  - credentials: GetItem/Query/Scan/PutItem/UpdateItem (Get/Digest-Lookup/List+Key-Suchen/Issue/Rotate/Mark-Used).
- NICHT enthalten: DeleteItem (kein Loesch-Pfad: REVOKED persistiert), Batch*/Transact* (Transact betrifft BESTEHENDE Entitlements-Tabelle — separater Follow-up, NICHT dieses Gate), fremde Tabellen, Cognito/S3/TF-Rechte.
- Lambda-Env: API_PROFILES_TABLE/OFFERS_TABLE/CREDENTIALS_TABLE (Namen, KEINE Secrets) + depends_on-Erweiterung (kein anderer Lambda-Eingriff).
- Follow-up (NICHT P18, dokumentiert): `TransactWriteItems` (+ ggf. `DeleteItem`) auf Entitlements-Tabelle fehlt fuer P11-Grant/Withdraw live (bestehende Policy kennt nur Get/Query/BatchGet) — separates Mini-Gate VOR Grant-E2E.

## 5. fmt/validate/Plan (mayaws/dev, Backend S3+Lock, KEIN Apply)

- `fmt`: EIGENE Zeilen clean (Repo hat pre-existing fmt-Verstoesse anderswo — NICHT angefasst, belegt via stash-Vergleich).
- `validate`: Success (nur bekannte Warnings).
- Voll-Plan (/tmp/p18.tfplan): **20 to add, 2 to change, 0 to destroy** (JSON-verifiziert, KEIN Delete/Replace irgendwo).
- Klassifikation: A) P18 = 4 (3 Tabellen + 1 Policy) · B) P16 = 7 Routen · C) P13 = 1 Route · D) CLI-Drift = 6 Routen · E) SQS/IAM-Drift = 2 · F) Pool-Var-Artefakt = 1 Update (ohne `--var` geplant) · G) Lambda-Code-Drift = 1 Update (u.a. neue Env + Rebuild-Hash; KEIN Replace). 68x no-op. 20 = 4+7+1+6+2 exakt aufgeschluesselt.

## 6. Tests / Hygiene

- Domain-Suiten (P10/P11/P09/P14-HTTP/Introspection): 281 passed. Gesamt: 709/8/15+1 Hash-IDENTISCH zur Baseline (KEINE Python-Aenderung in P18 — Erwartung bestaetigt).
- Secret-Scan: KEINE Secrets/Tokens/Digests in Diff/Reports (keine gehandhabt; Tabellen enthalten per Contract KEINE Secret-Spalte).

## 7. Apply-Optionen (Entscheid OFFEN — KEIN Apply erfolgt)

- A) Gezielt NUR A (3 Tabellen + 1 Policy): EMPFOHLEN nach Freigabe (reine Adds, KEIN Destroy/Replace, KEIN Datenverlust-Risiko). Env-Verdrahtung + depends_on wirken ERST mit dem Lambda-Update (G, separater Deploy-Entscheid) — bis dahin bleiben die Routen bei 503 (Tabellen da, Code ohne Env).
- B) Mit B/C kombiniert (P16+P13-Routen): moeglich, braucht Lambda-Deploy-Entscheid (Handler-Code sonst 404) — separates Gate.
- C) Kein Apply: gueltiger Zwischenstand.
- Naechstes Gate bei A: Live-Readback (Status/Keys/GSIs/Tags/Policy-Actions/State-Paritaet) + Domaenen-Smoke (leere Reads, KEIN Credential-E2E) — NICHT in P18.

**HARD STOP (kein Apply ohne Entscheid; P17 NICHT erneut ausgefuehrt).**
