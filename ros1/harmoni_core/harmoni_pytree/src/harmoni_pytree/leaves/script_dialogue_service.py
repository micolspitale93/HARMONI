#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import py_trees
import rospy

from harmoni_common_lib.constants import *

class ScriptDialogueService(py_trees.behaviour.Behaviour):
    # TODO : NEED TO DEFINE WHAT IS THE SCRIPT DOING. SETTING THE NLP FOR THE AGENT WHETHER 2 (SKIP THE AGENT) OR 1. 
    def __init__(self, name):
        self.name = name
        self.blackboards = []
        self.blackboard_scene = self.attach_blackboard_client(name=self.name, namespace=PyTreeNameSpace.scene.name)
        self.blackboard_scene.register_key(key="nlp", access=py_trees.common.Access.WRITE)
        self.blackboard_scene.register_key(key="utterance", access=py_trees.common.Access.WRITE)
        self.blackboard_bot = self.attach_blackboard_client(name=self.name, namespace=DialogueNameSpace.bot.name)
        self.blackboard_bot.register_key("result", access=py_trees.common.Access.READ)
        self.blackboard_stt = self.attach_blackboard_client(name=self.name, namespace=DetectorNameSpace.stt.name)
        self.blackboard_stt.register_key("result", access=py_trees.common.Access.READ)
        
        super(ScriptDialogueService, self).__init__(name)
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))

    def setup(self):
        
        self.blackboard_scene.nlp = 1
        self.blackboard_scene.utterance = ""
        self.logger.debug("  %s [ScriptDialogueService::setup()]" % self.name)

    def initialise(self):
        self.logger.debug("  %s [ScriptDialogueService::initialise()]" % self.name)

    def update(self):
        if self.blackboard_stt.result!="":
            self.blackboard_scene.utterance =  "['*user* "+self.blackboard_stt.result+"']"
        else:
            self.blackboard_scene.utterance = ""
        rospy.loginfo("============ THE UTTERANCE ARRIVED IS:")
        rospy.loginfo(self.blackboard_scene.utterance)
        return py_trees.common.Status.SUCCESS

    def terminate(self, new_status):
        """
        if new_status == py_trees.common.Status.INVALID:
            self.scene_counter = 0
        """
        self.logger.debug("  %s [ScriptService::terminate().terminate()][%s->%s]" % (self.name, self.status, new_status))
