// Pins the reference verifier the CI job replays the vectors corpus against.
// The Action pin in ci.yml must name the same release: a newer corpus replayed
// against an older verifier fails on the vectors the newer release added.
// .github/dependabot.yml moves both pins in one pull request, and
// tests/test_pins.py fails when they differ.
module evidence-starter/tools

go 1.24

tool github.com/probityai/agent-evidence-vectors/cmd/aee-verify

require github.com/probityai/agent-evidence-vectors v0.29.3 // indirect
