#!/usr/bin/env python3
##############################################################################
# Imports
##############################################################################
import rospy
from harmoni_tts.aws_tts_service_pytree import AWSTtsServicePytree
from harmoni_bot.aws_lex_service_pytree import AWSLexServicePytree
from harmoni_speaker.speaker_service_pytree import SpeakerServicePytree
from harmoni_face.face_service_pytree import FaceServicePytree
import argparse
import py_trees
import sys
import time

import py_trees.console as console

##############################################################################
# Classes
##############################################################################


def description():
    content = "Demonstrates sequences in action.\n\n"
    content += "A sequence is populated with 2-tick jobs that are allowed to run through to\n"
    content += "completion.\n"

    if py_trees.console.has_colours:
        banner_line = console.green + "*" * 79 + "\n" + console.reset
        s = "\n"
        s += banner_line
        s += console.bold_white + "Sequences".center(79) + "\n" + console.reset
        s += banner_line
        s += "\n"
        s += content
        s += "\n"
        s += banner_line
    else:
        s = content
    return s


def epilog():
    if py_trees.console.has_colours:
        return console.cyan + "And his noodly appendage reached forth to tickle the blessed...\n" + console.reset
    else:
        return None


def command_line_argument_parser():
    parser = argparse.ArgumentParser(description=description(),
                                     epilog=epilog(),
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     )
    parser.add_argument('-r', '--render', action='store_true', help='render dot tree to file')
    return parser


def create_root():
    root = py_trees.composites.Sequence("Sequence")
    tts = AWSTtsServicePytree("AwsTtsPyTreeTest")
    chatbot = AWSLexServicePytree("AwsLexPyTreeTest")
    speaker = SpeakerServicePytree("SpeakerPyTreeTest")
    face = FaceServicePytree("FacePyTreeTest")
    parall_speaker_face = py_trees.composites.Parallel("Parallel")
    root.add_child(chatbot)
    root.add_child(tts)
    root.add_child(parall_speaker_face)
    parall_speaker_face.add_child(speaker)
    parall_speaker_face.add_child(face)
    return root


##############################################################################
# Main
##############################################################################

def main():
    """
    Entry point for the demo script.
    """
    rospy.init_node("prova_nodo", log_level=rospy.INFO)

    args = command_line_argument_parser().parse_args()
    print(description())
    py_trees.logging.level = py_trees.logging.Level.DEBUG

    root = create_root()

    ####################
    # Tree Stewardship
    ####################
    print("Tree Stewardship")
    behaviour_tree = py_trees.trees.BehaviourTree(root)
    behaviour_tree.visitors.append(py_trees.visitors.DebugVisitor())
    behaviour_tree.visitors.append(py_trees.visitors.SnapshotVisitor())
    additional_parameters = dict([
        ("AWSTtsServicePytree_mode",False),
        ("SpeakerServicePytree_mode",False),
        ("FaceServicePytree_mode",True),
        ("AWSLexServicePytree_mode",True)])
    behaviour_tree.setup(timeout=15,**additional_parameters)

    print(py_trees.display.unicode_tree(root=root))
    
    ####################
    # Execute
    ####################
    
    blackboardProvaIn = py_trees.blackboard.Client(name="blackboardProva", namespace="harmoni_input_bot")
    blackboardProvaIn.register_key("result_data", access=py_trees.common.Access.WRITE)
    blackboardProvaIn.register_key("result_message", access=py_trees.common.Access.WRITE)
    blackboardProvaIn.result_message = "SUCCESS"
    blackboardProvaIn.result_data = "Vorrei ordinare dei fiori"

    def print_tree(tree):
        print(py_trees.display.unicode_tree(root=tree.root, show_status=True))
        
    try:
        for i in range(1, 12):
            print("\n--------- Tick {0} ---------\n".format(i))
            behaviour_tree.tick(
                pre_tick_handler=None,
                post_tick_handler=print_tree
            )
            time.sleep(1.0)
            if behaviour_tree.root.status ==  py_trees.common.Status.SUCCESS:
                break
    except KeyboardInterrupt:
        behaviour_tree.interrupt()

if __name__ == "__main__":
    main()