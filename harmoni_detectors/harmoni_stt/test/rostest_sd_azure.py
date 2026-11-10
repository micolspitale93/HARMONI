#!/usr/bin/env python3
"""Live rostest for the Azure speaker diarization STT service."""

PKG = "test_harmoni_stt"
import sys
import unittest

import rospy

from harmoni_common_lib.action_client import HarmoniActionClient
from harmoni_common_lib.constants import ActionType, DetectorNameSpace


class TestSDAzure(unittest.TestCase):
    def setUp(self):
        rospy.init_node("test_sd_azure", log_level=rospy.INFO)
        self.result = None
        self.names = [n.strip() for n in rospy.get_param("stt/default_param/names").split(",")]
        self.name = DetectorNameSpace.stt.name + "_default"
        self.client = HarmoniActionClient(self.name)
        self.client.setup_client(self.name, self.result_cb, self.feedback_cb, wait=True)

    def feedback_cb(self, data):
        rospy.logdebug(f"Feedback: {data}")

    def result_cb(self, data):
        rospy.loginfo(f"Result: {data}")
        self.result = data

    def test_transcription_has_speaker(self):
        rospy.loginfo("TestSDAzure: please say something now")
        self.client.send_goal(action_goal=ActionType.REQUEST.value, optional_data="", wait=True)
        self.assertIsNotNone(self.result, "No result received from the STT service")
        self.assertTrue(self.result["do_action"])
        message = self.result["message"]
        self.assertIn(":", message, f"Transcription without speaker: {message}")


def main():
    import rostest

    rostest.rosrun(PKG, "test_sd_azure", TestSDAzure, sys.argv)


if __name__ == "__main__":
    main()
