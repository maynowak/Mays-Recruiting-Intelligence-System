# JM-RIS-AUTH-POOL-REPAIR-01 — Execution Log

CHECKPOINT: 2026-10-31 20:49 UTC — Baseline und Live-Read-only-Prüfung (Branch: main, HEAD: c49eb2b37ab3d629eeee224084045a9659c59705)

- Current status: IN PROGRESS — Ursache und Soll-Pool werden vor Änderungen verifiziert.
- Audit date/time: 2026-10-31 20:49 UTC
- Current Git branch and HEAD: `main`, `c49eb2b37ab3d629eeee224084045a9659c59705`
- Audit scope: Ermitteln, welcher Cognito User Pool aktuell von `mays-job-matcher.app` verwendet wird; korrigieren des beim Update verdrehten Jobsearch/RIS-Pool- und Custom-Domain-Wirings; Live-Verifikation und Abschlussbericht.
- Completed audit sections: Template-/Repo-Regeln gelesen; User-Bericht aus `../Mays-Jobsearch/docs/reports/JM-AUTH-COGNITO-CUSTOM-DOMAIN-REGRESSION-01.md` geprüft; RIS-Konfiguration, Cognito-Modul und beide live Pools read-only geprüft.
- Actual findings (nur verifizierte Fakten):
  - Jobsearch-Codefallback und der vorgelegte Jobsearch-Bericht zeigen aktuell auf Pool `eu-central-1_ZURSMpD2O`, Client `5hb3f6dj5ialg77jf4blur9g6g`.
  - Live AWS Account `240571105849`, Region `eu-central-1`: Pool `eu-central-1_ZURSMpD2O` heißt `ris-dev-jobsearch-dev-users`, Prefix-Domain `ris-dev-jobsearch-dev`, CustomDomain `null`.
  - Live Pool `eu-central-1_ojbmoiYGM` heißt laut API derzeit `mays-ris-dev-users`, Prefix-Domain `mays-ris-dev`, CustomDomain `null`.
  - `installer/project-configs/ris-dev.json` enthält bereits `identity_custom_domain_enabled=true`, Domain `auth.mays-job-matcher.app` und das ACM-Zertifikat in `us-east-1`.
  - Das RIS-Cognito-Modul würde die Custom Domain an seinen Terraform-verwalteten RIS-Pool binden; ein Apply ohne Overlay hatte stattdessen eine Prefix-Domain erzeugt.
  - Aktueller Projektstandard (`AGENTS.md`): Jobsearch muss den RIS-Pool `ris-dev-dev-users` / `eu-central-1_ojbmoiYGM` verwenden, nicht den separaten Orders-Pool. Ob die produktive Website per Vercel-Umgebungsvariable noch auf `ZURSMpD2O` zeigt, wird als Nächstes direkt verifiziert.
