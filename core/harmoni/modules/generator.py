"""Generate a new HARMONI module (sensor, detector, dialogue or actuator) from a short description::

    from harmoni.modules.generator import create_module
    create_module({
        "name": "raised_hand",
        "kind": "detector",
        "description": "Detects a raised hand in the camera image",
        "actions": ["REQUEST"],
        "params": [{"name": "threshold", "type": "float", "default": 0.5, "doc": "detection threshold"}],
        "requirements": ["mediapipe"],
        "credentials": [],
        "visibility": "private",
    })

The generated module works out of the box (it echoes its input) and passes its own tests; the
developer then replaces the TODO parts with the real logic. Files::

    modules/<visibility>/<name>/
    ├── harmoni_module.yaml      manifest (what the module is, needs and offers)
    ├── backend.py               the service backend (the only file to edit)
    ├── tests/test_<name>.py     unit tests, including the module inside a tree
    ├── example_config.yaml      service configuration (ROS 2 and simulation)
    ├── example_tree.json        minimal tree calling the module
    ├── requirements.txt
    └── README.md
"""

import datetime
import json
import keyword
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

from harmoni.modules import MANIFEST, VISIBILITIES, forget, modules_dir

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
PIP_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-\[\],<>=!~ ]{0,99}$")
KINDS = ("sensor", "detector", "dialogue", "actuator")
ACTIONS = ("REQUEST", "DO", "ON", "OFF")
TYPES = {"str": str, "int": int, "float": float, "bool": bool, "list": list}

KIND_HINTS = {
    "sensor": ("read the device (e.g. open the camera / microphone)", "read one sample from the device"),
    "detector": ("load the model", "run the model on the input (e.g. a frame or an utterance) and return the detection"),
    "dialogue": ("connect to the dialogue service / load the model", "compute the answer to the user input"),
    "actuator": ("connect to the robot or device", "execute the command (say, move, show, ...)"),
}


class ModuleSpecError(ValueError):
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _camel(name):
    return "".join(part.capitalize() for part in name.split("_"))


