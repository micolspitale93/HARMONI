"""Cast (any number of humans and agents), role-based leaves, conversation log, configurations"""

import json

import py_trees
import pytest

from harmoni.config import load_config
from harmoni.leaves.multiparty import AgentSpeak, AgentsAction, LogUtterance, split_speaker
from harmoni.tree import BuildContext, TreeRunner, services_used, validate
from harmoni.tree.cast import Cast, merge_cast, validate_cast
from tests.conftest import bb_get, bb_set
from tests.test_leaves import FakeClient, tick

Status = py_trees.common.Status

CAST = {
    "humans": "Sarah, Jane, Alex",
    "agents": [
        {"role": "Mover", "name": "Manny", "robot": "Furhat", "services": {"speech": "speaker_furhat", "led": "led_furhat"}},
        {"role": "Opposer", "name": "Sam", "robot": "NAO", "services": {"speech": "speaker_nao", "led": "led_nao"}},
        {"role": "Moderator", "name": "Pepper", "robot": "Pepper", "services": {"speech": "speaker_pepper"}},
    ],
}


class Clients:
    """One FakeClient per service id"""

    def __init__(self):
        self.by_service = {}

    def __call__(self, service):
        return self.by_service.setdefault(service, FakeClient())


def context(clock, cast=CAST):
    clients = Clients()
    bb_set(conversation=[])
    return BuildContext(client_for=clients, clock=clock, cast=Cast.from_spec(cast)), clients


# ------------------------------------------------------------------ cast
def test_cast_parsing():
    cast = Cast.from_spec(CAST)
    assert cast.humans == ["Sarah", "Jane", "Alex"]
    assert cast.roles == ["Mover", "Opposer", "Moderator"]
    assert cast.agent("opposer").name == "Sam" and cast.agent("Pepper").role == "Moderator"
    assert cast.services("led") == ["led_furhat", "led_nao"]
    assert cast.channels() == ["led", "speech"]
    assert Cast.from_spec({"humans": [{"name": "Ann"}, "Bob", " "]}).humans == ["Ann", "Bob"]


def test_merge_cast_by_role_and_replace():
    swapped = merge_cast(CAST, {"agents": {"Mover": {"robot": "NAO", "services": {"speech": "speaker_nao"}}}})
    mover = swapped["agents"][0]
    assert mover["name"] == "Manny" and mover["robot"] == "NAO"
    assert mover["services"] == {"speech": "speaker_nao", "led": "led_furhat"}
    assert merge_cast(CAST, {"humans": ["Ann"]})["humans"] == ["Ann"]
    assert merge_cast(CAST, {"agents": [{"role": "Solo"}]})["agents"] == [{"role": "Solo"}]
    assert merge_cast(CAST, {"agents": {"New": {"name": "Nova"}}})["agents"][-1] == {"role": "New", "name": "Nova"}


def test_validate_cast():
    assert validate_cast(CAST) == []
    issues = validate_cast({"agents": [{"role": "A"}, {"role": "a"}, {"name": "no role"}]})
    assert {m for _, _, m in issues} == {"duplicate role 'a'", "an agent needs a role"}


# ------------------------------------------------------------------ AgentSpeak
def test_agent_speak_routes_to_the_chosen_role(clock):
    ctx, clients = context(clock)
    bb_set(**{"bot/agent": "Moderator", "bot/message": 'Say "hi"', "bot/addressee": "Jane", "bot/speak": True})
    leaf = AgentSpeak("speak", ctx)
    assert tick(leaf) == Status.RUNNING
    client = clients.by_service["speaker_pepper"]
    action, data = client.sent[0]
    assert action == "DO" and json.loads(data) == {"input": 'Say "hi"', "addressee": "Jane", "agent": "Moderator", "name": "Pepper"}
    client.calls[0].finish(True)
    assert tick(leaf) == Status.SUCCESS
    assert bb_get("conversation")[-1] == {**bb_get("conversation")[-1], "kind": "agent", "speaker": "Pepper",
                                          "role": "Moderator", "to": "Jane", "text": 'Say "hi"'}


