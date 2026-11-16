"""Check the time members of an agent record with asymmetric bounds.

A record that a third party will judge for freshness carries its time members
explicitly. The rules this checker applies, each a one-line function:

- every integer a time rule does arithmetic on is an I-JSON integer
  (|x| <= 2**53 - 1); anything larger is refused as `unsafe-integer` before any
  subtraction, because two parsers disagree on its value;
- an input's age runs from its `lastResult` to the decision's `reportedAt`, and
  an age equal to `maxAge` is still fresh; a negative `maxAge` is stale;
- the bounds are asymmetric: the past side is `maxAge`, the future side is the
  clock-skew tolerance only, so a `lastResult` more than the skew after
  `reportedAt` is malformed rather than fresh;
- a `lastResult` of `none` is never established;
- every time is RFC 3339 UTC written `YYYY-MM-DDTHH:MM:SS[.fraction]Z` with ASCII
  digits; the other ISO 8601 forms a general parser takes (basic, week dates,
  hour only) are refused, because another reader would refuse them;
- the record is parsed with duplicate members refused, every member a rule reads
  must be present with its type (`blockTime` a boolean, never a truthy string),
  and two inputs with one name are refused rather than the last one kept;
- an anchor (a transparency-log entry or a block time) counts only when it lands
  no later than `anchorWithin` plus its allowance after the time the anchor is
  due from; a block-time anchor takes the block-time allowance, a log anchor the
  skew tolerance.

    python examples/time_members/check_time.py examples/time_members/record.json
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SAFE = 2**53 - 1
SKEW_SECONDS = 300
BLOCK_TIME_ALLOWANCE_SECONDS = 7200
RFC3339_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z")


def load(text: str) -> Any:
    """Parse JSON with duplicate members refused: two readers keep different copies of one."""
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        if len({key for key, _ in pairs}) != len(pairs):
            raise ValueError("duplicate-member")
        return dict(pairs)
    return json.loads(text, object_pairs_hook=unique)


def instant(value: Any) -> datetime:
    if not isinstance(value, str) or not RFC3339_UTC.fullmatch(value):
        raise ValueError("not-rfc3339")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise ValueError("not-rfc3339") from None


def member(holder: Any, name: str, kind: type) -> Any:
    if not isinstance(holder, dict) or name not in holder:
        raise ValueError(f"missing-{name}")
    if type(holder[name]) is not kind:
        raise ValueError(f"{name}-not-{kind.__name__}")
    return holder[name]


def safe_integer(value: Any) -> int:
    if type(value) is not int:
        raise ValueError("not-an-integer")
    if abs(value) > SAFE:
        raise ValueError("unsafe-integer")
    return value


def freshness(entry: dict, reported_at: datetime, skew: int = SKEW_SECONDS) -> str:
    """Return fresh, stale, not-established, or raise ValueError with a code."""
    if not isinstance(entry, dict) or "maxAge" not in entry:
        raise ValueError("missing-maxAge")
    max_age = safe_integer(entry["maxAge"])
    if member(entry, "lastResult", str) == "none":
        return "not-established"
    age = (reported_at - instant(entry["lastResult"])).total_seconds()
    if age < -skew:
        raise ValueError("last-result-after-report")
    return "fresh" if max_age >= 0 and age <= max_age else "stale"


def anchor_on_time(due_from: str, anchored_at: str, anchor_within: int, *, block_time: bool) -> bool:
    allowance = BLOCK_TIME_ALLOWANCE_SECONDS if block_time else SKEW_SECONDS
    late_by = (instant(anchored_at) - instant(due_from)).total_seconds() - safe_integer(anchor_within)
    return late_by <= allowance


def judge_inputs(entries: Any, reported_at: datetime) -> dict[str, str]:
    if not isinstance(entries, list):
        raise ValueError("inputs-not-list")
    verdicts: dict[str, str] = {}
    for entry in entries:
        name = member(entry, "input", str)
        if name in verdicts:
            raise ValueError("duplicate-input")
        verdicts[name] = freshness(entry, reported_at)
    return verdicts


def judge_anchor(anchor: Any) -> None:
    if anchor is None:
        return
    on_time = anchor_on_time(member(anchor, "dueFrom", str), member(anchor, "anchoredAt", str),
                             member(anchor, "anchorWithin", int), block_time=member(anchor, "blockTime", bool))
    if not on_time:
        raise ValueError("entry-anchor-late")


def check(record: Any) -> dict[str, Any]:
    """Judge every time member of a record shaped like `record.json`."""
    try:
        if not isinstance(record, dict):
            raise ValueError("record-not-object")
        if not isinstance(record.get("decision"), dict) or "reportedAt" not in record["decision"]:
            return {"entry": "malformed", "code": "missing-reported-at"}
        reported_at = instant(record["decision"]["reportedAt"])
        instant(member(record, "issuedAt", str))
        inputs = judge_inputs(member(record, "inputs", list), reported_at)
        judge_anchor(record.get("anchor"))
    except ValueError as refusal:
        return {"entry": "malformed", "code": str(refusal)}
    return {"entry": "well-formed", "inputs": inputs}


def main(argv: list[str]) -> int:
    try:
        result = check(load(Path(argv[1]).read_text()))
    except ValueError as refusal:
        code = "duplicate-member" if str(refusal) == "duplicate-member" else "not-json"
        result = {"entry": "malformed", "code": code}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["entry"] == "well-formed" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
