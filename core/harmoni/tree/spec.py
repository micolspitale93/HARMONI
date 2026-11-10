"""HARMONI tree file format: loading, variable substitution and validation.

A tree file is JSON (or YAML) independent of ROS::

    {
      "harmoni_tree": 1,
      "name": "GroupInteraction",
      "description": "...",
      "variables": {"session": "1session", "llm_timeout_s": 60},
      "stop_when": "scene/finished",
      "root": {
        "type": "Sequence", "name": "Main",
        "children": [
          {"type": "ServiceAction", "name": "Ask LLM",
           "params": {"service": "bot_default", "input_key": "scene/utterance",
                      "output_key": "bot/raw", "timeout_s": "${llm_timeout_s}"}}
        ]
      }
    }

- ``variables`` can be overridden when the tree is loaded (e.g. from a config file); a
  parameter equal to ``"${name}"`` takes the value *and type* of the variable, while
  ``"Hello ${name}"`` is string interpolation.
- ``stop_when`` (optional) is a blackboard key: the runner stops when its value is true.
- ``blackboard`` (optional) gives initial blackboard values.
- ``cast`` (optional) lists the humans and the agents (robots) of the interaction, with the services
  of each agent per channel (see :mod:`harmoni.tree.cast`). It can be overridden at run time.
"""

import copy
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from harmoni.tree.cast import Cast, merge_cast, validate_cast
from harmoni.tree.registry import NodeType, get_node_type, node_types, normalize_key

FORMAT_VERSION = 1
_VAR_FULL = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_VAR_INLINE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass
class Issue:
    level: str  # "error" or "warning"
    path: str
    message: str

    def __str__(self):
        return f"{self.level.upper()} {self.path}: {self.message}"


class TreeSpecError(ValueError):
    """Raised when a tree file has errors"""

    def __init__(self, issues: List[Issue]):
        self.issues = issues
        errors = [str(i) for i in issues if i.level == "error"]
        super().__init__("Invalid HARMONI tree:\n  " + "\n  ".join(errors))


def load_spec(source) -> Dict[str, Any]:
    """Load a tree from a path (.json, .yaml, .yml) or return a copy of a dict.

    The directory of the file is stored in ``spec["_base_dir"]`` so that leaves can resolve
    relative paths (e.g. the dialogue script of the group interaction).
    """
    if isinstance(source, dict):
        spec = copy.deepcopy(source)
        spec.setdefault("_base_dir", os.getcwd())
        return spec
    path = os.path.abspath(str(source))
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith((".yaml", ".yml")):
            import yaml

            spec = yaml.safe_load(f)
        else:
            spec = json.load(f)
    if not isinstance(spec, dict):
        raise TreeSpecError([Issue("error", path, "a tree file must contain an object")])
    spec["_base_dir"] = os.path.dirname(path)
    spec["_source"] = path
    return spec


def _substitute(value, variables, path, issues):
    if isinstance(value, str):
        full = _VAR_FULL.match(value)
        if full:
            name = full.group(1)
            if name not in variables:
                issues.append(Issue("error", path, f"undefined variable '${{{name}}}'"))
                return None
            return copy.deepcopy(variables[name])

        def repl(match):
            name = match.group(1)
            if name not in variables:
                issues.append(Issue("error", path, f"undefined variable '${{{name}}}'"))
                return match.group(0)
            return str(variables[name])

        return _VAR_INLINE.sub(repl, value)
    if isinstance(value, list):
        return [_substitute(v, variables, f"{path}[{i}]", issues) for i, v in enumerate(value)]
    if isinstance(value, dict):
        return {k: _substitute(v, variables, f"{path}.{k}", issues) for k, v in value.items()}
    return value


def resolve_spec(spec, overrides: Optional[Dict[str, Any]] = None, cast: Optional[dict] = None):
    """Return ``(resolved_spec, issues)`` with every ``${variable}`` substituted.

    ``cast`` is an optional override of the cast of the tree (see :func:`harmoni.tree.cast.merge_cast`).
    """
    issues: List[Issue] = []
    resolved = copy.deepcopy(spec)
    variables = dict(spec.get("variables") or {})
    for name in overrides or {}:
        if name not in variables:
            issues.append(Issue("warning", "variables", f"override of unknown variable '{name}'"))
    variables.update(overrides or {})
    resolved["variables"] = variables

    def walk(node, path):
        if not isinstance(node, dict):
            return
        if "params" in node:
            node["params"] = _substitute(node["params"], variables, f"{path}.params", issues)
        if "name" in node:
            node["name"] = _substitute(node["name"], variables, f"{path}.name", issues)
        for i, child in enumerate(node.get("children") or []):
            walk(child, f"{path}.children[{i}]")

    walk(resolved.get("root"), "root")
    if "cast" in resolved or cast:
        resolved["cast"] = _substitute(merge_cast(resolved.get("cast"), cast), variables, "cast", issues)
    return resolved, issues


