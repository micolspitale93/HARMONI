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
from audio_common_msgs.msg import AudioData
from std_msgs.msg import String, Float32
import numpy as np
import os
import io
import time
from six.moves import queue
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv


class SDAzureService(HarmoniServiceManager):
    """
    Google service
    """

    def __init__(self, name, param):
        super().__init__(name)
        """ Initialization of variables and google parameters """
        self.sample_rate = param["sample_rate"]
        self.language = param["language_id"]
        self.audio_channel = param["audio_channel"]
        self.subscriber_id = param["subscriber_id"]
        self.wait_duration = param["wait_duration"]
        self.max_silence = param["max_silence"]
        self.num_speakers = param["num_speakers"]
        self.names = param["names"].split(",")
        self.time_start_request = None
        self.start_time = None
        self.service_id = hf.get_child_id(self.name)
        self.result_msg = ""
        self.stt_response = ""
        self._buff = queue.Queue()
        self.conversation_transcriber = None
        self.transcribing_stop = False
        self.speaker_talking = ""
        self._first_request = True
        self._current_speaker_talking = ""
        self._transcription = ""

        """Setup the google service as server """
        self.response_text = ""
        self.data = b""

        """Setup publishers and subscribers"""
        
        rospy.Subscriber("/audio/audio", AudioData, None)

        self.text_pub = rospy.Publisher(
            DetectorNameSpace.stt.value + self.service_id, String, queue_size=10
        )

        self.duration_pub = rospy.Publisher(
            DetectorNameSpace.stt.value + self.subscriber_id + '/duration', Float32, queue_size=1
        )

        rospy.Subscriber(
            DetectorNameSpace.stt.value + self.service_id,
            String,
            self.stt_callback,
        )

        rospy.Subscriber(
            SensorNameSpace.microphone.value + self.subscriber_id,
            AudioData,
            self.callback,
        )

        """Setup the stt service as server """
        self.state = State.INIT
        return

    def pause_back(self, data):
        rospy.loginfo(f"pausing for data: {len(data.data)}")
        self.pause()
        rospy.sleep(int(len(data.data) / 30000))  # TODO calibrate this guess
        self.state = State.START
        return

    def callback(self, data):
        """ Callback function subscribing to the microphone topic"""
        #rospy.loginfo("Add data to buffer")
        if (self.state == State.REQUEST | self.state == State.START):
            self._buff.put(data.data)
            


    def stt_callback(self, data):
        """ Callback function subscribing to the microphone topic"""
        self.response_received = True


    def conversation_transcriber_recognition_canceled_cb(self, evt: speechsdk.SessionEventArgs):
        print('Canceled event')

    def conversation_transcriber_session_stopped_cb(self,evt: speechsdk.SessionEventArgs):
        print('SessionStopped event')

    def conversation_transcriber_transcribed_cb(self, evt: speechsdk.SpeechRecognitionEventArgs):
        print('\nTRANSCRIBED:')
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:            
            self.speaker_talking = evt.result.speaker_id
            for i in range(0, self.num_speakers - 1):
                if (self.speaker_talking == "Guest-" + str(i+1)):
                    self.speaker_talking = self.names[i]
                    break
                else:
                    self.speaker_talking = "AGENT-UNKNOWN"
            print('\tText={}'.format(evt.result.text))
            print('\tSpeaker ID={}\n'.format(self.speaker_talking))
            if len(evt.result.text)!=0:
                self.stt_response = self.speaker_talking + ": " + evt.result.text
                self.stt_response = self.stt_response.replace("'"," ")
                self.state = State.SUCCESS
                self.response_received = True
                self.result_msg = self.stt_response
                self.conversation_transcriber.stop_transcribing_async()  
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            print('\tNOMATCH: Speech could not be TRANSCRIBED: {}'.format(evt.result.no_match_details))

    def conversation_transcriber_transcribing_cb(self, evt: speechsdk.SpeechRecognitionEventArgs):
        print('TRANSCRIBING:')
        self._current_speaker_talking = evt.result.speaker_id
        for i in range(0, self.num_speakers - 1):
            if (self._current_speaker_talking == "Guest-" + str(i+1)):
                self._current_speaker_talking = self.names[i]
                break
            else:
                self._current_speaker_talking = "AGENT-UNKNOWN"
        self._transcription = evt.result.text
        print('\tText={}'.format(self._transcription))
        print('\tSpeaker ID={}'.format(self._current_speaker_talking))
        

    def conversation_transcriber_session_started_cb(self, evt: speechsdk.SessionEventArgs):
        print('SessionStarted event')

    def recognize_from_mic(self):
        load_dotenv("/root/harmoni_catkin_ws/src/HARMONI/.env")
        speech_config = speechsdk.SpeechConfig(subscription=os.getenv('MICROSOFT_SPEECH_KEY'), region=os.getenv('MICROSOFT_SPEECH_REGION'))
        speech_config.speech_recognition_language="en-US"
        speech_config.set_property(property_id=speechsdk.PropertyId.SpeechServiceResponse_DiarizeIntermediateResults, value='true')
        #audio_format = speechsdk.audio.AudioStreamFormat(samples_per_second=sample_rate, bits_per_sample=16, channels=1)
        #stream_callback = MyAudioStream(buff)
        #audio_input = speechsdk.audio.PullAudioInputStream(stream_callback, audio_format)
        #audio_config = speechsdk.audio.AudioConfig(stream=audio_input)
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)#device_name="TONOR TC30 Audio Device: USB Audio (hw:1,0)")
        self.conversation_transcriber = speechsdk.transcription.ConversationTranscriber(speech_config=speech_config, audio_config=audio_config)
        self.conversation_transcriber.properties.set_property(speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs, "4000")
        self.conversation_transcriber.properties.set_property(speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "1200") ##NOT WORKING PROPERLY...



        def stop_cb(evt: speechsdk.SessionEventArgs):
            #"""callback that signals to stop continuous recognition upon receiving an event `evt`"""
            print('CLOSING on {}'.format(evt))
            self.transcribing_stop = True

        # Connect callbacks to the events fired by the conversation transcriber
        self.conversation_transcriber.transcribed.connect(self.conversation_transcriber_transcribed_cb)
        self.conversation_transcriber.transcribing.connect(self.conversation_transcriber_transcribing_cb)
        self.conversation_transcriber.session_started.connect(self.conversation_transcriber_session_started_cb)
        self.conversation_transcriber.session_stopped.connect(self.conversation_transcriber_session_stopped_cb)
        self.conversation_transcriber.canceled.connect(self.conversation_transcriber_recognition_canceled_cb)
        
        # stop transcribing on either session stopped or canceled events
        self.conversation_transcriber.session_stopped.connect(stop_cb)
        self.conversation_transcriber.canceled.connect(stop_cb)

        print("START TRANSCRIPTION")
        self.conversation_transcriber.start_transcribing_async()

        # Waits for completion.
        
        #while not self.transcribing_stop:
        #    time.sleep(.5)
        #print("STOP TRANSCRIPTION")
        #self.conversation_transcriber.stop_transcribing_async()
        


    def request(self, data):
        ## THIS IS WORKING WITH THE REQUEST WITHOUT SENDING OUT THE INFORMATION ABOUT THE SPEAKER THOUGH. IT SHOULD:
        ## 1) SEND IN THE MESSAGE THE SPEAKER INFORMATION
        ## 2) KEEP TRANSCRIBING EVEN WHEN THE AGENT IS PROCESSING WHAT HAS JUST BEEN SAID
        ## 3) SHOULD IT WORK WITH START AND STOP INSTEAD? TO TEST
        ## 4) GET SILENCE TIME / THRESHOLD TO DECIDE WHEN TO SAY SOMETHING (EXPLORE THE PROPERTY in here: https://www.youtube.com/watch?v=2X5XBr19-G0 )
        rospy.loginfo("Start the %s request" % self.name)
        self.state = State.REQUEST
        self.stt_response = ""
        self.response_received = False
        if self._first_request:
            self.recognize_from_mic()
        else:
            self.conversation_transcriber.start_transcribing_async()
        try:
            # Transcribes data coming from microphone
            r = rospy.Rate(1)
            print("HEREEEEEE")
            while not self.response_received:
                r.sleep()
            print("AFTER WHILE")
            print("FINAL STT response text: "+ self.stt_response)
            self._first_request = False
            self.state = State.SUCCESS
            self.response_received = True        
            self.result_msg = self.stt_response
            rospy.loginfo("FINAL STT response text: "+ self.stt_response)
            self.text_pub.publish(self.stt_response)
        except rospy.ServiceException:
            self.state = State.FAILED
            rospy.loginfo("Service call failed")
            self.response_received = True
            self.result_msg = ""
        return {"response": self.state, "message": self.result_msg}


    def start(self, rate=""):
        try:
            rospy.loginfo("Start the %s service" % self.name)
            self.state = State.START
            self.recognize_from_mic()
        except Exception:
            rospy.loginfo("Killed the %s service" % self.name)
        return

    def stop(self):
        rospy.loginfo("Stop the %s service" % self.name)
        try:            
            # Signal the STT input data generator to terminate so that the client's
            # streaming_recognize method will not block the process termination.
            self.transcribing_stop = True
            #self._buff.put(None)
            self.conversation_transcriber.stop_transcribing_async()
            self.state = State.SUCCESS
        except Exception:
            self.state = State.FAILED
        return

    def pause(self):
        rospy.loginfo("Pause the %s service" % self.name)
        self.state = State.SUCCESS
        return

def main():
    """Set names, collect params, and give service to server"""

    service_name = DetectorNameSpace.stt.name  # "stt"
    instance_id = rospy.get_param("instance_id")  # "default"
    service_id = f"{service_name}_{instance_id}"
    try:
        rospy.init_node(service_name, log_level=rospy.DEBUG)

        # stt/default_param/[all your params]
        params = rospy.get_param(service_name + "/" + instance_id + "_param/")

        s = SDAzureService(service_id, params)
        #s.request()
        service_server = HarmoniServiceServer(name=service_id, service_manager=s)
        print(service_name)
        print("**********************************************************************************************")
        print(service_id)
        #s.start()
        # Streaming audio from mic
        service_server.start_sending_feedback()
        rospy.spin()
        
    except rospy.ROSInterruptException:
        pass

if __name__ == "__main__":
    main()