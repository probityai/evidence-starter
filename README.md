# evidence-starter

[![Verified by Probity](https://raw.githubusercontent.com/probityai/agent-evidence/main/assets/verified-by-probity.svg)](https://github.com/probityai/probity)
Verified by Probity (github.com/probityai/probity): [latest passing run](https://github.com/probityai/evidence-starter/actions/workflows/ci.yml)

A template project that records a signed agent action and checks a claim about it offline, with the packages pinned and the conformance Action already in CI.

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
recorded /work/result.txt in run
decision: supported (assertion_matches_authenticated_history)
```

[`demo.py`](src/evidence_starter/demo.py) has two halves. The producer uses [agent-evidence-observer](https://github.com/probityai/probity/tree/main/packages/observer): a broker writes one file, signs its history and seals a packet into `run/`. The consumer uses [probity-verify](https://github.com/probityai/probity-verify): it reads only those retained bytes and a policy pinning the two public keys, and decides whether a report about the write holds. Run it with `--claim false` and the same evidence gives `contradicted`; change a byte of `run/history.jsonl` and the verifier refuses with exit 2. `.venv/bin/python -m pytest` checks all three.

## What CI runs

| job | what it proves |
| --- | --- |
| `demo` | the pins install, the example prints `supported`, the tests pass, and the README stays one screen |
| `vectors` | builds the reference verifier pinned in [`tools/go.mod`](tools/go.mod) and replays the [agent-evidence-vectors](https://github.com/probityai/agent-evidence-vectors) corpus against it with the project's GitHub Action |

To test a verifier of your own, replace the `verifier:` line in [`ci.yml`](.github/workflows/ci.yml). Dependabot keeps the PyPI pins, the Go pin and the Action pin current.

## Status

Version 0.1.0. It pins `agent-evidence-observer==0.0.2`, `probity-verify==0.1.1` and the `v0.18.1` vectors release. Keys are generated per run on one host, so every record says `witnessScope: PEER`: it shows what this broker saw, not what an independent witness saw.

## Links

| page | read it for |
| --- | --- |
| [Observer docs](https://github.com/probityai/probity/blob/main/packages/observer/docs/README.md) | brokered writes, workloads and the witness ledger |
| [Brokered file write check](https://github.com/probityai/probity-verify/blob/main/docs/brokered-file-write.md) | every field of the report, case and policy this example writes |
| [Vectors CI guide](https://github.com/probityai/agent-evidence-vectors/blob/main/docs/guides/runner.md) | Action inputs, outputs and how to read the report |
| [Verifier contract](https://github.com/probityai/agent-evidence-vectors/blob/main/docs/reference/verifier-contract.md) | what your verifier must print for the corpus |

## License

Apache-2.0; see [LICENSE](LICENSE).
