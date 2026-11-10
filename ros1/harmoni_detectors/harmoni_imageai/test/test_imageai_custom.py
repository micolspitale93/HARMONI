#!/usr/bin/env python3


PKG = "test_harmoni_imageai"
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
import cv2
from cv_bridge import CvBridge, CvBridgeError
from harmoni_common_lib.constants import SensorNameSpace
from std_msgs.msg import String
from sensor_msgs.msg import Image

# from std_msgs.msg import String
import time
import os, io


class TestImageAI_Common(unittest.TestCase):
       
    def setUp(self):
        self.feedback = State.INIT
        self.result = False
        self.img_encoding = "rgb8"  # NOTE: There's a weird bug with facenet and ROS Kinetic which will crash if this is set to "bgr8"
        self.image = cv2.imread(rospy.get_param("test_imageai_custom_input"))
        self.instance_id = rospy.get_param('instance_id')
        rospy.init_node("test_imageai_custom", log_level=rospy.INFO)
        self.rate = rospy.Rate(1)
        self.cv_bridge = CvBridge()
        # provide mock camera
        self.camera_topic = "/camera/color/image_raw" #SensorNameSpace.camera.value + "default"
        self.image_pub = rospy.Publisher(
            self.camera_topic,
            Image,
            queue_size=10,
        )

        rospy.loginfo(f"Testside-Image source: {SensorNameSpace.camera.value}default")
        rospy.loginfo(
            f"Testside-expected detection: {DetectorNameSpace.imageai_custom_yolo.value}default"
        )

        # startup imageai node
        self.server = DetectorNameSpace.imageai_custom_yolo.name + "_" + self.instance_id
        self.client = HarmoniActionClient(self.server)
        rospy.loginfo("***********SETTING UP CLIENT")
        rospy.loginfo(self.server)
        self.client.setup_client(
            self.server, self._result_callback, self._feedback_callback, wait=True
        )
        rospy.loginfo("DONE SETTING UP****************")
        rospy.loginfo("TestImageAI_Common: Turning ON imageai server")
        
        self.client.send_goal(
            action_goal=ActionType.ON, wait=False
        )
        rospy.loginfo("TestImageAI_Common: Started up.")

        self.client.send_goal(
            action_goal=ActionType.REQUEST.value, wait=True
        )
        rospy.loginfo("TestImageAI_Common: Requesting service.")

        rospy.loginfo("TestImageAI_Common: publishing image")

        self.image_pub.publish(
           self.cv_bridge.cv2_to_imgmsg(self.image, encoding=self.img_encoding)
        )

        rospy.loginfo(
            f"TestImageAI_Common: image subscribed to by #{self.output_sub.get_num_connections()} connections."
        )

    def _feedback_callback(self, data):
        rospy.loginfo(f"TestImageAI_Common: Feedback: {data}")
        self.feedback = data["state"]

    def _status_callback(self, data):
        rospy.loginfo(f"TestImageAI_Common: Status: {data}")
        # self.result = True

    def _result_callback(self, data):
        rospy.loginfo(f"TestImageAI_Common: Result: {data}")
        self.result = True


class TestImageAI_Valid(TestImageAI_Common):
    def test_IO(self):
        rospy.loginfo(
            "TestImageAI[TEST]: basic IO test to ensure data "
            + "(example image) is received and responded to. Waiting for detection..."
        )
        
        while not rospy.is_shutdown() and not self.result:
            self.image_pub.publish(
               self.cv_bridge.cv2_to_imgmsg(self.image, encoding=self.img_encoding)
            )
            rospy.sleep(1)
        self.client.send_goal(
            action_goal=ActionType.OFF, wait=False
        )
        assert self.result == True


def main():
    import rostest

    rospy.loginfo("TestImageAI_Valid: sys.argv: %s" % str(sys.argv))
    rostest.rosrun(PKG, "test_imageai_custom", TestImageAI_Valid, sys.argv)


if __name__ == "__main__":
    main()
