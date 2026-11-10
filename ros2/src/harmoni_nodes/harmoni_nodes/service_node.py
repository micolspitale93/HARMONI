"""Generic HARMONI service node: serves any core service backend as a ROS2 action.

    ros2 run harmoni_nodes harmoni_service --ros-args \\
        -p service_id:=bot_default -p config:=/root/HARMONI/ros2/config/group_interaction.yaml

- action server ``/<service_id>`` (harmoni_interfaces/action/Harmoni)
- every successful answer is published on ``/harmoni/<service_id>/result`` (std_msgs/String)
- side outputs of the backend (e.g. the assistant thread id) on ``/harmoni/<service_id>/<channel>``
  with transient-local durability, so that nodes started later still receive the last value
"""

import threading

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from harmoni.constants import State
from harmoni.services import create_backend
from harmoni_interfaces.action import Harmoni
from harmoni_nodes.config import load_config, service_config, topic_for

LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)


class HarmoniServiceNode(Node):
    def __init__(self):
        super().__init__("harmoni_service")
        self.service_id = self.declare_parameter("service_id", "").value
        config_path = self.declare_parameter("config", "").value
        if not self.service_id or not config_path:
            raise ValueError("parameters 'service_id' and 'config' are required")
        backend_name, params, subscribe = service_config(load_config(config_path), self.service_id)

        self._side_publishers = {}
        self._result_pub = self.create_publisher(String, topic_for(self.service_id, "result"), 10)
        self.backend = create_backend(backend_name, self.service_id, params, emit=self._emit)
        for channel, topic in subscribe.items():
            self.create_subscription(String, topic, lambda msg, ch=channel: self.backend.on_input(ch, msg.data), LATCHED)

        try:
            self.backend.setup()
        except Exception as e:  # noqa: BLE001 - keep serving: every call will report the problem
            self.get_logger().error(f"setup of '{backend_name}' failed: {e}")

        self._busy = threading.Lock()  # one action at a time, like the ROS1 HARMONI services
        self._server = ActionServer(
            self, Harmoni, self.service_id,
            execute_callback=self._execute,
            goal_callback=lambda goal: GoalResponse.ACCEPT,
            cancel_callback=self._cancel,
            callback_group=ReentrantCallbackGroup(),
        )
        self.get_logger().info(f"HARMONI service '{self.service_id}' ready (backend: {backend_name})")

    def _emit(self, channel, message):
        if channel not in self._side_publishers:
            self._side_publishers[channel] = self.create_publisher(String, topic_for(self.service_id, channel), LATCHED)
        self._side_publishers[channel].publish(String(data=str(message)))

    def _cancel(self, goal_handle):
        self.backend.cancel()
        return CancelResponse.ACCEPT

    def _execute(self, goal_handle):
        request = goal_handle.request
        feedback = Harmoni.Feedback()
        feedback.state = int(State.REQUEST)
        goal_handle.publish_feedback(feedback)
        with self._busy:
            outcome = self.backend.handle(request.action_type, request.optional_data)
        result = Harmoni.Result()
        result.do_action = bool(outcome.ok)
        result.message = outcome.message or ""
        if goal_handle.is_cancel_requested:
            goal_handle.canceled()
            return result
        goal_handle.succeed()
        if outcome.ok and outcome.message:
            self._result_pub.publish(String(data=outcome.message))
        return result


def main(args=None):
    rclpy.init(args=args)
    node = HarmoniServiceNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.backend.stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
