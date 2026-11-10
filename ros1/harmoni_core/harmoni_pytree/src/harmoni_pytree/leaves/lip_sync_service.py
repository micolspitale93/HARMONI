#!/usr/bin/env python3

# Common Imports
import rospy

from harmoni_common_lib.constants import *
from harmoni_common_lib.action_client import HarmoniActionClient
from actionlib_msgs.msg import GoalStatus
from harmoni_common_lib.constants import ActuatorNameSpace, ActionType, PyTreeNameSpace, Resources

import time
import py_trees

class LipSyncServicePytree(py_trees.behaviour.Behaviour):
    def __init__(self, name):

        self.name = name
        self.service_client_mouth = None
        self.service_client_eyes = None
        self.service_client_nose = None
        self.client_result = None
        self.send_request = True
        
        self.blackboards = []
        self.blackboard_tts = self.attach_blackboard_client(name=self.name, namespace=ActuatorNameSpace.tts.name)
        self.blackboard_tts.register_key("result", access=py_trees.common.Access.READ)
        self.blackboard_lips = self.attach_blackboard_client(name=self.name, namespace=Resources.face.value[1])

        super(LipSyncServicePytree, self).__init__(name)
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))

    def setup(self,**additional_parameters):
        self.logger.debug("Begin %s.setup()" % (self.__class__.__name__))
        """
        for parameter in additional_parameters:
            print(parameter, additional_parameters[parameter])  
            if(parameter == ActuatorNameSpace.face.name):
                self.mode = additional_parameters[parameter]        
        """
        self.service_client_face = HarmoniActionClient(self.name)
        self.server_name = "face"
        
        #self.service_client_face.setup_client(self.server_name, self._result_callback, self._feedback_callback)
        
        self.instance_id = "default"
        
        self.name_mouth = ActuatorNameSpace.face.name + "_mouth_" + self.instance_id
        self.service_client_mouth = HarmoniActionClient(self.name_mouth)
        self.name_nose = ActuatorNameSpace.face.name + "_nose_" + self.instance_id
        self.service_client_nose = HarmoniActionClient(self.name_nose)
        self.name_eyes = ActuatorNameSpace.face.name + "_eyes_" + self.instance_id
        self.service_client_eyes = HarmoniActionClient(self.name_eyes)
        self.service_client_mouth.setup_client(self.name_mouth, self._result_callback, self._feedback_callback)
        self.service_client_eyes.setup_client(self.name_eyes, self._result_callback, self._feedback_callback)
        self.service_client_nose.setup_client(self.name_nose, self._result_callback, self._feedback_callback)
        
        self.logger.debug("Behavior %s interface action clients have been set up!" % (self.server_name))
        
        self.logger.debug("End %s.setup()" % (self.__class__.__name__))

    def initialise(self):
        self.logger.debug("%s.initialise()" % (self.__class__.__name__))

    def update(self):
        new_state = self.service_client_mouth.get_state()
        print(new_state)
        if self.send_request:
            self.send_request = False
            self.logger.debug(f"Sending goal to {self.server_name}")
            self.service_client_mouth.send_goal(
                action_goal = ActionType["DO"].value,
                optional_data = self.blackboard_tts.result,
                wait=False,
            )
            self.logger.debug(f"Goal sent to {self.server_name}")
            new_status = py_trees.common.Status.RUNNING
        else:
            if new_state == GoalStatus.ACTIVE:
                new_status = py_trees.common.Status.RUNNING
            elif new_state == GoalStatus.SUCCEEDED:
                new_status = py_trees.common.Status.SUCCESS
            else:
                new_status = py_trees.common.Status.FAILURE

        self.logger.debug("%s.update()[%s]--->[%s]" % (self.__class__.__name__, self.status, new_status))
        return new_status 

    def terminate(self, new_status):
        new_state = self.service_client_mouth.get_state()
        print("terminate : ",new_state)
        if new_state == GoalStatus.SUCCEEDED or new_state == GoalStatus.ABORTED or new_state == GoalStatus.LOST:
            self.send_request = True
        if new_state == GoalStatus.PENDING:
            self.send_request = True
            self.logger.debug(f"Cancelling goal to {self.server_name}")
            self.service_client_mouth.cancel_all_goals()
            self.client_result = None
            self.logger.debug(f"Goal cancelled to {self.server_name}")
            #self.service_client_mouth.stop_tracking_goal()
            #self.logger.debug(f"Goal tracking stopped to {self.server_name}")
        self.logger.debug("%s.terminate()[%s->%s]" % (self.__class__.__name__, self.status, new_status))

    def _result_callback(self, result):
        """ Recieve and store result with timestamp """
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
    blackboard_input = py_trees.blackboard.Client(name=ActuatorNameSpace.tts.name, namespace=ActuatorNameSpace.tts.name)
    blackboard_input.register_key("result", access=py_trees.common.Access.WRITE)
    blackboard_input.result = "[{'start': 1, 'type': 'viseme', 'id': 'POSTALVEOLAR'}]"
    """
    [{'start':10, 'type': 'gaze', 'id':'target', 'point': [1,5,10]}]
    [{'start': 1, 'type': 'au', 'id': 'au13', 'pose': 1}]
    [{'start': 2, 'type': 'action', 'id': 'breath_face'}]
    [{'start': 5, 'type': 'action', 'id': 'saucy_face'}]
    [{'start': 8, 'type': 'viseme', 'id': 'POSTALVEOLAR'}]
    """
   
    print(blackboard_input)

    rospy.init_node("face_default", log_level=rospy.INFO)

    facePyTree = LipSyncServicePytree("FaceServiceTest")
    facePyTree.setup()
    try:
        for unused_i in range(0, 5):
            facePyTree.tick_once()
            time.sleep(0.5)
            print(blackboard_input)
        print("\n")
    except KeyboardInterrupt:
        print("Exception occurred")
        pass

if __name__ == "__main__":
    main()