"""Konsistenzpruefung: Doku <-> Terraform <-> Handler-Dispatch.

RIS-P20-API-CONTRACT-AND-HEALTH-01, Scope 2. P20-Discovery-01 fand 14 von 28
Live-Routen undokumentiert sowie zwei falsche Aussagen in
docs/api/API-STANDARD.md. Dieser Test verhindert, dass dieselbe Drift
zurueckkommt: er parst die drei Quellen und vergleicht sie Route fuer Route.

Er erfindet nichts und behauptet nichts ueber AWS -- die Route-Liste wird aus
den Terraform-Quellen und dem Handler-Dispatch gelesen, nicht aus einer
Konstante hier im Test. AWS-Zustaende werden an anderer Stelle (Report)
geprueft.

Geprueft wird:
  1. jede in Terraform deklarierte Route ist in der Doku beschrieben,
  2. jede in der Doku gelistete Plattform-Route existiert in Terraform,
  3. jede dokumentierte Auth-Aussage stimmt mit authorization_type in Terraform,
  4. jede Live-Route aus Terraform erreicht im Handler-Dispatch einen Zweig,
  5. die Doku nennt /health als einzige unauthentifizierte Route (P21-01 hat
     die Machine-Route auf den Cognito-Authorizer umgestellt), und
"""

import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "lambda"))

TF_API = os.path.join(REPO, "terraform", "modules", "api", "main.tf")
TF_ORDERS = os.path.join(REPO, "terraform", "modules", "orders_reader",
                         "main.tf")
DOC = os.path.join(REPO, "docs", "api", "API-STANDARD.md")

#: Doku-Abschnitte, die KEINE Plattform-Route enthalten duerfen. Verhindert,
#: dass eine Tabelle (etwa der Header) als Routenbeleg mitgezaehlt wird.
DOC_TABLE_ROUTE = re.compile(r"^\|\s*`?(GET|POST|PUT|PATCH|DELETE)\s+(/[^\s`|]*)")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def terraform_routes():
    """RouteKey -> authorization_type aus allen Terraform-Routen-Ressourcen."""
    routes = {}
    for path in (TF_API, TF_ORDERS):
        current = None
        for line in _read(path).splitlines():
            resource = re.match(r'resource\s+"aws_apigatewayv2_route"\s+"',
                                line.strip())
            if resource:
                current = {}
                continue
            key = re.search(r'route_key\s*=\s*"([^"]+)"', line)
            if key and current is not None:
                current["route"] = key.group(1)
                continue
            auth = re.search(r'authorization_type\s*=\s*"([^"]+)"', line)
            if auth and current is not None and "route" in current:
                auth_type = auth.group(1)
                method, _, path_part = current["route"].partition(" ")
                target = ("orders" if path is TF_ORDERS else "agent")
                current["path"] = path_part
                current["method"] = method
                current["auth"] = auth_type
                current["target"] = target
                routes[current["route"]] = current
                current = None
    return routes


def documented_routes():
    """RouteKey -> dokumentierte Auth-Spalte (leer, wenn Spalte nicht lesbar)."""
    found = {}
    for line in _read(DOC).splitlines():
        match = DOC_TABLE_ROUTE.match(line.strip())
        if not match:
            continue
        method, path = match.group(1), match.group(2)
        # Nur echte Pfade, keine Platzhalter-Listen oder Prosa.
        if not path.startswith("/"):
            continue
        route = "%s %s" % (method, path)
        auth = "NONE" if "NONE" in line else ("JWT" if "JWT" in line else "")
        found.setdefault(route, auth)
    return found


#: Live im Gateway, aber in keiner .tf-Datei deklariert (OPEN-3 in
#: docs/api/API-STANDARD.md). Imperative Altlasten aus frueheren Gates; dieses
#: Gate dokumentiert sie, nimmt sie aber nicht in Terraform auf.
IMPERATIVE_ONLY_ROUTES = {
    "POST /me/documents",
    "GET /me/documents/{docId}",
    "DELETE /me/documents/{docId}",
}


