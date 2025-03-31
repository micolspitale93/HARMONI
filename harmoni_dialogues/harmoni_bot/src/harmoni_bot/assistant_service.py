#!/usr/bin/env python3

# Common Imports
import rospy
from dotenv import load_dotenv
from harmoni_common_lib.constants import State
from harmoni_common_lib.service_server import HarmoniServiceServer
from harmoni_common_lib.service_manager import HarmoniServiceManager
import harmoni_common_lib.helper_functions as hf
# Specific Imports
from harmoni_common_lib.constants import DialogueNameSpace
from std_msgs.msg import String
import openai
import os
import ast

class AssistantOpenAIService(HarmoniServiceManager):
    """This is a class representation of a harmoni_dialogue service
    (HarmoniServiceManager). It is essentially an extended combination of the
    :class:`harmoni_common_lib.service_server.HarmoniServiceServer` and :class:`harmoni_common_lib.service_manager.HarmoniServiceManager` classes

    :param name: Name of the current service
    :type name: str
    :param param: input parameters of the configuration.yaml file
    :type param: from yaml
    """

    def __init__(self, name, param):
        """Constructor method: Initialization of variables and chatgpt parameters + setting up"""
        super().__init__(name)
        """ Initialization of variables and chatgpt parameters """
        self.name = name
        self.assistant_id = param["assistant_id"]
        self.service_id = param["service_id"]
        self.thread_id = ""
        self.stop_request = False
        self.flagged_sentence = []
        self.assistant = None
        self.state = State.INIT
        self._utterance_pub = rospy.Publisher(DialogueNameSpace.bot.value + self.service_id, String, queue_size=1)
        self._thread_pub = rospy.Publisher(DialogueNameSpace.bot.value + self.service_id + "/thread_id", String, queue_size=1)
        return

    def setup_openai(self):
        """[summary] Setup the chatgpt request, connecting to Assistant services of OpenAI"""
        env_path="/root/harmoni_catkin_ws/src/HARMONI/.env"
        load_dotenv(env_path)
        rospy.loginfo("Connecting to GPT")
        openai.organization = os.getenv("OPENAI_ORGANIZATION")
        openai.api_key = os.getenv("OPENAI_API_KEY")
        #openai.Model.list()
        rospy.loginfo("Connected")
        self.client = openai.OpenAI()
        self.assistant = self.client.beta.assistants.retrieve(self.assistant_id) #the type of assistant will depend on the config file
        if self.service_id == "default": # only if it is the oracle setup the thread is created for the first time
            thread = self.client.beta.threads.create()
            self.thread_id = thread.id
            self._thread_pub.publish(self.thread_id)
        else: #otherwise subscribe to the thread already existing
            self._thread_sub = rospy.Subscriber(DialogueNameSpace.bot.value + self.service_id + "/thread_id", String, self.thread_callback)
        return
    
    def thread_callback(self, data):
        self.thread_id = data.data
        print("The thread is: ")
        print(self.thread_id)
        return

    def request(self, input_text):
        """[summary]

        Args:
            input_text (str): User request (or input text) for triggering chatgpt

        Returns:
            object: It containes information about the response received (bool) and response message (str)
                response: bool
                message: str
        """
        #TODO: i need to modify this in line with the assistant definition creating a run for each request that is linked to the assistant and also to the thread of the conversation
        rospy.loginfo("Start the %s request" % self.name)
        self.state = State.REQUEST
        print(input_text)
        input_text = ast.literal_eval(input_text)
        result = {"response": False, "message": None}
        rospy.loginfo("=============================== UTTERANCE IS")
        messages_array = []
        for message in input_text:
            print(message)
            m =  message.split("*")
            print(m)
            role = m[1]
            content = m[2]
            messages_array.append({"role": role, "content": content})
            
        try:
            thread_message = self.client.beta.threads.messages.create(
                self.thread_id,
                role= role,
                content=content,
            )
            run = self.client.beta.threads.runs.create_and_poll(
                thread_id=self.thread_id,
                assistant_id=self.assistant_id,
                instructions=""
            )
            if run.status == 'completed': 
                messages = self.client.beta.threads.messages.list(
                    thread_id=self.thread_id
                )
                print(messages.data[0].content[0].text.value)
                ai_response = messages.data[0].content[0].text.value
            else:
                print(run.status)
                self.state = State.FAILED
            self.result_msg = ai_response
            self._utterance_pub.publish(self.result_msg)
            self.response_received = True
            self.state = State.SUCCESS
        except rospy.ServiceException:
            self.state = State.FAILED
            rospy.loginfo("Service call failed")
            self.response_received = True
            self.result_msg = ""
        return {"response": self.state, "message": self.result_msg}

def main():
    """[summary]
    Main function for starting HarmoniChatGPT service
    """
    service_name = DialogueNameSpace.bot.name
    instance_id = rospy.get_param("instance_id")  # "default"
    service_id = f"{service_name}_{instance_id}"
    try:
        rospy.init_node(service_name, log_level=rospy.DEBUG)
        params = rospy.get_param(service_name + "/" + instance_id + "_param/")
        s = AssistantOpenAIService(service_id, params)
        s.setup_openai()
        service_server = HarmoniServiceServer(service_id, s)
        #s.request("['*user* Hi my name is Micol, what is your role today?']")
        print(service_name)
        print("**********************************************************************************************")
        print(service_id)

        service_server.start_sending_feedback()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()