def test_agent_speak_silence_and_nothing_to_say(clock):
    ctx, clients = context(clock)
    bb_set(**{"bot/agent": "Mover", "bot/message": "hello", "bot/speak": False})
    assert tick(AgentSpeak("speak", ctx)) == Status.SUCCESS
    bb_set(**{"bot/speak": True, "bot/message": "  "})
    assert tick(AgentSpeak("speak", ctx)) == Status.SUCCESS
    assert clients.by_service == {} and bb_get("conversation") == []


@pytest.mark.parametrize("agent, default_role, service", [
    ("null", None, "speaker_furhat"),          # unknown: the first agent
    ("Opposer", None, "speaker_nao"),
    ("nobody", "Opposer", "speaker_nao"),      # unknown: the default role
    ("Sam", None, "speaker_nao"),              # by name
])
def test_agent_speak_fallbacks(clock, agent, default_role, service):
    ctx, clients = context(clock)
    bb_set(**{"bot/agent": agent, "bot/message": "hello", "bot/speak": True})
    tick(AgentSpeak("speak", ctx, default_role=default_role))
    assert list(clients.by_service) == [service]


def test_agent_speak_without_the_channel_skips(clock):
    ctx, clients = context(clock)
    bb_set(**{"bot/agent": "Moderator", "bot/message": "hello"})
    leaf = AgentSpeak("speak", ctx, channel="gesture")
    assert tick(leaf) == Status.SUCCESS and "no agent" in leaf.feedback_message


@pytest.mark.parametrize("policy, expected", [("success", Status.SUCCESS), ("failure", Status.FAILURE)])
def test_agent_speak_robot_failure_policy(clock, policy, expected):
    ctx, clients = context(clock)
    bb_set(**{"bot/agent": "Mover", "bot/message": "hello"})
    leaf = AgentSpeak("speak", ctx, on_failure=policy)
    tick(leaf)
    clients.by_service["speaker_furhat"].calls[0].fail("robot unreachable")
    assert tick(leaf) == expected


def test_agent_speak_timeout_cancels(clock):
    ctx, clients = context(clock)
    bb_set(**{"bot/agent": "Mover", "bot/message": "hello"})
    leaf = AgentSpeak("speak", ctx, timeout_s=5)
    tick(leaf)
    clock.advance(6)
    assert tick(leaf) == Status.SUCCESS
    assert clients.by_service["speaker_furhat"].calls[0].cancelled


# ------------------------------------------------------------------ AgentsAction
def test_agents_action_reaches_every_agent_with_the_channel(clock):
    ctx, clients = context(clock)
    leaf = AgentsAction("leds", ctx, channel="led", input_value="red")
    assert tick(leaf) == Status.RUNNING
    assert set(clients.by_service) == {"led_furhat", "led_nao"}  # Pepper has no led
    clients.by_service["led_furhat"].calls[0].finish(True)
    assert tick(leaf) == Status.RUNNING
    clients.by_service["led_nao"].calls[0].finish(True)
    assert tick(leaf) == Status.SUCCESS


def test_agents_action_roles_and_no_wait(clock):
    ctx, clients = context(clock)
    leaf = AgentsAction("leds", ctx, channel="led", input_value={"color": "green"}, roles=["Opposer"], wait=False)
    assert tick(leaf) == Status.SUCCESS  # fire and forget
    assert list(clients.by_service) == ["led_nao"]
    assert json.loads(clients.by_service["led_nao"].sent[0][1]) == {"color": "green"}


def test_agents_action_failure_policy(clock):
    ctx, clients = context(clock)
    leaf = AgentsAction("leds", ctx, channel="led", input_value="red", on_failure="failure")
    tick(leaf)
    clients.by_service["led_furhat"].calls[0].finish(True)
    clients.by_service["led_nao"].calls[0].fail("no bridge")
    assert tick(leaf) == Status.FAILURE and "led_nao" in leaf.feedback_message


