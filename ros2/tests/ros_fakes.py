"""Fakes of rclpy and of the generated ROS2 messages, to test the HARMONI ROS2 nodes without ROS.

These tests check the wiring between ROS2 and the core (parameters, topics, action results,
goal tracking). The real middleware is exercised in the container (./harmoni.sh ros2 run group-mock).
"""

import os
import sys
import types


HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "core"))
sys.path.insert(0, os.path.join(REPO, "ros2", "src", "harmoni_nodes"))
sys.path.insert(0, os.path.join(REPO, "ros2", "nao_bridge"))


def _module(name, **attrs):
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    sys.modules[name] = module
    return module


class Msg:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class String(Msg):
    def __init__(self, data=""):
        self.data = data


class FakePublisher:
    def __init__(self, topic, qos):
        self.topic, self.qos, self.published = topic, qos, []

    def publish(self, msg):
        self.published.append(msg.data)


class FakeTime:
    def __init__(self, ns):
        self.nanoseconds = ns

    def __sub__(self, other):
        return FakeTime(self.nanoseconds - other.nanoseconds)


class FakeClock:
    now_ns = 0

    def now(self):
        return FakeTime(FakeClock.now_ns)


class FakeLogger:
    def __init__(self):
        self.messages = []

    def _log(self, level, msg):
        self.messages.append((level, msg))

    def debug(self, msg):
        self._log("debug", msg)

    def info(self, msg):
        self._log("info", msg)

    def warning(self, msg):
        self._log("warning", msg)

    def error(self, msg):
        self._log("error", msg)


class FakeNode:
    parameters = {}

    def __init__(self, name):
        self.name = name
        self.publishers, self.subscriptions, self.timers = {}, {}, []
        self.logger = FakeLogger()
        self.clock = FakeClock()

    def declare_parameter(self, name, default):
        return types.SimpleNamespace(value=FakeNode.parameters.get(name, default))

    def create_publisher(self, msg_type, topic, qos):
        self.publishers[topic] = FakePublisher(topic, qos)
        return self.publishers[topic]

    def create_subscription(self, msg_type, topic, callback, qos):
        self.subscriptions[topic] = callback

    def create_timer(self, period, callback, callback_group=None):
        self.timers.append(callback)

    def get_logger(self):
        return self.logger

    def get_clock(self):
        return self.clock

    def destroy_node(self):
        pass


class FakeActionServer:
    def __init__(self, node, action_type, name, execute_callback, goal_callback, cancel_callback, callback_group):
        self.name, self.execute, self.cancel = name, execute_callback, cancel_callback
        node.action_server = self


class FakeActionClient:
    instances = []

    def __init__(self, node, action_type, name, callback_group=None):
        self.name, self.ready, self.sent = name, True, []
        FakeActionClient.instances.append(self)

    def server_is_ready(self):
        return self.ready

    def send_goal_async(self, goal):
        future = FakeFuture()
        self.sent.append((goal, future))
        return future


class FakeFuture:
    def __init__(self):
        self.callbacks, self._result, self._exception = [], None, None

    def add_done_callback(self, callback):
        self.callbacks.append(callback)

    def set_result(self, result):
        self._result = result
        for callback in self.callbacks:
            callback(self)

    def result(self):
        if self._exception:
            raise self._exception
        return self._result


QoS = types.SimpleNamespace(TRANSIENT_LOCAL="transient_local", RELIABLE="reliable")

_module("rclpy", init=lambda args=None: None, ok=lambda: False, shutdown=lambda: None, spin=lambda node: None)
_module("rclpy.node", Node=FakeNode)
_module("rclpy.action", ActionServer=FakeActionServer, ActionClient=FakeActionClient,
        CancelResponse=types.SimpleNamespace(ACCEPT="accept"), GoalResponse=types.SimpleNamespace(ACCEPT="accept"))
_module("rclpy.callback_groups", ReentrantCallbackGroup=lambda: None, MutuallyExclusiveCallbackGroup=lambda: None)
_module("rclpy.executors", MultiThreadedExecutor=lambda: None)
_module("rclpy.qos", QoSProfile=lambda **kw: kw, DurabilityPolicy=QoS, ReliabilityPolicy=QoS)
_module("std_msgs")
_module("std_msgs.msg", String=String)
_module("action_msgs")
_module("action_msgs.msg", GoalStatus=types.SimpleNamespace(STATUS_SUCCEEDED=4, STATUS_CANCELED=5, STATUS_ABORTED=6))
_module("harmoni_interfaces")
_module("harmoni_interfaces.action", Harmoni=types.SimpleNamespace(
    Goal=type("Goal", (Msg,), {}), Result=type("Result", (Msg,), {}), Feedback=type("Feedback", (Msg,), {})))


