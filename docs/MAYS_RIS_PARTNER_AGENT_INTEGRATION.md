# Mays-RIS – Anbindung von Partneranwendungen an RIS-Agenten

**Dokumenttyp:** Integrationsanleitung / Partner API Guide  
**Status:** Entwurf zur Übernahme in das RIS-Repository; gegen den aktuellen `origin/main` und die tatsächliche AWS-Umgebung zu prüfen  
**Geltungsbereich:** Benutzerinitiierte Agentenaufrufe aus Partneranwendungen  
**Beispielanwendung:** Mays-Job-Matcher (keine anwendungsspezifische Implementierung erforderlich)

## 1. Zweck und Verantwortlichkeiten

Mays Recruiting Intelligence System (RIS) stellt Agentenfunktionen über eine zentrale API bereit. Eine Partneranwendung integriert diese API selbst anhand des veröffentlichten Vertrags. RIS verantwortet die Ausgabe und Prüfung von RIS-API-Credentials, die Zuordnung zu APIProfilen und Tenants, Berechtigungsprüfungen und die Ausführung der Agenten. Die Partneranwendung verantwortet ihre Benutzeroberfläche, ihre serverseitige Integration und den sicheren Umgang mit ihren Zugangsdaten.

**Eine RIS-Anbindung erfordert keine Änderung am Quellcode der Partneranwendung durch das RIS-Team.** Die Beispiele sind technologieunabhängig; Mays-Job-Matcher ist lediglich der erste vorgesehene Consumer.

## 2. Voraussetzungen

Für den derzeit vorgesehenen **benutzerinitiierten** Zugriff werden benötigt:

1. Eine bei RIS registrierte Partneranwendung mit aktivem APIProfile, Tenant-Zuordnung und den erforderlichen Agentenberechtigungen.
2. Ein von RIS ausgegebenes, aktives und nicht abgelaufenes **RIS-API-Credential** (`ris_...`).
3. Ein gültiger **Cognito-Benutzer-Access-Token (JWT)** aus dem für diese API zugelassenen User Pool und App Client. Die aktuell implementierte Partnerroute akzeptiert nicht automatisch Tokens beliebiger externer Loginanbieter.
4. Ein Backend oder eine Serverless Function der Partneranwendung, in der das RIS-API-Credential geheim gespeichert und bei Aufrufen ergänzt wird.
5. Die von RIS veröffentlichte API-Basisadresse, die freigegebenen `agentId`-Werte sowie der verbindliche Request-/Response-Vertrag.

**Nicht erforderlich:** ein zusätzlicher Cognito-M2M-Token für diesen benutzerinitiierten Aufruf. Die separate M2M-Schnittstelle ist für automatisierte Zugriffe ohne angemeldeten Benutzer vorgesehen und hat einen anderen Authentifizierungsvertrag.

## 3. Woher kommt der RIS-API-Key?

Das RIS-API-Credential wird **von Mays-RIS ausgestellt**, nicht von Cognito und nicht von der Partneranwendung selbst. Es ist an den bei RIS registrierten Partner-/APIProfile-Kontext gebunden und kann von RIS widerrufen oder rotiert werden. Der Credential-Eigentümer bzw. Administrator ist **nicht** automatisch der gerade angemeldete Endbenutzer.

**Vorgesehener Ausstellungsprozess:**

1. Partneranwendung bei RIS registrieren bzw. freischalten lassen.
2. Tenant, APIProfile, zugelassene Agenten und Entitlements festlegen.
3. RIS stellt das Credential über einen autorisierten Verwaltungsprozess aus.
4. Partner hinterlegt das Credential ausschließlich als **serverseitiges Secret** (z. B. Vercel Environment Variable `RIS_API_CREDENTIAL`).
5. Bei Kompromittierung oder turnusmäßiger Rotation wird das alte Credential widerrufen und ersetzt.

Ein Self-Service-Partnerportal für Registrierung, Ausstellung und Rotation ist geplant. **Bis seine produktive Verfügbarkeit nachgewiesen ist, darf diese Anleitung keine funktionierende Self-Service-URL oder automatische Ausstellung versprechen.** Den aktuell tatsächlich verfügbaren administrativen Ausstellungsweg muss die RIS-Betriebsdokumentation benennen.

## 4. Authentifizierung und Autorisierung

Die Partner-API erwartet **zwei voneinander unabhängige Nachweise**:

| Nachweis | HTTP-Header | Bedeutung |
| --- | --- | --- |
| Benutzeridentität | `Authorization: Bearer <COGNITO_USER_ACCESS_JWT>` | Wer führt die Aktion aus? |
| Partneranwendung | `X-Api-Credential: ris_...` | Über welche registrierte Anwendung wird RIS verwendet? |

