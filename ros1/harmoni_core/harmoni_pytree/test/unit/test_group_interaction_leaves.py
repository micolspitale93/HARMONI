#!/usr/bin/env python3
"""Unit tests for the py_trees leaves used by the group interaction
(pytree_group_interaction.py): script, assistant (LLM orchestrator) and speaker leaves.

Action clients are replaced by fakes so that no ROS service is needed.
Run from the repository root with: python3 -m pytest harmoni_core/harmoni_pytree/test/unit
"""

import ast
import json

import py_trees
import pytest

from actionlib_msgs.msg import GoalStatus
from harmoni_pytree.leaves.assistant_service import AssistantServicePytree, parse_agent_response
from harmoni_pytree.leaves.script_group_dialogue_service import ScriptGroupDialogueService
from harmoni_pytree.leaves.speaker_service import SpeakerServicePytree

Status = py_trees.common.Status


class FakeActionClient:
    def __init__(self, state=GoalStatus.ACTIVE):
        self.goals = []
        self.state = state
        self.cancelled = 0

    def send_goal(self, action_goal, optional_data="", wait=False, **kwargs):
        self.goals.append((action_goal, optional_data))

    def get_state(self):
        return self.state

    def cancel_all_goals(self):
        self.cancelled += 1


@pytest.fixture(autouse=True)
def clean_blackboard():
    py_trees.blackboard.Blackboard.clear()
    yield
    py_trees.blackboard.Blackboard.clear()


def writer(namespace, **values):
    """Write values on the blackboard namespace used by the leaves"""
    client = py_trees.blackboard.Client(name=f"test_{namespace}", namespace=namespace)
    for key, value in values.items():
        client.register_key(key=key, access=py_trees.common.Access.WRITE)
        setattr(client, key, value)
    return client


def read(namespace, key):
    return py_trees.blackboard.Blackboard.get(f"/{namespace}/{key}")


# ======================================================================
# parse_agent_response
# ======================================================================
def test_parse_valid_json():
    text = json.dumps({"intervene": True, "agent": "Mover", "response": "Hello", "addressee": "Sarah"})
    assert parse_agent_response(text) == {
        "message": "Hello",
        "agent": "Mover",
        "intervene": True,
        "addressee": "Sarah",
    }


def test_parse_python_dict_with_single_quotes():
    text = "{'intervene': False, 'agent': 'Opposer', 'response': 'Why?', 'addressee': 'Jane'}"
    parsed = parse_agent_response(text)
    assert parsed["agent"] == "Opposer"
    assert parsed["intervene"] is False


@pytest.mark.parametrize("value, expected", [("false", False), ("False", False), ("true", True), ("0", False)])
def test_parse_intervene_given_as_string(value, expected):
    assert parse_agent_response(json.dumps({"intervene": value, "response": "x"}))["intervene"] is expected


def test_parse_missing_keys_get_defaults():
    assert parse_agent_response("{}") == {"message": "", "agent": "null", "intervene": True, "addressee": "null"}


def test_parse_plain_text_is_said():
    parsed = parse_agent_response("Can you please repeat what you said?")
    assert parsed["message"] == "Can you please repeat what you said?"
    assert parsed["intervene"] is True
    assert parsed["agent"] == "null"


@pytest.mark.parametrize("text", ["", "   ", None])
def test_parse_empty_result_means_silence(text):
    assert parse_agent_response(text)["intervene"] is False


# ======================================================================
# AssistantServicePytree
# ======================================================================
@pytest.fixture
def assistant_leaf():
    writer("scene", nlp=1, utterance="['*user* Sarah: hello']")
    leaf = AssistantServicePytree("LLM Assistant")
    leaf.service_client_chatgpt = FakeActionClient()
    leaf.server_name = "bot_default"
    return leaf


