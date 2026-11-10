#!/usr/bin/env python3

##############################################################################
# Imports
##############################################################################

import argparse
import functools
import py_trees.console as console
import py_trees
import rospy
from harmoni_common_lib.constants import *
from harmoni_pytree.leaves.aws_tts_service import AWSTtsServicePytree
from harmoni_pytree.leaves.deep_stt import DeepSpeechToTextServicePytree
from harmoni_pytree.leaves.aws_lex_trigger_service import AWSLexTriggerServicePytree
from harmoni_pytree.leaves.chat_gpt_service import ChatGPTServicePytree
from harmoni_pytree.leaves.speaker_service import SpeakerServicePytree
from harmoni_pytree.leaves.lip_sync_service import LipSyncServicePytree
from harmoni_pytree.leaves.microphone_service import MicrophoneServicePytree
from harmoni_pytree.leaves.check_stt_result import CheckSTTResult
from harmoni_pytree.leaves.gesture_service import GestureServicePytree
from harmoni_pytree.leaves.wait_results import WaitResults
from harmoni_pytree.leaves.backchannel_service import BackchannelService
from harmoni_pytree.leaves.google_service import SpeechToTextServicePytree
from harmoni_pytree.leaves.sentiment_service import SentimentServicePytree
from harmoni_pytree.leaves.script_errors_service import ScriptErrorsService
from harmoni_pytree.leaves.check_stt_result_minja import CheckSTTResultErrors


##############################################################################
# Classes
##############################################################################

def description(root):
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
    parser = argparse.ArgumentParser(description=self.description,
                                    epilog=self.epilog,
                                    formatter_class=argparse.RawDescriptionHelpFormatter,
                                    )
    parser.add_argument('-r', '--render', action='store_true', help='render dot tree to file')
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
    #print(py_trees.display.unicode_blackboard())

def create_root(params):
    root = py_trees.composites.Sequence("Dialogue")#, memory=True)
    sequence_speaking = py_trees.composites.Sequence("Speaking")#, memory=True)
    sequence_backchanneling = py_trees.composites.Sequence("Backchanneling")#, memory=True)
    sequence_sensing = py_trees.composites.Sequence("Sensing")#, memory=True)
    parallel_sensing_backchanneling = py_trees.composites.Parallel("Listening")#, policy = SuccessOnAll)
    chatbot = ChatGPTServicePytree("ChatGPTPyTreeTest")
    tts = AWSTtsServicePytree("TextToSpeech")
    tts_back = AWSTtsServicePytree("TextToSpeechBackchannel")
    script_errors = ScriptErrorsService("ScriptErrors", params)
    gesture = GestureServicePytree("Gesture")
    speaker = SpeakerServicePytree("Speaker")
    #sentiment = SentimentServicePytree("Sentiment")
    gesture_back = GestureServicePytree("GestureBackchannel")
    speaker_back = SpeakerServicePytree("SpeakerBackchannel")
    face = LipSyncServicePytree("Face")
    face_back = LipSyncServicePytree("FaceBackchannel")
    microphone=MicrophoneServicePytree("Microphone")
    stt=SpeechToTextServicePytree("SpeechToText")
    checkstt = CheckSTTResultErrors("CheckResultsErrors", params)
    backchanneling_script = BackchannelService("BackchannelScript", params)
    parall_speaker_face = py_trees.composites.Parallel("Playing")#, policy = SuccessOnAll)
    parall_playing_back = py_trees.composites.Parallel("PlayingBackchannel")#, policy = SuccessOnAll)
    sequence_backchanneling.add_children([backchanneling_script, tts_back, parall_playing_back])
    sequence_speaking.add_child(script_errors)
    sequence_speaking.add_child(chatbot)
    sequence_speaking.add_child(tts)
    sequence_speaking.add_child(parall_speaker_face)
    parall_playing_back.add_children([speaker_back, face_back, gesture_back])
    parall_speaker_face.add_child(speaker)
    parall_speaker_face.add_child(face)
    parall_speaker_face.add_child(gesture)
    sequence_sensing.add_children([microphone, stt, checkstt])
    parallel_sensing_backchanneling.add_children([sequence_sensing, sequence_backchanneling])
    root.add_children([sequence_speaking, parallel_sensing_backchanneling])
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
    root =create_root(params)

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


