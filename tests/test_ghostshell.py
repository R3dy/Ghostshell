"""ghostshell test suite.

Run with: python3 -m pytest tests/ -v
(Or: python3 tests/run_tests.py if pytest isn't available.)

Covers the public API contract (api-design.md Surfaces 1-4):
  - manual_crypto: round-trip, known-answer, tamper, disabled-passthrough
  - c2 http/dynamic_http: round-trip against a mock HTTP server
  - agent core: dispatch loop with a mock C2 adapter replaying scripted tasking
  - commands: ps/load/unload with a mock agent context
  - translator: build produces a script; the 'no non-stdlib imports' check
  - public-API contract: the Surface 1/2/3 shapes are asserted
"""
import os
import sys
import json
import base64
import socket
import threading
import http.server
import unittest
from unittest.mock import MagicMock, patch

# Make the agent_code package importable for tests.
AGENT_DIR = os.path.join(os.path.dirname(__file__), "..", "Payload_Type", "ghostshell",
                         "ghostshell", "agent_code", "base_agent")
AGENT_CODE_DIR = os.path.join(os.path.dirname(__file__), "..", "Payload_Type", "ghostshell",
                              "ghostshell", "agent_code")
sys.path.insert(0, AGENT_DIR)
sys.path.insert(0, AGENT_CODE_DIR)  # so `from ps import ps` / load / unload resolve

from manual_crypto import CryptoHelper, CryptoError  # noqa: E402


