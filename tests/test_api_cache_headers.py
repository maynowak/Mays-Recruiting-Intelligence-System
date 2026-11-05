import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ris_lambda_handler_cache", ROOT / "lambda" / "handler.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def event(path):
    return {"httpMethod": "GET", "path": path}


def test_personal_response_boundary_adds_no_store_private():
    response = MODULE._finalize_personal_response(event("/v1/partner/me/applications"), {"statusCode": 401})
    assert response["headers"]["Cache-Control"] == "no-store, private"


def test_personal_response_boundary_preserves_other_headers():
    response = MODULE._finalize_personal_response(
        event("/me/profile"), {"statusCode": 503, "headers": {"X-Test": "1"}})
    assert response["headers"] == {"X-Test": "1", "Cache-Control": "no-store, private"}


def test_public_health_and_unknown_paths_are_not_changed():
    response = MODULE._finalize_personal_response(event("/health"), {"statusCode": 200})
    assert "headers" not in response
    response = MODULE._finalize_personal_response(event("/unknown"), {"statusCode": 404})
    assert "headers" not in response
