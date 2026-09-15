# API Documentation Standard

## Purpose and Scope

This document defines the standard for documenting all API interfaces in the Mays Recruiting Intelligence System. It ensures consistency across all teams and enables developers to understand contracts without needing internal implementation details.

---

## 1. Zweck und Scope

Die Dokumentation dient als **verbindlicher Contract** zwischen API-Providern und -Consumern.

**GILT FÜR:**
- Alle REST-API-Endpunkte
- Alle GraphQL-Endpunkte
- Alle internen Service-Contracts

**GILT NICHT FÜR:**
- Interne Python-Klassen/Funktionen
- DynamoDb, SQS, Lambda Interna
- Terraform Konfigurationen

---

## 2. Provider / Consumer

### Provider
- Team oder Service, der die API bereitstellt
- Verantwortlich für Implementierung und Wartung
- Besitzt die Security Boundary

### Consumer
- Team oder Service, der die API verwendet
- Darf nur das dokumentierte Contract nutzen
- Vertritt keine internen Implementation Details

---

## 3. Boundary / Datenfluss

Jede API-Dokumentation muss diese Fragen beantworten:

```
Provider
    ↓ (Contract)
Consumer
```

**Definition der Boundary:**
- Was passiert **innerhalb** des Providers?
- Was passiert **außerhalb** der Boundary?
- Welche Daten überschreiten die Boundary?

---

## 4. Authentication

### Standard
- JWT-Basierte Authentifizierung via Cognito
- Token im `Authorization` Header: `Bearer <JWT>`

### Dokumentationspflicht
- Welcher Auth-Typ wird verwendet?
- Wie wird der Token validiert?
- Welche Claims sind relevant?

---

## 5. Authorization

### Trennung
- **Authentication**: Wer bist du? (Cognito)
- **Authorization**: Was darfst du? (Entitlements)

### Tenant Isolation
- `tenantId` muss in jedem Request verfügbar sein
- Tiere können nur ihre eigenen Daten sehen
- Frontend darf keine tenantId manipulieren

---

## 6. API-Version

### Versionierung
- API-Version im Docstring, nicht im Pfad
- Base-Version: `1.0.0`
- Breaking Changes: Major-Version erhöhen

### Semantik
```
v1.2.3
│   │ │
│   │ └── Patch: Bugfixes, keine Breaking Changes
│   └──── Minor: Neue Features, rückwärtskompatibel
└──────── Major: Breaking Changes
```

---

## 7. Endpoints / Operations

### Struktur
Jeder Endpunkt muss diese Metadaten haben:

| Feld | Typ | Pflicht |
|------|-----|-------|
| Path | string | ✅ |
| Method | GET/POST/PUT/DELETE | ✅ |
| Auth | NONE/JWT | ✅ |
| Auth-Flow | wie Authentifizierung erfolgt | ✅ |
| Purpose | Kurze Beschreibung | ✅ |

### Beispiel

```yaml
GET /me
  Auth: JWT
  Purpose: Returns authenticated user context
  Version: 1.0.0
```

---

## 8. Request

### Schema
- JSON-Format
- STRUKTURIERTE Anforderung
- Keine Semantik verstecken

### Dokumentation
- Request-Field-Beschreibung
- Typ (string, integer, boolean, array, object)
- Pflichtfeld (required)
- Validierungsregeln

### Beispiel

```json
{
  "userId": "uuid-string",
  "tenantId": "string",
  "required": {
    "query": "string"
  },
  "optional": {
    "limit": "integer"
  }
}
```

---

## 9. Response

### Standard-Format

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

### Felder

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| success | boolean | Request erfolgreich? |
| data | object | Ergebnis-Daten |
| error | object/null | Fehler-Details falls vorhanden |

---

## 10. Fehlerverhalten

### Standard-Error-Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

### HTTP-Status-Codes

| Code | Bedeutung |
|------|-----------|
| 200 | OK |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 500 | Internal Error |

---

## 11. synchrone/asynchrone Semantik

### SYNCHRON (HTTP/JSON)
- Direkte Antwort
- Erwartete Latenz: < 100ms
- Blockierender Aufruf

### ASYNCHRON (SQS/DynamoDB)
- Status wird später geprüft
- Token-basiertes Status Abfragen
- Work Item mit UUID

