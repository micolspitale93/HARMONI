# Group Interaction (Furhat + NAO + LLM orchestrator)

HARMONI 2.0 includes a multi-party interaction in which two robots take part in a discussion
among 1 to 3 people:

- **Manny, the Mover** (Furhat): proposes ideas and moves the conversation forward;
- **Andrea, the Opposer** (NAO): questions assumptions and brings alternative perspectives.

An LLM *orchestrator* (an OpenAI Assistant on Azure) receives what each participant says, with the name of
the speaker (Azure speaker diarization), and decides whether a robot should intervene, which one, what it
should say and to whom.

## How it works

The behavior tree is defined in `harmoni_pytree/src/harmoni_pytree/pytree_group_interaction.py`:

```
GroupInteraction (Sequence)
├── DialogueStateProcessing   web: red light, the robots are "thinking"
├── Script                    next scene of resources/group_interaction.json
├── LLM Assistant             asks the orchestrator what to do (only for LLM scenes)
├── Agent Selector (Selector)
│   ├── Mover   (speaker_furhat)
│   └── Opposer (speaker_nao)
└── Listening (Parallel)
    ├── Diarization           Azure STT: "<name>: <text>"
    └── DialogueStateListening web: green light, the robots are listening
```

At each turn:

1. **Script** (`leaves/script_group_dialogue_service.py`) reads the next scene of the session from
   `harmoni_pytree/resources/group_interaction.json`. A scene has `nlp: 0` (scripted: the robot `agent` says
   `utterance`, `$USERNAME1..3` are replaced with the participants' names) or `nlp: 1` (the LLM decides).
   After `max_number_scene` turns (30) the closing utterance (last scene) is said.
2. **LLM Assistant** (`leaves/assistant_service.py`) sends the last transcription to
   `harmoni_bot/assistant_service.py` and parses the JSON answer
   `{"intervene", "agent", "response", "addressee"}`. If `intervene` is false the robots stay silent.
3. **Agent Selector**: each speaker leaf succeeds only if it is the selected agent, so exactly one robot speaks,
   turning to the `addressee`.
4. **Listening**: `harmoni_stt/sd_azure_service.py` returns the next utterance with the speaker name.

## Configuration

The participants' names must be the same, in the same order, in three files:

| File | Parameter |
|------|-----------|
| `harmoni_core/harmoni_pytree/config/group_configuration.yaml` | `session` (`1session`, `2session` or `3session` = number of participants), `user_names: "Sarah,Jane,Alex"` |
| `harmoni_detectors/harmoni_stt/config/sd_azure_configuration.yaml` | `names: "Sarah,Jane,Alex"`, `num_speakers: 3` |
| `harmoni_dialogues/harmoni_bot/config/configuration.yaml` | `participants: "Sarah, Jane, Alex"`, `num_speaker: 3`, `scenario`, `assistant_id` |

Robots: set `robot_ip` of `furhat_param` and `nao_param` in
`harmoni_actuators/harmoni_speaker/config/configuration.yaml` (`mockup: 1` to run without the robot).

Credentials: `AZURE_OPENAI_API_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `MICROSOFT_SPEECH_KEY`,
`MICROSOFT_SPEECH_REGION` in `.env`, see [Cloud Services](../configuration/Cloud-Services).

## Run

1. Build the NAO bridge image once (it needs the NAOqi SDK, see `dockerfiles/harmoni/kinetic/nao/README.md`):
   ```bash
   ./harmoni.sh build group
   ```
2. Start the containers and build the workspace:
   ```bash
   ./harmoni.sh up group
   ./harmoni.sh build-ws harmoni_full_group
   ```
3. Start the interaction:
   ```bash
   ./harmoni.sh run group
   ```
   This launches `roslaunch harmoni_pytree root_group.launch` in `harmoni_full_group` and, 15 seconds later,
   the NAO bridge (`apis_nao_node.py`) in `harmoni_nao`. The web page showing the listening/processing
   state is served at [http://localhost:8082](http://localhost:8082).

### Without the robots

Set `mockup: 1` for both robots in `harmoni_speaker/config/configuration.yaml`: the robot sentences are
printed in the log instead of being said. You can then run only the `harmoni_full_group` container.

## Test

```bash
python3 -m pytest harmoni_core/harmoni_pytree harmoni_dialogues/harmoni_bot \
    harmoni_detectors/harmoni_stt harmoni_actuators/harmoni_speaker   # no ROS needed
rostest harmoni_speaker speaker_furhat_mock.test                       # in the container
rostest harmoni_speaker speaker_nao_mock.test
rostest harmoni_bot assistant.test                                     # needs Azure OpenAI keys
rostest harmoni_stt sd_azure.test                                      # needs Azure Speech keys
```
