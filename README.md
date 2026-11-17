# evidence-starter

A template project that checks a claim about a retained, signed agent action offline, with the packages pinned and the conformance Action already in CI.

It is for anyone wiring agent evidence into their own harness, evaluation pipeline or review process who wants a working base to change rather than a blank repository.

[Use this template](https://github.com/new?template_name=evidence-starter&template_owner=probityai), or clone it and install the pinned packages (Python 3.12 or later):

```sh
git clone https://github.com/probityai/evidence-starter && cd evidence-starter
python3 -m venv .venv && .venv/bin/pip install ".[test]"
```

## 30-second example

```sh
.venv/bin/evidence-starter run
```

```text
retained /work/result.txt in run
decision: supported (assertion_matches_authenticated_history)
```

[`demo.py`](src/evidence_starter/demo.py) is the consumer half of agent evidence. The template keeps one retained record under [`retained/`](src/evidence_starter/retained): a signed history, a witness ledger and head, a sealed packet, and the two public keys a consumer pins. The demo copies those bytes into `run/`, writes a report about the write and a policy of your own, and [agent-evidence-verify](https://github.com/probityai/probity/tree/main/packages/probity-verify) decides from the retained bytes alone whether the report holds. Run `.venv/bin/evidence-starter run-false --claim false` (the argument is the new directory it writes, so it must not exist yet) and the same evidence gives `contradicted`; change a byte of `run/history.jsonl` and the verifier refuses with exit 2. [agent-evidence-observer](https://github.com/probityai/probity/tree/main/packages/agent-evidence-observer) checks the same record offline. `.venv/bin/python -m pytest` checks all three.

## What CI runs

| job | what it proves |
| --- | --- |
| `demo` | the pins install, the example prints `supported`, the tests pass, and the README stays one screen |
| `lock` | `uv.lock` matches `pyproject.toml`, and the example and the tests pass on exactly the hash-locked versions it records |
| `vectors` | builds the reference verifier pinned in [`tools/go.mod`](tools/go.mod) and replays the [agent-evidence-vectors](https://github.com/probityai/agent-evidence-vectors) corpus against it with the project's GitHub Action |

To test a verifier of your own, replace the `verifier:` line in [`ci.yml`](.github/workflows/ci.yml). Dependabot keeps the PyPI pins, the Go pin and the Action pin current, together.

## Status

Version 0.1.0. The packages are pinned in [`pyproject.toml`](pyproject.toml), the verifier in [`tools/go.mod`](tools/go.mod) and the vectors Action in [`ci.yml`](.github/workflows/ci.yml). Dependabot moves all of them in one weekly pull request, and a test fails if the Action and the verifier name different releases. The retained record says `witnessScope: PEER`: the witness key ran on the same host as the broker, so it shows what that broker saw, not what an independent witness saw.

## Links

| page | read it for |
| --- | --- |
| [Observer docs](https://github.com/probityai/probity/blob/main/packages/agent-evidence-observer/docs/README.md) | retained broker packets, workloads and the witness ledger |
| [Brokered file write check](https://github.com/probityai/probity/blob/main/packages/probity-verify/docs/brokered-file-write.md) | every field of the report, case and policy this example writes |
| [Vectors CI guide](https://github.com/probityai/agent-evidence-vectors/blob/main/docs/guides/runner.md) | Action inputs, outputs and how to read the report |
| [Verifier contract](https://github.com/probityai/agent-evidence-vectors/blob/main/docs/reference/verifier-contract.md) | what your verifier must print for the corpus |
| [Evaluation claim example](examples/evaluation_claim/README.md) | turn an expectation table and a run into a signed claim record |
| [Time members example](examples/time_members/README.md) | the time fields a record carries, with asymmetric freshness bounds |

## License

Apache-2.0; see [LICENSE](LICENSE).
