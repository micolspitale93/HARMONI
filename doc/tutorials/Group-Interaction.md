# Group Interaction: humans and robots moderated by an LLM

This is an example of a multi-party interaction built with HARMONI: robots take part in a discussion
among a group of people (in the study: three students negotiating how to share an apartment), and an LLM
*orchestrator* decides at every turn whether a robot intervenes, which one, what it says and to whom.
Nothing in HARMONI is specific to it: the same building blocks work with any number of humans and of
robots (see *Cast* below).

In the study configuration:

- **Manny** plays the **Mover** (proposes ideas, moves the discussion forward);
- **Sam** plays the **Opposer** (questions assumptions, offers alternatives), or a second Mover in the
  homogeneous condition;
- the robots show the state of the dialogue with their LEDs: red while processing, green while listening;
- Azure speaker diarization tells who is speaking.

The interaction exists in two versions:

- **ROS 2** (recommended): the tree file `core/trees/group_interaction.json`, run by the ROS 2 nodes;
- **ROS 1**: the original python tree `ros1/harmoni_core/harmoni_pytree/src/harmoni_pytree/pytree_group_interaction.py`.

## How it works (ROS 2 tree)

```
GroupInteraction (Sequence)
├── Processing light          AgentsAction: every agent's LED red
├── Script                    DialogueScript: next scene of scripts/group_interaction.json
├── Decide (Selector)
│   ├── Scripted scene        the agent of the scene says the scripted line
│   └── Orchestrator scene    ask the orchestrator, parse its decision
├── Chosen agent speaks       AgentSpeak: the chosen role speaks with its own robot (silent turns are skipped)
└── Listen (Selector)
    ├── Interaction finished  no listening after the closing scene
    └── Listening
        ├── Speech to text + every agent's LED green (Parallel)
        └── Log what was said
```

At each turn:

1. **Script** reads the next scene of the session (`1session`, `2session`, `3session`: chosen from the number
   of humans). A scene is scripted (`nlp: 0`: the agent with role `agent` says `utterance`; `$USERNAME1..`
   are replaced with the names) or decided by the orchestrator (`nlp: 1`). After the introductions the
   orchestrator is told to start the negotiation; after `max_scenes` turns the closing scene is said.
2. **Decide**: the last transcription (`"<name>: <text>"`) is sent to the orchestrator, whose JSON answer
   `{"intervene", "agent", "response", "addressee"}` is parsed; `agent` is a **role** of the cast.
3. **Chosen agent speaks**: if `intervene` is false nobody speaks and the microphone is reopened;
   otherwise the agent with that role speaks on its own speech service.
4. **Listen**: Azure diarization returns the next utterance with the speaker name, or a prompt to reignite
   the conversation after `max_silence` seconds; it is added to the conversation log.

Every call has a timeout (`llm_timeout_s`, `speech_timeout_s`, `listen_timeout_s` variables) and a robot
that does not answer does not stop the interaction.

## Cast: any number of humans and robots

The tree never names a robot: it addresses **roles**. The cast of the tree says who takes part:

```json
"cast": {
  "humans": "${participants}",
  "agents": [
    {"role": "Mover", "name": "Manny", "robot": "Furhat", "services": {"speech": "speaker_furhat", "led": "led_furhat"}},
    {"role": "Opposer", "name": "Sam", "robot": "NAO", "services": {"speech": "speaker_nao", "led": "led_nao"}}
  ]
}
```

Adding a third robot (e.g. a *Moderator* on Pepper) means adding one agent to the cast and its services
to the configuration, and telling the orchestrator about the role; the tree stays the same. The cast can
be edited in HARMONI Studio (Compose → Tree settings → Cast) and overridden by configurations and runs.

## The study conditions

The conditions only change the cast, the script and the assistant, so they are small configurations that
`extend` the base one (`ros2/config/`):

| Condition | Configuration | Roles |
|-----------|---------------|-------|
| heterogeneous | `group_interaction.yaml` | Mover = Manny on Furhat, Opposer = Sam on NAO |
| heterogeneous, inversed | `group_interaction_het_inversed.yaml` | Mover on NAO, Opposer on Furhat |
| homogeneous | `group_interaction_homog.yaml` | Mover1 = Manny on Furhat, Mover2 = Sam on NAO, homogeneous script and assistant |
| homogeneous, inversed | `group_interaction_homog_inversed.yaml` | Mover1 on NAO, Mover2 on Furhat |

```yaml
# group_interaction_het_inversed.yaml
extends: group_interaction.yaml
tree:
  cast:
    agents:
      Mover: {robot: NAO, services: {speech: speaker_nao, led: led_nao}}
      Opposer: {robot: Furhat, services: {speech: speaker_furhat, led: led_furhat}}
```

The participants are written once at the top of `group_interaction.yaml` (`participants: &participants
"Micol, Emmanuel, Yukun"`, in the order Azure detects the speakers) and reused for the cast, the
diarization and the assistant. Other settings there: the assistant ids, the scenario and the instruction to
balance the participation, the microphone (`device_name: "hw:1,0"`), the robot IPs (`NAO_IP` in `.env` for
the NAO bridge). Credentials: `AZURE_OPENAI_API_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `MICROSOFT_SPEECH_KEY`,
`MICROSOFT_SPEECH_REGION` in `.env`, see [Cloud Services](../configuration/Cloud-Services).

## Run on ROS 2

```bash
./harmoni.sh ros2 build --nao     # once; the NAO bridge needs the NAOqi SDK (ros2/nao_bridge/README.md)
./harmoni.sh ros2 up --nao
./harmoni.sh ros2 run group                                  # heterogeneous condition
./harmoni.sh ros2 run group_interaction_homog_inversed       # any other condition, by name
./harmoni.sh ros2 run group-mock                             # without robots, microphone or keys
./harmoni.sh ros2 monitor                                    # in another terminal: the tree, live
```

In HARMONI Studio (`./harmoni.sh ros2 studio`, page Run) you can follow the conversation and the
participation of each person and robot while the study runs.

Without ROS at all, to try a change of the tree, of the script or of the cast:

```bash
PYTHONPATH=core python3 -m harmoni.tree simulate core/trees/group_interaction.json \
    --services core/trees/group_interaction.mock.yaml --set participants="Micol, Jane"
```

## Run on ROS 1

The ROS 1 tree selects the condition with `condition` in
`ros1/harmoni_core/harmoni_pytree/config/group_configuration.yaml` (0 heterogeneous, 1 heterogeneous inversed,
2 homogeneous, 3 homogeneous inversed), together with `interaction` (`group_interaction` or
`group_interaction_homog`), `session`, `user_names` and `max_turns`. The assistant id is in
`ros1/harmoni_dialogues/harmoni_bot/config/configuration.yaml`, the LED service (`harmoni_led`) and the
robot IPs in their `config/configuration.yaml`.

```bash
./harmoni.sh ros1 build group          # once: the NAO image needs the NAOqi SDK
./harmoni.sh ros1 up group
./harmoni.sh ros1 build-ws harmoni_full_group
./harmoni.sh ros1 run group
```

This launches `roslaunch harmoni_pytree root_group.launch` (diarization, assistant, LED, speakers, rosbag
recording of the transcriptions and of the orchestrator) and, 15 seconds later, the NAO bridge in `harmoni_nao`.

## Test

```bash
./harmoni.sh test                  # core, ros2 and ros1 unit tests, no ROS needed
./harmoni.sh ros2 smoke-test       # the mock interaction on real ROS 2
```

The core tests run this tree with the study conditions and with three robots and two humans.
