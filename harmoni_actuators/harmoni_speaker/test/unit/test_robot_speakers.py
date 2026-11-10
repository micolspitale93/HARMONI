#!/usr/bin/env python3
"""Unit tests for the robot speakers (NAO and Furhat) of harmoni_speaker.

The NAO ROS service proxy and the Furhat remote API are faked, so no robot is needed.
Run from the repository root with: python3 -m pytest harmoni_actuators/harmoni_speaker/test/unit
"""

import json

import pytest

from harmoni_common_lib.constants import State
from harmoni_speaker import speaker_service_furhat, speaker_service_nao
from harmoni_speaker.speaker_service_furhat import SpeakerServiceFurhat
from harmoni_speaker.speaker_service_nao import SpeakerServiceNAO, parse_speech_request

ROBOT_PARAMS = {"robot_ip": "127.0.0.1", "instance_id": "test", "mockup": 0}


# ---------------------------------------------------------------- payload parsing
@pytest.mark.parametrize("module", [speaker_service_nao, speaker_service_furhat])
@pytest.mark.parametrize(
    "payload, expected",
    [
        (json.dumps({"input": "Hello", "addressee": "Sarah"}), ("Hello", ["Sarah"])),
        (json.dumps({"input": "Hello", "addressee": "Sarah, Jane"}), ("Hello", ["Sarah", "Jane"])),
        (json.dumps({"input": "Hello", "addressee": "null"}), ("Hello", [])),
        (json.dumps({"input": "Hello", "addressee": ""}), ("Hello", [])),
        (json.dumps({"input": "Hello"}), ("Hello", [])),
        (json.dumps({"input": 'She said "hi"\nthen left'}), ('She said "hi"\nthen left', [])),
        ("plain text, not json", ("plain text, not json", [])),
    ],
)
def test_parse_speech_request(module, payload, expected):
    assert module.parse_speech_request(payload) == expected


# ---------------------------------------------------------------- NAO
@pytest.fixture
def nao():
    return SpeakerServiceNAO("speaker_nao", dict(ROBOT_PARAMS))


def test_nao_publishes_robot_ip_on_connect(nao, published):
    assert published("/speaker_nao/connect") == ["127.0.0.1"]


def test_nao_says_text_and_publishes_addressee(nao, published):
    result = nao.do(json.dumps({"input": "Hello Sarah", "addressee": "Sarah"}))
    assert result == {"response": State.SUCCESS}
    assert nao.speak_service.calls == [("Hello Sarah",)]
    assert published("/speaker_nao/addressee") == ["Sarah"]
    assert nao.actuation_completed is True


def test_nao_multiple_addressees_are_not_published(nao, published):
    nao.do(json.dumps({"input": "Hello all", "addressee": "Sarah, Jane"}))
    assert published("/speaker_nao/addressee") == []


def test_nao_missing_addressee_does_not_crash(nao, published):
    assert nao.do(json.dumps({"input": "Hello"}))["response"] == State.SUCCESS
    assert published("/speaker_nao/addressee") == []


def test_nao_service_failure_returns_failed(nao):
    import rospy

    nao.speak_service.side_effect = rospy.ServiceException("robot unreachable")
    assert nao.do(json.dumps({"input": "Hello"}))["response"] == State.FAILED
    assert nao.actuation_completed is True


def test_nao_mockup_does_not_call_robot():
    nao = SpeakerServiceNAO("speaker_nao", dict(ROBOT_PARAMS, mockup=1))
    assert nao.do(json.dumps({"input": "Hello", "addressee": "Sarah"}))["response"] == State.SUCCESS
    assert nao.speak_service.calls == []


# ---------------------------------------------------------------- Furhat
class FakeFurhat:
    def __init__(self, ip=None):
        self.ip = ip
        self.said = []
        self.attended = []
        self.voice = None
        self.error = None

    def get_voices(self):
        return []

    def set_voice(self, name):
        self.voice = name

    def say(self, text, blocking=True):
        if self.error:
            raise self.error
        self.said.append(text)

    def attend(self, userid):
        self.attended.append(userid)


@pytest.fixture
def furhat(monkeypatch):
    monkeypatch.setattr(speaker_service_furhat, "FurhatRemoteAPI", FakeFurhat)
    return SpeakerServiceFurhat("speaker_furhat", dict(ROBOT_PARAMS))


def test_furhat_connects_and_sets_voice(furhat):
    assert furhat.furhat.ip == "127.0.0.1"
    assert furhat.furhat.voice == "Matthew"


def test_furhat_says_text_and_attends_addressee(furhat):
    result = furhat.do(json.dumps({"input": "Hello Jane", "addressee": "Jane"}))
    assert result == {"response": State.SUCCESS}
    assert furhat.furhat.said == ["Hello Jane"]
    assert furhat.furhat.attended == ["Jane"]


@pytest.mark.parametrize("addressee", ["null", "", "Sarah, Jane"])
def test_furhat_does_not_attend_when_no_single_addressee(furhat, addressee):
    furhat.do(json.dumps({"input": "Hello", "addressee": addressee}))
    assert furhat.furhat.attended == []


def test_furhat_api_error_returns_failed(furhat):
    furhat.furhat.error = RuntimeError("robot unreachable")
    assert furhat.do(json.dumps({"input": "Hello"}))["response"] == State.FAILED


def test_furhat_mockup_does_not_connect(monkeypatch):
    monkeypatch.setattr(speaker_service_furhat, "FurhatRemoteAPI", FakeFurhat)
    s = SpeakerServiceFurhat("speaker_furhat", dict(ROBOT_PARAMS, mockup=1))
    assert not hasattr(s, "furhat")
    assert s.do(json.dumps({"input": "Hello"}))["response"] == State.SUCCESS
