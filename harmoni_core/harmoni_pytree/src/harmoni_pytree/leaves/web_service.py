#!/usr/bin/env python3

# Common Imports
import rospy

from harmoni_common_lib.action_client import HarmoniActionClient
from actionlib_msgs.msg import GoalStatus
from harmoni_common_lib.constants import PyTreeNameSpace, DetectorNameSpace, ActuatorNameSpace, ActionType
from harmoni_common_lib.constants import *
# Specific Imports
import time
import py_trees

class WebServicePytree(py_trees.behaviour.Behaviour):
    def __init__(self, name = "WebServicePytree", color="red"):
        
        self.name = name
        self.service_client_web = None
        self.server_state = None
        self.server_name = None
        self.client_result = None
        self.old_state = None
        self.image = ""
        self.color = color
        self.send_request = True
        self.blackboards = []
        #self.blackboard_web = self.attach_blackboard_client(name=self.name, namespace=ActuatorNameSpace.web.name)
        #self.blackboard_web.register_key("image", access=py_trees.common.Access.READ)
        super(WebServicePytree, self).__init__(name)
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))

    def setup(self,**additional_parameters):
        
        self.service_client_web = HarmoniActionClient(self.name)
        self.server_name = "web_default"
        self.service_client_web.setup_client(self.server_name,
                                            self._result_callback,
                                            self._feedback_callback)
        self.logger.debug("Behavior %s interface action clients have been set up!" % (self.server_name))
        
        self.logger.debug("%s.setup()" % (self.__class__.__name__))

    def initialise(self): 
        self.logger.debug("%s.initialise()" % (self.__class__.__name__))

    def update(self):
        if self.color == "green":
            _image = "{'component_id':'display_color', 'set_content': 'green'}"
        else: 
            _image = "{'component_id':'display_color', 'set_content': 'red'}"
        if self.send_request:
            self.send_request = False
            self.logger.debug(f"Sending goal to {self.server_name}")
            self.service_client_web.send_goal(
                action_goal = ActionType["DO"].value,
                optional_data = _image,
                wait=False,
            )
            self.logger.debug(f"Goal sent to {self.server_name}")
            new_status =  py_trees.common.Status.RUNNING
        else:
            new_state = self.service_client_web.get_state()
            print(new_state)
            if new_state == GoalStatus.ACTIVE:
                new_status = py_trees.common.Status.SUCCESS
            elif new_state == GoalStatus.SUCCEEDED:
                new_status = py_trees.common.Status.SUCCESS
            elif new_state == GoalStatus.PENDING:
                self.send_request = True
                self.logger.debug(f"Cancelling goal to {self.server_name}")
                self.service_client_web.cancel_all_goals()
                self.client_result = None
                self.logger.debug(f"Goal cancelled to {self.server_name}")
                #self.service_client_web.stop_tracking_goal()
                #self.logger.debug(f"Goal tracking stopped to {self.server_name}")
                new_status = py_trees.common.Status.RUNNING
            else:
                new_status = py_trees.common.Status.FAILURE
                raise

        self.logger.debug("%s.update()[%s]--->[%s]" % (self.__class__.__name__, self.status, new_status))
        return new_status

    def terminate(self, new_status):
        """
        new_state = self.service_client_web.get_state()
        print("terminate : ",new_state)
        if new_state == GoalStatus.SUCCEEDED or new_state == GoalStatus.ABORTED or new_state == GoalStatus.LOST:
            self.send_request = True
        if new_state == GoalStatus.PENDING:
            self.send_request = True
            self.logger.debug(f"Cancelling goal to {self.server_name}")
            self.service_client_web.cancel_all_goals()
            self.client_result = None
            self.logger.debug(f"Goal cancelled to {self.server_name}")
            self.service_client_web.stop_tracking_goal()
            self.logger.debug(f"Goal tracking stopped to {self.server_name}")
        """
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
    
    rospy.init_node("web_default" , log_level=rospy.INFO)

    blackboard_web = py_trees.blackboard.Client(name=ActuatorNameSpace.web.name, namespace=ActuatorNameSpace.web.name)
    blackboard_web.register_key("image", access=py_trees.common.Access.WRITE)
    print(blackboard_web)

    blackboard_web.image = "[{'component_id':'img_only', 'set_content':'https://www.google.it/images/branding/googlelogo/2x/googlelogo_color_160x56dp.png'},{'component_id':'raccolta_container', 'set_content': ''}]"

    webPyTree = WebServicePytree("WebServicePytreeTest")

    additional_parameters = dict([
        ("WebServicePytree_mode",False)])

    webPyTree.setup(**additional_parameters)
    try:
        for unused_i in range(0, 5):
            webPyTree.tick_once()
            print(blackboard_web)
            time.sleep(0.5)
        print("\n")
    except KeyboardInterrupt:
        print("Exception occurred")
        pass

if __name__ == "__main__":
    main()