#!/usr/bin/env python3

# Common Imports
import rospy
import roslib

from harmoni_common_lib.constants import State
from harmoni_common_lib.service_server import HarmoniServiceServer
from harmoni_common_lib.service_manager import HarmoniServiceManager
import harmoni_common_lib.helper_functions as hf

# Specific Imports
from harmoni_common_lib.constants import ActuatorNameSpace
import numpy as np
import re
import json
import ast
import sys
from transformers import pipeline


class SentimentService(HarmoniServiceManager):
    """
    Sentiment service
    """

    def __init__(self, name, param):
        """Constructor method: Initialization of variables and polly parameters + setting up"""
        super().__init__(name)
        """ Initialization of variables and sentiment parameters """
        self.model_name = param["model_name"]
        self.sentiment_analysis = pipeline("sentiment-analysis",model=self.model_name)
        self.state = State.INIT
        return

    def request(self, input_text):
        """[summary]

        Args:
            input_text (str): Input string to synthetize
        Returns:
            object: It containes information about the response received (bool) and response message (str)
                response: bool
                message: str
        """
        rospy.loginfo("Start the %s request" % self.name)
        self.state = State.REQUEST
        text = input_text
        try:
            sentiment_response = self.sentiment_analysis(input_text)
            rospy.loginfo(sentiment_response)
            self.state = State.SUCCESS
            self.response_received = True
            self.result_msg = str(sentiment_response)
            rospy.loginfo("Request successfully completed")
        except:
            rospy.logerr("ERROR")
            self.state = State.FAILED
            self.response_received = True
            self.result_msg = ""
        return {"response": self.state, "message": self.result_msg}

def main():
    """[summary]
    Main function for starting HarmoniPolly service
    """
    service_name = ActuatorNameSpace.sentiment.name
    instance_id = rospy.get_param("instance_id")
    service_id = f"{service_name}_{instance_id}"
    try:
        rospy.init_node(service_name)
        param = rospy.get_param(service_name + "/" + instance_id + "_param/")
        s = SentimentService(service_id, param)
        service_server = HarmoniServiceServer(service_id, s)
        #s.request("I love you!!")

        service_server.start_sending_feedback()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()