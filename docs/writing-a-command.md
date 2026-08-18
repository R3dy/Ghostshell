# Write a command module in 15 minutes (student walkthrough)

This is the student centerpiece. By the end you'll have a new `hello` command that runs against a live Mythic callback.

## The two halves of a command

Every ghostshell command is **two files**:

1. **Agent-side** (`agent_code/<name>.py`): the function that runs on the implant. This is where the tradecraft lives. It's a top-level `def <name>(self, task_id, **params) -> str`.
2. **Mythic-side** (`mythic/agent_functions/<name>.py`): the operator-facing contract. A `CommandBase` subclass that tells Mythic how to render the UI tasking form + route the response. It's boilerplate — you copy the template.

The agent-side function is the star. The Mythic-side file is plumbing you copy once.

## Step 1: copy the template

```bash
cd Payload_Type/ghostshell/ghostshell
cp agent_code/_template/hello.py agent_code/hello.py       # already a working example
cp mythic/agent_functions/_template_hello.py mythic/agent_functions/hello.py
```

(The template ships as a working `hello` command — you can rebuild + run it as-is to see the flow, then modify it.)

## Step 2: read the agent-side function

Open `agent_code/hello.py`. It's ~15 lines:

```python
def hello(self, task_id, **params):
    """<one-line help string -- shows up in the Mythic UI>"""
    if [t for t in self.taskings if t["task_id"] == task_id][0]["stopped"]:
        return "Job stopped."
    return "hello from ghostshell"
```

Three things to notice:
- `self` is the **GhostshellAgent** instance — it gives you the context API (`self.postMessageAndRetrieveResponse`, `self.taskings`, `self.sendTaskOutputUpdate`, etc.). See `module-interface.md` for the full list.
- `task_id` is the Mythic task id — use it to check the stop flag (the `if [...]` line) in any long-running command.
- The function **returns a string** — that's what the operator sees in the Mythic UI. The base agent wraps it in the Mythic response envelope.

## Step 3: modify it

Change the return value. Add a parameter. Run a shell command. For example, a `whoami` command:

```python
import getpass
def whoami(self, task_id, **params):
    """Print the current username."""
    return getpass.getuser()
```

Save it as `agent_code/whoami.py`.

## Step 4: write the Mythic-side file

Open `mythic/agent_functions/hello.py` (the copy you made). It's a `CommandBase` subclass. For a no-argument command like `whoami`, you only need to change:
- `cmd = "hello"` -> `cmd = "whoami"`
- `help_cmd`, `description`, the class names (`HelloArguments` -> `WhoamiArguments`, `HelloCommand` -> `WhoamiCommand`).

The required fields: `cmd`, `help_cmd`, `description`, `argument_class`, `attributes` (with `supported_python_versions` + `supported_os`), `create_tasking`, `process_response`. See the template for the full shape + line-by-line comments.

## Step 5: rebuild the payload + run

1. Rebuild ghostshell in Mythic: `sudo ./mythic-cli rebuild ghostshell` (or restart the container: `sudo ./mythic-cli restart ghostshell`).
2. In the Mythic UI, create a new payload — this time include `whoami` in the selected commands (or load it at runtime with `load whoami`).
3. Run the payload, get a callback, task `whoami` — you see the username.

## Step 6 (advanced): load it at runtime

Instead of rebuilding, use `load`:
1. Build a payload WITHOUT `whoami` (just load/unload/ps). Run it, get a callback.
2. In the Mythic UI, task `load whoami`. Mythic stages the `whoami.py` agent code as a file; the agent fetches it, `exec`s it into its namespace, and registers it.
3. Task `whoami` — it works, even though it wasn't compiled into the original payload.

This is the dynamic-loading pattern: the agent starts minimal and grows at runtime. It's the same pattern Medusa uses; ghostshell keeps it readable so you can follow every step.

## The module interface (reference)

For the full list of what `self` exposes inside a command, see `module-interface.md`. The short version:

| Member | What it does |
|--------|-------------|
| `self.taskings` | list of task dicts; check `[...]["stopped"]` for your task_id |
| `self.postMessageAndRetrieveResponse(data)` | send a Mythic action envelope, get the response |
| `self.sendTaskOutputUpdate(task_id, output)` | stream mid-execution output |
| `self.loaded_commands` | the currently loaded command registry (read-only) |
| `self.c2` / `self.crypto` | the transport + crypto helpers (rarely needed directly) |

## Common mistakes

- **Forgetting the stop-check** in a long-running command — the operator can't stop it without killing the agent.
- **Importing a non-stdlib module** (`import requests`) — the built payload runs with no pip; it'll `ImportError` on the implant. Use stdlib only.
- **Top-level executable code** in the command file — only `def`/`import`/constants at the top level (the translator concatenates files; top-level code runs at build).
- **Not returning a string** — the base agent wraps the return value as `user_output`; return something the operator can read.

That's it. You wrote a Mythic command module. Open `agent_code/ps.py` next to see a real one.
