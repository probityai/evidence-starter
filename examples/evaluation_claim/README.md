# Evaluation claim from an expectation table

`expectations.tsv` is the contract: one row per case with the outcome the run
must reach (`verified` or `falsified` for a proof tool, `pass` or `fail` for a
test suite). `observed.json` is what one run reached. `make_claim.py` turns the
two into a signed `evaluation-claim` record of
[agent-evidence-vectors](https://github.com/probityai/agent-evidence-vectors/tree/main/packaging/agent_evidence_vectors/claim_record):

```sh
.venv/bin/python examples/evaluation_claim/make_claim.py claim-out
```

```text
verdict pass: 4 of 4 cases reached their expectation
case set sha256:...
```

The core is six steps in `build()` and `sign()`: read the table, put each row's
expectation into the case set, compare the outcomes, emit the record, wrap it in
an in-toto Statement, sign it as a DSSE envelope. Because the expectation sits
inside the case set, the case set's digest binds it: a consumer that pins that
digest in its acceptance rule refuses a record built after one expectation was
flipped (`CASE_SET_NOT_ACCEPTED`), so a regression cannot be relabelled as the
expected result. A case with no outcome is recorded as not run, never dropped. The table header
must be `id`, `requirement`, `expect` and every expectation one of the four
above; an outcome for a case the table does not hold, or an outcome file with a
duplicate member, is refused rather than left out.

The record says how the run fared against the table. It does not re-run the
cases or say who observed the run; pin the signer's key and keep the case set
you accept. `tests/test_example_evaluation_claim.py` checks every refusal.
