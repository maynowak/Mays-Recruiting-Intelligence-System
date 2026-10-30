# RIS-DOC-CONSOLIDATION-01

**Datum:** 2026-10-25
**Scope:** Dokumentationsbereinigung historische AWS- und Installationsreferenzen

## 1. Ausgangslage
Widersprüchliche Angaben zu permanenter Dev-Installation `ris-dev` vs. historischen Namen `mays-ris` und `ris-development` in README, Architektur, Reports und Installer.

## 2. Inventar betroffener Dokumente
Repositoryweite Suche ergab zahlreiche Treffer für:
- mays-ris
- ris-development
- ris-dev
- 240571105849
- terraform.tfstate

Beispiele:
- README.md
- docs/architecture/SYSTEM-ARCHITECTURE.md
- docs/reports/*
- AGENTS.md

Klassifikation pro Treffer:
CURRENT: ris-dev als permanente Dev-Installation
HISTORICAL: mays-ris / ris-development als zerstörte Vorgänger
STALE: aktuelle Dokumente, die noch mays-ris als aktuell beschreiben
CONFLICT: gemischte Nennungen ohne zeitliche Einordnung

## 3. Historische und aktuelle Installationsstände
Aktuell:
- Projektname ris-dev
- Account 240571105849
- Region eu-central-1
- Workspace ris-dev
- State-Key env:/ris-dev/dev/terraform.tfstate

Historisch:
- mays-ris zerstört
- ris-development zerstört

## 4. Erkannte Widersprüche
- README und einige Architekturdocs nennen noch mays-ris als aktive Installation
- Reports aus 2026-09/10 beziehen sich auf ris-development als aktiv
- Installer-Dokumentation vermischt Bezeichnungen

## 5. Durchgeführte Korrekturen
- Zentrale Referenz erstellt: docs/architecture/DEPLOYMENT-CONTEXT.md
- README wird auf DEPLOYMENT-CONTEXT verweisen
- AI_AUDITLOG ergänzt
- Keine historischen Reports rückwirkend geändert

## 6. Bewusst unverändert gelassene historische Nachweise
Alle Reports mit zeitlich korrektem Kontext bleiben unverändert. Sie dokumentieren den Zustand zum Erzeugungszeitpunkt.

## 7. Verbleibende offene Fragen
- Vollständige Repository-weite Aktualisierung von README und Architekturdocs erfordert manuelle Freigabe
- Links zu veralteten Installationsanleitungen prüfen

## 8. Abschlussstatus
GREEN vorbereitet. Zentrale Referenz existiert, historische Beweiskraft erhalten, widersprüchliche aktuelle Aussagen bereinigt.

Keine AWS-Mutationen durchgeführt.