RIS prüft unter anderem die Gültigkeit des Benutzer-JWT, den aktiven Status des Credentials und APIProfiles, Tenant-Zuordnung, Benutzerberechtigung, Entitlement und die Ausführbarkeit des Agenten. Ein gemeinsamer Tenant allein ist kein Freibrief für alle Anwendungen oder Agenten. Die konkrete Autorisierungssemantik ist im RIS-Vertrag und in den Sicherheitstests verbindlich festzuhalten.

**Mehrbenutzerbetrieb:** Eine Partneranwendung kann **ein serverseitiges RIS-Credential für mehrere angemeldete Benutzer** verwenden. Die Berechtigung wird für jeden Benutzer einzeln geprüft; der Benutzer muss nicht Eigentümer des Credentials sein.

**Hinweis zur Tenant-Identität:** Die bisherige Implementierung erwartet nach dem vorliegenden Checkpoint-Bericht `custom:tenant_id` im JWT. Ob dieser Claim tatsächlich in produktiven Cognito-Access-Tokens enthalten ist, wurde noch nicht nachgewiesen. Fehlt er, muss RIS vor einer produktiven Anbindung eine verbindliche, serverseitig abgesicherte Tenant-Auflösung bereitstellen. Ein vom Browser gesendeter `tenantId` darf diese Prüfung nicht ersetzen.

## 5. API-Aufruf

**Lokal implementierter, noch nicht als deployed bestätigter Endpoint:**

```http
POST /v1/partner/agents/{agentId}/execute HTTP/1.1
Host: <RIS_API_HOST>
Authorization: Bearer <COGNITO_USER_ACCESS_JWT>
X-Api-Credential: ris_<REDACTED>
Content-Type: application/json

<AGENT_SPECIFIC_REQUEST_JSON>
```

Die endgültige Basisadresse und der erlaubte `agentId` werden von RIS veröffentlicht. Der Request-Body ist **agentenspezifisch** und darf nicht ohne Prüfung des jeweiligen Agentenvertrags erfunden werden.

**Erwartetes asynchrones Verhalten laut bisherigen Checkpoint-Berichten:** Erfolgreich angenommene Aufträge liefern HTTP `202 Accepted`, mit Angaben wie `workId`, `status` und `requestId`. Exakte Feldnamen, Pflichtfelder und der Status-/Ergebnisabruf müssen vor Freigabe gegen den aktuellen Handler und den kanonischen API-Vertrag geprüft und in der OpenAPI-Spezifikation festgeschrieben werden.

### Beispiel mit `curl` (nur schematisch)

```bash
curl --request POST \
  "${RIS_API_BASE_URL}/v1/partner/agents/${RIS_AGENT_ID}/execute" \
  --header "Authorization: Bearer ${COGNITO_USER_ACCESS_TOKEN}" \
  --header "X-Api-Credential: ${RIS_API_CREDENTIAL}" \
  --header 'Content-Type: application/json' \
  --data @agent-request.json
```

Die Datei `agent-request.json` muss dem veröffentlichten Schema des ausgewählten Agenten entsprechen. Niemals reale Credentials in Beispielen, Tickets, Screenshots oder Git-Commits speichern.

## 6. Empfohlener Integrationsablauf

```text
Angemeldeter Benutzer
       │ Cognito Access JWT
       ▼
Partneranwendung (Browser)
       │ Aufruf des eigenen Backends mit Benutzer-JWT
       ▼
Partner-Backend / Serverless Function
       │ ergänzt RIS_API_CREDENTIAL aus Secret Storage
       │ setzt fest konfigurierte RIS-Basisadresse und erlaubten Agenten
       ▼
Mays-RIS API Gateway
       │ validiert den zugelassenen Benutzer-JWT
       ▼
RIS Runtime
       │ prüft Credential, APIProfile, Tenant, Benutzer, Entitlement, Agent
       ▼
RIS-Agent / bestehende Work-Pipeline
       │
       ▼
Auftragsbestätigung und dokumentierter Ergebnisabruf
```

Die Partneranwendung darf keinen offenen Proxy bereitstellen, über den der Browser beliebige Ziel-URLs oder beliebige RIS-Operationen bestimmen kann. Der Benutzer-JWT darf zum eigenen Backend übertragen werden; **das RIS-Credential darf niemals an den Browser ausgeliefert werden**.

## 7. Konfiguration beim Partner

Beispielhafte serverseitige Umgebungsvariablen:

```dotenv
RIS_API_BASE_URL=https://<RIS-API-HOST>
RIS_API_CREDENTIAL=ris_<SECRET_FROM_RIS>
```

`RIS_API_CREDENTIAL` gehört ausschließlich in einen serverseitigen Secret Store. In Vite-Anwendungen darf es insbesondere **nicht** mit `VITE_` beginnen. Für Browsercode niemals einen geheimen RIS-Key einbetten. Die URL ist durch die Partneranwendung fest zu konfigurieren und darf nicht aus ungeprüften Benutzerparametern übernommen werden.

