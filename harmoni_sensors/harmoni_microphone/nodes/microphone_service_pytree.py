#!/usr/bin/env python3

# Common Imports
import rospy
import roslib

from harmoni_common_lib.constants import State
from actionlib_msgs.msg import GoalStatus
from harmoni_common_lib.action_client import HarmoniActionClient
import harmoni_common_lib.helper_functions as hf
from microphone_service import MicrophoneService
# Other Imports
from harmoni_common_lib.constants import SensorNameSpace
from audio_common_msgs.msg import AudioData
import pyaudio
import wave
import numpy as np
# Specific Imports
from harmoni_common_lib.constants import ActuatorNameSpace, ActionType, DialogueNameSpace
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
from collections import deque 
import soundfile as sf
import numpy as np
import boto3
import re
import json
import ast
import sys

#py_tree
import py_trees
import time

import py_trees.console

class MicrophoneServicePytree(py_trees.behaviour.Behaviour):

    #TODO tutte le print devono diventare console py_tree
    """
    mode è il boolean che controlla la modalità di funzionamento:
    true: opzione 1 (utilizzo come una classe python)
    false: opzione 2 (utilizzo mediate action_goal)
    """


    def __init__(self, name = "MicrophoneServicePytree"):
        """
        Qui abbiamo pensato di chiamare soltanto 
        il costruttore del behaviour tree 
        """
        self.name = name
        self.mode = False
        self.microphone_service = None
        self.result_data = None
        self.service_client_microphone = None
        self.client_result = None

        self.blackboards = []
        self.blackboard_microphone = self.attach_blackboard_client(name=self.name, namespace="harmoni_microphone")
        self.blackboard_microphone.register_key("result_message", access=py_trees.common.Access.WRITE)

        super(MicrophoneServicePytree, self).__init__(name)
        self.logger.debug("%s.__init__()" % (self.__class__.__name__))

    def setup(self,**additional_parameters):
        """
        Qui chiamiamo l'inizializzazione del servizio AWSTtsService, 
        motivo per cui abbiamo aggiunto param al metodo che 
        pensiamo debbano essere passati dal chiamante e non possono essere
        creati all'interno del metodo stesso.  
        """
        for parameter in additional_parameters:
            print(parameter, additional_parameters[parameter])  
            if(parameter =="MicrophoneServicePytree_mode"):
                self.mode = additional_parameters[parameter]        

        service_name = SensorNameSpace.microphone.name  # "microphone"
        instance_id = rospy.get_param("instance_id")  # "default"
        service_id = f"{service_name}_{instance_id}"

        params = rospy.get_param(service_name + "/" + instance_id + "_param/")

        self.microphone_service = MicrophoneService(service_id, params) 

        #TODO questo dobbiamo farlo nell'if 
        #rospy init node mi fa diventare un nodo ros
        rospy.init_node("microphone_default", log_level=rospy.INFO)

        if(not self.mode):
            self.service_client_microphone = HarmoniActionClient(self.name)
            self.client_result = deque()
            self.service_client_microphone.setup_client("microphone_default", 
                                                self._result_callback,
                                                self._feedback_callback)
            self.logger.debug("Behavior interface action clients have been set up!")
        
        self.logger.debug("%s.setup()" % (self.__class__.__name__))

    def initialise(self):
        """
        
        """
            
        self.logger.debug("%s.initialise()" % (self.__class__.__name__))
    def update(self):
        """
        
        """    
        if(self.mode):
            pass
        else:
            if self.service_client_microphone.get_state() == GoalStatus.LOST:
                self.logger.debug(f"Sending goal to {self.microphone_service}")
                # Send request for each sensor service to set themselves up
                self.service_client_microphone.send_goal(
                    action_goal=ActionType["ON"].value,
                    optional_data="Setup",
                    wait="",
                )
                self.logger.debug(f"Goal sent to {self.microphone_service}")
                self.blackboard_microphone.result_message = "RUNNING"
                new_status = py_trees.common.Status.RUNNING
            else:
                if self.service_client_microphone.get_state() != GoalStatus.LOST:
                    #TODO qui succede che appena ci arriva un audio nuovo noi sovrascriviamo, cosa non del tutto giusta
                    if len(self.client_result) > 0:
                        self.result_data = self.client_result.popleft()["data"]
                        self.blackboard_microphone.result_message = "RUNNING"
                        new_status = py_trees.common.Status.RUNNING
                    else:
                        #se siamo qui vuol dire che il risultato ancora non c'è, dunque
                        #si è rotto tutto o dobbiamo solo aspettare?
                        #incerti di questa riga, vedi 408 sequential_pattern.py
                        if(self.microphone_service.state == State.FAILED):
                            self.blackboard_microphone.result_message = "FAILURE"
                            new_status = py_trees.common.Status.FAILURE
                        else:
                            self.blackboard_microphone.result_message = "RUNNING"
                            new_status = py_trees.common.Status.RUNNING
                else:
                    new_status = py_trees.common.Status.FAILURE

        self.logger.debug("%s.update()[%s]--->[%s]" % (self.__class__.__name__, self.status, new_status))
        return new_status

        

    def terminate(self, new_status):
        """
        When is this called?
           Whenever your behaviour switches to a non-running state.
            - SUCCESS || FAILURE : your behaviour's work cycle has finished
            - INVALID : a higher priority branch has interrupted, or shutting down
        """
        if(new_status == py_trees.common.Status.INVALID):
            #esegui codice per interrupt 
            #self.blackboard_tts.result_message = "INVALID"
            #TODO 
            if(self.mode):
                pass
            else:
                pass
        else:
            #esegui codice per terminare (SUCCESS || FAILURE)
            self.client_result = deque()

        self.logger.debug("%s.terminate()[%s->%s]" % (self.__class__.__name__, self.status, new_status))

    def _result_callback(self, result):
        """ Recieve and store result with timestamp """
        self.logger.debug("The result of the request has been received")
        self.logger.debug(
            f"The result callback message from {result['service']} was {len(result['message'])} long"
        )
        self.client_result.append(
            {"data": result["message"]}
        )
        # TODO add handling of errors and continue=False
        return

    def _feedback_callback(self, feedback):
        """ Feedback is currently just logged """
        self.logger.debug("The feedback recieved is %s." % feedback)
        # Check if the state is end, stop the behavior pattern
        # if feedback["state"] == State.END:
        #    self.end_pattern = True
        return

def main():
    #command_line_argument_parser().parse_args()

    py_trees.logging.level = py_trees.logging.Level.DEBUG
    
    blackboardProva = py_trees.blackboard.Client(name="blackboardProva", namespace="harmoni_microphone")
    blackboardProva.register_key("result_message", access=py_trees.common.Access.READ)


    print(blackboardProva)

    microphonePyTree = MicrophoneServicePytree("MicrophoneServicePytreeTest")

    additional_parameters = dict([
        ("MicrophoneServicePytree_mode",False)])

    microphonePyTree.setup(**additional_parameters)
    try:
        for unused_i in range(0, 3):
            microphonePyTree.tick_once()
            time.sleep(0.5)
            print(blackboardProva)
        print("\n")
    except KeyboardInterrupt:
        print("Exception occurred")
        pass
    

if __name__ == "__main__":
    main()
