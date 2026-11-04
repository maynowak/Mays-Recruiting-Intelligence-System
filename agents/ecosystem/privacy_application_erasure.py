"""Resumable, identity-scoped ApplicationV1 erasure executor.

The existing privacy orchestrator owns durable operation/checkpoint storage.
This executor supplies the application phase: it reads only the owner GSI,
deletes one complete application transaction at a time, and returns the raw
DynamoDB cursor for the orchestrator to persist. No global feature flag is
enabled by importing this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jobsearch.application_contract import ApplicationContext
from jobsearch.application_repository import ApplicationConflict, ApplicationRepository


@dataclass(frozen=True)
class ApplicationErasureProgress:
    deleted: int
    pending: bool
    cursor: dict[str, Any] | None
    failed_application_id: str | None = None


class ApplicationErasureExecutor:
    def __init__(self, repository: ApplicationRepository):
        self.repository = repository

    def run(self, context: ApplicationContext, *, cursor: dict[str, Any] | None = None,
            limit: int = 25) -> ApplicationErasureProgress:
        context.validate()
        items, next_cursor = self.repository.list(
            context, limit=limit, cursor=cursor, include_deleting=True)
        deleted = 0
        for item in items:
            try:
                self.repository.delete(item["applicationId"], item["version"], context)
                deleted += 1
            except (ApplicationConflict, KeyError):
                # The orchestrator persists this cursor and retries the same
                # page. A partial result is never reported as complete.
                return ApplicationErasureProgress(
                    deleted=deleted, pending=True, cursor=cursor,
                    failed_application_id=item.get("applicationId"))
        return ApplicationErasureProgress(
            deleted=deleted, pending=bool(next_cursor), cursor=next_cursor)
