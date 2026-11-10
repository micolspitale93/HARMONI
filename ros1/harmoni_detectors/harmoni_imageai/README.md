# HARMONI Imageai


ImageAI is a python library built to empower developers to build applications and systems with self-contained Deep Learning and Computer Vision capabilities.  
Now in HARMONI you can find one among the several services that ImageAI provides: stream detection.  

In particular we created two different services

- the first one use the state of art model for object detection yoloV3 
- the other one use a custom model trained on the top of yoloV3


You have to run this module into the `harmoni_imageai` container.

## Usage

So as to use plain yoloV3 model you have to do nothing but download the **yoloV3** model [here](https://github.com/OlafenwaMoses/ImageAI/releases/download/1.0/yolo.h5) and then add it in the container in following path: `HARMONI/harmoni_detectors/harmoni_imageai/src/[PUT HERE]`.

As far custom models are concerned, there are some steps that have to be followed:

1. Create your own model following the steps in the documentation of ImageAI here: [https://github.com/OlafenwaMoses/ImageAI/blob/master/imageai/Detection/Custom/CUSTOMDETECTIONTRAINING.md](https://github.com/OlafenwaMoses/ImageAI/blob/master/imageai/Detection/Custom/CUSTOMDETECTIONTRAINING.md).  
At the end of this process you will obtain 2 files: a model.h5 and a config.json. 
2. Put these two files in the following path  `HARMONI/harmoni_models/yolo/[PUT HERE]` in the container. Be sure that names coincide with the ones in `custom_configuration.yaml` file under `harmoni_imageai` folder.

Full documentation of ImageAI: [https://github.com/OlafenwaMoses/ImageAI#readme](https://github.com/OlafenwaMoses/ImageAI#readme)


The following documentation refers to the ImageAI request.

The API for ImageAI has:

- Request Name: ActionType: START (to start the ImageAI detection)
- Body: no body 
- Response: no response only State (int)


- Request Name: ActionType: STOP (to stop the ImageAI detection)
- Body: no body 
- Response: no response only State (int)
   


Here are the steps that you can follow in order to run the ImageAI service in HARMONI.




**YoloV3**  
Run the following commands in order to run camera service and yolo service in two different terminals:

```  bash
roslaunch harmoni_sensors camera_service.launch
roslaunch harmoni_imageai yolo_service.launch
```

Camera will open and one frame will be captured and put as input of the yolov3 model. Once the output of the imageai service arrives another frame will be captured and again used as input for yolov3 model and so on.

**Custom yolo**  
Run the following command in order to run camera service and custom yolo service in two different terminals:

```  bash
roslaunch harmoni_sensors camera_service.launch
roslaunch harmoni_imageai custom_service.launch
```

Camera will open and one frame will be captured and put as input of the custom model. Once the output of the imageai service arrives another frame will be captured and again used as input for custom model and so on. 


## Parameters

Parameters input for the yolo service corresponds the the $instand_id_param which includes:

|Parameters| Definition| Value |
|---|-----------|------------|
| frame_per_second  | frames per second |     int; 30|
| output_file name  |   directory path where the output files are stored| string; "$(find harmoni_openface)/output/ "   |
| subscriber_id  | name of the subscriber id |  string; "default"   |
| log_progress  | logging of the model |  bool; True   |
| minimum_percentage_probability  | minimum percentage for recognizing objects |  int; 50   |
| return_detected_frame  | if true, allows you to obtain the detected video frame as a Numpy array |  bool; False   |
| model_path  | path of the model stored |  string; "/root/harmoni_catkin_ws/src/HARMONI/harmoni_models/yolo/"   |
| temp_path  | temporary directory where to store results |  string; "/root/harmoni_catkin_ws/src/HARMONI/harmoni_detectors/harmoni_imageai/temp_data/"   |



## Testing

The module can be tested using

**YoloV3**
```  bash
rostest harmoni_imageai imageai_yolo.test
```

**Custom Yolo**
```  bash
rostest harmoni_imageai imageai_custom.test
```

## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_imageai.html)