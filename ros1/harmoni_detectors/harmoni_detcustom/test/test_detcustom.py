#!/usr/bin/env python3


PKG = "test_harmoni_detcustom"
# Common Imports
import unittest, rospy, roslib, sys

# Specific Imports
from actionlib_msgs.msg import GoalStatus
from harmoni_common_lib.action_client import HarmoniActionClient
from harmoni_common_lib.constants import (
    DetectorNameSpace,
    SensorNameSpace,
    ActionType,
    State,
)
from harmoni_common_msgs.msg import harmoniAction, harmoniFeedback, harmoniResult
from cv_bridge import CvBridge, CvBridgeError
from harmoni_common_lib.constants import SensorNameSpace, DetectorNameSpace
from std_msgs.msg import String, Bool
from sensor_msgs.msg import Image
import cv2


# from std_msgs.msg import String
import time
import os, io


class TestDetCustom_Common(unittest.TestCase):
       
    def setUp(self):
        self.feedback = State.INIT
        self.result = False
        self.detections = []
        self.img_encoding = "rgb8"  # NOTE: There's a weird bug with facenet and ROS Kinetic which will crash if this is set to "bgr8"
        self.openface_data_file = rospy.get_param('test_detcustom_input_openface')
        self.opensmile_data_file = rospy.get_param('test_detcustom_input_opensmile')
        with open(self.openface_data_file,'r') as f:
            self.openface_data = f.readline().rstrip('\n')
        with open(self.opensmile_data_file,'r') as f:
            self.opensmile_data = f.readline().rstrip('\n')
        rospy.init_node("test_detcustom", log_level=rospy.INFO)
        self.rate = rospy.Rate(1)

        self.openface_topic = DetectorNameSpace.openface.value + 'default'
        self.opensmile_topic = DetectorNameSpace.opensmile.value + 'default'
        self.openface_pub = rospy.Publisher(
            self.openface_topic,
            String,
            queue_size=1,
        )
        self.opensmile_pub = rospy.Publisher(
            self.opensmile_topic,
            String,
            queue_size=1,
        )
        self.output_sub = rospy.Subscriber(
            DetectorNameSpace.detcustom.value + "default",
            Bool,
            self._detecting_callback,
        )
        # rospy.loginfo(f"Testside-Image source: {SensorNameSpace.camera.value}default")
        rospy.loginfo(
            f"Testside-expected detection: {DetectorNameSpace.detcustom.value}default"
        )

        # startup detcustom node
        self.server = "/harmoni/detecting/detcustom/default"
        self.client = HarmoniActionClient(self.server)
        rospy.loginfo("***********SETTING UP CLIENT")
        self.client.setup_client(
            self.server, self._result_callback, self._feedback_callback, wait=True
        )
        rospy.loginfo("DONE SETTING UP****************")
        rospy.loginfo("TestDetCustom: Turning ON detcustom server")
        self.client.send_goal(
            action_goal=ActionType.ON, optional_data="Setup", wait=False
        )
        rospy.loginfo("TestDetCustom: Started up. waiting for face detect startup")

        # wait for start state
        # while not rospy.is_shutdown() and self.feedback != State.START:
        #     self.rate.sleep()

        rospy.loginfo("TestDetCustom: publishing openface and opensmile")
        # self.image_pub.publish(self.image[:14000])

        rospy.loginfo(
            f"TestDestCustom: data subscribed to by #{self.output_sub.get_num_connections()} connections."
        )

    def _feedback_callback(self, data):
        rospy.loginfo(f"TestDetCustom: Feedback: {data}")
        self.feedback = data["state"]

    def _status_callback(self, data):
        rospy.loginfo(f"TestDetCustom: Status: {data}")
        # self.result = True

    def _result_callback(self, data):
        rospy.loginfo(f"TestDetCustom: Result: {data}")
        # self.result = True

    def text_received_callback(self, data):
        rospy.loginfo(f"TestDetCustom: Text back: {data}")
        # self.result = True

    def _detecting_callback(self, data):
        rospy.logdebug(f"TestDetCustom: Detecting: {data}")
        print(data)
        self.detections = data.data
        self.result = True



class TestDetCustom_Valid(TestDetCustom_Common):
    def test_IO(self):
        rospy.loginfo(
            "TestDetCustom[TEST]: basic IO test to ensure data "
            + "(example data) is received and responded to. Waiting for detection..."
        )
        while not rospy.is_shutdown() and not self.result:
            self.openface_pub.publish(
                self.openface_data
            )
            self.opensmile_pub.publish(
                self.opensmile_data
            )
            self.rate.sleep()
        assert self.result == True


def main():
    import rostest

    rospy.loginfo("Testdetcustom: sys.argv: %s" % str(sys.argv))
    rostest.rosrun(PKG, "test_detcustom", TestDetCustom_Valid, sys.argv)


if __name__ == "__main__":
    main()
