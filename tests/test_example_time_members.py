"""Time members with asymmetric bounds: the example under examples/time_members."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
_spec = importlib.util.spec_from_file_location("check_time", EXAMPLES / "time_members/check_time.py")
timing = importlib.util.module_from_spec(_spec)
sys.modules["check_time"] = timing
_spec.loader.exec_module(timing)


def _record(**changes) -> dict:
    record = json.loads((EXAMPLES / "time_members/record.json").read_text())
    for path, value in changes.items():
        target = record
        *parents, last = path.split("__")
        for part in parents:
            target = target[int(part)] if part.isdigit() else target[part]
        target[int(last) if last.isdigit() else last] = value
    return record


def test_skeleton_record_is_well_formed() -> None:
    assert timing.check(_record()) == {"entry": "well-formed",
                                       "inputs": {"account-standing": "fresh", "policy-version": "fresh"}}


@pytest.mark.parametrize("max_age, verdict", [
    (2**53 - 1, "well-formed"), (2**53, "unsafe-integer"), (2**53 + 1, "unsafe-integer"),
    (2**64 - 1, "unsafe-integer"), (1.5, "not-an-integer"),
])
def test_max_age_range_is_checked_before_arithmetic(max_age, verdict) -> None:
    result = timing.check(_record(inputs__0__maxAge=max_age))
    assert result.get("code", result["entry"]) == verdict


def test_age_equal_to_max_age_is_fresh_and_one_more_is_stale() -> None:
    assert timing.check(_record(inputs__0__maxAge=7200))["inputs"]["account-standing"] == "fresh"
    assert timing.check(_record(inputs__0__maxAge=7199))["inputs"]["account-standing"] == "stale"
    assert timing.check(_record(inputs__0__maxAge=-1))["inputs"]["account-standing"] == "stale"


def test_future_side_takes_the_skew_only() -> None:
    assert timing.check(_record(inputs__1__lastResult="2026-11-15T10:05:00Z"))["entry"] == "well-formed"
    assert timing.check(_record(inputs__1__lastResult="2026-11-15T10:05:01Z")) == {
        "entry": "malformed", "code": "last-result-after-report"}


def test_none_is_never_established_and_reported_at_is_required() -> None:
    assert timing.check(_record(inputs__0__lastResult="none"))["inputs"]["account-standing"] == "not-established"
    record = _record()
    del record["decision"]["reportedAt"]
    assert timing.check(record) == {"entry": "malformed", "code": "missing-reported-at"}


def test_block_time_allowance_boundary() -> None:
    assert timing.check(_record(anchor__anchoredAt="2026-11-15T13:00:09Z"))["entry"] == "well-formed"
    assert timing.check(_record(anchor__anchoredAt="2026-11-15T13:00:10Z"))["code"] == "entry-anchor-late"
    assert timing.check(_record(anchor__blockTime=False))["code"] == "entry-anchor-late"
