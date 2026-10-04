# RIS-AGENT-STATUS-NORMALIZATION-07 — Agent Status Normalization & Fail-Closed

STATUS: GREEN (implementiert + getestet; KEIN AWS, KEIN TF, KEINE Migration)

- Date/Time: 2026-10-03 UTC
- Branch + HEAD (RIS): main, 711aca3 (+ uncommitted: 5 Code-Dateien + 1 Test-Datei + diese Reports)
- Basis (verbindlich): P01-P06, insb. P6-R6 (ACTIVE = ausführbar; INACTIVE/DEPRECATED/RETIRED/REGISTERED/AVAILABLE/FAILED = blockiert; UNBEKANNT = BLOCKIERT). Alle 14 Regeln eingehalten (§-Liste im Auftrag).
- Scope: Status-Normalisierung + Fail-Closed auf allen Ausführungspfaden. NICHT: Worker-Entitlement-Re-check, Credential Verification, APIProfile-Authorization, Agent Sandboxing (Folge-Gates).
- Classification: GREEN (alle 18 Spec-Faelle + Sicherheitspruefung bestanden).
- Terraform/AWS/Cognito/DB/Gateway: KEINE Mutation (verifiziert). Migration: NONE.
- Git: nur P7-Dateien (s. Commit).
- Next: Folge-Gates per P6-R8 (Worker-Re-check, Sandboxing, Group-Migration) -> HARD STOP.

## 1. Ausgangsbefund (Schritt 1 — klassifiziert, vor Aenderung verifiziert)

- B1 (KRITISCH): `catalog_adapter._convert_to_descriptor` -> NameError bei JEDEM Aufruf (Funktions-lokaler Import in `populate_*`, Nutzung in Modul-Funktion) — DDB-Katalog befuellte Registry NIE (still geschluckt). [Adapter-Datei]
- B2 (KRITISCH): Adapter-Map mit Default ACTIVE bei unbekannt (fail-open) + Referenz auf nichtexistentes `AgentStatus.INACTIVE` (Enum hatte nur 6 Werte). [Adapter + Registry]
- B3: Handler `_init_catalog` gleiche INACTIVE-Referenz (AttributeError -> stiller Gesamt-Abbruch der Katalog-Init) + Default-ACTIVE. [handler.py:57-71]
- B4: Handler-Gates `_handle_agents` / `_execute_agent` vergleichen Kleinbuchstaben-`'active'` gegen DDB-GROSSWERTE (funktioniert nur bei klein-gespeicherten Seeds; fallabhaengig). [handler.py:606/779]
- B5: Eligibility blockiert hart NUR RETIRED/DEPRECATED; INACTIVE/FAILED/REGISTERED/AVAILABLE passieren als eligible (Quirk in der `eligible`-Berechnung). [eligibility.py:76-83]
- B6: Enum ohne INACTIVE (aber 2 Referenzen darauf). [registry.py]
- OK (unveraendert, konsistent): Discovery-Default ACTIVE + Enum-Vergleiche (registry.list, pipeline discovery-Aufrufe) — funktionieren nach Normierung korrekt weiter.
- Scope-fremd (NICHT angefasst, dokumentiert): WorkItem-Status (CREATED/QUEUED/... — eigene Domaene, base.py), Capability/Body/Runtime-Kompatibilitaet in Eligibility (bestehende Semantik ausserhalb Status), `get_descriptor`-Docstring (referenziert nichtexistente Methode — pre-existing, unberuehrt).

## 2. Zentrale Normalisierung (Schritt 2 — NEU: agents/ecosystem/agent_status.py)

- `normalize_agent_status(raw)`:.strip().upper()-Lookup im Enum; Enum-Mitglieder passieren; unbekannt/leer/None/Nicht-String -> None (= BLOCKED, kein persistierter Status, keine neue Statusklasse). NIEMALS Default-ACTIVE.
- `is_executable_status(raw)`: True GENAU bei ACTIVE (roh oder Enum) — EINZIGE Ausführbarkeits-Aussage.
- Enum ergaenzt: `INACTIVE` (referenziert, P6-kanonisch — kein erfundener Status).
- Alle Pfade nutzen DIESE Grenze (Adapter, Eligibility, Handler-Gates); Discovery/Registry/Pipeline konsumieren Enum-Werte (konsistent ohne Aenderung).

## 3. Betroffene Pfade (Schritte 3-6)

