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

class ChatGPTService(HarmoniServiceManager):
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
        self.stop_request = False
        self.flagged_sentence = []
        self.state = State.INIT
        self._utterance_pub = rospy.Publisher(DialogueNameSpace.bot.value + "default", String, queue_size=1)
        return

    def setup_chat_gpt(self):
        """[summary] Setup the chatgpt request, connecting to ChatGPT services"""
        env_path="/root/harmoni_catkin_ws/src/HARMONI/.env"
        load_dotenv(env_path)
        rospy.loginfo("Connecting to GPT")
        openai.organization = os.getenv("OPENAI_ORGANIZATION")
        openai.api_key = os.getenv("OPENAI_API_KEY")
        openai.Model.list()
        rospy.loginfo("Connected")
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
        rospy.loginfo("Start the %s request" % self.name)
        self.state = State.REQUEST
        input_text = ast.literal_eval(input_text)
        result = {"response": False, "message": None}
        rospy.loginfo("=============================== UTTERANCE IS")
        messages_array = []
        for message in input_text:
            m =  message.split("*")
            role = m[1]
            content = m[2]
            if content!="":
                if content not in self.flagged_sentence:
                    moderation_check = openai.Moderation.create(
                            input = content
                    )
                    flagged = moderation_check["results"][0]["flagged"]
                else:
                    flagged = False
        
            if not flagged:
                messages_array.append({"role": role, "content": content})
            else:
                self.stop_request = True
                self.flagged_sentence.append(content)
        try:
            if not self.stop_request:
                gpt_response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages = messages_array,
                temperature=0.9,
                max_tokens=150,#150,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0.6
                )
                #rospy.loginfo(f"The chatgpt response is {gpt_response['choices'][0]['text']}")
                #response = gpt_response['choices'][0]['text']
                response = gpt_response['choices'][0]['message']['content']
                ai_response = response.split("AI:")[-1]
                ai_response = ai_response.replace("Sure", "")
                if "!" in ai_response:
                    ai_response = ai_response.replace("!", "")
                moderation_check = openai.Moderation.create(
                    input = ai_response
                )
                flagged = moderation_check["results"][0]["flagged"]
                if not flagged:
                    self.result_msg = ai_response
                else:
                    self.result_msg = "Can you please repeat that?"
            else:
                self.result_msg = "I found your sentence very inappropriate. Let's finish the interaction here!"
                self.stop_request = False
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
        s = ChatGPTService(service_id, params)
        s.setup_chat_gpt()
        service_server = HarmoniServiceServer(service_id, s)
        #s.request("The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very friendly.\n\nHuman: Hello, who are you?\nAI: I am an AI created by OpenAI. How can I help you today?\nHuman: I want to do a positive psychology exercise")
        print(service_name)
        print("**********************************************************************************************")
        print(service_id)

        service_server.start_sending_feedback()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()