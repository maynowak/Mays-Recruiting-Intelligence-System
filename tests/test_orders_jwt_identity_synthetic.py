"""Synthetic JWT claim/signature and Orders id-token priority checks.

This verifies RIS token selection/forwarding only; it does not assert that an
unavailable Mays-Orders Provider checkout accepts or authorizes the token.
"""

import base64
import hashlib
import hmac
import json

from agents.orders.function import _token


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _synthetic_jwt(claims: dict, secret: bytes) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64(json.dumps(header, separators=(',', ':')).encode())}.{_b64(json.dumps(claims, separators=(',', ':')).encode())}"
    signature = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"


def _verify_synthetic_jwt(token: str, secret: bytes) -> dict:
    header_part, claims_part, signature_part = token.split(".")
    signing_input = f"{header_part}.{claims_part}"
    expected = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    actual = base64.urlsafe_b64decode(signature_part + "=" * (-len(signature_part) % 4))
    assert hmac.compare_digest(actual, expected)
    return json.loads(base64.urlsafe_b64decode(
        claims_part + "=" * (-len(claims_part) % 4)
    ))


def test_orders_uses_signed_work_item_id_token_and_preserves_claim_identity(monkeypatch):
    secret = b"synthetic-only-test-signing-key"
    chosen = _synthetic_jwt({
        "iss": "https://issuer.synthetic.invalid/pool",
        "aud": "synthetic-orders-client",
        "sub": "synthetic-subject-001",
        "custom:tenant_id": "synthetic-tenant-001",
        "token_use": "id",
    }, secret)
    lower_priority = _synthetic_jwt({"sub": "wrong-synthetic-subject"}, secret)
    monkeypatch.setenv("ORDERS_ID_TOKEN", "environment-token-must-not-win")

    work = {
        "auth": {"idToken": chosen},
        "payload": {"auth": {"idToken": lower_priority}},
    }
    selected = _token(work, work["payload"])
    claims = _verify_synthetic_jwt(selected, secret)
    assert selected == chosen
    assert claims["sub"] == "synthetic-subject-001"
    assert claims["custom:tenant_id"] == "synthetic-tenant-001"
    assert claims["aud"] == "synthetic-orders-client"
    assert claims["token_use"] == "id"


def test_engine_wrapped_id_token_is_selected_before_environment_fallback(monkeypatch):
    secret = b"synthetic-only-test-signing-key"
    token = _synthetic_jwt({"sub": "synthetic-wrapped-subject",
                            "custom:tenant_id": "synthetic-wrapped-tenant"}, secret)
    monkeypatch.setenv("ORDERS_ID_TOKEN", "environment-token-must-not-win")
    work = {"payload": {"payload": {"orderId": "synthetic-order"},
                        "auth": {"idToken": token}}}
    from agents.orders.function import _payload

    normalized = _payload(work)
    selected = _token(work, normalized)
    assert selected == token
    claims = _verify_synthetic_jwt(selected, secret)
    assert claims["sub"] == "synthetic-wrapped-subject"
    assert claims["custom:tenant_id"] == "synthetic-wrapped-tenant"
