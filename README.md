![logo](logo.svg)

[![Documentation Status](https://readthedocs.org/projects/harmoni-20/badge/?version=latest)](https://harmoni-20.readthedocs.io/en/latest/)
[![unit-tests](https://github.com/micolspitale93/HARMONI/actions/workflows/unit-tests.yaml/badge.svg?branch=dev/harmoni2.0)](https://github.com/micolspitale93/HARMONI/actions/workflows/unit-tests.yaml)

Welcome to the project for Human And Robot Modular & OpeN Interactions! (HARMONI - we know it is a stretch but we love it) HARMONI is a ROS based tool for creating and controlling human-robot interaction. HARMONI is an open source (MIT License) tool meant to speed up development, collaboration, and experimentation for the HRI community.

Repository: https://github.com/micolspitale93/HARMONI/

Full Documentation: https://harmoni-20.readthedocs.io/en/latest/

## Repository layout

HARMONI 2.0 separates the interaction logic from the middleware that runs it:

| Folder | What | ROS |
|--------|------|-----|
| [`core/`](core) | tree file format, tree runner, leaves and service backends (LLM, speech, robots) | none |
| [`ros2/`](ros2) | ROS 2 Jazzy docker setup and nodes running the core, NAO HTTP bridge | ROS 2 |
| [`ros1/`](ros1) | all the original HARMONI packages, docker images and scripts | ROS 1 Noetic |
| [`doc/`](doc) | documentation ([online](https://harmoni-20.readthedocs.io/en/latest/)) | |

ROS 1 Noetic reached its end of life in 2025: new interactions should be written as core tree files and run
on ROS 2. The ROS 1 packages are kept unchanged and working. See
[HARMONI 2.0 Architecture](doc/overview/HARMONI-2-Architecture.md).

### Packages (ROS 1) and backends (core / ROS 2)

| Group | ROS 1 packages | Core backends (ROS 2) |
|-------|----------------|----------------------|
| Sensors | `harmoni_microphone`, `harmoni_camera` | |
| Detectors | `harmoni_stt` (Google, DeepSpeech, Azure diarization), `harmoni_face_detect`, `harmoni_fer`, `harmoni_imageai`, `harmoni_openface`, `harmoni_opensmile`, `harmoni_vad`, `harmoni_detcustom` | `azure_diarization` |
| Dialogues | `harmoni_bot` (AWS Lex, Dialogflow, ChatGPT, OpenAI Assistants), `harmoni_rl` | `assistant` |
| Actuators | `harmoni_tts`, `harmoni_speaker` (audio, Furhat, NAO), `harmoni_face`, `harmoni_gesture`, `harmoni_web`, `harmoni_sentiment` | `furhat`, `nao_http` |
| Core | `harmoni_common_lib`, `harmoni_pytree`, `harmoni_recorder`, `harmoni_decision`, `harmoni_pattern` | tree runner, `mock` |

New in 2.0: a **multi-party group interaction** in which an LLM orchestrator decides when one of two robots
(Furhat as the *Mover*, NAO as the *Opposer*) should intervene in a discussion among 1-3 people,
using Azure speaker diarization to know who is speaking. See the
[group interaction tutorial](doc/tutorials/Group-Interaction.md).

## Quickstart

Requirements: Linux, [Docker](https://docs.docker.com/engine/install/) and Docker Compose v2.24+.

```bash
git clone -b dev/harmoni2.0 https://github.com/micolspitale93/HARMONI.git
cd HARMONI
```

**ROS 2** (recommended):

```bash
./harmoni.sh ros2 setup            # creates .env (API keys) in the repository root
./harmoni.sh ros2 build            # builds the ROS 2 Jazzy image
./harmoni.sh ros2 up               # starts the container
./harmoni.sh ros2 run group-mock   # the group interaction with mock services: no robots, no keys
./harmoni.sh ros2 monitor          # in another terminal: the running tree, live
```

**ROS 1**:

```bash
./harmoni.sh ros1 setup            # checks docker, creates .env and the credential folders
./harmoni.sh ros1 pull             # downloads the images (or: ./harmoni.sh ros1 build)
./harmoni.sh ros1 up               # basic | full | group
./harmoni.sh ros1 shell            # opens a terminal in harmoni_full
```

Run `./harmoni.sh ros2 help` or `./harmoni.sh ros1 help` for all the commands. Add the API keys of the cloud
services you need to `.env` (see [.env.example](.env.example)); it is shared by both setups.

More details: [ROS 2 quickstart](doc/quickstart/ROS2-Quickstart.md) · [ROS 1 quickstart](doc/quickstart/Docker-Quickstart.md) · [Cloud services](doc/configuration/Cloud-Services.md) · [Installing ROS 1 without Docker](doc/quickstart/pc-quickstart.md)

## HARMONI Studio: author interactions and modules in the browser

```bash
./harmoni.sh studio                # then open http://localhost:8800
./harmoni.sh ros2 studio           # in the ROS 2 container: also monitors trees running on ROS 2
```

- **Compose** behavior trees from the HARMONI nodes (drag and drop, forms generated from the node
  descriptions, validation while you edit), **Scripts** for scripted dialogues, **Services** to choose which
  module serves each service;
- **Run** a tree in simulation (mock services: no robots, no keys) or follow it live on ROS 2, with the tree
  status, the conversation and the blackboard; Studio only observes and sends commands between ticks;
- **Modules**: create new sensors, detectors, dialogues and actuators from a short description (working code,
  tests and examples are generated), test them, and keep them private or share them with everyone once their
  checks pass.

See [HARMONI Studio](doc/tutorials/HARMONI-Studio.md) and [Create a module](doc/tutorials/Create-a-Module.md).

## Authoring and testing interactions without ROS

```bash
./harmoni.sh validate core/trees/group_interaction.json
PYTHONPATH=core python3 -m harmoni.tree simulate core/trees/group_interaction.json \
    --services core/trees/group_interaction.mock.yaml
./harmoni.sh test                  # unit tests of core, ros2 and ros1 (no ROS, no docker)
./harmoni.sh ros2 smoke-test       # the mock group interaction on real ROS 2 (in the container)
```

See [Testing](doc/Testing.md).

# Call for Contributions
We hope you will enjoy and find use in our project. We always welcome developments on new robots or with modules. To learn more about developing new modules please see [here](https://harmoni-20.readthedocs.io/en/latest/Contributions.html). We also have a backlog of [issues](https://github.com/micolspitale93/HARMONI/issues) and welcome pull requests.
