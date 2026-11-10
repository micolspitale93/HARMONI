#!/bin/bash
# HARMONI ROS1 (noetic) docker helper: set up, start and use the ROS1 containers.
# Usually called through the dispatcher in the repository root:  ./harmoni.sh ros1 <command>
#
#   ./harmoni.sh ros1 setup                 check docker, create .env and credential folders
#   ./harmoni.sh ros1 pull   [setup]        pull the pre-built images (fastest way to start)
#   ./harmoni.sh ros1 build  [setup]        build the images locally instead of pulling them
#   ./harmoni.sh ros1 up     [setup]        start the containers in the background
#   ./harmoni.sh ros1 down   [setup]        stop and remove the containers
#   ./harmoni.sh ros1 status [setup]        show the running containers
#   ./harmoni.sh ros1 shell  [container]    open a shell in a container (default: harmoni_full)
#   ./harmoni.sh ros1 build-ws [container]  catkin build the workspace inside a container
#   ./harmoni.sh ros1 models                download local STT/TTS models into harmoni_models/
#   ./harmoni.sh ros1 test   [suite]        run tests: unit (local) | mock | cloud | hardware | all
#   ./harmoni.sh ros1 run group             start the group interaction study (Furhat + NAO)
#
# [setup] is one of:
#   basic  (default) docker-compose-basic.yml        full + hardware + fer + detectors
#   full             docker-compose.yml              all the noetic containers (~20 GB)
#   group            docker-compose-group-study.yml  full + NAO bridge, host network
#
# The setup used by the last `up` is remembered, so `down`/`status` need no argument.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"
ENV_FILE="$REPO/.env"   # shared by ROS1 and ROS2, passed to the containers with env_file
cd "$ROOT"
STATE_DIR="$ROOT/.harmoni"
mkdir -p "$STATE_DIR"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '\033[36m[harmoni]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[harmoni] WARNING:\033[0m %s\n' "$*"; }
die() { printf '\033[31m[harmoni] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

compose_file() {
    case "${1:-basic}" in
        basic) echo "docker-compose-basic.yml" ;;
        full) echo "docker-compose.yml" ;;
        group) echo "docker-compose-group-study.yml" ;;
        *) die "Unknown setup '$1'. Use: basic | full | group" ;;
    esac
}

current_setup() {
    if [ -n "${1:-}" ]; then echo "$1";
    elif [ -f "$STATE_DIR/setup" ]; then cat "$STATE_DIR/setup";
    else echo basic; fi
}

compose() {
    # compose <setup> <args...>
    local setup="$1"; shift
    local args=(-f "$(compose_file "$setup")")
    local override="$STATE_DIR/devices.$setup.override.yml"
    [ -f "$override" ] && args+=(-f "$override")
    docker compose "${args[@]}" "$@"
}

require_docker() {
    command -v docker >/dev/null 2>&1 || die "docker is not installed: https://docs.docker.com/engine/install/"
    docker compose version >/dev/null 2>&1 || die "docker compose v2 is not installed: https://docs.docker.com/compose/install/"
    docker info >/dev/null 2>&1 || die "cannot talk to the docker daemon. Is it running? Is your user in the 'docker' group? (sudo usermod -aG docker \$USER, then log out and in)"
}

default_container() {
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx harmoni_full_group; then
        echo harmoni_full_group
    else
        echo harmoni_full
    fi
}

ros_exec() {
    # ros_exec <container> <command>: run a command with the ROS environment sourced
    local container="$1"; shift
    local ws="/root/harmoni_catkin_ws"
    [ "$container" = "harmoni_nao" ] && ws="/nao/harmoni_catkin_ws"
    local tty=(-i)
    [ -t 0 ] && [ -t 1 ] && tty=(-it)
    docker exec "${tty[@]}" "$container" bash -c "source /opt/ros/\$ROS_DISTRO/setup.bash; \
        [ -f $ws/devel/setup.bash ] && source $ws/devel/setup.bash; \
        cd $ws/src/HARMONI && $*"
}

