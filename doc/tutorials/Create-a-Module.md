# Create a module

A module adds a new capability to HARMONI — a **sensor**, a **detector**, a **dialogue** component or an
**actuator** — without changing the core. Once created, it can be used in any service configuration
(`backend: <name>`), on ROS 2 and in simulation, and called from trees with a `ServiceAction` leaf.

## With HARMONI Studio

1. `./harmoni.sh studio`, page **Modules**, **+ New module**.
2. Describe the module:
   - **name** (`raised_hand`) and **kind**;
   - **description**, **author**, **license**;
   - **actions**: `REQUEST` to ask for a result (detectors, dialogues), `DO` to perform an action
     (actuators), `ON`/`OFF` for continuous activities;
   - **parameters** given in the configuration (e.g. a threshold, a model path, a robot IP), with type and default;
   - **python requirements** and **credentials** (names of the variables in `.env`, never the values);
   - **who can use it**: *keep it private*, or *share it with everyone*.

   The preview shows the generated `backend.py` while you type.
3. **Create module**. HARMONI generates a working module: it already answers (it echoes its input) and
   passes its tests, so you can use it in a tree right away and replace the logic afterwards.
4. **Code** tab: write the logic in the `TODO` parts and *Save & reload*.
5. **Tests** tab: *Run the tests*.
6. **Use** tab: add it to a services configuration and call it from a tree.

## Private or public

| | Where | Who sees it |
|---|---|---|
| Private | `modules/private/<name>` (ignored by git) | only this machine |
| Public | `modules/public/<name>` (committed) | everyone, after a pull request |
| External | any folder in `HARMONI_MODULE_PATH` | e.g. a team repository |

A module becomes public (*Share with everyone…*) only when its checks pass:

- it loads without errors and its tests pass;
- the manifest has a description, an author and a license, and the README has no `TODO` left;
- no credentials are written in its files (API keys, tokens, private keys): they must come from `.env`.

Then commit `modules/public/<name>` and open a pull request. *Make private* moves it back.

## What is generated

```
modules/private/raised_hand/
├── harmoni_module.yaml      manifest: kind, actions, parameters, requirements, credentials, visibility
├── backend.py               the service backend: the only file to edit
├── tests/test_raised_hand.py
├── example_config.yaml      services configuration using the module
├── example_tree.json        minimal tree calling the module
├── requirements.txt
└── README.md
```

```python
@register_backend("raised_hand", kind="detector", actions=["REQUEST"],
                  params={"threshold": Param(float, default=0.5, doc="detection threshold")},
                  credentials=["HAND_API_KEY"])
class RaisedHandBackend(ServiceBackend):
    def setup(self):
        load_env()
        self.hand_api_key = os.getenv("HAND_API_KEY")
        # TODO: load the model

    def request(self, data):
        # TODO: run the model on the input and return the detection
        return Result(True, json.dumps({"service": self.service_id, "input": data}))
```

## Without Studio

```python
from harmoni.modules.generator import create_module
create_module({"name": "raised_hand", "kind": "detector", "description": "Detects a raised hand",
               "author": "Me", "params": [{"name": "threshold", "type": "float", "default": 0.5}]})
```

```bash
cd modules/private/raised_hand
python3 -m pytest tests
PYTHONPATH=../../../core python3 -m harmoni.tree simulate example_tree.json --services example_config.yaml
```

On ROS 2, install the requirements of the modules in the container with `./harmoni.sh ros2 modules-install`,
then use the module in a configuration of `ros2/config`: the generic `harmoni_service` node serves it.
