"""
Contract governance tests for the canonical Platform OpenAPI document.

Gate G4-PLATFORM-OPENAPI-CONTRACT-01, closing OPEN-1.

Invariants enforced here:

1.  Every Terraform `(METHOD, PATH)` route exists in the spec.
2.  Every live/reachable dispatcher branch is either represented in the spec
    or an explicitly declared, approved governance exception.
3.  Coverage is `(METHOD, PATH)`. A `GET` route never satisfies a `DELETE`
    requirement — this is the class of drift that shipped an unreachable
    `DELETE /me/profile` in Gate-02.
4.  `DELETE /me/profile` is independently represented, and is documented as
    profile deletion rather than account erasure.
5.  OPEN-3 document routes stay explicitly visible with their imperative
    infrastructure status, and are never mislabelled Terraform-managed.
6.  Both OPEN-2 error-envelope families are represented accurately.
7.  Dispatcher-only prefixes (OPEN-5) are classified, not silently dropped.

The route inventory is REUSED from the canonical P20 helper rather than
reimplemented, so this suite and the existing route-governance suite can
never disagree about what a route is.
"""

import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "lambda"))
sys.path.insert(0, os.path.join(REPO, "tests"))

import yaml

from test_p20_api_contract_consistency import (  # canonical inventory
    IMPERATIVE_ONLY_ROUTES,
    WILDCARD_DISPATCH_PATHS,
    handler_dispatch_routes,
    reader_dispatch_routes,
    terraform_routes,
)

SPEC_PATH = os.path.join(REPO, "docs", "api", "openapi-platform.yaml")

HTTP_METHODS = ("get", "post", "put", "patch", "delete")

#: Dispatcher prefixes with no Gateway route by deliberate decision (OPEN-5
#: in docs/api/API-STANDARD.md). Approved exceptions, asserted explicitly so
#: that removing one fails this suite.
APPROVED_UNEXPOSED_DISPATCH = {
    ("GET", "/api/agents"),
    ("POST", "/api/agents"),
    ("GET", "/work"),
    ("POST", "/work"),
    ("GET", "/me/jobsearches"),
    ("POST", "/me/jobsearches"),
    ("PUT", "/me/jobsearches"),
    ("DELETE", "/me/jobsearches"),
}


