import json
from pathlib import Path

from installer.ris import load_project_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "installer" / "project-configs" / "ris-dev2.json"
COGNITO = ROOT / "terraform" / "modules" / "cognito" / "main.tf"
API = ROOT / "terraform" / "modules" / "api" / "main.tf"


def test_ris_dev2_identity_overlay_is_managed_and_non_secret():
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert data["project_name"] == "ris-dev2"
    values = data["terraform_vars"]
    assert values["identity_mode"] == "managed"
    assert values["identity_m2m_enabled"] == "false"
    assert values["identity_m2m_fallback_issuer"].endswith("eu-central-1_ojbmoiYGM")
    assert values["identity_m2m_fallback_client_id"] == "82ji073smu1b3fsvj96sonso"
    assert values["orders_lifecycle"] == "disabled"
    assert values["identity_oauth_enabled"] == "true"
    assert values["identity_custom_domain_enabled"] == "false"
    assert values["identity_oauth_callback_urls"] == '["http://localhost:5173/auth/callback"]'
    serialized = json.dumps(values).lower()
    for marker in ("secret", "password", "token", "certificate_arn", "external_cognito"):
        assert marker not in serialized


def test_installer_loads_only_the_dedicated_ris_dev2_overlay():
    values = load_project_config("ris-dev2", installer_dir=ROOT / "installer")
    assert values["identity_mode"] == "managed"
    assert values["identity_m2m_enabled"] == "false"
    assert values["orders_lifecycle"] == "disabled"
    assert values["identity_oauth_enabled"] == "true"
    assert values["identity_custom_domain_enabled"] == "false"
    assert "identity_google_client_secret" not in values


def test_m2m_opt_out_is_conditional_and_human_authorizer_stays_separate():
    cognito = COGNITO.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    assert 'count                                = var.m2m_enabled ? 1 : 0' in cognito
    assert 'count        = var.m2m_enabled ? 1 : 0' in cognito
    assert 'generate_secret = false' in cognito
    assert 'issuer   = var.cognito_issuer' in api
    assert 'issuer   = var.cognito_m2m_issuer' in api
