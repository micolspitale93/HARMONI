# HARMONI Speaker


You can run this module in the `harmoni_full` or/and  `harmoni_hardware` containers.


## Usage
The speaker device is configured in the dockerfiles/config/asoundrc file, whose contents are shown below:

```
pcm.!default {
  type plug
  slave {
    pcm "hw:0,0"
  }
}
ctl.!default {
  type hw
  card 1n
}
```

The speaker device is controlled by the hw values, currently listed as 0,0. To choose a speaker you may need to use the command ```aplay -L ``` to see what devices are available.


The following documentation refers to the spaeker do.

The API for Speaker has:

- Request Name: ActionType: DO
- Body: data(str): 
  - inputting string of a dict that contains audio data {"audo_data": data(AudioData)}, where data is a binary audio data in the format of AudioData from audio_common_messages ROS library 
  - inputting string of a location of .wav file
- Response:
    - response (int): SUCCESS, or FAILURE
    - message (str): the DO action as no response message


You can run the service as follows: 
```roslaunch harmoni_speaker speaker_service.launch```

### Robot speakers (Furhat and NAO)

The Furhat and NAO speakers make the robot say a sentence (with the robot own text-to-speech) and look at the person
it is talking to.

The API for the robot speakers has:
- Request Name: ActionType: DO
- Body: data(str): JSON string `{"input": "<text to say>", "addressee": "<participant name>"}`. The addressee is
  optional: when it is empty, `"null"` or a list of names (`"Sarah, Jane"`) the robot does not turn to anyone.
  A plain (non JSON) string is said as it is.
- Response:
    - response (int): SUCCESS, or FAILED (robot unreachable or error of the robot API)

**Furhat** uses the [Furhat Remote API](https://docs.furhat.io/remote-api/) (enable the Remote API skill on the robot):
```roslaunch harmoni_speaker speaker_service_robots.launch use_furhat:=true```

**NAO** uses the NAOqi SDK, which only supports python 2.7. For this reason the NAO speaker is split in two nodes:
- `speaker_service_nao.py` (noetic, `harmoni_full` container): the HARMONI service;
- `apis_nao_node.py` (kinetic, `harmoni_nao` container, see `docker-compose-group-study.yml`): the bridge to the robot,
  which offers the ROS service `/nao/speak` and listens to `/speaker_nao/connect` and `/speaker_nao/addressee`.

Start the HARMONI service first and then the bridge (`./harmoni.sh run group` does it for you):
```bash
roslaunch harmoni_speaker speaker_service_nao.launch          # in harmoni_full
rosrun harmoni_speaker apis_nao_node.py                      # in harmoni_nao
```

## Parameters
There are no Parameters input for the local speaker service.

The robot speakers read `config/configuration.yaml` (`speaker/furhat_param`, `speaker/nao_param`):

| Parameters           | Definition | Values |
|----------------------|------------|--------|
|robot_ip              |  IP address of the robot on the local network      |str; e.g., "192.168.1.101"     |
|mockup                |  1 to run without the robot (the text is only logged)      |int; 0 or 1     |


## Testing

To test that the speaker has been configured properly, use the command ```rostest harmoni_speaker speaker.test``` which will play a short phrase through the configured device. You may need to experiement with different values to ensure the proper speaker is set up.

The robot speaker nodes can be tested without the robots (mockup mode) with:
```bash
rostest harmoni_speaker speaker_furhat_mock.test
rostest harmoni_speaker speaker_nao_mock.test
```

Unit tests that do not need ROS nor robots (run from the repository root):
```bash
python3 -m pytest harmoni_actuators/harmoni_speaker
```

## References
[Documentation](https://harmoni20.readthedocs.io/en/latest/packages/harmoni_speaker.html)
