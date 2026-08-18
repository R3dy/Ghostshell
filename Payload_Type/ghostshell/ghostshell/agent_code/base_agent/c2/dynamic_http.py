"""ghostshell dynamic_http C2 adapter (PUBLIC — Surface 3).

A thin subclass of HTTPC2Adapter that rotates the request URI (and optionally
headers) across a configured list per beacon. Proves the C2 adapter interface
is real: a second transport that reuses the HTTP mechanics with mutable
parameters, not a parallel implementation (ADR-006 / api-design.md Surface 3).
"""

import random
from .http import HTTPC2Adapter


class DynamicHTTPC2Adapter(HTTPC2Adapter):
    """HTTP beaconing with rotating URIs/headers. The Mythic 'dynamic_http'
    profile supplies a list of URIs (and optionally header sets); each beacon
    picks the next (round-robin) or a random one."""

    def __init__(self, params):
        super().__init__(params)
        # uris may be a JSON list from the profile; tolerate a single string.
        uris = params.get("uris", [self.post_uri])
        if isinstance(uris, str):
            uris = [uris]
        self._post_uris = uris or [self.post_uri]
        self._idx = 0

    def _next_post_uri(self):
        # round-robin rotation -- deterministic, easy to verify in the demo
        uri = self._post_uris[self._idx % len(self._post_uris)]
        self._idx += 1
        return uri

    def make_request(self, data_b64, method="GET"):
        # Rotate the POST URI for POST requests; GET tasking keeps a stable URI
        # (Mythic's http profile serves tasking at one path).
        if method == "POST":
            self.post_uri = self._next_post_uri()
        return super().make_request(data_b64, method=method)
