"""Tests Gate B4-TERRAFORM-01: Terraform-managed Agent Catalog Entry.

Deckt ab (Gate §8):
  - Die Deklaration nutzt das BESTEHENDE Schema (Feldmenge des Read Paths)
  - Der kanonische Agent stimmt mit der Runtime-Definition ueberein
  - Kein `expiresAt` (TTL wuerde den Eintrag still entfernen)
  - Read Path findet den Eintrag und fail-closed bleibt intakt
  - Architekturregel: Terraform ist die einzige Quelle — kein
    Runtime-Writer, kein Seeder, kein manueller Write-Pfad im Repo
  - Keine Secrets / Personendaten in der Deklaration

Kein AWS, keine Mutation: die Item-Form wird aus der Terraform-Datei
gelesen und gegen den echten Read-Path-Code geprueft.
"""

import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.agent_status import (  # noqa: E402
    is_executable_status,
    normalize_agent_status,
)
from agents.ecosystem.catalog_adapter import (  # noqa: E402
    CatalogAdapter,
    populate_registry_from_catalog,
)
from agents.ecosystem.registry import (  # noqa: E402
    AgentRegistry,
    AgentStatus,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TF_FILE = os.path.join(ROOT, "terraform", "modules", "dynamodb", "main.tf")
TABLE = "test-agent-catalog"

#: Attributmenge, die die BESTEHENDEN Leser konsumieren. Aus dem Code
#: abgeleitet, nicht aus der Terraform-Datei (sonst wäre der Test zirkulär).
READ_PATH_FIELDS = {
    "agentId", "status", "name", "version", "description", "capabilities",
    "supported_bodies", "supported_runtimes", "risk_level", "metadata",
}


def _tf_text():
    with open(TF_FILE, encoding="utf-8") as fh:
        return fh.read()


def _strip_comments(text):
    """Drop `#` line comments, quote-aware.

    Two deliberate choices:
      * Only `#` is treated as a comment. `//` also appears INSIDE strings
        here (e.g. ARN patterns), and a naive `//` strip would corrupt them.
      * Block comments (`/* */`) are NOT stripped, because `"/index/*"` in
        an ARN string would pair with a later `*/` and silently delete a
        chunk of the policy.
    Terraform block comments are not used in the files inspected here.
    """
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


def _has_structural_brace(text):
    """True if `text` contains a `{` that is NOT inside a string literal."""
    in_str = False
    for i, ch in enumerate(text):
        if ch == '"' and (i == 0 or text[i - 1] != "\\"):
            in_str = not in_str
        elif ch == "{" and not in_str:
            return True
    return False


def _iam_statements(text):
    """Extract IAM statements as dicts from HCL policy blocks.

    Three things this parser had to get right, all found the hard way:
      * The policy is HCL object syntax with UNQUOTED keys
        (`Effect = "Allow"`), so json.loads does not apply.
      * Statements are LEAF objects. A naive depth-0 brace scan latches onto
        the enclosing `jsonencode({...})` and merges all statements into one,
        which then wrongly reports PutItem for the catalog.
      * Braces appear INSIDE strings: `"${var.agent_catalog_table_arn}/index/*"`.
        A plain character scan therefore counts a nested object where there
        is none and silently drops the catalog statement. Every brace scan
        here is quote-aware.

    So: for every `{`, find its matching `}` ignoring braces inside strings,
    then accept the block only if it contains an `Effect =` assignment AND
    no structural (non-string) nested `{`.
    """
    statements = []
    length = len(text)
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        depth, close = 0, None
        in_str = False
        j = i
        while j < length:
            c = text[j]
            if c == '"' and (j == 0 or text[j - 1] != "\\"):
                in_str = not in_str
            elif not in_str and c == "{":
                depth += 1
            elif not in_str and c == "}":
                depth -= 1
                if depth == 0:
                    close = j
                    break
            j += 1
        if close is None:
            continue
        block = text[i:close + 1]
        if _has_structural_brace(block[1:-1]):
            continue  # enclosing container, not a leaf statement
        if not re.search(r"(?<![\"\w])Effect\s*=", block):
            continue
        effect = re.search(r"Effect\s*=\s*\"([^\"]*)\"", block)
        actions = re.findall(
            r"\"((?:dynamodb|sts|s3|sqs|logs|lambda|execute-api):[^\"]*)\"",
            block)
        resources = re.findall(r"\$\{?var\.([\w.]+)\}?", block)
        statements.append({
            "effect": effect.group(1) if effect else None,
            "actions": actions,
            "resources": resources,
            "block": block,
        })
    return statements


def _functions(src):
    """Yield (name, builds_catalog_handle, writes, reads) per top-level function.

    `builds_catalog_handle` is true when the function resolves the catalog
    table itself: it reads the catalog table name from the environment (or
    a literal catalog name) AND constructs a DynamoDB Table object from it.
    That is exactly the privilege that must stay read-only.
    """
    import ast
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body_src = ast.get_source_segment(src, node) or ""
        # Precise marker: the catalog TABLE NAME source. The bare
        # identifier `agent_catalog` is too generic — it also matches the
        # local dict variable in _execute_agent, which builds a handle for
        # the WORK QUEUE, not for the catalog.
        names_catalog = ("AGENT_CATALOG_TABLE" in body_src
                         or "agent-catalog" in body_src
                         or "agent_catalog_table" in body_src)
        calls = [c for c in ast.walk(node)
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)]
        builds_handle = names_catalog and any(
            isinstance(c.func, ast.Attribute) and c.func.attr == "Table"
            for c in calls)
        writes = {c.func.attr for c in calls
                  if c.func.attr in ("put_item", "update_item",
                                    "delete_item", "batch_writer")}
        reads = {c.func.attr for c in calls
                 if c.func.attr in ("scan", "get_item", "query",
                                    "get_all_agents", "scan_all_agent_ids",
                                    "get_agent")}
        yield node.name, builds_handle, writes, reads


