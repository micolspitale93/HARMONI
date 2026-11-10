# HARMONI TTS

The Text To Speech package takes text as action arguments and produces audio and visemes for speech.
You can run this module in the `harmoni_full`  container. 

## Usage


### Amazon Polly TTS

Make sure that you have followed the instructions to link cloud services reported in [Cloud Services](https://harmoni-20.readthedocs.io/en/latest/configuration/Cloud-Services.html).


The following documentation refers to the tts request.

The API for TTS has:

- Request Name: ActionType: REQUEST
- Body: data(str): 
  - inputting string of SSML format of the text you want to synthetised. Look at the [Amazon Polly Documentation](https://docs.aws.amazon.com/polly/latest/dg/supportedtags.html) for more information about the SSML format.
- Response:
    - response (int): SUCCESS, or FAILURE
    - message (str): string of the following dictionary:
        {
            "audio_frame": int(),
            "audio_data": AudioData(data_array),
            "behavior_data": str(behaviours),
        }
        With the term behaviours we refer to the visemes (output of the tts), gestures or facial expressions that are synchronised with the speech and embedded in the text with **.


You can run the service as follows: 
```roslaunch harmoni_tts tts_service.launch```



### Local TTS service
To set up the local TTS service, first run `sh harmoni_actuators/harmoni_tts/setup_tts.sh` from the HARMONI directory to install the local TTS models, configuration files, and dependencies. The local TTS models and config files will be placed in the `harmoni_models/tts` directory.





## Parameters
Parameters input for the aws polly service: 


| Parameters           | Definition | Values |
|----------------------|------------|--------|
|region_name           |    region of the Amazon Polly service        |string, e.g., "eu-west-2"        |
|voice                 |   voice of Amazon Polly         | string, e.g., "Amy"       |
|language              | language to synthetise the text       | string, e.g., "en-UK"       |
|outdir                |   path of the directory where you want to save your temporary audio data         | string, e.g.,"$(find harmoni_tts)/temp_data"     |
|wav_header_length      |    hearder length of the wav file generated        | int, e.g., 24       |

Parameters input for the local TTS service [TO UPDATE!]:
| Parameters           | Definition | Values |
|----------------------|------------|--------|
|tts_config            |            |        |
|tts_model             |            |        |
|vocoder_config        |            |        |
|vocoder_model         |            |        |
|scale_stats_path      |            |        |
|use_cuda              |            |        |
|verbose               |            |        |
|speedup               |            |        |
|outdir                |            |        |
|sample_rate           |            |        |

## Testing

The local test will save a wav file of the speech specified in the tts.test test_tts_input parameter in the temp_data directory. 

To test that the amazon polly speaker has been configured properly, use the command ```rostest harmoni_tts polly.test```
## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_tts.html)

[Mozilla TTS](https://github.com/mozilla/TTS)
