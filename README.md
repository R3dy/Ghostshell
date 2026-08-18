# ghostshell

A minimal, modular **MythicC2 Python payload** for teaching offensive-security tradecraft. Three built-in commands (`load`, `unload`, `ps`), two C2 profiles (`http`, `dynamic_http`), and a single-file-per-command extension model so a student can add a working command module in one class session.

> **Educational payload — not for production use.** ghostshell is a teaching instrument for a hands-on C2 tradecraft course. The crypto is a textbook AES (not constant-time), the agent is deliberately stripped-down, and there is no OPSEC hardening. Do not use on engagements. Use it to learn how a Mythic agent is structured, how commands load/unload at runtime, and how to extend one.

---

## Quick start (instructor) — 30 minutes to first callback

1. **Start a Mythic server** (v3.3.x recommended — see `docs/install.md` for the AWS AMI path or the local Docker path).
2. **Install the ghostshell payload type** from the Mythic server:
   ```bash
   sudo ./mythic-cli install github https://github.com/R3dy/Ghostshell
   ```
3. **Install the built-in C2 profiles** (Mythic ships `http` + `dynamic_http`; verify they're installed in the Mythic UI under "C2 Profiles").
4. **Create a payload** from the Mythic UI: New Payload -> select `ghostshell` -> select the `http` C2 profile -> set `callback_host` to your Mythic server URL -> Build.
5. **Download `payload.py`**, copy it to a lab VM with Python 3, and run:
   ```bash
   python3 payload.py
   ```
6. **Watch the callback appear** in the Mythic UI's "Callbacks" view.
7. **Task `ps`** -> see a process listing.
8. **Task `unload ps`** -> `ps` vanishes from `help`; tasking `ps` now fails.
9. **Task `load ps`** -> `ps` is back in `help` and taskable.

See `docs/build-a-payload.md` for the screenshot walkthrough + `docs/writing-a-command.md` for the 15-minute "write your first command module" exercise (the student centerpiece).

---

## Repo map

```
Payload_Type/ghostshell/        The Mythic payload type package
  Dockerfile                    Builds the translator container
  main.py                       Translator entry point (starts the mythic_container service)
  rabbitmq_config.json          Wires the translator to Mythic's message bus
  ghostshell/
    agent_code/                 THE AGENT (what students read + modify)
      base_agent/
        manual_crypto.py        Stdlib-only AES-256-CBC + HMAC-SHA256 (the C2 crypto)
        core.py                 The GhostshellAgent: checkin, tasking loop, load/unload registry
        c2/
          __init__.py           The C2Adapter interface (Surface 3)
          http.py               HTTPC2Adapter (GET tasking, POST responses)
          dynamic_http.py       DynamicHTTPC2Adapter (rotating URIs, subclasses http)
      ps.py                     The `ps` command (the example students read first)
      load.py                   The `load` command (runtime module loading -- the teaching centerpiece)
      unload.py                 The `unload` command
      _template/                Copy-paste scaffold for a new command
    mythic/
      agent_functions/          Mythic-side command definitions (CommandBase subclasses)
        builder.py              The translator: reads + concatenates + injects params -> payload.py
        ps.py, load.py, unload.py   Operator-facing command contracts
C2_Profiles/                    Empty -- ghostshell uses Mythic's built-in http + dynamic_http
docs/                           Student + instructor docs
tests/                          The test suite (python3 tests/test_ghostshell.py)
```

---

## What makes ghostshell different

Production Mythic agents (Medusa, Apollo, Athena, Poseidon) optimize for capability. ghostshell optimizes for **legibility and modifiability**:

- **3 commands, not 40.** The whole agent + commands is 927 lines — readable in one sitting.
- **One file per command.** A student opens `agent_code/ps.py`, reads it, modifies it, rebuilds, and sees their change live.
- **Top-level defs, not class-body methods.** Commands are plain Python functions (`def ps(self, task_id, **params) -> str`) — the style a student already writes. No 4-space-indent concatenation tricks.
- **Real Mythic.** It installs via `mythic-cli install github`, builds from the UI, and beacons the real Mythic server. The tasking, the UI, the callbacks, the load/unload flow are all production tooling.

---

## The command-module interface (the student contract)

A command is **one agent-side file** + **one Mythic-side file**:

```python
# agent_code/<your_command>.py  (the tradecraft)
def your_command(self, task_id, **params):
    """One-line help string."""
    if [t for t in self.taskings if t["task_id"] == task_id][0]["stopped"]:
        return "Job stopped."
    # your logic here; `self` is the GhostshellAgent (see docs/module-interface.md)
    return "output for mythic"
```

```python
# mythic/agent_functions/<your_command>.py  (the operator-facing contract)
# Copy _template_hello.py and rename. See docs/writing-a-command.md.
```

See `docs/module-interface.md` for the full `self` context API (`postMessageAndRetrieveResponse`, `sendTaskOutputUpdate`, `loaded_commands`, `load_command`, `unload_command`, `c2`, `crypto`).

---

## Tests

```bash
cd ghostshell
python3 tests/test_ghostshell.py
```

23 tests cover: crypto round-trip + tamper, C2 adapter round-trip against a mock HTTP server, the dispatch loop, the three commands, the translator's stdlib-only contract, and the public-API surface (guards semver).

---

## Mythic version

Tested against Mythic **v3.3.x** (see ADR-006). The `mythic_container` SDK version is pinned in the `Dockerfile`. If you're on a different Mythic version, see `docs/install.md` for the upgrade path.

---

## License & disclaimer

MIT licensed. **Educational payload — not for production use.** See the disclaimer at the top of this README.

## Acknowledgements

The Mythic HTTP C2 protocol + the manual AES crypto are adapted from the [Medusa](https://github.com/MythicAgents/Medusa) agent by @ajpc500. ghostshell strips Medusa to its teaching essence.
