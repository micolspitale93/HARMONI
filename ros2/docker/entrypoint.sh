#!/bin/bash
set -e
source "/opt/ros/${ROS_DISTRO}/setup.bash"
if [ -f "${HARMONI_WS}/install/setup.bash" ]; then
    source "${HARMONI_WS}/install/setup.bash"
fi
exec "$@"
