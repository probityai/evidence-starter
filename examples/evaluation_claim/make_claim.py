"""Turn an expectation table and a run's outcomes into a signed evaluation-claim record.

The table is the contract: each case names the outcome the run must reach
(`verified` or `falsified` for a proof tool, `pass` or `fail` for a test suite).
The expectation goes into the case set, so the case set's digest binds it, and
a consumer that pins that digest refuses a record built from a table with one
expectation flipped. A case reaches `passed` when its outcome equals its
expectation and `failed` when it differs; a case with no outcome is recorded
as not run, never dropped. A table whose header, column count or expectations
fall outside this contract, an outcome for a case the table does not hold, and
an outcome file with a duplicate member are refused, never silently left out.

The record is the `evaluation-claim` predicate of agent-evidence-vectors,
wrapped in an in-toto Statement and signed as a DSSE envelope with Ed25519.

    python examples/evaluation_claim/make_claim.py OUT_DIR
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

from agent_evidence_vectors.claim_record.reader import CLAIM_TYPE, STATEMENT_TYPE, check_profile, digest_of, emit
from agent_evidence_vectors.claim_record.run import PACKAGED_CORPUS
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

HERE = Path(__file__).resolve().parent
PAYLOAD_TYPE = "application/vnd.in-toto+json"
HEADER = ["id", "requirement", "expect"]
EXPECTATIONS = frozenset({"verified", "falsified", "pass", "fail"})


def pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE pre-authentication encoding (DSSE v1)."""
    kind = payload_type.encode()
    return b"DSSEv1 %d %s %d %s" % (len(kind), kind, len(payload), payload)


def sha256_ref(name: str, path: Path) -> dict[str, str]:
    return {"name": name, "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}


def read_table(table: Path) -> list[list[str]]:
    """Read the expectation table, refusing anything outside its contract."""
    header, *lines = table.read_text().splitlines()
    if header.split("\t") != HEADER:
        raise ValueError(f"{table.name}: header must be {'<TAB>'.join(HEADER)}")
    rows = [line.split("\t") for line in lines if line]
    for row in rows:
        if len(row) != len(HEADER) or row[2] not in EXPECTATIONS:
            raise ValueError(f"{table.name}: row {row!r} needs three columns and an expectation in {sorted(EXPECTATIONS)}")
    return rows


def read_outcomes(observed: Path, ids: list[str]) -> dict[str, str]:
    """Read a run's outcomes; a duplicate member or a case the table does not hold is refused."""
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        if len({key for key, _ in pairs}) != len(pairs):
            raise ValueError(f"{observed.name}: duplicate member")
        return dict(pairs)
    outcome = json.loads(observed.read_text(), object_pairs_hook=unique)
    if not isinstance(outcome, dict) or not all(isinstance(v, str) for v in outcome.values()):
        raise ValueError(f"{observed.name}: must map each case id to an outcome string")
    unknown = sorted(set(outcome) - set(ids))
    if unknown:
        raise ValueError(f"{observed.name}: outcomes for cases the table does not hold: {unknown}")
    return outcome


def build(table: Path, observed: Path, *, implementation: Path, verifier: Path) -> tuple[dict, dict]:
    """Return the case set and the unsigned record."""
    rows = read_table(table)
    case_set = {"schema": "aev-claim-case-set/v1", "name": table.stem, "revision": "1",
                "cases": [{"id": i, "requirement": r, "expect": e} for i, r, e in rows]}
    outcome = read_outcomes(observed, [i for i, _, _ in rows])
    results = {"passed": [i for i, _, e in rows if outcome.get(i) == e],
               "failed": [i for i, _, e in rows if i in outcome and outcome[i] != e]}
    profile = check_profile(json.loads((PACKAGED_CORPUS / "profiles/conformance.json").read_text()))
    record = emit(case_set=case_set, results=results,
                  profile={"id": profile["id"], "digest": digest_of(profile)},
                  implementation=sha256_ref(implementation.name, implementation),
                  verifier=sha256_ref(verifier.name, verifier),
                  observation_vantage="artifact", observer="evidence-starter example")
    return case_set, record


def sign(record: dict, subject: dict[str, str], key: Ed25519PrivateKey) -> dict:
    """Wrap the record in an in-toto Statement and sign it as a DSSE envelope."""
    statement = {"_type": STATEMENT_TYPE, "predicateType": CLAIM_TYPE, "predicate": record,
                 "subject": [{"name": subject["name"], "digest": {"sha256": subject["digest"][7:]}}]}
    payload = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
    signature = key.sign(pae(PAYLOAD_TYPE, payload))
    return {"payloadType": PAYLOAD_TYPE, "payload": base64.b64encode(payload).decode(),
            "signatures": [{"keyid": "", "sig": base64.b64encode(signature).decode()}]}


def open_envelope(envelope: dict, public: Ed25519PublicKey) -> dict:
    """Check the one signature under the pinned key and return the Statement."""
    payload = base64.b64decode(envelope["payload"], validate=True)
    [signature] = envelope["signatures"]
    public.verify(base64.b64decode(signature["sig"], validate=True), pae(envelope["payloadType"], payload))
    return json.loads(payload)


def main(argv: list[str]) -> int:
    out = Path(argv[1])
    out.mkdir()
    case_set, record = build(HERE / "expectations.tsv", HERE / "observed.json",
                             implementation=HERE / "model.spthy", verifier=HERE / "make_claim.py")
    key = Ed25519PrivateKey.generate()
    envelope = sign(record, record["coordinates"]["bytes"]["implementation"], key)
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    (out / "case-set.json").write_text(json.dumps(case_set, indent=2) + "\n")
    (out / "claim.dsse.json").write_text(json.dumps(envelope, indent=2) + "\n")
    (out / "signer.pub.pem").write_bytes(public)
    print(f"verdict {record['verdict']}: {len(record['coordinates']['population']['passed'])} of "
          f"{record['coordinates']['population']['coverage_denominator']} cases reached their expectation")
    print(f"case set {digest_of(case_set)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
