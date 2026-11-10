#!/usr/bin/env python3

# Common Imports
import rospy
import sys
import unittest

# Specific Imports
import time
import wave
from harmoni_common_lib.action_client import HarmoniActionClient
from harmoni_common_lib.constants import ActionType, DetectorNameSpace, SensorNameSpace, State

from audio_common_msgs.msg import AudioData
from std_msgs.msg import String

PKG = "test_harmoni_stt"


class TestGoogle_Common(unittest.TestCase):

    def setUp(self):
        self.feedback = State.INIT
        self.result = False
        self.test_file = rospy.get_param("test_google_input")
        rospy.init_node("test_google", log_level=rospy.INFO)
        self.rate = rospy.Rate(20)
        self.output_sub = rospy.Subscriber(
            "/harmoni/detecting/stt/default", String, self._detecting_callback
        )
        # provide mock microphone
        self.audio_pub = rospy.Publisher(
            SensorNameSpace.microphone.value
            + rospy.get_param("stt/default_param/subscriber_id"),
            AudioData,
            queue_size=10,
        )
        rospy.Subscriber(
            DetectorNameSpace.stt.value + "stt_default",
            String,
            self.text_received_callback,
        )

        # startup stt node
        self.server = "stt_default"
        self.client = HarmoniActionClient(self.server)
        self.client.setup_client(
            self.server, self._result_callback, self._feedback_callback, wait=True
        )
        rospy.loginfo("TestGoogle: Turning ON stt server")
        self.client.send_goal(
            action_goal=ActionType.REQUEST, optional_data="Setup", wait=False
        )
        rospy.loginfo("TestGoogle: Started up. waiting for Google startup")

        time.sleep(5)

        rospy.loginfo("TestGoogle: publishing audio")

        chunk_size = 1024
        wf = wave.open(self.test_file)
        # read data (based on the chunk size)
        index = 0
        audio_length = wf.getnframes()
        while index+chunk_size < audio_length:
            data = wf.readframes(chunk_size)
            self.audio_pub.publish(data)
            index = index+chunk_size
            time.sleep(0.2)

        rospy.loginfo(
            f"TestGoogle: audio subscribed to by #{self.output_sub.get_num_connections()} connections."
        )

    def _feedback_callback(self, data):
        rospy.loginfo(f"TestGoogle: Feedback: {data}")
        self.feedback = data["state"]

    def _status_callback(self, data):
        rospy.loginfo(f"TestGoogle: Status: {data}")
        self.result = True

    def _result_callback(self, data):
        rospy.loginfo(f"TestGoogle: Result: {data}")
        self.result = True

    def text_received_callback(self, data):
        rospy.loginfo(f"TestGoogle: Text back: {data}")
        self.result = True

    def _detecting_callback(self, data):
        rospy.loginfo(f"TestGoogle: Detecting: {data}")
        self.result = True


class TestGoogle_Valid(TestGoogle_Common):
    def test_IO(self):
        rospy.loginfo(
            "TestGoogle[TEST]: basic IO test to ensure data "
            + "('hello' audio) is received and responded to. Waiting for transcription..."
        )
        while not rospy.is_shutdown() and not self.result:
            self.rate.sleep()
        assert self.result


def main():
    # TODO combine validity tests into test suite so that setup doesn't have to run over and over.
    import rostest

    rospy.loginfo("test_google started")
    rospy.loginfo("TestGoogle: sys.argv: %s" % str(sys.argv))
    rostest.rosrun(PKG, "test_google", TestGoogle_Valid, sys.argv)


if __name__ == "__main__":
    main()
