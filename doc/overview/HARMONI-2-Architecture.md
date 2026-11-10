# HARMONI 2.0 Architecture: core, ROS 2 and ROS 1

HARMONI 2.0 separates *what an interaction does* from *the middleware that runs it*:

```
HARMONI/
├── core/   ROS-independent python: tree format, runner, leaves, service backends (no ROS at all)
├── ros2/   ROS 2 (Jazzy) layer: docker image, nodes wrapping the core, NAO HTTP bridge
├── ros1/   ROS 1 (Noetic) layer: all the original HARMONI packages, docker images and scripts
└── doc/    this documentation
```

| | core | ros2 | ros1 |
|---|---|---|---|
| Depends on ROS | no | ROS 2 Jazzy | ROS 1 Noetic (+ kinetic for NAO) |
| Interaction logic | tree files (JSON) | runs core tree files | python behavior trees (`harmoni_pytree`) |
| Services | backends (python classes) | one generic node per backend | one package per service |
| Status | new | new, recommended for new projects | original HARMONI, maintained |

ROS 1 Noetic reached its end of life in May 2025: the ROS 1 code is kept unchanged in `ros1/`, and
new work goes in `core/` (logic) and `ros2/` (middleware).

## The core (`core/harmoni`)

### Tree files

An interaction is a JSON (or YAML) file describing a [py_trees](https://py-trees.readthedocs.io/)
behavior tree. Nothing in it refers to ROS: the same file runs on ROS 2, in the simulator, or in tests.

```json
{
  "harmoni_tree": 1,
  "name": "Hello",
  "variables": {"robot": "speaker_furhat", "timeout_s": 30},
  "root": {
    "type": "Sequence", "name": "Main",
    "children": [
      {"type": "ServiceAction", "name": "Listen",
       "params": {"service": "stt_default", "output_key": "stt/result", "timeout_s": "${timeout_s}"}},
      {"type": "ServiceAction", "name": "Greet",
       "params": {"service": "${robot}", "action": "DO",
                  "input_json": {"input": "Hello!"}}}
    ]
  }
}
```

- **Composites**: `Sequence`, `Selector` (fallback), `Parallel`.
- **Leaves** (`python -m harmoni.tree describe` prints them with their parameters):
  - `ServiceAction`: calls any HARMONI service (all services share the same interface: an action type,
    REQUEST/DO/ON/OFF, and a string payload, answered with ok + message);
  - `CheckValue`, `SetValue`, `CopyValue`, `Wait`: blackboard conditions/assignments and pauses;
  - multi-party: `AgentSpeak` (the agent chosen by role speaks with its own service), `AgentsAction`
    (every agent acts on a channel, e.g. LEDs), `LogUtterance`, `DialogueScript`, `ScriptedTurn`,
    `OrchestratorDecision`.
- **Variables**: `"${name}"` takes the value (and type) of a variable, which can be overridden from a
  configuration file; `"Hello ${name}"` is string interpolation.
- **Blackboard**: keys such as `bot/message`; `"@bot/message"` in `input_json` reads the blackboard.
- **Validation** before running: unknown node types or parameters, wrong types, missing required
  parameters are errors; keys read but never written are warnings.

```bash
./harmoni.sh validate core/trees/group_interaction.json
PYTHONPATH=core python3 -m harmoni.tree simulate core/trees/group_interaction.json \
    --services core/trees/group_interaction.mock.yaml          # no ROS, no robots
```

### Cast: any number of humans and agents

A tree can declare its **cast**: the humans, and the agents (robots, virtual agents) with their **role**,
name, robot and services per channel:

```json
"cast": {
  "humans": ["Sarah", "Jane", "Alex"],
  "agents": [
    {"role": "Mover", "name": "Manny", "robot": "Furhat", "services": {"speech": "speaker_furhat", "led": "led_furhat"}},
    {"role": "Opposer", "name": "Sam", "robot": "NAO", "services": {"speech": "speaker_nao", "led": "led_nao"}}
  ]
}
```

Leaves address agents by role and channel, never by robot, so one tree works with any number of robots and
people. The runner puts the cast on the blackboard (`cast/*`) and every spoken turn in the conversation log
(`conversation`: who said what to whom), which monitoring tools display generically.

Configurations (and runs) can override the cast: `humans` replaces the participants, `agents` as a list
replaces the agents, `agents` as a mapping updates the agents with those roles (e.g. to swap which robot plays
which role). With `extends`, an experimental condition is a few lines over a base configuration:

```yaml
extends: group_interaction.yaml
tree:
  cast:
    agents:
      Mover: {robot: NAO, services: {speech: speaker_nao, led: led_nao}}
```

### Service backends

A backend (`core/harmoni/services`) contains the logic of a service, e.g. the Azure diarization or the
Furhat speaker, as a plain python class with `request()`/`do()` methods. Adding a new sensor, detector
or actuator means writing one class:

```python
from harmoni.services import Result, ServiceBackend, register_backend

@register_backend("raised_hand")
class RaisedHandDetector(ServiceBackend):
    def setup(self):
        self.model = load_model(self.params["model_path"])

    def request(self, data):
        return Result(True, json.dumps(self.model.detect()))
```

It can then be used from a ROS 2 configuration (`backend: raised_hand`) and from tree files
(`ServiceAction` with `service: <its id>`), without writing any ROS code. Such classes are packaged as
**modules** (`modules/private` or `modules/public`), generated by HARMONI Studio or
`harmoni.modules.generator`: see [Create a module](../tutorials/Create-a-Module).

## Design rules

### The UI is never in the control loop

The tree runner (`harmoni.tree.TreeRunner`, wrapped by the ROS 2 node `harmoni_tree`) ticks the tree on
its own clock. Authoring and monitoring tools interact with it only through:

- **files**: a tool edits the tree file, then sends `reload`;
- **commands** (`pause`, `resume`, `stop`, `reload` on `/harmoni/tree/command`) queued and applied
  *between* two ticks; an invalid edit puts the runner in `error` but never crashes it;
- **snapshots**: after every tick the runner publishes a JSON snapshot of the tree (status of every node)
  and of the blackboard on `/harmoni/tree/status` (latched). A slow or crashed dashboard cannot delay
  the interaction, and a dashboard that connects later still receives the current state.

`./harmoni.sh ros2 monitor` is a minimal example of such a tool; [HARMONI Studio](../tutorials/HARMONI-Studio)
is the complete one (authoring, simulation, live monitoring, modules).

### Robot timing

Leaves never block a tick: a `ServiceAction` sends its request and polls it at every tick. Every call
has its own `timeout_s`; on timeout the call is cancelled and the leaf succeeds or fails according to
`on_timeout`, optionally writing a fallback value (e.g. the "nobody is talking" prompt). `on_failure:
success` keeps the interaction going when a robot is unreachable. Each service serves one action at a
time, so two sentences of the same robot never overlap.

### The ROS 1 / kinetic split

The NAOqi SDK only supports python 2.7. ROS 1 needed a whole ROS kinetic container for it; on ROS 2 the
NAO is reached through the **NAO bridge** (`ros2/nao_bridge`), a small python 2 HTTP server with no
ROS at all, called by the `nao_http` backend.

## ROS 2 layer (`ros2/`)

- `harmoni_interfaces`: the `Harmoni` action (same fields as the ROS 1 `harmoni_common_msgs`).
- `harmoni_nodes`:
  - `harmoni_service`: serves any backend as the action `/<service_id>`; publishes each answer on
    `/harmoni/<service_id>/result`;
  - `harmoni_tree`: runs a tree file, publishes `/harmoni/tree/status`, listens to `/harmoni/tree/command`;
  - `harmoni_monitor`: terminal view of a running tree;
  - `group_interaction.launch.py`: starts one service node per entry of a configuration file, plus the tree.
- `config/*.yaml`: which backend serves each service id, with its parameters, and which tree to run.

See the [ROS 2 quickstart](../quickstart/ROS2-Quickstart).