- Adapter (Schritt 3): Fail-Open-Map ENTFERNT; unbekannt -> Skip + Warnung (nicht registriert = blockiert); DDB-Werte UNVERAENDERT (nur Normierung); Converter liefert echten AgentDescriptor (zuvor NameError-Dict — Discovery braucht Attribut-Objekte); Modul-Imports auf Top-Level (pure, kein boto3).
- Eligibility (Schritt 4): zentrale Entscheidung; NUR ACTIVE passiert; alle anderen -> INELIGIBLE mit Status-Grund (RETIRED/DEPRECATED-Sonderfall obsolet-entfernt; Capability/Body/Runtime-Pruefungen unveraendert dahinter).
- Pipeline/Worker (Schritt 5): KEIN Code-Eingriff noetig — Pfad Discovery(ACTIVE-Filter) -> Eligibility(zentral) -> Selection blockt nicht-ACTIVE lueckenlos (Tests §5 belegen); KEINE Entitlement-/Credential-/Sandboxing-Logik hinzugefuegt (Scope-Verbot eingehalten).
- Read-Paths (Schritt 6): `_init_catalog` (zentral + Skip) + beide Gates (`/agents`-Filter, Execute-403) auf `is_executable_status` umgestellt — KEINE neue Introspection gebaut.

## 4. Fail-Closed-Regel (Schritt 9 — explizit geprueft)

- Unbekannt/NULL/leer/verstümmelt -> KEINE Ausfuehrung (getestet Faelle 10-12/17).
- Client-Payload-Status ueberschreibt Katalog NICHT (Gates lesen DDB-Katalog; Pipeline loest Deskriptor aus Registry, nicht aus Nachricht).
- Queue-Nachricht liefert KEINE Autorisierung (kein Status-als-Berechtigung; tenantId/agentId wortwoertlich, aber Deskriptor aus Registry).
- WorkItem liefert KEINE Autorisierung (Pflichtfelder nur Validierung; Dedup-Anker workId unveraendert).
- Katalog = zentrale Status-Wahrheit (einzige Mapping-Stelle + Registry-Filter).
- Status verleiht KEINE Entitlements; ersetzt KEINE Credential-/Profile-Pruefung (unberuehrte Pfade).

## 5. Testfaelle (Schritt 7 — tests/test_agent_status_normalization.py, 20 Tests, ALLE GRUEN)

Spec-Faelle 1-18 abgedeckt (1 ACTIVE, 2 `active`, 3 ` Active `, 4-9 INACTIVE/DEPRECATED/RETIRED/REGISTERED/AVAILABLE/FAILED blockiert, 10 unknown, 11 empty, 12 None, 13 ACTIVE-eligible, 14 INACTIVE-ineligible, 15 unknown-ineligible, 16 Pipeline-INACTIVE-nicht-ausgefuehrt (ValueError + kein RUNNING-Item), 17 Pipeline-unknown-nicht-ausgefuehrt, 18 reference.echo-End-to-End intakt) + Extras (Nicht-String, Enum-Mitglieder). Zentrale Funktion direkt getestet, keine Zweit-Logik.

## 6. Ergebnis / Validierung (Schritt 10)

- Neu: 20/20 GRUEN. Verwandt (Worker/Full-Pipeline/Routing/ATS/Event-Hook/Engine/Packaging): 50 passed + 2 Skip (live-gated).
- Gesamt-Suite: 398 passed (Baseline 378 + 20 neu), 8 skipped; 15 failed + 1 ERROR = IDENTISCHE Menge wie Baseline vor Aenderung (pre-existing: platform_handlers/invocation/reference_agent/processing_chain — unberuehrt, kein Bezug zu Status).
- `git diff --check` clean; Secret-Scan negativ (keine Secrets im Diff); nur P7-Dateien geaendert (4x Bestand + 1x neu-Modul + 1x Tests + 2x Reports).

## 7. Keine Migration / Folge-Gaps (Schritte 8/11)

- Migration: NONE (kein DDB-Scan/Write, kein Rewrite, kein TF, kein AWS). Kleinbuchstaben-Seeds funktionieren via Normierung weiter (bestehender `test_agents_filters_inactive` GRUEN). Spaeterer Bestands-Scan (kanonisch GROSS schreiben) OPTIONAL, nicht erforderlich.
- Kanonische Docs: UNVERAENDERT (keine falsche Aussage gefunden — Pipeline-Beschreibungen bleiben gueltig).
- Folge-Gaps (P6-R8): Worker-Entitlement-Re-check · Credential Verification · APIProfile-Authorization · Agent Sandboxing (In-Process-Rollen-Teilung) · `Admin`-Migration.

**HARD STOP (keine weiteren Gates in diesem Auftrag).**
