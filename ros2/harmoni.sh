#!/bin/bash
# HARMONI ROS2 docker helper. Usually called through the dispatcher in the repository root:
#   ./harmoni.sh ros2 <command>
#
#   setup                  check docker, create .env in the repository root
#   build | pull           build (or pull) the ROS2 image (and the NAO bridge with --nao)
#   up [--nao]             start the ROS2 container (and the NAO bridge)
#   down                   stop the containers
#   status                 show the containers
#   shell                  open a terminal in the ROS2 container
#   build-ws               colcon build the ROS2 workspace (after adding packages or interfaces)
#   run group              start the group interaction (real robots and cloud services)
#   run group-mock         start the group interaction with mock services (no robots, no keys)
#   run <config.yaml>      start the services and tree of any configuration file in ros2/config
#   tree <command>         send pause | resume | stop | reload to the running tree
#   monitor                show the running tree, live, in the terminal
#   validate [tree.json]   check a tree file (default: the group interaction)
#   test                   run the core and ros2 unit tests (no ROS needed, runs on the host)
#   smoke-test             run the mock group interaction on real ROS 2 in the container
#   studio                 HARMONI Studio in the container: also monitors ROS 2 trees (http://localhost:8800)
#   modules-install        install the python requirements of the HARMONI modules in the container
#
# Environment: ROS_DISTRO (default jazzy), ROS_DOMAIN_ID (default 0)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
ENV_FILE="$REPO/.env"
COMPOSE_FILE="$ROOT/docker-compose.yml"
CONTAINER=harmoni_ros2
STATE_DIR="$ROOT/.harmoni"
mkdir -p "$STATE_DIR"
cd "$ROOT"

info() { printf '\033[36m[harmoni ros2]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[harmoni ros2] WARNING:\033[0m %s\n' "$*"; }
die() { printf '\033[31m[harmoni ros2] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

require_docker() {
    command -v docker >/dev/null 2>&1 || die "docker is not installed: https://docs.docker.com/engine/install/"
    docker compose version >/dev/null 2>&1 || die "docker compose v2 is not installed: https://docs.docker.com/compose/install/"
    docker info >/dev/null 2>&1 || die "cannot talk to the docker daemon (is it running? is your user in the 'docker' group?)"
}

compose() {
    local args=(-f "$COMPOSE_FILE")
    [ -f "$STATE_DIR/devices.override.yml" ] && args+=(-f "$STATE_DIR/devices.override.yml")
    docker compose "${args[@]}" "$@"
}

# Start without /dev/snd on machines without a sound card
write_device_override() {
    rm -f "$STATE_DIR/devices.override.yml"
    if [ ! -e /dev/snd ]; then
        warn "/dev/snd not found: starting without audio devices (the Azure diarization needs a microphone)"
        printf 'services:\n  harmoni_ros2:\n    devices: !reset []\n' > "$STATE_DIR/devices.override.yml"
    fi
}

ros_exec() {
    local tty=(-i)
    [ -t 0 ] && [ -t 1 ] && tty=(-it)
    docker exec "${tty[@]}" "$CONTAINER" bash -c "source /opt/ros/\$ROS_DISTRO/setup.bash; \
        [ -f \$HARMONI_WS/install/setup.bash ] && source \$HARMONI_WS/install/setup.bash; \
        cd /root/HARMONI/ros2 && $*"
}

require_running() {
    docker ps --format '{{.Names}}' | grep -qx "$CONTAINER" || die "the ROS2 container is not running: ./harmoni.sh ros2 up"
}

cmd_setup() {
    require_docker
    if [ ! -f "$ENV_FILE" ]; then
        cp "$REPO/.env.example" "$ENV_FILE"
        info "created .env in the repository root: add the keys of the cloud services you use"
    else
        info ".env already exists in the repository root"
    fi
    echo "Next: ./harmoni.sh ros2 build   then   ./harmoni.sh ros2 up   then   ./harmoni.sh ros2 run group-mock"
}

profile_args() {
    for arg in "$@"; do [ "$arg" = "--nao" ] && echo "--profile nao"; done
}

cmd_build() { require_docker; compose $(profile_args "$@") build; }
cmd_pull() { require_docker; compose pull harmoni_ros2 || warn "no published image: use ./harmoni.sh ros2 build"; }

cmd_up() {
    require_docker
    [ -f "$ENV_FILE" ] || cmd_setup
    write_device_override
    compose $(profile_args "$@") up -d
    compose ps
    echo "Next: ./harmoni.sh ros2 run group-mock   (or run group with robots and keys)"
}

cmd_down() { require_docker; compose --profile nao down; }
cmd_status() { require_docker; compose --profile nao ps; }
cmd_shell() { require_docker; require_running; docker exec -it "$CONTAINER" bash; }

cmd_build_ws() {
    require_docker; require_running
    ros_exec "cd \$HARMONI_WS && python3 -m colcon build --symlink-install --base-paths /root/HARMONI/ros2/src"
}

cmd_run() {
    local target="${1:-}"
    local config
    case "$target" in
        group) config="config/group_interaction.yaml" ;;
        group-mock) config="config/group_interaction_mock.yaml" ;;
        *.yaml|*.yml) config="$target" ;;
        *) die "Usage: ./harmoni.sh ros2 run group | group-mock | <config.yaml>" ;;
    esac
    [ -f "$ROOT/$config" ] || [ -f "$config" ] || die "configuration not found: $config"
    require_docker; require_running
    if [ "$target" = group ]; then
        grep -q '^AZURE_OPENAI_API_KEY=.\+' "$ENV_FILE" 2>/dev/null || warn "AZURE_OPENAI_API_KEY is empty in .env"
        grep -q '^MICROSOFT_SPEECH_KEY=.\+' "$ENV_FILE" 2>/dev/null || warn "MICROSOFT_SPEECH_KEY is empty in .env"
        docker ps --format '{{.Names}}' | grep -qx harmoni_nao_bridge || warn "NAO bridge not running: ./harmoni.sh ros2 up --nao"
    fi
    info "launching $config (monitor it from another terminal with ./harmoni.sh ros2 monitor)"
    ros_exec "ros2 launch harmoni_nodes group_interaction.launch.py config:=/root/HARMONI/ros2/${config#./}"
}

