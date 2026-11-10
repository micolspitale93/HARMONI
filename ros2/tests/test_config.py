import os

import pytest

from harmoni.services import available_backends
from harmoni.tree import load_spec, resolve_spec, services_used, validate
from harmoni_nodes.config import load_config, service_config, topic_for, tree_settings

CONFIGS = ["group_interaction.yaml", "group_interaction_het_inversed.yaml", "group_interaction_homog.yaml",
           "group_interaction_homog_inversed.yaml", "group_interaction_mock.yaml"]


@pytest.fixture(autouse=True)
def harmoni_root(repo, monkeypatch):
    monkeypatch.setenv("HARMONI_ROOT", repo)


@pytest.mark.parametrize("name", CONFIGS)
def test_shipped_configs_are_consistent(repo, name):
    config = load_config(os.path.join(repo, "ros2", "config", name))
    tree_file, variables, period, cast = tree_settings(config)
    assert os.path.exists(tree_file)
    spec = load_spec(tree_file)
    resolved, issues = resolve_spec(spec, variables, cast)
    assert [str(i) for i in issues + validate(resolved, resolved=True) if i.level == "error"] == []
    # every service called by the tree or by its cast is configured, with a known backend
    for service_id in services_used(spec, cast):
        backend, params, _ = service_config(config, service_id)
        assert backend in available_backends()
    # participants are defined once (YAML anchor)
    assert variables["participants"] == config["participants"]


@pytest.mark.parametrize("name, roles", [
    ("group_interaction.yaml", [("Mover", "Furhat"), ("Opposer", "NAO")]),
    ("group_interaction_het_inversed.yaml", [("Mover", "NAO"), ("Opposer", "Furhat")]),
    ("group_interaction_homog.yaml", [("Mover1", "Furhat"), ("Mover2", "NAO")]),
    ("group_interaction_homog_inversed.yaml", [("Mover1", "NAO"), ("Mover2", "Furhat")]),
])
def test_study_conditions(repo, name, roles):
    from harmoni.tree.cast import Cast

    config = load_config(os.path.join(repo, "ros2", "config", name))
    tree_file, variables, _, cast = tree_settings(config)
    resolved, _ = resolve_spec(load_spec(tree_file), variables, cast)
    agents = Cast.from_spec(resolved["cast"]).agents
    assert [(a.role, a.robot) for a in agents] == roles
    assert {a.name for a in agents} == {"Manny", "Sam"}
    speech = {a.robot: a.services["speech"] for a in agents}
    assert speech == {"Furhat": "speaker_furhat", "NAO": "speaker_nao"}
    homog = "homog" in name
    assert variables["script"].endswith("group_interaction_homog.json" if homog else "group_interaction.json")
    assert config["services"]["bot_default"]["assistant_id"] == (
        "asst_JvDM8TQEWPrSyk0fB38vuLkw" if homog else "asst_7iYWPs6E7obv7Lp5343RGuo7")


def test_service_config_and_subscriptions(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("services:\n  bot_mover:\n    backend: assistant\n    assistant_id: a\n"
                    "    subscribe: {thread_id: /harmoni/bot_default/thread_id}\n")
    backend, params, subscribe = service_config(load_config(str(path)), "bot_mover")
    assert backend == "assistant" and params == {"assistant_id": "a"}
    assert subscribe == {"thread_id": "/harmoni/bot_default/thread_id"}
    with pytest.raises(KeyError):
        service_config(load_config(str(path)), "nope")


def test_topic_for():
    assert topic_for("bot_default", "thread_id") == "/harmoni/bot_default/thread_id"


def test_tree_override_and_relative_paths(tmp_path, repo):
    path = tmp_path / "c.yaml"
    path.write_text("tree: {file: core/trees/group_interaction.json, period_s: 0.5}\n")
    tree_file, _, period, _ = tree_settings(load_config(str(path)))
    assert tree_file == os.path.join(repo, "core", "trees", "group_interaction.json") and period == 0.5
    assert tree_settings(load_config(str(path)), "/abs/tree.json")[0] == "/abs/tree.json"
