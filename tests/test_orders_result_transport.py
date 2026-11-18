"""Static contracts for the managed Orders result transport.

RIS-ATS-RESULT-TRANSPORT-GATE-01: the result queue, DLQ and HMAC secret stay
owned by the generated Orders module. This suite pins the RIS-side plumbing:
worker env, least-privilege IAM, the dedicated enable flag, producer-role
pass-through and the builder output injection.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TF = REPO / "terraform"
LAMBDA_MAIN = TF / "modules" / "lambda" / "main.tf"
LAMBDA_VARS = TF / "modules" / "lambda" / "variables.tf"
ROOT_MAIN = TF / "main.tf"
ROOT_VARS = TF / "variables.tf"
ROOT_OUTPUTS = TF / "outputs.tf"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_worker_env_carries_the_result_transport_bindings():
    source = text(LAMBDA_MAIN)
    assert "ORDER_RESULT_QUEUE_URL  = var.agent_result_queue_url" in source
    assert "ORDER_RESULT_SECRET_ARN = var.agent_result_secret_arn" in source


def test_result_transport_variables_default_to_off():
    source = text(LAMBDA_VARS)
    for name in (
        "agent_result_queue_url",
        "agent_result_queue_arn",
        "agent_result_secret_arn",
    ):
        block = re.search(
            r'variable "%s" \{(.*?)\n\}' % re.escape(name), source, re.S)
        assert block, name
        assert 'default     = ""' in block.group(1), name


def test_count_is_plan_known_and_never_depends_on_an_arn():
    source = text(LAMBDA_MAIN)
    variables = text(LAMBDA_VARS)
    assert 'variable "agent_result_enabled"' in variables
    flag = re.search(
        r'variable "agent_result_enabled" \{(.*?)\n\}', variables, re.S)
    assert "default     = false" in flag.group(1)
    # Unknown ARNs (created in the same plan) must not drive count.
    for block in re.findall(
            r'resource "aws_iam_role_policy" "lambda_order_result_(?:send|secret)" \{(.*?)\n\}',
            source, re.S):
        assert "count = var.agent_result_enabled ? 1 : 0" in block
        assert "_arn !=" not in block.split("policy")[0]
    assert "agent_result_enabled                = local.orders_agent_result_enabled" in text(ROOT_MAIN)


def test_iam_is_count_gated_and_least_privilege():
    source = text(LAMBDA_MAIN)
    for resource, var, action in (
        ("lambda_order_result_send", "agent_result_queue_arn", "sqs:SendMessage"),
        ("lambda_order_result_secret", "agent_result_secret_arn",
         "secretsmanager:GetSecretValue"),
    ):
        block = re.search(
            r'resource "aws_iam_role_policy" "%s" \{(.*?)\n\}' % resource,
            source, re.S)
        assert block, resource
        body = block.group(1)
        assert "count = var.agent_result_enabled ? 1 : 0" in body
        assert f'"{action}"' in body
        assert "Resource = [var.%s]" % var in body
        assert '"*"' not in body
    # The worker may only write the result queue, never consume it.
    send_block = re.search(
        r'resource "aws_iam_role_policy" "lambda_order_result_send" \{(.*?)\n\}',
        source, re.S).group(1)
    assert "ReceiveMessage" not in send_block
    assert "DeleteMessage" not in send_block


def test_result_policies_are_dependencies_of_the_worker_lambda():
    source = text(LAMBDA_MAIN)
    depends = source.split("depends_on = [", 1)[1].split("]", 1)[0]
    assert "aws_iam_role_policy.lambda_order_result_send" in depends
    assert "aws_iam_role_policy.lambda_order_result_secret" in depends


def test_dedicated_flag_does_not_enable_the_ris_dispatch_queue():
    root = text(ROOT_MAIN)
    variables = text(ROOT_VARS)
    assert 'variable "orders_agent_result_enabled"' in variables
    flag = re.search(
        r'variable "orders_agent_result_enabled" \{(.*?)\n\}', variables, re.S)
    assert 'default     = false' in flag.group(1)
    # RIS dispatch transport keeps its own flag.
    assert 'variable "enable_agent_transport"' in variables
    assert "count  = var.enable_agent_transport ? 1 : 0" in root
    assert "count  = local.orders_agent_result_enabled ? 1 : 0" not in root


def test_managed_orders_module_receives_flag_and_worker_role():
    root = text(ROOT_MAIN)
    block = re.search(r'module "mays_orders" \{(.*?)\n\}', root, re.S).group(1)
    assert "enable_agent_transport        = local.orders_agent_result_enabled" in block
    assert ("ris_result_producer_role_arns = local.orders_agent_result_enabled "
            "? [module.lambda.lambda_role_arn] : []") in block


def test_root_wires_queue_and_secret_from_the_module_outputs():
    root = text(ROOT_MAIN)
    assert "local.orders_agent_result_enabled" in root
    assert "module.mays_orders[0].results_queue_url" in root
    assert "module.mays_orders[0].results_queue_arn" in root
    assert "module.mays_orders[0].result_hmac_secret_arn" in root
    lambda_block = re.search(r'module "lambda" \{(.*?)\n\}', root, re.S).group(1)
    assert "agent_result_queue_url              = local.agent_result_queue_url" in lambda_block
    assert "agent_result_queue_arn              = local.agent_result_queue_arn" in lambda_block
    assert "agent_result_secret_arn             = local.agent_result_secret_arn" in lambda_block


def test_worker_role_is_exported_at_root():
    outputs = text(ROOT_OUTPUTS)
    block = re.search(r'output "lambda_role_arn" \{(.*?)\n\}', outputs, re.S)
    assert block
    assert "module.lambda.lambda_role_arn" in block.group(1)


def test_builder_injects_the_three_transport_outputs():
    from installer import build_mays_orders_module as builder

    assert builder.TRANSPORT_OUTPUT_NAMES == (
        "results_queue_url", "results_queue_arn", "result_hmac_secret_arn")
    for name in builder.TRANSPORT_OUTPUT_NAMES:
        assert f'output "{name}"' in builder.TRANSPORT_OUTPUTS
        assert "try(module.agent_transport[0]." in builder.TRANSPORT_OUTPUTS


def test_builder_injection_is_additive_and_fails_closed_on_collision(tmp_path):
    from installer import build_mays_orders_module as builder

    outputs = tmp_path / "outputs.tf"
    outputs.write_text('output "existing" {\n  value = 1\n}\n', encoding="utf-8")
    builder.inject_transport_outputs(tmp_path)
    written = outputs.read_text(encoding="utf-8")
    assert 'output "existing"' in written
    for name in builder.TRANSPORT_OUTPUT_NAMES:
        assert f'output "{name}"' in written
    # Upstream adding the same output later must stop the build, not duplicate.
    try:
        builder.inject_transport_outputs(tmp_path)
    except RuntimeError as exc:
        assert "bereits" in str(exc)
    else:  # pragma: no cover - regression guard
        raise AssertionError("collision must fail closed")


def test_project_config_matches_the_managed_lifecycle():
    config = json.loads((REPO / "installer" / "project-configs"
                         / "ris-dev2.json").read_text(encoding="utf-8"))
    assert config["terraform_vars"]["orders_lifecycle"] == "managed"
    assert config["terraform_vars"]["orders_agent_result_enabled"] == "false"


def test_installer_does_not_guess_the_result_outputs():
    from installer import ris

    for name in ("results_queue_url", "results_queue_arn",
                 "result_hmac_secret_arn"):
        assert name in ris._UNCONSUMED_ORDERS_OUTPUTS
    assert "orders_agent_result_enabled" in ris.PROJECT_CONFIG_ALLOWED_KEYS


def test_worker_uses_the_live_ris_orders_facade_base_url():
    main = text(LAMBDA_MAIN)
    assert "ORDERS_BASE_URL  = var.orders_base_url" in main
    variables = text(LAMBDA_VARS)
    assert 'variable "orders_base_url"' in variables
    root = text(ROOT_MAIN)
    lambda_block = re.search(r'module "lambda" \{(.*?)\n\}', root, re.S).group(1)
    assert "orders_base_url                     = module.api.api_endpoint" in lambda_block
    # The dead upstream default must not be the effective configuration.
    real = (REPO / "agents" / "orders" / "real.py").read_text(encoding="utf-8")
    assert "aboqolpm0f" in real  # documented default stays, but is overridden

def test_reader_dispatches_agent_orders_through_the_existing_queue():
    root = text(ROOT_MAIN)
    reader = text(TF / "modules" / "orders_reader" / "main.tf")
    variables = text(TF / "modules" / "orders_reader" / "variables.tf")
    assert "RIS_DISPATCH_QUEUE_URL" in reader
    assert "API_PROFILES_TABLE" in reader
    assert 'resource "aws_iam_role_policy" "reader_agent_dispatch"' in reader
    assert "var.dispatch_enabled ? 1 : 0" in reader
    for name in ("dispatch_enabled", "dispatch_queue_url",
                 "dispatch_queue_arn", "api_profiles_table_name",
                 "api_profiles_table_arn"):
        assert f'variable "{name}"' in variables
    block = re.search(r'module "orders_reader" \{(.*?)\n\}', root, re.S).group(1)
    assert "dispatch_enabled        = local.agent_dispatch_enabled" in block
    assert "dispatch_queue_url      = local.agent_dispatch_queue_url" in block
    assert "api_profiles_table_name = module.dynamodb.api_profiles_table_name" in block


def test_dispatch_ingress_can_forward_the_order_result():
    transport = text(TF / "modules" / "agent_transport" / "lambda.tf")
    root = text(ROOT_MAIN)
    assert "ORDER_RESULT_QUEUE_URL  = var.order_result_queue_url" in transport
    assert "ORDER_RESULT_SECRET_ARN = var.order_result_secret_arn" in transport
    assert 'resource "aws_iam_role_policy" "dispatch_result_send"' in transport
    assert 'resource "aws_iam_role_policy" "dispatch_result_secret"' in transport
    assert "count = var.result_transport_enabled ? 1 : 0" in transport
    block = re.search(r'module "agent_transport" \{(.*?)\n\}', root, re.S).group(1)
    assert "result_transport_enabled = local.orders_agent_result_enabled" in block
    assert "order_result_queue_url   = local.agent_result_queue_url" in block
    assert "orders_producer_role_arns = local.agent_dispatch_enabled ? [module.orders_reader[0].role_arn] : var.orders_producer_role_arns" in block


def test_reader_bundle_ships_the_flat_dispatch_contract():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "build_zip_contract", REPO / "lambda" / "build_zip.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    READER_FILES = module.READER_FILES

    assert "lambda/orders_reader.py" in READER_FILES
    assert "agents/transport/order_transport.py" in READER_FILES
    assert "agents/orders/agent_order.py" in READER_FILES

def test_dispatch_ingress_entitlement_query_covers_the_gsi():
    transport = text(TF / "modules" / "agent_transport" / "lambda.tf")
    assert '"${var.entitlements_table_arn}/index/*"' in transport
    assert 'Action = ["dynamodb:GetItem", "dynamodb:Query"]' in transport


def test_ats_api_base_url_is_pinned_and_wired():
    root = text(ROOT_MAIN)
    variables = text(ROOT_VARS)
    worker = text(LAMBDA_MAIN)
    worker_vars = text(LAMBDA_VARS)
    ingress = text(TF / "modules" / "agent_transport" / "lambda.tf")
    assert 'variable "ats_api_base_url"' in variables
    assert 'default     = "https://mays-jobsearch.vercel.app"' in variables
    assert 'variable "ats_api_base_url"' in worker_vars
    assert "ATS_API_BASE_URL = var.ats_api_base_url" in worker
    assert "ATS_API_BASE_URL        = var.ats_api_base_url" in ingress
    assert "ats_api_base_url                    = var.ats_api_base_url" in root
    assert "ats_api_base_url         = var.ats_api_base_url" in root

def test_ats_lambdas_have_execution_headroom():
    root = text(ROOT_MAIN)
    variables = text(ROOT_VARS)
    worker = text(LAMBDA_MAIN)
    ingress = text(TF / "modules" / "agent_transport" / "lambda.tf")
    assert 'variable "agent_execution_timeout_seconds"' in variables
    assert "default     = 60" in variables
    assert "var.timeout_seconds" in worker
    assert "timeout     = var.timeout_seconds" in ingress
    assert "timeout_seconds                     = var.agent_execution_timeout_seconds" in root
    assert "timeout_seconds          = var.agent_execution_timeout_seconds" in root