- Evidence / file references: `AGENTS.md`; `installer/project-configs/ris-dev.json`; `terraform/modules/cognito/main.tf`; `../Mays-Jobsearch/src/lib/oidcConfig.ts`; `../Mays-Jobsearch/docs/reports/JM-AUTH-COGNITO-CUSTOM-DOMAIN-REGRESSION-01.md`; AWS CLI `sts get-caller-identity` und `cognito-idp describe-user-pool` für beide IDs.
- Classification: ORANGE — produktive Auth-Zuordnung möglicherweise falsch; Custom Domain live nicht aktiv; Änderung erst nach eindeutiger State-/Website-Zuordnung.
- Terraform checks actually executed and their results: Noch keine; nur Source-/AWS-Read-only-Prüfung.
- Git status: RIS-Repo hatte vor diesem Task bereits die fremde untracked Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md`; sie wird nicht verändert. Dieser Execution Log ist die einzige bisherige Task-Datei.
- Files changed, if any: `docs/reports/JM-RIS-AUTH-POOL-REPAIR-01-EXECUTION_LOG.md` neu.
- Explicit confirmation when no files were changed: Nicht zutreffend; Execution Log wurde gemäß Audit-Vorgabe angelegt.
- Open questions: Welcher Pool/Client steckt im aktuell ausgelieferten Produktionsbundle bzw. in Vercel Production? Welchen Pool verwaltet der aktuelle Workspace-State tatsächlich? Ist die Custom Domain nach Neuanlage DNS-seitig auf das neue CloudFront-Ziel umzuschalten?
- Risks: Ein Apply gegen den falschen Workspace oder ohne Overlay könnte weitere Domain-/Pool-Drift erzeugen. Eine Domain kann nur einem Pool zugeordnet sein. DNS kann nach Neuanlage stale bleiben. Fremde AWS-Ressourcen dürfen nicht verändert werden.
- Recommended next actions: Produktionsbundle/Vercel-Variablen read-only prüfen; Terraform-State im Workspace `ris-dev` read-only prüfen; zielgenauen Plan mit 0 unerwarteten Änderungen erzeugen; erst dann kontrolliert applyen und Vercel ggf. neu deployen.
- Current resume point: Read-only Website-/Vercel-/State-Prüfung.

CHECKPOINT: 2026-10-31 20:52 UTC — Produktionszuordnung und Ziel-Client verifiziert (Branch: main, HEAD: c49eb2b37ab3d629eeee224084045a9659c59705)

- Current status: IN PROGRESS — Ist-/Soll-Zuordnung eindeutig; kontrollierter Terraform-Plan steht aus.
- Audit date/time: 2026-10-31 20:52 UTC
- Current Git branch and HEAD: `main`, `c49eb2b37ab3d629eeee224084045a9659c59705`
- Audit scope: unverändert.
- Completed audit sections: Vercel Production Environment ausgelesen; ausgeliefertes JS-Bundle geprüft; Terraform-Backend initialisiert und Workspace `ris-dev` gewählt; State und live App Clients geprüft; Custom-Domain- und Route53-Zustand geprüft.
- Actual findings (nur verifizierte Fakten):
  - **Aktuell auf `mays-job-matcher.app` zugeordnet:** Pool `eu-central-1_ZURSMpD2O`, Client `5hb3f6dj5ialg77jf4blur9g6g`, Region `eu-central-1`. Belegt durch Vercel Production Environment und produktives Bundle `/assets/index-DNonqmtS.js` (beide IDs enthalten; `ojbmoiYGM` nicht enthalten).
  - **Soll laut aktuellem RIS-Standard:** RIS-Pool `eu-central-1_ojbmoiYGM`, dessen öffentlicher App Client `7ldhihlpdgsgcl3puvu4oi7ksv` ist. Terraform-State bindet Client und Pool korrekt zusammen.
  - Der Ziel-Client hat Code-Flow, Scopes `email/openid/profile`, Provider `COGNITO` sowie Produktions-Callback `https://www.mays-job-matcher.app/auth/callback` und Logout `https://www.mays-job-matcher.app/`.
  - Terraform-Workspace `ris-dev`, Backend `s3://mays-ris-tf-state-dev`, verwaltet Pool `ojbmoiYGM` und aktuell Prefix-Domain-Ressource `module.cognito.aws_cognito_user_pool_domain.domain[0]`.
  - `auth.mays-job-matcher.app` ist aktuell keinem Cognito-Pool zugeordnet (`DomainDescription={}`). Es gibt keine Route53 Hosted Zone für `mays-job-matcher.app` in diesem AWS-Account; DNS-Anpassung ist daher extern.
- Evidence / file references: Vercel Production env (nur drei nicht-geheime `VITE_*`-Werte ausgewertet; temporäre Datei unter `/tmp/opencode`); produktives JS-Bundle; Terraform state show/list; AWS `list-user-pool-clients`, `describe-user-pool-domain`, `route53 list-hosted-zones-by-name`.
- Classification: ORANGE — produktive Website ist verifiziert auf dem falschen/alten dedizierten Pool; Custom Domain fehlt.
- Terraform checks actually executed and their results: `terraform init -reconfigure` mit freigegebenem Backend erfolgreich (nur Deprecation-Warnung `dynamodb_table`); Workspace `ris-dev` erfolgreich gewählt; State nur gelesen.
- Git status: unverändert abgesehen von diesem Execution Log und der bereits fremden untracked Apply-Dokumentation.
- Files changed, if any: nur dieser Execution Log.
- Explicit confirmation when no files were changed: Keine Source-Dateien geändert.
- Open questions: Terraform-Planumfang; neues Cognito-CloudFront-Ziel und externer DNS-Zugriff.
- Risks: Ein Vercel-Env-Wechsel ohne neues Production Deployment ändert das ausgelieferte Bundle nicht. Custom Domain kann nach Apply bis DNS-Korrektur nicht erreichbar sein.
- Recommended next actions: Paketierung gemäß Vertrag; kontrollierten Plan mit Projekt-Overlay erstellen; nur bei erwarteter Domain-Änderung applyen; danach Vercel Production auf Ziel-Pool/-Client setzen und neu deployen.
- Current resume point: `package → plan` für `ris-dev` mit explizitem Backend.

