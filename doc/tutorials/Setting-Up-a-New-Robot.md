# Setting Up A Robot

HARMONI is currently running on two robots: QT robot and Misty II robot.
We hope that you can contribute integrating it to other robots.

## QT robot

The QT robot is composed by a NUC Intel in its chest and a Raspberry Pi on its head.
The NUC Intel is connect to the motor actuators, while the Raspberry Pi is connected to the speaker, microphone, and face.
We will run the master 'harmoni_full' HARMONI2.0 on the chest and the harmoni_hardware on the Pi.

When you login into the NUC you can build and run the following docker-compose for the harmoni_full (if you want you can also use the complete docker-compose with the other containers such as harmoni_fer):

```
version: "3.9"

services:
  harmoni_full:
    container_name: harmoni_full
    build:
      context: .
      dockerfile: dockerfiles/harmoni/noetic/full/dockerfile
      network: host
    image: harmoniteam/harmoni:noetic-full
    init: true
    environment:
      DISPLAY: $DISPLAY
      #QT_GRAPHICSSYSTEM: native
      ROS_MASTER_URI: http://192.168.100.1:11311 
      IS_DOCKER_ENV: "true"
      #ROS_HOSTNAME: harmoni_full
      CATKIN_WS: harmoni_catkin_ws
    privileged: true
    #network_mode: host
    hostname: harmoni_full
    ports:
      - "11312:11312"
      - "33691:33691"
      - "8081:8081" #harmoni_face
      - "8082:8082" #harmoni_web
    devices:
      - /dev/dri:/dev/dri
      - /dev/snd:/dev/snd
      - /dev/video0:/dev/video0
    volumes:
      - ../HARMONI/:/root/local_mount/HARMONI/
      # Configuration
      - ~/.aws:/root/.aws/
      - ~/.gcp/private-keys.json:/root/.gcp/private-keys.json
      # Other
      - /tmp/.X11-unix:/tmp/.X11-unix
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
    working_dir: /root/harmoni_catkin_ws/src/HARMONI
    command: tail  -f /dev/null

volumes:
    harmoni_catkin_ws:
```

While, when we login into the Pi, we need to run a lightwight container for arm architecture provided by HARMONI as follows:

```
docker run -it --name harmoni_hardware --network host --init \
--device=/dev/snd:/dev/snd \
-e "ROS_MASTER_URI=$ROS_MASTER_URI" \
-e "ROS_HOSTNAME=$ROS_HOSTNAME" \
-e "ROS_IP=$ROS_IP" \
-e "ROS_DISTRO=kinetic" \
-e "CATKIN_WS=harmoni_catkin_ws" \
-e "IS_DOCKER_ENV=true" \
-v /home/qtrobot/harmoni_catkin_ws/src/HARMONI/ros1/dockerfiles/config/setup_script.sh:/root/.setup_script.sh \
-v /home/qtrobot/harmoni_catkin_ws/src/HARMONI/ros1/dockerfiles/config/dev_setup_script.sh:/root/.dev_setup_script.sh \
-v /home/qtrobot/harmoni_catkin_ws/src/HARMONI/ros1/dockerfiles/config/asoundrc:/root/.asoundrc \
-v /tmp/.X11-unix:/tmp/.X11-unix \
-v /home/qtrobot/.gitconfig:/root/.gitconfig:ro \
-v /home/qtrobot/.ssh/:/root/.ssh:ro \
-v /home/qtrobot/.vimrc:/root/.vimrc:ro \
-v /home/qtrobot/.vim/:/root/.vim/:ro \
-v /etc/timezone:/etc/timezone:ro \
-v /etc/localtime:/etc/localtime:ro \
-w "/root/harmoni_catkin_ws/src/HARMONI" \
harmoniteam/lightweight:harmoni
```

### Running the interaction on QT robot

To start the interaction at the beginning of the day:
1. Please plug in the robot (it should automatically switch on)
2. Then connect to the same WiFi network (with your hotspot) from your laptop
3. To find the IPROBOT use the Fing app in the tablet and look for the mac number: E4:5F:01:6E:4E:7C (or the device name: Raspberry Pi) - it should be connected to the same network of the robot
4. Open THREE terminals and ssh into the robot NUC running the following commands (run it 3 times, one for each terminal):
```
ssh developer@IPROBOT (psw: XX)
```
5. From Terminal 3 run the following to ssh into the NUC and enter the container in the NUC:
```
ssh qtrobot@192.168.100.2 (psw:XX)
docker exec -it harmoni_core /bin/bash
```
6. From Terminal 1 and 2, you have already ssh into the PI of the robot running the following (run the commands twice, 1 for each terminal):
```
sudo docker exec -it harmoni_hardware /bin/bash
```
7. You are now inside the container of the PI from Terminal 1 and 2 (root@QTRD000306), and container of the NUC from Terminal 3 (root@QTPC)
8. From Terminal 1 (inside the container), run the following command:
```
roslaunch harmoni_speaker speaker_play.launch
```
9.From Terminal 3 run the following command to start the interaction:
```
roslaunch harmoni_pytree root_minja.launch
```
10. From Terminal 2 run the following command to start the face (important to make it on time otherwise you have to restart the interaction again, if you make it on time you will see the face of the robot on its screen):
```
export DISPLAY=:0 && luakit -U 'http://192.168.100.2:8081'
```
11. Remember to kill the interaction with Ctrl+C when the user has done with the interaction, otherwise it will keep collecting rosbag data
12. Kill Terminal 3, Terminal 2, and Terminal 1

## Misty II robot