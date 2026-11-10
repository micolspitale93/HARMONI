"""HARMONI core: everything that does not depend on ROS.

- :mod:`harmoni.tree`     behavior tree file format, validation, builder, runner, snapshots
- :mod:`harmoni.leaves`   ROS-agnostic py_trees leaves (service calls, conditions, group interaction)
- :mod:`harmoni.services` service backends (LLM, speech, robots) that ROS1/ROS2 nodes wrap

The ROS layers (``ros2/``) only translate between ROS and these classes, so the same tree
and the same backends can run on ROS2, in a simulator, or in tests without any ROS installed.
"""

__version__ = "2.0.0"
