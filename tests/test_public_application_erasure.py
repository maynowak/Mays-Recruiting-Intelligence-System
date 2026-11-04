import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "lambda"))
import handler


class _Ddb:
    def Table(self, name):
        return SimpleNamespace(name=name)


def _event():
    return {
        "httpMethod": "POST", "path": "/me/erasure",
        "requestContext": {"authorizer": {"jwt": {"claims": {
            "sub": "user-1", "custom:tenant_id": "tenant-1",
            "custom:partner_application_id": "partner-1",
            "iss": "https://issuer.example", "token_use": "access",
        }}}},
    }


def test_public_erasure_constructs_application_executor(monkeypatch):
    for name in ("CREDENTIALS_TABLE", "API_PROFILES_TABLE", "WORK_ITEMS_TABLE",
                 "USER_PROFILE_TABLE", "APPLICATIONS_TABLE"):
        monkeypatch.setenv(name, name.lower())
    monkeypatch.setattr(handler, "_get_dynamodb", lambda: _Ddb())
    captured = {}

    class Store:
        def __init__(self, **kwargs):
            pass

    class ApplicationRepository:
        def __init__(self, **kwargs):
            captured["repo"] = self

    class ApplicationExecutor:
        def __init__(self, repo):
            captured["executor_repo"] = repo

    class Erasure:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def erase(self, user_id, tenant_id=None):
            return SimpleNamespace(complete=True, to_dict=lambda: {
                "userId": user_id, "tenantId": tenant_id, "complete": True,
                "steps": []})

    import agents.ecosystem.privacy_erasure as legacy
    import agents.ecosystem.credentials as credentials
    import agents.ecosystem.api_profiles as profiles
    import agents.ecosystem.privacy_application_erasure as app_erasure
    import jobsearch.application_repository as app_repo
    monkeypatch.setattr(legacy, "PrivacyErasure", Erasure)
    monkeypatch.setattr(credentials, "DynamoDBCredentialStore", Store)
    monkeypatch.setattr(profiles, "DynamoDBApiProfileStore", Store)
    monkeypatch.setattr(app_erasure, "ApplicationErasureExecutor", ApplicationExecutor)
    monkeypatch.setattr(app_repo, "ApplicationRepository", ApplicationRepository)

    response = handler.handler(_event(), None)
    assert response["statusCode"] == 200
    assert response["headers"]["Cache-Control"] == "no-store, private"
    assert captured["executor_repo"] is captured["repo"]
    assert captured["application_context"].partner_application_id == "partner-1"


def test_public_erasure_fails_closed_without_application_store(monkeypatch):
    for name in ("CREDENTIALS_TABLE", "API_PROFILES_TABLE", "WORK_ITEMS_TABLE",
                 "USER_PROFILE_TABLE"):
        monkeypatch.setenv(name, name.lower())
    monkeypatch.delenv("APPLICATIONS_TABLE", raising=False)
    response = handler._handle_me_erasure(_event(), None)
    assert response["statusCode"] == 503
    assert "unavailable" in json.loads(response["body"])["error"].lower()
