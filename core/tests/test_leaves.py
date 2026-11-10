"""ROS-agnostic leaves"""

import ast
import json

import py_trees
import pytest

from harmoni.leaves.group import GroupScript, OrchestratorDecision, ScriptedTurn, parse_agent_response
from harmoni.leaves.generic import CheckValue, CopyValue, SetValue, Wait
from harmoni.leaves.service_action import ServiceAction
from harmoni.tree import BuildContext
from harmoni.tree.clients import CallStatus, ServiceCall
from tests.conftest import bb_get, bb_set

Status = py_trees.common.Status


class FakeCall(ServiceCall):
    def __init__(self):
        super().__init__()
        self.cancelled = False

    def finish(self, ok=True, message=""):
        self.ok, self.message, self.status = ok, message, CallStatus.SUCCEEDED

    def fail(self, message="boom"):
        self.message, self.status = message, CallStatus.FAILED

    def cancel(self):
        self.cancelled = True
        self.status = CallStatus.CANCELLED


class FakeClient:
    def __init__(self):
        self.sent = []
        self.calls = []

    def send(self, action, data):
        self.sent.append((action.name, data))
        call = FakeCall()
        self.calls.append(call)
        return call


def ctx(clock, client=None, base_dir=None):
    client = client or FakeClient()
    return BuildContext(client_for=lambda service: client, clock=clock, base_dir=base_dir), client


def tick(behaviour):
    behaviour.tick_once()
    return behaviour.status


# ------------------------------------------------------------------ generic
@pytest.mark.parametrize("params, value, expected", [
    ({"equals": 0}, 0, Status.SUCCESS),
    ({"equals": 0}, 1, Status.FAILURE),
    ({"equals": False}, False, Status.SUCCESS),
    ({"not_equals": "Mover"}, "Opposer", Status.SUCCESS),
    ({"one_of": ["a", "b"]}, "c", Status.FAILURE),
    ({"truthy": True}, "x", Status.SUCCESS),
])
def test_check_value(params, value, expected):
    bb_set(**{"k/v": value})
    assert tick(CheckValue("c", key="k/v", **params)) == expected


def test_check_value_missing_key_fails():
    assert tick(CheckValue("c", key="missing", equals=1)) == Status.FAILURE


def test_set_and_copy_value():
    tick(SetValue("s", key="a/b", value=[1, 2]))
    tick(CopyValue("c", source="a/b", target="x/y"))
    assert bb_get("x/y") == [1, 2]


def test_wait(clock):
    w = Wait("w", BuildContext(clock=clock), seconds=2)
    assert tick(w) == Status.RUNNING
    clock.advance(2.5)
    assert tick(w) == Status.SUCCESS


# ------------------------------------------------------------------ ServiceAction
def test_service_action_success_writes_output(clock):
    context, client = ctx(clock)
    bb_set(**{"scene/utterance": "hello"})
    leaf = ServiceAction("ask", context, service="bot_default", input_key="scene/utterance", output_key="bot/raw")
    assert tick(leaf) == Status.RUNNING
    assert client.sent == [("REQUEST", "hello")]
    assert tick(leaf) == Status.RUNNING  # never blocks
    client.calls[0].finish(True, "answer")
    assert tick(leaf) == Status.SUCCESS
    assert bb_get("bot/raw") == "answer"


def test_service_action_json_payload_with_blackboard_refs(clock):
    context, client = ctx(clock)
    bb_set(**{"bot/message": 'He said "hi"\nok', "bot/addressee": "Sarah"})
    leaf = ServiceAction("say", context, service="speaker_furhat", action="DO",
                         input_json={"input": "@bot/message", "addressee": "@bot/addressee", "lang": "en"})
    tick(leaf)
    action, data = client.sent[0]
    assert action == "DO"
    assert json.loads(data) == {"input": 'He said "hi"\nok', "addressee": "Sarah", "lang": "en"}


@pytest.mark.parametrize("on_failure, expected", [("failure", Status.FAILURE), ("success", Status.SUCCESS)])
def test_service_action_failure_outcome(clock, on_failure, expected):
    context, client = ctx(clock)
    leaf = ServiceAction("x", context, service="s", output_key="out", on_failure=on_failure, failure_output="fallback")
    tick(leaf)
    client.calls[0].finish(False, "service said no")
    assert tick(leaf) == expected
    assert bb_get("out") == "fallback"


def test_service_action_call_error(clock):
    context, client = ctx(clock)
    leaf = ServiceAction("x", context, service="s")
    tick(leaf)
    client.calls[0].fail("unreachable")
    assert tick(leaf) == Status.FAILURE
    assert "unreachable" in leaf.feedback_message


