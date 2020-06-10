#!/usr/bin/env python3

# Importing the libraries
import rospy
import roslib
from harmoni_common_lib.action_client import HarmoniActionClient
from harmoni_common_lib.service_manager import HarmoniServiceManager
from harmoni_common_lib.constants import *
from collections import defaultdict

# The main pattern will act as a service
# subscriptions do not need to be dynamic
class BehaviorPatternService(HarmoniServiceManager, object):
    """Abstract class defining common variables/functions for behavior patterns
    """

    def __init__(self, result_callback, feedback_callback):
        """Setup the Behavior Pattern as a client of all the routers """
        self.state = State.INIT
        super().__init__(self.state)
        self.router_names = [enum.value for enum in list(Router)]
        print(self.router_names)
        self.router_clients = defaultdict(HarmoniActionClient)
        for rout in self.router_names:
            self.router_clients[rout] = HarmoniActionClient()
        for rout, client in self.router_clients.items():
            client.setup_client(rout, result_callback, feedback_callback)
        rospy.loginfo("Behavior interface action clients have been set up")

    def start(self, action_goal, child_server, router, optional_data):
        """Start the Behavior Pattern sending the first goal to the child"""
        self.state = State.START
        rate = ""
        super().start(rate)
        #try:
        self.state = State.REQUEST
        rospy.loginfo("Sending the goal to the router %s" %router)
        self.router_clients[router].send_goal(action_goal=action_goal, optional_data=optional_data, child_server=child_server)
        self.state = State.SUCCESS
        rospy.loginfo("Sent the goal %s" %action_goal)
        #except:
        #    self.state = State.FAILED
        return

    def stop(self, router):
        """Stop the Behavior Pattern """
        super().stop()
        try:
            self.router_clients[router].cancel_goal()
            self.state = State.SUCCESS
        except:
            self.state = State.FAILED
        return

    def pause(self):
        """Pause the Behavior Pattern """
        super().pause()
        return

    def update(self, state):
        super().update(state)
        return

