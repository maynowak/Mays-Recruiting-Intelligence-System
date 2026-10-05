==================================================
CHECKPOINT: 2026-10-05 13:10 UTC — SCOPE-VIOLATION FORENSIK (READ-ONLY) (Branch: main, HEAD: 70de2b1)
==================================================

- Current status: Forensik vollstaendig; KEINE Mutation; Status GREEN mit einem YELLOW-Punkt (Empfehlung A)
- Audit date/time: 2026-10-05 13:10 UTC
- Current Git branch and HEAD: main, 70de2b1
- Audit scope: RIS-AUTHORIZATION-CONTEXT-SCOPE-VIOLATION-FORENSICS-01, Teile A-I. FORENSIK ONLY
- Completed audit sections:
  - AI_AUDITLOG-Pflicht-Template uebernommen
  - Kontext verifiziert (Profil, Account, Identity, Region, Workspace, Backend, Branch, HEAD, Working Tree)
  - TEIL A: State-Show lambda_policy; Plan read-only mit -lock=false; IAM-Inline-Timestamps (nicht vorhanden); CloudTrail-Alternative
  - TEIL A-CloudTrail: Trail-Konfiguration, Event-Selektoren, Trail-Status, lookup-events (0 Treffer), S3-Trail-Objekte gelesen
  - TEIL B: Live-Policy vollstaendig enumeriert + Musterpruefung (Wildcards, IAM/STS/KMS/Lambda, Conditions, Index-ARNs)
  - TEIL C: Rollenzuordnung aller 5 Lambda, Trust-Policies, Agent-Rolle, "inert"-Beleg
  - TEIL D: Code-Demand-Abgleich logs/dynamodb/s3; Redundanz zu lambda_dynamodb_work; S3-Bucket-Pruefung
  - TEIL E: Repo-Historie, Fix-Commit ad5cedc, Diff alt->neu, MalformedPolicyDocument-Ursache
  - TEIL F: ESM-Tags live/state/config/Funktionsvergleich, LastModified-Vergleich
  - TEIL H: Plan-Inhalt, Terraform-Version, -target-Semantik in plan -help vs apply -help
  - TEIL G/I: Impact-Matrix und Empfehlungen
  - Report erstellt
