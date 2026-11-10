![logo](logo.svg)

[![Documentation Status](https://readthedocs.org/projects/harmoni-20/badge/?version=latest)](https://harmoni-20.readthedocs.io/en/latest/)
[![unit-tests](https://github.com/micolspitale93/HARMONI/actions/workflows/unit-tests.yaml/badge.svg?branch=dev/harmoni2.0)](https://github.com/micolspitale93/HARMONI/actions/workflows/unit-tests.yaml)

Welcome to the project for Human And Robot Modular & OpeN Interactions! (HARMONI - we know it is a stretch but we love it) HARMONI is a ROS based tool for creating and controlling human-robot interaction. HARMONI is an open source (MIT License) tool meant to speed up development, collaboration, and experimentation for the HRI community.

Repository: https://github.com/micolspitale93/HARMONI/

Full Documentation: https://harmoni-20.readthedocs.io/en/latest/

## What is in HARMONI 2.0

HARMONI is organised in ROS packages, each wrapping one capability as a service that can be requested by a behavior tree ([py_trees](https://py-trees.readthedocs.io/)):

| Group | Packages |
|-------|----------|
| Sensors | `harmoni_microphone`, `harmoni_camera` |
| Detectors | `harmoni_stt` (Google, DeepSpeech, **Azure speaker diarization**), `harmoni_face_detect`, `harmoni_fer`, `harmoni_imageai`, `harmoni_openface`, `harmoni_opensmile`, `harmoni_vad`, `harmoni_detcustom` |
| Dialogues | `harmoni_bot` (AWS Lex, Dialogflow, ChatGPT, **OpenAI Assistants**), `harmoni_rl` |
| Actuators | `harmoni_tts`, `harmoni_speaker` (local audio, **Furhat**, **NAO**), `harmoni_face`, `harmoni_gesture`, `harmoni_web`, `harmoni_sentiment` |
| Core | `harmoni_common_lib`, `harmoni_pytree` (behavior trees and leaves), `harmoni_recorder`, `harmoni_decision`, `harmoni_pattern` |

New in 2.0: a **multi-party group interaction** in which an LLM orchestrator decides when one of two robots
(Furhat as the *Mover*, NAO as the *Opposer*) should intervene in a discussion among 1-3 people,
using Azure speaker diarization to know who is speaking. See the
[group interaction tutorial](doc/tutorials/Group-Interaction.md).

## Quickstart (Docker)

Requirements: Linux, [Docker](https://docs.docker.com/engine/install/) and Docker Compose v2.

```bash
git clone -b dev/harmoni2.0 https://github.com/micolspitale93/HARMONI.git
cd HARMONI
./harmoni.sh setup     # checks docker, creates .env and the credential folders
./harmoni.sh pull      # downloads the images (or: ./harmoni.sh build)
./harmoni.sh up        # starts the containers in the background
./harmoni.sh shell     # opens a terminal in the harmoni_full container
```

Your local clone is mounted in the containers, so code changes on the host are used directly.
Add the API keys of the cloud services you need to `.env` (see [.env.example](.env.example)).

| Command | What it does |
|---------|--------------|
| `./harmoni.sh up [basic\|full\|group]` | start a setup (`basic` by default, `group` for the group study) |
| `./harmoni.sh down` | stop the containers |
| `./harmoni.sh shell [container]` | open a terminal in a container |
| `./harmoni.sh build-ws` | `catkin build` the workspace inside the container (after pulling new code) |
| `./harmoni.sh run group` | start the group interaction study |
| `./harmoni.sh test [unit\|mock\|cloud\|hardware]` | run the tests |
| `./harmoni.sh models` | download the local STT/TTS models |

More details: [Docker quickstart](doc/quickstart/Docker-Quickstart.md) · [Cloud services](doc/configuration/Cloud-Services.md) · [Installing without Docker](doc/quickstart/pc-quickstart.md)

## Testing

```bash
./run_tests.sh unit    # ROS-free unit tests (pytest), runs anywhere in a few seconds
./harmoni.sh test mock # ROS integration tests inside the container, no robot or cloud needed
```

See [Testing](doc/Testing.md) for the cloud and hardware suites and for how to write new tests.

# Call for Contributions
We hope you will enjoy and find use in our project. We always welcome developments on new robots or with modules. To learn more about developing new modules please see [here](https://harmoni-20.readthedocs.io/en/latest/Contributions.html). We also have a backlog of [issues](https://github.com/micolspitale93/HARMONI/issues) and welcome pull requests.
