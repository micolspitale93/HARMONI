# HARMONI opensmile


The HARMONI opensmile is a module that uses openSMILE detection to extract speech features from audio. It subscribes to the microphone sensor to detect speech features.

You have to run this module into the `harmoni_detectors` container.



## Usage

The following documentation refers to the opensmile request.

The API for opensmile has:

- Request Name: ActionType: START (to start the opensmile detection)
- Body: no body 
- Response: no response only State (int)


- Request Name: ActionType: STOP (to stop the opensmile detection)
- Body: no body 
- Response: no response only State (int)
   

Run the following commands :

```  bash
roslaunch harmoni_opensmile opensmile_service.launch
```


## Paramaters 

|Parameters| Definition| Value |
|---|-----------|------------|
| rate_frame  | frame rate  |  int; 1   |
| output_dir  |   directory path where the output files are stored| string; "$(find harmoni_opensmile)/output/ "   |
| subscriber_id  | name of the subscriber id |  string; "default"   |
| sampling_rate  | sampling rate of the microphone  | int; e.g., 16000   |

## Testing

The module can be tested using

```  bash
rostest harmoni_opensmile opensmile.test
```

The mock audio used is harmoni_stt/test_data/hello.wav
It can be changed using the param test_opensmile_input


## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_imageai.html)