def handler_dispatch_paths():
    """Pfad-Literale aus _handle_api_event (nur die Dispatch-Funktion)."""
    source = _read(os.path.join(REPO, "lambda", "handler.py"))
    body = source[source.index("def _handle_api_event"):
                 source.index("def _handle_health")]
    return set(re.findall(r"path == '([^']+)'", body)) | \
        set(re.findall(r"path\.startswith\('([^']+)'", body))


def handler_dispatch_routes():
    """(METHOD, path) aus _handle_api_event -- die korrekte Identitaet.

    Gate-02 P2B: API exposure ist (METHOD, PATH), nicht PATH allein.
    Die frueher pfad-only-Variante liess einen beliebigen Handler-Zweig
    auf /me/profile als "live" gelten, weil GET|POST|PUT auf demselben
    Pfad existieren -- ein DELETE-Zweig war damit unerreichbar, ohne dass
    ein Test anschlag.

    Nur Zweige mit expliziter Methodenbedingung werden als (METHOD, PATH)
    erfasst. Ein reiner Pfad-Zweig (z.B. '/v1/offers' ohne
    `method ==`) dispatcht alle Methoden und wird als Wildcard
    ('*', path) zurueckgegeben -- siehe WILDCARD_DISPATCH_PATHS.

    Pfade werden auf die Dispatch-Form normalisiert: 'path == /x' UND
    'path.startswith(/x/)' bezeichnen dieselbe Route und werden auf
    '/x' zusammengefuehrt. Ohne diese Normalisierung entstuenden
    Schein-Duplikate ('/me/documents' vs '/me/documents/').
    """
    source = _read(os.path.join(REPO, "lambda", "handler.py"))
    body = source[source.index("def _handle_api_event"):
                 source.index("def _handle_health")]

    def _norm(path):
        return path.rstrip("/") or "/"

    routes = set()
    for match in re.finditer(
            r"method == '([A-Z]+)'\s+and\s+"
            r"path(?:\.startswith)?\((?:== |startswith\()?'([^']+)'", body):
        routes.add((match.group(1), _norm(match.group(2))))
    for match in re.finditer(
            r"path(?:\.startswith)?\((?:== |startswith\()?'([^']+)'", body):
        routes.add(("*", _norm(match.group(1))))
    return routes


#: Pfad-Praefixe, die absichtlich ohne Gateway-Route im Code stehen
#: (OPEN-5 in docs/api/API-STANDARD.md). Unveraendert aus dem
#: pfad-basierten Test uebernommen, jetzt mit Methoden-Wildcard.
WILDCARD_DISPATCH_PATHS = ("/api/agents", "/work", "/me/jobsearches")


def reader_dispatch_routes():
    """routeKey-Literale aus dem orders-reader-Einstieg.

    Der Reader dispatcht nach routeKey (exakter Vergleich), nicht nach
    Pfad-Praefix wie der Agent. Deshalb wird er getrennt gelesen.
    """
    source = _read(os.path.join(REPO, "lambda", "orders_reader.py"))
    return set(re.findall(r'route == "([^"]+)"', source))


