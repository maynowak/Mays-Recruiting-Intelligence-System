# RIS-ATS-AGENT-01 — Orchestrierter Promptplan

Stand: 2026-11-15 · Zielrepository: `maynowak/Mays-Recruiting-Intelligence-System` · Projektkontext: `ris-dev2` (lokale Entwicklung; keine Cloudbereitstellung)

## Verbindliche Entscheidung

**Kein neuer Agenten-Stack.** Bereits vorhandene, getestete Registry, Discovery, Eligibility, AgentBody, WorkItem, Transport V1, OrdersPort und `addition_agent` bleiben bestehen. RIS besitzt bereits `agents/ats_agent/{agent.py,registry.py}` (`ats-agent`, `analyze.job`, v1.0.0). Der bestehende Agent delegiert derzeit an einen veränderlichen Jobsearch-HTTP-Dienst; Ziel ist die kontrollierte Nutzung des aktuellen, anschließend fixierten ATS-Core-Pakets. Mays Jobsearch ist im gesamten Auftrag read-only.

### Verifizierte Remote-Baselines bei Planerstellung
- RIS `main`: `ae08267c3871d7bb85b7aa7ed2aed07a75385584` (Merge A04–A07, 2026-11-15).
- Jobsearch `main`: `a5640d12dba8ca39258484f5212def17eabf4eca` (2026-11-13). **Vor der Implementierung erneut `fetch` und auf Aktualität prüfen**; dieser SHA ist lediglich die Baseline der Planung, noch kein freigegebener Package-Pin.
- Jobsearch: `api/ats-analysis.mjs`, `api/_lib/ats.mjs`, `api/_lib/filter.mjs`, weitere transitive Imports, zugehörige API-Tests und Anzeige in `src/`.
- RIS bereits bestehende Pin-Datei `installer/mays-jobsearch-clone.pinned.json` verweist auf älteren Referenzcommit `29d8b730...`. Nicht stillschweigend als ATS-Paket-Pin nutzen oder überschreiben.
- Neuere ATS-Core-Commits: `3c79cccf...` (02.10. Score/Dedup), `c1866191...` (14.10. Normalisierung), `8456b1d9...` (30.10. gruppierte Begriffe). Der API-Handler allein ist nicht der vollständige Stand.
- Die 5-seitige Roadmap nennt AG-01–AG-10, gemeinsame Runtime und eigenes Cloud-Gate; lokales agenten-/Orders-E2E gilt als vorhandene Evidenz, nicht als neuer Architekturauftrag.

## Orchestrator — Hauptprompt (zum Einfügen in Coding-Agent)

> Du bist der Commander für `RIS-ATS-AGENT-01` im lokalen RIS-Checkout. Arbeite ausschließlich auf einem neuen Feature-Branch, bevorzugt `feature/ris-dev2-ats-agent-pinned-core-01`, aus einem überprüften und sauberen Basispunkt. Gehe vor jeder Mutation nach `AGENTS.md` vor und lies `docs/AI_AUDITLOG.md`. Jobsearch ist vollständig read-only; dort keine Branches, Tags, Commits, Patches, Releases oder Deployments erzeugen. Hole den aktuellen Jobsearch-Remote-Stand neu ab, überprüfe dessen HEAD und sämtliche ATS-API-Abhängigkeiten. Ein alter Pin ist keine Aktualitätsprüfung. Verwende bestehende RIS-Registry/Runtime/AgentBody/Orders-Verträge und das existierende `agents/ats_agent` statt einen neuen Agentenstack zu bauen. Nutze Unteragenten für parallele **read-only** Untersuchungen; alle schreibenden Änderungen, Build-Gates und Commits serialisiert der Commander. Nach jedem vollständig getesteten Schritt: Evidence und Auditlog schreiben, committen, Arbeitsbaum kontrollieren, erst dann nächsten Schritt. Keine AWS-/Terraform-Apply-, Deploy-, Cognito-, CloudFront-, DNS- oder fremden Infrastrukturaktionen; `ris-dev2` ist nach aktuellem Bericht abgebaut. Kein Merge und kein Push ohne gesonderten Auftrag. Dokumentiere echte Evidenz statt behaupteter Tests. Bei einem Blocker STOP und präzisen Handoff liefern.

## Gates und einzeln ausführbare Arbeitsprompts

