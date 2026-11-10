#!/usr/bin/env python3
"""End-to-end smoke test on real ROS 2 (run inside the harmoni_ros2 container).

Launches the group interaction with the mock configuration (every service is a real ROS2
node with canned answers) and waits until the tree reports that the interaction finished.

    ./harmoni.sh ros2 smoke-test          (or, in the container: python3 tests/ros_smoke_test.py)
"""

import json
import os
import signal
import subprocess
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

TIMEOUT_S = float(os.environ.get("SMOKE_TIMEOUT_S", 240))
CONFIG = os.path.join(os.environ.get("HARMONI_ROOT", "/root/HARMONI"), "ros2", "config", "group_interaction_mock.yaml")


def main():
    launch = subprocess.Popen(["ros2", "launch", "harmoni_nodes", "group_interaction.launch.py", f"config:={CONFIG}"],
                              start_new_session=True)
    rclpy.init()
    node = Node("harmoni_smoke_test")
    seen = {"last": None, "speakers": set()}

    def on_status(msg):
        snapshot = json.loads(msg.data)
        seen["last"] = snapshot
        agent = snapshot.get("blackboard", {}).get("/bot/agent")
        if agent:
            seen["speakers"].add(agent)

    qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)
    node.create_subscription(String, "/harmoni/tree/status", on_status, qos)
    deadline = time.time() + TIMEOUT_S
    try:
        while time.time() < deadline:
            rclpy.spin_once(node, timeout_sec=0.5)
            last = seen["last"]
            if last and last["state"] in ("finished", "error"):
                break
    finally:
        os.killpg(launch.pid, signal.SIGINT)
        try:
            launch.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(launch.pid, signal.SIGKILL)
        node.destroy_node()
        rclpy.shutdown()

    last = seen["last"]
    if not last:
        print("SMOKE TEST FAILED: no status received from the tree")
        return 1
    print(f"tree state: {last['state']} after {last['tick']} ticks; agents seen: {sorted(seen['speakers'])} {last['error']}")
    if last["state"] != "finished":
        print("SMOKE TEST FAILED")
        return 1
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
