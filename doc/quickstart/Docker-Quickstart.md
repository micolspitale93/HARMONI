# Docker Setup [recommended]

HARMONI runs in a set of docker containers that share a ROS network. The `harmoni.sh`
script in the repository root wraps all the docker commands you need.

## Requirements

- Linux (on Windows use WSL2; macOS is not supported because of device and display forwarding)
- Docker Engine: [https://docs.docker.com/engine/install/ubuntu/](https://docs.docker.com/engine/install/ubuntu/). Verify with `docker run hello-world`.
- Docker Compose **v2** (`docker compose`, with a space): [https://docs.docker.com/compose/install/](https://docs.docker.com/compose/install/)
- About 20 GB of free disk space for the complete set of images.

To use docker without `sudo`:
```bash
sudo usermod -aG docker ${USER}
# then log out and log in again
```

## Install

1. Clone the repository on the HARMONI 2.0 branch:
   ```bash
   git clone -b dev/harmoni2.0 https://github.com/micolspitale93/HARMONI.git
   cd HARMONI
   ```

2. Run the setup:
   ```bash
   ./harmoni.sh setup
   ```
   It checks that docker works, creates `.env` from [`.env.example`](https://github.com/micolspitale93/HARMONI/blob/dev/harmoni2.0/.env.example)
   and creates the `~/.aws` and `~/.gcp` folders that are mounted in the containers
   (if docker creates them, they are owned by root and hard to edit).

3. Get the images. Pulling is much faster than building:
   ```bash
   ./harmoni.sh pull          # or: ./harmoni.sh build
   ```

4. **(optional)** Add the credentials of the cloud services you want to use (OpenAI, Azure, AWS, Google)
   following the [Cloud Services section](../configuration/Cloud-Services).

## Run HARMONI

1. Start the containers:
   ```bash
   ./harmoni.sh up            # basic setup: harmoni_full, harmoni_hardware, harmoni_fer, harmoni_detectors
   ./harmoni.sh up full       # all the containers (adds harmoni_face_detector and harmoni_imageai)
   ./harmoni.sh up group      # group interaction study (harmoni_full_group and harmoni_nao)
   ```
   Devices that are not present on your machine (webcam `/dev/video0`, sound card `/dev/snd`, GPU `/dev/dri`)
   are skipped automatically with a warning, so the containers start anyway.

2. Open a terminal in a container (repeat in new terminals for more processes):
   ```bash
   ./harmoni.sh shell                 # harmoni_full
   ./harmoni.sh shell harmoni_hardware
   ```
   You will see:
   ```bash
   Hello! Welcome to Harmoni 2.0
   11:47 AM [dev/harmoni2.0] ~/harmoni_catkin_ws/src/HARMONI :
   root@harmoni_full#
   ```
   The folder `~/harmoni_catkin_ws/src/HARMONI` **is your local clone** (it is mounted in the container):
   there is no need to checkout branches inside the container, and files edited on the host are immediately available.

3. The first time, and every time you pull code that changes messages/services or adds packages, build the workspace:
   ```bash
   ./harmoni.sh build-ws
   ```

4. From a container terminal you can now launch `roscore` or any HARMONI service, e.g.
   ```bash
   roslaunch harmoni_bot bot_service.launch
   ```
   If `roscore` started correctly you will see `started core service [/rosout]`.
   ![packges](../images/roscore.png)

5. Stop everything with:
   ```bash
   ./harmoni.sh down
   ```

You are now set up for Harmoni with Docker! Check on your [configuration here](../Configuration) and then [start some services here](../tutorials/Launching-Services).

### Local speech models

The local DeepSpeech STT and Coqui TTS need model files in `harmoni_models/` (they are not in git).
Download them once with:
```bash
./harmoni.sh models
```

### Without the helper script

`harmoni.sh` only calls docker compose, so you can also use the compose files directly:
```bash
docker compose -f docker-compose-basic.yml up -d
docker exec -it harmoni_full bash
docker compose -f docker-compose-basic.yml down
```

| Compose file | Containers |
|--------------|------------|
| `docker-compose-basic.yml` | harmoni_full, harmoni_hardware, harmoni_fer, harmoni_detectors |
| `docker-compose.yml` | the basic ones + harmoni_face_detector, harmoni_imageai |
| `docker-compose-group-study.yml` | harmoni_full_group (noetic) and harmoni_nao (kinetic, NAOqi SDK), host network |

## Troubleshooting

1. **`cannot talk to the docker daemon`**: start docker (`sudo systemctl start docker`) and make sure your user is in the `docker` group.
2. **`error gathering device information`** when starting the containers: run them with `./harmoni.sh up`, which removes missing devices, or remove the device from the compose file.
3. **No window / display errors** (e.g. rviz, face): run `xhost +local:` on the host (done automatically by `./harmoni.sh up`).
4. **`~/.aws` or `~/.gcp` owned by root**: they were created by docker before `./harmoni.sh setup`. Fix with `sudo chown -R $USER ~/.aws ~/.gcp`.
5. **`ImportError: cannot import name 'nao_speak'`** or other missing messages: the workspace has not been built with the current code, run `./harmoni.sh build-ws`.
6. **git complains about `dubious ownership`** inside the container:
   ```bash
   git config --global --add safe.directory /root/harmoni_catkin_ws/src/HARMONI
   ```