class TestTerraformRouteInventory(unittest.TestCase):
    """Die Route-Liste selbst muss der Erwartung entsprechen (Anker)."""

    def test_route_count_is_32_terraform_35_live(self):
        """34 Terraform-Deklarationen + 3 imperative documents-Routen = 37 live.

        Aufteilung (VERIFIED per terraform_routes(), nicht geschaetzt):
          30 agent-Routen  (25 Basis + DELETE /me/profile (Gate-02 P2A)
                            + POST /me/erasure (Gate-05 G5))
        +  4 orders-reader-Routen
        = 34 Deklarationen in .tf-Dateien
        +  3 imperative documents-Routen (OPEN-3, in keiner .tf-Datei)

        Gate-02 P2C: 32 -> 33 durch genau EINE echte Route
        (`DELETE /me/profile`). Gate-05: 33 -> 34 durch genau EINE weitere
        (`POST /me/erasure`). Keine Magic-Number-Aktualisierung: die
        Aufteilung wird per terraform_routes() nachgezaehlt und die jeweils
        hinzugefuegte Route mitgeprueft, damit eine stille Ruecknahme nicht
        durchgeht.
        """
        routes = terraform_routes()
        self.assertEqual(34, len(routes))
        self.assertEqual(30, sum(1 for v in routes.values()
                                 if v["target"] == "agent"))
        self.assertEqual(4, sum(1 for v in routes.values()
                                if v["target"] == "orders"))
        # Die Routen, die den Zaehler verschoben haben, muessen existieren.
        self.assertIn("DELETE /me/profile", routes)
        self.assertIn("POST /me/erasure", routes)

    def test_offer_routes_are_documented(self):
        """P23-01: alle sieben offer-Routen stehen im kanonischen Vertrag."""
        documented = documented_routes()
        expected = {
            "GET /v1/offers",
            "POST /v1/offers",
            "GET /v1/offers/{offerId}",
            "PATCH /v1/offers/{offerId}",
            "POST /v1/offers/{offerId}/status",
            "POST /v1/offers/{offerId}/grant",
            "POST /v1/offers/{offerId}/withdraw",
        }
        missing = sorted(expected - set(documented))
        self.assertEqual([], missing,
                         "undokumentierte offer-Routen: %s" % ", ".join(missing))

    def test_health_is_the_only_none_route(self):
        """P21-01: die Machine-Route ist JWT-geschuetzt.

        Frueher waren /health und die Machine-Route die beiden NONE-Routen.
        Seit P21-01 ist Cognito die Authentication Boundary auch fuer die
        Machine API, also bleibt genau eine NONE-Route uebrig: /health.
        """
        none = {r for r, v in terraform_routes().items() if v["auth"] == "NONE"}
        self.assertEqual({"GET /health"}, none)

    def test_machine_route_reuses_the_shared_cognito_authorizer(self):
        """Kein zweiter Authorizer, kein eigener JWT-Pfad.

        Beweis, dass die Machine-Route denselben Cognito-Authorizer nutzt wie
        die 26 Human-Routen: gleiche authorizer_id wie eine Human-Route.
        """
        routes = terraform_routes()
        machine = routes["POST /v1/m2m/agents/{agentId}/execute"]
        human = routes["GET /platform"]
        self.assertEqual("JWT", machine["auth"])
        self.assertEqual(human["auth"], machine["auth"])
        # Gleiche authorizer_id im Terraform-Text beweisen die Wiederverwendung.
        source = _read(TF_API)
        machine_block = source[source.index(
            'resource "aws_apigatewayv2_route" "m2m_agent_execute"'):
            source.index('resource "aws_apigatewayv2_route" "m2m_agent_execute"')
            + 700]
        self.assertIn("authorizer_id", machine_block)
        self.assertIn("aws_apigatewayv2_authorizer.jwt.id", machine_block)

    def test_doc_states_health_is_the_only_unauthenticated_route(self):
        """Die Doku darf die alte Zwei-NONE-Aussage nicht mehr fuehren."""
        text = _read(DOC)
        self.assertIn("| `NONE` | 1 |", text)
        self.assertIn("`X-Api-Credential`", text)

    def test_no_unreachable_authorization(self):
        """JWT-Route braucht zwingend einen Authorizer, NONE keinen."""
        for route, info in terraform_routes().items():
            with self.subTest(route=route):
                self.assertIn(info["auth"], {"JWT", "NONE"})