CHECKPOINT: 2026-10-31 20:55 UTC — Scope auf vollständige `ris-dev`-Korrektur erweitert (Branch: main, HEAD: c49eb2b37ab3d629eeee224084045a9659c59705)

- Current status: IN PROGRESS — kein Plan angewendet; State-/Ressourcen-Inventar vor destruktiver Korrektur.
- Audit date/time: 2026-10-31 20:55 UTC
- Current Git branch and HEAD: `main`, `c49eb2b37ab3d629eeee224084045a9659c59705`
- Audit scope: Auf ausdrückliche User-Steuerung erweitert: Es soll nur die `ris-dev`-Installation existieren; der beim letzten Branch→main-Upgrade/Apply mit `project_name=mays-ris` erzeugte falsche Bestand/State ist zu korrigieren bzw. zu entfernen. Auth-Pool und Custom Domain bleiben Teil des Fixes.
- Completed audit sections: Paketierung erfolgreich; Installer-Planversuch analysiert; direkter Vollplan für korrekte Projektidentität `ris-dev` und separater stabilisierter/gezielter Auth-Plan erzeugt, aber beide **nicht angewendet**.
- Actual findings (nur verifizierte Fakten):
  - Der Installer-Plan scheiterte vor Planerstellung wegen fehlerhaft berechneter Bundle-Pfade (`/home/dci-student/projects/lambda/...` aus `installer/ris.py:1041-1050`).
  - Direkter Plan im Workspace `ris-dev` mit korrektem `project_name=ris-dev`: `105 add, 18 change, 105 destroy`; viele Ersetzungen benennen live `mays-ris-*` nach `ris-dev-*` um. Dieser Plan wurde nicht angewendet.
  - Direkter Plan mit der im State vorhandenen falschen Identität `project_name=mays-ris`: `1 add, 3 change, 1 destroy`; zielbegrenzter Auth-Plan: `1 add, 1 change, 1 destroy`. Auch diese Pläne wurden nicht angewendet, da der User nun die vollständige Namens-/State-Korrektur verlangt.
  - ACM-Zertifikat für `auth.mays-job-matcher.app` ist `ISSUED` und aktuell unbenutzt. DNS-CNAME zeigt stale auf `d2oa751y8iy3p0.cloudfront.net`.
- Evidence / file references: `/tmp/opencode/ris-dev-auth-fix-plan.txt`; `/tmp/opencode/ris-auth-domain-only-plan.txt`; `/tmp/opencode/ris-auth-targeted-plan.txt`; `installer/ris.py:1028-1051`; AWS ACM read-only; DNS lookup.
- Classification: RED — Workspace/Projektidentität sind cross-wired; Vollkorrektur ist destruktiv (105 Ersetzungen) und darf erst nach präziser State-/Live-Inventur erfolgen.
- Terraform checks actually executed and their results: `package` PASS; Installer `plan` FAIL wegen lokalen Pfaden; direkter Vollplan PASS (`105/18/105`); stabilisierter Plan PASS (`1/3/1`); zielbegrenzter Auth-Plan PASS (`1/1/1`); kein Apply.
- Git status: Bundle-Dateien wurden durch deterministische Paketierung aktualisiert (gitignored/Artefakte); keine Source-Datei geändert. Fremdes untracked Apply-Report unverändert.
- Files changed, if any: dieser Execution Log; Build-Artefakte durch `package`.
- Explicit confirmation when no files were changed: Keine Terraform-/Anwendungs-Source geändert; keine AWS-/Vercel-Mutation ausgeführt.
- Open questions: Welche Backend-State-Objekte/Workspaces existieren? Gibt es einen separaten falschen `mays-ris`-Workspace/State oder liegt nur falsche Projektidentität im korrekten Workspace `ris-dev`? Welche Datenressourcen würden bei Ersetzung verloren gehen?
- Risks: State-Löschung ohne vorherigen Resource-Destroy erzeugt verwaiste Ressourcen; Resource-Destroy kann persistente Daten löschen; der Vollplan enthält 105 Ersetzungen und benötigt genaue Prüfung.
- Recommended next actions: Backend/Workspace/State und Live-Ressourcen read-only inventarisieren; falschen State eindeutig bestimmen; Daten-/Schutzstatus der zu ersetzenden Buckets und Tabellen prüfen; danach Korrekturplan und sichere Reihenfolge festlegen.
- Current resume point: Read-only State-/Workspace-/Live-Inventar.

