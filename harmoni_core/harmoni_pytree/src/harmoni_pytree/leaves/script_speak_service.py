#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import py_trees
import rospy
import json
import os
import rospkg

from harmoni_common_lib.constants import *

class ScriptSpeakService(py_trees.behaviour.Behaviour):
    def __init__(self, name, params):
        self.name = name
        self.user_name=params['user_name']
        self.researcher_name=params['researcher_name']
        self.script_name = params['interaction']
        self.session = params['session']
        self.scene = params['scene']
        self.blackboards = []
        self.blackboard_scene = self.attach_blackboard_client(name=self.name, namespace=PyTreeNameSpace.scene.name)
        self.blackboard_scene.register_key(key="nlp", access=py_trees.common.Access.WRITE)
        self.blackboard_scene.register_key(key="utterance", access=py_trees.common.Access.WRITE)
        self.blackboard_bot = self.attach_blackboard_client(name=self.name, namespace=DialogueNameSpace.bot.name)
        self.blackboard_bot.register_key("result", access=py_trees.common.Access.WRITE)
        #self.blackboard_stt = self.attach_blackboard_client(name=self.name, namespace=DetectorNameSpace.stt.name)
        #self.blackboard_stt.register_key("result", access=py_trees.common.Access.READ)
        
        super(ScriptSpeakService, self).__init__(name)
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))

    def setup(self):
        self.blackboard_scene.nlp = 1
        self.blackboard_scene.utterance = "Ciao!"
        json_name = self.script_name
        rospack = rospkg.RosPack()
        pck_path = rospack.get_path("harmoni_pytree")
        pattern_script_path = pck_path + f"/resources/{json_name}.json"
        with open(pattern_script_path, "r") as read_file:
            self.context = json.load(read_file)
        self.blackboard_scene.utterance = self.context[self.session][0]["utterance"]
        self.blackboard_bot.result = {'message' : self.blackboard_scene.utterance}
        self.logger.debug("  %s [ScriptSpeakService::setup()]" % self.name)

    def initialise(self):
        self.logger.debug("  %s [ScriptSpeakService::initialise()]" % self.name)

    def update(self):
        rospy.loginfo("============ THE UTTERANCE ARRIVED IS:")
        self.scene = self.scene + 1
        self.blackboard_bot.result = {'message' : self.blackboard_scene.utterance}
        if self.scene == len(self.context[self.session]):
            self.blackboard_scene.utterance = self.context[self.session][len(self.context[self.session])]["utterance"]
        else:
            self.blackboard_scene.utterance = self.context[self.session][self.scene]["utterance"]
        rospy.loginfo(self.blackboard_scene.utterance)
        return py_trees.common.Status.SUCCESS

    def terminate(self, new_status):
        """
        if new_status == py_trees.common.Status.INVALID:
            self.scene_counter = 0
        """
        self.logger.debug("  %s [ScriptService::terminate().terminate()][%s->%s]" % (self.name, self.status, new_status))
