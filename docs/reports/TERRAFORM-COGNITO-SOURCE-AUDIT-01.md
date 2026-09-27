# TERRAFORM-COGNITO-SOURCE-AUDIT-01

STATUS: YELLOW

## 1. Audit Metadata

- Date/time: 2026-09-26 16:55 UTC
- Branch: main
- HEAD: b5a2703 (`fix(terraform): repair Lambda contracts`; Vorgänger 21cc04a/c34e1e9 unangetastet)
- Previous checkpoint: TERRAFORM-LAMBDA-CONTRACT-REPAIR-01
- Git status: 0 modified, 7 untracked (unberührt); genau 1 Audit-Log
- AWS mutation: NONE (read-only; kein init/plan/apply, kein Backend/Provider-Setup)

## 2. Cognito Variant Inventory

| Variant | Location | Terraform address | Classification | Evidence |
|---------|----------|-------------------|----------------|----------|
| Inline-Outputs (id/client_id/endpoint) | modules/cognito/main.tf:53-63 | `module.cognito.{user_pool_id,user_pool_client_id,user_pool_endpoint}` | ACTIVE (G0.1-Originale, korrekte Ziele) | `-S`-Historie G0.1; Ressourcen existent |
| outputs.tf-Kopie (5 Blöcke) | modules/cognito/outputs.tf:2-25 | dto. Namen | DUPLICATE, davon 2× BROKEN (`.app`/`.staff` nichtexistent) | c83e3a2-Neuanlage; T011-05/May's-Orders-Texte; Adress-Grep |
| Pool/Client/Groups/Domain | modules/cognito/main.tf:3-51 | `users`, `client`, `candidates/recruiters/admins`, `domain` | ACTIVE + CONNECTED (einzige Definitionen) | einzige Ressourcen im Modul; Consumer-Kette |
| `environment`-Call-Arg | terraform/main.tf (cognito-Call) | — (unclusiv) | STALE (unproven als Bedarf) | undeklariert + alle Nutzungen unklar s. §9 |

"3 Varianten" aus Consolidation-Audit = Inline-Outputs vs. outputs.tf-Kopie vs.
(implizit) Call-Arg-Schicht. Kein älterer Pool (nicht aus Alter geschlossen —
Referenz-belegt).

## 3. Root → Cognito Wiring

root (`module "cognito"`: project_name, environment, tags) → Pool
(`users`, Name `${project}-${environment}-users`) → Client (`client`) →
Groups (3) → Domain (`${project}-${environment}`) → api-Modul
(`user_pool_id/_client_id/_endpoint` → JWT-Authorizer) → Root-Outputs (5×,
inkl. arn/group NUR aus outputs.tf-Datei!). Adressen alle verbunden;
`environment` undeklariert übergeben UND modul-intern genutzt (s. §9).

## 4. User Pool Contract (nur Bestand, keine Wertung)

Name mit Env-Suffix; Password-Policy 8/upper/lower/number, Symbole false;
Schema: `custom:tenant_id` (String); KEIN MFA-Block, KEINE weiteren
Schema-Attribute, KEINE auto-verifizierten Attribute, KEIN Account-Recovery-
Block, KEINE Lambda-Trigger, KEIN Deletion-Protection, KEIN Lifecycle-Block;
Tags Project + var.tags. Abwesenheiten sind Beobachtung, kein Mangel-Urteil.

## 5. User Pool Client Contract

`client` ← Pool `.users.id`; Name mit Env-Suffix; `generate_secret = false`;
Attribute `explicit_authentic_authentication_factors = ["USERNAME"]` +
`preferred_authentic_authentications = ["USERNAME"]` — NICHT die Standard-
Provider-Argumente (vgl. Referenz `explicit_auth_flows`); Korrektheit
UNPROVEN (braucht validate mit init — verboten). KEIN OAuth-Block, KEINE
Callback/Logout-URLs, KEINE Token-Validity, KEINE Scopes. Consumer: JWT-
Authorizer (audience) via api-Input; Root-Output client_id.

## 6. Group Contract

Existent: `candidates`, `recruiters`, `admins` (je Name + pool-id, sonst
nackt). Keine Duplikate (je 1×). Root-Output `user_pool_group_staff_name`
adressiert nichtexistentes `staff` (BROKEN, s. §8). App-Code
(`lambda/handler.py:172`): `cognito:groups` generisch durchgeleitet (String-
Split robust) — KEIN hartcodierter Gruppenname; `custom:tenant_id`-Claim
matcht Pool-Schema. Keine Umbenennung (verboten).

## 7. API Gateway / JWT Integration