CHECKPOINT: 2026-10-31 20:58 UTC — Letztes Merge-Deployment vollständig rekonstruiert (Branch: main, HEAD: c49eb2b37ab3d629eeee224084045a9659c59705)

- Current status: READY FOR CONTROLLED RESTORE — letzter guter State gesichert, falscher Apply nachgewiesen, Datenumfang geprüft; noch kein neuer Apply.
- Audit date/time: 2026-10-31 20:58 UTC
- Current Git branch and HEAD: `main`, `c49eb2b37ab3d629eeee224084045a9659c59705`
- Audit scope: vollständige Wiederherstellung/Upgrade der permanenten `ris-dev`-Installation und Entfernung leerer falscher State-Objekte; anschließend Jobsearch auf RIS-Pool und Custom Domain zurückstellen.
- Completed audit sections: Merge analysiert; gespeicherte Planfiles dekodiert; versionierte Backend-State-Historie geprüft; letzten guten State vom 21.10. gesichert und mit aktuellem State verglichen; alle State-Objekte auf Resource-Anzahl geprüft; destruktiven Vollplan als JSON klassifiziert; Datenbestände der zu ersetzenden S3-/DynamoDB-Ressourcen geprüft.
- Actual findings (nur verifizierte Fakten):
  - Letzter Merge in `main`: `c49eb2b` vom 30.10.2026 17:59 UTC, PR #1, Integration des Mays-Orders-Modul-Builders.
  - Am 31.10. ab 06:41 UTC wurde im Workspace `ris-dev` der gespeicherte Plan `tfplan-controlled` mit **`project_name=mays-ris`** und Custom Domain `false` ausgeführt. Planinhalt: 104 Replace, 18 Update, 1 Delete, 1 Create. Das ersetzte den korrekten `ris-dev`-Bestand durch `mays-ris`-Namen.
  - Folgeplan `tfplan-v3` (07:57 lokale Dateizeit) hatte ebenfalls `project_name=mays-ris`, Custom Domain `false`, und 8 Creates. State-Versionen belegen die Apply-Schreibvorgänge 06:41–06:58 UTC.
  - Letzter guter State vor dem fehlerhaften Deploy: S3-Version `NByx8h1jlwlkGVD6p2UcVzD5UpS3_yXA`, 21.10.2026 13:28 UTC, serial 11, 185 Resources. Er belegt: Pool `ojbmoiYGM` = `ris-dev-dev-users`, Client `7ld...` = `ris-dev-dev-client`, API `g6901and25` = `ris-dev-dev-api`, Custom Domain `auth.mays-job-matcher.app`.
  - Aktueller State serial 26 hat dieselben stabilen IDs für Pool/Client/API, aber Namen `mays-ris-dev-*` und Prefix-Domain `mays-ris-dev`. Das zeigt: die Kern-IDs wurden teils in-place verdreht; viele namensgebundene Ressourcen wurden ersetzt.
  - Backend enthält 13 aktuelle State-Objekte. Nur `env:/ris-dev/dev/terraform.tfstate` enthält Resources (185); alle 12 anderen enthalten **0 Resources**. Sie sind daher leere/stale States, nicht Eigentümer live verwalteter Ressourcen.
  - Kontrollierter Restore-/Upgrade-Plan mit `project_name=ris-dev` und Custom Domain `true`: 104 Replace, 18 Update, 1 Create, 1 Delete; keine Anwendung bisher.
  - Datencheck vor Restore: 11 zu ersetzende App-DynamoDB-Tabellen sind leer, außer `mays-ris-dev-agent-catalog` mit exakt 2 Terraform-Seeds; Orders-Tabelle leer. App-/Dokument-/Health-State-Buckets leer; Health-Public enthält 2 Objektversionen (Terraform-generiert); CloudTrail-Bucket enthält 340 Log-Objektversionen und muss vor Bucket-Ersetzung verlustfrei gesichert/migriert werden.
