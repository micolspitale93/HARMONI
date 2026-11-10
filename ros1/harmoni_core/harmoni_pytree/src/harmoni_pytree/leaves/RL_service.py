#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Common Imports
import rospy
from harmoni_common_lib.constants import *
from actionlib_msgs.msg import GoalStatus
from harmoni_common_lib.action_client import HarmoniActionClient
from harmoni_common_lib.constants import ActionType, DialogueNameSpace, PyTreeNameSpace
# Specific Imports
import py_trees
import time


class RLPytreeService(py_trees.behaviour.Behaviour):
    def __init__(self, name):
        self.name = name
        self.blackboards = []
        self.blackboard_scene = self.attach_blackboard_client(name=self.name, namespace=PyTreeNameSpace.scene.name)
        self.blackboard_scene.register_key(key="action", access=py_trees.common.Access.WRITE)
        self.blackboard_scene.register_key(key="exercise", access=py_trees.common.Access.READ)
        self.blackboard_scene.register_key(key="rl", access=py_trees.common.Access.READ)
        self.blackboard_rl = self.attach_blackboard_client(name=self.name, namespace=DialogueNameSpace.rl.name)
        self.blackboard_rl.register_key("result", access=py_trees.common.Access.WRITE)
        super(RLPytreeService, self).__init__(name)
        self.send_request = True
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))

    def setup(self,**additional_parameters):
        self.service_client_rl = HarmoniActionClient(self.name)
        self.server_name = "rl_default"
        self.service_client_rl.setup_client(self.server_name, 
                                            self._result_callback,
                                            self._feedback_callback)
        self.logger.debug("Behavior %s interface action clients have been set up!" % (self.server_name))
        
        self.blackboard_rl.result = "null"
        self.blackboard_scene.action = 2

        self.logger.debug("%s.setup()" % (self.__class__.__name__))

    def initialise(self):   
        self.logger.debug("%s.initialise()" % (self.__class__.__name__))

    def update(self): 
        rospy.loginfo("HEEEEREEEEEE ================= ")
        rospy.loginfo(self.blackboard_scene.rl)
        if self.blackboard_scene.rl:
            if self.send_request:
                self.send_request = False
                self.logger.debug(f"Sending goal to {self.server_name}")
                self.service_client_rl.send_goal(
                    action_goal = ActionType["REQUEST"].value,
                    optional_data = str(1), #self.blackboard_scene.exercise,
                    wait=True,
                )
                self.logger.debug(f"Goal sent to {self.server_name}")
                new_status = py_trees.common.Status.RUNNING
            else:
                new_status = py_trees.common.Status.RUNNING
                new_state = self.service_client_rl.get_state()
                print("update : ",new_state)
                if new_state == GoalStatus.ACTIVE:
                    new_status = py_trees.common.Status.RUNNING
                elif new_state == GoalStatus.SUCCEEDED:
                    if self.client_result is not None:
                        self.blackboard_rl.result = self.client_result
                        self.blackboard_scene.action = int(self.client_result)
                        self.client_result = None
                        new_status = py_trees.common.Status.SUCCESS
                    else:
                        self.logger.debug(f"Waiting fot the result ({self.server_name})")
                        new_status = py_trees.common.Status.RUNNING
                elif new_state == GoalStatus.PENDING:
                    self.send_request = True
                    self.logger.debug(f"Cancelling goal to {self.server_name}")
                    self.service_client_rl.cancel_all_goals()
                    self.client_result = None
                    self.logger.debug(f"Goal cancelled to {self.server_name}")
                    #self.service_client_rl.stop_tracking_goal()
                    #self.logger.debug(f"Goal tracking stopped to {self.server_name}")
                    new_status = py_trees.common.Status.RUNNING
                else:
                    new_status = py_trees.common.Status.FAILURE
                    raise
        else:
            new_status = py_trees.common.Status.SUCCESS
        self.logger.debug("%s.update()[%s]--->[%s]" % (self.__class__.__name__, self.status, new_status))
        return new_status

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

    def terminate(self, new_status):
        new_state = self.service_client_rl.get_state()
        print("terminate : ",new_state)
        if new_state == GoalStatus.SUCCEEDED or new_state == GoalStatus.ABORTED or new_state == GoalStatus.LOST:
            self.send_request = True
        if new_state == GoalStatus.PENDING:
            self.send_request = True
            self.logger.debug(f"Cancelling goal to {self.server_name}")
            self.service_client_rl.cancel_all_goals()
            self.client_result = None
            self.logger.debug(f"Goal cancelled to {self.server_name}")
            #self.service_client_rl.stop_tracking_goal()
            #self.logger.debug(f"Goal tracking stopped to {self.server_name}")
        self.logger.debug("%s.terminate()[%s->%s]" % (self.__class__.__name__, self.status, new_status))


def main():
    #command_line_argument_parser().parse_args()

    py_trees.logging.level = py_trees.logging.Level.DEBUG
    
    #rospy init node mi fa diventare un nodo ros
    rospy.init_node("rl_default", log_level=rospy.INFO)

    blackboard_input = py_trees.blackboard.Client(name=DialogueNameSpace.rl.name, namespace=DialogueNameSpace.rl.name)
    blackboard_input.register_key("result", access=py_trees.common.Access.READ)
    blackboard_scene = py_trees.blackboard.Client(name=PyTreeNameSpace.scene.name, namespace=PyTreeNameSpace.scene.name)
    blackboard_scene.register_key("rl", access=py_trees.common.Access.WRITE)
    blackboard_scene.register_key("exercise", access=py_trees.common.Access.WRITE)
    blackboard_scene.register_key("action", access=py_trees.common.Access.WRITE)
    blackboard_scene.rl = 0
    blackboard_scene.action = 1
    blackboard_scene.exercise = 4
    print(blackboard_input)

    rlPyTree = RLPytreeService("RLPytreeServiceTest")

    additional_parameters = dict([
        ("RLPytreeService_mode",False)])

    rlPyTree.setup(**additional_parameters)
    try:
        for unused_i in range(0, 5):
            rlPyTree.tick_once()
            time.sleep(2)
            print(blackboard_input)
        print("\n")
    except KeyboardInterrupt:
        print("Exception occurred")
        pass

if __name__ == "__main__":
    main()