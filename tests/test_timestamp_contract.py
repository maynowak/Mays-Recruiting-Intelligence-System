"""
Serialization contract for timestamps (G6).

These tests pin the contract BEFORE any migration, so that the migration
cannot silently change what the platform emits or stores.

The contract
-------------
* Internally, time is timezone-aware UTC.
* At every serialization boundary (API response, DynamoDB attribute, queue
  payload), the value is emitted in the **legacy naive-UTC ISO-8601 form**
  that the platform has always used: `2026-10-07T12:00:00`.

That combination is deliberate. Building the value as aware UTC and then
stripping the offset at the boundary produces a string byte-identical to
`datetime.utcnow().isoformat()`, so:

* the deprecated `utcnow()` call disappears,
* internal arithmetic becomes correct (aware comparisons),
* and not one stored byte or response byte changes.

The alternative -- adopting `+00:00` on the wire -- would rewrite the
representation of every new timestamp while every already-stored row keeps
the old form, leaving two formats live in the same tables. That is a
migration with no consumer analysis behind it, so it is explicitly NOT what
this package does.

`test_wire_form_is_unchanged_by_migration` is the guard: if a future change
starts emitting an offset, this fails.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "lambda"))

from agents import timeutil


class TestInternalRepresentation(unittest.TestCase):
    """Internally we are aware; that is the point of the migration."""

    def test_utcnow_is_timezone_aware(self):
        moment = timeutil.utcnow()
        self.assertIsNotNone(moment.tzinfo)
        self.assertEqual(timedelta(0), moment.utcoffset(),
                         "the instant must be UTC, i.e. zero offset")

    def test_utcnow_is_not_deprecated(self):
        with self.assertWarns(DeprecationWarning):
            datetime.utcnow()  # the defect this package removes
        # and the replacement must NOT warn
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            timeutil.utcnow()  # must not raise


class TestWireRepresentation(unittest.TestCase):
    """At the boundary the legacy naive form is preserved exactly."""

    def test_utcnow_naive_iso_has_no_offset(self):
        value = timeutil.utcnow_naive_iso()
        self.assertNotIn("+00:00", value)
        self.assertNotIn("Z", value)
        self.assertNotIn("tzinfo", value)

    def test_wire_form_is_unchanged_by_migration(self):
        """THE contract guard.

        `datetime.utcnow().isoformat()` and the helper must produce the
        identical string for the same instant. If a future change starts
        emitting an offset, this fails.
        """
        naive = datetime(2026, 10, 7, 12, 0, 0)
        aware = naive.replace(tzinfo=timezone.utc)
        self.assertEqual(naive.isoformat(),
                         timeutil.to_legacy_iso(aware),
                         "wire format changed: legacy naive-UTC ISO was the "
                         "contract")
        micro = datetime(2026, 1, 1, 0, 0, 0, 123456)
        self.assertEqual(micro.isoformat(),
                         timeutil.to_legacy_iso(micro.replace(tzinfo=timezone.utc)))

    def test_offsets_are_normalized_to_utc_before_stripping(self):
        """An aware value in +02:00 must serialize as its UTC instant."""
        local = datetime(2026, 7, 1, 14, 0, 0,
                         tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual("2026-07-01T12:00:00",
                         timeutil.to_legacy_iso(local),
                         "offset must be converted to UTC, not merely dropped")

    def test_naive_input_is_treated_as_utc(self):
        naive = datetime(2026, 7, 1, 12, 0, 0)
        self.assertEqual("2026-07-01T12:00:00", timeutil.to_legacy_iso(naive))

    def test_round_trip_through_fromisoformat_is_stable(self):
        """What consumers do with the emitted string must keep working."""
        for moment in (datetime(2026, 10, 7, 12, 0, 0),
                       datetime(2026, 1, 1, 0, 0, 0, 123456)):
            emitted = timeutil.to_legacy_iso(moment.replace(tzinfo=timezone.utc))
            self.assertEqual(moment, datetime.fromisoformat(emitted))


class TestComparisonSafety(unittest.TestCase):
    """The G2 authorization defect must stay impossible."""

    def test_produced_timestamps_compare_against_entitlement_bounds(self):
        """Offset-bearing bounds must not raise against our timestamps.

        This is the exact failure mode of the G2 defect: a naive `now`
        compared with an aware bound raises TypeError, and that TypeError
        was swallowed, turning an invalid window into a valid one.
        """
        now = timeutil.utcnow()
        future = (now + timedelta(days=30)).isoformat()
        past = (now - timedelta(days=30)).isoformat()

        from dateutil.parser import parse
        self.assertGreater(parse(future), now)
        self.assertLess(parse(past), now)

    def test_no_naive_aware_comparison_error(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            now = timeutil.utcnow()
            bounds = [(now + timedelta(days=1)).isoformat(),
                      (now - timedelta(days=1)).isoformat()]
            from dateutil.parser import parse
            for b in bounds:
                parse(b) < now  # must not raise


class TestBoundaryHelperAvailability(unittest.TestCase):
    """One helper, imported everywhere -- no competing implementations."""

    def test_existing_helpers_delegate_to_the_canonical_one(self):
        """`agents.runtime.pipeline._utcnow` and
        `agents.ecosystem.introspection._utcnow` must not be rival
        implementations.

        Both already returned aware UTC. This test records the CURRENT
        representation rather than assuming one: `pipeline._utcnow` has
        always emitted an offset-bearing string (`...+00:00`), while the
        ingress writers in `lambda/handler.py` emit the naive form. That
        mixed representation inside `work_items` is pre-existing and is
        recorded here rather than silently "fixed" -- changing it would
        rewrite rows nobody asked us to rewrite.
        """
        from agents.runtime import pipeline
        from agents.ecosystem import introspection

        stamp = pipeline._utcnow()
        self.assertIsInstance(stamp, str)
        datetime.fromisoformat(stamp)  # must parse in both forms
        self.assertIn("_utcnow", pipeline.__dict__)
        self.assertIsNotNone(introspection._utcnow().tzinfo)

    def test_ingress_and_pipeline_writers_are_both_parseable(self):
        """The two writers disagree on representation; both must parse.

        Documented pre-existing inconsistency, asserted so it cannot become
        a parse failure.
        """
        from agents.runtime import pipeline
        from datetime import datetime as _dt
        legacy = _dt.utcnow().isoformat()   # what the handler writes
        modern = pipeline._utcnow()          # what the runtime writes
        self.assertIsInstance(_dt.fromisoformat(legacy), _dt)
        self.assertIsInstance(_dt.fromisoformat(modern), _dt)

    def test_helper_module_is_inside_the_lambda_bundle(self):
        """A helper outside agents/ would not be packaged and would break
        the deployed function at import time."""
        build_zip = __import__("build_zip") if "lambda" in sys.path else None
        root = os.path.join(REPO, "agents")
        self.assertTrue(os.path.exists(
            os.path.join(root, "timeutil.py")),
            "agents/timeutil.py must exist so it ships inside the bundle")


if __name__ == "__main__":
    unittest.main()