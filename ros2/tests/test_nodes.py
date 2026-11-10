"""ROS2 nodes with a fake rclpy: parameters, topics, action results, goal tracking"""

import json
import os
import types

import pytest

from harmoni.constants import ActionType
from harmoni.tree.clients import CallStatus, LocalServiceClient
from harmoni.services import create_backend
from ros_fakes import FakeActionClient, FakeClock, FakeFuture, FakeNode

MOCK_CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config",
                           "group_interaction_mock.yaml")


@pytest.fixture(autouse=True)
def harmoni_root(repo, monkeypatch):
    monkeypatch.setenv("HARMONI_ROOT", repo)


# ------------------------------------------------------------------ service node
class GoalHandle:
    def __init__(self, action_type, data, cancel=False):
        self.request = types.SimpleNamespace(action_type=int(action_type), optional_data=data)
        self.is_cancel_requested = cancel
        self.feedback, self.outcome = [], None

    def publish_feedback(self, feedback):
        self.feedback.append(feedback.state)

    def succeed(self):
        self.outcome = "succeeded"

    def canceled(self):
        self.outcome = "canceled"


def service_node(service_id, config=MOCK_CONFIG):
    from harmoni_nodes.service_node import HarmoniServiceNode

    FakeNode.parameters = {"service_id": service_id, "config": config}
    return HarmoniServiceNode()


def test_service_node_serves_the_backend_as_an_action():
    node = service_node("stt_default")
    node.backend.delay_s = 0
    assert node.action_server.name == "stt_default"
    goal = GoalHandle(ActionType.REQUEST, "")
    result = node._execute(goal)
    assert goal.outcome == "succeeded" and goal.feedback == [2]
    assert result.do_action is True and result.message == "Micol: Hi, I am Micol, nice to meet you"
    assert node.publishers["/harmoni/stt_default/result"].published == [result.message]


def test_service_node_reports_failures_as_results():
    node = service_node("speaker_furhat")
    result = node._execute(GoalHandle(ActionType.REQUEST, ""))  # furhat does not support REQUEST
    assert result.do_action is False and "does not support" in result.message
    assert node.publishers["/harmoni/speaker_furhat/result"].published == []


def test_service_node_cancel():
    node = service_node("bot_default")
    cancelled = []
    node.backend.cancel = lambda: cancelled.append(True)
    assert node._cancel(None) == "accept" and cancelled
    goal = GoalHandle(ActionType.DO, "x", cancel=True)
    node.backend.delay_s = 0
    node._execute(goal)
    assert goal.outcome == "canceled"


def test_side_outputs_and_inputs(tmp_path):
    config = tmp_path / "c.yaml"
    config.write_text("services:\n  bot_mover:\n    backend: mock\n"
                      "    subscribe: {thread_id: /harmoni/bot_default/thread_id}\n")
    node = service_node("bot_mover", str(config))
    received = []
    node.backend.on_input = lambda channel, message: received.append((channel, message))
    node.subscriptions["/harmoni/bot_default/thread_id"](types.SimpleNamespace(data="thread_1"))
    assert received == [("thread_id", "thread_1")]
    node._emit("thread_id", "thread_2")
    publisher = node.publishers["/harmoni/bot_mover/thread_id"]
    assert publisher.published == ["thread_2"] and publisher.qos["durability"] == "transient_local"


def test_service_node_survives_backend_setup_errors(tmp_path):
    config = tmp_path / "c.yaml"
    config.write_text("services:\n  speaker_furhat:\n    backend: furhat\n    robot_ip: 1.2.3.4\n")
    node = service_node("speaker_furhat", str(config))  # furhat_remote_api is not installed here
    assert any(level == "error" and "setup" in msg for level, msg in node.logger.messages)


def test_missing_parameters():
    from harmoni_nodes.service_node import HarmoniServiceNode

    with pytest.raises(ValueError):
        HarmoniServiceNode()


# ------------------------------------------------------------------ ROS client
def make_call(action=ActionType.REQUEST, data="hi"):
    from harmoni_nodes.ros_client import RosServiceClient

    client = RosServiceClient(FakeNode("tree"), "bot_default")
    call = client.send(action, data)
    goal, future = client.action_client.sent[-1]
    return client, call, goal, future


class FakeGoalHandle:
    def __init__(self, accepted=True):
        self.accepted = accepted
        self.result_future = FakeFuture()
        self.cancelled = False

    def get_result_async(self):
        return self.result_future

    def cancel_goal_async(self):
        self.cancelled = True


def result(status=4, ok=True, message="answer"):
    return types.SimpleNamespace(status=status, result=types.SimpleNamespace(do_action=ok, message=message))


def test_ros_call_success():
    _, call, goal, future = make_call()
    assert (goal.action_type, goal.optional_data) == (3, "hi")
    handle = FakeGoalHandle()
    future.set_result(handle)
    assert call.status == CallStatus.RUNNING
    handle.result_future.set_result(result())
    assert (call.status, call.ok, call.message) == (CallStatus.SUCCEEDED, True, "answer")


def test_ros_call_service_answers_failure():
    _, call, _, future = make_call()
    handle = FakeGoalHandle()
    future.set_result(handle)
    handle.result_future.set_result(result(ok=False, message="no"))
    assert call.status == CallStatus.SUCCEEDED and call.ok is False