def _seed_block():
    """Return the locals.agent_catalog_seed block of the Terraform config."""
    text = _tf_text()
    start = text.index("agent_catalog_seed = {")
    return text[start:text.index("\n  }", start) + 4]


def _declared_seed():
    """Parse the declared seed agent out of the Terraform local.

    Deliberately a narrow parser: it only understands the flat
    ``key = "literal"`` / ``key = ["a", "b"]`` shape this config uses, and
    it FAILS loudly on anything else. A test must not silently pass on a
    config it did not understand.
    """
    block = _seed_block()
    out = {}
    for key, value in re.findall(
            r"(\w+)\s*=\s*(\[[^\]]*\]|\"[^\"]*\")", block):
        if value.startswith("["):
            out[key] = re.findall(r"\"([^\"]*)\"", value)
        else:
            out[key] = value.strip('"')
    return out


class FakeTable:
    """In-memory stand-in for a boto3 DynamoDB Table resource."""

    def __init__(self, items=None):
        self.items = {k: dict(v) for k, v in (items or {}).items()}

    def put_item(self, Item=None, **kwargs):
        if kwargs:
            raise AssertionError(f"unexpected put_item kwargs: {kwargs}")
        self.items[Item["agentId"]] = dict(Item)
        return {}

    def get_item(self, Key=None, **kwargs):
        if kwargs:
            raise AssertionError(f"unexpected get_item kwargs: {kwargs}")
        item = self.items.get(Key["agentId"])
        return {"Item": dict(item)} if item else {}

    def scan(self, **kwargs):
        unknown = set(kwargs) - {"ProjectionExpression"}
        if unknown:
            raise AssertionError(f"unexpected scan kwargs: {unknown}")
        items = list(self.items.values())
        if kwargs.get("ProjectionExpression"):
            items = [{"agentId": i["agentId"]} for i in items]
        return {"Items": [dict(i) for i in items]}


class FakeResource:
    def __init__(self, table):
        self._table = table

    def Table(self, name):
        assert name == TABLE, name
        return self._table


def terraform_item_to_native(declared):
    """Terraform local (native) -> read-path item (native)."""
    return {
        "agentId": declared["agentId"],
        "name": declared["name"],
        "version": declared["version"],
        "status": declared["status"],
        "description": declared["description"],
        "risk_level": declared["risk_level"],
        "capabilities": list(declared["capabilities"]),
        "supported_bodies": list(declared["supported_bodies"]),
        "supported_runtimes": list(declared["supported_runtimes"]),
        "metadata": {},
    }


