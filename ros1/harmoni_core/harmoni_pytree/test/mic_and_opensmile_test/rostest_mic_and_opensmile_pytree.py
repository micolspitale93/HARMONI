#!/usr/bin/env python3


PKG = "test_harmoni_mic_opensmile"
# Common Imports
import unittest, rospy, roslib, sys
import traceback

# Specific Imports
from harmoni_common_lib.constants import *
import ast
import time

#py_tree
import py_trees
from harmoni_pytree.subtrees.mic_and_opensmile import *

class TestMicAndOpenSmilePyTree(unittest.TestCase):

    def setUp(self):

        rospy.init_node("test_mic_opensmile", log_level=rospy.INFO)
        self.instance_id = rospy.get_param("instance_id")
        
        # NOTE currently no feedback, status, or result is received.
        py_trees.logging.level = py_trees.logging.Level.DEBUG
        
        
        # blackboard for test-to-speech data, which is updated after result is fetched
        self.blackboard_opensmile = py_trees.blackboard.Client(name="blackboard_opensmile", namespace=DetectorNameSpace.opensmile.name)
        self.blackboard_opensmile.register_key("result", access=py_trees.common.Access.WRITE)


        self.root = create_root()
        self.tree = py_trees.trees.BehaviourTree(self.root)
        self.tree.setup(timeout=15)
        self.success = False

        rospy.loginfo("Setup completed....starting test")

   
    def test_mic_opensmile(self):
        rospy.loginfo(f"Starting to tick")
        try:
            for unused_i in range(0, 5):
                self.tree.tick()
                time.sleep(1)
                print(self.blackboard_opensmile)
                rospy.loginfo(self.blackboard_opensmile)
                print("Tick number: ", unused_i)

        except Exception:
            assert self.root.status==py_trees.common.Status.SUCCESS
            print(traceback.format_exc())

        assert self.root.status==py_trees.common.Status.SUCCESS

        return
    

def main():
    import rostest
    rospy.loginfo("test_mic_opensmile started")
    rospy.loginfo("TestMicAndOpenSmile: sys.argv: %s" % str(sys.argv))
    rostest.rosrun(PKG, "test_mic_opensmile_pytree", TestMicAndOpenSmilePyTree, sys.argv)


if __name__ == "__main__":
    main()