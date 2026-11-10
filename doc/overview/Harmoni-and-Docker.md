# Harmoni and Docker

## What is Docker?
Docker is a tool for developing and running containers, which are virtual machines that runs in parallel with your OS. There is a lot that could be said about Docker, but you can read more [here](https://www.docker.com/).

## Why Docker?
Although Harmoni will work without Docker, Harmoni is intended to be used with Docker to maximize portability and scalability. By using Docker Harmoni is quick and easy to set up on any OS or Hardware which currently supports docker.  We provide pre-built images for development, lightweight images for deployment, and even support for deploying to ARM chipsets.

## Docker Containers
We provide two sets of docker images. The first set is a heavier development set of images, which are based off of a ubuntu-16 image and contain graphical tools for use in a typical development cycle. These are intended to be helpful for developing interactively on a new machine. We also provide a set of lightweight images for deployment to space constrained machines, as well as images built with the arm architecture. 

All containers are built on Ros noetic with python 3.6. In future releases we may build containers entirely without python2.7, including a ros installation that is built on python3.6. We may also choose to jump directly to Ros 2.

## Container Organization
Harmoni spreads the workload across several containers to maximize CPU usage. This includes a `harmoni_full` container, a container for interfacing with the hardware named `harmoni_hardware`, a container for each detector used such as `harmoni_face_detector` (for running OpenFace), `harmoni_imageai` (for running YOLO), and `harmoni_detectors` (e.g., for running openSMILE).

The `harmoni_full` container is responsible for the following:

   - Actuators:
      - harmoni_face (to display the face on the screen)
      - harmoni_web (to use a web GUI)
      - harmoni_speaker (to play audio)
      - harmoni_gesture (to perform gestures on the robot)
   - Detectors:
      - harmoni_sentiment (to analyse the sentiment of the text)
      - harmoni_stt (to transcribe speech from audio streaming)
   - Dialogues:
      - harmoni_rl (to run reinforcement learning models to make decisions in the dialogue flow)
      - harmnoni_bot (to process natural language using NLP models, such as ChatGPT or AWS Lex)
   - Sensors:
      - harmoni_microphone (to sense audio from the laptop/robot mic where the container is running)
      - harmoni_camera (to sense images from the laptop/robot camera where the container is running)

[Optional] The `harmoni_hardware` container can be responsible for the following (you can run everything on `harmoni_full` if there are not required any specific dependencies):

   - Sensors (that are not in the same device where the `harmoni_full` container is running):
      - harmoni_microphone (to sense audio from the laptop/robot mic where the container is running)
      - harmoni_camera (to sense images from the laptop/robot camera where the container is running)
   - Actuators (that are not in the same device where the `harmoni_full` container is running)::
      - harmoni_speaker (to play audio)
      - harmoni_gesture (to perform gestures on the robot)

The `harmoni_face_detector` container is responsible for the following:

   - Detectors:
      - harmoni_openface (to run OpenFace and extract facial action units)

The `harmoni_detectors` container is responsible for the following:

   - Detectors:
      - harmoni_opensmile (to run openSMILE and extract audio features)
      - harmoni_vad (to detect voice activity from audio streaming)

The `harmoni_fer` container is responsible for the following:

   - Detectors:
      - harmoni_fer (to recognize facial expressions)

The `harmoni_imageai` container is responsible for the following:

   - Detectors:
      - harmoni_imageai (to recognize objects)


Note that if you try to run a module that belongs to a different container (e.g., running harmoni_fer into the harmoni_full container) it is not going to work because we decide to allocate it to a separate container for dependencies issues. The containers provided have already the required versioning libraries for each of the module to run correctly.

## Getting started
Unless adding a new node which requires additional libraries that have not been included, it unlikely you will need to modify the dockerfiles. Once Docker has been installed, you should be able to quickly get up and running with docker-compose. Docker-compose files have been provided which launch core, hardware, and detector containers. You may need to modify the network, devices, or volumes to suit your hardware configuration.

Additional instructions for building and running images are provided in the [ros1/dockerfiles/README.md](https://github.com/micolspitale93/HARMONI/blob/dev/harmoni2.0/ros1/dockerfiles/README.md)
