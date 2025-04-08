#!/usr/bin/env python3
##############################################################################
# Imports
##############################################################################

import argparse
import functools
from py_trees.behaviours import dummy
from py_trees.idioms import either_or
import py_trees
import time
import rospy
from random import randint
import subprocess
import operator
import py_trees.console as console

from harmoni_common_lib.constants import *

from harmoni_pytree.leaves.sd_azure_service import DiarSpeechToTextServicePytree
from harmoni_pytree.leaves.assistant_service import AssistantServicePytree
from harmoni_pytree.leaves.speaker_service import SpeakerServicePytree
from harmoni_pytree.leaves.script_group_dialogue_service import ScriptGroupDialogueService

##############################################################################
# Classes
##############################################################################


def description(root):
    content = "\n\n"
    content += "\n"
    content += "EVENTS\n"
    if py_trees.console.has_colours:
        banner_line = console.green + "*" * 79 + "\n" + console.reset
        s = "\n"
        s += banner_line
        s += console.bold_white + "Test".center(79) + "\n" + console.reset
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
    parser = argparse.ArgumentParser(description=description(create_root()),
                                     epilog=epilog(),
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     )
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-b', '--with-blackboard-variables', default=False, action='store_true', help='add nodes for the blackboard variables')
    group.add_argument('-r', '--render', action='store_true', help='render dot tree to file')
    group.add_argument('-i', '--interactive', action='store_true', help='pause and wait for keypress at each tick')
    return parser


def pre_tick_handler(behaviour_tree):
    print("\n--------- Run %s ---------\n" % behaviour_tree.count)


def post_tick_handler(snapshot_visitor, behaviour_tree):
    print(
        "\n" + py_trees.display.unicode_tree(
            root=behaviour_tree.root,
            visited=snapshot_visitor.visited,
            previously_visited=snapshot_visitor.previously_visited
        )
    )
    print(py_trees.display.unicode_blackboard())


def create_root(name= "GroupInteraction", params=""):
    diar_stt=DiarSpeechToTextServicePytree("Diarization")
    script = ScriptGroupDialogueService("Script", params=params)
    bot = AssistantServicePytree('LLM Assistant')
    speaker_1 = SpeakerServicePytree(name = 'Mover', instance_id = 'furhat')
    speaker_2 = SpeakerServicePytree(name = 'Opposer', instance_id = 'nao')
    agent_selector = py_trees.composites.Selector(name="Agent Selector", memory=True)
    agent_selector.add_children([speaker_1, speaker_2])
    root = py_trees.composites.Sequence(name="GroupInteraction",memory=True)
    root.add_children([script, bot, agent_selector, diar_stt])
    return root


##############################################################################
# Main
##############################################################################
def main():
    """
    Entry point for the demo script.
    """
    py_trees.logging.level = py_trees.logging.Level.DEBUG
    params = rospy.get_param("pytree/default_param/")
    root =create_root(params=params)

    print("########################################################")

    print(description(root))
        
    ####################
    # Tree Stewardship
    ####################

    rospy.init_node("test_default", log_level=rospy.INFO)
    
    behaviour_tree = py_trees.trees.BehaviourTree(root)
    print(py_trees.display.unicode_tree(root=root))

    behaviour_tree.add_pre_tick_handler(pre_tick_handler)
    #behaviour_tree.visitors.append(py_trees.visitors.DebugVisitor())
    snapshot_visitor = py_trees.visitors.SnapshotVisitor()
    behaviour_tree.visitors.append(snapshot_visitor)
    behaviour_tree.add_post_tick_handler(functools.partial(post_tick_handler, snapshot_visitor))
    
    behaviour_tree.setup(timeout=15)

    ####################
    # Tick Tock
    ####################

    try:
        behaviour_tree.tick_tock(
            period_ms=500,
            number_of_iterations=py_trees.trees.CONTINUOUS_TICK_TOCK,
        )
    except KeyboardInterrupt:
        behaviour_tree.interrupt()
    print("\n")

if __name__ == "__main__":
    main()   