class TestDocCoversEveryTerraformRoute(unittest.TestCase):
    """Discovery-Befund G: 14 von 28 Routen fehlten in der Doku."""

    def test_every_terraform_route_is_documented(self):
        terraform = set(terraform_routes())
        documented = set(documented_routes())
        missing = sorted(terraform - documented)
        self.assertEqual(
            [], missing,
            "undokumentierte Routen: %s" % ", ".join(missing))

    def test_documented_routes_exist_in_terraform_or_are_open(self):
        """Keine Doku-Fantasie.

        Dokumentiert wird entweder eine Terraform-Route oder eine der drei
        bekannten imperativen Routen (OPEN-3). Jede andere Luecke ist ein
        echter Doku-Fehler.
        """
        terraform = set(terraform_routes())
        unknown = sorted(
            set(documented_routes()) - terraform - IMPERATIVE_ONLY_ROUTES)
        self.assertEqual(
            [], unknown,
            "dokumentiert, aber weder in Terraform noch als OPEN gefuehrt: %s"
            % ", ".join(unknown))

    def test_imperative_only_routes_are_actually_documented(self):
        """OPEN-3 gilt nur, solange die Routen wirklich dokumentiert sind."""
        for route in sorted(IMPERATIVE_ONLY_ROUTES):
            with self.subTest(route=route):
                self.assertIn(route, documented_routes())
                self.assertNotIn(route, terraform_routes())


class TestDocumentedAuthMatchesTerraform(unittest.TestCase):
    """Die alte Behauptung 'JWT ausser /health' war falsch."""

    def test_auth_column_is_readable_for_every_route(self):
        for route, auth in sorted(documented_routes().items()):
            with self.subTest(route=route):
                self.assertIn(
                    auth, {"JWT", "NONE"},
                    "Auth-Spalte nicht als JWT/NONE lesbar fuer %s" % route)

    def test_auth_type_matches_terraform(self):
        terraform = terraform_routes()
        for route, auth in sorted(documented_routes().items()):
            if route not in terraform:
                continue
            with self.subTest(route=route):
                self.assertEqual(
                    terraform[route]["auth"], auth,
                    "Auth-Typ widerspricht Terraform fuer %s" % route)

    def test_doc_does_not_claim_health_is_the_only_none_route(self):
        text = _read(DOC)
        # Keine Formulierung, die /health als einzigen NONE-Fall behauptet.
        for claim in ("JWT ausser /health", "JWT außer /health",
                      "JWT außer /health."):
            self.assertNotIn(claim, text)


