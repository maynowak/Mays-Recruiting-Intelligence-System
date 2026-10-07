"""
Health event sink for RIS Health Plane (G7).

The HealthTracker produces HealthEvent objects but never emits them.
This module provides the minimal operational sink: structured CloudWatch
Logs emission. It reuses the existing Lambda logging infrastructure, so
no new AWS service is introduced.

Design constraints:
* Emission failure must never break business processing.
* Events are emitted as JSON, containing only the fields defined by
  HealthEvent.to_dict() — no payload/PII.
* Tenant isolation is preserved by the caller; the sink is passive.
* The sink is deliberately small: log-and-swell. Operators can query
  CloudWatch Logs Insights on the log group.

The sink is fail-safe: any exception is swallowed after warning.
"""

from __future__ import annotations

import json
import logging
from typing import List

from agents.ecosystem.health_plane import HealthEvent

logger = logging.getLogger("ris.health")
# Ensure a distinct logger name so CloudWatch Logs Insights can filter.
logger.setLevel(logging.INFO)


def emit(events: List[HealthEvent]) -> None:
    """Emit health events to the operational sink.

    Each event is serialized via HealthEvent.to_dict() and written as a
    single-line JSON log record. The function is defensive: errors are
    logged at warning level and never propagated.
    """
    if not events:
        return
    for ev in events:
        try:
            # Structured log. Using logger.info keeps the emission within the
            # existing CloudWatch Logs pipeline. No custom metrics or new
            # services are introduced.
            logger.info(json.dumps(ev.to_dict()))
        except Exception:
            # Fail-safe: observability must never break processing.
            # Avoid recursive health emission loops.
            logging.getLogger(__name__).warning(
                "health sink emission failed for event %s", getattr(ev, "event_id", "?"),
                exc_info=True,
            )


__all__ = ["emit"]