# ------------------------------------------------------------------ conversation log
@pytest.mark.parametrize("text, expected", [("Sarah: hello: there", ("Sarah", "hello: there")),
                                            ("No one is talking.", (None, "No one is talking."))])
def test_split_speaker(text, expected):
    assert split_speaker(text) == expected


def test_log_utterance(clock):
    ctx, _ = context(clock)
    bb_set(**{"stt/result": "Jane: I agree"})
    tick(LogUtterance("log", ctx))
    bb_set(**{"stt/result": "No one is talking."})
    tick(LogUtterance("log", ctx))
    bb_set(**{"stt/result": ""})
    tick(LogUtterance("log", ctx))
    log = bb_get("conversation")
    assert [(t["kind"], t["speaker"], t["text"]) for t in log] == [("human", "Jane", "I agree"), ("event", "", "No one is talking.")]


# ------------------------------------------------------------------ tree format
def test_cast_in_tree_files(trees_dir):
    spec = {"harmoni_tree": 1, "name": "T", "variables": {"people": "A, B"},
            "cast": {"humans": "${people}", "agents": [{"role": "R", "services": {"speech": "speaker_x"}}]},
            "root": {"type": "AgentSpeak", "name": "s"}}
    assert [i for i in validate(spec) if i.level == "error"] == []
    assert "speaker_x" in services_used(spec)
    bad = dict(spec, cast={"agents": [{"role": "R"}, {"role": "R"}]})
    assert any("duplicate role" in i.message for i in validate(bad))


def test_runner_cast_override_and_blackboard():
    spec = {"harmoni_tree": 1, "name": "T", "cast": {"humans": ["A"], "agents": [{"role": "R"}]},
            "root": {"type": "Wait", "name": "w", "params": {"seconds": 0}}}
    snapshot = TreeRunner(spec, cast={"humans": ["X", "Y"]}).step()
    assert snapshot["cast"]["humans"] == ["X", "Y"]
    assert snapshot["blackboard"]["/cast/humans"] == ["X", "Y"] and snapshot["blackboard"]["/cast/roles"] == ["R"]
    assert snapshot["blackboard"]["/conversation"] == []


# ------------------------------------------------------------------ configurations
def test_config_extends(tmp_path):
    (tmp_path / "base.yaml").write_text(
        "participants: &p 'A, B'\n"
        "tree: {file: t.json, variables: {participants: *p, x: 1}}\n"
        "services:\n  s1: {backend: mock, responses: [a], delay_s: 1}\n  s2: {backend: mock}\n")
    (tmp_path / "cond.yaml").write_text(
        "extends: base.yaml\n"
        "tree: {variables: {x: 2}, cast: {agents: {Mover: {robot: NAO}}}}\n"
        "services:\n  s1: {delay_s: 3}\n  s2: {backend: furhat, mockup: true}\n")
    (tmp_path / "cond2.yaml").write_text("extends: cond.yaml\ntree: {cast: {agents: {Opposer: {robot: Furhat}}}}\n")
    config = load_config(str(tmp_path / "cond.yaml"))
    assert config["tree"]["variables"] == {"participants": "A, B", "x": 2}
    assert config["services"]["s1"] == {"backend": "mock", "responses": ["a"], "delay_s": 3}  # merged
    assert config["services"]["s2"] == {"backend": "furhat", "mockup": True}                  # replaced
    assert config["tree"]["cast"] == {"agents": {"Mover": {"robot": "NAO"}}}  # still an override
    nested = load_config(str(tmp_path / "cond2.yaml"))
    agents = merge_cast({"agents": [{"role": "Mover"}, {"role": "Opposer"}]}, nested["tree"]["cast"])["agents"]
    assert agents == [{"role": "Mover", "robot": "NAO"}, {"role": "Opposer", "robot": "Furhat"}]
