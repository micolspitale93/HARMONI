#!/usr/bin/env python3

# Common Imports
import rospy
import roslib

from harmoni_common_lib.constants import *
from actionlib_msgs.msg import GoalStatus
from harmoni_common_lib.action_client import HarmoniActionClient
from harmoni_common_lib.constants import ActionType, PyTreeNameSpace, ActuatorNameSpace
#py_tree
import time
import py_trees
import py_trees.console

class GestureServicePytree(py_trees.behaviour.Behaviour):

    def __init__(self, name):
        self.name = name
        self.server_state = None
        self.service_client_gesture = None
        self.client_result = None
        self.send_request = True

        # here there is the inizialization of the blackboards
        self.blackboards = []
        self.blackboard_gesture = self.attach_blackboard_client(name=self.name, namespace=ActuatorNameSpace.gesture.name)
        self.blackboard_gesture.register_key("result", access=py_trees.common.Access.READ)
        super(GestureServicePytree, self).__init__(name)
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))

    def setup(self,**additional_parameters):
        self.service_client_gesture = HarmoniActionClient(self.name)
        self.server_name = "gesture_default"
        self.service_client_gesture.setup_client(self.server_name, 
                                            self._result_callback,
                                            self._feedback_callback)
        self.logger.debug("%s.setup()" % (self.__class__.__name__))

    def initialise(self):
        self.logger.debug("%s.initialise()" % (self.__class__.__name__))

    def update(self):    
        new_state = self.service_client_gesture.get_state()
        print(new_state)
        if self.send_request:
            self.send_request = False
            self.logger.debug(f"Sending goal to {self.server_name}")
            self.service_client_gesture.send_goal(
                action_goal = ActionType["DO"].value,
                optional_data = self.blackboard_gesture.result,
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
        new_state = self.service_client_gesture.get_state()
        print("terminate : ",new_state)
        if new_state == GoalStatus.SUCCEEDED or new_state == GoalStatus.ABORTED or new_state == GoalStatus.LOST:
            self.send_request = True
        if new_state == GoalStatus.PENDING:
            self.send_request = True
            self.logger.debug(f"Cancelling goal to {self.server_name}")
            self.service_client_gesture.cancel_all_goals()
            self.client_result = None
            self.logger.debug(f"Goal cancelled to {self.server_name}")
            #self.service_client_gesture.stop_tracking_goal()
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
    
    blackboard_gesture = py_trees.blackboard.Client(name=ActuatorNameSpace.gesture.name, namespace=ActuatorNameSpace.gesture.name)
    blackboard_gesture.register_key("result", access=py_trees.common.Access.WRITE)
    blackboard_gesture.result = "{'gesture':'QT/bye', 'timing': 0.5}"
   
    print(blackboard_gesture)

    rospy.init_node("gesture_default", log_level=rospy.INFO)

    gesturePyTree = GestureServicePytree("GestureServiceTest")
    gesturePyTree.setup()
    try:
        for unused_i in range(0, 5):
            gesturePyTree.tick_once()
            time.sleep(0.5)
            print(blackboard_gesture)
        print("\n")
    except KeyboardInterrupt:
        print("Exception occurred")
        pass

if __name__ == "__main__":
    main()