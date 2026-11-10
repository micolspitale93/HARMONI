#!/bin/bash
# HARMONI: one entry point for both middleware versions.
#
#   ./harmoni.sh ros2 <command>    ROS 2 (Jazzy): core trees + ROS2 nodes   -> ros2/harmoni.sh
#   ./harmoni.sh ros1 <command>    ROS 1 (Noetic): all the original packages -> ros1/harmoni.sh
#   ./harmoni.sh test              unit tests of core, ros1 and ros2 (no ROS or docker needed)
#   ./harmoni.sh validate [tree]   check a HARMONI tree file
#
# Run `./harmoni.sh ros1 help` or `./harmoni.sh ros2 help` for the commands of each setup.

set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

case "${1:-help}" in
    ros1) shift; exec "$REPO/ros1/harmoni.sh" "$@" ;;
    ros2) shift; exec "$REPO/ros2/harmoni.sh" "$@" ;;
    test)
        shift
        "$REPO/ros2/harmoni.sh" test
        (cd "$REPO/ros1" && ./run_tests.sh unit)
        ;;
    validate) shift; exec "$REPO/ros2/harmoni.sh" validate "$@" ;;
    help|-h|--help) usage ;;
    up|down|shell|setup|pull|build|status|run|build-ws|models)
        echo "HARMONI now has two setups: use './harmoni.sh ros2 $1' or './harmoni.sh ros1 $1'." >&2
        exit 2
        ;;
    *) usage; exit 2 ;;
esac
