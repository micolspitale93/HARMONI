#!/usr/bin/env python3
"""rostest for the OpenAI Assistant service: sends a REQUEST and checks that the
orchestrator answers with the JSON structure expected by the group interaction tree."""

PKG = "test_harmoni_bot"
# Common Imports
import json
import sys
import unittest

import rospy

# Specific Imports
from harmoni_common_lib.action_client import HarmoniActionClient
from harmoni_common_lib.constants import ActionType, DialogueNameSpace


class TestAssistant(unittest.TestCase):
    def setUp(self):
        rospy.init_node("test_assistant", log_level=rospy.INFO)
        self.text = rospy.get_param("test_assistant_input")
        self.instance_id = rospy.get_param("instance_id")
        self.result = None
        self.name = DialogueNameSpace.bot.name + "_" + self.instance_id
        self.service_client = HarmoniActionClient(self.name)
        self.service_client.setup_client(self.name, self.result_cb, self.feedback_cb)
        # give the service the time to create the assistant thread
        rospy.sleep(3)

    def feedback_cb(self, data):
        rospy.loginfo(f"Feedback: {data}")

    def result_cb(self, data):
        rospy.loginfo(f"Result: {data}")
        self.result = data

    def test_request_response(self):
        self.service_client.send_goal(
            action_goal=ActionType.REQUEST.value,
            optional_data=self.text,
            wait=True,
        )
        self.assertIsNotNone(self.result, "No result received from the assistant service")
        self.assertTrue(self.result["do_action"], f"Assistant request failed: {self.result}")
        response = json.loads(self.result["message"])
        for key in ("intervene", "agent", "response"):
            self.assertIn(key, response)


def main():
    import rostest

    rostest.rosrun(PKG, "test_assistant", TestAssistant, sys.argv)


if __name__ == "__main__":
    main()
