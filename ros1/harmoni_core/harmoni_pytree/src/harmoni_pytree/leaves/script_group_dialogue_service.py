#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import py_trees
import rospy
import json
import rospkg

from harmoni_common_lib.constants import *

class ScriptGroupDialogueService(py_trees.behaviour.Behaviour):
    def __init__(self, name, params):
        self.name = name
        self.blackboards = []
        self.script_name = params['interaction']
        self.session = params['session']
        self.user_names = params["user_names"].split(",")
        self.blackboard_scene = self.attach_blackboard_client(name=self.name, namespace=PyTreeNameSpace.scene.name)
        self.blackboard_scene.register_key(key="nlp", access=py_trees.common.Access.WRITE)
        self.blackboard_scene.register_key(key="max_number_scene", access=py_trees.common.Access.WRITE)
        self.blackboard_scene.register_key(key="utterance", access=py_trees.common.Access.WRITE)
        self.blackboard_scene.register_key(key="agent", access=py_trees.common.Access.WRITE)
    
        self.blackboard_bot = self.attach_blackboard_client(name=self.name, namespace=DialogueNameSpace.bot.name)
        self.blackboard_bot.register_key("result", access=py_trees.common.Access.READ)
        self.blackboard_stt = self.attach_blackboard_client(name=self.name, namespace=DetectorNameSpace.stt.name)
        self.blackboard_stt.register_key("result", access=py_trees.common.Access.READ)
        self.scene_number = 0
        self.max_number_scene = int(params.get("max_number_scene", 30))
        super(ScriptGroupDialogueService, self).__init__(name)
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))

    def setup(self):
        json_name = self.script_name
        rospack = rospkg.RosPack()
        pck_path = rospack.get_path("harmoni_pytree")
        pattern_script_path = pck_path + f"/resources/{json_name}.json"
        with open(pattern_script_path, "r") as read_file:
            self.context = json.load(read_file)
        self.blackboard_scene.max_number_scene = self.max_number_scene #MAXIMUM NUMBER OF TURNS
        self.blackboard_scene.utterance = self.context[self.session][0]["utterance"]
        self.blackboard_scene.nlp = self.context[self.session][0]["nlp"]
        self.blackboard_scene.agent = self.context[self.session][0]["agent"]
        print(self.blackboard_scene.agent)
        self.logger.debug("  %s [ScriptGroupDialogueService::setup()]" % self.name)

    def initialise(self):
        self.logger.debug("  %s [ScriptGroupDialogueService::initialise()]" % self.name)

    @staticmethod
    def format_user_utterance(text):
        """Wrap a user utterance in the format expected by the assistant service.

        repr() is used so that quotes contained in the transcription do not break the
        python literal parsed by the assistant (``ast.literal_eval``).
        """
        return repr(["*user* " + str(text)])

    def update(self):
        scenes = self.context[self.session]
        # Never index past the end of the script: stay on the closing scene
        scene = scenes[min(self.scene_number, len(scenes) - 1)]
        self.blackboard_scene.utterance = self.format_user_utterance(self.blackboard_stt.result)
        self.blackboard_scene.nlp = scene["nlp"]
        if self.scene_number == 1+int(self.session[0]):
            self.blackboard_scene.utterance = self.format_user_utterance("Now you can MUST START the discussion without telling your name.")
        if self.blackboard_scene.nlp==0:
            self.blackboard_scene.agent = scene["agent"]
            self.blackboard_scene.utterance = scene["utterance"]
        rospy.loginfo("============ THE UTTERANCE ARRIVED IS:")
        rospy.loginfo(self.blackboard_scene.utterance)
        if self.scene_number == self.blackboard_scene.max_number_scene:
            self.blackboard_scene.nlp = 0
            self.blackboard_scene.utterance = self.context[self.session][-1]["utterance"]
        i=0
        for name in self.user_names:
            i+=1
            self.blackboard_scene.utterance = self.blackboard_scene.utterance.replace("$USERNAME"+str(i), name)
        self.scene_number +=1
        return py_trees.common.Status.SUCCESS

    def terminate(self, new_status):
        """
        if new_status == py_trees.common.Status.INVALID:
            self.scene_counter = 0
        """
        self.logger.debug("  %s [ScriptGroupDialogueService::terminate().terminate()][%s->%s]" % (self.name, self.status, new_status))