def normalize_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a module description and fill in the defaults. Raises ModuleSpecError."""
    from harmoni.services.base import _BACKENDS

    errors = []
    s = {
        "name": str(spec.get("name", "")).strip(),
        "kind": spec.get("kind", "detector"),
        "description": str(spec.get("description", "")).strip(),
        "author": str(spec.get("author", "")).strip(),
        "license": str(spec.get("license", "MIT")).strip() or "MIT",
        "visibility": spec.get("visibility", "private"),
        "actions": list(spec.get("actions") or []),
        "params": list(spec.get("params") or []),
        "requirements": [str(r).strip() for r in spec.get("requirements") or [] if str(r).strip()],
        "credentials": [str(c).strip() for c in spec.get("credentials") or [] if str(c).strip()],
    }
    if not NAME_RE.match(s["name"]) or keyword.iskeyword(s["name"]):
        errors.append("name: 2-40 characters, lowercase letters, digits and _, starting with a letter")
    elif s["name"] in _BACKENDS:
        errors.append(f"name: a backend called '{s['name']}' already exists")
    if s["kind"] not in KINDS:
        errors.append(f"kind: one of {', '.join(KINDS)}")
    if s["visibility"] not in VISIBILITIES:
        errors.append(f"visibility: one of {', '.join(VISIBILITIES)}")
    if not s["description"]:
        errors.append("description: required")
    if not s["actions"]:
        s["actions"] = ["DO"] if s["kind"] == "actuator" else ["REQUEST"]
    bad = [a for a in s["actions"] if a not in ACTIONS]
    if bad:
        errors.append(f"actions: unknown {bad}, use {', '.join(ACTIONS)}")
    params, seen = [], set()
    for i, p in enumerate(s["params"]):
        pname = str(p.get("name", "")).strip()
        ptype = p.get("type", "str")
        if not re.match(r"^[a-z][a-z0-9_]{0,39}$", pname) or keyword.iskeyword(pname):
            errors.append(f"params[{i}].name: lowercase identifier required")
            continue
        if pname in seen or pname in ("service_id", "params", "emit"):
            errors.append(f"params[{i}].name: '{pname}' is duplicated or reserved")
            continue
        seen.add(pname)
        if ptype not in TYPES:
            errors.append(f"params[{i}].type: one of {', '.join(TYPES)}")
            continue
        default = p.get("default")
        if default in ("", None):
            default = None
        else:
            try:
                default = _coerce(default, ptype)
            except (TypeError, ValueError):
                errors.append(f"params[{i}].default: not a valid {ptype}")
                continue
        params.append({"name": pname, "type": ptype, "default": default, "doc": str(p.get("doc", "")),
                       "required": bool(p.get("required", False))})
    s["params"] = params
    for c in s["credentials"]:
        if not ENV_RE.match(c):
            errors.append(f"credentials: '{c}' must be an environment variable name (e.g. MY_API_KEY)")
    for r in s["requirements"]:
        if not PIP_RE.match(r):
            errors.append(f"requirements: '{r}' is not a valid pip requirement")
    if errors:
        raise ModuleSpecError(errors)
    return s


def _coerce(value, ptype):
    if ptype == "bool":
        if isinstance(value, bool):
            return value
        if str(value).lower() in ("true", "1", "yes"):
            return True
        if str(value).lower() in ("false", "0", "no"):
            return False
        raise ValueError(value)
    if ptype == "list":
        if isinstance(value, list):
            return value
        value = json.loads(value) if str(value).strip().startswith("[") else [v.strip() for v in str(value).split(",")]
        return value
    return TYPES[ptype](value)


# ---------------------------------------------------------------------------- templates
def render_backend(s) -> str:
    cls = _camel(s["name"]) + "Backend"
    setup_hint, action_hint = KIND_HINTS[s["kind"]]
    params = "\n".join(
        f'        "{p["name"]}": Param({p["type"]}, required={p["required"]}, default={p["default"]!r}, doc={p["doc"]!r}),'
        for p in s["params"])
    attrs = "\n".join(f'        self.{p["name"]} = self.params.get("{p["name"]}", {p["default"]!r})' for p in s["params"])
    creds = "\n".join(f'        self.{c.lower()} = os.getenv("{c}")' for c in s["credentials"])
    methods = []
    if "REQUEST" in s["actions"]:
        methods.append(f'''
    def request(self, data):
        """REQUEST: {action_hint}.

        Args:
            data (str): payload sent by the tree (text or JSON)
        Returns:
            Result: ok and the answer written to the blackboard by the ServiceAction leaf
        """
        # TODO: {action_hint}
        answer = {{"service": self.service_id, "input": data}}
        return Result(True, json.dumps(answer))
''')
    if "DO" in s["actions"]:
        methods.append(f'''
    def do(self, data):
        """DO: {action_hint}.

        Args:
            data (str): command sent by the tree (text or JSON)
        """
        # TODO: {action_hint}
        self.log.info("%s DO %s", self.service_id, data)
        return Result(True, "done")
''')
    if "ON" in s["actions"]:
        methods.append('''
    def start(self, data=""):
        """ON: start a long running activity (e.g. streaming)"""
        # TODO: start
        self.running = True
        return Result(True, "started")
''')
    if "OFF" in s["actions"]:
        methods.append('''
    def stop(self):
        """OFF: stop the long running activity"""
        # TODO: stop
        self.running = False
        return Result(True, "stopped")
''')
    actions = ", ".join(f'"{a}"' for a in s["actions"])
    params_block = "{\n" + params + "\n    }" if params else "{}"
    return f'''"""{s["description"]}

