import subprocess
from pathlib import Path

import pytest

from evidence_starter.demo import main, record, verify, write_claim


def test_true_report_is_supported(tmp_path: Path) -> None:
    assert main([str(tmp_path / "run")]) == 0


def test_false_report_is_contradicted(tmp_path: Path) -> None:
    run = tmp_path / "run"
    decision = verify(*write_claim(run, record(run), completion_recorded=False))
    assert decision["decision"] == "contradicted"


def test_tampered_history_is_refused(tmp_path: Path) -> None:
    run = tmp_path / "run"
    case, policy = write_claim(run, record(run), completion_recorded=True)
    history = run / "history.jsonl"
    history.write_bytes(history.read_bytes().replace(b"write-1", b"write-2"))
    with pytest.raises(subprocess.CalledProcessError) as refused:
        verify(case, policy)
    assert refused.value.returncode == 2  # invalid evidence: no verdict at all
