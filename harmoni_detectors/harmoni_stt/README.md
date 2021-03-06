# HARMONI STT

## Usage
## Parameters
## Testing
### Testing W2L 
Note: If running w2l, run get_w2l_models.sh before attempting to launch this service.

To test if the model has been built properly off of your microphone you can run the following in the terminal:

`ffmpeg -hide_banner -loglevel error -f alsa -i default -ar 16000 -ac 1 -ab 256k -f wav - | /root/wav2letter/build/inference/inference/examples/simple_streaming_asr_example --input_files_base_path=/root/model/w2l/`

`ffmpeg -hide_banner -loglevel error -f alsa -i hw:3 -ar 16000 -ac 1 -ab 256k -f wav - | /root/wav2letter/build/inference/inference/examples/simple_streaming_asr_example --input_files_base_path=/root/model/w2l/`

or

`roslaunch harmoni_detectors/harmoni_stt/launch/direct_stt_service.launch`

`ffmpeg -hide_banner -loglevel error -f alsa -i hw:3 -ar 16000 -ac 1 -ab 256k -f wav - | /root/wav2letter/build/inference/inference/examples/simple_streaming_asr_example --input_files_base_path=/root/model/w2l/`

`rostest harmoni_stt w2l.test --text`

To record your own test audio, use the following:

`arecord -r 16000 -d 6 -f S16_LE test_example.wav`

## References
[Documentation](https://harmoni.readthedocs.io/en/latest/packages/harmoni_stt.html)

https://trac.ffmpeg.org/wiki/Capture/ALSA