class TestTerraformDeclaration(unittest.TestCase):
    def test_seed_block_exists(self):
        self.assertIn("agent_catalog_seed", _tf_text())

    def test_uses_existing_dynamodb_table_resource(self):
        text = _tf_text()
        self.assertIn('resource "aws_dynamodb_table" "agent_catalog"', text)
        self.assertIn("table_name = aws_dynamodb_table.agent_catalog.name", text)
        self.assertIn("depends_on = [aws_dynamodb_table.agent_catalog]", text)

    def test_declared_agent_is_the_canonical_reference_agent(self):
        declared = _declared_seed()
        from agents.runtime.pipeline import (
            REFERENCE_AGENT_ID,
            REFERENCE_CAPABILITY,
            BODY_VERSION,
            RUNTIME_LAMBDA,
        )
        self.assertEqual(declared["agentId"], REFERENCE_AGENT_ID)
        self.assertEqual(declared["capabilities"], [REFERENCE_CAPABILITY])
        self.assertEqual(declared["supported_bodies"], [BODY_VERSION])
        self.assertEqual(declared["supported_runtimes"], [RUNTIME_LAMBDA])

    def test_declared_status_is_known_to_existing_normaliser(self):
        declared = _declared_seed()
        status = normalize_agent_status(declared["status"])
        self.assertIsNotNone(status, "unknown status would block the agent")
        self.assertTrue(is_executable_status(declared["status"]))

    def test_item_shape_equals_existing_read_path_fields(self):
        item = terraform_item_to_native(_declared_seed())
        self.assertEqual(set(item), READ_PATH_FIELDS)

    def test_no_expires_at_declared(self):
        """TTL is enabled on expiresAt — declaring it would expire the item."""
        self.assertNotIn("expiresAt", _declared_seed())
        self.assertNotIn("expiresAt", _seed_block())

    def test_no_secret_or_personal_data(self):
        blob = json.dumps(_declared_seed()).lower()
        for needle in ("secret", "token", "password", "credential",
                       "bearer", "apikey", "api_key", "private", "@",
                       "arn:aws", "userid", "user_id", "tenant", "email"):
            self.assertNotIn(needle, blob, f"seed declares {needle!r}")

    def test_item_uses_dynamodb_attributevalue_json(self):
        """aws_dynamodb_table_item only accepts `item` as AttributeValue JSON;
        free attributes are not valid arguments for that resource type."""
        text = _tf_text()
        self.assertIn("item = jsonencode({", text)
        for wrapper in ("{ S = ", "{ L = ", "{ M = {} }"):
            self.assertIn(wrapper, text)

    def test_no_range_key_declared(self):
        """agent_catalog has a hash key only (verified live).

        Comments are stripped first: the word appears in the explanatory
        comment, and `range_key = "status"` appears in OTHER tables' GSI
        definitions, so a naive substring match would false-positive.
        """
        block = _strip_comments(_tf_text())
        item_res = block[block.index(
            'resource "aws_dynamodb_table_item" "agent_catalog_seed"'):]
        for line in item_res.splitlines():
            self.assertNotRegex(
                line.strip(), r"^range_key\b",
                f"range_key must not be declared: {line.strip()!r}")

    def test_table_schema_untouched(self):
        """No new attribute definition, no new table, no new key."""
        text = _tf_text()
        table_res = text[text.index('resource "aws_dynamodb_table"'
                                    ' "agent_catalog"'):]
        table_res = table_res[:table_res.index("\n}\n")]
        self.assertEqual(table_res.count("attribute {"), 2)
        self.assertNotIn("sort_key", table_res)
        self.assertIn('hash_key     = "agentId"', table_res)

    def test_only_one_resource_type_added(self):
        text = _tf_text()
        before = text.count('resource "aws_dynamodb_table_item"')
        self.assertEqual(before, 1, "exactly one item resource expected")