- Evidence / file references: Git `c49eb2b`; gespeicherte Pläne in `~/.ris-workdirs/ris-dev/dev/terraform/tfplan-*`; S3 Object Versions für `env:/ris-dev/dev/terraform.tfstate`; `/tmp/opencode/ris-dev-good-2026-10-21.tfstate`; `/tmp/opencode/ris-dev-state.json`; `/tmp/opencode/ris-dev-restore-plan.json`; AWS DynamoDB/S3 read-only Inventar.
- Classification: RED → YELLOW (Restore-Pfad belegt, aber kontrolliert destruktiv und noch nicht ausgeführt).
- Terraform checks actually executed and their results: Vollplan erfolgreich (`105 add, 18 change, 105 destroy`, davon 104 Replace); JSON-Analyse erfolgreich; letzter guter/current State erfolgreich gelesen; kein Apply.
- Git status: keine Source-Änderungen; Execution Log neu; fremder Apply-Report unverändert.
- Files changed, if any: nur dieser Execution Log und lokale Build-/Planartefakte.
- Explicit confirmation when no files were changed: Keine Source-Dateien und noch keine neue AWS-/Vercel-Konfiguration geändert.
- Open questions: Keine fachliche Ziel-Frage mehr; operative Reihenfolge muss CloudTrail-Logs erhalten und State-Cleanup erst nach erfolgreichem Restore ausführen.
- Risks: 104 Ersetzungen; CloudTrail-Logverlust bei ungesichertem Bucket-Cleanup; kurze Downtime; externer DNS-CNAME muss nach Cognito-Custom-Domain-Neuanlage ggf. aktualisiert werden.
- Recommended next actions: State/DynamoDB/S3 lokal sichern und Hashmanifest erzeugen; CloudTrail-/Health-Public-Objekte herunterladen; ersetzte Buckets kontrolliert leeren; exakten gespeicherten Restore-Plan anwenden; live verifizieren; CloudTrail-Logs in neuen Bucket zurückspielen; danach leere stale State-Objekte löschen; Vercel Pool/Client ändern und Production deployen.
- Current resume point: Sicherheitsbackup vor dem kontrollierten Restore-Apply.

CHECKPOINT: 2026-10-31 21:06 UTC — Restore partiell erfolgreich, Custom Domain DNS-blockiert (Branch: main, HEAD: c49eb2b37ab3d629eeee224084045a9659c59705)

- Current status: PARTIAL SUCCESS / EXTERNAL DNS BLOCKER — `ris-dev`-Familie wiederhergestellt; Custom Domain noch nicht angelegt.
- Audit date/time: 2026-10-31 21:06 UTC
- Current Git branch and HEAD: `main`, `c49eb2b37ab3d629eeee224084045a9659c59705`
- Audit scope: unverändert.
- Completed audit sections: vollständiges Sicherheitsbackup mit Hashmanifest; CloudTrail kontrolliert pausiert; versionierte alte Bucket-Inhalte geleert; exakten Restore-/Upgrade-Plan angewendet; Partial-Failure analysiert; neuen State und CloudTrail geprüft; 340 gesicherte CloudTrail-Logs in neuen Bucket zurückgespielt.
- Actual findings (nur verifizierte Fakten):
  - Backup unter `/tmp/opencode/ris-dev-restore-backup`: 355 Dateien, 3.0 MiB, `SHA256SUMS`; enthält guten/aktuellen State, DynamoDB-Scans und alle 340 CloudTrail-Logobjekte sowie Health-Public-Artefakte.
  - Restore-Apply hat die fehlerhaften `mays-ris-*` Ressourcen durch die korrekte `ris-dev-*` Familie ersetzt bzw. stabile Ressourcen zurückbenannt. Post-Apply-State serial 35, 188 Resources, Namensinventar 116× `ris-dev`, 0× `mays-ris` in den relevanten Identitätswerten.
  - Pool-ID `eu-central-1_ojbmoiYGM` blieb erhalten und heißt wieder `ris-dev-dev-users`; Prefix- und CustomDomain sind momentan `null`.
  - CloudTrail `ris-dev-trail` ist nach Terraform-Erstellung wieder aktiv (`IsLogging=true`). Gesicherte Logs wurden in `ris-dev-cloudtrail-240571105849` zurückgespielt.
  - Einzige Apply-Fehlermeldung: Cognito Custom Domain `auth.mays-job-matcher.app` konnte nicht erstellt werden, weil der DNS-CNAME noch auf die alte CloudFront-Distribution `d2oa751y8iy3p0.cloudfront.net` zeigt (`CloudFront 409`, incorrectly configured DNS record).
  - Autoritative Nameserver sind `ns.checkdomain.de` / `ns2.checkdomain.de`; die Zone liegt nicht in AWS Route53 und nicht in Vercel DNS (Vercel zeigt nur Default-Records). Der stale `auth`-Record muss daher bei Checkdomain entfernt/geändert werden, bevor AWS die neue Cognito-Distribution anlegen kann.
