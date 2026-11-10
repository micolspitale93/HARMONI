#!/usr/bin/env python3

# Common Imports
import rospy

from harmoni_common_lib.constants import State
from harmoni_common_lib.service_server import HarmoniServiceServer
from harmoni_common_lib.service_manager import HarmoniServiceManager
from harmoni_common_lib.constants import State, DetectorNameSpace, SensorNameSpace
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
import cv2
from std_msgs.msg import String
import os
import subprocess
import pandas as pd

class OpenFaceDetector(HarmoniServiceManager):
    """Face expression recognition detector based off of OpenFace
    Args:
        detector_threshold(float): Confidence threshold for faces. Positive values
            will return fewer detections, and negative values more detections.
            This value can be changed at any time with no major side-effects.
    """


    def __init__(self, name, param, detector_threshold=0):
        super().__init__(name)
        self._rate = param["rate_frame"]
        self._fps = param["fps"]
        self._window_size = param["window_size"]
        self._overlap = param['overlap']
        self.executable_dir = param["executable_dir"]
        self.input_dir = param["input_dir"]
        self.output_dir = param["output_dir"]
        self.subscriber_id = param["subscriber_id"]
        self.robot_subscriber_id = param["robot_subscriber_id"]
        self.detector_threshold = detector_threshold
        self.counter_initial = True
        self.service_id = name
        self._image_source_camera = SensorNameSpace.camera.value + self.subscriber_id
        self._image_source_robot = self.robot_subscriber_id
        print("Expected image source: ", self._image_source_robot)
        self._image_sub = (
            None  # assign this when start() called. #TODO test subscription during init
        )
        print(
            "Expected detected destination: ",
            DetectorNameSpace.openface.value + self.service_id,
        )
        self._n_frames = self._fps*self._window_size
        self._n_frames_overlap = self._fps*self._overlap
        self._face_pub = rospy.Publisher(
            self.service_id,
            String,
            queue_size=1,
        )
        #self.detections = Float64MultiArray()
        self.counter = 0
        self._cv_bridge = CvBridge()
        self.state = State.INIT


    def setup():
        return


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
        self._image_sub = rospy.Subscriber(
            self._image_source_robot, Image, self.detect_callback
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

    def detect_callback(self, image):
        """Uses image to detect and publish face info.
        Args:
            image(Image): the image we want to run face detection on.
        """
        rospy.loginfo("=== DETECTING A CALLBACK HERE")
        frame = self._cv_bridge.imgmsg_to_cv2(image, desired_encoding='rgb8')
        rospy.loginfo("Made it past the bridge")
        if frame is not None:
            self.counter += 1
            cv2.imwrite(self.input_dir + 'frame%d.jpg' %self.counter, frame)
            rospy.loginfo('====== frame%d.jpg SAVED' %self.counter )
            command_line = self.executable_dir
            command_line += ' -f ' + self.input_dir + 'frame%d.jpg'%(self.counter) + ' -out_dir ' +self.output_dir + ' -aus'
            openface_process = subprocess.Popen(command_line, shell = True)
            if self.counter == self._n_frames:
                
                if self.counter_initial:
                    self.counter = 1
                    self.counter_initial = False
                else:
                    self.counter = self._n_frames_overlap
                self._detection = []
                for i in range(self._n_frames_overlap):
                    os.rename(self.input_dir + 'frame%d.jpg'%(self._n_frames - self._n_frames_overlap + i),  self.input_dir + 'frame%d.jpg'%(i + self.counter))
                csv_files = os.listdir(self.output_dir)
                rospy.sleep(0.1)
                for f in csv_files:
                    if ".csv" in f:
                        rospy.loginfo(self.output_dir + f)
                        aus = pd.read_csv(self.output_dir + f)
                        aus = aus.drop(columns=["frame","face_id","timestamp","confidence","success"])
                        aus = aus.fillna(0)
                        values = aus.values[:1][0]
                        new_values = []
                        for j in range(len(values)):
                            new_values.append(float(values[j]))
                        self._detection.append(new_values)
                rospy.loginfo("")
                rospy.loginfo("")
                rospy.loginfo("")
                rospy.loginfo(self._detection)
                #self._detection = [[float(self._detection[i][j]) for j in range(len(self._detection)) for i in range(len(self._detection[0]))]]
                #self.detections.data = self._detection
                self._face_pub.publish(str(self._detection))


def main():

    service_name = DetectorNameSpace.openface.name  
    instance_id = rospy.get_param("instance_id")  # "default"
    service_id = DetectorNameSpace.openface.value + instance_id

    try:
        rospy.init_node(service_name, log_level=rospy.INFO)

        params = rospy.get_param(DetectorNameSpace.openface.name +'/'+ instance_id + "_param/")

        s = OpenFaceDetector(service_id, params)
        service_server = HarmoniServiceServer(service_id, s)
        #s.start(1)
        service_server.start_sending_feedback()
        
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()
