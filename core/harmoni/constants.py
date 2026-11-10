"""Constants shared by every HARMONI layer (values are part of the wire protocol)."""

from enum import IntEnum


class ActionType(IntEnum):
    """Action requested to a service. Same values as the ROS1 harmoni_common_lib."""

    OFF = 0
    ON = 1
    PAUSE = 2
    REQUEST = 3
    DO = 4


class State(IntEnum):
    """State of a service. Same values as the ROS1 harmoni_common_lib."""

    INIT = 0
    START = 1
    REQUEST = 2
    SUCCESS = 3
    FAILED = 4
    PAUSE = 5