HARMONI {s["kind"]} module "{s["name"]}", generated on {datetime.date.today().isoformat()}.
Edit the TODO parts; keep the class registered with @register_backend so that HARMONI finds it.
Credentials are read from the environment (.env), never written in the code.
"""

import json
import os
import threading

from harmoni.services import Result, ServiceBackend, register_backend
from harmoni.services.base import load_env
from harmoni.tree.registry import Param


@register_backend(
    "{s["name"]}",
    kind="{s["kind"]}",
    actions=[{actions}],
    doc={s["description"]!r},
    params={params_block},
    requirements={s["requirements"]!r},
    credentials={s["credentials"]!r},
)
class {cls}(ServiceBackend):
    """{s["description"]}"""

    def __init__(self, service_id, params=None, emit=None):
        super().__init__(service_id, params, emit)
{attrs or "        pass"}
        self.running = False
        self._cancelled = threading.Event()

    def setup(self):
        """Called once before the first action: {setup_hint}"""
        load_env()
{creds or "        pass"}
        # TODO: {setup_hint}
{"".join(methods)}
    def cancel(self):
        """Called when the tree stops waiting (timeout, stop): interrupt the current action"""
        self._cancelled.set()
'''


def render_tests(s) -> str:
    cls = _camel(s["name"]) + "Backend"
    defaults = {p["name"]: p["default"] for p in s["params"] if p["default"] is not None}
    action = s["actions"][0]
    unsupported = next((a for a in ("REQUEST", "DO") if a not in s["actions"]), None)
    unsupported_test = f'''

def test_unsupported_action_fails():
    assert not make().handle(ActionType.{unsupported}, "").ok
''' if unsupported else ""
    return f'''"""Tests of the HARMONI module "{s["name"]}" (run: python3 -m pytest {{this folder}})"""

import importlib.util
import json
import sys
import time
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
for parent in MODULE_DIR.parents:  # make the HARMONI core importable
    if (parent / "core" / "harmoni").is_dir():
        sys.path.insert(0, str(parent / "core"))
        break

from harmoni.constants import ActionType  # noqa: E402
from harmoni.services import base  # noqa: E402
from harmoni.tree import BuildContext, ClientRegistry, LocalServiceClient, TreeRunner  # noqa: E402

if "{s["name"]}" not in base._BACKENDS:
    _spec = importlib.util.spec_from_file_location("harmoni_modules.{s["name"]}", MODULE_DIR / "backend.py")
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
{cls} = base._BACKENDS["{s["name"]}"]

DEFAULTS = {defaults!r}


def make():
    backend = {cls}("{s["name"]}_default", dict(DEFAULTS))
    backend.setup()
    return backend


def test_registered_with_metadata():
    info = {cls}.backend_info
    assert info["kind"] == "{s["kind"]}"
    assert info["actions"] == {s["actions"]!r}


def test_{action.lower()}():
    result = make().handle(ActionType.{action}, json.dumps({{"example": "input"}}))
    assert result.ok, result.message
{unsupported_test}

def test_in_a_tree():
    """The module called by a ServiceAction leaf, as in a real interaction"""
    tree = json.loads((MODULE_DIR / "example_tree.json").read_text())
    clients = ClientRegistry({{"{s["name"]}_default": LocalServiceClient(make())}})
    runner = TreeRunner(tree, BuildContext(client_for=clients))
    for _ in range(500):
        snapshot = runner.step()
        if snapshot["root"]["status"] != "RUNNING":
            break
        time.sleep(0.005)
    clients.shutdown()
    assert snapshot["root"]["status"] == "SUCCESS", snapshot
'''


def render_example_tree(s) -> dict:
    service = f"{s['name']}_default"
    children = []
    for action in [a for a in s["actions"] if a in ("REQUEST", "DO")]:
        node = {"type": "ServiceAction", "name": f"{s['name']} {action}",
                "params": {"service": service, "action": action, "input_value": "hello", "timeout_s": 30}}
        if action == "REQUEST":
            node["params"]["output_key"] = f"{s['name']}/result"
        children.append(node)
    if not children:
        children.append({"type": "ServiceAction", "name": f"{s['name']} ON",
                         "params": {"service": service, "action": "ON", "timeout_s": 30}})
    return {"harmoni_tree": 1, "name": f"{_camel(s['name'])}Example",
            "description": f"Minimal tree calling the {s['name']} module",
            "root": {"type": "Sequence", "name": "Example", "children": children}}


def render_example_config(s) -> str:
    entry = {"backend": s["name"]}
    entry.update({p["name"]: p["default"] for p in s["params"] if p["default"] is not None})
    config = {"tree": {"file": f"modules/{s['visibility']}/{s['name']}/example_tree.json"},
              "services": {f"{s['name']}_default": entry}}
    return ("# Service configuration using the module (ROS 2: ./harmoni.sh ros2 run <this file>;\n"
            "# simulation: python -m harmoni.tree simulate example_tree.json --services example_config.yaml)\n"
            + yaml.safe_dump(config, sort_keys=False))


def render_readme(s) -> str:
    rows = "\n".join(f"| `{p['name']}` | {p['type']} | {'yes' if p['required'] else 'no'} | `{p['default']!r}` | {p['doc']} |"
                     for p in s["params"]) or "| | | | | |"
    creds = ", ".join(f"`{c}`" for c in s["credentials"]) or "none"
    reqs = ", ".join(f"`{r}`" for r in s["requirements"]) or "none"
    return f"""# {s['name']}

