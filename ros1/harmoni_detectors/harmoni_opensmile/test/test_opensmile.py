#!/usr/bin/env python3


PKG = "test_harmoni_opensmile"
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
from harmoni_common_lib.constants import SensorNameSpace
from std_msgs.msg import String
from audio_common_msgs.msg import AudioData
import wave


# from std_msgs.msg import String
import time
import os, io


class TestOpenSmile_Common(unittest.TestCase):
       
    def setUp(self):
        self.feedback = State.INIT
        self.result = False
        self.detections = []
        rospy.init_node("test_opensmile", log_level=rospy.INFO)
        self.rate = rospy.Rate(1)
        self.test_file = rospy.get_param('test_opensmile_input')
        # provide mock mic
        self.mic_topic = SensorNameSpace.microphone.value + "default"
        self.audio_pub = rospy.Publisher(
            self.mic_topic,
            AudioData,
            queue_size=10,
        )

        self.output_sub = rospy.Subscriber(
            DetectorNameSpace.opensmile.value + "default",
            String,
            self._detecting_callback,
        )
        rospy.loginfo(f"Testside-Audio source: {SensorNameSpace.microphone.value}default")
        rospy.loginfo(
            f"Testside-expected detection: {DetectorNameSpace.opensmile.value}default"
        )

        # startup opensmile node
        self.server = "/harmoni/detecting/opensmile/default"
        self.client = HarmoniActionClient(self.server)
        rospy.loginfo("***********SETTING UP CLIENT")
        self.client.setup_client(
            self.server, self._result_callback, self._feedback_callback, wait=True
        )
        rospy.loginfo("DONE SETTING UP****************")
        rospy.loginfo("TestOpenSmile: Turning ON opensmile server")
        self.client.send_goal(
            action_goal=ActionType.ON, optional_data="Setup", wait=False
        )
        rospy.loginfo("TestOpenSmile: Started up. waiting for face detect startup")

        # wait for start state
        # while not rospy.is_shutdown() and self.feedback != State.START:
        #     self.rate.sleep()

        rospy.loginfo("TestOpenSmile: publishing audio")

        chunk_size = 512 #only 54 iterations on test file for chunk size 1024
        wf = wave.open(self.test_file)
        index = 0
        audio_length = wf.getnframes()
        while index+chunk_size < audio_length:
            data = wf.readframes(chunk_size)
            self.audio_pub.publish(data)
            index = index+chunk_size
            time.sleep(0.2)

        rospy.loginfo(
            f"TestOpenSmile: audio subscribed to by #{self.output_sub.get_num_connections()} connections."
        )

    def _feedback_callback(self, data):
        rospy.loginfo(f"TestOpenSmile: Feedback: {data}")
        self.feedback = data["state"]

    def _status_callback(self, data):
        rospy.loginfo(f"TestOpenSmile: Status: {data}")
        # self.result = True

    def _result_callback(self, data):
        rospy.loginfo(f"TestOpenSmile: Result: {data}")
        # self.result = True

    def text_received_callback(self, data):
        rospy.loginfo(f"TestOpenSmile: Text back: {data}")
        # self.result = True

    def _detecting_callback(self, data):
        rospy.logdebug(f"TestOpenSmile: Detecting: {data}")
        print(data)
        self.detections = data.data
        self.result = True



class TestOpenSmile_Valid(TestOpenSmile_Common):
    def test_IO(self):
        rospy.loginfo(
            "TestOpenSmile[TEST]: basic IO test to ensure data "
            + "(example audio) is received and responded to. Waiting for detection..."
        )
        while not rospy.is_shutdown() and not self.result:
            print('Waiting')
            self.rate.sleep()
        assert self.result == True


def main():
    import rostest

    rospy.loginfo("Testopensmile: sys.argv: %s" % str(sys.argv))
    rostest.rosrun(PKG, "test_opensmile", TestOpenSmile_Valid, sys.argv)


if __name__ == "__main__":
    main()