- Evidence / file references: `/tmp/opencode/ris-dev-restore-backup/SHA256SUMS`; `/tmp/opencode/ris-dev-restore-apply.txt`; `/tmp/opencode/ris-dev-state-after-partial.json`; AWS `describe-user-pool`, `get-trail-status`; DNS `NS`/`CNAME`; Vercel DNS read-only.
- Classification: YELLOW — Kern-Restore erfolgreich, Auth-Custom-Domain extern DNS-blockiert; Jobsearch Production wurde noch nicht auf RIS-Pool umgestellt und bleibt daher funktional am alten Pool.
- Terraform checks actually executed and their results: gespeicherter Vollplan angewendet; 104 Ersetzungen/18 Updates weitgehend erfolgreich; Abschluss exit nonzero ausschließlich wegen Custom-Domain-Create. State wurde bis serial 35 fortgeschrieben.
- Git status: keine Source-Änderungen; Execution Log fortgeschrieben; fremder Report unverändert.
- Files changed, if any: nur Execution Log und lokale Backups/Build-/Planartefakte.
- Explicit confirmation when no files were changed: Keine Terraform-Source geändert; AWS-Infrastruktur wurde wie beschrieben ersetzt.
- Open questions: Zugriff auf den Checkdomain-DNS-Record `auth` ist in dieser Umgebung nicht vorhanden/noch nicht nachgewiesen.
- Risks: Ziel-Pool hat momentan keine Login-Domain; Umschalten von Vercel vor Custom-Domain-Recovery würde Login brechen. DNS-Änderung und Cognito-Anlage müssen in dieser Reihenfolge erfolgen.
- Recommended next actions: leere stale Backend-State-Objekte entfernen; Checkdomain-CNAME `auth` löschen; warten bis DNS nicht mehr auf alte CloudFront-Distribution zeigt; Recovery-Plan/Apply nur für Custom Domain; neuen CloudFront-Zielwert ermitteln und Checkdomain-CNAME darauf setzen; dann Vercel Pool/Client umstellen und Production deployen.
- Current resume point: Stale State-Cleanup und DNS-Zugriffsblocker.

CHECKPOINT: 2026-10-31 21:28 UTC — Produktive Poolgrenze korrigiert, Domain-Recovery provisioniert (Branch: main, HEAD: c49eb2b37ab3d629eeee224084045a9659c59705)

