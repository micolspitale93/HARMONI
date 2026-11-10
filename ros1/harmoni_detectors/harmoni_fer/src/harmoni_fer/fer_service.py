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
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
import cv2
from FaceChannel.FaceChannelV1.FaceChannelV1 import FaceChannelV1
from FaceChannel.FaceChannelV1.imageProcessingUtil import imageProcessingUtil
from std_msgs.msg import String
import numpy as np
import os
import io

class FERDetector(HarmoniServiceManager):
    """Face expression recognition detector based off of FaceChannels
    Args:
        detector_threshold(float): Confidence threshold for faces. Positive values
            will return fewer detections, and negative values more detections.
            This value can be changed at any time with no major side-effects.
    """


    def __init__(self, name, param, detector_threshold=0):
        super().__init__(name)
        self._rate = param["rate_frame"]
        self.subscriber_id = param["subscriber_id"]
        self.robot_subscriber_id = param["robot_subscriber_id"]
        self.detector_threshold = detector_threshold
        self.service_id = name
        self._image_source_camera = SensorNameSpace.camera.value + self.subscriber_id
        self._image_source_robot = self.robot_subscriber_id
        print("Expected image source: ", self._image_source_robot)
        self._image_sub = (
            None  # assign this when start() called. #TODO test subscription during init
        )
        print(
            "Expected detected destination: ",
            DetectorNameSpace.fer.value + self.subscriber_id,
        )
        self._face_pub = rospy.Publisher(
            DetectorNameSpace.fer.value + self.subscriber_id,
            String,
            queue_size=1,
        )
        self._face_baseline_pub = rospy.Publisher(
            DetectorNameSpace.fer.value + self.subscriber_id+"/baseline",
            String,
            queue_size=1,
        )
        self.valence_baseline = []
        self.baseline = True
        self._face_size = (64, 64) 
        self.face_channel_detector = FaceChannelV1("Dim", loadModel=True)
        self._image_processing = imageProcessingUtil()
        self.detections = []
        self._cv_bridge = CvBridge()
        self.state = State.INIT

    def start(self, rate=""):
        """
        Args:
            rate(int): How often the detector should run per second (Hz).
                Note that this rate should be limited by subscribed camera framerate.
                TODO: actually use this rate. Rate currently matches camera publish rate regardless of this setting
        """
        def baseline_cb(event):
            if len(self.valence_baseline)!=0:
                self.baseline = False
                maxval = np.max(self.valence_baseline)
                minval = np.min(self.valence_baseline)
                valence_values = [minval, maxval]
                rospy.loginfo("BASELINE DONE")
                rospy.loginfo(str(valence_values))
                self._face_baseline_pub.publish(str(valence_values))
        rospy.Timer(rospy.Duration(60), baseline_cb)
        rospy.loginfo("==== STARTED")
        self.state = State.START
        self._rate = rate
        self._image_sub = rospy.Subscriber(
            self._image_source_robot, Image, self._facechannel_detect_callback
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

    def _facechannel_detect_callback(self, image):
        """Uses image to detect and publish face info.
        Args:
            image(Image): the image we want to run face detection on.
        """
        frame = self._cv_bridge.imgmsg_to_cv2(image, desired_encoding='rgb8')
        if frame is not None:
            face_points, face = self._image_processing.detectFace(frame)
            if not len(face) == 0: # if a face is detected
                face = self._image_processing.preProcess(face, self._face_size)
                dimensional_fer = np.array(self.face_channel_detector.predict(face, preprocess = False))
                self.detections = [dimensional_fer[0][0][0],dimensional_fer[1][0][0]] #arousal, valences
                rospy.loginfo(self.detections)
                if self.baseline:
                    self.valence_baseline.append(self.detections[1])
                self._face_pub.publish(str(self.detections))

def main():

    service_name = DetectorNameSpace.fer.name  
    instance_id = rospy.get_param("instance_id")  # "default"
    service_id = DetectorNameSpace.fer.value + instance_id

    try:
        rospy.init_node(service_name, log_level=rospy.INFO)

        params = rospy.get_param(DetectorNameSpace.fer.name +'/'+ instance_id + "_param/")

        s = FERDetector(service_id, params)
        service_server = HarmoniServiceServer(service_id, s)
        #s.start(1)
        service_server.start_sending_feedback()
        
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()
