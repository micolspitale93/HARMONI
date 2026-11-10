#!/bin/bash
# Run the HARMONI test suites.
#
#   ./run_tests.sh unit       ROS-free unit tests (pytest). Works on any machine with python3,
#                             no ROS, robots or credentials needed. This is what CI runs.
#   ./run_tests.sh mock       rostests that need ROS (run inside the harmoni_full container)
#                             but no robots or cloud credentials (robots in mockup mode).
#   ./run_tests.sh cloud      rostests that call cloud services (OpenAI/Azure, AWS, Google).
#                             Need the credentials described in .env.example.
#   ./run_tests.sh hardware   rostests that need a microphone, camera, speaker or screen.
#   ./run_tests.sh all        everything above.
#
# Default: unit

set -u
SUITE="${1:-unit}"
FAILED=()

cd "$(dirname "$0")"

run() {
    echo
    echo "=================================================================="
    echo ">> $*"
    echo "=================================================================="
    if ! "$@"; then
        FAILED+=("$*")
    fi
}

unit() {
    if ! python3 -c "import pytest, py_trees" 2>/dev/null; then
        echo "Installing unit test requirements (pytest, py_trees)..."
        python3 -m pip install --quiet pytest py_trees python-dotenv
    fi
    run python3 -m pytest
}

mock() {
    run rostest harmoni_speaker speaker_furhat_mock.test
    run rostest harmoni_speaker speaker_nao_mock.test
    run rostest harmoni_bot mock_lex.test
    run rostest harmoni_tts mock_polly.test
}

cloud() {
    run rostest harmoni_bot assistant.test      # Azure OpenAI Assistant (group interaction)
    run rostest harmoni_bot chatgpt.test        # OpenAI ChatGPT
    run rostest harmoni_bot lex.test            # AWS Lex
    run rostest harmoni_tts polly.test          # AWS Polly
    run rostest harmoni_stt google.test         # Google STT
}

hardware() {
    run rostest harmoni_microphone microphone.test
    run rostest harmoni_camera camera.test
    run rostest harmoni_speaker speaker.test
    run rostest harmoni_face face.test
    run rostest harmoni_web web.test
    run rostest harmoni_stt deepspeech.test
    run rostest harmoni_stt sd_azure.test       # Azure diarization, needs someone talking
    run rostest harmoni_face_detect dlib.test
}

case "$SUITE" in
    unit) unit ;;
    mock) mock ;;
    cloud) cloud ;;
    hardware) hardware ;;
    all) unit; mock; cloud; hardware ;;
    *) echo "Unknown suite '$SUITE'. Use: unit | mock | cloud | hardware | all"; exit 2 ;;
esac

echo
if [ ${#FAILED[@]} -eq 0 ]; then
    echo "All '$SUITE' tests passed."
else
    echo "Failed:"
    printf '  - %s\n' "${FAILED[@]}"
    exit 1
fi
