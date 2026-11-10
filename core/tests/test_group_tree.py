"""The group interaction tree (trees/group_interaction.json) end to end, with mock services"""

import json
import os

import pytest

from harmoni.services import create_backend
from harmoni.tree import BuildContext, ClientRegistry, LocalServiceClient, TreeRunner

ORCHESTRATOR_SAYS = '{"intervene": true, "agent": "%s", "response": "%s", "addressee": "Micol"}'
SILENT = '{"intervene": false, "agent": "Mover", "response": "", "addressee": ""}'


def run_tree(trees_dir, bot_responses, max_scenes=6, extra=None, max_ticks=500, **variables):
    services = {
        "stt_default": {"backend": "mock", "responses": ["Micol: one", "Micol: two", "Micol: three"]},
        "bot_default": {"backend": "mock", "responses": bot_responses},
        "speaker_furhat": {"backend": "mock"},
        "speaker_nao": {"backend": "mock"},
    }
    services.update(extra or {})
    backends = {sid: create_backend(p.pop("backend"), sid, p) for sid, p in
                ((sid, dict(p)) for sid, p in services.items())}
    clients = ClientRegistry({sid: LocalServiceClient(b) for sid, b in backends.items()})
    variables.setdefault("max_scenes", max_scenes)
    runner = TreeRunner(os.path.join(trees_dir, "group_interaction.json"), BuildContext(client_for=clients),
                        variables, period_s=0)
    state = runner.run(max_ticks=max_ticks, sleep=lambda s: __import__("time").sleep(0.001))
    clients.shutdown()
    return state, backends, runner


def said(backend):
    return [json.loads(data)["input"] for kind, data in backend.calls if kind == "DO"]


def test_full_interaction_finishes(trees_dir):
    state, b, runner = run_tree(trees_dir, [ORCHESTRATOR_SAYS % ("Opposer", "Why?")])
    assert state == "finished"
    # scripted introductions: Manny (Furhat) then Andrea (NAO)
    assert "Manny" in said(b["speaker_furhat"])[0]
    assert "Andrea" in said(b["speaker_nao"])[0]
    # LLM turns: the Opposer is the NAO
    assert "Why?" in said(b["speaker_nao"])
    # the closing scene is said and the microphone is not reopened afterwards
    assert "See you next time" in said(b["speaker_furhat"])[-1]
    assert runner.snapshot()["blackboard"]["/scene/finished"] is True


def test_intervene_false_skips_speaking_and_reopens_the_microphone(trees_dir):
    state, b, _ = run_tree(trees_dir, [SILENT])
    furhat, nao = said(b["speaker_furhat"]), said(b["speaker_nao"])
    # only the scripted lines (2 introductions + closing) are said: every LLM turn was silent
    assert len(furhat) + len(nao) == 3
    stt_requests = [c for c in b["stt_default"].calls if c[0] == "REQUEST"]
    llm_requests = [c for c in b["bot_default"].calls if c[0] == "REQUEST"]
    assert len(llm_requests) >= 2
    assert len(stt_requests) >= len(llm_requests)  # after every silent decision we listen again


def test_mover_is_the_default_speaker(trees_dir):
    _, b, _ = run_tree(trees_dir, [ORCHESTRATOR_SAYS % ("Mover", "Let us start")])
    assert "Let us start" in said(b["speaker_furhat"])
    assert "Let us start" not in said(b["speaker_nao"])


def test_robot_failure_does_not_stop_the_interaction(trees_dir):
    state, b, _ = run_tree(trees_dir, [ORCHESTRATOR_SAYS % ("Opposer", "Why?")],
                           extra={"speaker_nao": {"backend": "mock", "ok": False}})
    assert state == "finished"
    assert "Why?" not in said(b["speaker_furhat"])  # the Mover does not say the Opposer line


def test_slow_llm_times_out_and_the_interaction_goes_on(trees_dir):
    state, b, _ = run_tree(trees_dir, [ORCHESTRATOR_SAYS % ("Mover", "too late")],
                           extra={"bot_default": {"backend": "mock", "delay_s": 5,
                                                  "responses": [ORCHESTRATOR_SAYS % ("Mover", "too late")]}},
                           llm_timeout_s=0.05, max_ticks=3000)
    assert state == "finished"
    assert "too late" not in said(b["speaker_furhat"])
