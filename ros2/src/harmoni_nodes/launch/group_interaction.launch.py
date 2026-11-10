"""Launch the HARMONI services of a configuration file and the tree runner.

    ros2 launch harmoni_nodes group_interaction.launch.py                       # real robots/cloud
    ros2 launch harmoni_nodes group_interaction.launch.py config:=<path>.yaml   # another setup
    ros2 launch harmoni_nodes group_interaction.launch.py run_tree:=false       # services only

One harmoni_service node is started for every entry of ``services`` in the configuration.
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from harmoni_nodes.config import harmoni_root, load_config


def _nodes(context):
    config_path = LaunchConfiguration("config").perform(context)
    run_tree = LaunchConfiguration("run_tree").perform(context).lower() in ("1", "true", "yes")
    config = load_config(config_path)
    nodes = [
        Node(package="harmoni_nodes", executable="harmoni_service", name=service_id, output="screen",
             parameters=[{"service_id": service_id, "config": config_path}])
        for service_id in (config.get("services") or {})
    ]
    if run_tree:
        nodes.append(Node(package="harmoni_nodes", executable="harmoni_tree", name="harmoni_tree", output="screen",
                          parameters=[{"config": config_path}]))
    return nodes


def generate_launch_description():
    default = os.path.join(harmoni_root(), "ros2", "config", "group_interaction.yaml")
    return LaunchDescription([
        DeclareLaunchArgument("config", default_value=default, description="HARMONI ROS2 configuration file"),
        DeclareLaunchArgument("run_tree", default_value="true", description="also start the tree runner"),
        OpaqueFunction(function=_nodes),
    ])
