#!/usr/bin/env python3
"""Unit tests for the LED service (harmoni_led/led_service.py), with a fake Furhat API.
Run from the ros1/ folder with: python3 -m pytest harmoni_actuators/harmoni_led
"""

import pytest

from harmoni_common_lib.constants import State
from harmoni_led import led_service
from harmoni_led.led_service import LedService

PARAMS = {"furhat_robot_ip": "127.0.0.1", "nao_robot_ip": "127.0.0.2"}


class FakeFurhat:
    def __init__(self, ip):
        self.ip = ip
        self.leds = []

    def set_led(self, red, green, blue):
        self.leds.append((red, green, blue))


@pytest.fixture
def led(monkeypatch):
    monkeypatch.setattr(led_service, "FurhatRemoteAPI", FakeFurhat)
    return LedService("led_default", dict(PARAMS))


def test_connects_both_robots(led, published):
    assert led.furhat.ip == "127.0.0.1"
    assert published("/nao/connect") == ["127.0.0.2"]


@pytest.mark.parametrize("color, rgb", [("red", (255, 0, 0)), ("green", (0, 255, 0))])
def test_sets_the_color_on_both_robots(led, published, color, rgb):
    assert led.do(color) == {"response": State.SUCCESS}
    assert led.furhat.leds == [rgb]
    assert published("/led_nao/set") == [color]


def test_unknown_color_only_reaches_the_nao(led, published):
    assert led.do("blue") == {"response": State.SUCCESS}
    assert led.furhat.leds == []
    assert published("/led_nao/set") == ["blue"]
