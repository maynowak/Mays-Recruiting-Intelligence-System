"""Scoped DynamoDB persistence for ApplicationV1.

The repository never accepts identity from a payload. All access paths include
the verified context and all writes use conditions or transactions.
"""

from __future__ import annotations

import hashlib
import base64
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

try:
    import boto3
    from boto3.dynamodb.conditions import Key
    from boto3.dynamodb.types import TypeSerializer
except ImportError:  # pragma: no cover - Lambda provides boto3
    boto3 = None
    Key = None
    TypeSerializer = None

from jobsearch.application_contract import (
    ApplicationContractError, ApplicationContext, validate_create,
    JOBSEARCH_STAGES, STATUSES, legacy_status_stage, validate_patch, validate_stage_filter,
    validate_cover_letter_version, validate_stage_transition, validate_status_filter,
    validate_transition,
)


class ApplicationNotFound(LookupError):
    pass


class ApplicationConflict(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ApplicationRepository:
    def __init__(self, table_name: str | None = None, dynamodb: Any = None,
                 profile_repository: Any = None):
        self.table_name = table_name or os.environ.get("APPLICATIONS_TABLE")
        if not self.table_name:
            raise ValueError("APPLICATIONS_TABLE is required")
        self.dynamodb = dynamodb or boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)
        # Use a dedicated low-level client for serialized transaction values.
        # Moto and botocore otherwise retain the resource client's conversion
        # hooks and reject nested AttributeValue maps.
        region = self.dynamodb.meta.client.meta.region_name
        endpoint = self.dynamodb.meta.client.meta.endpoint_url
        self.client = boto3.client("dynamodb", region_name=region, endpoint_url=endpoint)
        self.profile_repository = profile_repository
        if self.profile_repository is None and os.environ.get("PARTNER_PROFILE_TABLE"):
            from jobsearch.partner_profile_repository import PartnerProfileRepository
            self.profile_repository = PartnerProfileRepository(
                table_name=os.environ["PARTNER_PROFILE_TABLE"], dynamodb=self.dynamodb)

    @staticmethod
    def _scope(ctx: ApplicationContext) -> str:
        ctx.validate()
        return "|".join((ctx.tenant_id, ctx.user_id, ctx.partner_application_id, ctx.issuer))

    @staticmethod
    def _transaction_item(item: dict[str, Any]) -> dict[str, Any]:
        """Serialize resource values for the low-level DynamoDB client."""
        serializer = TypeSerializer()
        result = dict(item)
        if "Item" in result:
            result["Item"] = {key: serializer.serialize(value) for key, value in result["Item"].items()}
        if "Key" in result:
            result["Key"] = {key: serializer.serialize(value) for key, value in result["Key"].items()}
        if "ExpressionAttributeValues" in result:
            result["ExpressionAttributeValues"] = {
                key: serializer.serialize(value)
                for key, value in result["ExpressionAttributeValues"].items()
            }
        return result

    def _transact(self, items: list[dict[str, Any]]) -> None:
        self.client.transact_write_items(
            TransactItems=[{action: self._transaction_item(value)
                            for action, value in item.items()}
                           for item in items])

    @staticmethod
    def _idempotency_key(ctx: ApplicationContext, key: str) -> str:
        return hashlib.sha256((ApplicationRepository._scope(ctx) + "|" + key).encode()).hexdigest()

    @staticmethod
    def _cursor_secret() -> bytes:
        secret = os.environ.get("RIS_CURSOR_SECRET")
        if not secret:
            raise RuntimeError("RIS_CURSOR_SECRET is required for pagination")
        return secret.encode()

    def issue_cursor(self, key: dict[str, Any], *, user_id: str, tenant_id: str,
                     partner_app_id: str | None, issuer: str | None,
                     scope: str, resource_type: str, limit: int,
                     status_filter: str | None = None,
                     stage_filter: str | None = None) -> str:
        payload = {"key": key, "scope": scope, "resourceType": resource_type,
                   "limit": limit, "statusFilter": status_filter,
                   "stageFilter": stage_filter,
                   "owner": "|".join((tenant_id, user_id, partner_app_id or "", issuer or ""))}
        raw = base64.urlsafe_b64encode(_json(payload).encode()).decode().rstrip("=")
        sig = hmac.new(self._cursor_secret(), raw.encode(), hashlib.sha256).hexdigest()
        return raw + "." + sig

    def resolve_cursor(self, token: str, *, user_id: str, tenant_id: str,
                       partner_app_id: str | None, issuer: str | None,
                       scope: str, resource_type: str, limit: int,
                       status_filter: str | None = None,
                       stage_filter: str | None = None) -> dict[str, Any]:
        try:
            raw, sig = token.split(".", 1)
            expected = hmac.new(self._cursor_secret(), raw.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected):
                raise ValueError
            payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
            owner = "|".join((tenant_id, user_id, partner_app_id or "", issuer or ""))
            if (payload.get("scope") != scope or payload.get("resourceType") != resource_type
                    or payload.get("limit") != limit
                    or payload.get("statusFilter") != status_filter
                    or payload.get("stageFilter") != stage_filter
                    or payload.get("owner") != owner):
                raise ValueError
            return payload["key"]
        except Exception as exc:
            raise ValueError("invalid cursor") from exc

    def _owned(self, application_id: str, ctx: ApplicationContext,
               consistent: bool = True, allow_deleting: bool = False) -> dict[str, Any]:
        row = self.table.get_item(Key={"applicationId": application_id, "entityKey": "META"}, ConsistentRead=consistent).get("Item")
        if not row or row.get("ownerKey") != self._scope(ctx):
            raise ApplicationNotFound("application not found")
        if row.get("deletionState") == "IN_PROGRESS" and not allow_deleting:
            raise ApplicationConflict("ERASURE_IN_PROGRESS")
        return row

    def _verify_cv_reference(self, reference: Mapping[str, Any], ctx: ApplicationContext) -> None:
        """Verify a canonical CV reference through the existing profile store."""
        cv_id = reference.get("cvId")
        if self.profile_repository is None:
            raise ApplicationContractError("REFERENCE_STORE_UNAVAILABLE", "CV ownership cannot be verified")
        resource = self.profile_repository.get(
            cv_id, ctx.user_id, ctx.tenant_id, ctx.partner_application_id, ctx.issuer)
        if resource is None or getattr(resource, "cv_id", None) != cv_id:
            raise ApplicationContractError("CV_NOT_OWNED", "cvReference is not owned by the caller")
        document_id = reference.get("documentId")
        if document_id is not None and getattr(resource, "document_id", None) != document_id:
            raise ApplicationContractError("CV_DOCUMENT_MISMATCH", "cvReference document is not owned by the caller")

    def _verify_legacy_reference(self, reference: Mapping[str, Any], name: str,
                                 ctx: ApplicationContext) -> None:
        if self.profile_repository is None:
            # Existing records and synthetic local fixtures may carry legacy
            # references without a profile table. New documents.cvReference
            # remains fail-closed through _verify_cv_reference above.
            return
        resource = self.profile_repository.get(
            reference["id"], ctx.user_id, ctx.tenant_id,
            ctx.partner_application_id, ctx.issuer)
        if resource is None:
            raise ApplicationContractError("REFERENCE_NOT_OWNED", f"{name} is not owned by the caller")
        if name == "cvRef" and getattr(resource, "resource_type", None) != "CVDocument":
            raise ApplicationContractError("INVALID_REFERENCE", "cvRef is not a CV reference")

    @staticmethod
    def _public(row: Mapping[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in row.items() if k not in {"entityKey", "ownerKey", "idempotencyHash", "entityType", "deletionState"}}

    def create(self, data: Mapping[str, Any], ctx: ApplicationContext) -> dict[str, Any]:
        ctx.validate()
        parsed = validate_create(data)
        for name in ("profileRef", "cvRef"):
            if name in parsed:
                self._verify_legacy_reference(parsed[name], name, ctx)
        if parsed.get("documents", {}).get("cvReference") is not None:
            self._verify_cv_reference(parsed["documents"]["cvReference"], ctx)
        stamp, app_id = _now(), str(uuid.uuid4())
        idempotency_key = parsed.pop("idempotencyKey", None)
        request_hash = hashlib.sha256(_json(parsed).encode()).hexdigest()
        row = {
            **parsed, "schemaVersion": 1, "applicationId": app_id, "entityKey": "META",
            "entityType": "META", "userId": ctx.user_id, "tenantId": ctx.tenant_id,
            "partnerApplicationId": ctx.partner_application_id, "issuer": ctx.issuer,
            "ownerKey": self._scope(ctx), "status": "DRAFT", "version": 1,
            "stage": "draft", "createdAt": stamp, "updatedAt": stamp, "submittedAt": None,
        }
        items = [{"Put": {"TableName": self.table_name, "Item": row,
                            "ConditionExpression": "attribute_not_exists(applicationId)"}}]
        if idempotency_key:
            idem = self._idempotency_key(ctx, idempotency_key)
            row["idempotencyHash"] = idem
            items.append({"Put": {"TableName": self.table_name,
                                   "Item": {"applicationId": "IDEMP#" + idem, "entityKey": "IDEMP",
                                             "entityType": "IDEMP", "ownerKey": self._scope(ctx),
                                             "targetApplicationId": app_id, "requestHash": request_hash,
                                             "createdAt": stamp},
                                   "ConditionExpression": "attribute_not_exists(applicationId)"}})
        try:
            self._transact(items)
        except Exception as exc:
            # An idempotent retry returns the original row after the conditional
            # conflict; other conditional conflicts are safe conflicts.
            if idempotency_key:
                existing = self.table.get_item(Key={"applicationId": "IDEMP#" + self._idempotency_key(ctx, idempotency_key), "entityKey": "IDEMP"}, ConsistentRead=True).get("Item")
                if existing and existing.get("targetApplicationId"):
                    if existing.get("requestHash") != request_hash:
                        raise ApplicationConflict("IDEMPOTENCY_PAYLOAD_CONFLICT") from exc
                    return self._public(self._owned(existing["targetApplicationId"], ctx))
            raise ApplicationConflict("application already exists or could not be created") from exc
        return self._public(row)

    def get(self, application_id: str, ctx: ApplicationContext) -> dict[str, Any]:
        return self._public(self._owned(application_id, ctx))

    def list(self, ctx: ApplicationContext, limit: int = 50, cursor: dict[str, Any] | None = None,
             status_filter: str | None = None, stage_filter: str | None = None) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        if not 1 <= limit <= 100:
            raise ApplicationContractError("INVALID_LIMIT", "limit is invalid")
        if status_filter is not None:
            validate_status_filter(status_filter)
        if stage_filter is not None:
            validate_stage_filter(stage_filter)
        if status_filter is not None and stage_filter is not None:
            raise ApplicationContractError("FILTER_CONFLICT", "status and stage filters cannot be combined")
        items: list[dict[str, Any]] = []
        start_key = cursor
        last_key = None
        while len(items) < limit:
            kwargs: dict[str, Any] = {"IndexName": "gsi-owner", "KeyConditionExpression": Key("ownerKey").eq(self._scope(ctx)), "Limit": limit, "ScanIndexForward": False}
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            result = self.table.query(**kwargs)
            page = [x for x in result.get("Items", []) if x.get("entityType") == "META" and not x.get("deletionState")]
            if status_filter is not None:
                page = [x for x in page if x.get("status") == status_filter]
            if stage_filter is not None:
                page = [x for x in page if (x.get("stage") or legacy_status_stage(x.get("status"))) == stage_filter]
            items.extend(page)
            last_key = result.get("LastEvaluatedKey")
            if not last_key:
                break
            start_key = last_key
        return [self._public(x) for x in items[:limit]], last_key

    def metrics(self, ctx: ApplicationContext) -> dict[str, int]:
        """Compute complete owner metrics by consuming every cursor page."""
        ctx.validate()
        rows: list[dict[str, Any]] = []
        cursor = None
        while True:
            page, cursor = self.list(ctx, limit=100, cursor=cursor)
            rows.extend(page)
            if not cursor:
                break
        today = datetime.now(timezone.utc).date().isoformat()
        open_follow_ups = [
            row.get("followUp") for row in rows
            if isinstance(row.get("followUp"), Mapping) and row["followUp"].get("status") == "open"
        ]
        submitted = {"submitted"}
        interviews = {"interview"}
        drafts = sum(1 for row in rows if row.get("stage") == "draft" or ("stage" not in row and row.get("status") == "DRAFT"))
        sent = sum(1 for row in rows if row.get("stage") in submitted or ("stage" not in row and row.get("status") == "SUBMITTED"))
        conversations = sum(1 for row in rows if row.get("stage") in interviews)
        overdue = sum(1 for item in open_follow_ups if isinstance(item.get("dueOn"), str) and item["dueOn"] < today)
        return {
            "total": len(rows),
            "drafts": drafts,
            "submitted": sent,
            "interviews": conversations,
            "openFollowUps": len(open_follow_ups),
            "overdueFollowUps": overdue,
        }

    def patch(self, application_id: str, data: Mapping[str, Any], ctx: ApplicationContext) -> dict[str, Any]:
        current = self._owned(application_id, ctx)
        parsed = validate_patch(data)
        if parsed["expectedVersion"] != current.get("version"):
            raise ApplicationConflict("VERSION_CONFLICT")
        updates = {k: v for k, v in parsed.items() if k != "expectedVersion"}
        for name in ("profileRef", "cvRef"):
            if name in updates:
                self._verify_legacy_reference(updates[name], name, ctx)
        stamp = _now()
        documents = current.get("documents")
        if "documents" in updates and updates["documents"] is not None:
            if updates["documents"].get("cvReference") is not None:
                self._verify_cv_reference(updates["documents"]["cvReference"], ctx)
            documents = {**(documents if isinstance(documents, Mapping) else {}), **updates.pop("documents")}
            updates["documents"] = documents
        for name in ("applicationDate", "applicationChannel", "contact", "notes", "salary", "followUp", "documents"):
            if name in updates and updates[name] is None:
                updates.pop(name)
                current.pop(name, None)
                if name == "documents":
                    continue
        current.update(updates, version=current["version"] + 1, updatedAt=stamp)
        try:
            self.table.put_item(Item=current, ConditionExpression="version = :expected AND ownerKey = :owner", ExpressionAttributeValues={":expected": parsed["expectedVersion"], ":owner": self._scope(ctx)})
        except Exception as exc:
            raise ApplicationConflict("VERSION_CONFLICT") from exc
        return self._public(current)

    def status(self, application_id: str, target: str, expected_version: int, confirm: bool,
               ctx: ApplicationContext, note: str | None = None) -> dict[str, Any]:
        current = self._owned(application_id, ctx)
        is_stage = target in JOBSEARCH_STAGES
        if is_stage:
            current_stage = current.get("stage") or legacy_status_stage(current["status"])
            if current_stage is None:
                raise ApplicationContractError("STAGE_UNAVAILABLE", "legacy status has no jobsearch stage")
            validate_stage_transition(current_stage, target, confirm)
        else:
            validate_transition(current["status"], target, confirm)
        if current["version"] != expected_version:
            raise ApplicationConflict("VERSION_CONFLICT")
        stamp = _now()
        history = {"applicationId": application_id, "entityKey": "HISTORY#" + stamp + "#" + str(uuid.uuid4()), "entityType": "HISTORY", "ownerKey": self._scope(ctx), "status": target, "fromStatus": current.get("status"), "toStatus": target if not is_stage else current.get("status"), "createdAt": stamp, "actorUserId": ctx.user_id}
        if note is not None:
            history["note"] = note
        updated = dict(current)
        if is_stage:
            updated["stage"] = target
            updated["status"] = "SUBMITTED" if target in {"submitted", "feedback", "interview", "offer", "rejected"} else "WITHDRAWN" if target == "withdrawn" else "DRAFT"
            history.update(fromStage=current.get("stage", "draft"), toStage=target)
        else:
            updated["status"] = target
            projected_stage = legacy_status_stage(target)
            if projected_stage is not None:
                updated["stage"] = projected_stage
        updated.update(version=expected_version + 1, updatedAt=stamp, submittedAt=stamp if target in {"SUBMITTED", "submitted"} else current.get("submittedAt"))
        current = updated
        tx = [{"Put": {"TableName": self.table_name, "Item": current, "ConditionExpression": "version = :expected AND ownerKey = :owner", "ExpressionAttributeValues": {":expected": expected_version, ":owner": self._scope(ctx)}}}, {"Put": {"TableName": self.table_name, "Item": history, "ConditionExpression": "attribute_not_exists(applicationId)"}}]
        try:
            self._transact(tx)
        except Exception as exc:
            raise ApplicationConflict("VERSION_CONFLICT") from exc
        return self._public(current)

    def add_history(self, application_id: str, event: Mapping[str, Any], expected_version: int, ctx: ApplicationContext) -> dict[str, Any]:
        current = self._owned(application_id, ctx)
        if current["version"] != expected_version:
            raise ApplicationConflict("VERSION_CONFLICT")
        if not isinstance(event, Mapping) or not isinstance(event.get("type"), str):
            raise ApplicationContractError("INVALID_HISTORY", "history type is required")
        stamp = _now()
        item = {"applicationId": application_id, "entityKey": "HISTORY#" + stamp + "#" + str(uuid.uuid4()), "entityType": "HISTORY", "ownerKey": self._scope(ctx), "event": dict(event), "createdAt": stamp, "actorUserId": ctx.user_id}
        updated = dict(current, version=expected_version + 1, updatedAt=stamp)
        try:
            self._transact([
                {"Put": {"TableName": self.table_name, "Item": updated, "ConditionExpression": "version = :expected AND ownerKey = :owner", "ExpressionAttributeValues": {":expected": expected_version, ":owner": self._scope(ctx)} }},
                {"Put": {"TableName": self.table_name, "Item": item, "ConditionExpression": "attribute_not_exists(applicationId)"}},
            ])
        except Exception as exc:
            raise ApplicationConflict("VERSION_CONFLICT") from exc
        return {**item, "applicationVersion": updated["version"]}

    def add_cover_letter(self, application_id: str, letter: str, expected_version: int, ctx: ApplicationContext) -> dict[str, Any]:
        current = self._owned(application_id, ctx)
        if not isinstance(letter, str) or not letter.strip() or len(letter) > 100_000:
            raise ApplicationContractError("INVALID_COVER_LETTER", "cover letter is invalid")
        if current["version"] != expected_version:
            raise ApplicationConflict("VERSION_CONFLICT")
        stamp = _now(); version_id = str(uuid.uuid4())
        version = letter if isinstance(letter, Mapping) else {"jobId": current["job"]["jobId"], "content": letter, "source": "manual"}
        version = validate_cover_letter_version(version)
        if version["jobId"] != current["job"]["jobId"]:
            raise ApplicationContractError("INVALID_COVER_LETTER", "cover-letter jobId does not match application")
        version.setdefault("versionId", version_id)
        version.setdefault("createdAt", stamp)
        item = {"applicationId": application_id, "entityKey": "COVER#" + stamp + "#" + version["versionId"], "entityType": "COVER_LETTER", "ownerKey": self._scope(ctx), "versionId": version["versionId"], "jobId": version["jobId"], "content": version["content"], "source": version["source"], "createdAt": version["createdAt"], "actorUserId": ctx.user_id}
        for field in ("language", "model"):
            if field in version:
                item[field] = version[field]
        documents = dict(current.get("documents") or {"coverLetterDraft": "", "coverLetterVersions": [], "documentStatus": "missing"})
        documents["coverLetterVersions"] = list(documents.get("coverLetterVersions") or []) + [version]
        if documents.get("documentStatus") == "missing":
            documents["documentStatus"] = "draft"
        updated = dict(current, documents=documents, version=expected_version + 1, updatedAt=stamp)
        try:
            self._transact([
                {"Put": {"TableName": self.table_name, "Item": updated, "ConditionExpression": "version = :expected AND ownerKey = :owner", "ExpressionAttributeValues": {":expected": expected_version, ":owner": self._scope(ctx)} }},
                {"Put": {"TableName": self.table_name, "Item": item, "ConditionExpression": "attribute_not_exists(applicationId)"}},
            ])
        except Exception as exc:
            raise ApplicationConflict("VERSION_CONFLICT") from exc
        return {**version, "applicationVersion": updated["version"]}

    def export(self, application_id: str, ctx: ApplicationContext) -> dict[str, Any]:
        app = self._owned(application_id, ctx)
        children: list[dict[str, Any]] = []
        exclusive_start_key = None
        while True:
            kwargs: dict[str, Any] = {
                "KeyConditionExpression": Key("applicationId").eq(application_id),
                "ConsistentRead": True,
            }
            if exclusive_start_key:
                kwargs["ExclusiveStartKey"] = exclusive_start_key
            page = self.table.query(**kwargs)
            children.extend(page.get("Items", []))
            exclusive_start_key = page.get("LastEvaluatedKey")
            if not exclusive_start_key:
                break
        history = [{k: v for k, v in x.items() if k not in {"ownerKey", "entityType", "entityKey"}} for x in children if x.get("entityType") == "HISTORY"]
        versions = [{k: v for k, v in x.items() if k not in {"ownerKey", "entityType", "entityKey", "text"}} for x in children if x.get("entityType") == "COVER_LETTER"]
        return {"application": self._public(app), "history": history, "coverLetterVersions": versions, "documents": self._public(app).get("documents", {})}

    def delete(self, application_id: str, expected_version: int, ctx: ApplicationContext) -> None:
        current = self._owned(application_id, ctx, allow_deleting=True)
        if current.get("version") != expected_version:
            raise ApplicationConflict("VERSION_CONFLICT")
        if current.get("deletionState") != "IN_PROGRESS":
            marked = dict(current, deletionState="IN_PROGRESS", updatedAt=_now())
            try:
                self.table.put_item(
                    Item=marked,
                    ConditionExpression="version = :expected AND ownerKey = :owner",
                    ExpressionAttributeValues={":expected": expected_version, ":owner": self._scope(ctx)},
                )
            except Exception as exc:
                raise ApplicationConflict("VERSION_CONFLICT") from exc
            current = marked
        children: list[dict[str, Any]] = []
        exclusive_start_key = None
        while True:
            kwargs: dict[str, Any] = {
                "KeyConditionExpression": Key("applicationId").eq(application_id),
                "ConsistentRead": True,
            }
            if exclusive_start_key:
                kwargs["ExclusiveStartKey"] = exclusive_start_key
            page = self.table.query(**kwargs)
            children.extend(page.get("Items", []))
            exclusive_start_key = page.get("LastEvaluatedKey")
            if not exclusive_start_key:
                break
        children = [child for child in children if child.get("entityType") != "META"]
        actions = [{"Delete": {"TableName": self.table_name,
                                "Key": {"applicationId": child["applicationId"], "entityKey": child["entityKey"]},
                                "ConditionExpression": "ownerKey = :owner",
                                "ExpressionAttributeValues": {":owner": self._scope(ctx)}}}
                   for child in children]
        idempotency_hash = current.get("idempotencyHash")
        try:
            for offset in range(0, len(actions), 100):
                self._transact(actions[offset:offset + 100])
            final_actions = [{"Delete": {"TableName": self.table_name,
                                           "Key": {"applicationId": application_id, "entityKey": "META"},
                                           "ConditionExpression": "ownerKey = :owner AND version = :expected AND deletionState = :state",
                                           "ExpressionAttributeValues": {":owner": self._scope(ctx), ":expected": expected_version, ":state": "IN_PROGRESS"}}}]
            if idempotency_hash:
                final_actions.append({"Delete": {"TableName": self.table_name,
                                                   "Key": {"applicationId": "IDEMP#" + idempotency_hash, "entityKey": "IDEMP"},
                                                   "ConditionExpression": "ownerKey = :owner",
                                                   "ExpressionAttributeValues": {":owner": self._scope(ctx)}}})
            self._transact(final_actions)
        except Exception as exc:
            raise ApplicationConflict("VERSION_CONFLICT") from exc