- Current status: WAITING FOR AWS ACTIVE — technische Korrektur abgeschlossen; Cognito-Domain provisioniert noch (erwartete Dauer bis ca. 20 Minuten).
- Audit date/time: 2026-10-31 21:28 UTC
- Current Git branch and HEAD: `main`, `c49eb2b37ab3d629eeee224084045a9659c59705`
- Audit scope: final präzisiert: Upgrade/Restore von `ris-dev`, aber **keine Migration des produktiven Jobsearch-Pools**. Jobsearch bleibt auf seinem dedizierten Pool `eu-central-1_ZURSMpD2O`.
- Completed audit sections: User-Korrektur zur produktiven Poolgrenze aufgenommen; Vercel unverändert verifiziert; RIS-Overlay/Regeln/Tests angepasst; RIS-Prefix-Domain separat angelegt; stale Checkdomain-CNAME durch User entfernt; Custom Domain am bestehenden Jobsearch-Pool neu angelegt; neuen CNAME durch User gesetzt; DNS/OIDC/HTTPS geprüft; abschließenden Terraform-No-Drift-Plan und Tests ausgeführt.
- Actual findings (nur verifizierte Fakten):
  - Die frühere Zwischenempfehlung, Jobsearch auf den RIS-Kernelpool `ojbmoiYGM` umzuschalten, war falsch. Sie wurde **nicht umgesetzt**: keine Vercel-Änderung, kein Jobsearch-Code-Deployment, keine Nutzer-/Client-Migration.
  - Vercel Production bleibt: Pool `eu-central-1_ZURSMpD2O`, Client `5hb3f6dj5ialg77jf4blur9g6g`, Region `eu-central-1`.
  - Schutzregel ergänzt: Produktive Site-Pools/-Domains dürfen bei einem Upgrade niemals ohne ausdrückliche Bestätigung der betroffenen Site und des Zielpools migriert, entfernt oder umgehängt werden.
  - RIS-Overlay beansprucht `auth.mays-job-matcher.app` nicht mehr (`identity_custom_domain_enabled=false`); RIS-Kernelpool `ojbmoiYGM` hat seine separate Prefix-Domain `ris-dev-dev`.
  - Custom Domain erfolgreich am bestehenden Jobsearch-Pool erstellt: `auth.mays-job-matcher.app` → Cognito `UserPoolId=eu-central-1_ZURSMpD2O`, neue CloudFront-Distribution `dsv3el0c1dn2.cloudfront.net`, Managed Login v1.
  - Autoritatives DNS und Resolver 1.1.1.1/8.8.8.8 liefern CNAME `auth.mays-job-matcher.app → dsv3el0c1dn2.cloudfront.net` (TTL 300).
  - OIDC-Discovery des unveränderten Pools liefert wieder `https://auth.mays-job-matcher.app/oauth2/authorize` und `/oauth2/token`; HTTPS-Probe gegen die neue Distribution antwortet `302` (erwarteter Managed-Login-Redirect).
  - Cognito-Status war beim Checkpoint noch `CREATING`; begrenzte Hintergrundprüfung (max. 20 Minuten) wartet auf `ACTIVE`.
  - Backend-State-Cleanup abgeschlossen: Im State-Bucket existiert aktuell nur `env:/ris-dev/dev/terraform.tfstate`; 12 leere/stale State-Objekte wurden entfernt, ihre historischen Versionen bleiben durch S3-Versionierung wiederherstellbar.
  - Finaler Terraform-Plan mit korrektem `project_name=ris-dev` und ohne Anspruch auf die Jobsearch-Domain: `No changes`, Detailed Exit Code 0.