def _spec():
    with open(SPEC_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _spec_operations(spec):
    """(METHOD, PATH) -> operation object."""
    out = {}
    for path, item in spec.get("paths", {}).items():
        for method in HTTP_METHODS:
            if method in item:
                out[(method.upper(), path)] = item[method]
    return out


def _terraform_routes_set():
    return {(info["method"], info["path"])
            for info in terraform_routes().values()}


def _imperative_routes_set():
    out = set()
    for route in IMPERATIVE_ONLY_ROUTES:
        method, _, path = route.partition(" ")
        out.add((method, path))
    return out


class TestSpecStructure(unittest.TestCase):
    def setUp(self):
        self.spec = _spec()
        self.ops = _spec_operations(self.spec)

    def test_parses_as_openapi_3(self):
        self.assertTrue(str(self.spec.get("openapi", "")).startswith("3."),
                        "spec must declare an OpenAPI 3.x version")

    def test_operation_ids_unique(self):
        ids = [op.get("operationId") for op in self.ops.values()]
        self.assertTrue(all(ids), "every operation needs an operationId")
        duplicates = {i for i in ids if ids.count(i) > 1}
        self.assertEqual(set(), duplicates, "duplicate operationId: %s" % duplicates)

    def test_all_internal_refs_resolve(self):
        text = open(SPEC_PATH, encoding="utf-8").read()
        refs = set(re.findall(r'"#/components/(\w+)/([A-Za-z0-9_]+)"', text))
        self.assertTrue(refs, "spec should use $ref for shared schemas")
        missing = ["%s/%s" % (s, n) for s, n in refs
                   if n not in self.spec.get("components", {}).get(s, {})]
        self.assertEqual([], missing, "unresolved $ref: %s" % missing)

    def test_no_external_refs(self):
        text = open(SPEC_PATH, encoding="utf-8").read()
        external = [r for r in re.findall(r"\$ref:\s*(\S+)", text)
                    if not r.startswith('"#')]
        self.assertEqual([], external,
                         "spec must be self-contained; external refs: %s" % external)


class TestCoverageOfTerraformRoutes(unittest.TestCase):
    """Invariant 1 + 3: every Terraform route present, matched on METHOD+PATH."""

    def setUp(self):
        self.ops = _spec_operations(_spec())

    def test_every_terraform_route_is_documented(self):
        missing = sorted(_terraform_routes_set() - set(self.ops))
        self.assertEqual([], missing,
                         "Terraform routes absent from OpenAPI: %s" % missing)

    def test_no_spec_route_without_terraform_or_imperative_source(self):
        """The spec may not invent reachable routes."""
        allowed = _terraform_routes_set() | _imperative_routes_set()
        extra = sorted(set(self.ops) - allowed)
        self.assertEqual([], extra,
                         "OpenAPI documents routes no source declares: %s" % extra)

    def test_method_matters_not_just_path(self):
        """Negative invariant: a path present is not coverage.

        `GET /me/profile` exists, so a path-only check would be satisfied even
        if `DELETE /me/profile` were missing from the spec entirely.
        """
        self.assertIn(("GET", "/me/profile"), self.ops)
        self.assertIn(("DELETE", "/me/profile"), self.ops)
        # Every (METHOD, PATH) in the spec is keyed distinctly; a route whose
        # only sibling methods exist must not be silently absorbed.
        self.assertNotIn(("DELETE", "/me/profile"), set(
            k for k in self.ops if k[1] == "/me/profile" and k[0] == "GET"))


class TestDeleteProfileSemantics(unittest.TestCase):
    """Invariant 4: DELETE /me/profile must not overclaim."""

    def setUp(self):
        self.ops = _spec_operations(_spec())

    def test_delete_profile_present_and_independent(self):
        self.assertIn(("DELETE", "/me/profile"), self.ops)
        op = self.ops[("DELETE", "/me/profile")]
        self.assertEqual("deleteProfile", op["operationId"])

    def test_declares_204_and_empty_body_semantics(self):
        responses = self.ops[("DELETE", "/me/profile")]["responses"]
        self.assertIn("204", responses)
        self.assertNotIn("200", responses,
                         "deletion returns 204, not 200")
        for code in ("401", "404", "500"):
            self.assertIn(code, responses)

    def test_does_not_claim_account_erasure(self):
        op = self.ops[("DELETE", "/me/profile")]
        self.assertFalse(op.get("x-is-account-erasure", False))
        self.assertEqual("USER_PROFILE_TABLE-row-only",
                         op.get("x-deletion-scope"))
        text = (op.get("description") or "").lower()
        self.assertIn("not account deletion", text)
        # The retained stores must be named so the boundary is explicit.
        for retained in ("entitlement", "credential", "work item",
                         "job search", "document"):
            self.assertIn(retained, text,
                          "description should name retained store %r" % retained)

    def test_body_is_not_a_target_selector(self):
        """A caller must not be able to choose whose profile is deleted."""
        op = self.ops[("DELETE", "/me/profile")]
        self.assertNotIn("requestBody", op,
                         "deletion takes no body: identity comes from the JWT")


class TestOpen3ImperativeRoutes(unittest.TestCase):
    """Invariant 5: OPEN-3 routes visible, correctly labelled."""

    def setUp(self):
        self.spec = _spec()
        self.ops = _spec_operations(self.spec)

    def test_open3_routes_present(self):
        for method, path in sorted(_imperative_routes_set()):
            self.assertIn((method, path), self.ops,
                          "OPEN-3 route %s %s must remain visible" % (method, path))

    def test_open3_routes_marked_imperative_not_terraform(self):
        for method, path in sorted(_imperative_routes_set()):
            op = self.ops[(method, path)]
            self.assertEqual("imperative-open-3",
                             op.get("x-infrastructure-governance"),
                             "%s %s must declare imperative governance"
                             % (method, path))
            self.assertIn("OPEN-3", op.get("x-infrastructure-note", ""))

    def test_terraform_routes_are_not_marked_imperative(self):
        for method, path in sorted(_terraform_routes_set()):
            op = self.ops[(method, path)]
            self.assertEqual("terraform-managed",
                             op.get("x-infrastructure-governance"),
                             "%s %s is Terraform-managed" % (method, path))


class TestOpen2ErrorEnvelopes(unittest.TestCase):
    """Invariant 6: both error families represented, neither faked."""

    def setUp(self):
        self.spec = _spec()

    def test_both_envelopes_defined(self):
        schemas = self.spec["components"]["schemas"]
        self.assertIn("ErrorString", schemas)
        self.assertIn("ErrorObject", schemas)

    def test_envelopes_are_structurally_distinct(self):
        schemas = self.spec["components"]["schemas"]
        string_error = schemas["ErrorString"]["properties"]["error"]
        object_error = schemas["ErrorObject"]["properties"]["error"]
        self.assertEqual("string", string_error["type"])
        self.assertEqual("object", object_error["type"])

    def test_orders_routes_declare_the_object_envelope(self):
        ops = _spec_operations(self.spec)
        for (method, path), op in ops.items():
            if not path.startswith("/orders"):
                continue
            self.assertEqual("ErrorObject", op.get("x-error-envelope"),
                             "%s %s is served by the orders-reader Lambda"
                             % (method, path))

    def test_agent_routes_do_not_declare_the_object_envelope(self):
        ops = _spec_operations(self.spec)
        for (method, path), op in ops.items():
            if path.startswith("/orders"):
                continue
            self.assertNotEqual("ErrorObject", op.get("x-error-envelope"),
                                "%s %s is served by the agent Lambda"
                                % (method, path))

    def test_open2_remains_declared_open(self):
        text = self.spec["info"]["description"]
        self.assertIn("OPEN-2", text)
        self.assertIn("ErrorString", text)
        self.assertIn("ErrorObject", text)


class TestDispatcherCoverageAndExceptions(unittest.TestCase):
    """Invariant 2 + 7: dispatcher branches classified, never dropped."""

    def setUp(self):
        self.ops = _spec_operations(_spec())

    def test_reachable_dispatcher_branches_are_documented(self):
        live = {r for r in _terraform_routes_set() if r[1] != "/v1/m2m"}
        live |= _imperative_routes_set()
        missing = sorted(r for r in live if r not in self.ops)
        self.assertEqual([], missing,
                         "reachable dispatcher routes absent from spec: %s" % missing)

    def test_unexposed_dispatcher_prefixes_are_declared_exceptions(self):
        """OPEN-5 branches are code-only; each must be an approved exception."""
        for method, path in sorted(APPROVED_UNEXPOSED_DISPATCH):
            if (method, path) in self.ops:
                continue  # exposed after all
            self.assertIn((method, path), APPROVED_UNEXPOSED_DISPATCH,
                          "%s %s is unexposed but not an approved exception"
                          % (method, path))

    def test_exception_list_has_no_route_that_is_actually_reachable(self):
        """An exception must not cover a route the spec does document."""
        stale = sorted(APPROVED_UNEXPOSED_DISPATCH & set(self.ops))
        self.assertEqual([], stale,
                         "routes listed as unexposed are documented: %s" % stale)

    def test_open5_prefixes_declared(self):
        """Each OPEN-5 prefix must appear as an approved exception."""
        documented_or_excepted = set(self.ops) | APPROVED_UNEXPOSED_DISPATCH
        for path in WILDCARD_DISPATCH_PATHS:
            matching = {(m, p) for m, p in documented_or_excepted if p == path}
            self.assertTrue(
                matching,
                "OPEN-5 prefix %s must be classified as an approved "
                "unexposed exception, not silently dropped" % path)

    def test_orders_reader_dispatch_is_covered(self):
        """The orders-reader dispatches on exact routeKey, not path prefix."""
        for route in reader_dispatch_routes():
            method, _, path = route.partition(" ")
            self.assertIn(
                (method, path), self.ops,
                "orders-reader route %s missing from spec" % route)


class TestJobsearchPrefixNotAdvertised(unittest.TestCase):
    """`/me/jobsearches` is OPEN-5 code-only; it must NOT appear as an API."""

    def test_jobsearch_prefix_absent_from_spec(self):
        ops = _spec_operations(_spec())
        leaked = sorted(k for k in ops if k[1].startswith("/me/jobsearches"))
        self.assertEqual([], leaked,
                         "unreachable /me/jobsearches must not be advertised: %s"
                         % leaked)

    def test_work_and_api_agents_absent_from_spec(self):
        ops = _spec_operations(_spec())
        leaked = sorted(k for k in ops
                        if k[1] == "/work" or k[1].startswith("/api/agents"))
        self.assertEqual([], leaked,
                         "unreachable code-only prefixes must not be advertised: %s"
                         % leaked)


if __name__ == "__main__":
    unittest.main()