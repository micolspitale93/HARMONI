# Group Interaction (Furhat + NAO + LLM orchestrator)

HARMONI 2.0 includes a multi-party interaction in which two robots take part in a discussion
among 1 to 3 people:

- **Manny, the Mover** (Furhat): proposes ideas and moves the conversation forward;
- **Andrea, the Opposer** (NAO): questions assumptions and brings alternative perspectives.

An LLM *orchestrator* (an OpenAI Assistant on Azure) receives what each participant says, with the name of
the speaker (Azure speaker diarization), and decides whether a robot should intervene, which one, what it
should say and to whom.

The interaction exists in two versions:

- **ROS 2** (recommended): the tree file `core/trees/group_interaction.json`, run by the ROS 2 nodes
  (see [HARMONI 2.0 Architecture](../overview/HARMONI-2-Architecture));
- **ROS 1**: the original python tree `ros1/harmoni_core/harmoni_pytree/src/harmoni_pytree/pytree_group_interaction.py`.

Both follow the same steps and use the same script.

## How it works

```
GroupInteraction (Sequence)
├── Script                      next scene of scripts/group_interaction.json
├── Decide (Selector)
│   ├── Scripted scene          scripted line (introductions, closing)
│   └── LLM scene               ask the orchestrator, parse its decision
├── Speak (Selector)
│   ├── Stay silent             the orchestrator decided not to intervene: skip speaking
│   ├── Opposer speaks          NAO
│   └── Furhat says             Mover (default)
└── Listen (Selector)
    ├── Interaction finished    no listening after the closing scene
    └── Diarization STT         "<name>: <text>"
```

At each turn:

1. **Script** reads the next scene of the session from the script. A scene has `nlp: 0` (scripted: the
   robot `agent` says `utterance`, `$USERNAME1..3` are replaced with the participants' names) or `nlp: 1`
   (the LLM decides). After `max_scenes` turns (30) the closing scene is said and the interaction ends.
2. **Decide**: for LLM scenes the last transcription is sent to the orchestrator, whose JSON answer
   `{"intervene", "agent", "response", "addressee"}` is parsed.
3. **Speak**: if `intervene` is false the speaking step is skipped completely and the microphone is
   reopened; otherwise the selected robot speaks, turning to the `addressee`.
4. **Listen**: the Azure diarization returns the next utterance with the speaker name, or a "nobody is
   talking" prompt after `max_silence` seconds.

On ROS 2 every call has a timeout (`llm_timeout_s`, `speech_timeout_s`, `listen_timeout_s` variables of
the tree) and a robot that does not answer does not stop the interaction.

## Configuration

**ROS 2**: everything is in one file, `ros2/config/group_interaction.yaml`; the participants are written
once and reused (YAML anchor):

```yaml
participants: &participants "Sarah, Jane, Alex"
tree:
  variables: {session: 3session, user_names: *participants}
services:
  bot_default: {backend: assistant, assistant_id: asst_..., participants: *participants, scenario: ...}
  stt_default: {backend: azure_diarization, names: *participants}
  speaker_furhat: {backend: furhat, robot_ip: 192.168.1.101}
  speaker_nao: {backend: nao_http, bridge_url: http://localhost:8765}   # NAO_IP in .env
```

**ROS 1**: the participants' names must be the same, in the same order, in three files:

| File | Parameter |
|------|-----------|
| `ros1/harmoni_core/harmoni_pytree/config/group_configuration.yaml` | `session` (`1session`, `2session` or `3session` = number of participants), `user_names: "Sarah,Jane,Alex"` |
| `ros1/harmoni_detectors/harmoni_stt/config/sd_azure_configuration.yaml` | `names: "Sarah,Jane,Alex"`, `num_speakers: 3` |
| `ros1/harmoni_dialogues/harmoni_bot/config/configuration.yaml` | `participants: "Sarah, Jane, Alex"`, `num_speaker: 3`, `scenario`, `assistant_id` |

Robots: set `robot_ip` of `furhat_param` and `nao_param` in
`ros1/harmoni_actuators/harmoni_speaker/config/configuration.yaml` (`mockup: 1` to run without the robot).

Credentials (both versions): `AZURE_OPENAI_API_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `MICROSOFT_SPEECH_KEY`,
`MICROSOFT_SPEECH_REGION` in `.env`, see [Cloud Services](../configuration/Cloud-Services).

## Run on ROS 2

```bash
./harmoni.sh ros2 build --nao     # once; the NAO bridge needs the NAOqi SDK (ros2/nao_bridge/README.md)
./harmoni.sh ros2 up --nao
./harmoni.sh ros2 run group       # or: run group-mock, without robots and keys
./harmoni.sh ros2 monitor         # in another terminal: the tree, live
```

Without ROS at all, to try a change of the tree or of the script:

```bash
PYTHONPATH=core python3 -m harmoni.tree simulate core/trees/group_interaction.json \
    --services core/trees/group_interaction.mock.yaml
```

## Run on ROS 1

1. Build the NAO bridge image once (it needs the NAOqi SDK, see `ros1/dockerfiles/harmoni/kinetic/nao/README.md`):
   ```bash
   ./harmoni.sh ros1 build group
   ```
2. Start the containers and build the workspace:
   ```bash
   ./harmoni.sh ros1 up group
   ./harmoni.sh ros1 build-ws harmoni_full_group
   ```
3. Start the interaction:
   ```bash
   ./harmoni.sh ros1 run group
   ```
   This launches `roslaunch harmoni_pytree root_group.launch` in `harmoni_full_group` and, 15 seconds later,
   the NAO bridge (`apis_nao_node.py`) in `harmoni_nao`. The web page showing the listening/processing
   state is served at [http://localhost:8082](http://localhost:8082).

Without the robots: set `mockup: 1` for both robots in `ros1/harmoni_actuators/harmoni_speaker/config/configuration.yaml`.

## Test

```bash
./harmoni.sh test                  # core, ros2 and ros1 unit tests, no ROS needed
./harmoni.sh ros2 smoke-test       # the mock interaction on real ROS 2
```

On ROS 1 (in the container): `rostest harmoni_speaker speaker_furhat_mock.test`, `speaker_nao_mock.test`,
`rostest harmoni_bot assistant.test` (Azure OpenAI keys), `rostest harmoni_stt sd_azure.test` (Azure Speech keys).