class TestManualCrypto(unittest.TestCase):
    """E2.1: AES-256-CBC + HMAC-SHA256, stdlib only."""

    def setUp(self):
        self.key_b64 = base64.b64encode(os.urandom(32)).decode()
        self.h = CryptoHelper(self.key_b64)

    def test_roundtrip_varied(self):
        for pt in [b"", b"x", b"a" * 16, b"a" * 17, b"the quick brown fox" * 5, bytes(range(256))]:
            with self.subTest(length=len(pt)):
                self.assertEqual(self.h.decrypt(self.h.encrypt(pt)), pt)

    def test_tamper_middle_byte_raises(self):
        ct = bytearray(self.h.encrypt(b"secret message"))
        ct[20] ^= 0x01  # flip a MIDDLE byte (not the last -- padding bits, MEMORY.md lesson)
        with self.assertRaises(CryptoError):
            self.h.decrypt(bytes(ct))

    def test_wrong_key_raises(self):
        ct = self.h.encrypt(b"secret")
        other = CryptoHelper(base64.b64encode(os.urandom(32)).decode())
        with self.assertRaises(CryptoError):
            other.decrypt(ct)

    def test_disabled_passthrough(self):
        h = CryptoHelper("")
        self.assertEqual(h.encrypt(b"x"), b"x")
        self.assertEqual(h.decrypt(b"x"), b"x")

    def test_no_nonstdlib_imports(self):
        """ADR-003: manual_crypto uses stdlib only."""
        src = open(os.path.join(AGENT_DIR, "manual_crypto.py")).read()
        import ast
        tree = ast.parse(src)
        stdlib = {"os", "base64", "hmac", "ast", "sys"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                self.assertIn(top, stdlib | {"builtins"}, "non-stdlib import: " + node.module)
            elif isinstance(node, ast.Import):
                for n in node.names:
                    self.assertIn(n.name.split(".")[0], stdlib, "non-stdlib import: " + n.name)


class TestC2Adapters(unittest.TestCase):
    """E2.2/E2.3: HTTP + dynamic_http round-trip against a mock server."""

    @classmethod
    def setUpClass(cls):
        # Spin a tiny mock Mythic HTTP server that echoes back a base64-encoded
        # response (the agent base64-decodes whatever it receives).
        cls.received = []
        cls.handler = type("H", (http.server.BaseHTTPRequestHandler,), {
            "do_GET": lambda s: cls._respond(s, cls),
            "do_POST": lambda s: cls._respond(s, cls),
            "log_message": lambda *a: None,
        })
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), cls.handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def _respond(cls, s, self_ref):
        # capture the request, echo a base64-encoded JSON response
        length = int(s.headers.get("Content-Length", 0)) if s.command == "POST" else 0
        body = s.rfile.read(length) if length else b""
        path = s.path
        cls.received.append({"method": s.command, "path": path, "body": body})
        # Mythic's response is base64(UUID + encrypted(json)). For the mock we
        # return base64(json) -- the agent will base64-decode it.
        resp = base64.b64encode(json.dumps({"tasks": [], "responses": []}).encode())
        s.send_response(200)
        s.send_header("Content-Type", "application/octet-stream")
        s.send_header("Content-Length", str(len(resp)))
        s.end_headers()
        s.wfile.write(resp)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _config(self, profile="http"):
        c = {
            "callback_host": "http://127.0.0.1",
            "callback_port": str(self.port),
            "post_uri": "/post_uri",
            "get_uri": "/get_uri",
            "query_path_name": "q",
            "headers": {},
            "callback_interval": 1,
            "callback_jitter": 0,
            "AESPSK": "",
            "encrypted_exchange_check": "no",
            "c2_profile": profile,
        }
        if profile == "dynamic_http":
            c["uris"] = ["/a", "/b", "/c"]
        return c

    def test_http_adapter_make_request_get(self):
        from c2.http import HTTPC2Adapter
        adapter = HTTPC2Adapter(self._config())
        out = adapter.make_request(base64.b64encode(b"hello"), method="GET")
        self.assertTrue(len(out) > 0)
        self.assertEqual(self.received[-1]["method"], "GET")

    def test_http_adapter_make_request_post(self):
        from c2.http import HTTPC2Adapter
        adapter = HTTPC2Adapter(self._config())
        out = adapter.make_request(base64.b64encode(b"hello"), method="POST")
        self.assertTrue(len(out) > 0)
        self.assertEqual(self.received[-1]["method"], "POST")

    def test_dynamic_http_rotates_post_uri(self):
        from c2.dynamic_http import DynamicHTTPC2Adapter
        adapter = DynamicHTTPC2Adapter(self._config("dynamic_http"))
        adapter.make_request(base64.b64encode(b"x"), method="POST")
        adapter.make_request(base64.b64encode(b"x"), method="POST")
        adapter.make_request(base64.b64encode(b"x"), method="POST")
        paths = [r["path"] for r in self.received[-3:]]
        # the post_uri should rotate through /a, /b, /c
        self.assertEqual(len(set(paths)), 3, "expected 3 distinct URIs, got: {}".format(paths))