cmd_tree() {
    local command="${1:-}"
    case "$command" in pause|resume|stop|reload) ;; *) die "Usage: ./harmoni.sh ros2 tree pause|resume|stop|reload" ;; esac
    require_docker; require_running
    ros_exec "ros2 topic pub --once /harmoni/tree/command std_msgs/msg/String '{data: $command}'"
}

cmd_monitor() { require_docker; require_running; ros_exec "ros2 run harmoni_nodes harmoni_monitor"; }

cmd_validate() {
    local tree="${1:-$REPO/core/trees/group_interaction.json}"
    PYTHONPATH="$REPO/core" python3 -m harmoni.tree validate "$tree"
}

cmd_studio() {
    require_docker; require_running
    info "HARMONI Studio on http://localhost:8800 (Ctrl+C to stop)"
    ros_exec "python3 -m harmoni.studio --root /root/HARMONI --host 127.0.0.1 --port \${HARMONI_STUDIO_PORT:-8800}"
}

cmd_modules_install() {
    require_docker; require_running
    ros_exec 'for r in /root/HARMONI/modules/*/*/requirements.txt; do [ -s "$r" ] && echo "== $r" && pip install --quiet -r "$r"; done; echo done'
}

cmd_smoke_test() { require_docker; require_running; ros_exec "python3 tests/ros_smoke_test.py"; }

cmd_test() {
    if ! python3 -c "import pytest, py_trees, yaml" 2>/dev/null; then
        info "installing the test requirements (pytest, py_trees, pyyaml)"
        python3 -m pip install --quiet pytest py_trees pyyaml
    fi
    (cd "$REPO/core" && python3 -m pytest -q)
    (cd "$ROOT" && python3 -m pytest -q tests)
}

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

case "${1:-help}" in
    setup) shift; cmd_setup "$@" ;;
    build) shift; cmd_build "$@" ;;
    pull) shift; cmd_pull "$@" ;;
    up|start) shift; cmd_up "$@" ;;
    down|stop) shift; cmd_down "$@" ;;
    status|ps) shift; cmd_status "$@" ;;
    shell|exec) shift; cmd_shell "$@" ;;
    build-ws) shift; cmd_build_ws "$@" ;;
    run) shift; cmd_run "$@" ;;
    tree) shift; cmd_tree "$@" ;;
    monitor) shift; cmd_monitor "$@" ;;
    validate) shift; cmd_validate "$@" ;;
    test) shift; cmd_test "$@" ;;
    smoke-test) shift; cmd_smoke_test "$@" ;;
    studio) shift; cmd_studio "$@" ;;
    modules-install) shift; cmd_modules_install "$@" ;;
    help|-h|--help) usage ;;
    *) usage; exit 2 ;;
esac
