"""The NAO bridge (python 2/3 HTTP server) with the nao_http backend, over real HTTP"""

import json
import threading
import urllib.request

import pytest

import nao_bridge
from harmoni.services.robots import NaoHttpBackend


@pytest.fixture
def bridge():
    robot = nao_bridge.Robot("127.0.0.1", mock=True)
    server = nao_bridge.make_server(robot, host="127.0.0.1", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield robot, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_health(bridge):
    robot, url = bridge
    with urllib.request.urlopen(url + "/health") as r:
        assert json.loads(r.read()) == {"ok": True, "mock": True, "robot_ip": "127.0.0.1"}


def test_nao_http_backend_says_through_the_bridge(bridge):
    robot, url = bridge
    backend = NaoHttpBackend("speaker_nao", {"bridge_url": url})
    assert backend.do(json.dumps({"input": 'Is it "really" true?', "addressee": "Jane"})).ok
    assert robot.said == [('Is it "really" true?', "Jane")]


def test_robot_error_is_reported(bridge):
    robot, url = bridge

    def broken(text, addressee=""):
        raise RuntimeError("NAO is sleeping")

    robot.say = broken
    result = NaoHttpBackend("speaker_nao", {"bridge_url": url}).do("Hello")
    assert not result.ok and "NAO is sleeping" in result.message


def test_bad_request(bridge):
    _, url = bridge
    request = urllib.request.Request(url + "/say", data=b'{"no_text": 1}', method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(request)
    assert e.value.code == 400


def test_led_through_the_bridge(bridge):
    from harmoni.services.robots import NaoLedHttpBackend

    robot, url = bridge
    assert NaoLedHttpBackend("led_nao", {"bridge_url": url}).do("red").ok
    assert robot.colors == ["red"]