### ORCH-00 — Baseline / Audit (erster Prompt)
> Prüfe `git status`, Branch, HEAD, Remotes und Existenz konkurrierender Arbeitszweige. Lies `AGENTS.md`, `docs/AI_AUDITLOG.md`, die Agent-Ecosystem-Roadmap sowie `agents/ats_agent/agent.py`, `agents/ats_agent/registry.py`, `agents/addition_agent/agent.py`, `agents/runtime/pipeline.py`, `agents/orders/*` und relevante Tests. Markiere bereits verifizierte A04–A07- und Gate-7-Funktionalität ausdrücklich als wiederzuverwenden. Lege einen neuen Branch nur an, wenn HEAD/Baseline und Cleanliness geklärt sind; fremde uncommitted Dateien nicht anfassen. Schreibe die Baseline- und Konfliktmatrix ins RIS-Audit und committe nur dokumentierte Änderungen. Kein Architektur-Refactoring.

**Abnahme:** Identität des bestehenden ATS-Agenten, Runtime-Wiring, Baseline und harte Grenzen belegt.

### ORCH-01 — Aktuelle Jobsearch-ATS-API read-only abholen
> Prüfe die gegenwärtige Remote-HEAD von `maynowak/mays-jobsearch`, fetch nur read-only in einem getrennten/ignorierten Clone, notiere vollen Commit-SHA und Quelle. Untersuche `api/ats-analysis.mjs`, `api/_lib/ats.mjs` und alle transitiven Imports samt relevanten Tests, Fixtures, CV-/ATS-UI-Komponenten und Ergebnisfeldern. Vergleiche neuesten Stand mit dem älteren RIS-Referenz-Pin und dokumentiere Änderungen, insbesondere Keyword-Score-Prozent 0–100, Requirement-Deduplikation, Skill-Normalisierung und gruppierte Terms. Prüfe auch ob die API oder Frontend-Ausgabe inzwischen andere Formen unterstützt. Trenne tatsächlich vorhandene API-Schnittstellen von Vorschlägen. Keine Änderungen oder neue Tags in Jobsearch. Committe einen RIS-seitigen Audit-/API-Snapshot-Bericht.

**Abnahme:** Nachvollziehbare Import-/Version-/Field-Matrix; Remote SHA frisch geprüft; keine Jobsearch-Mutation.

### ORCH-02 — Paketstrategie und unveränderlicher Source-Pin
> Prüfe zuerst, ob der Jobsearch-Code im aktuellen Stand tatsächlich als eigenständiges Paket nutzbar ist. Wenn nicht, baue ausschließlich im RIS-Buildpfad einen reproduzierbaren, minimalen Vendor-/Core-Adapter aus dem frisch verifizierten Commit und seinen Imports. Kein stillschweigend behauptetes bestehendes npm-Paket; kein willkürlicher Release-Tag. Verknüpfe Manifest mit Repo, vollem Commit-SHA, Datei-/Artefakt-Hash, Buildkommando, Lizenz/NOTICE, Vertrag und Runtime-Requirements. Bestehende historische Clone-Pins nicht umdeuten. Prüfe AGPL-/Drittlizenzhinweise beim Pakettransfer. Rebuild zweimal, vergleiche SHA und durchlaufe echte Artefakttests. Audit und Commit.

**Abnahme:** deterministischer Artefakt-Pin, Manifest, Lizenznachweis, Build-/Hash-Evidence.

### ORCH-03 — RIS ats_agent aktualisieren, keine Agentenduplikation
> Erweitere `agents/ats_agent` am bestehenden Registry-Identifier `ats-agent` und der bestehenden Capability `analyze.job`; prüfe vor einer eventuellen Capability-Erweiterung die Kompatibilität zu bestehenden Clients. Behalte AgentBase, WorkItem, AgentBody, Routing, Eligibility, Tenantprüfung, Idempotency und Transport bei. Nutze den versionierten lokalen ATS-Core über einen sauber getesteten Ausführungsadapter; eine Abhängigkeit auf die veränderliche Jobsearch-Produktiv-HTTP-API erfüllt den Pin nicht. Kein Neubau der Runtime oder eigener SQS-Transport. Achte auf Node-/Python-Prozessgrenze, Timeouts, Fehlercodes und Bundle. Tests, Audit, Commit.

