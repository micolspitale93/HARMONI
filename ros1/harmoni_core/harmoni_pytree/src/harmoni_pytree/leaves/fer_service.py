#!/usr/bin/env python3

# Common Imports
import rospy

from harmoni_common_lib.constants import *
from actionlib_msgs.msg import GoalStatus
from harmoni_common_lib.service_server import HarmoniServiceServer
from harmoni_common_lib.service_manager import HarmoniServiceManager
from harmoni_common_lib.action_client import HarmoniActionClient
import harmoni_common_lib.helper_functions as hf

# Specific Imports
from harmoni_common_lib.constants import DetectorNameSpace, ActionType
from sensor_msgs.msg import Image
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
from collections import deque 
import numpy as np
import boto3
import re
import json
import ast
import sys

#py_tree
import py_trees
import time

import py_trees.console

class FERServicePytree(py_trees.behaviour.Behaviour):

    def __init__(self, name = "FERServicePytree"):
        self.name = name
        self.server_state = None
        self.service_client_fer = None
        self.client_result = None
        self.server_name = None
        self.send_request = True

        self.blackboards = []
        self.blackboard_fer = self.attach_blackboard_client(name=self.name, namespace=DetectorNameSpace.fer.name)
        self.blackboard_fer.register_key("result", access=py_trees.common.Access.WRITE)
        super(FERServicePytree, self).__init__(name)
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))

    def setup(self,**additional_parameters):    
        self.service_client_fer = HarmoniActionClient(self.name)
        self.server_name = DetectorNameSpace.fer.value + "default"
        self.service_client_fer.setup_client(self.server_name, 
                                            self._result_callback,
                                            self._feedback_callback,
                                            wait = True)
        self.logger.debug("Behavior %s interface action clients have been set up!" % (self.server_name))
        self.service_client_fer.send_goal(
                action_goal = ActionType.ON,
                optional_data="Setup",
                wait=False,
            )
        self.logger.debug("%s.setup()" % (self.__class__.__name__))

    def initialise(self):
        self.logger.debug("%s.initialise()" % (self.__class__.__name__))

    def update(self):
        new_state = self.service_client_fer.get_state()
        rospy.loginfo(new_state)
        if new_state == GoalStatus.ACTIVE:
            new_status = py_trees.common.Status.RUNNING
        elif new_state == GoalStatus.SUCCEEDED:
                new_status = py_trees.common.Status.SUCCESS
        elif new_state == GoalStatus.PENDING:
            new_status = py_trees.common.Status.RUNNING
        elif new_state == GoalStatus.ABORTED:
            new_status = py_trees.common.Status.SUCCESS
        else:
            new_status = py_trees.common.Status.FAILURE
        self.blackboard_fer.result = new_status
        self.logger.debug("%s.update()[%s]--->[%s]" % (self.__class__.__name__, self.status, new_status))
        return new_status
        
    def terminate(self, new_status):
        new_state = self.service_client_fer.get_state()
        print("terminate : ",new_state)
        if new_state == GoalStatus.SUCCEEDED or new_state == GoalStatus.ABORTED or new_state == GoalStatus.LOST:
            self.send_request = True
        if new_state == GoalStatus.PENDING:
            self.send_request = True
            self.logger.debug(f"Cancelling goal to {self.server_name}")
            self.service_client_service_client_fer.cancel_all_goals()
            self.client_result = None
            self.logger.debug(f"Goal cancelled to {self.server_name}")
            #self.service_client_fer.stop_tracking_goal()
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
        self.server_state = feedback
        return

def main():
    #command_line_argument_parser().parse_args()
    py_trees.logging.level = py_trees.logging.Level.DEBUG
    
    #rospy init node mi fa diventare un nodo ros
    rospy.init_node("fer_default", log_level=rospy.INFO)

    blackboard_output = py_trees.blackboard.Client(name=DetectorNameSpace.fer.name, namespace=DetectorNameSpace.fer.name)
    blackboard_output.register_key("result", access=py_trees.common.Access.READ)
    print(blackboard_output)

    ferPyTree = FERServicePytree("FERServicePytreeTest")

    additional_parameters = dict([
        ("FERServicePytree_mode",False)])

    ferPyTree.setup(**additional_parameters)
    try:
        for unused_i in range(0, 5):
            ferPyTree.tick_once()
            time.sleep(2)
            print(blackboard_output)
        print("\n")
    except KeyboardInterrupt:
        print("Exception occurred")
        pass

if __name__ == "__main__":
    main()