def _type_ok(value, expected):
    types = expected if isinstance(expected, tuple) else (expected,)
    if value is None:
        return True
    for t in types:
        if t is Any:
            return True
        if t is float and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if t is int and isinstance(value, bool):
            continue
        if isinstance(value, t):
            return True
    return False


def iter_nodes(spec):
    """Yield ``(path, node)`` for every node of a (resolved) spec, depth first"""

    def walk(node, path):
        yield path, node
        for i, child in enumerate(node.get("children") or []):
            if isinstance(child, dict):
                yield from walk(child, f"{path}.children[{i}]")

    root = spec.get("root")
    if isinstance(root, dict):
        yield from walk(root, "root")


def validate(spec, resolved: bool = False) -> List[Issue]:
    """Check a tree. Returns a list of issues (errors make the tree unusable).

    Args:
        spec: tree dict (as returned by :func:`load_spec`)
        resolved: True if the variables have already been substituted
    """
    issues: List[Issue] = []
    if not resolved:
        spec, issues = resolve_spec(spec)

    version = spec.get("harmoni_tree", FORMAT_VERSION)
    if version != FORMAT_VERSION:
        issues.append(Issue("error", "harmoni_tree", f"unsupported format version {version} (expected {FORMAT_VERSION})"))
    if not isinstance(spec.get("root"), dict):
        issues.append(Issue("error", "root", "missing root node"))
        return issues

    for level, path, message in validate_cast(spec.get("cast")):
        issues.append(Issue(level, path, message))

    types = node_types()
    # the runner writes the cast and the conversation log on the blackboard
    written = {normalize_key(k) for k in (spec.get("blackboard") or {})}
    written.update({"/cast/humans", "/cast/agents", "/cast/roles", "/conversation"})
    reads = []
    names = {}
    for path, node in iter_nodes(spec):
        type_name = node.get("type")
        if type_name not in types:
            issues.append(Issue("error", path, f"unknown node type '{type_name}'"))
            continue
        node_type: NodeType = types[type_name]
        name = node.get("name")
        if not name:
            issues.append(Issue("warning", path, f"node without name, '{type_name}' will be used"))
        else:
            names.setdefault(name, []).append(path)
        children = node.get("children") or []
        if node_type.kind == "composite" and not children:
            issues.append(Issue("error", path, f"composite '{type_name}' needs at least one child"))
        if node_type.kind == "leaf" and children:
            issues.append(Issue("error", path, f"leaf '{type_name}' cannot have children"))

        params = node.get("params") or {}
        if not isinstance(params, dict):
            issues.append(Issue("error", path, "params must be an object"))
            continue
        for key in params:
            if key not in node_type.params:
                issues.append(Issue("error", f"{path}.params.{key}", f"unknown parameter for '{type_name}'"))
        for key, decl in node_type.params.items():
            value = params.get(key)
            if decl.required and value is None:
                issues.append(Issue("error", f"{path}.params.{key}", "required parameter is missing"))
            elif not _type_ok(value, decl.type):
                issues.append(Issue("error", f"{path}.params.{key}",
                                    f"expected {decl.to_dict()['type']}, got {type(value).__name__}"))
            elif decl.choices and value is not None and value not in decl.choices:
                issues.append(Issue("error", f"{path}.params.{key}", f"must be one of {decl.choices}"))
        effective = {k: (params[k] if k in params else d.default) for k, d in node_type.params.items()}
        written.update(node_type.writes_for(effective))
        reads.extend((path, key) for key in node_type.reads_for(effective))

    for path, key in reads:
        if key not in written:
            issues.append(Issue("warning", path, f"reads '{key}' but no node writes it"))
    for name, paths in names.items():
        if len(paths) > 1:
            issues.append(Issue("warning", paths[1], f"duplicate node name '{name}'"))
    stop_when = spec.get("stop_when")
    if stop_when and normalize_key(stop_when) not in written:
        issues.append(Issue("warning", "stop_when", f"'{stop_when}' is never written by the tree"))
    return issues


def services_used(spec, cast: Optional[dict] = None) -> List[str]:
    """Service ids called by the tree and by its cast (to know which services must be running)"""
    resolved, _ = resolve_spec(spec, cast=cast)
    services = []
    if isinstance(resolved.get("cast"), dict):
        services.extend(Cast.from_spec(resolved["cast"]).services())
    for _, node in iter_nodes(resolved):
        service = (node.get("params") or {}).get("service")
        if node.get("type") == "ServiceAction" and service and service not in services:
            services.append(service)
    return services


def has_errors(issues):
    return any(i.level == "error" for i in issues)
