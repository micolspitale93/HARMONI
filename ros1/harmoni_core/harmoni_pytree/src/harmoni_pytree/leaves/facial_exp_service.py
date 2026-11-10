#!/usr/bin/env python3

# Common Imports
import rospy
from harmoni_common_lib.constants import ActuatorNameSpace, ActionType, PyTreeNameSpace
from harmoni_common_lib.action_client import HarmoniActionClient
from actionlib_msgs.msg import GoalStatus

# Specific Imports

import time
import py_trees

class FacialExpServicePytree(py_trees.behaviour.Behaviour):
    def __init__(self, name):

        self.name = name
        self.service_client_mouth = None
        self.service_client_eyes = None
        self.service_client_nose = None
        self.client_result = None
        self.send_request = True

        self.blackboards = []

        self.blackboard_face = self.attach_blackboard_client(name=self.name, namespace=ActuatorNameSpace.face.name)
        self.blackboard_face.register_key("face_exp", access=py_trees.common.Access.READ)
        self.blackboard_scene = self.attach_blackboard_client(name=self.name, namespace=PyTreeNameSpace.scene.name)
        self.blackboard_scene.register_key(key="nlp", access=py_trees.common.Access.READ)
        
        print(self.blackboard_scene)
        super(FacialExpServicePytree, self).__init__(name)
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))

    def setup(self,**additional_parameters):
        self.server_name = "face"
        self.instance_id = "default"
        self.name_mouth = ActuatorNameSpace.face.name + "_mouth_" + self.instance_id
        self.service_client_mouth = HarmoniActionClient(self.name_mouth)
        self.name_nose = ActuatorNameSpace.face.name + "_nose_" + self.instance_id
        self.service_client_nose = HarmoniActionClient(self.name_nose)
        self.name_eyes = ActuatorNameSpace.face.name + "_eyes_" + self.instance_id
        self.service_client_eyes = HarmoniActionClient(self.name_eyes)
        self.service_client_mouth.setup_client(self.name_mouth, self._result_callback, self._feedback_callback)
        self.service_client_eyes.setup_client(self.name_eyes, self._result_callback, self._feedback_callback, wait=False)
        self.service_client_nose.setup_client(self.name_nose, self._result_callback, self._feedback_callback, wait=False)
        self.logger.debug("Behavior %s interface action clients have been set up!" % (self.server_name))
        
        self.logger.debug("%s.setup()" % (self.__class__.__name__))

    def initialise(self):
        self.logger.debug("%s.initialise()" % (self.__class__.__name__))

    def update(self):
        if self.blackboard_scene.nlp == 2:
            new_status = py_trees.common.Status.SUCCESS
        else:  
            if self.send_request:
                self.send_request = False
                self.data = self.blackboard_face.face_exp
                self.logger.debug(f"Sending goal to {self.server_name}")
                self.service_client_mouth.send_goal(
                    action_goal=ActionType.DO.value,
                    optional_data=self.data,
                    wait=True,
                )
                self.logger.debug(f"Goal sent to {self.server_name}")
                new_status = py_trees.common.Status.RUNNING
            else:
                new_state = self.service_client_mouth.get_state()
                print(new_state)
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
        """ Receive and store result with timestamp """
        self.logger.debug("The result of the request has been received")
        self.logger.debug(
            f"The result callback message from {result['service']} was {len(result['message'])} long"
        )
        self.client_result = result["message"]
        return

    def _feedback_callback(self, feedback):
        """ Feedback is currently just logged """
        self.logger.debug("The feedback received is %s." % feedback)
        self.server_state = feedback["state"]
        return

def main():
    #command_line_argument_parser().parse_args()
    py_trees.logging.level = py_trees.logging.Level.DEBUG
    blackboard_face = py_trees.blackboard.Client(name=ActuatorNameSpace.face.name, namespace=ActuatorNameSpace.face.name)
    blackboard_scene = py_trees.blackboard.Client(name=PyTreeNameSpace.scene.name, namespace=PyTreeNameSpace.scene.name)
    blackboard_face.register_key("face_exp", access=py_trees.common.Access.WRITE)
    blackboard_scene.register_key("nlp", access=py_trees.common.Access.WRITE)
    blackboard_face.face_exp = "[{'start': 1, 'type': 'viseme', 'id': 'POSTALVEOLAR'}]"
    blackboard_scene.nlp = 0
    """
    [{'start':10, 'type': 'gaze', 'id':'target', 'point': [1,5,10]}]
    [{'start': 1, 'type': 'au', 'id': 'au13', 'pose': 1}]
    [{'start': 2, 'type': 'action', 'id': 'breath_face'}]
    [{'start': 5, 'type': 'action', 'id': 'saucy_face'}]
    [{'start': 8, 'type': 'viseme', 'id': 'POSTALVEOLAR'}]
    """
   
    print(blackboard_scene)

    rospy.init_node("face_default", log_level=rospy.INFO)

    facePyTree = FacialExpServicePytree("FaceServiceTest")
    facePyTree.setup()
    try:
        for unused_i in range(0, 5):
            facePyTree.tick_once()
            time.sleep(0.5)
            print(blackboard_scene)
        print("\n")
    except KeyboardInterrupt:
        print("Exception occurred")
        pass

if __name__ == "__main__":
    main()
