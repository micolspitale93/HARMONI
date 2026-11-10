#!/usr/bin/env python3

# Common Imports
import rospy, rospkg, roslib

from harmoni_common_lib.constants import State, ActuatorNameSpace
from harmoni_common_lib.service_server import HarmoniServiceServer
from harmoni_common_lib.service_manager import HarmoniServiceManager
import harmoni_common_lib.helper_functions as hf
from harmoni_speaker.srv import nao_speak

# Specific Imports
from std_msgs.msg import String, Bool
import numpy as np
import json


def parse_speech_request(data):
    """Parse the payload of a robot speaker DO request.

    Args:
        data (str): JSON string ``{"input": <text>, "addressee": <name(s)>}``.
            A plain (non JSON) string is interpreted as the text to say.

    Returns:
        tuple: (text to say, list of addressees). The list is empty when the speech is
        not addressed to anyone in particular (missing, empty or "null" addressee).
    """
    try:
        payload = json.loads(data)
    except (TypeError, ValueError):
        payload = {"input": data}
    if not isinstance(payload, dict):
        payload = {"input": str(payload)}
    text = str(payload.get("input", ""))
    addressee = payload.get("addressee") or ""
    names = [a.strip() for a in str(addressee).split(",")]
    names = [a for a in names if a and a.lower() != "null"]
    return text, names



class SpeakerServiceNAO(HarmoniServiceManager):
    
    """Takes sound and publishes it to the default audio topic for the audio_play package

    Args:
        HarmoniServiceManager ([type]): [description]
    """

    
    def __init__(self, name, params):
        """ Initialization of variables and camera parameters """
        super().__init__(name)
        self.robot_ip = params["robot_ip"]
        self.mock = params["mockup"]
        print("Initializing publishers")
        self.speak_service = rospy.ServiceProxy('/nao/speak', nao_speak)
        
        self.setup_pub = rospy.Publisher(
            "/" + self.name  +"/connect",
            String,
            queue_size=1,
        )
        self.play_pub = rospy.Publisher(
            "/" +self.name  +"/play",
            String,
            queue_size=1,
        )
        self.addressee_pub = rospy.Publisher(
            "/" +self.name  +"/addressee",
            String,
            queue_size=1,
        )
        self.nao_up_sub = rospy.Subscriber(
            "/speaker_nao/start",
            Bool,
            self.connected,
        )
        print("Start the connection")
        self.setup_pub.publish(self.robot_ip)
        self.state = State.INIT
        #self.setup_connection()
        return
    
    def connected(self, data):
        if data.data:
            if not self.mock:
                self.setup_pub.publish(self.robot_ip)
                print("CONNECTED")
                rospy.sleep(5)
                #self.do("CIAO")
                rospy.wait_for_service('/nao/speak')
            else:
                print("Mockup connection with the NAO robot")
        return
        
        
    def stop(self):
        return

    def do(self, data):
        """
        Converts input audio from bytes or a local/network path to an audio msg.

        Args:
            data (str): This could be a string of:
                            - string
                            - path of local wav file
        """
        self.state = State.REQUEST
        self.actuation_completed = False
        text, addressees = parse_speech_request(data)
        try:
            if not self.mock:
                self.speak_service(text)
                if len(addressees) > 1:
                    rospy.loginfo("The speech is addressed to multiple people")
                elif len(addressees) == 1:
                    rospy.loginfo(f"The speech is addressed to {addressees[0]}")
                    self.addressee_pub.publish(addressees[0])
            else:
                rospy.loginfo(f"[mockup] NAO is supposed to say: {text} (addressee: {addressees})")
            self.state = State.SUCCESS
            self.actuation_completed = True
        except (IOError, rospy.ServiceException) as e:
            rospy.logwarn(f"Speaker failed: {e}")
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

