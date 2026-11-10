"""Terminal monitor of a running HARMONI tree.

    ros2 run harmoni_nodes harmoni_monitor

It only subscribes to /harmoni/tree/status: like any dashboard, it observes the tree and
can send commands on /harmoni/tree/command, but it is never part of the control loop.
"""

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from harmoni_nodes.tree_node import LATCHED, STATUS_TOPIC

SYMBOL = {"RUNNING": "*", "SUCCESS": "+", "FAILURE": "x", "INVALID": " "}


def render(snapshot, show_blackboard=("/scene/number", "/bot/agent", "/bot/message", "/stt/result")):
    lines = [f"[{snapshot['state']}] {snapshot['tree']} tick {snapshot['tick']} {snapshot.get('error', '')}".rstrip()]

    def walk(node, depth):
        message = f"  ({node['message']})" if node.get("message") else ""
        lines.append(f"{'  ' * depth}{SYMBOL.get(node['status'], '?')} {node['name']}{message}")
        for child in node.get("children", []):
            walk(child, depth + 1)

    if snapshot.get("root"):
        walk(snapshot["root"], 1)
    blackboard = snapshot.get("blackboard", {})
    for key in show_blackboard:
        if key in blackboard:
            lines.append(f"  {key} = {blackboard[key]!r}")
    return "\n".join(lines)


class Monitor(Node):
    def __init__(self):
        super().__init__("harmoni_monitor")
        self.create_subscription(String, STATUS_TOPIC, self._on_status, LATCHED)

    def _on_status(self, msg):
        print("\033[2J\033[H" + render(json.loads(msg.data)), flush=True)


def main(args=None):
    rclpy.init(args=args)
    node = Monitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