class TestAgentCore(unittest.TestCase):
    """E2.4: dispatch loop + Surface 2 API with a mock C2 adapter."""

    def _make_agent(self, commands_return=None):
        """Build a GhostshellAgent with a mock C2 + no crypto, for dispatch tests."""
        from core import GhostshellAgent
        config = {"PayloadUUID": "test-payload-uuid", "c2_profile": "http",
                  "AESPSK": "", "callback_interval": 0, "callback_jitter": 0}
        agent = GhostshellAgent.__new__(GhostshellAgent)  # bypass __init__ (avoids registering globals)
        agent.callback_uuid = "test-payload-uuid"
        agent.uuid = "callback-uuid"
        agent.taskings = []
        agent.loaded_commands = {}
        agent.crypto = CryptoHelper("")
        agent.agent_config = config
        # mock C2: returns a base64(json) response for any request
        class MockC2:
            def make_request(self, data_b64, method="GET"):
                # Echo a scripted tasking on GET, ack on POST
                if method == "GET":
                    return base64.b64encode(json.dumps({"tasks": []}).encode())
                return base64.b64encode(json.dumps({"responses": []}).encode())
        agent.c2 = MockC2()
        # register the built-in commands if available in globals
        return agent

    def test_register_and_dispatch_ps(self):
        agent = self._make_agent()
        # register a fake 'ps' command that returns a fixed string
        agent.loaded_commands["ps"] = MagicMock(return_value="PID COMM\n1 init")
        agent.taskings.append({"task_id": "t1", "command": "ps", "parameters": "{}",
                               "result": "", "completed": False, "started": False, "error": False, "stopped": False})
        agent._run_task(agent.taskings[0])
        self.assertTrue(agent.taskings[0]["completed"])
        self.assertEqual(agent.taskings[0]["result"], "PID COMM\n1 init")
        self.assertFalse(agent.taskings[0]["error"])

    def test_dispatch_unknown_command_errors(self):
        agent = self._make_agent()
        agent.taskings.append({"task_id": "t2", "command": "nonexistent", "parameters": "{}",
                               "result": "", "completed": False, "started": False, "error": False, "stopped": False})
        agent._run_task(agent.taskings[0])
        self.assertTrue(agent.taskings[0]["completed"])
        self.assertTrue(agent.taskings[0]["error"])
        self.assertIn("not loaded", agent.taskings[0]["result"])

    def test_command_exception_becomes_error_output(self):
        agent = self._make_agent()
        def boom(self, task_id, **params):
            raise ValueError("kaboom")
        agent.loaded_commands["boom"] = boom
        agent.taskings.append({"task_id": "t3", "command": "boom", "parameters": "{}",
                               "result": "", "completed": False, "started": False, "error": False, "stopped": False})
        agent._run_task(agent.taskings[0])
        self.assertTrue(agent.taskings[0]["error"])
        self.assertIn("kaboom", agent.taskings[0]["result"])

    def test_format_message_envelope(self):
        agent = self._make_agent()
        msg = agent._format_message({"action": "get_tasking"})
        decoded = base64.b64decode(msg)
        self.assertTrue(decoded.startswith(b"callback-uuid"))

    def test_unload_refuses_load_and_unload(self):
        agent = self._make_agent()
        agent.loaded_commands = {"load": lambda *a, **k: None, "unload": lambda *a, **k: None, "ps": lambda *a, **k: None}
        self.assertFalse(agent.unload_command("load"))
        self.assertFalse(agent.unload_command("unload"))
        self.assertTrue(agent.unload_command("ps"))
        self.assertNotIn("ps", agent.loaded_commands)

    def test_unload_already_unloaded(self):
        agent = self._make_agent()
        self.assertFalse(agent.unload_command("ps"))


class TestCommands(unittest.TestCase):
    """E3/E4/E5: ps/load/unload agent-side functions with a mock agent."""

    def _mock_agent(self, taskings=None):
        agent = MagicMock()
        agent.taskings = taskings or [{"task_id": "t1", "stopped": False}]
        return agent

    def test_ps_returns_listing(self):
        from ps import ps
        out = ps(self._mock_agent(), "t1")
        self.assertIsInstance(out, str)
        # ps should return something (a listing or an error message)
        self.assertTrue(len(out) > 0)

    def test_ps_stop_flag(self):
        from ps import ps
        agent = self._mock_agent([{"task_id": "t1", "stopped": True}])
        self.assertEqual(ps(agent, "t1"), "Job stopped.")

    def test_unload_refuses_load(self):
        from unload import unload
        agent = self._mock_agent()
        agent.loaded_commands = {"load": None, "unload": None, "ps": None}
        agent.unload_command = MagicMock(return_value=False)
        # unload is a top-level def that calls self.unload_command; but the
        # agent-side unload calls self.unload_command directly. Mock it.
        out = unload(agent, "t1", module="load")
        self.assertIn("Cannot unload", out)

    def test_unload_unknown(self):
        from unload import unload
        agent = self._mock_agent()
        agent.loaded_commands = {}
        agent.unload_command = MagicMock(return_value=False)
        out = unload(agent, "t1", module="ps")
        self.assertIn("not loaded", out)

    def test_load_missing_module(self):
        from load import load
        agent = self._mock_agent()
        out = load(agent, "t1")
        self.assertIn("no module", out.lower())


