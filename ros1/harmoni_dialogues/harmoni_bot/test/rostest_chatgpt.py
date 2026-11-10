#!/usr/bin/env python3


PKG = "test_harmoni_bot"
# Common Imports
import unittest, rospy, sys

# Specific Imports
from actionlib_msgs.msg import GoalStatus
from harmoni_common_msgs.msg import harmoniFeedback, harmoniResult
from std_msgs.msg import String
from harmoni_common_lib.action_client import HarmoniActionClient
from std_msgs.msg import String
from harmoni_common_lib.constants import DialogueNameSpace, ActionType
from collections import deque



class TestChatGPT(unittest.TestCase):

    def setUp(self):
        """
        Set up the client for requesting to harmoni_bot
        """
        rospy.init_node("test_chatgpt", log_level=rospy.INFO)
        self.text = rospy.get_param("test_chatgpt_input")
        self.instance_id = rospy.get_param("instance_id")
        self.result = False
        self.name = DialogueNameSpace.bot.name + "_" + self.instance_id
        self.service_client = HarmoniActionClient(self.name)
        self.client_result = deque()
        self.service_client.setup_client(self.name, self.result_cb, self.feedback_cb)
        # NOTE currently no feedback, status, or result is received.
        rospy.Subscriber(
            "/harmoni_bot_default/feedback", harmoniFeedback, self.feedback_cb
        )
        rospy.Subscriber("/harmoni_bot_default/status", GoalStatus, self.status_cb)
        rospy.Subscriber("/harmoni_bot_default/result", harmoniResult, self.result_cb)
        rospy.loginfo("Testchatgpt: Started up. waiting for chatgpt startup")
        rospy.loginfo("Testchatgpt: Started")

    def feedback_cb(self, data):
        rospy.loginfo(f"Feedback: {data}")
        self.result = False

    def status_cb(self, data):
        rospy.loginfo(f"Status: {data}")
        self.result = False

    def result_cb(self, data):
        rospy.loginfo(f"Result: {data}")
        self.result = True

    def test_request_response(self):
        rospy.loginfo(f"The input text is {self.text}")
        self.service_client.send_goal(
            action_goal=ActionType.REQUEST.value,
            optional_data=self.text,
            wait=True,
        )
        assert self.result == True


def main():
    # TODO convert to a test suite so that setup doesn't have to run over and over.
    import rostest

    rospy.loginfo("test_chatgpt started")
    rospy.loginfo("Testchatgpt: sys.argv: %s" % str(sys.argv))
    rostest.rosrun(PKG, "test_chatgpt", TestChatGPT, sys.argv)


if __name__ == "__main__":
    main()