{s['description']}

- Kind: {s['kind']}
- Actions: {', '.join(s['actions'])}
- Author: {s['author'] or 'TODO'}
- License: {s['license']}
- Python requirements: {reqs} (`pip install -r requirements.txt`)
- Credentials (in the `.env` of the repository root): {creds}

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
{rows}

## Use it

In a service configuration (ROS 2 `ros2/config/*.yaml`, or `--services` of the simulator):

```yaml
services:
  {s['name']}_default:
    backend: {s['name']}
```

In a tree, call it with a `ServiceAction` leaf (`service: {s['name']}_default`), see `example_tree.json`.

```bash
python3 -m pytest tests                       # unit tests
PYTHONPATH=../../../core python3 -m harmoni.tree simulate example_tree.json --services example_config.yaml
```
"""


def create_module(spec: Dict[str, Any], overwrite: bool = False) -> Path:
    """Create the files of a new module and return its folder"""
    s = normalize_spec(spec)
    folder = modules_dir(s["visibility"]) / s["name"]
    other = modules_dir("public" if s["visibility"] == "private" else "private") / s["name"]
    if (folder.exists() or other.exists()) and not overwrite:
        raise ModuleSpecError([f"name: a module called '{s['name']}' already exists"])
    (folder / "tests").mkdir(parents=True, exist_ok=True)
    manifest = {
        "harmoni_module": 1,
        "name": s["name"],
        "version": "0.1.0",
        "kind": s["kind"],
        "description": s["description"],
        "author": s["author"],
        "license": s["license"],
        "visibility": s["visibility"],
        "backend": "backend.py",
        "actions": s["actions"],
        "params": {p["name"]: {k: p[k] for k in ("type", "default", "doc", "required")} for p in s["params"]},
        "requirements": s["requirements"],
        "credentials": s["credentials"],
        "created": datetime.date.today().isoformat(),
    }
    (folder / MANIFEST).write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    (folder / "backend.py").write_text(render_backend(s), encoding="utf-8")
    (folder / "tests" / f"test_{s['name']}.py").write_text(render_tests(s), encoding="utf-8")
    (folder / "example_tree.json").write_text(json.dumps(render_example_tree(s), indent=2) + "\n", encoding="utf-8")
    (folder / "example_config.yaml").write_text(render_example_config(s), encoding="utf-8")
    (folder / "requirements.txt").write_text("".join(r + "\n" for r in s["requirements"]), encoding="utf-8")
    (folder / "README.md").write_text(render_readme(s), encoding="utf-8")
    forget(s["name"])
    return folder