def test_assistant_sends_request_then_parses_result(assistant_leaf):
    assert assistant_leaf.update() == Status.RUNNING
    assert assistant_leaf.service_client_chatgpt.goals == [(3, "['*user* Sarah: hello']")]

    assistant_leaf.service_client_chatgpt.state = GoalStatus.SUCCEEDED
    assistant_leaf.client_result = json.dumps(
        {"intervene": True, "agent": "Opposer", "response": "Are you sure?", "addressee": "Sarah"}
    )
    assert assistant_leaf.update() == Status.SUCCESS
    assert read("bot", "agent") == "Opposer"
    assert read("bot", "addressee") == "Sarah"
    assert read("bot", "speak") == 1
    assert read("tts", "result") == "Are you sure?"


def test_assistant_intervene_false_sets_speak_zero(assistant_leaf):
    assistant_leaf.update()
    assistant_leaf.service_client_chatgpt.state = GoalStatus.SUCCEEDED
    assistant_leaf.client_result = json.dumps({"intervene": False, "agent": "Mover", "response": "", "addressee": ""})
    assert assistant_leaf.update() == Status.SUCCESS
    assert read("bot", "speak") == 0


def test_assistant_non_json_result_does_not_crash(assistant_leaf):
    assistant_leaf.update()
    assistant_leaf.service_client_chatgpt.state = GoalStatus.SUCCEEDED
    assistant_leaf.client_result = "Can you please repeat what you said?"
    assert assistant_leaf.update() == Status.SUCCESS
    assert read("tts", "result") == "Can you please repeat what you said?"


def test_assistant_waits_for_result(assistant_leaf):
    assistant_leaf.update()
    assistant_leaf.service_client_chatgpt.state = GoalStatus.SUCCEEDED
    assistant_leaf.client_result = None
    assert assistant_leaf.update() == Status.RUNNING


def test_assistant_scripted_scene_skips_llm():
    writer("scene", nlp=0, utterance="Hi, I am Manny")
    leaf = AssistantServicePytree("LLM Assistant")
    leaf.service_client_chatgpt = FakeActionClient()
    assert leaf.update() == Status.SUCCESS
    assert leaf.service_client_chatgpt.goals == []
    assert read("tts", "result") == "Hi, I am Manny"


# ======================================================================
# ScriptGroupDialogueService
# ======================================================================
@pytest.fixture
def script_leaf():
    writer("stt", result="Sarah: hello everyone")
    leaf = ScriptGroupDialogueService(
        "Script",
        params={"interaction": "group_interaction", "session": "3session", "user_names": "Sarah,Jane,Alex"},
    )
    leaf.setup()
    return leaf


def test_script_setup_loads_first_scene(script_leaf):
    first = script_leaf.context["3session"][0]
    assert read("scene", "agent") == first["agent"]
    assert read("scene", "nlp") == first["nlp"]
    assert read("scene", "max_number_scene") == 30


def test_script_scripted_scenes_replace_usernames(script_leaf):
    script_leaf.update()
    utterance = read("scene", "utterance")
    assert "$USERNAME" not in utterance


def test_script_user_utterance_is_a_valid_literal_even_with_quotes(script_leaf):
    writer("stt", result="Sarah: I'm sure it's \"fine\"")
    # move to the first LLM driven scene
    nlp_scene = next(i for i, s in enumerate(script_leaf.context["3session"]) if s["nlp"] != 0)
    script_leaf.scene_number = nlp_scene + 10
    script_leaf.update()
    utterance = read("scene", "utterance")
    assert ast.literal_eval(utterance) == ["*user* Sarah: I'm sure it's \"fine\""]


def test_script_closing_scene_at_max_number(script_leaf):
    script_leaf.scene_number = 30
    script_leaf.update()
    assert read("scene", "nlp") == 0
    assert read("scene", "utterance") == script_leaf.context["3session"][-1]["utterance"]


def test_script_never_indexes_past_the_end(script_leaf):
    script_leaf.scene_number = len(script_leaf.context["3session"]) + 5
    assert script_leaf.update() == Status.SUCCESS


@pytest.mark.parametrize("session", ["1session", "2session", "3session"])
def test_all_sessions_end_with_closing_by_robot(session, script_leaf):
    scenes = script_leaf.context[session]
    assert scenes[-1]["nlp"] == 0
    assert scenes[-1]["agent"] in ("Mover", "Opposer")
    assert len(scenes) > 30, "the session must have more scenes than max_number_scene"