**WICHTIG**: API-Endpoints sind SYNCHRON. Work-Execution ist ASYNCHRON.

---

## 12. Daten, die die Boundary überschreiten

### ERLAUBT
- Nutzer-ID
- Tenant-ID
- JWT Claims
- Status-Informationen

### NIX-ÜBERFOLGEN
- DynamoDb Tabellen-Namen
- SQS Queue URLs
- Lambda Namen
- IAM ARN Strings
- interne Python Module
- Terraform States

---

## 13. Security

### Must-Have
- JWT Validierung
- Tenant Isolation
- Rate Limiting
- Input Validierung

### Must-NICHT
- implement user UI
- handle password reset
- manage Cognito directly

---

## 14. Versionierung

### API Versionierung
- `x-api-version` Header oder
- Document Version Tag

### Comppatibilität
- Breaking Changes: Major erhöhen
- Neue Features: Minor erhöhen
- Bugfixes: Patch erhöhen

---

## 15. Backward Compatibility

### Regeln
- Kein Entfernen alter Endpoints innerhalb Major-Version
- Alte Felder dürfen deprecated bleiben
- Neue Felder müssen optional sein

---

## 16. Contract Tests

### Verpflichtend für Provider
- Request-Validierung testen
- Response-Schema testen
- Auth-Tests
- Tenant Isolation Tests
- Fehlerpfade testen

### Verwenden
- Consumer können gegen Contract testen
- Tests als Integration Reference dienen

---

## 17. Integration Tests

### Testarten
1. **Unit Tests**: Klein und schnell
2. **Contract Tests**: Vertragsgerechtigkeit
3. **Integration Tests**: End-to-End

### Fokus
- Teste nur das, was dokumentiert ist
- Keine Implementation Details

---

## 18. Ownership

| Artefakt | Owner | Change Procedure |
|----------|-------|------------------|
| API Contract | API Owner | PR + Review |
| Documentation | Maintainer | PR + Review |
| Endpoints | Backend Team | PR + Review |
| Security | Security Lead | PR + Review |

---

## 19. Change Procedure

### Breaking Change
1. Neue Major-Version
2. Migration Guide
3. Deprecations ankündigen

### Non-Breaking Change
1. Minor-Version
2. Dokumentation aktualisieren
3. Tests aktualisieren

---

## 20. Future / Non-Goals

### FUTURE
- [ ] GraphQL Support
- [ ] WebSocket Streaming
- [ ] Rate Limiting via API

### NON-GOALS
- Direkter Zugriff auf AWS Services vom Frontend
- Implementierung von Auth/UI
- Deployment

---

## 21. Dokumentations-Linz

Diese Datei muss als Referenz für:
- Neue API-Erstellung
- API-Überarbeitung
- Team-Onboarding

---

## 22. Examples

### Vollständige Endpunkt-Dokumentation

```
### GET /me

**Purpose**: Returns the authenticated user's context.

**Auth**: JWT required in Authorization header.

**Request**: None

**Response**:
```json
{
  "userId": "uuid",
  "email": "user@example.com",
  "tenantId": "tenant-uuid",
  "groups": ["admin", "user"]
}
```

**Errors**:
- 401: Unauthenticated
- 403: Forbidden

**Sync**: Yes (HTTP JSON)

**Boundary Crosses**: userId, tenantId, email from Cognito

**NOT Cross**: DynamoDB table names, JWT signs, Cognito pool id

**Version**: 1.0.0

**Owner**: Platform Team

**Tests**: See tests/test_me_endpoint.py
```

---

## 23. Git

### Commit Message Format

```
docs: [API] add documentation for /me endpoint

- Added /me contract specification
- Added tenant isolation notes
- Added to API doc standard reference

Refs: #123
```

---

### STOPP

Dies ist der API-Dokumentations-Standard.  
Er ist eine Instruktionsdatei, kein Implementierungscode.

Nächste Schritte:
1. docs/API/PLATFORM_FRONTEND_INTEGRATION.md erstellen
2. Projekt-Status aktualisieren
3. Audit Log aktualisieren


---

## 24. Änderungsprotokoll

| Version | Datum | Änderung |
|---------|-------|----------|
| 1.0.0 | 2026-09-15 | Initiale Erstellung |