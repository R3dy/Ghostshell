# Module interface reference

The contract a ghostshell command module builds against. This is the distilled version of `docs/02-planning/api-design.md` — a student reference.

## The agent-side command function (Surface 1)

```python
def <command_name>(self, task_id: str, **params) -> str:
    """<one-line help string>"""
```

- `self`: the `GhostshellAgent` instance (see the context API below).
- `task_id`: the Mythic task id. Use it to look up + stop-check your task in `self.taskings`.
- `**params`: the command's arguments, parsed by the Mythic-side `TaskArguments.parse_arguments()` and forwarded as keyword arguments.
- **Returns:** a string — the output the operator sees in the Mythic UI. The base agent wraps it in the response envelope.
- **Raises:** (nothing mandatory) — exceptions raised inside a command are caught by the base agent and returned to Mythic as error `user_output` with `completed=True`. You may `raise ValueError("bad arg")` to signal a clean error.

## The `self` context API (Surface 2)

These are the PUBLIC methods + attributes a command may call on `self`. Everything else on the agent is INTERNAL — don't reach past this list.

| Member | Signature | Returns | Failure behavior |
|--------|-----------|---------|------------------|
| `self.postMessageAndRetrieveResponse(data)` | `(data: dict) -> dict` | the server's full response dict | **Raises `C2Error`** if the transport fails after retry. The dispatch loop catches it + retries the beacon; the agent never crashes. |
| `self.taskings` | attribute (list[dict]) | list of task dicts | N/A. Each dict: `{"task_id", "command", "parameters", "result", "completed", "started", "error", "stopped"}`. |
| `self.sendTaskOutputUpdate(task_id, output)` | `(task_id: str, output: str) -> None` | None | **Best-effort, non-raising.** Logs + continues on failure. |
| `self.loaded_commands` | attribute (dict[str, callable]) | name -> function | N/A. Read-only. What `help` lists. |
| `self.load_command(name)` | `(name: str) -> bool` | True if loaded | Returns `False` (non-raising) on failure. Used by `load`. |
| `self.unload_command(name)` | `(name: str) -> bool` | True if unloaded | Returns `False` (non-raising) if not loaded or protected. Used by `unload`. |
| `self.c2` | attribute (`C2Adapter`) | the active adapter | N/A. The transport (rarely needed directly). |
| `self.crypto` | attribute (`CryptoHelper`) | the crypto helper | N/A. Encrypt/decrypt (rarely needed directly). |

**Error-semantics summary:** the two transport-touching members handle their own failures (raise vs. swallow, respectively). A command never needs to catch a transport error. A command raising its own exception becomes error `user_output` — no try/except needed for that.

## The C2 adapter interface (Surface 3)

If you want to add a transport (e.g. a `tcp` exercise), subclass `C2Adapter`:

```python
from c2 import C2Adapter, C2Error

class TCPC2Adapter(C2Adapter):
    def __init__(self, params):
        self.host = params["callback_host"]
        self.port = params["callback_port"]
        # ...

    def make_request(self, data_b64, method="GET"):
        # send data_b64 over tcp, return the base64-decoded response bytes
        # raise C2Error on transport failure
        ...
```

The base agent calls `self.c2.make_request(...)` for every Mythic round-trip. Your adapter owns the transport mechanics + retry. See `c2/http.py` for the reference implementation.

## The translator build-parameter schema (Surface 4)

The translator reads these when the operator clicks "Build" in the Mythic UI:

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `selected_commands` | list[str] | yes | `["load", "unload", "ps"]` | Which agent-side commands to compile in. `load`/`unload` always included. |
| `c2_profile` | `"http"` \| `"dynamic_http"` | yes | `"http"` | Which C2 adapter to compile in. |
| `c2_params` | dict | yes | profile-dependent | The C2 profile's params (callback_host, callback_port, interval, jitter, AESPSK, uris, headers...). |
| `python_version` | `"Python 3"` | yes | `"Python 3"` | MVP is Py3-only. |
| `AESPSK` | str | no | generated | The encryption key (Mythic generates it; the translator injects it into the agent + the C2 adapter reads it via `params["AESPSK"]`). |

## The Mythic-side command definition (Surface 5)

A `CommandBase` subclass + a `TaskArguments` subclass. See `_template_hello.py` for the copy-paste scaffold + line-by-line comments. Required fields: `cmd`, `help_cmd`, `description`, `argument_class`, `attributes` (with `supported_python_versions` + `supported_os`), `create_tasking`, `process_response`.

## What's NOT public (INTERNAL — don't depend on)

- The base agent's dispatch loop internals (`core.py`).
- The message-envelope builder (`_format_message` / `_format_response`).
- The crypto internals (`manual_crypto.py`'s AES core).
- The translator's concatenation mechanics (`builder.py`).

These can change between minor versions. Commands reaching past the documented `self` API break under refactor.
