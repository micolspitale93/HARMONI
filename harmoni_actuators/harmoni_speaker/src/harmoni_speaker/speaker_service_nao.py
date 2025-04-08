#!/usr/bin/env python3

# Common Imports
import rospy, rospkg, roslib

from harmoni_common_lib.constants import State, ActuatorNameSpace
from harmoni_common_lib.service_server import HarmoniServiceServer
from harmoni_common_lib.service_manager import HarmoniServiceManager
import harmoni_common_lib.helper_functions as hf


# Specific Imports
from audio_common_msgs.msg import AudioData
import numpy as np

# import wget
import contextlib
import ast
import wave
import os
#from naoqi import ALProxy

AUDIO_DELAY = 0.5 # this constant is used to make shorter the duration in which the service is sleeping.  

class SpeakerServiceNAO(HarmoniServiceManager):
    
    """Takes sound and publishes it to the default audio topic for the audio_play package

    Args:
        HarmoniServiceManager ([type]): [description]
    """

    def __init__(self, name, params):
        """ Initialization of variables and camera parameters """
        super().__init__(name)
        self.robot_ip = params["robot_ip"]
        self.tts = ""
        self.mock = params["mockup"]
        self.setup_connection()
        self.state = State.INIT
        self.rospack = rospkg.RosPack()
        return
    
    def setup_connection(self):
        if not self.mock:
            self.tts = ALProxy("ALTextToSpeech", "<IP of your robot>", 9559)
            self.audio_player_service = ALProxy("ALAudioPlayer", "<IP of your robot>", 9559)
        else:
            print("Mockup connection with the NAO robot")
        

        
    def stop(self):
        return

    def do(self, data):
        # TODO: include the addressee of the conversation!
        """
        Converts input audio from bytes or a local/network path to an audio msg.

        Args:
            data (str): This could be a string of:
                            - string
                            - path of local wav file
        """
        duration = 0
        self.state = State.REQUEST
        self.actuation_completed = False
        try:
            if not self.mock:
                self.tts.say(data)
            else:
                print("NAO is supposed to say ", data)
            self.state = State.SUCCESS
            self.actuation_completed = True
        except IOError:
            rospy.logwarn("Speaker failed: Audio appears too busy")
            self.state = State.FAILED
            self.actuation_completed = True
        return {"response": self.state}

def main():
    """Set names, collect params, and give service to server"""

    service_name = ActuatorNameSpace.speaker.name
    instance_id = "nao"
    service_id = f"{service_name}_{instance_id}"

    try:
        rospy.init_node(service_name)

        params = rospy.get_param(service_name + "/" + instance_id + "_param/")

        s = SpeakerServiceNAO(service_id, params)

        service_server = HarmoniServiceServer(service_id, s)

        print(service_name)
        print("****************************************************************************")
        print(service_id)

        service_server.start_sending_feedback()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()