- Evidence / file references: `AGENTS.md`; `installer/project-configs/ris-dev.json`; `tests/test_project_config_overlay.py`; Vercel Production env read-only; AWS `create/describe-user-pool-domain`; OIDC Discovery; DNS trace; `/tmp/opencode/ris-dev-final-plan.txt`; dieser Execution Log.
- Classification: YELLOW pending `ACTIVE`; Infrastruktur/State GREEN, DNS/OIDC/HTTPS GREEN, Browser-E2E noch offen.
- Terraform checks actually executed and their results: Restore-Apply partiell, danach Recovery-Apply `1 add, 0 change, 0 destroy` erfolgreich; finaler Full Plan `No changes` (exit 0); `terraform validate` PASS mit 16 bekannten Deprecation-Warnungen; `terraform fmt -check` PASS.
- Git status: Task-Dateien geändert: `AGENTS.md`, `installer/project-configs/ris-dev.json`, `tests/test_project_config_overlay.py`, dieser Execution Log. Fremde untracked Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` unverändert. Keine Jobsearch-Repo-Datei verändert.
- Files changed, if any: wie Git status oben; AWS-Ressourcen und State wie dokumentiert.
- Explicit confirmation when no files were changed: Keine Vercel-Env-, Jobsearch-Code- oder Jobsearch-Repo-Änderung; produktiver Pool/Client unverändert.
- Open questions: Nur Abschlussstatus `ACTIVE` und optionaler echter Browser-Login mit Testnutzer.
- Risks: Bis `ACTIVE` kann Cognito die Domain noch provisionieren; Browser-E2E wurde ohne Zugangsdaten nicht durchgeführt. Die Custom Domain des dedizierten Jobsearch-Pools ist bewusst out-of-band gegenüber dem RIS-Kernel-Terraform und darf nicht erneut vom Kernel-Overlay beansprucht werden.
- Recommended next actions: `ACTIVE` abwarten; danach normale HTTPS-/Discovery-Prüfung wiederholen; optional Browser-Login bis `/auth/callback` und `/profil` testen; Änderungen reviewen/committen.
- Current resume point: Hintergrundprüfung auf Cognito `ACTIVE` läuft.

CHECKPOINT: 2026-10-31 21:30 UTC — FINAL / Domain ACTIVE (Branch: main, HEAD: c49eb2b37ab3d629eeee224084045a9659c59705)

- Current status: COMPLETE — `ris-dev`-Upgrade korrigiert; falsche State-Objekte entfernt; produktiver Jobsearch-Pool unverändert; Custom Domain wieder ACTIVE.
- Audit date/time: 2026-10-31 21:30 UTC
- Current Git branch and HEAD: `main`, `c49eb2b37ab3d629eeee224084045a9659c59705`
- Audit scope: abgeschlossen wie im vorigen Checkpoint präzisiert.
- Completed audit sections: Alle Audit-, Restore-, State-Cleanup-, DNS-, Cognito-, OIDC-, HTTPS-, Terraform- und Regression-Prüfungen abgeschlossen.
- Actual findings (nur verifizierte Fakten):
  - Cognito `describe-user-pool-domain`: Domain `auth.mays-job-matcher.app`, Pool `eu-central-1_ZURSMpD2O`, Status `ACTIVE`, CloudFront `dsv3el0c1dn2.cloudfront.net`, Managed Login v1.
  - DNS autoritativ sowie über 1.1.1.1/8.8.8.8: `auth.mays-job-matcher.app CNAME dsv3el0c1dn2.cloudfront.net`, TTL 300.
  - Normale HTTPS-Probe auf `/oauth2/authorize` antwortet `302`; OIDC-Discovery liefert die Custom Domain als Authorization Endpoint.
  - Vercel Production ist unverändert auf Pool `ZURSMpD2O` und Client `5hb3...`; keine Migration und kein Redeploy erforderlich.
  - RIS-Terraform-Endzustand: `No changes` (Detailed Exit 0). Backend enthält nur den aktiven `ris-dev`-State.
  - CloudTrail `ris-dev-trail` ist aktiv; letzter Delivery Attempt erfolgreich. Gesicherte historische Logs liegen im neuen `ris-dev-cloudtrail-240571105849` Bucket.
  - Abschlussinventar: keine Lambdas, SQS-Queues, APIs oder Cognito-Pools mit Präfix `mays-ris`; einzige verbleibende `mays-ris`-Namen sind die kanonischen Backend-Ressourcen `mays-ris-tf-state-dev` und `mays-ris-tf-lock`.
- Evidence / file references: gesamte Checkpoint-Historie dieses Logs; AWS-/DNS-/HTTPS-/OIDC-Ausgaben um 21:29 UTC; `/tmp/opencode/ris-dev-final-plan.txt`; `/tmp/opencode/ris-dev-restore-backup/SHA256SUMS`.
- Classification: GREEN (Browser-E2E mit echtem Nutzer nicht ausgeführt, aber Infrastruktur-, Discovery- und HTTPS-Vertrag verifiziert).
- Terraform checks actually executed and their results: `package` PASS; Restore-Plan/Apply ausgeführt; Recovery-Apply PASS; finaler Plan `No changes`; validate PASS (bekannte Warnungen); fmt-check PASS.
- Git status: `AGENTS.md`, `docs/AI_AUDITLOG.md`, `installer/project-configs/ris-dev.json`, `tests/test_project_config_overlay.py` geändert; dieser Report neu. Fremde untracked Datei `docs/reports/TF-APPLY-CONTROLLED-2026-10-31.md` unverändert.
- Files changed, if any: wie Git status; AWS/State/DNS wie oben.
- Explicit confirmation when no files were changed: Keine Jobsearch-Code-, Vercel-Env- oder Jobsearch-Repo-Änderung.
- Open questions: Keine Blocker. Optionaler Browser-E2E mit Testkonto bleibt möglich.
- Risks: Die dedizierte Jobsearch-Custom-Domain ist bewusst nicht Eigentum des RIS-Kernel-Cognito-Moduls. Schutzregel und Overlay verhindern erneutes Beanspruchen; Planreviews müssen diese Produktionsgrenze weiterhin beachten.
- Recommended next actions: Änderungen reviewen und committen; optional Login im Browser bis `/profil` testen.
- Current resume point: Task abgeschlossen.

## Test summary

- `tests/test_project_config_overlay.py`: **22 passed**.
- Vollsuite: **1669 passed, 11 skipped, 2 failed**. Die zwei Fehler liegen in bestehenden Installer-Tests (`test_install_dry_run_performs_no_mutation`, `test_validate_skips_workspace_without_backend`) und betreffen Pin-/Mock-Verhalten; die task-spezifischen Tests sind vollständig grün.
- `python3 -m py_compile installer/ris.py`: PASS.
- `terraform validate`: PASS, 16 bekannte Deprecation-Warnungen.
- `terraform fmt -check`: PASS.
- `git diff --check`: PASS.