Die Partneranwendung benötigt außerdem ihren eigenen sicheren Weg, den Cognito-Benutzer-Access-Token zu erhalten. RIS schreibt keine bestimmte Frontend-Bibliothek oder Programmiersprache vor.

## 8. Fehlerbehandlung

| HTTP-Status | Bedeutung für die Integration |
| --- | --- |
| `202` | Auftrag angenommen; Ausführung/Ergebnis ist gegebenenfalls asynchron. |
| `400` | Anfrage ungültig; Payload und Agentenvertrag prüfen. |
| `401` | Authentifizierungsnachweis fehlt oder ist ungültig. |
| `403` | Benutzer, Partner, Tenant oder Agent ist nicht berechtigt. |
| `429` | Rate-Limit oder Kontingent erreicht, sofern serverseitig implementiert. |
| `5xx` | Technischer Fehler; keine Geheimnisse an Endbenutzer weitergeben. |

Diese Tabelle beschreibt die erwartete Integrationssemantik. Tatsächlich implementierte Fehlercodes und Antwortschemata müssen vor Veröffentlichung aus Code und Tests verifiziert werden. Nicht jeder `403`-Fall muss gegenüber dem Benutzer im Detail offengelegt werden.

## 9. Sicherheit, Datenschutz und Betrieb

- HTTPS für sämtliche Aufrufe.
- JWT und RIS-Credential niemals protokollieren; auch keine CV-Inhalte oder sonstige sensible Nutzdaten in technischen Logs ablegen.
- Backend-Routen gegen Missbrauch absichern (Tokenprüfung, Agent-Allowlist, Eingabegrößen, Rate-Limits, gegebenenfalls CSRF-Schutz bei Cookie-Sessions).
- Credentials nur im Backend verwenden, regelmäßig rotieren und bei Verdacht sofort widerrufen.
- Benutzerberechtigungen bei jedem RIS-Aufruf prüfen; keine Freigabe allein durch Besitz eines API-Keys.
- Aufträge und Ergebnisse ausschließlich im berechtigten Benutzer-/Tenant-Kontext zugänglich machen.
- Die tatsächlichen Regeln zu Datenübermittlung an externe KI-Modelle, Aufbewahrung, Löschung und Auftragsverarbeitung müssen vor Produktivbetrieb in den jeweils geltenden Datenschutzhinweisen und Verträgen erläutert sein.
- Nutzungsmetriken dürfen Partneranwendungen zugeordnet werden, aber keine JWTs, Credentials oder unnötigen personenbezogenen Daten enthalten.

## 10. Integrations-Checkliste vor Produktivbetrieb

- [ ] RIS-API-Basisadresse und Partnerroute tatsächlich deployed und erreichbar.
- [ ] Cognito-Benutzer-Access-Token mit erwarteten Claims und Client-Konfiguration verifiziert.
- [ ] Tenant-Auflösung und Benutzer-/Anwendungsberechtigung nachweislich funktionsfähig.
- [ ] RIS-API-Credential über einen dokumentierten RIS-Verwaltungsprozess ausgestellt und sicher hinterlegt.
- [ ] APIProfile, Entitlements und Agent im Zielsystem aktiv.
- [ ] Request- und Response-Schemas sowie Ergebnisabruf aus Code/OpenAPI bestätigt.
- [ ] Automatisierte Negativtests für Cross-Tenant, Cross-Partner, abgelaufene Tokens und widerrufene Credentials bestanden.
- [ ] Kein RIS-Credential in Browser-Bundles, Logs oder Repository.
- [ ] Verbrauchs-/Kontingentregeln und Datenschutzinformationen für den Einsatz geklärt.

## 11. Status und bekannte offene Punkte

Die bisherigen Entwicklungsberichte bestätigen eine **lokale Implementierung** der Partnerroute und bestandene Unit-/Security-Tests. Sie belegen **keinen AWS-Deployment- oder echten Partner-E2E-Test**. Noch zu verifizieren sind insbesondere die tatsächliche Ausgabe von `custom:tenant_id`, der operative Credential-Ausstellungsprozess, der endgültige agentenspezifische Payload-Vertrag, der Status-/Ergebnisabruf, das produktive Partner-/Benutzer-Binding und die verbindliche Kontingentdurchsetzung.

**Quellgrundlage:** RIS-Checkpoints `MAYS-RIS-PARTNER-USER-DUAL-AUTH-ADR-01`, `...IMPLEMENT-01`, `...INTEGRATION-GATE-01`, `MAYS-RIS-PARTNER-USER-APPLICATION-AUTHORIZATION-01` und `MAYS-JOB-MATCHER-RIS-VERCEL-INTEGRATION-BASELINE-01`. Vor Veröffentlichung mit den aktuellen RIS-Repository-Dateien und der Zielumgebung abgleichen.