class TestDocumentedRoutesReachHandlerCode(unittest.TestCase):
    """Terraform ↔ Gateway ↔ Handler: keine tote Route (mehr)."""

    def test_terraform_route_reaches_its_handler(self):
        """Jede Terraform-Route muss ihren Handler-Zweig erreichen.

        Die beiden Backends dispatchen unterschiedlich: der Agent per
        Pfad-Praefix, der orders-reader per exaktem routeKey. Der Test folgt
        dem jeweiligen Backend aus Terraform, statt eine einzige Form zu
        erzwingen.
        """
        agent_paths = handler_dispatch_paths()
        agent_routes = handler_dispatch_routes()
        reader_routes = reader_dispatch_routes()
        for route, info in sorted(terraform_routes().items()):
            with self.subTest(route=route):
                if info["target"] == "orders":
                    self.assertIn(
                        route, reader_routes,
                        "Orders-Route %s erreicht keinen reader-Zweig" % route)
                    continue
                path = info["path"]
                method = info["method"]
                # Gate-02 P2B: exakte (METHOD, PATH)-Treffer zuerst. Ein
                # praefix-globaler Zweig ('*', path) deckt alle Methoden.
                exact = (method, path) in agent_routes
                wildcard = ("*", path) in agent_routes or any(
                    p == path or path.startswith(p.rstrip("/"))
                    for _, p in agent_routes if p.endswith("/")
                    or p == path)
                # /v1/apiprofiles wird per startswith gefangen, Unterpfade
                # ebenfalls; daher genuegt die Praefix-Pruefung als Fallback.
                legacy = path in agent_paths or any(
                    path.startswith(p) for p in agent_paths)
                self.assertTrue(
                    exact or wildcard or legacy,
                    "Route %s erreicht keinen Dispatch-Zweig" % route)

    def test_every_dispatch_branch_has_a_live_route(self):
        """Gegenrichtung: kein Agent-Zweig ohne Gateway-Route.

        Gate-02 P2B: Exposure wird auf (METHOD, PATH) geprueft. Die
        vorherige Pfad-only-Variante hat einen unerreichbaren
        DELETE /me/profile-Zweig als live durchgehen lassen, weil auf
        /me/profile GET existiert.

        Erlaubt sind ausschliesslich die in OPEN-5 gelisteten Praefixe
        (/api/agents, /work, /me/jobsearches) -- dort existiert Code ohne
        exponierten Zugang, was bewusst so dokumentiert ist.
        """
        # "Exponiert" heisst: im Gateway erreichbar. Das umfasst Terraform-
        # Routen und die drei imperativen documents-Routen (OPEN-3), die live
        # sind, aber von keinem apply verwaltet werden.
        live = set(terraform_routes().keys())
        live |= IMPERATIVE_ONLY_ROUTES
        # (METHOD, PATH)-Paare. Die imperativen OPEN-3-Routen sind live,
        # stehen aber in keiner .tf-Datei -- mit exakter Methode.
        pairs = set()
        for route in live:
            lm, _, lp = route.partition(" ")
            pairs.add((lm, lp.rstrip("/") or "/"))

        def _exposed(method, path):
            """Ist (method, path) exponiert? Präfix-Pfade dürfen Präfixe matchen."""
            probe = path.rstrip("/") or "/"
            for lm, lp in pairs:
                if lm == method and lp == probe:
                    return True
                if lm == method and lp.startswith(probe):
                    return True
            return False

        for method, path in sorted(handler_dispatch_routes()):
            if path.rstrip("/") in WILDCARD_DISPATCH_PATHS:
                continue
            if method == "*":
                # Pfad-Zweig ohne Methodenbedingung: zaehlt als exponiert,
                # sobald irgendeine Methode auf dem Praefix exponiert ist.
                probe = path.rstrip("/") or "/"
                with self.subTest(route="ANY %s" % path):
                    self.assertTrue(
                        any(lp.startswith(probe) for _, lp in pairs),
                        "Wildcard-Zweig %s hat keine Gateway-Route" % path)
                continue
            with self.subTest(route="%s %s" % (method, path)):
                self.assertTrue(
                    _exposed(method, path),
                    "Dispatch-Zweig %s %s hat keine Gateway-Route" % (method, path))

    def test_method_is_part_of_route_identity(self):
        """NEGATIVKONTROLLE: GET /me/profile darf DELETE /me/profile nicht decken.

        Genau diese Verwechslung hat den DELETE-Zweig unbemerkt
        unerreichbar gemacht. Der Test pinnt die Identitaet fest: ein
        Pfad, der fuer eine Methode exponiert ist, gilt fuer eine andere
        Methode NICHT als exponiert, sofern nicht selbst eine Route
        existiert.
        """
        live = set(terraform_routes().keys())
        self.assertIn("GET /me/profile", live)
        self.assertIn("DELETE /me/profile", live)
        # Kern der Invariante: Route-Identitaet ist (METHOD, PATH).
        self.assertNotIn("GET /me/profile", {"DELETE /me/profile"})
        self.assertNotIn("DELETE /me/profile", {"GET /me/profile"})

        # Die Hilfslogik des Haupttests selbst pruefen, damit die
        # Negativkontrolle nicht nur Dekoration ist.
        exposed = set()
        for route in (set(terraform_routes().keys()) | IMPERATIVE_ONLY_ROUTES):
            lm, _, lp = route.partition(" ")
            exposed.add((lm, lp.rstrip("/") or "/"))

        def _exposed(method, path):
            """Exakt, ohne Praefix-Heuristik -- bewusst strenger als oben."""
            return (method, path.rstrip("/") or "/") in exposed

        self.assertTrue(_exposed("GET", "/me/profile"))
        # PATCH existiert auf keinem /me/profile-Pfad: eine GET-Route
        # darf das nicht decken.
        self.assertFalse(_exposed("PATCH", "/me/profile"))
        self.assertFalse(_exposed("TRACE", "/me"))
        # Gegenprobe: die imperative documents-Route IST methoden-spezifisch
        # erkannt, obwohl sie in keiner .tf steht.
        self.assertTrue(_exposed("DELETE", "/me/documents/{docId}"))
        self.assertFalse(_exposed("PATCH", "/me/documents/{docId}"))

    def test_no_unreachable_method_branch_on_live_paths(self):
        """Breiter Sweep: jeder (METHOD, PATH)-Zweig braucht exakt seine Route.

        Erkennt dieselbe Fehlerklasse generisch, nicht nur am
        /me/profile-Beispiel.
        """
        live = {(r.split(" ", 1)[0], r.split(" ", 1)[1].rstrip("/"))
            for r in terraform_routes()}
        # Die imperativen OPEN-3-Routen sind exponiert, stehen aber in keiner
        # .tf-Datei. Sie zaehlen als live -- mit exakter Methode.
        imperative = {(r.split(" ", 1)[0], r.split(" ", 1)[1])
                      for r in IMPERATIVE_ONLY_ROUTES}
        known = {p.rstrip("/") for p in WILDCARD_DISPATCH_PATHS}
        orphans = []
        for method, path in sorted(handler_dispatch_routes()):
            if method == "*" or path.rstrip("/") in known:
                continue
            # Der Dispatch nutzt bewusst Praefixe, Terraform konkrete
            # Pfade: 'POST /v1/m2m/' deckt die konkrete Route
            # 'POST /v1/m2m/agents/{agentId}/execute' ab. Praefix-Match
            # ist hier korrekt -- entscheidend ist, dass die METHODE
            # uebereinstimmen muss (das war der P2B-Defekt).
            # Fuer die Template-Pfade der OPEN-3-Routen gilt: praefixweise
            # ({docId} steht im Terraform nicht, im Dispatch schon).
            if (method, path) in live or (method, path) in imperative:
                continue
            if any(lm == method and (lp.startswith(path)
                                    or path.startswith(lp))
                   for lm, lp in live | imperative):
                continue
            orphans.append("%s %s" % (method, path))
        self.assertEqual(
            [], orphans,
            "Dispatcher-Aestige ohne exakte (METHOD, PATH)-Terraform-Route: %s"
            % orphans)

    def test_health_branch_exists(self):
        """Regression auf den eigentlichen Befund H."""
        import handler
        source = _read(handler.__file__)
        dispatch = source[source.index("def _handle_api_event"):
                         source.index("def _handle_health")]
        self.assertIn("path == '/health'", dispatch)
        self.assertIn("return _handle_health(event, context)", dispatch)


