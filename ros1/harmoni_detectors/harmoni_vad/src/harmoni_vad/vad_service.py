#!/usr/bin/env python3

# Common Imports
import rospy

from harmoni_common_lib.constants import State
from harmoni_common_lib.service_server import HarmoniServiceServer
from harmoni_common_lib.service_manager import HarmoniServiceManager

# Specific Imports
from harmoni_common_lib.constants import State, DetectorNameSpace, SensorNameSpace
from std_msgs.msg import String, Bool
from audio_common_msgs.msg import AudioData
import numpy as np
import torch

class VoiceActivityDetector(HarmoniServiceManager):
    """Voice activity detector
    
    """


    def __init__(self, name, param, detector_threshold=0):
        super().__init__(name)
        self._rate = param["rate_frame"]
        self.subscriber_id = param["subscriber_id"]
        self.sampling_rate = param["sampling_rate"]
        self.detector_threshold = detector_threshold
        self.service_id = name
        self._microphone_source_robot = SensorNameSpace.microphone.value + self.subscriber_id
        print("Expected audio source: ", self._microphone_source_robot)
        self._audio_sub = (
            None  # assign this when start() called. #TODO test subscription during init
        )
        model, utils = torch.hub.load(repo_or_dir = 'snakers4/silero-vad',
                                      model = 'silero_vad',
                                      force_reload = True,
                                      onnx = True
                                      )
                                    
        (_,_,_,VADIterator, _) = utils
        self._vad_iterator = VADIterator(model)
        self._vad_pub = rospy.Publisher(
            self.service_id,
            Bool,
            queue_size=1,
        )
        self._first_stream = True
        self.state = State.INIT

    def start(self, rate=""):
        """
        Args:
            rate(int): How often the detector should run per second (Hz).
                Note that this rate should be limited by subscribed camera framerate.
                TODO: actually use this rate. Rate currently matches camera publish rate regardless of this setting
        """
        #rospy.Timer(rospy.Duration(60), baseline_cb)
        rospy.loginfo("==== STARTED")
        self.state = State.START
        self._rate = rate
        self._audio_sub = rospy.Subscriber(
            self._microphone_source_robot, AudioData, self.detect_callback
        )
        

    def stop(self):
        rospy.loginfo("Voice detector stopped.")
        self.state = State.SUCCESS
        try:
            self._audio_sub.unregister()
        except rospy.ROSInternalException:
            pass

    def pause(self):
        self.stop()

    def detect_callback(self, audio):
        """Uses image to detect and publish face info.
        Args:
            audio(AudioData): the data streaming we want to analyse
        """
        data = np.fromstring(audio.data, np.uint8)   
        speech_dict = self._vad_iterator(data, return_seconds = True)
        if speech_dict:
            vad = True
        else:
            vad = False
        self._vad_pub.publish(vad)

        


def main():

    service_name = DetectorNameSpace.vad.name  
    instance_id = rospy.get_param("instance_id")  # "default"
    service_id = DetectorNameSpace.vad.value + instance_id

    try:
        rospy.init_node(service_name, log_level=rospy.INFO)

        params = rospy.get_param(DetectorNameSpace.vad.name +'/'+ instance_id + "_param/")

        s = VoiceActivityDetector(service_id, params)
        service_server = HarmoniServiceServer(service_id, s)
        #s.start(1)
        service_server.start_sending_feedback()
        
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()