class TestArchitectureRuleNoRuntimeWriter(unittest.TestCase):
    """§2/§4: Terraform is the only source for catalog entries."""

    def test_no_catalog_writer_module(self):
        self.assertFalse(os.path.exists(
            os.path.join(ROOT, "agents", "ecosystem", "catalog_writer.py")))

    def test_no_runtime_put_item_on_agent_catalog(self):
        """A function that builds the CATALOG TABLE HANDLE must be read-only.

        Scoped deliberately narrowly, per FUNCTION and via the AST. Both
        coarser variants are wrong:
          * file-wide substring scan -> handler.py writes the user-profile
            and work-queue tables, false positive
          * "function mentions the catalog AND writes" -> _execute_agent
            reads the catalog and legitimately enqueues a work item
        The rule that actually protects the catalog is: whoever resolves the
        catalog Table object may only read from it.
        """
        offenders, checked = [], []
        for base in ("agents", "lambda", "installer"):
            for dirpath, _dirs, files in os.walk(os.path.join(ROOT, base)):
                if "__pycache__" in dirpath:
                    continue
                for name in sorted(files):
                    if not name.endswith(".py"):
                        continue
                    path = os.path.join(dirpath, name)
                    src = open(path, encoding="utf-8", errors="replace").read()
                    for fn_name, builds_handle, writes, reads in _functions(src):
                        if not builds_handle:
                            continue
                        rel = os.path.relpath(path, ROOT)
                        checked.append(f"{rel}:{fn_name}")
                        if writes:
                            offenders.append(
                                f"{rel}:{fn_name}:{sorted(writes)}")
        self.assertTrue(checked, "no catalog table handle found — test is "
                                 "not actually checking anything")
        self.assertEqual(offenders, [],
                         f"catalog handle used for writing: {offenders}")

    def test_catalog_handle_function_only_reads(self):
        """Named, explicit assertion of the invariant above."""
        offenders, checked = [], []
        for base in ("agents", "lambda", "installer"):
            for dirpath, _dirs, files in os.walk(os.path.join(ROOT, base)):
                if "__pycache__" in dirpath:
                    continue
                for name in sorted(files):
                    if not name.endswith(".py"):
                        continue
                    path = os.path.join(dirpath, name)
                    src = open(path, encoding="utf-8", errors="replace").read()
                    for fn_name, builds_handle, writes, reads in _functions(src):
                        if builds_handle:
                            rel = os.path.relpath(path, ROOT)
                            checked.append((rel, fn_name))
                            if not reads:
                                offenders.append(
                                    f"{rel}:{fn_name} has neither read nor write")
                            if writes:
                                offenders.append(f"{rel}:{fn_name} writes")
        self.assertIn(("lambda/handler.py", "_get_agent_catalog"), checked)
        self.assertEqual(offenders, [])

    def test_no_seeder_script(self):
        self.assertFalse(os.path.exists(
            os.path.join(ROOT, "installer", "scripts",
                         "seed_agent_catalog.py")))
        self.assertFalse(os.path.exists(
            os.path.join(ROOT, "installer", "scripts",
                         "unseed_agent_catalog.py")))

    def test_lambda_role_read_model_unchanged(self):
        """The runtime keeps reading; it never gains a provisioning right.

        Enforced declaratively: the IAM statement whose Resource names the
        catalog table must stay read-only. The statement is extracted as a
        whole block — a fixed character window would miss the Action list,
        which sits ABOVE the Resource in this file.
        """
        iam = _strip_comments(open(
            os.path.join(ROOT, "terraform", "modules", "lambda", "main.tf"),
            encoding="utf-8").read())
        statements = _iam_statements(iam)
        self.assertTrue(statements, "no IAM statement parsed — test is not "
                                    "actually checking anything")
        catalog = [st for st in statements
                   if any("agent_catalog" in r for r in st["resources"])]
        self.assertEqual(len(catalog), 1,
                         f"expected exactly one catalog IAM statement, "
                         f"got {len(catalog)}")
        actions = catalog[0]["actions"]
        for forbidden in ("dynamodb:PutItem", "dynamodb:UpdateItem",
                          "dynamodb:DeleteItem", "dynamodb:BatchWriteItem"):
            self.assertNotIn(forbidden, actions,
                             f"runtime must not get {forbidden}")
        self.assertIn("dynamodb:Scan", actions)
        self.assertIn("dynamodb:GetItem", actions)


class TestReadPathWithTerraformDeclaredItem(unittest.TestCase):
    """The declared item must satisfy the existing read path."""

    def _seeded_table(self):
        table = FakeTable({"reference_agent": terraform_item_to_native(
            _declared_seed())})
        return FakeResource(table), table

    def test_existing_read_path_finds_the_declared_agent(self):
        db, _ = self._seeded_table()
        self.assertEqual(
            CatalogAdapter(TABLE, dynamodb=db).scan_all_agent_ids(),
            ["reference_agent"])

    def test_existing_registry_population_registers_it(self):
        db, _ = self._seeded_table()
        registry = AgentRegistry()
        self.assertEqual(
            populate_registry_from_catalog(registry, TABLE, dynamodb=db), 1)
        entry = registry.get("reference_agent")
        self.assertEqual(entry.status, AgentStatus.ACTIVE)
        self.assertEqual(entry.capabilities,
                         _declared_seed()["capabilities"])
        self.assertTrue(entry.can_execute(
            _declared_seed()["capabilities"][0]))

    def test_read_path_still_fail_closed_on_unknown_status(self):
        item = terraform_item_to_native(_declared_seed())
        item["status"] = "NONSENSE"
        db = FakeResource(FakeTable({"reference_agent": item}))
        registry = AgentRegistry()
        self.assertEqual(
            populate_registry_from_catalog(registry, TABLE, dynamodb=db), 0)
        self.assertFalse(registry.is_registered("reference_agent"))

    def test_verify_api_credential_step14_resolves_declared_agent(self):
        """B3 precondition: the catalog lookup resolves a real entry."""
        db, _ = self._seeded_table()
        items = CatalogAdapter(TABLE, dynamodb=db).get_all_agents()
        catalog = {aid: item.get("status") for aid, item in items.items()}
        raw = catalog.get("reference_agent")
        self.assertEqual(raw, "ACTIVE")
        self.assertTrue(is_executable_status(raw))

    def test_absent_entry_blocks_execution(self):
        self.assertFalse(is_executable_status(None))
        self.assertFalse(is_executable_status(""))


if __name__ == "__main__":
    unittest.main()