# ======================================================================
# SpeakerServicePytree
# ======================================================================
def speaker_leaf(name="Mover", instance_id="furhat"):
    leaf = SpeakerServicePytree(name=name, instance_id=instance_id)
    leaf.service_client_speaker = FakeActionClient()
    leaf.server_name = f"speaker_{instance_id}"
    return leaf


def test_speaker_payload_is_valid_json_with_quotes_and_newlines():
    message = 'He said "AI is great"\nand left'
    writer("tts", result=message)
    writer("scene", nlp=1, agent="")
    writer("bot", agent="Mover", speak=1, addressee="Sarah")
    leaf = speaker_leaf()
    assert leaf.update() == Status.RUNNING
    action, payload = leaf.service_client_speaker.goals[0]
    assert action == 4  # DO
    assert json.loads(payload) == {"input": message, "addressee": "Sarah"}


def test_speaker_stays_silent_when_bot_does_not_intervene():
    # speak == 0 used to be ignored because of operator precedence (nlp == 2 | speak == 0)
    writer("tts", result="something")
    writer("scene", nlp=1, agent="")
    writer("bot", agent="Mover", speak=0, addressee="Sarah")
    leaf = speaker_leaf()
    assert leaf.update() == Status.SUCCESS
    assert leaf.service_client_speaker.goals == []


def test_speaker_of_other_agent_fails_so_selector_tries_next():
    writer("tts", result="something")
    writer("scene", nlp=1, agent="")
    writer("bot", agent="Opposer", speak=1, addressee="Sarah")
    leaf = speaker_leaf(name="Mover")
    assert leaf.update() == Status.FAILURE


def test_scripted_scene_is_said_by_the_scripted_agent():
    writer("tts", result="Hi, I am Andrea")
    writer("scene", nlp=0, agent="Opposer")
    writer("bot", agent="null", speak=1, addressee="null")
    assert speaker_leaf(name="Mover").update() == Status.FAILURE
    opposer = speaker_leaf(name="Opposer", instance_id="nao")
    assert opposer.update() == Status.RUNNING
    opposer.service_client_speaker.state = GoalStatus.SUCCEEDED
    assert opposer.update() == Status.SUCCESS


# ======================================================================
# Speak -> Listen step of the group interaction tree
# ======================================================================
class RecordingListener(py_trees.behaviour.Behaviour):
    """Stands in for the Listening branch (diarization STT + web)"""

    def __init__(self):
        super().__init__("Listening")
        self.ticks = 0

    def update(self):
        self.ticks += 1
        return Status.SUCCESS


def speak_then_listen():
    mover = speaker_leaf(name="Mover", instance_id="furhat")
    opposer = speaker_leaf(name="Opposer", instance_id="nao")
    selector = py_trees.composites.Selector(name="Agent Selector", memory=True)
    selector.add_children([mover, opposer])
    listening = RecordingListener()
    root = py_trees.composites.Sequence(name="SpeakThenListen", memory=True)
    root.add_children([selector, listening])
    return root, mover, opposer, listening


def test_intervene_false_skips_speaking_and_reopens_the_microphone():
    writer("tts", result="I should not be said")
    writer("scene", nlp=1, agent="")
    writer("bot", agent="Opposer", speak=0, addressee="Sarah")
    root, mover, opposer, listening = speak_then_listen()

    root.tick_once()

    assert root.status == Status.SUCCESS
    assert mover.service_client_speaker.goals == []
    assert opposer.service_client_speaker.goals == []
    assert listening.ticks == 1  # the microphone is reopened in the same tick


def test_intervene_true_speaks_before_listening():
    writer("tts", result="Are you sure?")
    writer("scene", nlp=1, agent="")
    writer("bot", agent="Opposer", speak=1, addressee="Sarah")
    root, mover, opposer, listening = speak_then_listen()

    root.tick_once()
    assert listening.ticks == 0  # still speaking
    assert len(opposer.service_client_speaker.goals) == 1
    assert mover.service_client_speaker.goals == []

    opposer.service_client_speaker.state = GoalStatus.SUCCEEDED
    root.tick_once()
    assert listening.ticks == 1
    assert root.status == Status.SUCCESS