# Write an override file that keeps only the devices that exist on this machine, so that
# containers start on machines without a webcam / sound card.
write_device_override() {
    local setup="$1"
    local file; file="$(compose_file "$setup")"
    local override="$STATE_DIR/devices.$setup.override.yml"
    rm -f "$override"
    command -v python3 >/dev/null 2>&1 || { warn "python3 not found: skipping the device check"; return; }
    docker compose -f "$file" config --format json 2>/dev/null | python3 -c '
import json, os, sys
config = json.load(sys.stdin)
lines, missing = [], set()
for name, service in config.get("services", {}).items():
    devices = service.get("devices") or []
    present = []
    for d in devices:
        source = d["source"] if isinstance(d, dict) else d.split(":")[0]
        target = d.get("target", source) if isinstance(d, dict) else d.split(":")[1]
        if os.path.exists(source):
            present.append(f"{source}:{target}")
        else:
            missing.add(source)
    if len(present) != len(devices):
        lines.append(f"  {name}:")
        lines.append("    devices: !override")
        lines += [f"      - {p}" for p in present] if present else []
        if not present:
            lines[-1] = "    devices: !reset []"
if lines:
    print("# generated by harmoni.sh: devices missing on this machine: " + ", ".join(sorted(missing)))
    print("services:")
    print("\n".join(lines))
' > "$override.tmp" || true
    if [ -s "$override.tmp" ]; then
        mv "$override.tmp" "$override"
        warn "$(head -n1 "$override" | sed 's/# generated by harmoni.sh: //'). The containers will start without them."
    else
        rm -f "$override.tmp"
    fi
}

cmd_setup() {
    bold "HARMONI setup"
    require_docker
    info "docker $(docker --version | awk '{print $3}' | tr -d ,) and $(docker compose version --short 2>/dev/null | sed 's/^/compose /') found"

    if [ ! -f "$ENV_FILE" ]; then
        cp "$REPO/.env.example" "$ENV_FILE"
        info "created .env from .env.example in the repository root: add your API keys there (only for the cloud services you use)"
    else
        info ".env already exists in the repository root"
    fi

    # Create the credential folders mounted by docker compose. If they do not exist docker
    # creates them as root-owned folders.
    mkdir -p "$HOME/.aws"
    if [ ! -e "$HOME/.gcp/private-keys.json" ]; then
        mkdir -p "$HOME/.gcp/private-keys.json"
        info "created ~/.gcp/private-keys.json/ (put your Google key there as private-keys.json if you use Google services)"
    fi
    [ -f /etc/timezone ] || warn "/etc/timezone not found: remove that line from the compose file if docker complains"

    for d in /dev/snd /dev/video0 /dev/dri; do
        [ -e "$d" ] || warn "$d not found: containers will start without it (no $(case $d in /dev/snd) echo audio;; /dev/video0) echo camera;; *) echo GPU;; esac))"
    done

    echo
    bold "Next steps"
    echo "  ./harmoni.sh ros1 pull        # download the images (or ./harmoni.sh ros1 build)"
    echo "  ./harmoni.sh ros1 up          # start the containers"
    echo "  ./harmoni.sh ros1 shell       # open a terminal in harmoni_full"
}

cmd_up() {
    local setup; setup="$(current_setup "${1:-}")"
    require_docker
    [ -f "$ENV_FILE" ] || { warn ".env not found, running setup first"; cmd_setup; }
    if command -v xhost >/dev/null 2>&1 && [ -n "${DISPLAY:-}" ]; then
        xhost +local: >/dev/null 2>&1 || true
    fi
    write_device_override "$setup"
    echo "$setup" > "$STATE_DIR/setup"
    info "starting '$setup' ($(compose_file "$setup"))"
    compose "$setup" up -d --remove-orphans
    compose "$setup" ps
    echo
    bold "HARMONI is running"
    if [ "$setup" = group ]; then
        echo "  ./harmoni.sh ros1 run group           # start the group interaction"
        echo "  ./harmoni.sh ros1 shell harmoni_nao   # terminal in the NAO bridge container"
    else
        echo "  ./harmoni.sh ros1 shell               # terminal in harmoni_full"
        echo "  ./harmoni.sh ros1 build-ws            # rebuild the catkin workspace after pulling new code"
    fi
    echo "  ./harmoni.sh ros1 down                # stop everything"
}

cmd_down() {
    local setup; setup="$(current_setup "${1:-}")"
    require_docker
    compose "$setup" down
}

cmd_status() {
    local setup; setup="$(current_setup "${1:-}")"
    require_docker
    compose "$setup" ps
}

cmd_pull() {
    local setup; setup="$(current_setup "${1:-}")"
    require_docker
    # the NAO bridge image is not published: it has to be built (it needs the NAOqi SDK)
    if [ "$setup" = group ]; then
        compose "$setup" pull harmoni_full
        info "the harmoni_nao image must be built: ./harmoni.sh ros1 build group (see dockerfiles/harmoni/kinetic/nao/README.md)"
    else
        compose "$setup" pull
    fi
}

