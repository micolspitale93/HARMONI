#!/usr/bin/env python3


PKG = "test_harmoni_cam_openface"
# Common Imports
import unittest, rospy, roslib, sys
import traceback

# Specific Imports
from harmoni_common_lib.constants import *
import ast
import time

#py_tree
import py_trees
from harmoni_pytree.subtrees.camera_and_openface import *

class TestCamAndOpenFacePyTree(unittest.TestCase):

    def setUp(self):

        rospy.init_node("test_cam_openface", log_level=rospy.INFO)
        self.instance_id = rospy.get_param("instance_id")
        
        # NOTE currently no feedback, status, or result is received.
        py_trees.logging.level = py_trees.logging.Level.DEBUG
        
        
        # blackboard for test-to-speech data, which is updated after result is fetched
        self.blackboard_openface = py_trees.blackboard.Client(name="blackboard_openface", namespace=DetectorNameSpace.openface.name)
        self.blackboard_openface.register_key("result", access=py_trees.common.Access.WRITE)


        self.root = create_root()
        self.tree = py_trees.trees.BehaviourTree(self.root)
        self.tree.setup(timeout=15)
        self.success = False

        rospy.loginfo("Setup completed....starting test")

   
    def test_cam_openface(self):
        rospy.loginfo(f"Starting to tick")
        try:
            for unused_i in range(0, 10):
                self.tree.tick()
                time.sleep(1)
                print(self.blackboard_openface)
                print("Tick number: ", unused_i)

        except Exception:
            assert self.root.status==py_trees.common.Status.SUCCESS
            print(traceback.format_exc())

        assert self.root.status==py_trees.common.Status.SUCCESS

        return
    

def main():
    import rostest
    rospy.loginfo("test_cam_openface started")
    rospy.loginfo("TestCamAndOpenFace: sys.argv: %s" % str(sys.argv))
    rostest.rosrun(PKG, "test_camera_openface_pytree", TestCamAndOpenFacePyTree, sys.argv)


if __name__ == "__main__":
    main()