#!/usr/bin/env python
"""HTTP bridge to the NAO robot.

The NAOqi python SDK only supports python 2.7, so instead of running a whole ROS kinetic
container, HARMONI talks to the NAO through this tiny HTTP server (standard library only,
python 2.7 and 3 compatible). The ROS2 service ``speaker_nao`` (backend ``nao_http``) calls it.

    GET  /health                                   -> {"ok": true, "mock": false, "robot_ip": "..."}
    POST /say   {"text": "...", "addressee": ""}   -> {"ok": true}   (returns when NAO finished speaking)

Configuration (environment variables): NAO_IP, NAO_PORT (9559), BRIDGE_PORT (8765),
NAO_MOCK=1 to run without robot (the text is only printed).
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
    def __init__(self, ip, port=9559, mock=False):
        self.ip = ip
        self.port = int(port)
        self.mock = mock
        self.tts = None
        self.lock = threading.Lock()
        self.said = []

    def connect(self):
        from naoqi import ALProxy  # only available in the NAOqi SDK (python 2.7)

        self.tts = ALProxy("ALTextToSpeech", self.ip, self.port)

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
            if self.path != "/say":
                return self._answer(404, {"ok": False, "error": "unknown path"})
            try:
                length = int(self.headers.get("Content-Length", 0))
                request = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                text = request["text"]
            except (ValueError, KeyError) as e:
                return self._answer(400, {"ok": False, "error": "bad request: %s" % e})
            try:
                robot.say(text, request.get("addressee", ""))
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
                  mock=os.environ.get("NAO_MOCK", "0").lower() in ("1", "true", "yes"))
    if not robot.mock:
        robot.connect()  # fail early if the robot is not reachable
    server = make_server(robot, port=os.environ.get("BRIDGE_PORT", 8765))
    print("NAO bridge on port %s (robot %s%s)" % (server.server_port, robot.ip, ", mock" if robot.mock else ""))
    server.serve_forever()


if __name__ == "__main__":
    main()
