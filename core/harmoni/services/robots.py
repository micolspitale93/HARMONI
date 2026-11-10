"""Robot speakers: Furhat (Remote API) and NAO (through the HTTP NAO bridge)."""

import json
import urllib.error
import urllib.request

from harmoni.tree.registry import Param
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


@register_backend(
    "furhat",
    kind="actuator",
    actions=["DO"],
    doc="Furhat robot: says the text and attends the addressee",
    params={
        "robot_ip": Param(str, doc="IP of the robot (required unless mockup)"),
        "voice": Param(str, default="Matthew"),
        "attend": Param(str, default="random", choices=["random", "addressee", "none"],
                        doc="before speaking, look at a random detected user (nod if nobody is detected), "
                            "at the user whose Furhat id is the addressee, or do nothing"),
        "mockup": Param(bool, default=False, doc="log only, no robot"),
    },
    requirements=["furhat-remote-api"],
)
class FurhatBackend(ServiceBackend):
    """DO: the Furhat robot says the text.

    Params: robot_ip, voice (default Matthew), attend (random | addressee | none), mockup (log only)
    """

    def __init__(self, service_id, params=None, emit=None):
        super().__init__(service_id, params, emit)
        self.mockup = bool(self.params.get("mockup", False))
        self.attend = self.params.get("attend", "random")
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
        if self.attend == "random":
            if self.api.get_users():
                self.api.attend(user="RANDOM")
            else:
                self.api.gesture(name="Nod")  # nobody detected: acknowledge with a nod
        elif self.attend == "addressee" and len(addressees) == 1:
            self.api.attend(userid=addressees[0])
        self.api.say(text=text, blocking=True)
        return Result(True)


COLORS = {"red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255), "yellow": (255, 200, 0),
          "white": (255, 255, 255), "off": (0, 0, 0), "black": (0, 0, 0)}


def parse_color(data):
    """'red' | '#ff0000' | '{"color": "red"}' -> (name, (r, g, b))"""
    try:
        value = json.loads(data)
        value = value.get("color", "") if isinstance(value, dict) else value
    except (TypeError, ValueError):
        value = data
    value = str(value or "").strip().lower()
    if value in COLORS:
        return value, COLORS[value]
    if len(value) == 7 and value.startswith("#"):
        try:
            return value, tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            pass
    raise ValueError(f"unknown color '{data}' (use {', '.join(COLORS)} or #rrggbb)")


@register_backend(
    "furhat_led",
    kind="actuator",
    actions=["DO"],
    doc="Furhat LED: shows a color (e.g. red while processing, green while listening)",
    params={"robot_ip": Param(str, doc="IP of the robot (required unless mockup)"),
            "mockup": Param(bool, default=False, doc="log only, no robot")},
    requirements=["furhat-remote-api"],
)
class FurhatLedBackend(ServiceBackend):
    def __init__(self, service_id, params=None, emit=None):
        super().__init__(service_id, params, emit)
        self.mockup = bool(self.params.get("mockup", False))
        self.api = None

    def setup(self):
        if self.mockup or self.api is not None:
            return
        from furhat_remote_api import FurhatRemoteAPI

        self.api = FurhatRemoteAPI(self.params["robot_ip"])

    def do(self, data):
        name, (red, green, blue) = parse_color(data)
        if self.mockup:
            self.log.info("[mockup] Furhat LED: %s", name)
            return Result(True)
        if self.api is None:
            self.setup()
        self.api.set_led(red=red, green=green, blue=blue)
        return Result(True)


@register_backend(
    "nao_http",
    kind="actuator",
    actions=["DO"],
    doc="NAO robot through the NAO bridge (HTTP)",
    params={
        "bridge_url": Param(str, default="http://localhost:8765"),
        "timeout_s": Param(float, default=60.0),
        "mockup": Param(bool, default=False, doc="log only, no robot"),
    },
)
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


@register_backend(
    "nao_led_http",
    kind="actuator",
    actions=["DO"],
    doc="NAO chest LEDs, through the NAO bridge (HTTP)",
    params={
        "bridge_url": Param(str, default="http://localhost:8765"),
        "timeout_s": Param(float, default=10.0),
        "mockup": Param(bool, default=False, doc="log only, no robot"),
    },
)
class NaoLedHttpBackend(NaoHttpBackend):
    def do(self, data):
        name, rgb = parse_color(data)
        if self.mockup:
            self.log.info("[mockup] NAO LED: %s", name)
            return Result(True)
        return self._post("/led", {"color": name, "rgb": list(rgb)})