**Abnahme:** synthetischer WorkItem-Durchlauf durch bestehenden AgentBody ohne live Jobsearch-HTTP; Addition-Regressionsfall unverändert.

### ORCH-04 — Ergebnisbody / Jobsearch-Darstellungsparität
> Definiere einen versionierten `ATSAnalysisResultBody V1` innerhalb des existierenden RIS `success/data/metrics`-Resultvertrags. Übernimm alle belegten Felder aus dem frischen Jobsearch-API-Resultat, insbesondere `analysis.score`, `analysis.keywordCoverage.overall`, `requirements`, `matches`, `criticalGaps`, `recommendations`, `ai`. Nicht nur Anzeige simulieren: feste JSON-Fixtures mit 0/50/100, Duplikaten, fehlenden/optionalen Feldern, Matches/Partials/Unknowns und leeren Listen. Die Quell-API liefert Matching von `job` und `profile`; Dokument-/PDF-Extraktion ist separat zu spezifizieren und nur zu integrieren, falls dafür bereits geeigneter RIS-Code nachgewiesen ist. Kein Parser- oder LLM-Feature erfinden. Quellenmetadaten nur datensparsam im Body. Audit, Commit.

**Abnahme:** dieselbe Ausgabe semantisch identisch wie Jobsearch für gleiche Testinputs; Schema- und Consumer-Vertragstests bestanden.

### ORCH-05 — Integration und Regression
> Führe gezielte Core-, Agent-, Registry-, Body-, WorkItem-, Agent-Order-, Orders-/Transport-Contract- und Additionsregressionen aus. Verwende echtes gebautes ZIP/Artefakt statt nur Quellpfad-Tests. Prüfe fail-closed für ungültige Inputs, unerlaubte Capability, fremden Tenant, Consent/PII, Doppelauslieferung, stale WorkId, Hash-Drift, nie loggen von CV-Rohtext/Secrets. Keine Cloud-Tests als lokal ausgegeben. Dokumentiere Pass/Fail/Skip präzise, Audit und Commit.

**Abnahme:** fokussierte und übergreifende Regressionen mit reproduzierbaren Kommandos und unverändertem addition_agent.

### ORCH-06 — Abschluss-/Handoff-Bericht
> Liefere Commit-Tabelle, verifizierten Jobsearch-Quell-SHA, Paket-SHA, Testmatrix, Schema-/UI-Parität, Änderungen im RIS-Branch, Auditlog-Nachweise, offene technische Punkte und separate AWS-Gates. Lass `main`, Jobsearch und AWS unangetastet. Stopp mit reviewfähigem Branch; kein automatisch ausgeführter Merge/Deploy.

## Orchestrierungsregeln
1. Read-only-Subagenten dürfen parallel untersuchen: (A) Jobsearch API/Core/Imports, (B) UI-Contract/Tests, (C) RIS Registry/Runtime/ATS, (D) Security/Lizenzen. Sie liefern Reports und vorgeschlagene Auditlog-Einträge; Commander serialisiert Writes.
2. Vor jedem Gate echte Baseline prüfen. Pro abgeschlossenem Gate: minimaler Diff, Tests, Audit-Eintrag, **Commit**, clean tree.
3. Keine Wiederholung der bereits vorhandenen A04–A07-Orchestrierungsarchitektur oder unaufgeforderte neue Agenten-SQS.
4. `ris-dev2` bezeichnet die Ziel-/Projektkonfiguration, **nicht** eine als live anzunehmende AWS-Installation.
5. Bei Abweichungen zuerst tatsächliche Implementierung prüfen, nicht veraltete Roadmap-Angaben blind übernehmen.
6. Ein Version-Pin wird nach frischem Fetch festgelegt und danach ausschließlich bewusst aktualisiert.

## Offene Entscheidungen mit Default
- **Tag:** Kein Tag im Jobsearch-Repo ohne Auftrag; vorerst RIS-eigener voller Source-SHA + Artefakt-SHA.
- **Dokument:** ATS-Matching aus strukturierten Job-/Profile-Daten ist in Jobsearch belegt. PDF-/DOCX-Eingang nur durch nachgewiesenen, separaten Parser-/Extraction-Adapter; nicht als implementiert ausgeben.
- **KI:** Default deaktiviert; externer Provider nur unter eigenem Consent-/Security-Gate.
- **Release:** Nur lokale verifizierte Integration, kein AWS Apply/Deploy, kein Merge.
