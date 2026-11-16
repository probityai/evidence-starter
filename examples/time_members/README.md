# Time members

A record a third party will judge for freshness carries its time members as
fields, never as prose. `record.json` is the skeleton; `check_time.py` applies
the rules below and prints one verdict.

| member | what it fixes | rule |
|---|---|---|
| `issuedAt` | when the record was written | RFC 3339 UTC; it never dates the inputs |
| `decision.reportedAt` | the time every age is measured to | required; a record without it is malformed |
| `inputs[].lastResult` | when each input was last read | `none` is never established; more than the skew after `reportedAt` is malformed |
| `inputs[].maxAge` | how old that input may be, in seconds | an I-JSON integer (at most 2^53 - 1 in magnitude, else `unsafe-integer`); age equal to `maxAge` is fresh; negative is stale |
| `anchor.anchorWithin` | how soon an independent anchor must land | late by more than the allowance is `entry-anchor-late` |
| skew tolerance | clock disagreement allowed | 300 seconds, on the future side only |
| block-time allowance | a block time's own slack | 7200 seconds for a block-time anchor, in place of the skew |
| `anchor.blockTime` | which allowance applies | a JSON boolean; a string such as `"false"` is malformed, never truthy |

Every time is written `YYYY-MM-DDTHH:MM:SS[.fraction]Z` with ASCII digits; the
basic, week-date and hour-only forms a general ISO 8601 parser takes are
`not-rfc3339`. The record is parsed with duplicate members refused, a missing
member is reported by name (`missing-maxAge`), and two inputs with one name are
`duplicate-input` rather than the last one kept.

The bounds are asymmetric on purpose: the past side is `maxAge`, the future
side is the skew alone, so a reading from the future cannot be stretched into
a fresh one. Integers are range-checked before any subtraction, because two
parsers disagree on the value of a larger one.

```sh
.venv/bin/python examples/time_members/check_time.py examples/time_members/record.json
```

```text
{"entry": "well-formed", "inputs": {"account-standing": "fresh", "policy-version": "fresh"}}
```

These rules follow the freshness section of the
[audit-record corpus](https://github.com/probityai/agent-evidence-vectors/tree/main/corpora/vectors-agent-audit-record)
in agent-evidence-vectors, whose members pin each boundary. Run that corpus
against your own reader with the vectors Action
(`corpus: vectors-agent-audit-record`) once your project emits records.
