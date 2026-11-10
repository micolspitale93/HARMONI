#!/usr/bin/env python2

# Common Imports
import rospy
from std_msgs.msg import String, Bool
from harmoni_speaker.srv import nao_speak

# Specific Imports
import numpy as np
import time
import random

# import wget
from naoqi import ALProxy


class SpeakerAPINAO():
    
    """Takes sound and publishes it to the default audio topic for the audio_play package

    Args:
        HarmoniServiceManager ([type]): [description]
    """

    def __init__(self):
        """ Initialization of variables and camera parameters """
        print("APIs Nao node up and running")
        self.setup_sub = rospy.Subscriber(
            "/speaker_nao/connect",
            String,
            self.setup_connection,
        )
        self.start_pub = rospy.Publisher(
            "/speaker_nao/start",
            Bool,
            queue_size = 1,
        )
        self.play_sub = rospy.Subscriber(
            "/speaker_nao/play",
            String,
            self.play,
        )
        self.play_service = rospy.Service('/nao/speak', nao_speak, self.play)
        self.addressee_sub = rospy.Subscriber(
            "/speaker_nao/addressee",
            String,
            self.move,
        )
        self.tts = None
        rospy.sleep(3)
        self.start_pub.publish(True)
        return
    
    def setup_connection(self, data):
        print(data.data)
        self.tts = ALProxy("ALTextToSpeech", data.data, 9559)
        self.motion = ALProxy("ALMotion", data.data, 9559)
        return
        
    def play(self, data):
        print(data.data)
        id = self.tts.say(data.data)
        print("DONE THE SPEECH")
        return "done"

    def move(self,data):
        print(data.data)
        """
        self.motion.moveInit()
        testTime = 10 # seconds
        t = 0
        dt = 0.2
        while (t<testTime):
            # JERKY HEAD
            self.motion.setAngles("HeadYaw", random.uniform(-1.0, 1.0), 0.6)
            self.motion.setAngles("HeadPitch", random.uniform(-0.5, 0.5), 0.6)
            t = t + dt
            time.sleep(dt)
        # stop walk on the next double support
        self.motion.stopMove()
        """
        return

def main():
    """Set names, collect params, and give service to server"""
    try:
        rospy.init_node("API_Nao")
        s = SpeakerAPINAO()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()
