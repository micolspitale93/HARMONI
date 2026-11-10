"""Runs a HARMONI tree file on ROS2.

    ros2 run harmoni_nodes harmoni_tree --ros-args -p config:=/root/HARMONI/ros2/config/group_interaction.yaml

- ticks the tree on its own timer: no tool or UI is in the control loop;
- publishes a JSON snapshot of the tree after every tick on ``/harmoni/tree/status``
  (latched, so a dashboard that connects later gets the current state);
- accepts ``pause``, ``resume``, ``stop``, ``reload`` on ``/harmoni/tree/command``,
  applied between two ticks (``reload`` re-reads the tree file after an edit).
"""

import json

import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

from harmoni.tree import BuildContext, ClientRegistry, TreeRunner, load_spec, services_used
from harmoni_nodes.config import load_config, tree_settings
from harmoni_nodes.ros_client import RosServiceClient

STATUS_TOPIC = "/harmoni/tree/status"
COMMAND_TOPIC = "/harmoni/tree/command"
LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)


class TreeRunnerNode(Node):
    def __init__(self):
        super().__init__("harmoni_tree")
        config_path = self.declare_parameter("config", "").value
        tree_override = self.declare_parameter("tree", "").value
        self.startup_timeout_s = float(self.declare_parameter("startup_timeout_s", 30.0).value)
        tree_file, variables, period_s, cast = tree_settings(load_config(config_path) if config_path else {},
                                                             tree_override)

        self.service_clients = ClientRegistry(factory=lambda service_id: RosServiceClient(self, service_id))
        context = BuildContext(client_for=self.service_clients, logger=_RosLogger(self.get_logger()))
        self.runner = TreeRunner(tree_file, context, variables, period_s=period_s, cast=cast)
        self.required = services_used(load_spec(tree_file), cast)
        for service_id in self.required:
            self.service_clients(service_id)  # create the action clients now, so discovery starts

        self.status_pub = self.create_publisher(String, STATUS_TOPIC, LATCHED)
        self.runner.observers.append(lambda snapshot: self.status_pub.publish(String(data=json.dumps(snapshot))))
        self.create_subscription(String, COMMAND_TOPIC, self._on_command, 10)
        self._waiting_since = self.get_clock().now()
        self._started = False
        self._last_state = None
        self.timer = self.create_timer(period_s, self._on_timer, callback_group=MutuallyExclusiveCallbackGroup())
        self.get_logger().info(f"tree {tree_file}: waiting for services {', '.join(self.required)}")

    def _on_command(self, msg):
        try:
            self.runner.command(msg.data)
        except ValueError as e:
            self.get_logger().warning(str(e))

    def _services_ready(self):
        missing = [s for s in self.required if not self.service_clients(s).is_ready()]
        waited = (self.get_clock().now() - self._waiting_since).nanoseconds / 1e9
        if missing and waited < self.startup_timeout_s:
            return False
        if missing:
            self.get_logger().warning(f"starting without services: {', '.join(missing)} (their calls will fail)")
        return True

    def _on_timer(self):
        if not self._started:
            if not self._services_ready():
                return
            self._started = True
            try:
                self.runner.load()
                self.get_logger().info("tree started")
            except Exception as e:  # noqa: BLE001 - report it, keep the node alive (fix the file, then `reload`)
                self.runner.state, self.runner.error = "error", f"{type(e).__name__}: {e}"
        snapshot = self.runner.step()
        if snapshot["state"] != self._last_state:
            self._last_state = snapshot["state"]
            log = self.get_logger().error if snapshot["state"] == "error" else self.get_logger().info
            log(f"tree {snapshot['state']} {snapshot['error']}".strip())


class _RosLogger:
    """logging.Logger-like adapter used by the leaves"""

    def __init__(self, logger):
        self._logger = logger

    def debug(self, msg, *args):
        self._logger.debug(msg % args if args else msg)

    def info(self, msg, *args):
        self._logger.info(msg % args if args else msg)

    def warning(self, msg, *args):
        self._logger.warning(msg % args if args else msg)

    def error(self, msg, *args):
        self._logger.error(msg % args if args else msg)


def main(args=None):
    rclpy.init(args=args)
    node = TreeRunnerNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.runner.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
