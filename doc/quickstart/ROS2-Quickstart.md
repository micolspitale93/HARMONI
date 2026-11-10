# ROS 2 Docker Setup [recommended]

The ROS 2 setup (folder `ros2/`) runs HARMONI trees on ROS 2 Jazzy. It uses the ROS-independent core
(`core/`) described in [HARMONI 2.0 Architecture](../overview/HARMONI-2-Architecture).

## Requirements

- Linux with Docker Engine and Docker Compose v2.24 or newer (`docker compose version`)
- About 5 GB of disk space

## Install and run

```bash
git clone -b dev/harmoni2.0 https://github.com/micolspitale93/HARMONI.git
cd HARMONI
./harmoni.sh ros2 setup        # creates .env in the repository root
./harmoni.sh ros2 build        # builds the ROS 2 image (about 10 minutes the first time)
./harmoni.sh ros2 up           # starts the harmoni_ros2 container
./harmoni.sh ros2 run group-mock
```

`run group-mock` runs the whole group interaction on ROS 2 with mock services: every service is a real
ROS 2 node, but answers with canned responses, so no robot, microphone or API key is needed. In another
terminal you can follow the tree live and control it:

```bash
./harmoni.sh ros2 monitor
./harmoni.sh ros2 tree pause      # resume | stop | reload
```

To check an installation end to end: `./harmoni.sh ros2 smoke-test`.

## With the robots and cloud services

1. Add the keys to `.env` (see [Cloud Services](../configuration/Cloud-Services)): `AZURE_OPENAI_API_ENDPOINT`,
   `AZURE_OPENAI_API_KEY`, `MICROSOFT_SPEECH_KEY`, `MICROSOFT_SPEECH_REGION`, and `NAO_IP`.
2. Put the NAOqi SDK in `ros2/nao_bridge/` (see its README).
3. Edit `ros2/config/group_interaction.yaml`: participants, assistant id, Furhat IP.
4. Start and run:
   ```bash
   ./harmoni.sh ros2 build --nao
   ./harmoni.sh ros2 up --nao
   ./harmoni.sh ros2 run group
   ```

## Working in the container

```bash
./harmoni.sh ros2 shell
ros2 topic list                       # /harmoni/<service_id>/result, /harmoni/tree/status, ...
ros2 launch harmoni_nodes group_interaction.launch.py config:=/root/HARMONI/ros2/config/<file>.yaml
```

The repository is mounted at `/root/HARMONI`, so changes to `core/` and to the nodes are used directly.
After adding a ROS 2 package or changing `harmoni_interfaces`, rebuild the workspace with
`./harmoni.sh ros2 build-ws`.

ROS 2 tools on the host (or Foxglove) see the nodes, since the container uses the host network; set the
same `ROS_DOMAIN_ID` (default 0).

## A new configuration

A configuration file says which backend serves each service id and which tree to run:

```yaml
participants: &participants "Sarah, Jane"
tree:
  file: core/trees/group_interaction.json
  variables: {session: 2session, user_names: *participants}
services:
  stt_default: {backend: azure_diarization, names: *participants}
  speaker_furhat: {backend: furhat, robot_ip: 192.168.1.101}
  ...
```

Run it with `./harmoni.sh ros2 run config/<file>.yaml`.

## Troubleshooting

- **`/dev/snd not found`**: the container starts without audio; the Azure diarization needs a microphone.
- **`service 'X' is not available`** in the tree log: the service node did not start (see its log in the
  `run` output) or its backend failed `setup()` (e.g. missing keys).
- **The NAO does not speak**: `curl http://localhost:8765/health` must answer; check `NAO_IP` in `.env`.
- **To use another ROS 2 distribution**: `ROS_DISTRO=humble ./harmoni.sh ros2 build`.
