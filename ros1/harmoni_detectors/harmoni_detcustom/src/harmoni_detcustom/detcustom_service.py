#!/usr/bin/env python3

# Common Imports
import rospy
import roslib

from harmoni_common_lib.constants import State
from harmoni_common_lib.service_server import HarmoniServiceServer
from harmoni_common_lib.service_manager import HarmoniServiceManager
import harmoni_common_lib.helper_functions as hf

# Specific Imports
from harmoni_common_lib.constants import State, DetectorNameSpace, SensorNameSpace
from std_msgs.msg import String, Bool
import numpy as np
import os
import io
import ast
import tensorflow as tf

class CustomDetector(HarmoniServiceManager):
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
        self.model_dir = param["model_dir"]
        self.model_name_face = param["model_name_face"]
        self.model_name_audio = param["model_name_audio"]
        self.service_id = name
        self._aus_sub = (
            None  # assign this when start() called. #TODO test subscription during init
        )
        
        print(
            "Expected detected destination: ",
            DetectorNameSpace.detcustom.value + self.service_id,
        )
        self._ir_pub = rospy.Publisher(
            DetectorNameSpace.detcustom.value + self.subscriber_id,
            Bool,
            queue_size=1,
        )
        self._openface_topic = DetectorNameSpace.openface.value + self.subscriber_id 
        self._opensmile_topic = DetectorNameSpace.opensmile.value + self.subscriber_id 
        json_file_face = open(self.model_dir + self.model_name_face + '.json', 'r')
        loaded_model_json_face = json_file_face.read()
        json_file_face.close()
        self._custom_model_face = tf.keras.models.model_from_json(loaded_model_json_face) 
        self._custom_model_face.load_weights(self.model_dir + self.model_name_face + '.h5')

        json_file_audio = open(self.model_dir + self.model_name_audio + '.json', 'r')
        loaded_model_json_audio = json_file_audio.read()
        json_file_audio.close()
        self._custom_model_audio = tf.keras.models.model_from_json(loaded_model_json_audio) 
        self._custom_model_audio.load_weights(self.model_dir + self.model_name_audio + '.h5')
        self.prediction = 0
        self.prediction_audio = 0
        self.prediction_face = 0
        self.state = State.INIT


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
        self._aus_sub = rospy.Subscriber(
            self._openface_topic, String, self.detect_callback
        )
        self._opensmile_sub = rospy.Subscriber(
            self._opensmile_topic, String, self.audio_detect_callback
        )
        

    def stop(self):
        rospy.loginfo("Face detector stopped.")
        self.state = State.SUCCESS
        try:
            self._image_sub.unregister()
        except rospy.ROSInternalException:
            pass

    def pause(self):
        self.stop()

    def audio_detect_callback(self, data):
        """Uses image to detect and publish face info.
        Args:
            data(data): String from the openface
        """
        result = data.data
        #data_array = np.array(result)#
        data_array = ast.literal_eval(result)
        if len(data_array)!=0:
            data_array = data_array[0::10]
            input_data = np.array(data_array)
            input_data = input_data.reshape(1, input_data.shape[0], input_data.shape[1])
            rospy.loginfo(input_data.shape)
            prediction = self._custom_model_audio.predict(input_data)
            self.prediction_audio = prediction #
            if self.prediction_audio < 0.5:
                prediction = min(self.prediction_audio, self.prediction_face)
            else:
                prediction = max(self.prediction_audio, self.prediction_face)
            prediction = np.argmax(prediction)
            self._ir_pub.publish(prediction)


    def detect_callback(self, data):
        """Uses image to detect and publish face info.
        Args:
            data(data): String from the openface
        """
        result = data.data
        #data_array = np.array(result)#
        data_array = ast.literal_eval(result)
        if len(data_array)!=0:
            data_array = data_array[0::30]
            input_data = np.array(data_array)
            input_data = input_data.reshape(1, input_data.shape[0], input_data.shape[1])
            rospy.loginfo(input_data.shape)
            prediction = self._custom_model_face.predict(input_data)
            self.prediction_face = prediction # np.argmax(prediction)
            #self._ir_pub.publish(float(prediction))

def main():

    service_name = DetectorNameSpace.detcustom.name  
    instance_id = rospy.get_param("instance_id")  # "default"
    service_id = DetectorNameSpace.detcustom.value + instance_id

    try:
        rospy.init_node(service_name, log_level=rospy.INFO)

        params = rospy.get_param(DetectorNameSpace.detcustom.name +'/'+ instance_id + "_param/")

        s = CustomDetector(service_id, params)
        service_server = HarmoniServiceServer(service_id, s)
        #s.start(1)
        service_server.start_sending_feedback()
        
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()
