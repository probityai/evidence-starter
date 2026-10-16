"""Record one brokered file write, then check a claim about it offline.

The producer half uses agent-evidence-observer: a broker performs the write,
signs a history and seals a packet. The consumer half uses probity-verify: it
reads only the retained bytes and a policy the consumer wrote, and decides
whether a report about the write holds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from probity_observer.broker import Broker
from probity_observer.crypto import SigningKey, canonical
from probity_observer.ledger import LedgerWitness

REQUEST_ID = "write-1"
TARGET = "/work/result.txt"
CONTENT = b"hello from the agent\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(run: Path) -> dict[str, object]:
    """Run one write through the broker and keep the signed evidence in ``run``."""
    run.mkdir(parents=True, exist_ok=False)
    (run / "work").mkdir()
    observer_key, witness_key = SigningKey.generate(), SigningKey.generate()
    authority = {"intervalId": "starter-run", "scope": "/work", "operation": "write-file"}
    witness = LedgerWitness(run / "ledger.jsonl", witness_key, observer_key.public_hex)
    broker = Broker(run / "work", run / "history.jsonl", authority, observer_key, witness)
    broker.begin()
    broker.write(REQUEST_ID, TARGET, CONTENT)
    (run / "packet.json").write_bytes(canonical(broker.seal()))
    (run / "head.json").write_bytes(canonical(witness.signed_head()))
    # What the consumer pins out of band: the two public keys and the request.
    return {"observer_key": observer_key.public_hex, "witness_key": witness_key.public_hex,
            "authority": authority, "content_sha256": hashlib.sha256(CONTENT).hexdigest()}


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
    """Run the probity-verify CLI on the retained bytes and return its JSON decision."""
    result = subprocess.run([sys.executable, "-m", "probity_verify.cli", str(case), "--policy", str(policy), "--json"],
                            capture_output=True, check=True, text=True)
    decision: dict[str, object] = json.loads(result.stdout)
    return decision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="new directory for the evidence")
    parser.add_argument("--claim", choices=("true", "false"), default="true",
                        help="what the report says about the write (default: true)")
    args = parser.parse_args(argv)
    pins = record(args.run)
    decision = verify(*write_claim(args.run, pins, args.claim == "true"))
    print(f"recorded {TARGET} in {args.run}")
    print(f"decision: {decision['decision']} ({decision['reason']})")
    return 0 if decision["decision"] == "supported" else 1


if __name__ == "__main__":
    raise SystemExit(main())
