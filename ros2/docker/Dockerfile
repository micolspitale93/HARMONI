# HARMONI ROS2 image (default: ROS 2 Jazzy, Ubuntu 24.04)
#
# Build context: the repository root (it needs core/ and ros2/):
#   docker compose -f ros2/docker-compose.yml build      (or ./harmoni.sh ros2 build)
#
# Python packages that are not in apt (OpenAI, Azure Speech, Furhat) are installed in a virtual
# environment that also sees the system packages (rclpy, py_trees), as recommended for
# Ubuntu 24.04. colcon is run with that python so that the node executables use it too.
ARG ROS_DISTRO=jazzy
FROM ros:${ROS_DISTRO}-ros-base
ARG ROS_DISTRO

ENV ROS_DISTRO=${ROS_DISTRO} \
    HARMONI_ROOT=/root/HARMONI \
    HARMONI_WS=/root/harmoni_ws \
    HARMONI_VENV=/opt/harmoni-venv \
    PYTHONUNBUFFERED=1
SHELL ["/bin/bash", "-c"]

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3-pip python3-venv python3-yaml python3-pytest \
        ros-${ROS_DISTRO}-py-trees \
        ros-${ROS_DISTRO}-rosbridge-server \
        ca-certificates alsa-utils nano iputils-ping curl \
    && (DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libasound2t64 libssl3t64 \
        || DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libasound2 libssl3) \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv --system-site-packages ${HARMONI_VENV} \
    && ${HARMONI_VENV}/bin/pip install --no-cache-dir \
        "openai>=1.0" \
        azure-cognitiveservices-speech \
        furhat-remote-api \
        python-dotenv
ENV PATH=${HARMONI_VENV}/bin:${PATH} \
    PYTHONPATH=${HARMONI_ROOT}/core

# Same paths as at runtime (docker compose mounts the repository on ${HARMONI_ROOT}), so that
# the symlinked install keeps working with your local code.
COPY core ${HARMONI_ROOT}/core
COPY ros2/src ${HARMONI_ROOT}/ros2/src
RUN source /opt/ros/${ROS_DISTRO}/setup.bash \
    && mkdir -p ${HARMONI_WS} && cd ${HARMONI_WS} \
    && python3 -m colcon build --symlink-install --base-paths ${HARMONI_ROOT}/ros2/src \
    && source ${HARMONI_WS}/install/setup.bash \
    && python3 -c "import rclpy, harmoni.tree, harmoni.services, harmoni_nodes.config; from harmoni_interfaces.action import Harmoni; print('HARMONI ROS2 image OK')"

COPY ros2/docker/entrypoint.sh /harmoni_entrypoint.sh
RUN chmod +x /harmoni_entrypoint.sh \
    && echo 'source /opt/ros/${ROS_DISTRO}/setup.bash' >> /root/.bashrc \
    && echo '[ -f ${HARMONI_WS}/install/setup.bash ] && source ${HARMONI_WS}/install/setup.bash' >> /root/.bashrc \
    && echo 'echo "Hello! Welcome to HARMONI 2.0 on ROS 2 ${ROS_DISTRO}"' >> /root/.bashrc

WORKDIR ${HARMONI_ROOT}/ros2
ENTRYPOINT ["/harmoni_entrypoint.sh"]
CMD ["bash"]
