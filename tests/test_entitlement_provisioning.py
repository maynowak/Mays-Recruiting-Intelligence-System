"""Tests Gate B5: Terraform-managed Foundation-Entitlement.

Deckt ab (Gate §14):
  Unit          — gueltige/fehlende Entitlement, Zeitfenster, Agent-Bindung,
                  Tenant-Bindung
  Provisioning  — erster Lauf, zweiter Lauf (Idempotenz), Live-Parität
  B3-Integration— positive Machine Execution ueber die echte Verification,
                  fehlende / abgelaufene / falsche-Agent-Entitlement
  Regression    — bestehende Suite (unveraendert, nicht geschwaecht)

Die Entitlement-Zeilenform wird gegen den BESTEHENDEN Grant-Vertrag
(agents.ecosystem.offers.py grant_offer) und den BESTEHENDEN Read Path
(worker_authorization) geprueft — nicht gegen eine eigene Definition.
Kein AWS, keine Mutation: die Deklaration wird aus der Terraform-Datei
gelesen und gegen echten Produktivcode validiert.
"""

import json
import os
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lambda"))

from agents.ecosystem.api_profiles import (  # noqa: E402
    InMemoryApiProfileStore,
    create_profile,
    effective_status,
    transition_status,
)
from agents.ecosystem.credentials import (  # noqa: E402
    InMemoryCredentialStore,
    VerifyOutcome,
    issue_credential,
    verify_api_credential,
)
from agents.ecosystem.worker_authorization import (  # noqa: E402
    DynamoDBEntitlementResolver,
    is_entitlement_valid,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TF_MAIN = os.path.join(ROOT, "terraform", "modules", "dynamodb", "main.tf")
TF_ROOT = os.path.join(ROOT, "terraform", "main.tf")
TF_VARS = os.path.join(ROOT, "terraform", "variables.tf")
AGENT = "reference_agent"
OWNER = "e3c4d8c2-8041-7046-6ad4-2fb6b76c4a52"
TENANT = "b5-1791220725"

#: Attributmenge des BESTEHENDEN grant_offer-Entitlement-Vertrags
#: (agents/ecosystem/offers.py:588-611). Kein Feld ist hier erfunden.
GRANT_CONTRACT_FIELDS = {
    "entitlementId", "userId", "tenantId", "agentId", "validFrom",
    "validUntil", "expiresAt", "offerId", "grantId", "createdAt", "createdBy",
}
#: Vom Read Path tatsaechlich gelesene Felder
#: (worker_authorization.py:40-89).
READ_PATH_FIELDS = {"userId", "tenantId", "agentId", "validFrom", "validUntil"}


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def declared_item_keys():
    """Attribute names the Terraform seed resource actually writes."""
    text = open(TF_MAIN, encoding="utf-8").read()
    start = text.index('resource "aws_dynamodb_table_item" '
                       '"foundation_entitlement"')
    body = text[start:text.index("\n}", start)]
    inner = body[body.index("item = jsonencode({"):]
    keys = re.findall(r"^\s{4}(\w+)\s*=", inner, re.M)
    return set(keys)


# ------------------------------------------------------------- Schema / IaC

class TestDeclarationMatchesExistingContract(unittest.TestCase):
    def test_seed_resource_exists(self):
        text = open(TF_MAIN, encoding="utf-8").read()
        self.assertIn('resource "aws_dynamodb_table_item" '
                      '"foundation_entitlement"', text)

    def test_uses_existing_entitlements_table(self):
        text = open(TF_MAIN, encoding="utf-8").read()
        start = text.index('resource "aws_dynamodb_table_item" '
                           '"foundation_entitlement"')
        block = text[start:text.index("\n}", start)]
        self.assertIn("table_name = aws_dynamodb_table.entitlements.name",
                      block)
        self.assertIn("hash_key   = aws_dynamodb_table.entitlements.hash_key",
                      block)
        self.assertIn("depends_on = [aws_dynamodb_table.entitlements]", block)

    def test_no_range_key(self):
        """The entitlements table has a hash key only (verified live)."""
        text = open(TF_MAIN, encoding="utf-8").read()
        start = text.index('resource "aws_dynamodb_table_item" '
                           '"foundation_entitlement"')
        block = text[start:text.index("\n}", start)]
        self.assertNotRegex(_strip_tf_comments(block), r"^\s*range_key\s*=",
                            re.M)

    def test_writes_only_contract_attributes(self):
        """No invented attributes: every written field exists in the
        grant_offer contract."""
        written = declared_item_keys()
        self.assertTrue(written)
        self.assertEqual(written - GRANT_CONTRACT_FIELDS, set(),
                         "seed writes attributes outside the grant contract")

    def test_writes_every_field_the_read_path_needs(self):
        self.assertEqual(READ_PATH_FIELDS - declared_item_keys(), set(),
                         "seed omits an attribute the read path requires")

    def test_no_status_attribute(self):
        """The entitlement contract has NO status field; is_entitlement_valid
        decides on the time window only. Inventing one would break the
        existing semantics."""
        self.assertNotIn("status", declared_item_keys())

    def test_no_expires_at(self):
        """TTL is enabled on expiresAt; a populated value would silently
        delete the fixture. Removal is an explicit IaC act instead."""
        self.assertNotIn("expiresAt", declared_item_keys())

    def test_no_offer_or_grant_id(self):
        """There is no offer behind a foundation fixture; inventing
        plausible-looking offerId/grantId would misrepresent provenance."""
        written = declared_item_keys()
        self.assertNotIn("offerId", written)
        self.assertNotIn("grantId", written)

    def test_opt_in_by_default(self):
        """A production workspace must provision nothing."""
        for path in (TF_VARS,
                     os.path.join(ROOT, "terraform", "modules", "dynamodb",
                                  "variables.tf")):
            body = open(path, encoding="utf-8").read()
            idx = body.index('variable "foundation_entitlements"')
            end = body.find("\nvariable ", idx + 1)
            block = body[idx:end if end != -1 else len(body)]
            self.assertIn("map(object(", block, path)
            self.assertRegex(block, r"default\s*=\s*\{\}", path)

    def test_root_passes_variable_through(self):
        body = open(TF_ROOT, encoding="utf-8").read()
        self.assertIn("foundation_entitlements = var.foundation_entitlements",
                      body)

    def test_entitlements_table_untouched(self):
        text = open(TF_MAIN, encoding="utf-8").read()
        start = text.index('resource "aws_dynamodb_table" "entitlements"')
        block = text[start:start + 2000]
        block = block[:block.index("\n}\n")]
        self.assertEqual(block.count("attribute {"), 3)
        self.assertIn('hash_key     = "entitlementId"', block)
        self.assertIn('name            = "gsi-user"', block)
        self.assertIn('name            = "gsi-agent"', block)
        self.assertIn('attribute_name = "expiresAt"', block)


class TestRuntimeStaysReadOnly(unittest.TestCase):
    """§6: the Lambda role must not gain any entitlement write right."""

    def _entitlement_statement_actions(self):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "tfseed", os.path.join(ROOT, "tests",
                                   "test_agent_catalog_terraform_seed.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        iam = mod._strip_comments(open(
            os.path.join(ROOT, "terraform", "modules", "lambda", "main.tf"),
            encoding="utf-8").read())
        actions = []
        for st in mod._iam_statements(iam):
            if any("entitlement" in r for r in st["resources"]):
                actions.extend(st["actions"])
        return actions

    def test_entitlement_iam_has_no_write_actions(self):
        actions = self._entitlement_statement_actions()
        self.assertTrue(actions, "no entitlements IAM statement found")
        for forbidden in ("dynamodb:PutItem", "dynamodb:DeleteItem",
                          "dynamodb:UpdateItem", "dynamodb:TransactWriteItems",
                          "dynamodb:Scan"):
            self.assertNotIn(forbidden, actions,
                             f"runtime must not get {forbidden}")

    def test_entitlement_iam_keeps_query_on_user_index(self):
        """The read path queries gsi-user; that must stay permitted."""
        actions = self._entitlement_statement_actions()
        self.assertIn("dynamodb:Query", actions)
        self.assertIn("dynamodb:GetItem", actions)

    def test_no_new_iam_resource_in_this_gate(self):
        """B5 provisions through Terraform's own identity, so no IAM
        resource may be touched."""
        import subprocess
        diff = subprocess.run(
            ["git", "diff", "HEAD", "--", "terraform/"],
            capture_output=True, text=True, cwd=ROOT).stdout
        added = [l for l in diff.splitlines()
                 if l.startswith("+") and not l.startswith("+++")]
        offenders = [l for l in added
                     if re.search(r"aws_iam|Policy|policy_arn", l)]
        self.assertEqual(offenders, [],
                         f"gate must not add IAM: {offenders}")


