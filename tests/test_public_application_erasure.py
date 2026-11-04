import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "lambda"))
import handler
from agents.ecosystem.privacy_erasure import PrivacyErasure
from jobsearch.application_contract import ApplicationContext


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
    response = handler.handler(_event(), None)
    assert response["statusCode"] == 503
    assert response["headers"]["Cache-Control"] == "no-store, private"
    assert "unavailable" in json.loads(response["body"])["error"].lower()


def test_application_phase_consumes_all_pages_and_resumes_after_cursor():
    class Pages:
        def __init__(self):
            self.cursors = []

        def run(self, context, *, cursor=None):
            self.cursors.append(cursor)
            if cursor is None:
                return SimpleNamespace(deleted=1, pending=True, cursor={"page": 2})
            return SimpleNamespace(deleted=1, pending=False, cursor=None)

    pages = Pages()
    result = PrivacyErasure(
        application_erasure=pages,
        application_context=ApplicationContext("u", "t", "p", "i"),
    ).erase("u", "t")
    assert result.complete
    assert result.applications_deleted == 2
    assert pages.cursors == [None, {"page": 2}]


def test_application_phase_failure_is_not_reported_complete():
    class Broken:
        def run(self, context, *, cursor=None):
            raise RuntimeError("application store unavailable")

    result = PrivacyErasure(
        application_erasure=Broken(),
        application_context=ApplicationContext("u", "t", "p", "i"),
    ).erase("u", "t")
    assert not result.complete
    assert next(step for step in result.steps
                if step.step == "erase-applications").ok is False
