# HARMONI on ROS 1

All the original HARMONI packages (ROS 1 Noetic, plus a kinetic image for the NAO), with their docker
images, compose files and scripts. This folder is the catkin workspace content: the docker containers
mount it at `/root/harmoni_catkin_ws/src/HARMONI`.

Use it from the repository root with `./harmoni.sh ros1 <command>` (`./harmoni.sh ros1 help`).
Quickstart: `doc/quickstart/Docker-Quickstart.md`. Tests: `./run_tests.sh unit` (from this folder).

ROS 1 Noetic reached its end of life in 2025: new interactions should be written as tree files in
`../core` and run on ROS 2 (`../ros2`).
