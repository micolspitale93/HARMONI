"""HARMONI configuration files (YAML): which backend serves each service, and which tree runs::

    extends: group_interaction.yaml          # optional: start from another configuration
    participants: &participants "Sarah, Jane"
    tree:
      file: core/trees/group_interaction.json  # relative to the repository root
      period_s: 0.2
      variables: {participants: *participants}
      cast:                                     # optional override of the cast of the tree
        agents: {Mover: {robot: NAO, services: {speech: speaker_nao}}}
    services:
      bot_default: {backend: assistant, assistant_id: asst_...}

``extends`` makes experimental conditions small: a condition file contains only what differs from
the base configuration. Mappings are merged recursively, lists and values are replaced, a service
listed with ``backend`` replaces the base service entirely, and ``tree.cast`` follows the cast rules
(``agents`` as a mapping updates the agents with those roles, see :mod:`harmoni.tree.cast`).
"""

import copy
import os
from typing import Any, Dict, Optional

import yaml

MAX_DEPTH = 10


def deep_merge(base: Any, override: Any, path: str = "") -> Any:
    if path == "tree.cast":
        if base is None:  # keep it an override: it is applied to the cast of the tree at run time
            return copy.deepcopy(override)
        from harmoni.tree.cast import merge_cast  # cast rules: agents by role, humans replaced

        return merge_cast(base, override)
    if isinstance(base, dict) and isinstance(override, dict):
        result = copy.deepcopy(base)
        for key, value in override.items():
            if path == "services" and isinstance(value, dict) and "backend" in value:
                result[key] = copy.deepcopy(value)  # a new backend: do not mix parameters
            else:
                result[key] = deep_merge(result.get(key), value, f"{path}.{key}".strip("."))
        return result
    return copy.deepcopy(override)


def parse_config(text: str, path: Optional[str] = None, depth: int = 0) -> Dict[str, Any]:
    """Parse configuration text, resolving ``extends`` relative to ``path``"""
    config = yaml.safe_load(text) or {}
    if not isinstance(config, dict):
        raise ValueError(f"{path or 'configuration'}: must be a mapping")
    parent = config.pop("extends", None)
    if parent:
        if depth >= MAX_DEPTH:
            raise ValueError(f"{path}: too many nested 'extends'")
        base_dir = os.path.dirname(os.path.abspath(path)) if path else os.getcwd()
        parent_path = parent if os.path.isabs(parent) else os.path.join(base_dir, parent)
        with open(parent_path, "r", encoding="utf-8") as f:
            base = parse_config(f.read(), parent_path, depth + 1)
        base.pop("_path", None)
        config = deep_merge(base, config)
        config["_extends"] = os.path.abspath(parent_path)
    return config


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        config = parse_config(f.read(), path)
    config["_path"] = os.path.abspath(path)
    return config
