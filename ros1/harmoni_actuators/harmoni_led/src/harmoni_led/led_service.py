#!/usr/bin/env python3

# Common Imports
import rospy, rospkg
import roslib

from harmoni_common_lib.constants import State
from harmoni_common_lib.service_server import HarmoniServiceServer
from harmoni_common_lib.service_manager import HarmoniServiceManager


# Specific Imports
from harmoni_common_lib.constants import ActuatorNameSpace
from std_msgs.msg import String, Bool
from furhat_remote_api import FurhatRemoteAPI



class LedService(HarmoniServiceManager):
    """
    led service
    """
    def __init__(self, name, params):
        """ Initialization of variables and camera parameters """
        super().__init__(name)
        self.fur_robot_ip = params["furhat_robot_ip"]
        self.nao_robot_ip = params["nao_robot_ip"]

        
        self.nao_led_pub = rospy.Publisher(
            "/led_nao/set",
            String,
            queue_size = 1,
        )
        self.setup_pub = rospy.Publisher(
            "/nao/connect",
            String,
            queue_size=1,
        )
        self.setup_connection()
        self.state = State.INIT
        self.rospack = rospkg.RosPack()
        return
    
    def setup_connection(self):
        self.furhat = FurhatRemoteAPI(self.fur_robot_ip)
        self.setup_pub.publish(self.nao_robot_ip)

        
    def stop(self):
        return

    def do(self, data):
        """Publishes the string with either an audio file location or text to synthetise

        Converts input audio from bytes or a local/network path to an audio msg.

        Args:
            data (str): This could be a string of:
                            - string to say
                            - path of local wav file
        """
        self.state = State.REQUEST
        self.actuation_completed = False
        try:
            if data == "red":
                self.furhat.set_led(red=255, green=0, blue=0)
            elif data == "green":
                self.furhat.set_led(red=0, green=255, blue=0)
            self.nao_led_pub.publish(data)
            rospy.loginfo("End sending light updates")
            self.state = State.SUCCESS
            self.actuation_completed = True
        except IOError:
            rospy.logwarn("Connection with the robots failed")
            self.state = State.FAILED
            self.actuation_completed = True
        return {"response": self.state}
    
def main():
    """[summary]
    Main function for starting HarmoniPolly service
    """
    service_name = ActuatorNameSpace.led.name
    instance_id = rospy.get_param("instance_id")
    service_id = f"{service_name}_{instance_id}"
    try:
        rospy.init_node(service_name)
        param = rospy.get_param(service_name + "/" + instance_id + "_param/")
        s = LedService(service_id, param)
        service_server = HarmoniServiceServer(service_id, s)
        #s.do("red")
        service_server.start_sending_feedback()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()