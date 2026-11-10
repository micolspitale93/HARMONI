# HARMONI Camera

The harmoni_camera package provides a simple wrapper around the camera for publishing images. 
You can run this module in both `harmoni_full` and `harmoni_hardware` containers.


## Usage


The following documentation refers to the Camera request.

The API for Camera has:

- Request Name: ActionType: START (to start the Camera sensing)
- Body: no body 
- Response: no response only State (int)


- Request Name: ActionType: STOP (to stop the Camera sensing)
- Body: no body 
- Response: no response only State (int)

Configure harfware using [the guide](https://harmoni.readthedocs.io/en/latest/configuration/Hardware.html)
Run using

```  bash
roslaunch harmoni_camera camera_service.launch
```

## Parameters

|Parameters| Definition| Value |
|---|-----------|------------|
| input_device_index  | index of the camera device  |  int; 0   |
| show  | if it is true it show the camera view  |  bool; True   |
| video_format  | the format of the image camera  |  string; "bgr8"   |
| fps  | frames per second  |  int; 30   |
| test_outdir  | output directory of the image for testing |  string; "$(find harmoni_camera)/temp_data/test_example.png"   |


## Testing

Module can be tested using

```  bash
rostest harmoni_camera camera.test
```

## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_camera.html)