- Actual findings (nur verifizierte Fakten):
  - Kontext: AWS_PROFILE=mayaws; Account 240571105849; Identity user/Mayaws; Region eu-central-1; Workspace mays-ris; Backend S3 terraform.tfstate + Lock mays-ris-tf-lock; Branch main; HEAD 70de2b1; Working Tree 0 tracked Aenderungen -> KONTEXT KONFORM
  - TEIL A: lambda_policy IM STATE; id=mays-ris-lambda-role:mays-ris-lambda-policy; Rolle mays-ris-lambda-role; definiert in terraform/modules/iam/main.tf:65-95; Inputs var.project_name/var.dynamodb_table_arn/var.s3_bucket_arn/aws_iam_role.lambda_role.id; Abhaengigkeit aws_iam_role.lambda_role
  - TEIL A: Plan read-only (-lock=false) = "No changes." -> State == Config, KEIN weiterer Drift
  - TEIL A: lambda_policy war vorher FOREIGN DRIFT (Plan zeigte create) und ist Teil des gewuenschten Zustands
  - TEIL A: IAM-Inline-Policies fuehren KEINE Timestamps -> Erstellungszeitpunkt nicht direkt belegbar
  - TEIL A-CloudTrail: lookup-events lieferte 0 Treffer AUCH fuer den definitiven UpdateFunctionCode; Trail schreibt nur nach S3 (mays-ris-cloudtrail-240571105849), KEINE CloudWatch-Loggruppe; IncludeManagementEvents=true ohne Ausschluesse; IsLogging=true; im S3-Trail GetRolePolicy @10:07:09Z gefunden (eigener Read), aber die drei Mutations-Events nicht -> S3-Delivery-/Listing-Verzögerung; Erstellung stattdessen belegt durch Plan(create) + Apply(1 added) + State/Live
  - TEIL B: Policy live = 3 Statements, alle Allow, 0 Conditions; logs:CreateLogGroup/CreateLogStream/PutLogEvents auf arn:aws:logs:*:*:*; dynamodb:PutItem/GetItem/UpdateItem/Query/DeleteItem auf work-items + /index/*; s3:PutObject/GetObject/DeleteObject auf arn:aws:s3:::mays-ris-dev-data/*
  - TEIL B: KEINE Service-Wildcard, KEINE Action-Wildcard, KEIN Resource-Wildcard "*", KEINE IAM-/STS-/KMS-/Lambda-Aktionen, KEIN PassRole, KEINE Conditions; Index-ARNs vorhanden
  - TEIL B: Live == Config (Plan bestaetigt)
  - TEIL C: 0 von 5 Lambda-Funktionen verwenden mays-ris-lambda-role -> "inert" BELEGT (list-functions vollstaendig, Trust-Policy = lambda.amazonaws.com)
  - TEIL C: Agent nutzt arn:aws:iam::240571105849:role/mays-ris-dev-agent; Rollenzuordnung aller 5 Funktionen dokumentiert
  - TEIL C: REDUNDANZ: Agent-Rolle hat work-items-Rechte bereits via mays-ris-dev-lambda-dynamodb-work (PutItem/GetItem/UpdateItem/Query/DeleteItem/BatchGetItem)
  - TEIL C: Trust-Policy der Rolle identisch zur Agent-Rolle
  - TEIL C: Nicht untersucht = Nutzung durch ECS/Step-Funktionen (ausserhalb Lambda) -> als offener Punkt vermerkt
  - TEIL D: logs-Rechte breiter als noetig (alle Loggruppen), aber auf ungenutzter Rolle
  - TEIL D: dynamodb work-items bereits gedeckt (lambda/handler.py:1600-1604, :1834-1840: put_item/get_item)
  - TEIL D: s3:mays-ris-dev-data -> KEINE Referenz in terraform/ (grep), KEINE Code-Referenz; Bucket EXISTIERT (head-bucket), ist NICHT im Terraform-State und NICHT im Repo deklariert; Policy referenziert var.s3_bucket_arn aus aws_s3_bucket.data
  - TEIL D: Bewertung = praktisch vollstaendig ungenutzt, mit redundanten DDB-Rechten und ungenutztem S3-Ziel
  - TEIL E: Historie modules/iam/main.tf = d87a48f (Einfuehrung), 5ff851b, ad5cedc ("fix(terraform): valid iam lambda policy statements", 2026-10-03)
  - TEIL E: MalformedPolicyDocument-Ursache BELEGT: alte Struktur bettete data.aws_iam_policy_document.lambda_dynamodb.json und .lambda_s3.json (beides bereits JSON-STRING) in jsonencode({Statement=[...]}) -> doppelt kodierter String im Statement-Array; ad5cedc ersetzte beide durch explizite Statement-Objekte; aktuelle Deklaration konsistent mit live
  - TEIL F: ESM 7cc946b9...; vorherige Tags LEER (in P17/P17A/P18 dokumentiert); aktuell {Environment, Maker, Project}; Terraform-Wunsch identisch aus default_tags (terraform/main.tf:30-38); Grund: Mapping am 2026-10-01 per USER_INITIATED ausserhalb TF erstellt -> Default-Tags nie erhalten; keine funktionale Wirkung; State/Enabled/BatchSize/LastModified 2026-10-01T18:04:22.068+02:00 IDENTISCH zur P17A-Referenz; Lambda mays-ris-dev-agent traegt identische Tags
  - TEIL H: /tmp/sf.tfplan enthielt 3 non-noop (95 resource_changes): lambda_policy create, sqs_mapping update (tags_all), agent update
  - TEIL H: ROOT CAUSE BELEGT - Terraform v1.16.1: -target ist in plan -help dokumentiert ("Limit the planning operation"), in apply -help NICHT vorhanden (0 Treffer); apply-Hilfe: "provide a plan file ... Terraform will take the actions described in that plan"; korrekte Form waere apply -target OHNE Planfile oder ein per plan -target erzeugter Plan
  - TEIL G: Security GREEN, Functional GREEN, IAM YELLOW, Runtime GREEN, Data GREEN, Cost GREEN, Compliance YELLOW, State GREEN, FutureDrift GREEN
  - TEIL I: A) WEITER UNTERSUCHEN (rollback wuerde create-Drift erzeugen; S3-Zielherkunft unklaer; Rolle ohne Nutzer), B) BELASSEN (rollback nicht begruendet, wuerde Drift zurueckbringen), C) State unveraendert lassen (No changes, keine Anomalie)
  - Working Tree nach Forensik: 0 tracked Aenderungen; Authorization-Fix unangetastet (kein diff an lambda/handler.py, agents/, tests/)
- Evidence / file references: terraform/modules/iam/main.tf:65-95 (Definition), :3-60 (data sources + Rolle); terraform/main.tf:30-38 (default_tags), :15-19 (Backend); lambda/handler.py:1600-1604, :1834-1840 (work-items Ops); commits ad5cedc, 5ff851b, d87a48f; /tmp/sf.tfplan, /tmp/live_policy.json, /tmp/forensics.tfplan (nicht committet)
- Classification: GREEN (Forensik vollstaendig, keine Mutation) mit YELLOW-Empfehlungspunkt A
- Terraform checks actually executed and their results: KEINE Mutation. Nur: state show (read-only), state list, plan -lock=false (read-only, "No changes."), show -json des alten Planfiles. KEIN apply/import/destroy/state rm/state mv/state push
- Git status: 0 modified tracked; 1 neuer Report; 9 untracked alt unberuehrt
- Files changed, if any: docs/reports/RIS-AUTHORIZATION-CONTEXT-SCOPE-VIOLATION-FORENSICS-01.md (neu), docs/reports/RIS-AUTHORIZATION-CONTEXT-SCOPE-VIOLATION-FORENSICS-01-EXECUTION_LOG.md (dieser Log)
- Explicit confirmation when no files were changed: entfaellt (nur die beiden Forensik-Reports; kein Produktcode, kein Terraform, kein Testfile, kein State, keine AWS-Ressource geaendert)
- Open questions: (1) Zweck und Herkunft des nicht-TF-verwalteten Buckets mays-ris-dev-data; (2) ob mays-ris-lambda-role ueberhaupt existieren soll (0 Nutzer); (3) exakter CloudTrail-Zeitstempel der Policy-Erstellung (S3-Delivery-Verzögerung); (4) ob die Rolle durch Nicht-Lambda-Ressourcen genutzt wird
- Risks: keine Secrets/Tokens/Authorization Header/Passwoerter im Report; keine Mutation; keine Rechte entfernt; keine Testaenderung; Rollenmodell unberuehrt; keine AWS-Administration aus RIS-Rollen
- Recommended next actions: Reports committen; HARD STOP. Danach optional: YELLOW-Erklaerungs-Gate (S3-Bucket + Rollennutzung), Prozess-Gate zur verbsindlichen Target/Planfile-Regel. P17 NICHT starten, P20 NICHT starten, kein Rollback
- Current resume point: Commit der Forensik-Reports

==================================================