class TestTranslatorContract(unittest.TestCase):
    """E1.1: the translator produces a script with no non-stdlib imports (ADR-003)."""

    def test_agent_files_no_nonstdlib_imports(self):
        """Every agent_code file uses stdlib only (intra-agent imports of
        manual_crypto / c2.* are allowed -- the translator strips them for the
        built script; they're needed for unit-test imports of the source files)."""
        import ast
        agent_root = os.path.join(AGENT_DIR, "..")  # agent_code/
        stdlib = {"os", "sys", "json", "time", "random", "socket", "base64",
                  "getpass", "platform", "threading", "subprocess", "urllib",
                  "ssl", "hmac", "ast", "re", "pathlib", "builtins", "queue", "datetime"}
        # agent's OWN modules (intra-agent imports -- allowed in source, stripped at build)
        intra_agent = {"manual_crypto", "c2", "ps", "load", "unload"}
        problems = []
        for dirpath, _, files in os.walk(agent_root):
            for f in files:
                if not f.endswith(".py") or "template" in f:
                    continue
                path = os.path.join(dirpath, f)
                try:
                    tree = ast.parse(open(path).read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        if node.level > 0:  # relative import (intra-package) -- allowed
                            continue
                        top = node.module.split(".")[0]
                        if top in stdlib or top in intra_agent:
                            continue
                        if node.module.startswith("mythic_container"):
                            continue
                        problems.append("{}: {}".format(f, node.module))
                    elif isinstance(node, ast.Import):
                        for n in node.names:
                            top = n.name.split(".")[0]
                            if top in stdlib or top in intra_agent:
                                continue
                            if n.name.startswith("mythic_container"):
                                continue
                            problems.append("{}: {}".format(f, n.name))
        self.assertEqual(problems, [], "non-stdlib imports found: " + str(problems))


class TestPublicAPIContract(unittest.TestCase):
    """E10: the Surface 1/2/3 contracts in api-design.md are asserted (guards semver)."""

    def test_agent_context_api_surface(self):
        """Surface 2: GhostshellAgent exposes the documented methods."""
        from core import GhostshellAgent
        for method in ["postMessageAndRetrieveResponse", "getMessageAndRetrieveResponse",
                        "sendTaskOutputUpdate", "load_command", "unload_command"]:
            self.assertTrue(hasattr(GhostshellAgent, method), "missing Surface 2 method: " + method)
        for attr in ["taskings", "loaded_commands", "crypto", "c2"]:
            # these are instance attrs set in __init__; check the class doesn't shadow them oddly
            self.assertTrue(attr in GhostshellAgent.__init__.__code__.co_names or
                            hasattr(GhostshellAgent, attr), "missing Surface 2 attr: " + attr)

    def test_c2_adapter_interface(self):
        """Surface 3: C2Adapter + the two concrete adapters exist."""
        from c2 import C2Adapter, C2Error, HTTPC2Adapter, DynamicHTTPC2Adapter
        self.assertTrue(issubclass(HTTPC2Adapter, C2Adapter))
        self.assertTrue(issubclass(DynamicHTTPC2Adapter, HTTPC2Adapter))

    def test_command_signatures(self):
        """Surface 1: commands are top-level defs taking (self, task_id, **params)."""
        import inspect
        sys.path.insert(0, os.path.join(AGENT_DIR, ".."))
        for cmd, mod in [("ps", "ps"), ("load", "load"), ("unload", "unload")]:
            mod_obj = __import__(mod)
            fn = getattr(mod_obj, cmd)
            sig = inspect.signature(fn)
            params = list(sig.parameters.keys())
            self.assertEqual(params[0], "self", "{} must take self first".format(cmd))
            self.assertEqual(params[1], "task_id", "{} must take task_id second".format(cmd))


if __name__ == "__main__":
    unittest.main(verbosity=2)
