# HARMONI Openface

The HARMONI openface is a module that uses OpenFace detection to extract facial action units from camera images. It subscribes to the camera sensor to detect FAUs.

You have to run this module into the `harmoni_openface` container.



## Usage


The following documentation refers to the OpenFace request.

The API for OpenFace has:

- Request Name: ActionType: START (to start the OpenFace detection)
- Body: no body 
- Response: no response only State (int)


- Request Name: ActionType: STOP (to stop the OpenFace detection)
- Body: no body 
- Response: no response only State (int)
   

Run the following commands in order to run camera service and openface service in two different terminals:

```  bash
roslaunch harmoni_sensors camera_service.launch
roslaunch harmoni_openface openface_service.launch
```

## Parameters



Parameters input for the openface service corresponds the the $instand_id_param which includes:

|Parameters| Definition| Value |
|---|-----------|------------|
| rate_frame  | frame rate  |  int; 1   |
| fps  | frames per second |     int; 1|
| window_size  | size of the window |   int; 1  |
| overlap  | overalapping between following windows |   int; 0  |
| executable_dir  |  path of the location of the OpenFace executable (it is in the folder provided unless you want to change executable )| string;"/root/OpenFace/build/bin/FaceLandmarkImg"     |
| input_dir  | directory path where the input files are stored  |  string; "$(find harmoni_openface)/input/ "  |
| output_dir  |   directory path where the output files are stored| string; "$(find harmoni_openface)/output/ "   |
| subscriber_id  | name of the subscriber id |  string; "default"   |
| robot_subscriber_id  | name of the topic the openface detector is subscribing to  | string; e.g., from the camera "/camera/color/image_raw"    |


## Testing
The module can be tested using

```  bash
rostest harmoni_openface openface.test
```

The mock image used is harmoni_face_detect/test/test_data/composer.jpg
It can be changed using the param test_openface_input

## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_openface.html)