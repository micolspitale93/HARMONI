#!/bin/bash
# Kept for backward compatibility: use ./harmoni.sh instead.
#   ./run_compose.sh            -> ./harmoni.sh up basic
#   ./run_compose.sh full       -> ./harmoni.sh up full
#   ./run_compose.sh group      -> ./harmoni.sh up group
exec "$(dirname "$0")/harmoni.sh" up "${1:-basic}"
