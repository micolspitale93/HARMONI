# HARMONI FER


FER (facial expression recognition) is a packege which used the state-of-the-art FaceChannel service to detect Arousal and Valence, find more details in: https://facechannel.readthedocs.io/en/latest/. It subscribes to the harmoni_camera module to get camera images to analyse and return facial expression recognition.


Run this detector in another container: harmoni_detector_fer.


## Usage


The following documentation refers to the fer request.

The API for FER has:

- Request Name: ActionType: START (to start the fer detection)
- Body: no body 
- Response: no response only State (int)


- Request Name: ActionType: STOP (to stop the fer detection)
- Body: no body 
- Response: no response only State (int)
   

   

Run the following commands in order to run camera service and FER service in two different terminals:

```  bash
roslaunch harmoni_sensors camera_service.launch
roslaunch harmoni_fer fer_service.launch
```

It is a detector that subscribe from a camera sensor (either the robots or an external camera) (Image) data, and it publish two set of String:
- /harmoni/detecting/fer/default: returning arousal, valence 
- /harmoni/detecting/fer/default/baseline: retuning valence max and valence min of the first 60 seconds of the interaction (to get a baseline)

## Testing

Run using the following command

```  bash
rostest harmoni_fer fer.test
```

The mock image used is harmoni_face_detect/test/test_data/composer.jpg
It can be changed using the param test_openface_input

## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_fer.html)