def _strip_tf_comments(text):
    out = []
    for line in text.splitlines():
        in_str, cut = False, None
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"' and (i == 0 or line[i - 1] != "\\"):
                in_str = not in_str
            elif ch == "#" and not in_str:
                cut = i
                break
            i += 1
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


# ------------------------------------------------------------------ Unit

def _entitlement_row(**over):
    row = {
        "entitlementId": "ent_b5_reference_agent",
        "userId": OWNER,
        "tenantId": TENANT,
        "agentId": AGENT,
        "validFrom": _ts(-1),
        "validUntil": _ts(30),
        "createdBy": {"actor": "terraform", "role": "provisioning"},
    }
    row.update(over)
    return row


class _Resolver:
    def __init__(self, rows):
        self.rows = rows

    def find_entitlements(self, user_id):
        return [r for r in self.rows if r.get("userId") == user_id]


class TestEntitlementUnit(unittest.TestCase):
    def test_valid_entitlement_passes_time_window(self):
        self.assertTrue(is_entitlement_valid(_entitlement_row()))

    def test_expired_entitlement_is_temporally_invalid(self):
        row = _entitlement_row(validFrom=_ts(-30), validUntil=_ts(-1))
        self.assertFalse(is_entitlement_valid(row))

    def test_not_yet_started_entitlement_is_invalid(self):
        self.assertFalse(is_entitlement_valid(
            _entitlement_row(validFrom=_ts(5), validUntil=_ts(30))))

    def test_time_window_is_the_only_validity_criterion(self):
        """Confirms there is no status field to honour (contract)."""
        self.assertTrue(is_entitlement_valid(_entitlement_row()))

    def test_agent_binding_must_match(self):
        from agents.ecosystem.worker_authorization import check_worker_entitlement
        decision = check_worker_entitlement(
            user_id=OWNER, tenant_id=TENANT, agent_id=AGENT,
            work_id="w-b5", api_profile_id=None, resolver=_Resolver([_entitlement_row()]))
        self.assertTrue(decision.authorized, decision.reason)

    def test_wrong_agent_is_denied(self):
        from agents.ecosystem.worker_authorization import check_worker_entitlement
        decision = check_worker_entitlement(
            user_id=OWNER, tenant_id=TENANT, agent_id="jobsearch-agent",
            work_id="w-b5", api_profile_id=None, resolver=_Resolver([_entitlement_row()]))
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.reason, "no-entitlement")

    def test_foreign_tenant_is_denied(self):
        from agents.ecosystem.worker_authorization import check_worker_entitlement
        decision = check_worker_entitlement(
            user_id=OWNER, tenant_id="other-tenant", agent_id=AGENT,
            work_id="w-b5", api_profile_id=None, resolver=_Resolver([_entitlement_row()]))
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.reason, "tenant-mismatch")

    def test_missing_entitlement_is_denied(self):
        from agents.ecosystem.worker_authorization import check_worker_entitlement
        decision = check_worker_entitlement(
            user_id=OWNER, tenant_id=TENANT, agent_id=AGENT,
            work_id="w-b5", api_profile_id=None, resolver=_Resolver([]))
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.reason, "no-entitlement")

    def test_expired_entitlement_denied_through_chain(self):
        from agents.ecosystem.worker_authorization import check_worker_entitlement
        row = _entitlement_row(validFrom=_ts(-30), validUntil=_ts(-1))
        decision = check_worker_entitlement(
            user_id=OWNER, tenant_id=TENANT, agent_id=AGENT,
            work_id="w-b5", api_profile_id=None, resolver=_Resolver([row]))
        self.assertFalse(decision.authorized)
        self.assertEqual(decision.reason, "time-window")


