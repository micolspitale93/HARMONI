"""Service backends with fake SDKs (no network, no robots)"""

import json
import threading
import types
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from harmoni.constants import ActionType
from harmoni.services import Result, ServiceBackend, create_backend
from harmoni.services.assistant import FALLBACK_MESSAGE, AssistantBackend, parse_input
from harmoni.services.azure_diarization import SILENCE_MESSAGE, AzureDiarizationBackend
from harmoni.services.robots import FurhatBackend, NaoHttpBackend, parse_speech_request


# ------------------------------------------------------------------ base
class Echo(ServiceBackend):
    def request(self, data):
        return Result(True, data.upper())

    def do(self, data):
        raise RuntimeError("motor stuck")


def test_handle_dispatches_and_never_raises():
    b = Echo("echo_default")
    assert b.handle(ActionType.REQUEST, "hi") == Result(True, "HI")
    assert b.handle(ActionType.DO, "x") == Result(False, "RuntimeError: motor stuck")
    assert b.handle(ActionType.ON).ok


def test_unsupported_action_and_unknown_backend():
    class OnlyRequest(ServiceBackend):
        def request(self, data):
            return Result(True)

    assert not OnlyRequest("x").handle(ActionType.DO, "").ok
    with pytest.raises(KeyError):
        create_backend("nope", "x")


def test_mock_backend_cycles_and_echoes():
    m = create_backend("mock", "m", {"responses": ["a", "b"]})
    assert [m.request("").message for _ in range(3)] == ["a", "b", "a"]
    assert create_backend("mock", "e").do("payload").message == "payload"


def test_mock_backend_cancel_interrupts_delay():
    m = create_backend("mock", "m", {"delay_s": 10})
    threading.Timer(0.05, m.cancel).start()
    assert m.request("") == Result(False, "cancelled")


# ------------------------------------------------------------------ assistant
def _event(name, text=None):
    data = None if text is None else types.SimpleNamespace(
        content=[types.SimpleNamespace(text=types.SimpleNamespace(value=text))])
    return types.SimpleNamespace(event=name, data=data)


class FakeOpenAI:
    def __init__(self, answer='{"intervene": true}', error=None):
        self.messages, self.runs, self.answer, self.error = [], [], answer, error
        outer = self
        self.beta = types.SimpleNamespace(threads=types.SimpleNamespace(
            create=lambda: types.SimpleNamespace(id="thread_1"),
            messages=types.SimpleNamespace(create=lambda tid, role, content: outer.messages.append((tid, role, content))),
            runs=types.SimpleNamespace(create=self._run),
        ))

    def _run(self, **kwargs):
        self.runs.append(kwargs)
        if self.error:
            raise self.error
        return iter([_event("thread.run.created"), _event("thread.message.completed", self.answer)])


def make_assistant(service_id="bot_default", **params):
    emitted = []
    b = AssistantBackend(service_id, dict({"assistant_id": "asst_1", "participants": "Sarah, Jane"}, **params),
                         emit=lambda ch, msg: emitted.append((ch, msg)))
    b.client = FakeOpenAI()
    return b, emitted


def test_parse_input():
    assert parse_input("['*user* I *really* agree']") == [{"role": "user", "content": "I *really* agree"}]
    for bad in ["", "[]", "nope", "['no role']"]:
        with pytest.raises(ValueError):
            parse_input(bad)


def test_orchestrator_creates_and_shares_the_thread():
    b, emitted = make_assistant()
    b.setup()
    assert b.thread_id == "thread_1" and ("thread_id", "thread_1") in emitted
    assert b.response_format["type"] == "json_schema"


def test_other_assistants_join_the_thread():
    b, emitted = make_assistant("bot_mover")
    b.setup()
    assert b.thread_id == "" and emitted == []
    b.on_input("thread_id", "thread_shared")
    assert b.thread_id == "thread_shared"
    assert b.response_format == {"type": "text"}


def test_assistant_request():
    b, emitted = make_assistant()
    b.setup()
    result = b.request("['*user* Sarah: hello', '*user* Jane: hi']")
    assert result == Result(True, '{"intervene": true}')
    assert b.client.messages == [("thread_1", "user", "Jane: hi")]
    assert b.client.runs[0]["assistant_id"] == "asst_1"
    instructions = b.client.runs[0]["additional_instructions"]
    assert "Sarah, Jane" in instructions and "The name of the 2 university students" in instructions


@pytest.mark.parametrize("payload, error", [("not a list", None), ("['*user* hi']", RuntimeError("API down"))])
def test_assistant_errors_return_fallback(payload, error):
    b, _ = make_assistant()
    b.setup()
    b.client.error = error
    assert b.request(payload) == Result(False, FALLBACK_MESSAGE)