def test_ros_call_rejected_and_aborted():
    _, call, _, future = make_call()
    future.set_result(FakeGoalHandle(accepted=False))
    assert call.status == CallStatus.FAILED
    _, call, _, future = make_call()
    handle = FakeGoalHandle()
    future.set_result(handle)
    handle.result_future.set_result(result(status=6))
    assert call.status == CallStatus.FAILED and "status 6" in call.message


def test_ros_call_cancel_before_and_after_acceptance():
    _, call, _, future = make_call()
    call.cancel()
    handle = FakeGoalHandle()
    future.set_result(handle)
    assert call.status == CallStatus.CANCELLED and handle.cancelled
    _, call, _, future = make_call()
    handle = FakeGoalHandle()
    future.set_result(handle)
    call.cancel()
    handle.result_future.set_result(result())
    assert call.status == CallStatus.CANCELLED and handle.cancelled


def test_ros_client_service_not_available():
    from harmoni_nodes.ros_client import RosServiceClient

    client = RosServiceClient(FakeNode("tree"), "stt_default")
    client.action_client.ready = False
    call = client.send("REQUEST", "")
    assert call.status == CallStatus.FAILED and "not available" in call.message


# ------------------------------------------------------------------ tree node
def tree_node(monkeypatch, local=True, **params):
    import harmoni_nodes.tree_node as tree_node_module

    if local:  # serve the mock services in-process instead of through ROS
        import yaml

        services = yaml.safe_load(open(MOCK_CONFIG))["services"]

        def local_client(node, service_id):
            params = dict(services[service_id], delay_s=0)
            client = LocalServiceClient(create_backend(params.pop("backend"), service_id, params))
            client.is_ready = lambda: True
            return client

        monkeypatch.setattr(tree_node_module, "RosServiceClient", local_client)
    FakeNode.parameters = dict({"config": MOCK_CONFIG}, **params)
    return tree_node_module.TreeRunnerNode()


def test_tree_node_runs_the_tree_and_publishes_snapshots(monkeypatch):
    import time

    node = tree_node(monkeypatch)
    assert set(node.required) == {"bot_default", "stt_default", "speaker_furhat", "speaker_nao"}
    on_timer = node.timers[0]
    errors = []

    def executor_thread():  # ROS 2 timers run in executor threads, not in the main thread
        try:
            for _ in range(2000):
                on_timer()
                if node.runner.state == "finished":
                    break
                time.sleep(0.001)
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    import threading

    thread = threading.Thread(target=executor_thread)
    thread.start()
    thread.join()
    assert errors == [] and node.runner.state == "finished"
    status = node.publishers["/harmoni/tree/status"].published
    snapshot = json.loads(status[-1])
    assert snapshot["state"] == "finished" and snapshot["tree"] == "GroupInteraction"
    assert node.publishers["/harmoni/tree/status"].qos["durability"] == "transient_local"


def test_tree_node_commands(monkeypatch):
    node = tree_node(monkeypatch)
    node.timers[0]()
    node.subscriptions["/harmoni/tree/command"](types.SimpleNamespace(data="pause"))
    node.timers[0]()
    assert node.runner.state == "paused"
    node.subscriptions["/harmoni/tree/command"](types.SimpleNamespace(data="dance"))
    assert any(level == "warning" for level, _ in node.logger.messages)


def test_tree_node_waits_for_services_then_starts_anyway(monkeypatch):
    node = tree_node(monkeypatch, local=False, startup_timeout_s=10.0)
    for client in FakeActionClient.instances:
        client.ready = False
    node.timers[0]()
    assert not node._started
    FakeClock.now_ns = int(11e9)
    node.timers[0]()
    assert node._started
    assert any(level == "warning" and "starting without services" in msg for level, msg in node.logger.messages)


# ------------------------------------------------------------------ monitor
def test_monitor_render():
    from harmoni_nodes.monitor import render

    text = render({"state": "running", "tree": "T", "tick": 3, "error": "",
                   "root": {"name": "root", "status": "RUNNING", "message": "",
                            "children": [{"name": "Ask", "status": "RUNNING", "message": "REQUEST sent"}]},
                   "blackboard": {"/bot/agent": "Mover"}})
    assert "* Ask  (REQUEST sent)" in text and "/bot/agent = 'Mover'" in text


def test_tree_node_reports_a_broken_tree_instead_of_crashing(monkeypatch, tmp_path):
    tree = tmp_path / "broken.json"
    tree.write_text('{"harmoni_tree": 1, "name": "Broken", "root": {"type": "NoSuchNode", "name": "x"}}')
    config = tmp_path / "c.yaml"
    config.write_text(f"tree: {{file: {tree}}}\nservices: {{}}\n")
    node = tree_node(monkeypatch, config=str(config))
    node.timers[0]()  # must not raise
    snapshot = json.loads(node.publishers["/harmoni/tree/status"].published[-1])
    assert snapshot["state"] == "error" and "NoSuchNode" in snapshot["error"]
    assert any(level == "error" and "NoSuchNode" in msg for level, msg in node.logger.messages)
    # after fixing the file, `reload` starts it
    tree.write_text('{"harmoni_tree": 1, "name": "Fixed", "root": {"type": "Wait", "name": "w", "params": {"seconds": 0}}}')
    node.subscriptions["/harmoni/tree/command"](types.SimpleNamespace(data="reload"))
    node.timers[0]()
    assert json.loads(node.publishers["/harmoni/tree/status"].published[-1])["state"] in ("running", "finished")
