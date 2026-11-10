#!/usr/bin/env python3

# Common Imports
import rospy

from actionlib_msgs.msg import GoalStatus
from harmoni_common_lib.action_client import HarmoniActionClient
from harmoni_common_lib.constants import SensorNameSpace , ActionType
import py_trees
import time

import py_trees.console

class MicrophoneServicePytree(py_trees.behaviour.Behaviour):

    def __init__(self, name = "MicrophoneServicePytree"):

        self.name = name
        self.server_state = None
        self.service_client_microphone = None
        self.client_result = None
        self.send_request = True

        self.blackboards = []
        self.blackboard_microphone = self.attach_blackboard_client(name=self.name, namespace=SensorNameSpace.microphone.name)
        self.blackboard_microphone.register_key("result", access=py_trees.common.Access.WRITE)

        super(MicrophoneServicePytree, self).__init__(name)
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))

    def setup(self,**additional_parameters):
        self.service_client_microphone = HarmoniActionClient(self.name)
        self.server_name = "microphone_default"
        self.service_client_microphone.setup_client(self.server_name, 
                                            self._result_callback,
                                            self._feedback_callback)
        self.logger.debug("Behavior %s interface action clients have been set up!" % (self.server_name))
        
        self.logger.debug("%s.setup()" % (self.__class__.__name__))

    def initialise(self):
        self.logger.debug("%s.initialise()" % (self.__class__.__name__))

    def update(self):
        if self.send_request:
            self.send_request = False
            self.logger.debug(f"Sending goal to {self.server_name}")
            # Send request for each sensor service to set themselves up
            self.service_client_microphone.send_goal(
                action_goal=ActionType["ON"].value,
                optional_data="Setup",
                wait="",
            )
            self.logger.debug(f"Goal sent to {self.server_name}")
            new_status = py_trees.common.Status.RUNNING
        else:
            new_state = self.service_client_microphone.get_state()
            print(new_state)
            if new_state == GoalStatus.LOST:
                new_status = py_trees.common.Status.FAILURE
                raise
            elif new_state == GoalStatus.ABORTED:
                new_status = py_trees.common.Status.SUCCESS
            elif new_state == GoalStatus.SUCCEEDED:
                new_status = py_trees.common.Status.SUCCESS
                
            else:
                new_status = py_trees.common.Status.FAILURE
                raise
            self.blackboard_microphone.result = new_status
        self.logger.debug("%s.update()[%s]--->[%s]" % (self.__class__.__name__, self.status, new_status))
        return new_status

    def terminate(self, new_status):
        """
        new_state = self.service_client_microphone.get_state()
        print("terminate : ",new_state)
        if new_state == GoalStatus.SUCCEEDED or new_state == GoalStatus.ABORTED or new_state == GoalStatus.LOST:
            self.send_request = True
        if new_state == GoalStatus.PENDING:
            self.send_request = True
            self.logger.debug(f"Cancelling goal to {self.server_name}")
            self.service_client_microphone.cancel_all_goals()
            self.client_result = None
            self.logger.debug(f"Goal cancelled to {self.server_name}")
            self.service_client_microphone.stop_tracking_goal()
            self.logger.debug(f"Goal tracking stopped to {self.server_name}")
        """
        self.logger.debug("%s.terminate()[%s->%s]" % (self.__class__.__name__, self.status, new_status))

    def _result_callback(self, result):
        """ Receive and store result with timestamp """
        self.logger.debug("The result of the request has been received")
        self.logger.debug(
            f"The result callback message from {result['service']} was {len(result['message'])} long"
        )
        self.client_result = result["message"]
        return

    def _feedback_callback(self, feedback):
        """ Feedback is currently just logged """
        self.logger.debug("The feedback recieved is %s." % feedback)
        self.server_state = feedback["state"]
        return


def main():
    #command_line_argument_parser().parse_args()

    py_trees.logging.level = py_trees.logging.Level.DEBUG
    
    blackboard_output = py_trees.blackboard.Client(name=SensorNameSpace.microphone.name, namespace=SensorNameSpace.microphone.name)
    blackboard_output.register_key("result", access=py_trees.common.Access.READ)

    rospy.init_node("microphone_default", log_level=rospy.INFO)

    print(blackboard_output)

    microphonePyTree = MicrophoneServicePytree("MicrophoneServicePytreeTest")

    additional_parameters = dict([
        ("MicrophoneServicePytree_mode",False)])

    microphonePyTree.setup(**additional_parameters)
    try:
        for unused_i in range(0, 3):
            microphonePyTree.tick_once()
            time.sleep(0.5)
            print(blackboard_output)
        print("\n")
    except KeyboardInterrupt:
        print("Exception occurred")
        pass