#!/usr/bin/env python3


PKG = "test_harmoni_rl"
# Common Imports
import unittest, rospy, roslib, sys, rospkg

# Specific Imports
from actionlib_msgs.msg import GoalStatus
from harmoni_common_msgs.msg import harmoniAction, harmoniFeedback, harmoniResult
from std_msgs.msg import String
from harmoni_common_lib.action_client import HarmoniActionClient
from std_msgs.msg import String, Bool, Float32
from harmoni_common_lib.constants import DialogueNameSpace, ActionType, DetectorNameSpace
from collections import deque
import os, io
import ast


class TestRL(unittest.TestCase):

    def setUp(self):
        """
        Set up the client for requesting to harmoni_rl
        """
        rospy.init_node("test_rl", log_level=rospy.INFO)
        self.text = rospy.get_param("test_rl_input")
        self.instance_id = rospy.get_param("instance_id")
        self.result = False
        self.name = DialogueNameSpace.rl.name + "_" + self.instance_id
        
        self._duration_pub = rospy.Publisher(
            DetectorNameSpace.stt.value + self.instance_id + '/duration',
            Float32,
            queue_size=1)  
        self._fer_pub = rospy.Publisher(
            DetectorNameSpace.fer.value + self.instance_id,
            String,
            queue_size=1)
        self._fer_pub_baseline = rospy.Publisher(
            DetectorNameSpace.fer.value + self.instance_id + "/baseline",
            String,
            queue_size=1)
        self._detcustom_pub = rospy.Publisher(
            DetectorNameSpace.detcustom.value + self.instance_id,
            Bool,
            queue_size=1)
        self._vad_pub = rospy.Publisher(
            DetectorNameSpace.vad.value + self.instance_id,
            Bool,
            queue_size=1)
        self._stt_pub = rospy.Publisher(
            DetectorNameSpace.stt.value + self.instance_id,
            String,
            queue_size=1)
        
        self.service_client = HarmoniActionClient(self.name)
        self.client_result = deque()
        self.service_client.setup_client(self.name, self.result_cb, self.feedback_cb)

        # NOTE currently no feedback, status, or result is received.
        rospy.loginfo("TestRL: Started up. waiting for rl startup")
        rospy.Subscriber(DialogueNameSpace.rl.name+'feedback', harmoniFeedback, self.feedback_cb)
        rospy.Subscriber(DialogueNameSpace.rl.name+'status', GoalStatus, self.status_cb)
        rospy.Subscriber(DialogueNameSpace.rl.name+'result', harmoniResult, self.result_cb)
        
        rospy.loginfo("TestRL: Started")

    def feedback_cb(self, data):
        rospy.loginfo(f"Feedback: {data}")
        # self.result = False

    def status_cb(self, data):
        rospy.loginfo(f"Status: {data}")
        # self.result = False

    def result_cb(self, data):
        rospy.loginfo(f"Result: {data}")
        self.result = True

    def test_request_response(self):
        rospy.loginfo(f"The input text is {self.text}")
        self._duration_pub.publish(float(3))
        self._fer_pub.publish(str([0.1093499, 0.60552657]))
        self._fer_pub_baseline.publish(str([0.11084521, 0.5602681]))
        self._detcustom_pub.publish(True)
        self._vad_pub.publish(True)
        self._stt_pub.publish('Hello')
        rospy.loginfo('TestRl: Published Mock Data')

        self.service_client.send_goal(
            action_goal=ActionType.REQUEST.value,
            wait=True,
            optional_data='3'
        )

        assert self.result == True


def main():
    # TODO convert to a test suite so that setup doesn't have to run over and over.
    import rostest

    rospy.loginfo("test_rl started")
    rospy.loginfo("Testrl: sys.argv: %s" % str(sys.argv))
    rostest.rosrun(PKG, "test_rl", TestRL, sys.argv)


if __name__ == "__main__":
    main()
