# HARMONI STT
This is a module for transcribing the speech from audio files and audio streaming. 
You can run your STT in the `harmoni_full` container.

## Usage

### Local DeepSpeech STT
Using the DeepSpeech service:
To set up the local STT service, first run `sh harmoni_detectors/harmoni_stt/get_deepspeech_models.sh` 
from the HARMONI directory in order to place the models in a parallel directory.


The API for Local DeepSpeech STT has:
- Request Name: ActionType: REQUEST
- Body: None (the STT is already listening from the microphone)
- Response:
    - response (int): SUCCESS, or FAILURE 
    - message (str): text transcribed from the streaming audio or audio file


The local DeepSpeech speech-to-text service can be launched with `roslaunch harmoni_stt stt_deepspeech_service.launch` or `roslaunch harmoni_stt stt_service.launch service_to_use:=deepspeech`.
Transcriptions are only published by the DeepSpeech service when the client determines the text as final based on the `t_wait` parameter (the default is 0.5s).

### Google STT

The API for Google STT has:
- Request Name: ActionType: REQUEST
- Body: None (the STT is already listening from the microphone)
- Response:
    - response (int): SUCCESS, or FAILURE 
    - message (str): text transcribed from the streaming audio or audio file


You can run the service with the following command:
```roslaunch harmoni_stt stt_google_service.launch```

### Azure STT with speaker diarization

Transcribes the speech of a group of people and tells who is talking, using the Azure Speech
conversation transcriber. It listens directly from the default microphone of the container.

The API for Azure diarization STT has:
- Request Name: ActionType: REQUEST
- Body: None
- Response:
    - response (int): SUCCESS, or FAILED
    - message (str): `"<speaker name>: <text>"`, e.g. `"Sarah: I agree with you"`. Azure speaker ids
      (`Guest-1`, `Guest-2`, ...) are mapped to the `names` parameter in order; unknown speakers keep the Azure id.
      If nobody talks for more than `max_silence` seconds the message is
      `"No one is talking. Please initiate a question to reignite the conversation."`

Credentials (`MICROSOFT_SPEECH_KEY`, `MICROSOFT_SPEECH_REGION`) are read from the `.env` file in the root of the repository.

You can run the service with the following command:
```roslaunch harmoni_stt stt_sd_azure_service.launch``` or ```roslaunch harmoni_stt stt_service.launch service_to_use:=sd_azure```

## Parameters

### Azure STT with speaker diarization

Parameters in `config/sd_azure_configuration.yaml`:

| Parameters           | Definition | Values |
|----------------------|------------|--------|
|language_id       |  language spoken    |  str; "en-US"    |
|names       |  comma separated names of the participants, in the order Azure detects them (Guest-1, Guest-2, ...)    |  str; "Sarah,Jane,Alex"    |
|num_speakers       |  number of participants    |  int; 3    |
|max_silence       |  seconds of silence after which the silence message is returned    |  int; 10    |
|subscriber_id         |    id of the microphone subscriber        |  e.g., "default"      |

### Local DeepSpeech STT
Parameters input for the local STT service:
| Parameters           | Definition | Values |
|----------------------|------------|--------|
|model_file_path       |   path of the local STT model         |  str; e.g., "$(find harmoni_models)/stt/deepspeech-0.9.3-models.pbmm"      |
|scorer_path           |  path of the scorer for the deepspeech model          |  str; e.g., "$(find harmoni_models)/stt/deepspeech-0.9.3-models.scorer"       |
|lm_alpha              |   parameters of the deepspeech model         |   int; 0.75      |
|lm_beta               |   parameters of the deepspeech model           |   int; 1.85     |
|beam_width            |    width of them beam        | int; 700       |
|t_wait                |    seconds to wait of silence before stoping transcribing        | int; 3s       |
|subscriber_id         |    id of the subscriber        |  e.g., "default"      |

### Google STT

Parameters input for the Google STT service:

| Parameters           | Definition | Values |
|----------------------|------------|--------|
|language_id       |  language of the audio file    |  str; "en-US"    |
|sample_rate           |  sample rate of the audio file (it should match with the microphone one in case of streaming)        |  int; e.g., 48000, or 44100     |
|audio_channel              |   number of audio channels   |   int; 1      |
|max_duration               |   maximum duration of empty streaming (seconds)           |   int; 30   |
|waiting_time            |   time of silence to wait after stopping the transcription (seconds)     | int; 2       |
|credential_path                |   path where private keys are mounted        | str; "$(env HOME)/.gcp/private-keys.json/private-keys.json"      |
|subscriber_id         |    id of the subscriber        |  e.g., "default"      |


## Testing

Local DeepSpeech STT module can be tested using

```  bash
rostest harmoni_stt deepspeech.test
```

Online Gooogle STT module can be tested using

```  bash
rostest harmoni_stt google.test
```

Azure diarization STT can be tested using (speak when asked)

```  bash
rostest harmoni_stt sd_azure.test
```

Unit tests that do not need ROS nor credentials (run from the repository root):

```  bash
python3 -m pytest harmoni_detectors/harmoni_stt
```

## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_stt.html)

https://trac.ffmpeg.org/wiki/Capture/ALSA