Kette PROVEN: Pool `.endpoint` → `var.cognito_user_pool_endpoint` →
`jwt_configuration.issuer` (api/main.tf:29) + Client-ID → `audience` (Z.28) →
Authorizer `jwt` → Routen (`/me`, `/me/profile`, … `authorization_type JWT`,
`authorizer_id`). Genutzte Cognito-Ressource: Pool `users` (+ Client-ID).
API-Config unverändert.

## 8. Output Contract

- Verbraucht (consumed): `user_pool_id`, `user_pool_client_id`,
  `user_pool_endpoint` (je → api-Modul UND root outputs).
- Exportiert, aber nur via outputs.tf-Datei: `user_pool_arn`,
  `user_pool_group_staff_name` (→ root outputs; Inline-Seite hat sie NICHT).
- Duplikat: id/endpoint/client_id je 2× (Inline ACTIVE vs. Kopie).
- Stale/broken: Kopie-`client_id` (`.app`), Kopie-`group_staff_name` (`.staff`).
- Unknown: keiner (alle Adressen geprüft). NICHTS entfernt (Audit).

## 9. Variable Contract

Modul deklariert: `project_name`, `tags` (beide konsumiert). Root übergibt
zusätzlich `environment`: UNDEKLARIERT, aber modul-intern 3× genutzt
(Pool-/Client-/Domain-Namen) → weder "tot" noch "aktiv" sauber — STALE als
Deklarationslage, Bedarf PROVEN (Namen hängen dran). `custom:tenant_id` ist
Schema, keine Variable. Kein Duplikat, kein weiterer Stale-Fund. Repair
offen (eigener Checkpoint).

## 10. Dependency Graph

```
root ──project_name/tags(+environment:stale)──▶ module.cognito
  ├─ users ──┬─▶ client ──▶ api.jwt(audience) ──▶ routes
  │          ├─▶ domain
  │          ├─▶ candidates/recruiters/admins (kein Terraform-Consumer; App liest Claim generisch)
  │          └─▶ endpoint ──▶ api.jwt(issuer)
  └─▶ root outputs (5×; arn/group nur via outputs.tf-Datei)
KEINE Kante: cognito→IAM, cognito→Lambda(direkt), cognito→SQS/DynamoDB.
```

## 11. Findings

PROVEN: Adressen/Kette oben; Kopie = Mays-Orders-Verbatim (`.app`/`.staff`/
T011-05/"May's Orders"-Texte vs. Referenz-Modul mit exakt diesen Namen);
`environment`-Doppellage (Arg + Nutzung, keine Deklaration); JWT-Kette;
generische Gruppen-Durchleitung + Tenant-Claim-Match.
UNPROVEN: Client-Attributnamen-Gültigkeit; Apply-Verhalten der broken Outputs;
ob `staff` je existierte (Historie: Total-Grep laufend — hier als UNPROVEN,
nicht UNKNOWN, da prüfbar im Repair).
UNKNOWN: Laufzeit-Pool-Stand (kein Live-Lookup, DO NOT GUESS).

## 12. Candidate Next Small Repair

TERRAFORM-COGNITO-CONTRACT-REPAIR-01 (nach Review, NICHT hier): (a) Kopie-
Blöcke id/endpoint/client_id entfernen (PROVEN identisch); (b) broken
`.app`/`.staff`-Blöcke entfernen NACH Umlenkung der Root-Outputs
(`user_pool_arn`→ Inline-`users.arn` neu; `group_staff_name` → STALE-Entscheid:
keine `staff`-Gruppe belegt → Output entfernen oder Gruppe klären, Owner);
(c) `environment` DEKLARIEREN (Bedarf PROVEN durch Namens-Nutzung) + totes
Arg damit heilen. KEINE Pool-/Client-/Gruppen-/Authorizer-Änderung.

## 13. Risks

Broken Outputs blockieren `validate` sobald Parse-/Init-Schicht passiert
(Plan-Beleg ausstehend); `staff`-Output-Entscheid braucht Owner (Claim-Code
ist gruppen-agnostisch → Entfernung wahrscheinlich sicher, dennoch Review);
Client-Attribute könnten Provider-Fehler werfen (UNPROVEN).

## 14. Resume Point

Audit committet (s. Commit); wartet auf Review vor
TERRAFORM-COGNITO-CONTRACT-REPAIR-01. Keine Implementierungsänderung erfolgt;
`terraform/`-Diff leer.

---

*Audit: TERRAFORM-COGNITO-SOURCE-AUDIT-01 · read-only · Mays-Orders nur Muster
(Ein-Rollen-Analogie: dort `app`/`staff` REAL — RIS-Kopie adressiert
Fremdnamen; RIS behält eigene Architektur).*
