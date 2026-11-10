#!/usr/bin/env python3


PKG = "test_harmoni_fer"
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
from harmoni_common_lib.constants import SensorNameSpace
from std_msgs.msg import String
from sensor_msgs.msg import Image
import cv2


# from std_msgs.msg import String
import time
import os, io


class TestFaceExprRec_Common(unittest.TestCase):
       
    def setUp(self):
        self.feedback = State.INIT
        self.result = False
        self.detections = []
        self.img_encoding = "rgb8"  # NOTE: There's a weird bug with facenet and ROS Kinetic which will crash if this is set to "bgr8"
        self.image = cv2.imread(rospy.get_param("test_fer_input"))
        rospy.loginfo(f'Mock Image Source {rospy.get_param("test_fer_input")}')
        rospy.init_node("test_fer", log_level=rospy.INFO)
        self.rate = rospy.Rate(1)
        self.cv_bridge = CvBridge()
        # provide mock camera
        self.camera_topic = "/camera/color/image_raw" #SensorNameSpace.camera.value + "default"
        self.image_pub = rospy.Publisher(
            self.camera_topic,
            Image,
            queue_size=10,
        )
        rospy.loginfo("Started Mock Image Publisher")

        self.output_sub = rospy.Subscriber(
            DetectorNameSpace.fer.value + "default",
            String,
            self._detecting_callback,
        )
        rospy.loginfo(f"Testside-Image source: {SensorNameSpace.camera.value}default")
        rospy.loginfo(
            f"Testside-expected detection: {DetectorNameSpace.fer.value}default"
        )

        # startup fer node
        self.server = "/harmoni/detecting/fer/default"
        self.client = HarmoniActionClient(self.server)
        rospy.loginfo("***********SETTING UP CLIENT")
        self.client.setup_client(
            self.server, self._result_callback, self._feedback_callback, wait=True
        )
        rospy.loginfo("DONE SETTING UP****************")
        rospy.loginfo("TestFaceExprRec: Turning ON fer server")
        self.client.send_goal(
            action_goal=ActionType.ON, optional_data="Setup", wait=False
        )
        rospy.loginfo("TestFaceExprRec: Started up. waiting for face detect startup")

        # wait for start state
        # while not rospy.is_shutdown() and self.feedback != State.START:
        #     self.rate.sleep()

        rospy.loginfo("TestFaceExprRec: publishing image")

        self.image_pub.publish(
            self.cv_bridge.cv2_to_imgmsg(self.image, encoding=self.img_encoding)
        )
        # self.image_pub.publish(self.image[:14000])

        rospy.loginfo(
            f"TestFaceExprRec: image subscribed to by #{self.output_sub.get_num_connections()} connections."
        )

    def _feedback_callback(self, data):
        rospy.loginfo(f"TestFaceExprRec: Feedback: {data}")
        self.feedback = data["state"]

    def _status_callback(self, data):
        rospy.loginfo(f"TestFaceExprRec: Status: {data}")
        # self.result = True

    def _result_callback(self, data):
        rospy.loginfo(f"TestFaceExprRec: Result: {data}")
        # self.result = True

    def text_received_callback(self, data):
        rospy.loginfo(f"TestFaceExprRec: Text back: {data}")
        # self.result = True

    def _detecting_callback(self, data):
        rospy.logdebug(f"TestFaceExprRec: Detecting: {data}")
        print(data)
        self.detections = data.data
        self.result = True



class TestFaceExprRec_Valid(TestFaceExprRec_Common):
    def test_IO(self):
        rospy.loginfo(
            "TestFaceExprRec[TEST]: basic IO test to ensure data "
            + "(example image) is received and responded to. Waiting for detection..."
        )
        while not rospy.is_shutdown() and not self.result:
            self.image_pub.publish(
                self.cv_bridge.cv2_to_imgmsg(self.image, encoding=self.img_encoding)
            )
            self.rate.sleep()
        assert self.result == True


def main():
    import rostest

    rospy.loginfo("TestFER: sys.argv: %s" % str(sys.argv))
    rostest.rosrun(PKG, "test_fer", TestFaceExprRec_Valid, sys.argv)


if __name__ == "__main__":
    main()
