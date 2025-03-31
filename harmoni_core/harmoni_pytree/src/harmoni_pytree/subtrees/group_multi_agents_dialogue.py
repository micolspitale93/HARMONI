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

from harmoni_pytree.leaves.microphone_service import MicrophoneServicePytree
from harmoni_pytree.leaves.sd_azure_service import DiarSpeechToTextServicePytree
from harmoni_pytree.leaves.google_service import SpeechToTextServicePytree
from harmoni_pytree.leaves.chat_gpt_service import ChatGPTServicePytree
from harmoni_pytree.leaves.aws_tts_service import AWSTtsServicePytree
from harmoni_pytree.leaves.speaker_service import SpeakerServicePytree
from harmoni_pytree.leaves.lip_sync_service import LipSyncServicePytree
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


def create_root(name= "MultipartyGroupInteraction"):

    root = py_trees.composites.Sequence(name="GroupInteraction",memory=True)
    agent_selector = py_trees.composites.Selector(name="AgentSelector", memory = True)
    seq_agent_1 = py_trees.composites.Sequence(name="Agent1",memory=True)
    seq_agent_2 = py_trees.composites.Sequence(name="Agent2",memory=True)
    parall_speaker_face_1 = py_trees.composites.Parallel("Playing1", policy = py_trees.common.ParallelPolicy.SuccessOnAll())
    parall_speaker_face_2 = py_trees.composites.Parallel("Playing2", policy = py_trees.common.ParallelPolicy.SuccessOnAll())
    diar_stt=DiarSpeechToTextServicePytree("Diarization")
    oracle_llm = ChatGPTServicePytree('OracleLLM') # TODO: DECIDE WHETHER THE ORACLE AND THE SCRIPT SHOULD MATCH
    script = ScriptGroupDialogueService("Script")
    llm_agent_1 = ChatGPTServicePytree('LLM1')
    llm_agent_2 = ChatGPTServicePytree('LLM2')
    tts_1 = AWSTtsServicePytree('TTS1')
    tts_2 = AWSTtsServicePytree('TTS2')
    speaker_1 = SpeakerServicePytree('Speaker1')
    speaker_2 = SpeakerServicePytree('Speaker2')
    face_1 = LipSyncServicePytree("Face1")
    face_2 = LipSyncServicePytree("Face2")
    parall_speaker_face_1.add_children([face_1, speaker_1])
    parall_speaker_face_2.add_children([face_2, speaker_2])
    seq_agent_1.add_children([llm_agent_1, tts_1, parall_speaker_face_1])
    seq_agent_2.add_children([llm_agent_2, tts_2, parall_speaker_face_2])
    agent_selector.add_children([seq_agent_1, seq_agent_2])
    root.add_children([diar_stt, oracle_llm, script, agent_selector])
    return root

##############################################################################
# Main
##############################################################################
