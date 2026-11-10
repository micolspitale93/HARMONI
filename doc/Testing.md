# Testing

HARMONI has two kinds of tests:

- **Unit tests** (`<package>/test/unit/test_*.py`, pytest): test the python logic of a service in
  isolation. ROS, robots and cloud SDKs are replaced by fakes, so they run anywhere in a few seconds
  and run automatically on GitHub for every push and pull request.
- **Integration tests** (`<package>/test/*.test`, rostest): start the real ROS nodes and
  talk to them through the HARMONI action servers. They run inside the containers.

All the suites are run with `run_tests.sh` (or `./harmoni.sh test <suite>` from the host):

| Suite | Command | Needs |
|-------|---------|-------|
| unit | `./run_tests.sh unit` | python 3 only (installs `pytest` and `py_trees` if missing) |
| mock | `./run_tests.sh mock` | ROS (harmoni_full container); robots in mockup mode |
| cloud | `./run_tests.sh cloud` | credentials in `.env`, `~/.aws`, `~/.gcp` |
| hardware | `./run_tests.sh hardware` | microphone, camera, speaker, screen; some need a person talking |

## Unit tests

```bash
# from the repository root, on the host or in a container
./run_tests.sh unit
# or directly
python3 -m pytest                                    # all packages
python3 -m pytest harmoni_dialogues/harmoni_bot      # one package
python3 -m pytest -k diarization -v                  # by name
```

Currently covered:

| Package | Test file | What is tested |
|---------|-----------|----------------|
| harmoni_bot | `test/unit/test_assistant_service.py` | OpenAI Assistant: input parsing, request/response, thread setup, every API error releases the action server |
| harmoni_stt | `test/unit/test_sd_azure_service.py` | Azure diarization: speaker-id to name mapping, transcription callbacks, silence timeout, microphone buffering |
| harmoni_speaker | `test/unit/test_robot_speakers.py` | Furhat and NAO speakers: payload parsing, addressee handling, mockup mode, robot errors |
| harmoni_pytree | `test/unit/test_group_interaction_leaves.py` | Group interaction leaves: LLM response parsing, script progression, speaker selection |
| harmoni_common_lib | `test/unit/test_constants_and_helpers.py` | constants contract and helper functions |

### Writing a unit test

The repository root `conftest.py` puts every package `src` folder on the python path and replaces
`rospy`, `actionlib`, the ROS messages, `openai`, the Azure speech SDK and the Furhat API with fakes.
A minimal test of a new service looks like:

```python
# harmoni_<group>/harmoni_<pkg>/test/unit/test_my_service.py
from harmoni_common_lib.constants import State
from harmoni_mypkg.my_service import MyService


def test_request_succeeds(published):
    service = MyService("mypkg_default", {"param": 1})
    result = service.request("hello")
    assert result["response"] == State.SUCCESS
    # messages published with rospy.Publisher are recorded
    assert published("/harmoni/.../default") == ["hello"]
```

Useful fixtures: `published(topic)` (messages published on a topic), `ros_params` (dict backing `rospy.get_param`).
Replace external clients with fakes using pytest's `monkeypatch` (see the existing tests).
Always make sure that every error path sets `self.response_received = True` in `request()`,
otherwise the HARMONI action server waits forever.

## Integration tests (rostest)

Run inside a container (`./harmoni.sh shell`), after `./harmoni.sh build-ws`:

```bash
rostest harmoni_speaker speaker_furhat_mock.test   # Furhat speaker node, mockup mode
rostest harmoni_speaker speaker_nao_mock.test      # NAO speaker node, mockup mode
rostest harmoni_bot assistant.test                 # Azure OpenAI Assistant (needs .env keys)
rostest harmoni_stt sd_azure.test                  # Azure diarization, speak when asked
rostest harmoni_speaker speaker.test               # plays a wav on the local speaker
```

There are three levels of testing:
- Unit Testing - _Do individual classes/functions run as expected?_
- Package Testing - _Do packages perform the function requested?_
- Integration Testing - _Do packages communicate with each other as expected?_

## Package Testing

Package testing for sensors, actuators, and dialogues is ideally performed on real hardware. Some testing using simulation and/or rosbags in place of hardware is also acceptable. Package tests should force the package to perform some subset of the functionality the package provides and verify the output.

  - harmoni_actuators: _Force the actuator to do something and verify the correct message is published._
    - harmoni_face
    - harmoni_speaker
    - harmoni_tts
    - harmoni_web
    - etc.
  - harmoni_detectors - _Take a sample input and output the appropriate detection._
    - harmoni_face_detect
    - harmoni_stt
    - etc.
  - harmoni_dialogues - _Take a sample phrase and return the expected response._
    - harmoni_bot
  - harmoni_sensors - _Read from a sensor_
    - harmoni_camera
    - harmoni_microphone
    - etc.
  - harmoni_core - _Tested during integration._

## Integration Testing

Integration tests may be largely similar to package tests, except that they will involve more than one package and in certain instances may require user interaction or mock user interaction.
The behavior trees in `harmoni_pytree/test/*_test/` combine several packages (e.g. microphone, STT, bot, TTS and speaker).
