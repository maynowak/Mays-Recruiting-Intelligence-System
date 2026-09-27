# TERRAFORM-COGNITO-CONTRACT-REPAIR-01

STATUS: GREEN

## 1. Metadata

- Date/time: 2026-09-26 17:10 UTC
- Branch: main
- Starting HEAD: 8971a1a (`docs: audit Terraform Cognito source of truth`)
- Final HEAD: (s. Commit nach Ausführung)
- Scope: Nur Cognito-Contract (Kopien, Broken-Refs, arn-Sicherung, env-Deklaration). Ressourcen frozen, Client-Attribute frozen, andere Module frozen
- AWS mutation: NONE

## 2. Repairs

1. Duplicate copies entfernt (`modules/cognito/outputs.tf`): `user_pool_id`/
   `user_pool_endpoint`/`user_pool_client_id`-Blöcke (PROVEN identische Values
   zu Inline G0.1). Reason: Duplikat-Klasse eliminieren; Consumer (api-Modul,
   Root-Outputs) adressieren Modul-Namespace — unberührt.
2. Broken `.app`-Block entfernt: `user_pool_client_id`-Kopie adressierte
   nichtexistentes `client.app` (nur `client` belegt; MO-Clone belegt
   Fremdherkunft). Inline-Original deckt alle Consumer.
3. Broken `.staff`-Block + Root-Output entfernt: `user_pool_group_staff_name`
   adressierte nichtexistente `staff`-Gruppe (nur candidates/recruiters/admins
   belegt). Downstream des Root-Outputs: NULL (py/sh/yml/CI-Grep leer) —
   tote Kette beidseitig entfernt, kein realer Consumer gebrochen. Keine
   `staff`-Gruppe neu erfunden (verboten).
4. `user_pool_arn`-Block BEHALTEN (einzig korrekter Block der Datei,
   `users.arn` existent) — Root-ARN-Output damit auf aktiver Quelle, kein
   zweiter Output/keine zweite Ressource.
5. `environment` DEKLARIERT (`modules/cognito/variables.tf`, Wortlaut/Typ
   gespiegelt aus lambda/sqs/api-Modulen: `string`, kein Default, keine
   Validation — keine Erfindung). Heilt Call-Arg + 3 Namens-Nutzungen
   (Pool/Client/Domain). Keine Namens-/Verhaltensänderung.

## 3. Explicitly Retained

Pool `users`, Client `client` (inkl. nicht-standard Attribute — UNPROVEN,
unberührt), Groups (Namen unverändert), Domain, JWT/API-Integration
(Issuer/Audience/Routen), Root-Outputs id/arn/endpoint/client_id.

## 4. Validation

- Reference checks: entfernte Refs leer (`.app`/`.staff`/group-Namen);
  arn-Ziel `users` existent; env deklariert + 3 Nutzungen gültig;
  Ressourcen-Diff leer; JWT/API-Greps unverändert.
- Terraform checks: `fmt -check` (editierte Dateien, kein Write) EXIT 0;
  `validate` ohne init nicht erneut sinnvoll (Module-not-installed,
  init verboten) — Adress-Beweise statt validate (wie im Audit).
- `git diff --check`: PASS. Scope: 3 TF-Dateien (+ Report/Log).
- Test result: keine Terraform-Test-Abhängigkeit (Agent-Tests unberührt).

## 5. Open Questions

Client-Attribut-Semantik (`explicit_authentic_*` — braucht init/validate);
Laufzeit-Pool-Stand (kein Lookup); ob `staff`-Gruppe je gewünscht war (Owner;
Claim-Code gruppen-agnostisch).

## 6. Risks

ARN-Output hing an Kopie-Datei (jetzt Einzel-Block — aufmerksam bei
Folge-Edits); `staff`-Entfernung ist final ohne Gruppen-Bedarf (Review).

## 7. Resume Point

Repair committet (s. Commit); wartet auf Review. Nächster Block separat
(DynamoDB). Keine Folgereparatur hier.

---

*Repair: TERRAFORM-COGNITO-CONTRACT-REPAIR-01 · nur Beweisbares ·
Ressourcen/Client/Gruppen/JWT frozen · keine Erfindung.*