def test_assistant_without_thread_fails():
    b, _ = make_assistant("bot_mover")
    assert not b.request("['*user* hi']").ok


# ------------------------------------------------------------------ azure diarization
class FakeTranscriber:
    def __init__(self):
        self.started = self.stopped = 0

    def start_transcribing_async(self):
        self.started += 1

    def stop_transcribing_async(self):
        self.stopped += 1


def recognized(speaker, text):
    return types.SimpleNamespace(result=types.SimpleNamespace(
        reason=types.SimpleNamespace(name="RecognizedSpeech"), speaker_id=speaker, text=text))


@pytest.fixture
def diarization():
    b = AzureDiarizationBackend("stt_default", {"names": "Sarah, Jane", "max_silence": 0.3, "max_wait_s": 5})
    b.transcriber = FakeTranscriber()
    return b


@pytest.mark.parametrize("speaker, name", [("Guest-1", "Sarah"), ("Guest-2", "Jane"), ("Guest-3", "Guest-3"),
                                           ("Unknown", "Unknown"), (None, "Unknown")])
def test_speaker_names(diarization, speaker, name):
    assert diarization.speaker_name(speaker) == name


def test_diarization_returns_speaker_and_text(diarization):
    threading.Timer(0.05, diarization.on_transcribed, [recognized("Guest-2", "I'm not sure")]).start()
    assert diarization.request() == Result(True, "Jane: I m not sure")
    assert diarization.transcriber.started == diarization.transcriber.stopped == 1


def test_diarization_silence(diarization):
    assert diarization.request() == Result(True, SILENCE_MESSAGE)


def test_diarization_ongoing_speech_postpones_silence(diarization):
    def talk():
        for _ in range(4):
            diarization.on_transcribing(None)
            threading.Event().wait(0.15)
        diarization.on_transcribed(recognized("Guest-1", "long sentence"))

    threading.Thread(target=talk).start()
    assert diarization.request().message == "Sarah: long sentence"


def test_diarization_cancel(diarization):
    threading.Timer(0.05, diarization.cancel).start()
    diarization.max_silence = 10
    assert diarization.request() == Result(False, "cancelled")
    assert diarization.transcriber.stopped == 1


# ------------------------------------------------------------------ robots
@pytest.mark.parametrize("payload, expected", [
    (json.dumps({"input": "Hi", "addressee": "Sarah"}), ("Hi", ["Sarah"])),
    (json.dumps({"input": "Hi", "addressee": "Sarah, Jane"}), ("Hi", ["Sarah", "Jane"])),
    (json.dumps({"input": "Hi", "addressee": "null"}), ("Hi", [])),
    ("plain", ("plain", [])),
])
def test_parse_speech_request(payload, expected):
    assert parse_speech_request(payload) == expected


class FakeFurhat:
    def __init__(self):
        self.said, self.attended = [], []

    def say(self, text, blocking):
        self.said.append(text)

    def attend(self, userid):
        self.attended.append(userid)


def test_furhat():
    b = FurhatBackend("speaker_furhat", {"robot_ip": "1.2.3.4"})
    b.api = FakeFurhat()
    assert b.do(json.dumps({"input": "Hi", "addressee": "Jane"})).ok
    assert b.do(json.dumps({"input": "Hi all", "addressee": "Jane, Sarah"})).ok
    assert b.api.said == ["Hi", "Hi all"] and b.api.attended == ["Jane"]


def test_furhat_mockup_needs_no_sdk():
    assert FurhatBackend("speaker_furhat", {"mockup": True}).do("Hi").ok


class _Bridge(BaseHTTPRequestHandler):
    received = []
    ok = True

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Bridge.received.append((self.path, body))
        answer = json.dumps({"ok": _Bridge.ok, "error": "" if _Bridge.ok else "robot fell"}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(answer)))
        self.end_headers()
        self.wfile.write(answer)

    def log_message(self, *args):
        pass


@pytest.fixture
def bridge():
    server = HTTPServer(("127.0.0.1", 0), _Bridge)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _Bridge.received, _Bridge.ok = [], True
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_nao_http(bridge):
    b = NaoHttpBackend("speaker_nao", {"bridge_url": bridge})
    assert b.do(json.dumps({"input": "Hello", "addressee": "Sarah"})).ok
    assert _Bridge.received == [("/say", {"text": "Hello", "addressee": "Sarah"})]
    _Bridge.ok = False
    assert b.do("Hi") == Result(False, "robot fell")


def test_nao_http_unreachable():
    result = NaoHttpBackend("speaker_nao", {"bridge_url": "http://127.0.0.1:1", "timeout_s": 1}).do("Hi")
    assert not result.ok and "unreachable" in result.message
