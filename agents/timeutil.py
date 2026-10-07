"""
Canonical UTC helpers (Gate-06).

One place defines "now", so the runtime does not accumulate rival
implementations.

Two representations exist on purpose:

``utcnow()``
    Timezone-aware UTC ``datetime``. Use this for anything that is
    *compared*, *subtracted* or *reasoned about* internally. Aware values
    cannot silently disagree with offset-bearing inputs.

``utcnow_naive_iso()`` / ``to_legacy_iso()``
    The legacy naive-UTC ISO-8601 **wire and persistence** form,
    ``2026-10-07T12:00:00``. This is what the platform has always emitted
    and stored, and what its consumers parse.

Why keep the legacy form rather than adopting ``+00:00``?

Because every timestamp already sitting in DynamoDB is in the naive form.
Emitting ``+00:00`` from here on would leave two formats live in the same
tables, and would change the representation of API responses with no
consumer analysis behind the change. Producing the aware instant and then
stripping the offset at the boundary is byte-identical to the old output:

    datetime.utcnow().isoformat()
        == datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

so the deprecation is removed and correctness improves internally while the
external contract stays exactly as it was.

This module lives under ``agents/`` deliberately: that directory is part of
the Lambda bundle (``lambda/handler.py``, ``lambda/documents.py``,
``agents/``, ``jobsearch/``), so anything placed here is packaged and
importable from both the handler and the agent runtime. A helper at the
repository root would not ship and would break the deployed function.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    """Timezone-aware UTC now. Use for internal reasoning."""
    return datetime.now(timezone.utc)


def to_legacy_iso(moment: Optional[datetime]) -> Optional[str]:
    """Serialize to the legacy naive-UTC ISO-8601 wire form.

    An aware value is converted to UTC first, so ``+02:00`` inputs are
    normalized rather than having their offset silently dropped. A naive
    value is treated as UTC, matching what the platform has always stored.
    Returns ``None`` for ``None`` so optional fields stay optional.
    """
    if moment is None:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment.isoformat()


def utcnow_naive_iso() -> str:
    """Current UTC instant in the legacy naive-UTC ISO-8601 form.

    The direct, byte-compatible replacement for
    ``datetime.utcnow().isoformat()``.
    """
    return utcnow().replace(tzinfo=None).isoformat()


__all__ = ["utcnow", "to_legacy_iso", "utcnow_naive_iso"]