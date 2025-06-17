#!/usr/bin/env python3

# Importing the libraries
import rospy
import roslib

from harmoni_common_lib.constants import State
from harmoni_common_lib.service_server import HarmoniServiceServer
from harmoni_common_lib.service_manager import HarmoniServiceManager
from harmoni_common_lib.websocket_server import HarmoniWebsocketServer


class BehaviorController(HarmoniWebsocketServer):
    """Instantiates behaviors and receives commands/data for them.

    This class is a singleton ROS node and should only be instantiated once.
    """

    def __init__(self):
        rospy.loginfo("Connection to the socket")
        message = { "op": "publish",
                    "topic": "/qt_robot/gesture/play",
                    "msg": {'data': 'QT/kiss'}
                    }
        HarmoniWebsocketServer.__init__(self, ip = "192.168.100.1", port = "8081", secure=False, openmessage=message)


if __name__ == "__main__":
    try:
        rospy.init_node("test")
        bc = BehaviorController()
        rospy.loginfo("Started.")
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
