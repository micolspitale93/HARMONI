# Testing

HARMONI has three test suites, one per folder, plus integration tests on real ROS:

| Suite | Where | Needs | Command |
|-------|-------|-------|---------|
| core | `core/tests` | python 3 (pytest, py_trees, pyyaml) | `./harmoni.sh test` (runs all three) |
| ros2 | `ros2/tests` | python 3; rclpy is faked | `./harmoni.sh ros2 test` |
| ros1 | `ros1/harmoni_*/*/test/unit` | python 3; rospy is faked | `cd ros1 && ./run_tests.sh unit` |
| ROS 2 end to end | `ros2/tests/ros_smoke_test.py` | the ROS 2 container | `./harmoni.sh ros2 smoke-test` |
| Studio in a browser | `core/tests/e2e/studio.e2e.js` | node + Playwright (Chromium) | `core/tests/e2e/run_studio_e2e.sh` |
| ROS 1 rostest | `ros1/harmoni_*/*/test/*.test` | the ROS 1 containers | `./harmoni.sh ros1 test mock\|cloud\|hardware` |

The unit tests need no ROS, no docker, no robots and no credentials, and run on GitHub for every push
(`.github/workflows/unit-tests.yaml`). The ROS 2 image is built and the smoke test is run on real ROS 2
by `.github/workflows/ros2.yaml`.

## Core and ROS 2

```bash
./harmoni.sh test                                    # core + ros2 + ros1 unit tests
cd core && python3 -m pytest -k group -v             # a subset
./harmoni.sh validate core/trees/my_tree.json        # check a tree file
```

The core tests also cover the module system (generation, loading, checks, private/public) and the HARMONI
Studio API on a real server; the browser test drives the whole dashboard (compose, simulate, services,
modules) on a throwaway copy of the workspace.

The core tests cover the tree format (validation, variables), every leaf, the runner (commands,
snapshots, errors), the service backends with fake SDKs, and the group interaction end to end with mock
services (scripted introductions, LLM turns, silence, robot failures, timeouts).

The ROS 2 tests fake `rclpy` (`ros2/tests/ros_fakes.py`) to check the wiring of the nodes: parameters,
topics, action results and goal tracking; the NAO bridge is tested over real HTTP. The smoke test then
runs the mock group interaction on real ROS 2 and waits until the tree reports `finished`.

## ROS 1

All the ROS 1 suites are run with `ros1/run_tests.sh` (or `./harmoni.sh ros1 test <suite>` from the host):

| Suite | Command | Needs |
|-------|---------|-------|
| unit | `./run_tests.sh unit` | python 3 only (installs `pytest` and `py_trees` if missing) |
| mock | `./run_tests.sh mock` | ROS (harmoni_full container); robots in mockup mode |
| cloud | `./run_tests.sh cloud` | credentials in `.env`, `~/.aws`, `~/.gcp` |
| hardware | `./run_tests.sh hardware` | microphone, camera, speaker, screen; some need a person talking |

### Unit tests

```bash
# from the ros1/ folder, on the host or in a container
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
| harmoni_pytree | `test/unit/test_group_interaction_leaves.py` | Group interaction leaves: LLM response parsing, script progression, speaker selection, silence skips speaking |
| harmoni_common_lib | `test/unit/test_constants_and_helpers.py` | constants contract and helper functions |

### Writing a unit test

The `ros1/conftest.py` puts every package `src` folder on the python path and replaces
`rospy`, `actionlib`, the ROS messages, `openai`, the Azure speech SDK and the Furhat API with fakes.
A minimal test of a new service looks like:

```python
# ros1/harmoni_<group>/harmoni_<pkg>/test/unit/test_my_service.py
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

### Integration tests (rostest)

Run inside a container (`./harmoni.sh ros1 shell`), after `./harmoni.sh ros1 build-ws`:

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

### Package Testing

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

### Integration Testing

Integration tests may be largely similar to package tests, except that they will involve more than one package and in certain instances may require user interaction or mock user interaction.
The behavior trees in `harmoni_pytree/test/*_test/` combine several packages (e.g. microphone, STT, bot, TTS and speaker).
