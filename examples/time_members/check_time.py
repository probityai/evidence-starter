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
- an anchor (a transparency-log entry or a block time) counts only when it lands
  no later than `anchorWithin` plus its allowance after the time the anchor is
  due from; a block-time anchor takes the block-time allowance, a log anchor the
  skew tolerance.

    python examples/time_members/check_time.py examples/time_members/record.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SAFE = 2**53 - 1
SKEW_SECONDS = 300
BLOCK_TIME_ALLOWANCE_SECONDS = 7200


def instant(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"not an RFC 3339 UTC time: {value!r}")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def safe_integer(value: Any) -> int:
    if type(value) is not int:
        raise ValueError("not-an-integer")
    if abs(value) > SAFE:
        raise ValueError("unsafe-integer")
    return value


def freshness(entry: dict, reported_at: datetime, skew: int = SKEW_SECONDS) -> str:
    """Return fresh, stale, not-established, or raise ValueError with a code."""
    max_age = safe_integer(entry["maxAge"])
    if entry["lastResult"] == "none":
        return "not-established"
    age = (reported_at - instant(entry["lastResult"])).total_seconds()
    if age < -skew:
        raise ValueError("last-result-after-report")
    return "fresh" if max_age >= 0 and age <= max_age else "stale"


def anchor_on_time(due_from: str, anchored_at: str, anchor_within: int, *, block_time: bool) -> bool:
    allowance = BLOCK_TIME_ALLOWANCE_SECONDS if block_time else SKEW_SECONDS
    late_by = (instant(anchored_at) - instant(due_from)).total_seconds() - safe_integer(anchor_within)
    return late_by <= allowance


def check(record: dict) -> dict[str, Any]:
    """Judge every time member of a record shaped like `record.json`."""
    if "reportedAt" not in record.get("decision", {}):
        return {"entry": "malformed", "code": "missing-reported-at"}
    reported_at = instant(record["decision"]["reportedAt"])
    try:
        inputs = {e["input"]: freshness(e, reported_at) for e in record["inputs"]}
        anchor = record.get("anchor")
        if anchor is not None and not anchor_on_time(anchor["dueFrom"], anchor["anchoredAt"],
                                                     anchor["anchorWithin"], block_time=anchor["blockTime"]):
            return {"entry": "malformed", "code": "entry-anchor-late"}
    except ValueError as refusal:
        return {"entry": "malformed", "code": str(refusal)}
    return {"entry": "well-formed", "inputs": inputs}


def main(argv: list[str]) -> int:
    result = check(json.loads(Path(argv[1]).read_text()))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["entry"] == "well-formed" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
