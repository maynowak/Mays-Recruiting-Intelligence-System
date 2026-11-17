"""Partner erasure route recovery: dispatch through the existing lifecycle."""

import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lambda"))

import handler as h  # noqa: E402


def test_partner_edge_declares_erasure_route():
    source = (Path(ROOT) / "terraform" / "modules" / "partner_edge" / "main.tf").read_text(
        encoding="utf-8"
    )
    assert '"POST /v1/partner/me/erasure"' in source


def _event():
    return {
        "httpMethod": "POST",
        "path": "/v1/partner/me/erasure",
        "headers": {},
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/v1/partner/me/erasure",
            },
        },
    }


def test_partner_erasure_dispatches_to_existing_lifecycle(monkeypatch):
    calls = {}

    def context(event):
        calls["context"] = True
        return {"userId": "user-1"}, None

    def erasure(event, context):
        calls["erasure"] = True
        return {"statusCode": 200, "body": '{"complete": true}'}

    monkeypatch.setattr(h, "_partner_profile_context", context)
    monkeypatch.setattr(h, "_handle_me_erasure", erasure)

    response = h._handle_api_event(_event(), None)

    assert response["statusCode"] == 200
    assert calls == {"context": True, "erasure": True}


def test_partner_erasure_does_not_call_erasure_when_context_is_denied(monkeypatch):
    calls = {"erasure": False}

    monkeypatch.setattr(
        h, "_partner_profile_context",
        lambda event: (None, {"statusCode": 401, "body": '{"error":"Unauthorized"}'}),
    )
    monkeypatch.setattr(
        h, "_handle_me_erasure",
        lambda event, context: calls.update(erasure=True) or {"statusCode": 200},
    )

    response = h._handle_api_event(_event(), None)

    assert response["statusCode"] == 401
    assert calls["erasure"] is False
