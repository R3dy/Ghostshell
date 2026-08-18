# Changelog

All notable changes to ghostshell are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/). Versions follow [Semantic Versioning](https://semver.org/) (see ADR-004).

## [Unreleased]

## [v1.0.1] — 2026-08-18

### Fixed — live-Mythic S11 verification (10 defects found + fixed)
- **Missing `config.json`** at repo root — `mythic-cli install github` failed. Added the Mythic install config (copied from Medusa's format).
- **`ghostshell/mythic/__init__.py` had `__all__ = []`** — `from ghostshell.mythic import *` imported nothing, so the PayloadType + CommandBase subclasses were never loaded and `__subclasses__()` couldn't discover them. Fixed to import from `agent_functions`.
- **`CommandArgument` doesn't exist** in mythic_container v0.6.16 — it's `CommandParameter`. Fixed in `load.py` + `unload.py`.
- **`parameter_group_info` passed as dicts** — the SDK expects `ParameterGroupInfo` objects. Fixed in `load.py` + `unload.py`.
- **`agent_code_path` was wrong** — needed 3 levels up (agent_functions → mythic → ghostshell → agent_code), not 1. Fixed in `builder.py`.
- **PARAMS literal used `json.dumps()`** producing JSON booleans (`true`/`false`) — Python can't parse these. Fixed to use `json.loads(repr(json.dumps(config)))`.
- **`encrypted_exchange_check` misinterpreted as TLS verification** — the agent used default SSL which rejected Mythic's self-signed cert. Fixed to always use an unverified SSL context (Mythic uses self-signed certs; the AES+HMAC crypto provides message authenticity).
- **URL construction missing `/`** — `base_url + get_uri` produced `https://localhost:7443index`. Fixed to add a leading `/` to URIs.
- **Agent connected to nginx (7443) instead of the http C2 profile (80)** — the http C2 profile listens on port 80 (HTTP, use_ssl=false). Fixed callback_host/port guidance in docs.
- **Crypto UUID prefix not stripped before decrypt** — Mythic returns `UUID(36) + iv(16) + ct + hmac(32)`, but `crypto.decrypt()` expected `iv + ct + hmac`. The UUID was being treated as part of the IV, corrupting the HMAC check. Fixed by stripping the UUID before decryption (in `postMessageAndRetrieveResponse` + `getMessageAndRetrieveResponse`).
- **`await` on sync SDK methods** — `load_args_from_json_string` and `add_arg` are synchronous in mythic_container v0.6.16, but the code awaited them. Fixed by removing `await`.

### Verified — S11 live-Mythic end-to-end (2026-08-18)
- ghostshell installs into a live Mythic v3.4.0.61 via `mythic-cli install folder` (github install needs the new config.json).
- A payload built with `c2_profile=http` callbacks to a live Mythic server (1 callback, no re-checkin).
- `ps` returns a full process listing (PID PPID USER COMMAND).
- `unload ps` removes the command from the agent's registry.
- `unload load` is refused ("Cannot unload load/unload -- the agent must stay extensible.").
- `load ps` requires Mythic's UI file-staging flow (the agent code is correct; it needs the file_id Mythic provides through the load UI flow).

## [v1.0.0] — 2026-08-17

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
