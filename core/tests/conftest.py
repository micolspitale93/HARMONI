import os
import sys

import py_trees
import pytest

CORE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CORE)
TREES = os.path.join(CORE, "trees")


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


@pytest.fixture(autouse=True)
def clean_blackboard():
    py_trees.blackboard.Blackboard.clear()
    yield
    py_trees.blackboard.Blackboard.clear()


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def trees_dir():
    return TREES


def bb_get(key):
    return py_trees.blackboard.Blackboard.storage.get(key if key.startswith("/") else "/" + key)


def bb_set(**values):
    """bb_set(**{"scene/nlp": 1})"""
    for key, value in values.items():
        py_trees.blackboard.Blackboard.storage["/" + key.lstrip("/")] = value
