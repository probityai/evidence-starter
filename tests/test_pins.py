"""The vectors Action and the verifier it replays must name one release.

A newer corpus replayed against an older verifier fails on the vectors the
newer release added, which reads as a verifier defect when it is a split pin.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODULE = "github.com/probityai/agent-evidence-vectors"


def action_release() -> str:
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    pins = re.findall(r"uses: probityai/agent-evidence-vectors@[0-9a-f]{40} # (v\S+)", ci)
    assert len(pins) == 1, f"expected one vectors Action pin in ci.yml, found {pins}"
    return pins[0]


def verifier_release() -> str:
    gomod = (ROOT / "tools/go.mod").read_text()
    pins = re.findall(rf"^require {re.escape(MODULE)} (v\S+)", gomod, re.MULTILINE)
    assert len(pins) == 1, f"expected one {MODULE} requirement in tools/go.mod, found {pins}"
    return pins[0]


def test_action_and_verifier_name_one_release() -> None:
    assert action_release() == verifier_release()


def test_go_sum_holds_only_the_pinned_release() -> None:
    lines = (ROOT / "tools/go.sum").read_text().split()
    versions = {word.removesuffix("/go.mod") for word in lines if word.startswith("v")}
    assert versions == {verifier_release()}


def test_dependabot_moves_both_pins_together() -> None:
    config = yaml.safe_load((ROOT / ".github/dependabot.yml").read_text())
    entries = {entry["package-ecosystem"]: entry for entry in config["updates"]}
    action, verifier = entries["github-actions"], entries["gomod"]
    assert action["multi-ecosystem-group"] == verifier["multi-ecosystem-group"]
    assert verifier["multi-ecosystem-group"] in config["multi-ecosystem-groups"]
    # The verifier is an indirect requirement; Dependabot skips those by default.
    assert {"dependency-type": "all"} in verifier["allow"]
