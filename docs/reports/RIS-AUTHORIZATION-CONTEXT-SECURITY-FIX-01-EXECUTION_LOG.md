==================================================
CHECKPOINT: 2026-10-04 20:05 UTC — SECURITY FIX GATE: STAFF-VORPRUEFUNG (Branch: main, HEAD: 75d8de7)
==================================================

- Current status: Staff-Sicherheitsvorpruefung durchgefuehrt; PERMISSIVER PFAD BEWIESEN; HARD STOP vor Codeaenderung; kein Code geaendert
- Audit date/time: 2026-10-04 20:05 UTC
- Current Git branch and HEAD: main, 75d8de7
- Audit scope: Gate-Schritte 1 (Rollenmodell), 2 (Staff-Sicherheitsvorpruefung). Code-Fix, Tests, Live-Matrix B/D, Regression bewusst NICHT ausgefuehrt (Stoppbedingung)
- Completed audit sections:
  - AI_AUDITLOG-Pflicht-Template uebernommen
  - Kontext-Gate: Branch, HEAD, git status, AWS_PROFILE, Account, Region, Workspace
  - Rollenmodell aus bestehendem Vertrag bestaetigt (admins=Product Admin, Staff=Staff, Admin=deprecated, mayaws=AWS-Kontext)
  - Lokale Vorab-Analyse der Claim-Normalisierung (read-only, kein Deploy)
  - 2 synthetische Fixtures angelegt: p20-sec-staff (Gruppe Staff), p20-sec-owner (keine Gruppe), identischer synthetischer Tenant
  - Gruppenzugehoerigkeit verifiziert
  - Handler-Sicht auf Claim via /me geprueft
  - Staff-Pfade 1, 2a, 2b, 2c, 3a, 3b, 3c, 4a, 4b live gefahren
  - Persistenz des unzulaessig erzeugten Profils per DDB-Read verifiziert
  - Audit-Trail geprueft
  - Cleanup: Fixtures deaktiviert, Passwoerter/Tokens shred -u, tmp geloescht
  - Endzustand gelesen
  - Report erstellt
