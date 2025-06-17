#!/usr/bin/env python3

# Importing the libraries
import rospy
import roslib
import warnings
import websocket
import yaml
import _thread as thread
import time
import json
import ast

class HarmoniWebsocketServer(object):
    """
    The Harmoni Websocket client class implements a template class for interfacing between
    an external server and the client. 
    Class to send and receive messages to a websocket server.
    """

    def __init__(self, ip, port="", secure=False, openmessage="Hello"):
        """ The client setup will start the socket connection.
        Args:
            ip (str): url of websocket server
            port (int): port of server
            secure (bool): if the server is https (true) or not (false)
        """
        self.message = json.dumps(openmessage)
        #websocket.enableTrace(True)
        if port=="":
            
            if secure:
                endpoint = 'wss://' + ip
            else:
                endpoint= 'ws://' + ip
        else:
            
            if secure:
                endpoint = 'wss://' + ip + ':' + str(port)
            else:
                endpoint = 'ws://' + ip + ':' + str(port)
        rospy.loginfo("Connecting to websocket: "+endpoint)
        self.ws = websocket.WebSocketApp(endpoint,
                                on_message = self.on_message,
                                on_error = self.on_error,
                                on_close = self.on_close)
        self.ws.on_open = self.on_open
        self.ws.run_forever()
        

    def on_message(self, ws, message):
        rospy.loginfo(f"Receiving the message {message}")
        if isinstance(message, str):
            rospy.loginfo("The message is a string")
            message=ast.literal_eval(message)
        rospy.loginfo("The request received is " + message["request"])
        request = message["request"]
        body = message["body"]
        rospy.loginfo("The body received is " + body)
        if request=="OPEN":
            self.open(body)
        elif request=="COMMAND":
            self.do_command(body)
        elif request=="STORY":
            self.play_story(body)
        return

    def on_error(self, ws, error):
        rospy.loginfo(error)
        return

    def on_close(self, ws,c, d):
        rospy.loginfo("### closed ###")
        return

    def on_open(self, ws):
        def run(*args):
            self.ws.send(self.message)
        thread.start_new_thread(run, ())
        rospy.loginfo("### open ###")
        return

    def send(self, message):
        rospy.loginfo(f"Send the message {message}")
        self.ws.send(json.dumps(message))
        return
        

    def open(self, message):
        """ Make a request of another service, such as a web service

        Raises:
            NotImplementedError: To be used, this function should be overwritten by the child class.
        """
        rospy.loginfo("open")
        return

    def do_command(self, message):
        """ Make a request of another service, such as a web service

        Raises:
            NotImplementedError: To be used, this function should be overwritten by the child class.
        """
        rospy.loginfo("do_command")
        return


    def play_story(self, message):
        """ Make a request of another service, such as a web service

        Raises:
            NotImplementedError: To be used, this function should be overwritten by the child class.
        """
        rospy.loginfo("play")
        return


    