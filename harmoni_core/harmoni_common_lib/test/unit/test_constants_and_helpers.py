#!/usr/bin/env python3
"""Unit tests for harmoni_common_lib constants and helper functions (no ROS needed).

Run from the repository root with: python3 -m pytest harmoni_core/harmoni_common_lib/test/unit
"""

import pytest

import harmoni_common_lib.helper_functions as hf
from harmoni_common_lib.constants import (
    ActionType,
    ActuatorNameSpace,
    DetectorNameSpace,
    DialogueNameSpace,
    SensorNameSpace,
    State,
)


def test_action_types_match_action_server_contract():
    # These values are sent over ROS as integers: changing them breaks every client
    assert [a.value for a in ActionType] == [0, 1, 2, 3, 4]
    assert ActionType.REQUEST == 3 and ActionType.DO == 4


def test_states_are_ordered_and_unique():
    assert [s.value for s in State] == list(range(len(State)))


@pytest.mark.parametrize("namespace", [SensorNameSpace, ActuatorNameSpace, DialogueNameSpace, DetectorNameSpace])
def test_topic_namespaces_are_well_formed(namespace):
    for item in namespace:
        assert item.value.startswith("/harmoni/"), item


@pytest.mark.parametrize(
    "service_name, child_id",
    [("stt_default", "default"), ("speaker_nao", "nao"), ("bot_default", "default"), ("speaker_furhat", "furhat")],
)
def test_get_child_id(service_name, child_id):
    assert hf.get_child_id(service_name) == child_id


def test_check_if_detector():
    assert hf.check_if_detector("stt") is True