cmd_build() {
    local setup; setup="$(current_setup "${1:-}")"
    require_docker
    compose "$setup" build
}

cmd_shell() {
    local container="${1:-$(default_container)}"
    require_docker
    docker exec -it "$container" bash
}

cmd_build_ws() {
    local container="${1:-$(default_container)}"
    require_docker
    if [ "$container" = harmoni_nao ]; then
        ros_exec "$container" "cd ../.. && catkin build harmoni_speaker"
    else
        ros_exec "$container" "cd ../.. && catkin build"
    fi
}

cmd_models() {
    local container; container="$(default_container)"
    require_docker
    info "downloading DeepSpeech (STT) and Coqui (TTS) models into harmoni_models/ using $container"
    ros_exec "$container" "cd harmoni_models \
        && mkdir -p stt tts \
        && (cd stt && [ -f deepspeech-0.9.3-models.pbmm ] || wget -q --show-progress https://github.com/mozilla/DeepSpeech/releases/download/v0.9.3/deepspeech-0.9.3-models.pbmm) \
        && (cd stt && [ -f deepspeech-0.9.3-models.scorer ] || wget -q --show-progress https://github.com/mozilla/DeepSpeech/releases/download/v0.9.3/deepspeech-0.9.3-models.scorer) \
        && cd tts \
        && ([ -f tts_model.pth.tar ] || gdown --id 1dntzjWFg7ufWaTaFy80nRz-Tu02xWZos -O tts_model.pth.tar) \
        && ([ -f config.json ] || gdown --id 18CQ6G6tBEOfvCHlPqP8EBI4xWbrr9dBc -O config.json) \
        && ([ -f vocoder_model.pth.tar ] || gdown --id 1Ty5DZdOc0F7OTGj9oJThYbL5iVu_2G0K -O vocoder_model.pth.tar) \
        && ([ -f config_vocoder.json ] || gdown --id 1Rd0R_nRCrbjEdpOwq6XwZAktvugiBvmu -O config_vocoder.json) \
        && ([ -f scale_stats.npy ] || gdown --id 11oY3Tv0kQtxK_JPgxrfesa99maVXHNxU -O scale_stats.npy)"
}

cmd_test() {
    local suite="${1:-unit}"
    if [ "$suite" = unit ]; then
        ./run_tests.sh unit
    else
        require_docker
        ros_exec "$(default_container)" "./run_tests.sh $suite"
    fi
}

cmd_run() {
    case "${1:-}" in
        group)
            require_docker
            docker ps --format '{{.Names}}' | grep -qx harmoni_full_group || die "start the containers first: ./harmoni.sh ros1 up group"
            [ -f "$ENV_FILE" ] && grep -q '^AZURE_OPENAI_API_KEY=.\+' "$ENV_FILE" || warn "AZURE_OPENAI_API_KEY is empty in .env: the LLM orchestrator will not work"
            [ -f "$ENV_FILE" ] && grep -q '^MICROSOFT_SPEECH_KEY=.\+' "$ENV_FILE" || warn "MICROSOFT_SPEECH_KEY is empty in .env: speaker diarization will not work"
            info "the NAO bridge will start in harmoni_nao 15 s after the interaction (log: /tmp/nao_bridge.log in harmoni_nao)"
            # The bridge must start after speaker_service_nao is up, because it announces
            # itself once on /speaker_nao/start
            (sleep 15 && docker exec -d harmoni_nao bash -c "source /opt/ros/kinetic/setup.bash; \
                source /nao/harmoni_catkin_ws/devel/setup.bash; \
                rosrun harmoni_speaker apis_nao_node.py > /tmp/nao_bridge.log 2>&1") &
            ros_exec harmoni_full_group "roslaunch harmoni_pytree root_group.launch"
            ;;
        *) die "Usage: ./harmoni.sh ros1 run group" ;;
    esac
}

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

case "${1:-help}" in
    setup) shift; cmd_setup "$@" ;;
    up|start) shift; cmd_up "$@" ;;
    down|stop) shift; cmd_down "$@" ;;
    status|ps) shift; cmd_status "$@" ;;
    pull) shift; cmd_pull "$@" ;;
    build) shift; cmd_build "$@" ;;
    shell|exec) shift; cmd_shell "$@" ;;
    build-ws) shift; cmd_build_ws "$@" ;;
    models) shift; cmd_models "$@" ;;
    test) shift; cmd_test "$@" ;;
    run) shift; cmd_run "$@" ;;
    help|-h|--help) usage ;;
    *) usage; exit 2 ;;
esac
