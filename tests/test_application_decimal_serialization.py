"""ApplicationV1 HTTP serialization of DynamoDB Decimal values.

DynamoDB returns numeric attributes as ``Decimal``. The repository must keep
them as Decimal (storage contract), while the HTTP response must be valid
JSON. These tests pin the response boundary for list, detail, patch and
export, and ensure unknown types still fail closed.
"""

import json
import os
import sys
from decimal import Decimal
from unittest.mock import patch

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler  # noqa: E402
from jobsearch.application_repository import ApplicationConflict  # noqa: E402


ROW = {
    "schemaVersion": Decimal("1"),
    "applicationId": "app-decimal-1",
    "version": Decimal("2"),
    "status": "DRAFT",
    "stage": "draft",
    "job": {"jobId": "job-1", "title": "Synthetic"},
    "salary": {"expectation": {"amount": Decimal("50000"),
                               "currency": "EUR", "period": "year"}},
    "ratio": Decimal("12.5"),
}


class FakeRepo:
    def list(self, ctx, limit=50, cursor=None, status_filter=None,
             stage_filter=None):
        return [ROW], None

    def get(self, application_id, ctx):
        return ROW

    def patch(self, application_id, data, ctx):
        return ROW

    def export(self, application_id, ctx):
        return {"application": ROW, "exportedAt": "2026-11-05T00:00:00Z"}


def _event(method, path, body=None, app_id=None):
    return {
        "httpMethod": method,
        "path": path,
        "headers": {},
        "body": json.dumps(body) if body is not None else None,
        "queryStringParameters": None,
        "pathParameters": {"applicationId": app_id} if app_id else None,
    }


def _call(method, path, body=None, app_id=None):
    with patch.object(handler, "_application_ctx",
                      return_value=(object(), None)), \
            patch.object(handler, "_application_repo", return_value=FakeRepo()):
        return handler._application_routes(
            _event(method, path, body, app_id), None, method, path)


def _parsed(response):
    assert response["statusCode"] == 200
    return json.loads(response["body"])


def test_list_serializes_decimal_values():
    payload = _parsed(_call("GET", "/v1/partner/me/applications"))
    item = payload["items"][0]
    assert item["schemaVersion"] == 1
    assert item["version"] == 2
    assert item["ratio"] == 12.5
    assert item["salary"]["expectation"]["amount"] == 50000


def test_detail_serializes_decimal_values():
    payload = _parsed(_call(
        "GET", "/v1/partner/me/applications/app-decimal-1",
        app_id="app-decimal-1"))
    assert payload["application"]["version"] == 2
    assert payload["application"]["schemaVersion"] == 1


def test_patch_serializes_decimal_values():
    payload = _parsed(_call(
        "PATCH", "/v1/partner/me/applications/app-decimal-1",
        body={"expectedVersion": 1}, app_id="app-decimal-1"))
    assert payload["application"]["version"] == 2


def test_export_serializes_nested_decimal_values():
    payload = _parsed(_call(
        "GET", "/v1/partner/me/applications/app-decimal-1/export",
        app_id="app-decimal-1"))
    assert payload["application"]["salary"]["expectation"]["amount"] == 50000
    assert payload["application"]["ratio"] == 12.5


def test_unknown_unserializable_type_still_fails_closed():
    try:
        handler._application_json_default(object())
    except TypeError as exc:
        assert "not JSON serializable" in str(exc)
    else:
        raise AssertionError("unserializable values must not be silently dropped")


class RaisingRepo:
    def __init__(self, exc):
        self.exc = exc

    def create(self, data, ctx):
        raise self.exc


def _create_response(exc):
    path = "/v1/partner/me/applications"
    with patch.object(handler, "_application_ctx",
                      return_value=(object(), None)), \
            patch.object(handler, "_application_repo",
                         return_value=RaisingRepo(exc)):
        return handler._application_routes(
            _event("POST", path, {"job": {"jobId": "job-1"}}), None,
            "POST", path)


def test_serialization_type_error_maps_to_422_not_409():
    response = _create_response(TypeError("Float types are not supported"))
    assert response["statusCode"] == 422
    assert json.loads(response["body"])["code"] == "VALIDATION_ERROR"


def test_real_version_conflict_still_maps_to_409():
    response = _create_response(ApplicationConflict("VERSION_CONFLICT"))
    assert response["statusCode"] == 409
    assert json.loads(response["body"])["code"] == "VERSION_CONFLICT"
