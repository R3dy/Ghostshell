# Changelog

All notable changes to ghostshell are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/). Versions follow [Semantic Versioning](https://semver.org/) (see ADR-004).

## [Unreleased] — v1.0.0

### Added — initial MVP release
- `Payload_Type/ghostshell/` Mythic payload type: `Dockerfile` + `main.py` translator + `rabbitmq_config.json` + package registration.
- Base agent (`agent_code/base_agent/`):
  - `manual_crypto.py` — stdlib-only AES-256-CBC + HMAC-SHA256 (encrypt-then-MAC), adapted from Medusa.
  - `c2/__init__.py` — the `C2Adapter` interface + `C2Error`.
  - `c2/http.py` — `HTTPC2Adapter` (GET tasking, POST responses, encrypted).
  - `c2/dynamic_http.py` — `DynamicHTTPC2Adapter` (rotating URIs, subclasses http).
  - `core.py` — `GhostshellAgent`: checkin, tasking loop, load/unload registry, the Surface 2 context API.
- Three commands: `ps` (process listing), `load` (runtime module loading), `unload` (runtime module unloading, refuses load/unload).
- Mythic-side command definitions (`mythic/agent_functions/`) for all three commands + the translator `builder.py`.
- Command-module template (`agent_code/_template/` + `mythic/agent_functions/_template_hello.py`).
- Docs: README (30-min quickstart), install guide, build-a-payload walkthrough, writing-a-command (15-min student exercise), module-interface reference.
- Test suite (23 tests): crypto round-trip + tamper, C2 adapter round-trip against a mock HTTP server, dispatch loop, commands, translator stdlib-only contract, public-API surface.
- Uses Mythic's built-in `http` + `dynamic_http` C2 profiles (no custom profile packages).

### Tested against
- Mythic v3.3.x (see ADR-006). The `mythic_container` SDK version is pinned in the Dockerfile.

### Known limitations
- Educational payload — not for production use (textbook AES, no OPSEC hardening).
- Python 3 only (no 2.7 support).
- The agent-side is stdlib-only (no pip on the implant).
- `dynamic_http` rotates POST URIs round-robin (no header rotation in MVP).

[Unreleased]: https://github.com/R3dy/Ghostshell/compare/v0.0.0...HEAD