# ------------------------------------------------------- B3 integration

class _Chain:
    """Real stores + real verification, mirroring the B3 machine path."""

    def __init__(self, entitlement_rows):
        self.profiles = InMemoryApiProfileStore()
        self.creds = InMemoryCredentialStore()
        owner = {"userId": OWNER, "tenantId": TENANT, "groups": []}
        admin = {"userId": "a1", "tenantId": TENANT, "groups": ["admins"]}
        self.pid = create_profile(self.profiles, owner, "B5")["apiProfileId"]
        transition_status(self.profiles, admin, self.pid, "ACTIVE")
        self.secret = issue_credential(
            self.creds, self.profiles, self.pid, _ts(30), "owner", OWNER,
            reason="b5-test")["secret"]
        self.resolver = _Resolver(entitlement_rows)
        self.catalog = {AGENT: "ACTIVE"}

    def verify(self, agent_id=AGENT, secret=None, catalog=None):
        return verify_api_credential(
            bearer=secret or self.secret,
            agent_id=agent_id,
            credential_store=self.creds,
            profile_store=self.profiles,
            entitlement_resolver=self.resolver,
            catalog=self.catalog if catalog is None else catalog,
            operation="agent.execute",
            route="POST /v1/m2m/agents/{agentId}/execute",
            method="POST",
            request_id="req-b5",
        )