- Actual findings (nur verifizierte Fakten):
  - Account 240571105849 / user/Mayaws; Region eu-central-1; Workspace mays-ris; Branch main / 75d8de7; tracked tree clean
  - CLAIM: /me zeigt fuer Staff groups=[] -> auch der Staff-Claim erreicht den Handler stringifiziert ("[Staff]"), _is_staff ist False
  - PERMISSIV #1: Staff POST /v1/apiprofiles -> HTTP 201 mit apiProfileId (Contract: 403). Profil aprof_352e41330c42441b in DynamoDB PERSISTIERT, name=p20-staff-should-not-exist, status=PENDING, createdBy.role=owner
  - URSACHE: _is_staff False -> Staff wird als Owner behandelt -> create_profile nimmt den Owner-Pfad (api_profiles.py:272-275 greift nie)
  - PERMISSIV #2 (Folge): GET eigenes Staff-Profil ohne reason -> HTTP 200 (Support-Read ohne Reason sollte verweigert sein)
  - AUDIT-INTEGRITAET: der Staff-Create wurde als "action=profile-create outcome=success" auditiert, kein denied-Eintrag, createdBy.role=owner -> die Vertragsverletzung ist im Audit-Trail NICHT als solche erkennbar
  - NICHT-PERMISSIV: GET fremdes Profil 404 (auch mit reason), PATCH fremd 404, status DISABLED/ACTIVE/REVOKED fremd je 404
  - ZU ENG: GET fremdes Profil MIT reason -> 404; die im Contract vorgesehene Staff-Supportfunktion ist NICHT erreichbar
  - => Defekt wirkt BIDIREKTIONAL: gewaehrt eine unzulaessige Faehigkeit (Staff Create) und verweigert eine erlaubte (Support-Read mit Reason)
  - Gate-Stoppbedingung ERFUELLT: "Wenn ein permissiver Staff-Pfad gefunden wird: RED/HOLD und HARD STOP vor Codeaenderung"
  - KEINE Codeaenderung: git status tracked clean; der Fix (JSON-Parsing fuer None/[].["admins]."/Mehrfachgruppen/leerer String/unerwarteter Typ, ohne permissive Fallback-Rolle) ist ANALYSIERT, aber NICHT ausgefuehrt
  - ROLLENVERWECHSLUNG AUSGESCHLOSSEN: mayaws nur fuer AWS-Reads verwendet; keine AWS-Rolle/IAM-Berechtigung/Infrastruktur-Funktion aus einer RIS-Gruppe abgeleitet; RIS Product API bietet keine AWS-Administration
  - Cleanup: p20-sec-staff und p20-sec-owner CONFIRMED/Enabled:false; Secrets vernichtet; tmp geloescht
  - Endstand api_profiles: Count 5, alle PENDING ausser aprof_31f3fa09 (ACTIVE); 4 aus P19, 1 aus diesem Gate
  - Offener Rueckstand: aprof_352e41330c42441b (Staff-Missbrauch, PENDING) kann per API NICHT bereinigt werden (kein DELETE-Endpoint; REVOKE/DISABLED brauchen die nicht funktionierende Admin-Rolle; direkter DDB-Write waere ausserhalb des Gates)
  - DISKREPANZ gefunden: Gate-Tabelle erwartet 403, der etablierte neutrale Anti-Oracle-Pfad liefert durchgaengig 404. Vor dem Fix zu entscheiden, sonst bleibt es bestehen
- Evidence / file references: agents/ecosystem/api_profiles.py:104-109 (_is_admin/_is_staff), :272-281 (create_profile Rollenpruefung), :325-339 (get_profile), :342-362 (list_profiles), :444-510 (transition_status); lambda/handler.py (_extract_user_context, _aprof_fail, _cred_actor); /aws/lambda/mays-ris-dev-agent Log-Gruppe; docs/reports/RIS-P19-APIPROFILE-MANAGEMENT-API-01.md (A/B-Evidenz, Root Cause)
- Classification: RED / HOLD (Stoppbedingung eingetreten)
- Terraform checks actually executed and their results: KEINE Terraform-Kommandos in diesem Gate (kein Apply, kein Plan, keine Codeaenderung); nur Reads gegen Cognito-Metadaten, DynamoDB und Lambda-Logs
- Git status: 0 modified tracked; 2 neue Reports; 9 untracked alt unberuehrt
- Files changed, if any: docs/reports/RIS-AUTHORIZATION-CONTEXT-SECURITY-FIX-01.md (neu), docs/reports/RIS-AUTHORIZATION-CONTEXT-SECURITY-FIX-01-EXECUTION_LOG.md (dieser Log)
- Explicit confirmation when no files were changed: JA — es wurde bewusst KEIN Produktcode geaendert; tracked working tree ist clean. Nur die beiden Pflicht-Reports wurden angelegt.
- Open questions: (1) 403-vs-404-Konvention fuer Staff-Rollenverletzungen vor dem Fix entscheiden; (2) Cleanup des Staff-Missbrauchsprofils braucht einen sicheren Weg; (3) Audit-Hinweis fuer Contract-Verletzungen (optional, eigene Aufgabe)
- Risks: keine Secrets/Tokens/Authorization Header/Passwoerter in Report oder Log; nur Claim-Namen, Gruppenamen und synthetische Nicht-Sensitiv-Werte dokumentiert; beide Fixtures deaktiviert; keine Produktmutation; keine AWS-Rollen-/IAM-Aenderung; keine Rechte aus RIS-Gruppen abgeleitet
- Recommended next actions: Reports committen; HARD STOP. Naechster Schritt ist eine Entscheidung des Auftraggebers, ob der Fix trotz des dokumentierten Vorher-Zustands jetzt erfolgen soll (die Vorher-Evidenz ist gesichert und im Report festgeschrieben), oder ob zuerst die 403/404-Frage und der Cleanup-Weg geklaert werden. Danach eigener Fix-Gate mit Live-Testmatrix A-D und voller Regression inkl. M2M-Trennung
- Current resume point: Commit der Reports

==================================================