#!/usr/bin/env python3

# Common Imports
import rospy
import roslib
from datetime import datetime

from harmoni_common_lib.constants import State
from harmoni_common_lib.service_server import HarmoniServiceServer
from harmoni_common_lib.service_manager import HarmoniServiceManager
import harmoni_common_lib.helper_functions as hf

# Specific Imports
from harmoni_common_lib.constants import State, DetectorNameSpace, SensorNameSpace
from std_msgs.msg import String, Bool
from audio_common_msgs.msg import AudioData
import numpy as np
import os
import io
import ast
import pyaudio
import wave
import opensmile
import pandas as pd

class OpenSmileDetector(HarmoniServiceManager):
    """Face expression recognition detector based off of FaceChannels
    Args:
        detector_threshold(float): Confidence threshold for faces. Positive values
            will return fewer detections, and negative values more detections.
            This value can be changed at any time with no major side-effects.
    """


    def __init__(self, name, param):
        super().__init__(name)
        self._rate = param["rate_frame"]
        self.subscriber_id = param["subscriber_id"]
        self.out_dir = param["output_dir"]
        self.sampling_rate = param["sampling_rate"]
        self.service_id = name
        print(
            "Expected detected destination: ",
            DetectorNameSpace.opensmile.value + self.subscriber_id,
        )
        self._opensmile_pub = rospy.Publisher(
            self.service_id,
            String,
            queue_size=1,
        )
        self._mic_topic = SensorNameSpace.microphone.value + self.subscriber_id 
        self.first_frame = True
        self.state = State.INIT
        self.filename = "audio"
        self.done = False
        self.counter = 0


    def start(self, rate=""):
        """
        Args:
            rate(int): How often the detector should run per second (Hz).
                Note that this rate should be limited by subscribed camera framerate.
                TODO: actually use this rate. Rate currently matches camera publish rate regardless of this setting
        """
        rospy.loginfo("==== STARTED")
        self.state = State.START
        self._rate = rate
        self._microphone_sub = rospy.Subscriber(
            self._mic_topic, AudioData, self.detect_callback
        )

        

    def stop(self):
        rospy.loginfo("Face detector stopped.")
        self.state = State.SUCCESS

    def pause(self):
        self.stop()

    def _opensmile_process(self, data):
        sampling_rate = self.sampling_rate
        smile = opensmile.Smile(
            feature_set = opensmile.FeatureSet.eGeMAPSv02,
            feature_level = 'lld',
            options = {'frameMode': 'fixed', 'frameSize': 1, 'frameStep': 1},
            verbose = True,
        )
        feature_vector = smile.process_signal(data, sampling_rate)
        return feature_vector

    def detect_callback(self, data):
        """Uses audio to detect and publish that the opensmile has processed the audio file info.
        Args:
            data(data): String from the opensmile
        """
        data = np.frombuffer(data.data, np.uint8)
        if self.counter == 0:
            self._detection = []
        elif self.counter == 100:
            self._opensmile_pub.publish(str(self._detection))
            self._detection = []
            self.counter = 0
        self.counter +=1
        feature_vector = self._opensmile_process(data)
        opensmile_features = pd.DataFrame(data=feature_vector)
        opensmile_features = opensmile_features.fillna(0)
        values = opensmile_features.values[:1][0]
        new_values = []
        for j in range(len(values)):
            new_values.append(float(values[j]))
        self._detection.append(new_values)

def main():

    service_name = DetectorNameSpace.opensmile.name  
    instance_id = rospy.get_param("instance_id")  # "default"
    service_id = DetectorNameSpace.opensmile.value + instance_id

    try:
        rospy.init_node(service_name, log_level=rospy.INFO)

        params = rospy.get_param(DetectorNameSpace.opensmile.name +'/'+ instance_id + "_param/")

        s = OpenSmileDetector(service_id, params)
        service_server = HarmoniServiceServer(service_id, s)
        #s.start(1)
        service_server.start_sending_feedback()
        
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()
