#!/usr/bin/env python3

# Common Imports
import rospy, rospkg

from harmoni_common_lib.constants import State, ActuatorNameSpace
from harmoni_common_lib.service_server import HarmoniServiceServer
from harmoni_common_lib.service_manager import HarmoniServiceManager
import harmoni_common_lib.helper_functions as hf


# Specific Imports
from furhat_remote_api import FurhatRemoteAPI
from std_msgs.msg import String
import json
import ast


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



class SpeakerServiceFurhat(HarmoniServiceManager):
    """Takes text and send it to the Furhat robot, specifically note that the Furhat robot is using Amazon Polly to convert text into speech

    Args:
        HarmoniServiceManager ([type]): [description]
    """

    def __init__(self, name, params):
        """ Initialization of variables and camera parameters """
        super().__init__(name)
        self.robot_ip = params["robot_ip"]
        self.mock = params["mockup"]
        self.test_pub = rospy.Publisher(
            "/ciao",
            String,
            queue_size=0,
        )
        self.setup_connection()

        self.state = State.INIT
        self.rospack = rospkg.RosPack()
        return
    
    def setup_connection(self):
        if self.mock:
            print("Mockup connection to the Robot")
        else:
            self.furhat = FurhatRemoteAPI(self.robot_ip)
            # Get the voices on the robot
            voices = self.furhat.get_voices()
            # Set the voice of the robot
            self.furhat.set_voice(name='Matthew')

        
    def stop(self):
        return

    def do(self, data):
        """Makes the Furhat robot say a sentence and gaze at the addressee.

        Args:
            data (str): JSON string ``{"input": <text>, "addressee": <name>}``
        """
        self.state = State.REQUEST
        self.actuation_completed = False
        text, addressees = parse_speech_request(data)
        try:
            if self.mock:
                rospy.loginfo(f"[mockup] Furhat is supposed to say: {text} (addressee: {addressees})")
            else:
                self.furhat.say(text=text, blocking=True)
                if len(addressees) > 1:
                    rospy.loginfo("The speech is addressed to multiple people")
                elif len(addressees) == 1:
                    rospy.loginfo(f"The speech is addressed to {addressees[0]}")
                    self.furhat.attend(userid=addressees[0])  # addressee of the conversation
            rospy.loginfo("End writing data for speaker")
            self.state = State.SUCCESS
            self.actuation_completed = True
        except Exception as e:
            # IOError (audio busy) or any error raised by the Furhat remote API
            rospy.logwarn(f"Speaker failed: {e}")
            self.state = State.FAILED
            self.actuation_completed = True
        return {"response": self.state}

def main():
    """Set names, collect params, and give service to server"""

    service_name = ActuatorNameSpace.speaker.name
    instance_id = "furhat"
    service_id = f"{service_name}_{instance_id}"

    try:
        rospy.init_node(service_name)
        params = rospy.get_param(service_name + "/" + instance_id + "_param/")

        s = SpeakerServiceFurhat(service_id, params)
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
