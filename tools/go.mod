// Pins the reference verifier the CI job replays the vectors corpus against.
// Dependabot bumps this pin and the Action pin in ci.yml; keep them on one release.
module evidence-starter/tools

go 1.24

tool github.com/probityai/agent-evidence-vectors/cmd/aee-verify

require github.com/probityai/agent-evidence-vectors v0.18.1 // indirect