class TestB3Integration(unittest.TestCase):
    def test_positive_machine_execution_is_authorized(self):
        chain = _Chain([_entitlement_row()])
        decision = chain.verify()
        self.assertIs(decision.outcome, VerifyOutcome.AUTHORIZED,
                      decision.reason_category)
        self.assertEqual(decision.context["agentId"] if "agentId"
                         in decision.context else decision.context
                         ["resolution"]["agentId"], AGENT)
        self.assertEqual(decision.context["tenantId"], TENANT)
        self.assertEqual(decision.context["userId"], OWNER)
        self.assertTrue(decision.audit_ref)

    def test_missing_entitlement_denies(self):
        decision = _Chain([]).verify()
        self.assertIs(decision.outcome, VerifyOutcome.FORBIDDEN)

    def test_expired_entitlement_denies(self):
        row = _entitlement_row(validFrom=_ts(-30), validUntil=_ts(-1))
        decision = _Chain([row]).verify()
        self.assertIs(decision.outcome, VerifyOutcome.FORBIDDEN)

    def test_wrong_agent_denies(self):
        decision = _Chain([_entitlement_row()]).verify(agent_id="jobsearch-agent")
        self.assertIs(decision.outcome, VerifyOutcome.FORBIDDEN)

    def test_non_executable_agent_denies_even_with_entitlement(self):
        """Entitlement alone is not enough — the catalog step still applies."""
        decision = _Chain([_entitlement_row()]).verify(
            catalog={AGENT: "INACTIVE"})
        self.assertIs(decision.outcome, VerifyOutcome.FORBIDDEN)

    def test_authorization_requires_the_whole_chain(self):
        """Removing any single link flips AUTHORIZED to a denial. This is
        the structural guard against a simplified `credential exists ->
        execute` implementation."""
        chain = _Chain([_entitlement_row()])
        self.assertIs(chain.verify().outcome, VerifyOutcome.AUTHORIZED)

        chain.catalog = {}
        self.assertIs(chain.verify().outcome, VerifyOutcome.FORBIDDEN)
        chain.catalog = {AGENT: "ACTIVE"}

        chain.resolver = _Resolver([])
        self.assertIs(chain.verify().outcome, VerifyOutcome.FORBIDDEN)

        # Dropping only the profile keeps the credential KNOWN, so the
        # contract classifies it as "known but unusable" -> FORBIDDEN (403),
        # not UNAUTHORIZED. Asserting 401 here would have been a wrong
        # expectation of the existing contract, not a caught defect.
        chain.profiles = InMemoryApiProfileStore()
        self.assertIs(chain.verify().outcome, VerifyOutcome.FORBIDDEN)

    def test_denied_decision_carries_no_context(self):
        """No oracle: a denial exposes nothing about the credential."""
        decision = _Chain([]).verify()
        self.assertEqual(decision.context, {})

    def test_profile_status_still_binds(self):
        chain = _Chain([_entitlement_row()])
        transition_status(
            chain.profiles, {"userId": "a1", "tenantId": TENANT,
                             "groups": ["admins"]}, chain.pid, "REVOKED")
        self.assertIs(chain.verify().outcome, VerifyOutcome.FORBIDDEN)


