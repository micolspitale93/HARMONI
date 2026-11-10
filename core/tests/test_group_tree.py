"""The group interaction tree (trees/group_interaction.json) end to end, with mock services.

The same tree file is run with different casts: the study conditions (which robot plays which
role, homogeneous roles) and a setup with three robots and two humans.
"""

import json
import os
import time

from harmoni.services import create_backend
from harmoni.tree import BuildContext, ClientRegistry, LocalServiceClient, TreeRunner

SAYS = '{"intervene": true, "agent": "%s", "response": "%s", "addressee": "Micol"}'
SILENT = '{"intervene": false, "agent": "Mover", "response": "", "addressee": ""}'
SPEAKERS = ("speaker_furhat", "speaker_nao", "speaker_pepper")


def run_tree(trees_dir, bot_responses, max_scenes=6, extra=None, cast=None, max_ticks=500, **variables):
    services = {
        "stt_default": {"backend": "mock", "responses": ["Micol: one", "Jane: two", "Micol: three"]},
        "bot_default": {"backend": "mock", "responses": bot_responses},
    }
    for sid in SPEAKERS + ("led_furhat", "led_nao", "led_pepper"):
        services[sid] = {"backend": "mock"}
    services.update(extra or {})
    backends = {sid: create_backend(p["backend"], sid, {k: v for k, v in p.items() if k != "backend"})
                for sid, p in services.items()}
    clients = ClientRegistry({sid: LocalServiceClient(b) for sid, b in backends.items()})
    variables.setdefault("max_scenes", max_scenes)
    runner = TreeRunner(os.path.join(trees_dir, "group_interaction.json"), BuildContext(client_for=clients),
                        variables, period_s=0, cast=cast)
    state = runner.run(max_ticks=max_ticks, sleep=lambda s: time.sleep(0.001))
    clients.shutdown()
    return state, backends, runner


def said(backend):
    return [json.loads(data)["input"] for kind, data in backend.calls if kind == "DO"]


def conversation(runner):
    return runner.snapshot()["blackboard"]["/conversation"]


def test_full_interaction_finishes(trees_dir):
    state, b, runner = run_tree(trees_dir, [SAYS % ("Opposer", "Why?")])
    assert state == "finished"
    # scripted introductions: Manny (Mover, Furhat) then Sam (Opposer, NAO)
    assert "Manny" in said(b["speaker_furhat"])[0]
    assert "Sam" in said(b["speaker_nao"])[0]
    assert "Why?" in said(b["speaker_nao"])
    # the closing scene is said and the microphone is not reopened afterwards
    assert "wrap up" in said(b["speaker_furhat"])[-1]
    assert runner.snapshot()["blackboard"]["/scene/finished"] is True


def test_leds_of_every_agent_show_the_dialogue_state(trees_dir):
    _, b, _ = run_tree(trees_dir, [SILENT])
    for led in ("led_furhat", "led_nao"):
        colors = [data for kind, data in b[led].calls]
        assert colors[:2] == ["red", "green"] and set(colors) == {"red", "green"}


def test_conversation_log_records_humans_and_agents(trees_dir):
    _, _, runner = run_tree(trees_dir, [SAYS % ("Opposer", "Why?")])
    log = conversation(runner)
    agents = [(t["speaker"], t["role"]) for t in log if t["kind"] == "agent"]
    humans = [t["speaker"] for t in log if t["kind"] == "human"]
    assert ("Manny", "Mover") in agents and ("Sam", "Opposer") in agents
    assert {"Micol", "Jane"} <= set(humans)
    assert [t["n"] for t in log] == list(range(1, len(log) + 1))


def test_intervene_false_skips_speaking_and_reopens_the_microphone(trees_dir):
    _, b, _ = run_tree(trees_dir, [SILENT])
    spoken = sum(len(said(b[s])) for s in SPEAKERS)
    assert spoken == 3  # only the scripted lines: 2 introductions + closing
    stt = [c for c in b["stt_default"].calls if c[0] == "REQUEST"]
    llm = [c for c in b["bot_default"].calls if c[0] == "REQUEST"]
    assert len(llm) >= 2 and len(stt) >= len(llm)


def test_inversed_condition_is_a_cast_change(trees_dir):
    inversed = {"agents": {"Mover": {"services": {"speech": "speaker_nao", "led": "led_nao"}},
                           "Opposer": {"services": {"speech": "speaker_furhat", "led": "led_furhat"}}}}
    _, b, _ = run_tree(trees_dir, [SAYS % ("Opposer", "Why?")], cast=inversed)
    assert "Manny" in said(b["speaker_nao"])[0]       # the Mover is now the NAO
    assert "Why?" in said(b["speaker_furhat"])       # the Opposer is now the Furhat


def test_homogeneous_roles(trees_dir):
    homog = {"agents": [
        {"role": "Mover1", "name": "Manny", "services": {"speech": "speaker_furhat", "led": "led_furhat"}},
        {"role": "Mover2", "name": "Sam", "services": {"speech": "speaker_nao", "led": "led_nao"}}]}
    state, b, _ = run_tree(trees_dir, [SAYS % ("Mover2", "Let us vote")], cast=homog,
                           script="scripts/group_interaction_homog.json")
    assert state == "finished"
    assert "Let us vote" in said(b["speaker_nao"])


def test_three_robots_and_two_humans(trees_dir):
    cast = {"humans": ["Micol", "Jane"], "agents": [
        {"role": "Mover", "name": "Manny", "services": {"speech": "speaker_furhat", "led": "led_furhat"}},
        {"role": "Opposer", "name": "Sam", "services": {"speech": "speaker_nao", "led": "led_nao"}},
        {"role": "Moderator", "name": "Pepper", "services": {"speech": "speaker_pepper", "led": "led_pepper"}}]}
    state, b, runner = run_tree(trees_dir, [SAYS % ("Moderator", "Time check: 5 minutes left"),
                                            SAYS % ("Opposer", "Why?")], cast=cast)
    assert state == "finished"
    assert "Time check: 5 minutes left" in said(b["speaker_pepper"])
    assert "Why?" in said(b["speaker_nao"])
    assert [c[1] for c in b["led_pepper"].calls][:2] == ["red", "green"]
    # the 2-person session of the script is used, with both names
    assert "Micol and Jane" in said(b["speaker_furhat"])[0]
    assert runner.snapshot()["cast"]["humans"] == ["Micol", "Jane"]


def test_robot_failure_does_not_stop_the_interaction(trees_dir):
    state, b, _ = run_tree(trees_dir, [SAYS % ("Opposer", "Why?")],
                           extra={"speaker_nao": {"backend": "mock", "ok": False}})
    assert state == "finished"
    assert "Why?" not in said(b["speaker_furhat"])


def test_slow_llm_times_out_and_the_interaction_goes_on(trees_dir):
    state, b, _ = run_tree(trees_dir, [], extra={"bot_default": {"backend": "mock", "delay_s": 5,
                                                                 "responses": [SAYS % ("Mover", "too late")]}},
                           llm_timeout_s=0.05, max_ticks=3000)
    assert state == "finished"
    assert "too late" not in said(b["speaker_furhat"])
