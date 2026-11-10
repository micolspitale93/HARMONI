# HARMONI Microphone
The harmoni_microphone package provides a simple wrapper around the microphone for publishing audio data. 
You can run this module in both `harmoni_full` and `harmoni_hardware` containers.


## Usage

The following documentation refers to the Microphone request.

The API for Microphone has:

- Request Name: ActionType: START (to start the Microphone sensing)
- Body: no body 
- Response: no response only State (int)


- Request Name: ActionType: STOP (to stop the Microphone sensing)
- Body: no body 
- Response: no response only State (int)


Configure hardware using [the guide](https://harmoni.readthedocs.io/en/latest/configuration/Hardware.html)
Run using

```  bash
roslaunch harmoni_microphone microphone_service.launch
```
## Parameters
Parameters input for the microphone service: 

| Parameters           | Definition | Values |
|----------------------|------------|--------|
|audio_format_width    |    width of the audio format             |   int; 2     |
|chunk_size            |  the size of the chunk audio to stream and publish          |  int; e.g., 1600 or 4800      |
|total_channels        |   number of channels depends on the microphone characteristics         |      int; 1  |
|audio_rate            |   rate of the audio depends on the microphone characteristics         | int; e.g., 16000, or 48000     |
|device_name           |name of the device you get from arecord -l            |   str; "CBHT Audio: USB Audio (hw:1,0)"       |
|test_outdir           |path of the file that you get as output from testing            |   str; "$(find harmoni_microphone)/temp_data/test_example.wav"   |


## Testing

Module can be tested using

```  bash
rostest harmoni_microphone microphone.test
```

## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_microphone.html)