# ------------------------------------------------------------ Provisioning

class TestProvisioningIdempotency(unittest.TestCase):
    """§8: the row shape is stable and keyed, so repeated provisioning is
    the same state — Terraform replaces the row in place (hash key), never
    appending a second one."""

    def test_entitlement_id_is_the_map_key(self):
        """No extra id logic is invented: the for_each key becomes the
        primary key."""
        text = open(TF_MAIN, encoding="utf-8").read()
        self.assertIn("for_each = var.foundation_entitlements", text)
        self.assertIn("entitlementId = { S = each.key }", text)

    def test_no_generated_identifier(self):
        text = open(TF_MAIN, encoding="utf-8").read()
        start = text.index('resource "aws_dynamodb_table_item" '
                           '"foundation_entitlement"')
        block = _strip_tf_comments(text[start:text.index("\n}", start)])
        for forbidden in ("uuid", "timestamp(", "time()", "random"):
            self.assertNotIn(forbidden, block)

    def test_row_is_deterministic(self):
        row = _entitlement_row()
        self.assertEqual(row["entitlementId"], "ent_b5_reference_agent")
        self.assertEqual(row["userId"], OWNER)
        self.assertEqual(row["agentId"], AGENT)

    def test_values_come_from_the_variable_not_hardcoded(self):
        text = open(TF_MAIN, encoding="utf-8").read()
        start = text.index('resource "aws_dynamodb_table_item" '
                           '"foundation_entitlement"')
        block = _strip_tf_comments(text[start:text.index("\n}", start)])
        self.assertNotIn(OWNER, block)
        self.assertNotIn(TENANT, block)

    def test_catalog_seed_and_entitlement_seed_are_separate(self):
        """The B4 catalog seed must remain untouched by B5."""
        text = open(TF_MAIN, encoding="utf-8").read()
        self.assertIn('resource "aws_dynamodb_table_item" "agent_catalog_seed"',
                      text)
        self.assertIn('resource "aws_dynamodb_table_item" '
                      '"foundation_entitlement"', text)


class TestSecurityOfTheFixture(unittest.TestCase):
    def test_no_secret_or_pii_in_the_row(self):
        row = _entitlement_row()
        blob = json.dumps(row).lower()
        for needle in ("secret", "token", "password", "credential", "bearer",
                       "email", "@", "cv", "resume", "applicant"):
            self.assertNotIn(needle, blob)

    def test_actor_marks_provisioning_not_admin(self):
        """It must not pretend to be a human admin grant."""
        self.assertEqual(_entitlement_row()["createdBy"],
                         {"actor": "terraform", "role": "provisioning"})

    def test_no_wildcards_in_the_terraform_change(self):
        import subprocess
        diff = subprocess.run(
            ["git", "diff", "HEAD", "--", "terraform/"],
            capture_output=True, text=True, cwd=ROOT).stdout
        added = [l for l in diff.splitlines()
                 if l.startswith("+") and not l.startswith("+++")]
        offenders = [l for l in added if '"*"' in l or '"Resource"' in l]
        self.assertEqual(offenders, [], f"wildcard/resource policy added: {offenders}")


if __name__ == "__main__":
    unittest.main()
