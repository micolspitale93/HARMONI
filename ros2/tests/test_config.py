import os

import pytest

from harmoni.services import available_backends
from harmoni.tree import load_spec, services_used, validate
from harmoni_nodes.config import load_config, service_config, topic_for, tree_settings

CONFIGS = ["group_interaction.yaml", "group_interaction_mock.yaml"]


@pytest.fixture(autouse=True)
def harmoni_root(repo, monkeypatch):
    monkeypatch.setenv("HARMONI_ROOT", repo)


@pytest.mark.parametrize("name", CONFIGS)
def test_shipped_configs_are_consistent(repo, name):
    config = load_config(os.path.join(repo, "ros2", "config", name))
    tree_file, variables, period = tree_settings(config)
    assert os.path.exists(tree_file)
    spec = load_spec(tree_file)
    assert [i for i in validate(spec) if i.level == "error"] == []
    # every service called by the tree is configured, with a known backend
    for service_id in services_used(spec):
        backend, params, _ = service_config(config, service_id)
        assert backend in available_backends()
    # participants are defined once (YAML anchor)
    assert variables["user_names"] == config["participants"]


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
    tree_file, _, period = tree_settings(load_config(str(path)))
    assert tree_file == os.path.join(repo, "core", "trees", "group_interaction.json") and period == 0.5
    assert tree_settings(load_config(str(path)), "/abs/tree.json")[0] == "/abs/tree.json"
