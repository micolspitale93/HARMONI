"""Installs the rclpy fakes (see ros_fakes.py) before the HARMONI ROS2 nodes are imported."""

import py_trees
import pytest

from ros_fakes import REPO, FakeActionClient, FakeClock, FakeNode  # noqa: F401  (installs the fakes)


@pytest.fixture(autouse=True)
def _reset():
    FakeNode.parameters = {}
    FakeActionClient.instances = []
    FakeClock.now_ns = 0
    py_trees.blackboard.Blackboard.clear()
    yield
    py_trees.blackboard.Blackboard.clear()


@pytest.fixture
def repo():
    return REPO
