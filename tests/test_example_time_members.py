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


def test_duplicate_input_name_is_refused_not_overwritten() -> None:
    """Counter-example: a stale reading listed first and a fresh one with the same name used to report fresh."""
    record = _record()
    record["inputs"].insert(0, {"input": "account-standing", "lastResult": "2026-11-14T00:00:00Z", "maxAge": 60})
    assert timing.check(record) == {"entry": "malformed", "code": "duplicate-input"}


def test_duplicate_json_member_is_refused(tmp_path) -> None:
    text = (EXAMPLES / "time_members/record.json").read_text().replace('"maxAge": 7200', '"maxAge": 60, "maxAge": 7200')
    path = tmp_path / "record.json"
    path.write_text(text)
    with pytest.raises(ValueError, match="duplicate-member"):
        timing.load(text)
    assert timing.main(["check_time.py", str(path)]) == 1


@pytest.mark.parametrize("value", ["false", "true", 0, 1, None])
def test_block_time_must_be_a_boolean(value) -> None:
    """Counter-example: the string "false" is truthy, so a log anchor three hours late took the block-time allowance."""
    assert timing.check(_record(anchor__blockTime=value)) == {"entry": "malformed", "code": "blockTime-not-bool"}


@pytest.mark.parametrize("value", ["20261115T080000Z", "2026-W46-7T08Z", "2026-11-15 08:00:00Z", "2026-11-15T08Z",
                                   "2026-11-15T08:00:00+00:00", "2026-02-30T08:00:00Z",
                                   "\u0662\u0660\u0662\u0666-11-15T08:00:00Z"])
def test_only_rfc3339_utc_times_are_read(value) -> None:
    assert timing.check(_record(inputs__0__lastResult=value)) == {"entry": "malformed", "code": "not-rfc3339"}


def test_issued_at_is_checked() -> None:
    assert timing.check(_record(issuedAt="yesterday")) == {"entry": "malformed", "code": "not-rfc3339"}
    record = _record()
    del record["issuedAt"]
    assert timing.check(record) == {"entry": "malformed", "code": "missing-issuedAt"}


@pytest.mark.parametrize("change, code", [
    ({"decision__reportedAt": "noon"}, "not-rfc3339"),
    ({"decision": "reportedAt"}, "missing-reported-at"),
    ({"inputs": {"input": "a"}}, "inputs-not-list"),
    ({"anchor__anchorWithin": 3600.0}, "anchorWithin-not-int"),
])
def test_malformed_members_get_a_code_not_a_crash(change, code) -> None:
    assert timing.check(_record(**change)) == {"entry": "malformed", "code": code}


def test_missing_members_get_a_code_not_a_crash() -> None:
    record = _record()
    del record["inputs"][0]["maxAge"]
    assert timing.check(record) == {"entry": "malformed", "code": "missing-maxAge"}
    record = _record()
    del record["anchor"]["blockTime"]
    assert timing.check(record) == {"entry": "malformed", "code": "missing-blockTime"}
