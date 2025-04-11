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
        # TODO: include the addressee of the conversation!
        """Publishes the string with either an audio file location or text to synthetise

        Converts input audio from bytes or a local/network path to an audio msg.

        Args:
            data (str): This could be a string of:
                            - string to say
                            - path of local wav file
        """
        self.state = State.REQUEST
        self.actuation_completed = False
        data =   json.loads(data)
        try:
            if self.mock:
                print("The robot will say:" , data)
            else:
                self.furhat.say(text=data["input"])
                # Attend a user with a specific id
                if "," in data["addressee"]:
                    rospy.loginfo("The speech is addressed to multiple people")
                else:
                    rospy.loginfo(f"The speech is addressed to {data["addressee"]}")
                    self.furhat.attend(userid=data["addressee"]) #addressee of the conversation
            rospy.loginfo("Writing data for speaker")
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