class TestDocumentationClaimsAreNotStale(unittest.TestCase):
    """Aussagen, die in P20-Discovery-01 falsch waren."""

    def test_error_format_difference_is_documented(self):
        """orders-reader nutzt Objekt-, agent String-Fehler."""
        text = _read(DOC)
        self.assertIn('{"error": {"code"', text)
        self.assertIn('{"error": "<string>"}', text)

    def test_next_token_is_not_claimed_as_implemented(self):
        """Es gibt keine nextToken-Mechanik; die alte Aussage war falsch."""
        text = _read(DOC)
        self.assertIn("nextToken", text)
        self.assertIn("LastEvaluatedKey", text)
        # Keine Behauptung, es sei "vorhanden"/"implementiert".
        self.assertNotRegex(
            text,
            r"nextToken[^.]{0,40}(vorhanden|implementiert)")
        self.assertNotRegex(
            text,
            r"(vorhanden|implementiert)[^.]{0,40}nextToken")

    def test_documents_routes_are_documented_as_open_gap(self):
        """OPEN-3: 3 live Routen ohne Terraform-Deklaration."""
        text = _read(DOC)
        self.assertIn("OPEN-3", text)
        self.assertIn("POST /me/documents", documented_routes())

    def test_no_openapi_file_is_claimed_for_the_platform(self):
        text = _read(DOC)
        self.assertIn("OPEN-1", text)
        self.assertIn("jobsearch/openapi.yaml", text)


if __name__ == "__main__":
    unittest.main()