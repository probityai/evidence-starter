"""Check a claim about one retained agent file write, offline.

The evidence is a signed history, a witness ledger, a witness head and a sealed
packet that an operator's runtime wrote and that this template keeps under
``retained/``, next to the two public keys a consumer pins. This module is the
consumer half: it copies those retained bytes into a run directory, writes a
report about the write and a policy of the consumer's own, and asks
agent-evidence-verify whether the report holds. The packages that produce such
records are not part of this template; the decision rests only on the bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from probity_observer.crypto import canonical

RETAINED = Path(__file__).resolve().parent / "retained"
EVIDENCE = ("packet.json", "history.jsonl", "ledger.jsonl", "head.json")
PINS = json.loads((RETAINED / "pins.json").read_text())
REQUEST_ID = PINS["request_id"]
TARGET = PINS["path"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retain(run: Path) -> dict[str, object]:
    """Copy the retained evidence into a new ``run`` directory and return what the consumer pins."""
    run.mkdir(parents=True, exist_ok=False)
    for name in EVIDENCE:
        shutil.copyfile(RETAINED / name, run / name)
    return dict(PINS)


def write_claim(run: Path, pins: dict[str, object], completion_recorded: bool) -> tuple[Path, Path]:
    """Write a typed report, the case that binds the evidence, and the consumer policy."""
    authority = pins["authority"]
    assert isinstance(authority, dict)
    report = {"schema_version": "brokered-file-write-report/v1", "interval_id": authority["intervalId"],
              "request_id": REQUEST_ID, "path": TARGET, "content_sha256": pins["content_sha256"],
              "completion_recorded": completion_recorded}
    (run / "report.json").write_bytes(canonical(report))
    files = {"report": "report.json", "packet": "packet.json", "history": "history.jsonl",
             "ledger": "ledger.jsonl", "head": "head.json"}
    artifacts = {role: {"path": name, "length": (run / name).stat().st_size, "sha256": _sha256(run / name)}
                 for role, name in files.items()}

    def pick(role: str) -> dict[str, str]:
        return {"artifact": role, "sha256": artifacts[role]["sha256"]}

    case = {"schema_version": "probity-case/v1", "case_id": "starter", "artifacts": artifacts}
    policy = {"schema_version": "probity-policy/v1",
              "witnesses": {"broker": {"observer_key": pins["observer_key"], "witness_key": pins["witness_key"],
                                       "witness_scope": "PEER",
                                       "record": {"state": "sealed", **{r: pick(r) for r in files if r != "report"}}}},
              "assessments": {"starter": {"claim_type": "brokered_file_write/v1", "report": pick("report"),
                                          "broker_witness": "broker",
                                          "context": {"interval_id": authority["intervalId"], "request_id": REQUEST_ID,
                                                      "path": TARGET, "authority_scope": authority["scope"],
                                                      "intended_content_sha256": pins["content_sha256"]},
                                          "retained_target": None}}}
    (run / "case.json").write_bytes(canonical(case))
    (run / "policy.json").write_bytes(canonical(policy))
    return run / "case.json", run / "policy.json"


def verify(case: Path, policy: Path) -> dict[str, object]:
    """Run the agent-evidence-verify CLI on the retained bytes and return its JSON decision."""
    result = subprocess.run([sys.executable, "-m", "agent_evidence_verify.cli", str(case), "--policy", str(policy), "--json"],
                            capture_output=True, check=True, text=True)
    decision: dict[str, object] = json.loads(result.stdout)
    return decision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="new directory for the evidence")
    parser.add_argument("--claim", choices=("true", "false"), default="true",
                        help="what the report says about the write (default: true)")
    args = parser.parse_args(argv)
    pins = retain(args.run)
    decision = verify(*write_claim(args.run, pins, args.claim == "true"))
    print(f"retained {TARGET} in {args.run}")
    print(f"decision: {decision['decision']} ({decision['reason']})")
    return 0 if decision["decision"] == "supported" else 1


if __name__ == "__main__":
    raise SystemExit(main())
