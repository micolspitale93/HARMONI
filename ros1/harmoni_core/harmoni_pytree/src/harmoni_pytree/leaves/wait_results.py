#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from harmoni_common_lib.constants import *
import py_trees
import random
import rospy


class WaitResults(py_trees.behaviour.Behaviour):
    def __init__(self, name):
        self.name = name
        self.blackboards = []
        self.blackboard_scene = self.attach_blackboard_client(name=self.name, namespace=PyTreeNameSpace.scene.name)
        self.blackboard_scene.register_key(key=PyTreeNameSpace.scene.name+"/scene_end", access=py_trees.common.Access.WRITE)
        self.blackboard_scene.register_key(key=PyTreeNameSpace.scene.name+"/max_number_scene", access=py_trees.common.Access.READ)
        self.blackboard_scene.register_key(key=PyTreeNameSpace.scene.name+"/scene_counter", access=py_trees.common.Access.WRITE)
        super(WaitResults, self).__init__(name)
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))
        
    def setup(self):
        self.blackboard_scene.scene.scene_counter = 0
        self.blackboard_scene.scene.scene_end = ''
        self.logger.debug("  %s [WaitResults::setup()]" % self.name)

    def initialise(self):
        self.logger.debug("  %s [WaitResults::initialise()]" % self.name)

    def update(self):
        self.logger.debug("  %s [WaitResults::update()]" % self.name)
        if self.blackboard_scene.scene.scene_counter < self.blackboard_scene.scene.max_number_scene -1:
            rospy.sleep(10)
            self.blackboard_scene.scene.scene_counter+=1
        else:
            self.blackboard_scene.scene.scene_end = 'end'
        
        return py_trees.common.Status.SUCCESS

    def terminate(self, new_status):
        self.logger.debug("  %s [WaitResults::terminate().terminate()][%s->%s]" % (self.name, self.status, new_status))
