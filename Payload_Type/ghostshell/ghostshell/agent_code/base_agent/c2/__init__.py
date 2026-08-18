"""ghostshell C2 adapter interface (PUBLIC — Surface 3 of api-design.md).

A C2 profile is two-sided: the Mythic-side profile package (Mythic's built-in
http / dynamic_http profiles) defines the parameters, and the agent-side
adapter (this file + http.py / dynamic_http.py) implements the transport.
Students add a transport by subclassing C2Adapter.
"""


class C2Error(Exception):
    """Raised when the transport fails after exhausting retries. The base
    agent's dispatch loop catches this, sleeps one beacon interval, and
    retries -- the agent never crashes on a transient transport failure."""
    pass


class C2Adapter:
    """Agent-side C2 transport. One subclass per profile (http, dynamic_http).

    The base agent calls make_request() for every Mythic round-trip; the
    adapter owns the HTTP (or tcp/smb/etc) mechanics + retry/backoff.
    """

    def __init__(self, params):
        """params = the C2 profile's build parameters, injected by the
        translator. Includes callback_host, callback_port, post_uri, get_uri,
        query_path_name, headers, callback_interval, callback_jitter, and the
        translator-injected AESPSK (the encryption key)."""
        raise NotImplementedError

    def make_request(self, data_b64, method="GET"):
        """Send the base64-encoded message envelope to Mythic and return the
        base64-decoded response BYTES. method is 'GET' (tasking) or 'POST'
        (responses/checkin). MUST retry transient HTTP errors with backoff
        and raise C2Error only after exhausting retries."""
        raise NotImplementedError


# Lazy-accessor so `from c2 import HTTPC2Adapter` works without importing urllib
# at package-import time (keeps the interface import cheap for tests).
def __getattr__(name):
    if name == "HTTPC2Adapter":
        from .http import HTTPC2Adapter
        return HTTPC2Adapter
    if name == "DynamicHTTPC2Adapter":
        from .dynamic_http import DynamicHTTPC2Adapter
        return DynamicHTTPC2Adapter
    raise AttributeError(name)


__all__ = ["C2Adapter", "C2Error", "HTTPC2Adapter", "DynamicHTTPC2Adapter"]