def test_service_action_timeout_cancels_the_call(clock):
    context, client = ctx(clock)
    leaf = ServiceAction("listen", context, service="stt", output_key="stt/result", timeout_s=10,
                         on_timeout="success", timeout_output="silence")
    tick(leaf)
    clock.advance(5)
    assert tick(leaf) == Status.RUNNING
    clock.advance(6)
    assert tick(leaf) == Status.SUCCESS
    assert client.calls[0].cancelled
    assert bb_get("stt/result") == "silence"


def test_service_action_interrupted_cancels_the_call(clock):
    context, client = ctx(clock)
    leaf = ServiceAction("x", context, service="s")
    tick(leaf)
    leaf.stop(Status.INVALID)
    assert client.calls[0].cancelled


def test_service_action_new_call_at_each_activation(clock):
    context, client = ctx(clock)
    leaf = ServiceAction("x", context, service="s")
    for _ in range(2):
        tick(leaf)
        client.calls[-1].finish(True, "")
        assert tick(leaf) == Status.SUCCESS
    assert len(client.sent) == 2


# ------------------------------------------------------------------ group interaction
@pytest.fixture
def script(tmp_path):
    scenes = [
        {"utterance": "Hi $USERNAME1 and $USERNAME2", "agent": "Mover", "nlp": 0},
        {"utterance": "I am Andrea", "agent": "Opposer", "nlp": 0},
        {"utterance": "", "agent": "Mover", "nlp": 1},
        {"utterance": "", "agent": "Mover", "nlp": 1},
        {"utterance": "", "agent": "Mover", "nlp": 1},
        {"utterance": "Goodbye", "agent": "Opposer", "nlp": 0},
    ]
    path = tmp_path / "script.json"
    path.write_text(json.dumps({"2session": scenes}))
    return str(path)


def make_script(script, clock, **kw):
    params = dict(script=script, session="2session", user_names="Sarah, Jane", max_scenes=30)
    params.update(kw)
    leaf = GroupScript("script", BuildContext(clock=clock), **params)
    leaf.setup()
    return leaf


def test_group_script_scripted_scene_replaces_names(script, clock):
    leaf = make_script(script, clock)
    tick(leaf)
    assert bb_get("scene/utterance") == "Hi Sarah and Jane"
    assert bb_get("scene/nlp") == 0 and bb_get("scene/agent") == "Mover"


def test_group_script_llm_scene_wraps_transcription(script, clock):
    leaf = make_script(script, clock)
    leaf.scene_number = 4
    bb_set(**{"stt/result": "Sarah: I'm sure it's \"fine\""})
    tick(leaf)
    assert ast.literal_eval(bb_get("scene/utterance")) == ["*user* Sarah: I'm sure it's \"fine\""]


def test_group_script_start_discussion_prompt(script, clock):
    leaf = make_script(script, clock)
    leaf.scene_number = 3  # 1 + number of participants (2session)
    tick(leaf)
    assert "MUST START" in bb_get("scene/utterance")


@pytest.mark.parametrize("start, max_scenes", [(5, 30), (2, 2), (50, 30)])
def test_group_script_closing_scene_finishes(script, clock, start, max_scenes):
    leaf = make_script(script, clock, max_scenes=max_scenes)
    leaf.scene_number = start
    tick(leaf)
    assert bb_get("scene/utterance") == "Goodbye"
    assert bb_get("scene/agent") == "Opposer"
    assert bb_get("scene/finished") is True


def test_group_script_unknown_session(script, clock):
    with pytest.raises(KeyError):
        make_script(script, clock, session="9session")


def test_scripted_turn():
    bb_set(**{"scene/utterance": "Hello", "scene/agent": "Opposer"})
    tick(ScriptedTurn("t"))
    assert (bb_get("bot/message"), bb_get("bot/agent"), bb_get("bot/speak")) == ("Hello", "Opposer", True)


@pytest.mark.parametrize("raw, speak, agent", [
    ('{"intervene": true, "agent": "Opposer", "response": "Why?", "addressee": "Sarah"}', True, "Opposer"),
    ('{"intervene": false, "agent": "Mover", "response": ""}', False, "Mover"),
    ("{'intervene': 'false', 'agent': 'Mover'}", False, "Mover"),
    ("Can you repeat?", True, "null"),
    ("", False, "null"),
])
def test_orchestrator_decision(raw, speak, agent):
    bb_set(**{"bot/raw": raw})
    tick(OrchestratorDecision("d"))
    assert bb_get("bot/speak") is speak
    assert bb_get("bot/agent") == agent


def test_parse_agent_response_defaults():
    assert parse_agent_response("{}") == {"message": "", "agent": "null", "intervene": True, "addressee": "null"}
    assert parse_agent_response(None)["intervene"] is False
