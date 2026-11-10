"""Robot speakers: Furhat (Remote API) and NAO (through the HTTP NAO bridge)."""

import json
import urllib.error
import urllib.request

from harmoni.services.base import Result, ServiceBackend, register_backend


def parse_speech_request(data):
    """``{"input": text, "addressee": "Sarah"}`` -> ``("text", ["Sarah"])``.

    A plain string is the text to say. Missing, empty or "null" addressee -> ``[]``.
    """
    try:
        payload = json.loads(data)
    except (TypeError, ValueError):
        payload = {"input": data}
    if not isinstance(payload, dict):
        payload = {"input": str(payload)}
    names = [a.strip() for a in str(payload.get("addressee") or "").split(",")]
    return str(payload.get("input", "")), [a for a in names if a and a.lower() != "null"]


@register_backend("furhat")
class FurhatBackend(ServiceBackend):
    """DO: the Furhat robot says the text and attends the addressee.

    Params: robot_ip, voice (default Matthew), mockup (log only, no robot)
    """

    def __init__(self, service_id, params=None, emit=None):
        super().__init__(service_id, params, emit)
        self.mockup = bool(self.params.get("mockup", False))
        self.api = None

    def setup(self):
        if self.mockup or self.api is not None:
            return
        from furhat_remote_api import FurhatRemoteAPI

        self.api = FurhatRemoteAPI(self.params["robot_ip"])
        self.api.set_voice(name=self.params.get("voice", "Matthew"))

    def do(self, data):
        text, addressees = parse_speech_request(data)
        if self.mockup:
            self.log.info("[mockup] Furhat says: %s (to %s)", text, addressees or "everyone")
            return Result(True)
        if self.api is None:
            self.setup()
        self.api.say(text=text, blocking=True)
        if len(addressees) == 1:
            self.api.attend(userid=addressees[0])
        return Result(True)


@register_backend("nao_http")
class NaoHttpBackend(ServiceBackend):
    """DO: the NAO robot says the text, through the NAO bridge (ros2/nao_bridge).

    The NAOqi SDK only supports python 2.7: the bridge is a tiny python 2 HTTP server, so no
    ROS kinetic container is needed. Params: bridge_url (default http://localhost:8765),
    timeout_s (default 60), mockup (log only)
    """

    def __init__(self, service_id, params=None, emit=None):
        super().__init__(service_id, params, emit)
        self.url = str(self.params.get("bridge_url", "http://localhost:8765")).rstrip("/")
        self.timeout_s = float(self.params.get("timeout_s", 60))
        self.mockup = bool(self.params.get("mockup", False))

    def _post(self, path, payload):
        request = urllib.request.Request(self.url + path, data=json.dumps(payload).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                answer = json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            return Result(False, f"NAO bridge error {e.code}: {e.read().decode('utf-8', 'replace')}")
        except (urllib.error.URLError, OSError) as e:
            return Result(False, f"NAO bridge unreachable at {self.url}: {e}")
        return Result(bool(answer.get("ok")), answer.get("error", ""))

    def do(self, data):
        text, addressees = parse_speech_request(data)
        if self.mockup:
            self.log.info("[mockup] NAO says: %s (to %s)", text, addressees or "everyone")
            return Result(True)
        return self._post("/say", {"text": text, "addressee": addressees[0] if len(addressees) == 1 else ""})
