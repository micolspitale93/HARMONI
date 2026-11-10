# HARMONI Studio: compose interactions in the browser

HARMONI Studio is a web dashboard to author human-robot interactions from HARMONI modules,
run them, and create new modules. It edits the same files you would edit by hand
(tree files, scripts, service configurations, modules), so everything it produces can be
versioned with git and run with or without Studio.

```bash
./harmoni.sh studio            # on your computer: compose, simulate, create modules
./harmoni.sh ros2 studio       # in the ROS 2 container: also monitors trees running on ROS 2
```

Then open [http://localhost:8800](http://localhost:8800). Studio listens on `localhost` only, because it can
write files of the repository.

## Pages

### Compose

Build the behavior tree of an interaction.

- **Nodes** (left): every node type HARMONI knows, by category. Click one to add it to the selected
  container, or drag it into the tree. Composites (`Sequence`, `Selector`, `Parallel`) contain other nodes;
  `ServiceAction` calls any HARMONI service (sensor, detector, dialogue, actuator) by its service id.
- **Tree** (center): *Outline* to edit (drag rows to move them: on the top/bottom half of a row to put the node
  before/after it, in the middle of a container to put it inside), *Diagram* to see the whole tree.
- **Properties** (right): the parameters of the selected node, generated from the node description:
  required parameters are marked `*`, choices are drop-downs, `service` suggests the configured services,
  `*_key` parameters suggest the blackboard keys used in the tree. Any parameter can be a tree variable,
  e.g. `${llm_timeout_s}`. With nothing selected, the panel shows the tree settings: name, description,
  variables, initial blackboard and the stop condition.
- **Problems** (bottom): the tree is validated while you edit (unknown parameters, wrong types, missing
  required parameters, blackboard keys read but never written). Click a problem to select the node.

Shortcuts: `Ctrl+S` save, `Delete` remove the node, `Ctrl+D` duplicate, `Alt+↑/↓` move.

### Scripts

Edit scripted dialogues (used by the `GroupScript` leaf): one list of scenes per session; each scene is
said by a robot as written (*Script*), or decided by the LLM orchestrator (*LLM*). `$USERNAME1`,
`$USERNAME2`… are replaced by the participants' names.

### Services

Service configurations say which backend (module) serves each service id used by the trees, with its
parameters. `ros2/config/*.yaml` are used by ROS 2, `core/trees/*.yaml` by simulations. The YAML is edited
as text (comments and anchors are kept) and checked while you type: unknown backends or parameters,
missing required parameters, services called by the tree but not configured. *Add a service* builds the
YAML of a new service from a form generated from the backend description.

### Run

- **Simulation**: runs a tree inside Studio with the backends of a configuration. With the `mock`
  configurations no robot, microphone or API key is needed. Variables can be changed for the run.
- **ROS 2 live** (when Studio runs in the ROS 2 container): follows the tree started with
  `./harmoni.sh ros2 run …`.

The page shows the tree with the live status of every node, the conversation, the blackboard and the
activity of the services; *Pause*, *Resume*, *Reload* (re-read the tree file after an edit) and *Stop* are
sent to the runner, which applies them between two ticks. Studio is never in the control loop:
closing the browser does not affect the interaction.

### Modules

Create new HARMONI modules, test them and decide who can use them, see [Create a module](Create-a-Module).
