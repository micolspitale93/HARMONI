# NAO bridge

HTTP bridge between HARMONI (ROS2, python 3) and the NAO robot (NAOqi SDK, python 2.7 only).
It replaces the ROS kinetic container of the ROS1 setup: no ROS is needed on the python 2 side.

1. Download the NAOqi python SDK for linux (`pynaoqi-python2.7-<version>-linux64.tar.gz`) and put it in this folder (it is ignored by git).
2. Set `NAO_IP` in the `.env` file of the repository root.
3. Start it with the ROS2 setup: `./harmoni.sh ros2 up --nao`.

Check it with `curl http://localhost:8765/health` and
`curl -X POST -d '{"text": "Hello"}' http://localhost:8765/say`.

Without robot: `NAO_MOCK=1` (and build with `--build-arg NAOQI_SDK=none`).
