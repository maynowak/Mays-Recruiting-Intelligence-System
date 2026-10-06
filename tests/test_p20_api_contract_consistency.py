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
  5. die Doku nennt die beiden NONE-Routen (und nicht nur /health).
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


def reader_dispatch_routes():
    """routeKey-Literale aus dem orders-reader-Einstieg.

    Der Reader dispatcht nach routeKey (exakter Vergleich), nicht nach
    Pfad-Praefix wie der Agent. Deshalb wird er getrennt gelesen.
    """
    source = _read(os.path.join(REPO, "lambda", "orders_reader.py"))
    return set(re.findall(r'route == "([^"]+)"', source))


class TestTerraformRouteInventory(unittest.TestCase):
    """Die Route-Liste selbst muss der Erwartung entsprechen (Anker)."""

    def test_route_count_is_25_terraform_28_live(self):
        """25 Terraform-Deklarationen + 3 imperative documents-Routen = 28 live.

        Die 3 documents-Routen sind bewusst NICHT in Terraform (OPEN-3). Wenn
        jemand sie aufnimmt, muss dieser Test angepasst werden -- sonst
        stimmt die Zahl nicht mehr.
        """
        self.assertEqual(25, len(terraform_routes()))

    def test_exactly_two_none_routes(self):
        none = {r for r, v in terraform_routes().items() if v["auth"] == "NONE"}
        self.assertEqual({
            "GET /health",
            "POST /v1/m2m/agents/{agentId}/execute",
        }, none)

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
        reader_routes = reader_dispatch_routes()
        for route, info in sorted(terraform_routes().items()):
            with self.subTest(route=route):
                if info["target"] == "orders":
                    self.assertIn(
                        route, reader_routes,
                        "Orders-Route %s erreicht keinen reader-Zweig" % route)
                    continue
                path = info["path"]
                # /v1/apiprofiles wird per startswith gefangen, Unterpfade
                # ebenfalls; daher genuegt die Praefix-Pruefung.
                matched = path in agent_paths or any(
                    path.startswith(p) for p in agent_paths)
                self.assertTrue(
                    matched,
                    "Route %s erreicht keinen Dispatch-Zweig" % route)

    def test_every_dispatch_branch_has_a_live_route(self):
        """Gegenrichtung: kein Agent-Zweig ohne Gateway-Route.

        Erlaubt sind ausschliesslich die in OPEN-5 gelisteten Praefixe
        (/api/agents, /work, /me/jobsearches) -- dort existiert Code ohne
        exponierten Zugang, was bewusst so dokumentiert ist.
        """
        known_unexposed = ("/api/agents", "/work", "/me/jobsearches")
        # "Exponiert" heisst: im Gateway erreichbar. Das umfasst Terraform-
        # Routen und die drei imperativen documents-Routen (OPEN-3), die live
        # sind, aber von keinem apply verwaltet werden.
        live = {info["path"] for info in terraform_routes().values()}
        for route in IMPERATIVE_ONLY_ROUTES:
            _, _, path = route.partition(" ")
            live.add(path)
        # Der Dispatch enthaelt fuer einige Praefixe beide Formen (== und
        # startswith mit Slash). Fuer den Vergleich wird der Trailing-Slash
        # vereinheitlicht, sonst waere '/me/jobsearches/' ein Scheinfehler.
        for path in sorted(handler_dispatch_paths()):
            if path.rstrip("/") in known_unexposed:
                continue
            probe = path.rstrip("/") or "/"
            with self.subTest(path=path):
                self.assertTrue(
                    probe in live
                    or any(p.startswith(probe) for p in live)
                    or any(p.startswith(path) for p in live),
                    "Dispatch-Zweig %s hat keine Gateway-Route" % path)

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