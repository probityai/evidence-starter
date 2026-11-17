"""The nightly install smoke test keeps one issue that is open exactly while it fails."""

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/install-smoke.yml"


def report_job() -> dict:
    jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]
    assert set(jobs) == {"install", "report"}, sorted(jobs)
    return jobs["report"]


def test_report_runs_after_a_pass_as_well_as_a_failure() -> None:
    cond = report_job()["if"]
    # failure() alone would never run after a green night, so the issue would stay open.
    assert "always()" in cond and "failure()" not in cond
    assert "success" in cond and "failure" in cond and "schedule" in cond


def test_a_green_night_closes_the_issue_and_a_red_one_opens_or_updates_it() -> None:
    script = report_job()["steps"][0]["run"]
    assert "gh issue close" in script
    assert "gh issue comment" in script and "gh issue create" in script
    # head under pipefail can fail the step when it closes the pipe early.
    assert "| head" not in script
