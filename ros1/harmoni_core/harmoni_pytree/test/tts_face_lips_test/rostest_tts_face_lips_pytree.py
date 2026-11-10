#!/usr/bin/env python3


PKG = "test_harmoni_tts_face_lips"
# Common Imports
import unittest, rospy, roslib, sys
import traceback

# Specific Imports
from harmoni_common_lib.constants import *
import ast
import time

#py_tree
import py_trees
from harmoni_pytree.subtrees.tts_face_lips import *

class TestTtsAndFaceLipsPyTree(unittest.TestCase):

    def setUp(self):

        rospy.init_node("test_tts_face_lips", log_level=rospy.INFO)
        self.instance_id = rospy.get_param("instance_id")
        
        # NOTE currently no feedback, status, or result is received.
        py_trees.logging.level = py_trees.logging.Level.DEBUG
        
        
        # blackboard for test-to-speech data, which is updated after result is fetched
        self.blackboard_tts = py_trees.blackboard.Client(name="output_tts", namespace=ActuatorNameSpace.tts.name)
        self.blackboard_tts.register_key("result", access=py_trees.common.Access.READ) 
        self.blackboard_scene = py_trees.blackboard.Client(name="scene", namespace=PyTreeNameSpace.scene.name)
        self.blackboard_scene.register_key(key="nlp", access=py_trees.common.Access.WRITE)
        self.blackboard_face = py_trees.blackboard.Client(name="face", namespace=ActuatorNameSpace.face.name)
        self.blackboard_face.register_key(key="face_exp", access=py_trees.common.Access.WRITE)
        self.blackboard_scene.nlp = 1
        self.blackboard_face.face_exp = "[ {'start': 8, 'type': 'viseme', 'id': 'POSTALVEOLAR'}]"
        self.blackboard_input_tts = py_trees.blackboard.Client(name="input_tts", namespace=DialogueNameSpace.bot.name)
        self.blackboard_input_tts.register_key("result", access=py_trees.common.Access.WRITE)
        self.blackboard_input_tts.result = {"message":"Hello, my name is Botty!"}
        self.root = create_root()
        self.tree = py_trees.trees.BehaviourTree(self.root)
        self.tree.setup(timeout=15)
        print("++++++++++++++++++++")
        print(self.tree)
        self.success = False

        rospy.loginfo("Setup completed....starting test")

   
    def test_tts_face_lips(self):
        rospy.loginfo(f"Starting to tick")
        try:
            self.tree.tick_tock(period_ms=500, number_of_iterations=3)
            time.sleep(1)
            print(self.blackboard_tts)
            print(self.blackboard_scene)
            print(self.blackboard_input_tts)

        except Exception:
            print(traceback.format_exc())
            assert self.root.status==py_trees.common.Status.SUCCESS
        return
    

def main():
    import rostest
    rospy.loginfo("test_tts_face_lips started")
    rospy.loginfo("TestTtsAndFaceLips: sys.argv: %s" % str(sys.argv))
    rostest.rosrun(PKG, "test_tts_face_lips_pytree", TestTtsAndFaceLipsPyTree, sys.argv)


if __name__ == "__main__":
    main()