#!/usr/bin/env python3
"""Unit tests for the Azure speaker-diarization STT service (harmoni_stt/sd_azure_service.py).

The Azure Speech SDK is faked (see conftest.py): the transcriber callbacks are invoked
directly with synthetic events.
Run from the repository root with: python3 -m pytest harmoni_detectors/harmoni_stt/test/unit
"""

import time
import types

import pytest

from harmoni_common_lib.constants import State
from harmoni_stt.sd_azure_service import SILENCE_MESSAGE, SDAzureService

PARAMS = {
    "language_id": "en-US",
    "sample_rate": 16000,
    "audio_channel": 1,
    "subscriber_id": "default",
    "wait_duration": 5,
    "max_silence": 10,
    "num_speakers": 3,
    "names": "Sarah, Jane,Alex",
}


class FakeTranscriber:
    def __init__(self):
        self.stopped = 0

    def stop_transcribing_async(self):
        self.stopped += 1


def _event(speaker_id, text, reason="RecognizedSpeech"):
    return types.SimpleNamespace(
        result=types.SimpleNamespace(speaker_id=speaker_id, text=text, reason=reason, no_match_details="")
    )


@pytest.fixture
def service():
    s = SDAzureService("stt_default", dict(PARAMS))
    s.conversation_transcriber = FakeTranscriber()
    s.start_time = time.time()
    s.state = State.REQUEST
    s.response_received = False
    return s


def test_names_are_stripped(service):
    assert service.names == ["Sarah", "Jane", "Alex"]


@pytest.mark.parametrize(
    "speaker_id, expected",
    [
        ("Guest-1", "Sarah"),
        ("Guest-2", "Jane"),
        ("Guest-3", "Alex"),
        ("Guest-4", "Guest-4"),  # more speakers than configured names
        ("Unknown", "Unknown"),
        ("", "Unknown"),
        (None, "Unknown"),
    ],
)
def test_speaker_name_mapping(service, speaker_id, expected):
    assert service.speaker_name(speaker_id) == expected


def test_transcribed_speech_sets_result_with_speaker(service):
    service.conversation_transcriber_transcribed_cb(_event("Guest-2", "I think AI is useful"))
    assert service.response_received is True
    assert service.state == State.SUCCESS
    assert service.result_msg == "Jane: I think AI is useful"
    assert service.conversation_transcriber.stopped == 1


def test_transcribed_speech_removes_single_quotes(service):
    service.conversation_transcriber_transcribed_cb(_event("Guest-1", "I'm not sure"))
    assert "'" not in service.result_msg


def test_transcribed_speech_of_unknown_speaker_does_not_crash(service):
    service.conversation_transcriber_transcribed_cb(_event("Unknown", "hello"))
    assert service.result_msg == "Unknown: hello"


def test_empty_transcription_keeps_listening(service):
    service.conversation_transcriber_transcribed_cb(_event("Guest-1", ""))
    assert service.response_received is False
    assert service.conversation_transcriber.stopped == 0


def test_no_match_keeps_listening(service):
    service.conversation_transcriber_transcribed_cb(_event("Guest-1", "", reason="NoMatch"))
    assert service.response_received is False


def test_silence_longer_than_max_silence_returns_prompt(service):
    service.start_time = time.time() - (PARAMS["max_silence"] + 1)
    service.conversation_transcriber_transcribed_cb(_event("Guest-1", "late text"))
    assert service.result_msg == SILENCE_MESSAGE
    assert service.response_received is True


def test_transcribing_with_unknown_speaker_does_not_crash(service):
    # this used to raise ValueError: int("Unknown")
    service.conversation_transcriber_transcribing_cb(_event("Unknown", "partial"))
    assert service._current_speaker_talking == "Unknown"
    service.conversation_transcriber_transcribing_cb(_event("Guest-3", "partial"))
    assert service._current_speaker_talking == "Alex"


@pytest.mark.parametrize("state, buffered", [(State.REQUEST, 1), (State.START, 1), (State.INIT, 0), (State.SUCCESS, 0)])
def test_microphone_callback_buffers_only_when_listening(service, state, buffered):
    service.state = state
    service.callback(types.SimpleNamespace(data=b"\x00\x01"))
    assert service._buff.qsize() == buffered


def test_stop_stops_transcriber(service):
    service.stop()
    assert service.conversation_transcriber.stopped == 1
    assert service.state == State.SUCCESS
