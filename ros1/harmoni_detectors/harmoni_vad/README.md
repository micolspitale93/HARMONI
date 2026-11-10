# HARMONI VAD


VAD (Voice Activity Detection) is a packege which used the state-of-the-art VAD service sneakers4/silero-vad.
You have to run this module into the `harmoni_detectors` container.




## Usage

The following documentation refers to the VAD request.

The API for VAD has:

- Request Name: ActionType: START (to start the VAD detection)
- Body: no body 
- Response: no response only State (int)


- Request Name: ActionType: STOP (to stop the VAD detection)
- Body: no body 
- Response: no response only State (int)
   

Run the following commands in order to run microphone service and VAD service in two different terminals:

```  bash
roslaunch harmoni_sensors microphone_service.launch
roslaunch harmoni_vad vad_service.launch
```

It publish at /harmoni/detecting/vad/default a boolean (1: VAD present, 0: VAD absent)


## Paramaters 

|Parameters| Definition| Value |
|---|-----------|------------|
| rate_frame  | frame rate  |  int; 30   |
| subscriber_id  | name of the subscriber id |  string; "default"   |
| sampling_rate  | sampling rate of the microphone  | int; e.g., 16000   |

## Testing

The module can be tested using

```  bash
rostest harmoni_vad vad.test
```

The mock audio used is harmoni_stt/test_data/hello.wav
It can be changed using the param test_vad_input


## Troubleshooting

If an error like: "ImportError: cannot import name 'Self' from 'typing_extensions' (/usr/local/lib/python3.8/dist-packages/typing_extensions.py)" raises, run the following command in the harmoni_detector container:
```
pip install typing-extensions --upgrade
```

## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_vad.html)