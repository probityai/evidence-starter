"""An expectation table to a signed evaluation-claim record: the example under examples/evaluation_claim."""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from agent_evidence_vectors.claim_record.reader import check_profile, digest_of, index_by_digest, verify
from agent_evidence_vectors.claim_record.run import PACKAGED_CORPUS
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


claim = _load("make_claim", EXAMPLES / "evaluation_claim/make_claim.py")
CLAIM_DIR = EXAMPLES / "evaluation_claim"


def _profiles() -> dict:
    profile = check_profile(json.loads((PACKAGED_CORPUS / "profiles/conformance.json").read_text()))
    return {digest_of(profile): profile}


def _rule(case_set: dict) -> dict:
    profile = next(iter(_profiles().values()))
    return {"schema": "aev-claim-acceptance-rule/v1", "id": "starter-example",
            "profile": {"id": profile["id"], "digest": digest_of(profile)},
            "case_sets": [digest_of(case_set)], "accept_vantage": ["artifact"]}


def _build(table: Path) -> tuple[dict, dict]:
    return claim.build(table, CLAIM_DIR / "observed.json",
                       implementation=CLAIM_DIR / "model.spthy", verifier=CLAIM_DIR / "make_claim.py")


def test_signed_claim_is_admitted_with_verdict_pass(tmp_path: Path) -> None:
    assert claim.main(["make_claim.py", str(tmp_path / "out")]) == 0
    case_set, record = _build(CLAIM_DIR / "expectations.tsv")
    key = Ed25519PrivateKey.generate()
    statement = claim.open_envelope(claim.sign(record, record["coordinates"]["bytes"]["implementation"], key),
                                    key.public_key())
    outcome = verify(statement, _rule(case_set), _profiles(), index_by_digest([case_set]))
    assert outcome["result"] == "ADMITTED" and outcome["verdict"] == "pass"
    assert record["coordinates"]["population"]["coverage_denominator"] == 4


def test_expectation_flipped_to_hide_a_regression_is_refused(tmp_path: Path) -> None:
    """The run regressed (the replay attack now verifies) and the producer flips the expectation to match."""
    pinned, _ = _build(CLAIM_DIR / "expectations.tsv")
    regressed = tmp_path / "observed.json"
    outcomes = json.loads((CLAIM_DIR / "observed.json").read_text())
    outcomes["token-replay-across-servers"] = "verified"
    regressed.write_text(json.dumps(outcomes))
    flipped = tmp_path / "expectations.tsv"
    flipped.write_text((CLAIM_DIR / "expectations.tsv").read_text().replace(
        "token-replay-across-servers\trequired\tfalsified", "token-replay-across-servers\trequired\tverified"))
    case_set, record = claim.build(flipped, regressed,
                                   implementation=CLAIM_DIR / "model.spthy", verifier=CLAIM_DIR / "make_claim.py")
    assert record["verdict"] == "pass"
    outcome = verify(record, _rule(pinned), _profiles(), index_by_digest([case_set]))
    assert outcome["result"] == "REFUSED"
    assert "CASE_SET_NOT_ACCEPTED" in json.dumps(outcome)
    honest, record = claim.build(CLAIM_DIR / "expectations.tsv", regressed,
                                 implementation=CLAIM_DIR / "model.spthy", verifier=CLAIM_DIR / "make_claim.py")
    assert record["verdict"] == "fail"
    assert verify(record, _rule(pinned), _profiles(), index_by_digest([honest]))["verdict"] == "fail"


def test_envelope_under_another_key_is_refused() -> None:
    _, record = _build(CLAIM_DIR / "expectations.tsv")
    envelope = claim.sign(record, record["coordinates"]["bytes"]["implementation"], Ed25519PrivateKey.generate())
    with pytest.raises(InvalidSignature):
        claim.open_envelope(envelope, Ed25519PrivateKey.generate().public_key())
    payload = json.loads(base64.b64decode(envelope["payload"]))
    assert payload["subject"][0]["digest"]["sha256"] == record["coordinates"]["bytes"]["implementation"]["digest"][7:]


def test_missing_outcome_is_not_run(tmp_path: Path) -> None:
    partial = tmp_path / "observed.json"
    outcomes = json.loads((CLAIM_DIR / "observed.json").read_text())
    del outcomes["refresh-token-rotates"]
    partial.write_text(json.dumps(outcomes))
    _, record = claim.build(CLAIM_DIR / "expectations.tsv", partial,
                            implementation=CLAIM_DIR / "model.spthy", verifier=CLAIM_DIR / "make_claim.py")
    assert record["coordinates"]["population"]["not_run"] == ["refresh-token-rotates"]
    assert record["verdict"] == "incomplete"


def _write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


@pytest.mark.parametrize("table, observed, message", [
    # An outcome for a case the table does not hold: renaming a failing case would leave the original not run
    # and hide the failure under a name nobody reads, so it is refused instead of dropped.
    (None, '{"auth-code-binds-client": "verified", "refresh-token-rotates": "verified", '
           '"token-replay-across-servers": "falsified", "consent-skipped-on-reauth": "falsified", '
           '"token-replay-across-servers-v2": "verified"}', "does not hold"),
    # Two readers keep different copies of a duplicate member.
    (None, '{"auth-code-binds-client": "falsified", "auth-code-binds-client": "verified"}', "duplicate member"),
    (None, '{"auth-code-binds-client": null}', "outcome string"),
    ("id\trequirement\texpect\nx\trequired\tverifed\n", '{"x": "verifed"}', "expectation in"),
    ("id\texpect\trequirement\nx\tverified\trequired\n", '{"x": "verified"}', "header must be"),
    ("id\trequirement\texpect\nx\trequired\tverified\textra\n", '{"x": "verified"}', "three columns"),
])
def test_table_and_outcome_contract_refusals(tmp_path: Path, table: str | None, observed: str, message: str) -> None:
    table_path = CLAIM_DIR / "expectations.tsv" if table is None else _write(tmp_path / "t.tsv", table)
    with pytest.raises(ValueError, match=message):
        claim.build(table_path, _write(tmp_path / "observed.json", observed),
                    implementation=CLAIM_DIR / "model.spthy", verifier=CLAIM_DIR / "make_claim.py")
