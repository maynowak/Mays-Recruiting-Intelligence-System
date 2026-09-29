# RIS-API-GATEWAY-CONTRACT-03

## 1. Ausgangslage

Aus OPENAPI-01 (1 Artefakt, JobSearch-only) + HANDLER-02 (1 Lambda, v2-vs-REST-Bruch, Execute ohne GW-Route). Hier: formaler Gateway↔Lambda-Vertrag, keine Re-Analyse der Gesamtarchitektur.

## 2. Tatsächliche API-Gateway-Konfiguration

`aws_apigatewayv2_api.ris_api` (HTTP, `${project}-${env}-api`); Stage `$default`
(auto_deploy); JWT-Authorizer (audience = Client-ID, issuer = Pool-Endpoint);
EINE Integration (`AWS_PROXY` → `invoke_arn`, **payload_format_version 2.0**);
5 Routen (health NONE, Rest JWT): `GET /health|/platform|/me|/me/profile|/agents`.
Variablen: Standard (project/environment/cognito/lambda); keine Besonderheiten.

## 3. Payload-Format

GW liefert 2.0 (PROVEN: api/main.tf:39). Handler erwartet REST-v1-Felder
(PROVEN: handler.py-Dispatch auf `httpMethod`/`path`).

## 4. Event-Feld-Matrix

| Feld | Gateway liefert | Handler verwendet | Ergebnis |
|---|---|---|---|
| version/routeKey/rawPath/requestContext.http | JA (v2) | NEIN (Grep 0) | IGNORIERT |
| httpMethod/path | NEIN (v2) | JA (Dispatch) | FEHLT → Default `/`+GET |
| pathParameters/body | JA | JA | OK |
| requestContext.authorizer.jwt.claims | JA (bei JWT-Routen) | JA | OK |

BRUCH ausdrücklich bestätigt (nicht repariert).

## 5. Route-Matrix

| Route | Gateway | Handler | Dokumentiert | Ergebnis |
|---|---|---|---|---|
| GET /health | JA (NONE) | NEIN (404) | — | GATEWAY_ONLY |
| GET /platform|/me|/me/profile|/agents | JA (JWT) | JA | PLATFORM_FRONTEND_INTEGRATION | BOTH |
| POST /api/agents/{id}/execute | NEIN | JA (+Tests) | Handler-Docstring | HANDLER_ONLY |
| /me/jobsearches*, /work* | NEIN | JA | — | HANDLER_ONLY |

## 6. Runtime-Dispatch (statisch, NICHT live)

GW-Route → v2-Event → `httpMethod` None → kein Records → `_handle_api_event`
(path `/`, GET) → KEIN Branch → 404. Mit gültigem JWT: Lambda-404; ohne:
GW-401/403 (Authorizer VOR Lambda). Statisch ableitbar, live UNVERIFIED.

## 7. /api/agents/{agentId}/execute

Handler JA (401/403/404-Gates + Tests test_execute_agent[_unauthorized] mit
REST-Events); GW-Route NEIN; API-Doku: nur Docstring; externer Aufruf: KEIN
Beleg (keine GW-Route = nicht erreichbar); Work-Erzeugung + SQS: JA (Code).
Absicht öffentlich: UNKNOWN.

## 8. /health

GW-Route JA (NONE, Grund UNDOKUMENTIERT — kein Kommentar/Test/Doku);
Handler-Branch NEIN → statisch 404. Historie: nicht untersucht (kein Beleg);
keine Spekulation.

## 9. /me/jobsearches* und /work*

Handler JA (CRUD + Work-Create/Get); Tests: JobSearch-Handler-Tests (REST-Events);
interne Aufrufer: KEINE (kein Code ruft sie auf); GW-Routen: NEIN; Doku: KEINE
(als Routen); Intern-Status: UNKNOWN (weder als intern markiert noch belegt).

## 10. OpenAPI-Bezug

`jobsearch/openapi.yaml` beschreibt NICHT die Platform API (Pfade `/v1/*` vs.
implementiert `/me`, `/agents`; keine Extensions/Integrationen). KEINE
Spec-Erweiterung, KEINE Platform-Spec, KEINE Extensions (Ticket-Vorgabe).

## 11. Vertragsoptionen (keine Auswahl)

A) v2 behalten → Handler auf v2 ausrichten (Dispatch auf routeKey/rawPath;
Tests auf v2-Events; Auswirkung: Handler-Umbau + Test-Umbau).
B) Handler-Modell behalten → GW auf v1-Format (z. B. payload 1.0 oder REST-API;
Auswirkung: TF-Änderung + mögliche Stage-Neudeploy; 404-Verhalten für v2-Clients).
C) Adapter: NICHT VORHANDEN (Grep-leer PROVEN) — keine bestehende Schicht.

## 12. Offene Punkte

v2-Laufzeit-Wirkung (UNVERIFIED); Execute-/JobSearch-/Work-GW-Anbindung
(Absicht UNKNOWN); `/health`-Grund (UNKNOWN); SQS-Receive-Herkunft (fremder
Scope); batch_size (Runtime).

## 13. Schlussfolgerung

Bestehender Vertrag: HTTP-API (v2, JWT) → 1 Lambda → REST-Dispatch. Wirksam:
JWT-Gates + Claims-Kette funktionieren; Routen-Dispatch ist für GW-Events
statisch 404-seitig (v2-Felder ungenutzt); Execute-Funktionalität existiert,
ist aber per GW unerreichbar; JobSearch-Spec deckt Platform NICHT ab. Jede
Änderung (A/B/C) braucht Review-Entscheid.

---

*Gate: RIS-API-GATEWAY-CONTRACT-03 · Muster aus AI_AUDITLOG.md · nur Bestand ·
kein Umbau · keine AWS-Mutation.*
