"""TreeRunner: the UI never sits in the control loop"""

import json

import py_trees
import pytest

from harmoni.tree import BuildContext, TreeRunner, TreeSpecError
from harmoni.tree.registry import register_leaf


@register_leaf("TestBoom", doc="raises at every tick")
class Boom(py_trees.behaviour.Behaviour):
    def __init__(self, name, context=None):
        super().__init__(name)

    def update(self):
        raise RuntimeError("leaf crashed")


def counter_tree(stop_at=None):
    children = [{"type": "SetValue", "name": "mark", "params": {"key": "t/done", "value": True}}]
    spec = {"harmoni_tree": 1, "name": "Counter", "root": {"type": "Sequence", "name": "root", "children": children}}
    if stop_at:
        spec["stop_when"] = stop_at
    return spec


def test_snapshot_is_json_and_describes_the_tree():
    runner = TreeRunner(counter_tree())
    snapshot = runner.step()
    json.dumps(snapshot)
    assert snapshot["state"] == "running"
    assert snapshot["root"]["children"][0] == {"name": "mark", "type": "SetValue", "status": "SUCCESS", "message": ""}
    assert snapshot["blackboard"]["/t/done"] is True


def test_stop_when_finishes():
    runner = TreeRunner(counter_tree(stop_at="t/done"))
    assert runner.run(max_ticks=10, sleep=lambda s: None) == "finished"


def test_commands_are_applied_between_ticks():
    runner = TreeRunner(counter_tree())
    runner.step()
    runner.command("pause")
    assert runner.step()["state"] == "paused"
    tick = runner.tree.count
    runner.step()
    assert runner.tree.count == tick  # no tick while paused
    runner.command("resume")
    assert runner.step()["state"] == "running"
    runner.command("stop")
    assert runner.step()["state"] == "stopped"


def test_unknown_command():
    with pytest.raises(ValueError):
        TreeRunner(counter_tree()).command("explode")


def test_reload_picks_up_edits_and_survives_invalid_edits(tmp_path):
    path = tmp_path / "tree.json"
    path.write_text(json.dumps(counter_tree()))
    runner = TreeRunner(str(path))
    runner.step()
    edited = counter_tree()
    edited["root"]["children"][0]["params"]["value"] = "edited"
    path.write_text(json.dumps(edited))
    runner.command("reload")
    assert runner.step()["blackboard"]["/t/done"] == "edited"
    path.write_text('{"harmoni_tree": 1, "root": {"type": "Nope"}}')
    runner.command("reload")
    snapshot = runner.step()
    assert snapshot["state"] == "error" and "Nope" in snapshot["error"]


def test_invalid_tree_raises_at_load():
    with pytest.raises(TreeSpecError):
        TreeRunner({"harmoni_tree": 1, "root": {"type": "Nope"}}).load()


def test_crashing_leaf_puts_the_runner_in_error_without_raising():
    runner = TreeRunner({"harmoni_tree": 1, "name": "B", "root": {"type": "TestBoom", "name": "boom"}})
    snapshot = runner.step()
    assert snapshot["state"] == "error" and "leaf crashed" in snapshot["error"]


def test_failing_observer_is_ignored():
    runner = TreeRunner(counter_tree())
    seen = []

    def bad(snapshot):
        raise RuntimeError("UI crashed")

    runner.observers += [bad, seen.append]
    runner.step()
    assert len(seen) == 1 and runner.state == "running"


def test_load_and_run_from_a_worker_thread():
    """ROS 2 timers and Studio load trees outside the main thread"""
    import threading

    result = {}

    def worker():
        try:
            result["state"] = TreeRunner(counter_tree(stop_at="t/done")).run(max_ticks=5, sleep=lambda s: None)
        except Exception as e:  # noqa: BLE001
            result["error"] = repr(e)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert result == {"state": "finished"}
