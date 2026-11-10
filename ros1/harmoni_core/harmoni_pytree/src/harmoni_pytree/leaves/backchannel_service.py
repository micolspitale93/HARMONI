#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import py_trees
import rospkg
import random
import rospy

from harmoni_common_lib.constants import *

class BackchannelService(py_trees.behaviour.Behaviour):
    def __init__(self, name, params):
        self.name = name
        self.user_name=params['user_name']
        self.script_name = params['interaction']
        self.session = params['session']
        self.blackboards = []
        self.blackboard_scene = self.attach_blackboard_client(name=self.name, namespace=PyTreeNameSpace.scene.name)
        self.blackboard_scene.register_key(key="gesture", access=py_trees.common.Access.WRITE)
        self.blackboard_scene.register_key(key=PyTreeNameSpace.scene.name+"/max_number_scene", access=py_trees.common.Access.READ)
        self.blackboard_scene.register_key(key=PyTreeNameSpace.scene.name+"/scene_counter", access=py_trees.common.Access.READ)
        self.blackboard_scene.register_key(key=PyTreeNameSpace.scene.name+"/scene_end", access=py_trees.common.Access.READ)
        self.blackboard_bot = self.attach_blackboard_client(name=self.name, namespace=DialogueNameSpace.bot.name+"/"+PyTreeNameSpace.trigger.name)
        self.blackboard_bot.register_key("result", access=py_trees.common.Access.WRITE)
        super(BackchannelService, self).__init__(name)
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))

    def setup(self):
        #this is the name of the json without the extension
        json_name = self.script_name
        rospack = rospkg.RosPack()
        pck_path = rospack.get_path("harmoni_pytree")
        pattern_script_path = pck_path + f"/resources/{json_name}.json"
        with open(pattern_script_path, "r") as read_file:
            self.context = json.load(read_file)
        self.logger.debug("  %s [BackchannelService::setup()]" % self.name)

    def initialise(self):
        self.logger.debug("  %s [BackchannelService::initialise()]" % self.name)

    def update(self):
        self.logger.debug("  %s [BackchannelService::update()]" % self.name)
        utterance = self.context[self.session][self.blackboard_scene.scene.scene_counter]["sound"]
        gesture = self.context[self.session][self.blackboard_scene.scene.scene_counter]["back_channel"]
        rospy.sleep(1)
        if self.blackboard_scene.scene.scene_counter == 0:
                self.blackboard_bot.result = {
                                                                "message":   utterance
                                            }
                self.blackboard_scene.gesture = gesture
        elif self.blackboard_scene.scene.scene_end == "end":
            return py_trees.common.Status.FAILURE
        elif self.blackboard_scene.scene.scene_end == "call_researcher":
            return py_trees.common.Status.FAILURE
        else:
                self.blackboard_bot.result = {
                                                                "message":  utterance
                                            }
                self.blackboard_scene.gesture = gesture
        return py_trees.common.Status.SUCCESS

    def terminate(self, new_status):
        """
        if new_status == py_trees.common.Status.INVALID:
            self.scene_counter = 0
        """
        self.logger.debug("  %s [BackchannelService::terminate().terminate()][%s->%s]" % (self.name, self.status, new_status))