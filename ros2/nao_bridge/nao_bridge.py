#!/usr/bin/env python
"""HTTP bridge to the NAO robot.

The NAOqi python SDK only supports python 2.7, so instead of running a whole ROS kinetic
container, HARMONI talks to the NAO through this tiny HTTP server (standard library only,
python 2.7 and 3 compatible). The ROS2 service ``speaker_nao`` (backend ``nao_http``) calls it.

    GET  /health                                   -> {"ok": true, "mock": false, "robot_ip": "..."}
    POST /say   {"text": "...", "addressee": ""}   -> {"ok": true}   (returns when NAO finished speaking)
    POST /led   {"color": "red", "rgb": [255,0,0]} -> {"ok": true}   (chest LEDs)

Configuration (environment variables): NAO_IP, NAO_PORT (9559), BRIDGE_PORT (8765),
NAO_MOCK=1 to run without robot (the text is only printed), NAO_TTS_SPEED (90), NAO_TTS_PITCH (0.9),
NAO_AWAKE=1 to wake the robot up with basic awareness and autonomous blinking on connection.
Requests are served one at a time, so two sentences never overlap.
"""

from __future__ import print_function

import json
import os
import sys
import threading

try:  # python 2
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
except ImportError:  # python 3
    from http.server import BaseHTTPRequestHandler, HTTPServer

PY2 = sys.version_info[0] == 2


class Robot(object):
    def __init__(self, ip, port=9559, mock=False, speed=90, pitch=0.9, awake=True):
        self.ip = ip
        self.port = int(port)
        self.mock = mock
        self.speed, self.pitch, self.awake = float(speed), float(pitch), awake
        self.tts = None
        self.leds = None
        self.lock = threading.Lock()
        self.said = []
        self.colors = []

    def connect(self):
        from naoqi import ALProxy  # only available in the NAOqi SDK (python 2.7)

        self.tts = ALProxy("ALTextToSpeech", self.ip, self.port)
        self.tts.setParameter("speed", self.speed)
        self.tts.setParameter("pitchShift", self.pitch)
        self.leds = ALProxy("ALLeds", self.ip, self.port)
        if self.awake:
            ALProxy("ALMotion", self.ip, self.port).wakeUp()
            ALProxy("ALBasicAwareness", self.ip, self.port).setEnabled(True)
            ALProxy("ALAutonomousBlinking", self.ip, self.port).setEnabled(True)

    def say(self, text, addressee=""):
        with self.lock:
            self.said.append((text, addressee))
            if self.mock:
                print("[mock] NAO says: %s (to %s)" % (text, addressee or "everyone"))
                return
            if self.tts is None:
                self.connect()
            if PY2 and not isinstance(text, str):
                text = text.encode("utf-8")
            self.tts.say(text)

    def led(self, color, rgb=None):
        with self.lock:
            self.colors.append(color)
            if self.mock:
                print("[mock] NAO chest LEDs: %s" % color)
                return
            if self.leds is None:
                self.connect()
            groups = {"red": "ChestLedsRed", "green": "ChestLedsGreen", "blue": "ChestLedsBlue"}
            if color in groups or color == "off":
                for name, group in groups.items():
                    (self.leds.on if name == color else self.leds.off)(group)
            else:
                r, g, b = [c / 255.0 for c in (rgb or [255, 255, 255])]
                self.leds.fadeRGB("ChestLeds", r, g, b, 0.1)


def make_handler(robot):
    class Handler(BaseHTTPRequestHandler):
        def _answer(self, code, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._answer(200, {"ok": True, "mock": robot.mock, "robot_ip": robot.ip})
            else:
                self._answer(404, {"ok": False, "error": "unknown path"})

        def do_POST(self):
            if self.path not in ("/say", "/led"):
                return self._answer(404, {"ok": False, "error": "unknown path"})
            try:
                length = int(self.headers.get("Content-Length", 0))
                request = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                value = request["text" if self.path == "/say" else "color"]
            except (ValueError, KeyError) as e:
                return self._answer(400, {"ok": False, "error": "bad request: %s" % e})
            try:
                if self.path == "/say":
                    robot.say(value, request.get("addressee", ""))
                else:
                    robot.led(value, request.get("rgb"))
            except Exception as e:  # noqa: BLE001 - robot errors are reported to the caller
                return self._answer(500, {"ok": False, "error": "%s: %s" % (type(e).__name__, e)})
            self._answer(200, {"ok": True})

        def log_message(self, fmt, *args):
            sys.stderr.write("[nao_bridge] " + (fmt % args) + "\n")

    return Handler


def make_server(robot, host="0.0.0.0", port=8765):
    return HTTPServer((host, int(port)), make_handler(robot))


def main():
    robot = Robot(os.environ.get("NAO_IP", "192.168.1.100"), os.environ.get("NAO_PORT", 9559),
                  mock=os.environ.get("NAO_MOCK", "0").lower() in ("1", "true", "yes"),
                  speed=os.environ.get("NAO_TTS_SPEED", 90), pitch=os.environ.get("NAO_TTS_PITCH", 0.9),
                  awake=os.environ.get("NAO_AWAKE", "1").lower() in ("1", "true", "yes"))
    if not robot.mock:
        robot.connect()  # fail early if the robot is not reachable
    server = make_server(robot, port=os.environ.get("BRIDGE_PORT", 8765))
    print("NAO bridge on port %s (robot %s%s)" % (server.server_port, robot.ip, ", mock" if robot.mock else ""))
    server.serve_forever()


if __name__ == "__main__":
    main()
