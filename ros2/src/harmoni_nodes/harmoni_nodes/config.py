"""HARMONI ROS2 configuration files (plain YAML, no ROS parameter syntax).

Example (``ros2/config/group_interaction.yaml``)::

    participants: &participants "Sarah, Jane"
    tree:
      file: core/trees/group_interaction.json   # relative to HARMONI_ROOT
      period_s: 0.2
      variables: {session: 2session, user_names: *participants}
    services:
      bot_default:
        backend: assistant
        assistant_id: asst_...
        participants: *participants
      speaker_nao:
        backend: nao_http
        bridge_url: http://localhost:8765
        subscribe: {thread_id: /harmoni/bot_default/thread_id}   # optional side inputs

This module has no ROS dependency so that it can be tested anywhere.
"""

import os

import yaml

DEFAULT_ROOT = "/root/HARMONI"


def harmoni_root():
    return os.environ.get("HARMONI_ROOT", DEFAULT_ROOT)


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    if not isinstance(config, dict):
        raise ValueError(f"{path}: the configuration must be a mapping")
    config["_path"] = os.path.abspath(path)
    return config


def topic_for(service_id, channel):
    """Topic of a side output/input of a service, e.g. /harmoni/bot_default/thread_id"""
    return f"/harmoni/{service_id}/{channel}"


def service_config(config, service_id):
    """Return ``(backend name, backend params, {channel: topic} to subscribe)``"""
    services = config.get("services") or {}
    if service_id not in services:
        raise KeyError(f"service '{service_id}' not in {config.get('_path', 'config')} "
                       f"(available: {', '.join(services) or 'none'})")
    params = dict(services[service_id] or {})
    try:
        backend = params.pop("backend")
    except KeyError:
        raise KeyError(f"service '{service_id}' has no 'backend'") from None
    subscribe = dict(params.pop("subscribe", None) or {})
    return backend, params, subscribe


def tree_settings(config, override_file=""):
    """Return ``(tree file path, variables, period_s)``"""
    tree = dict(config.get("tree") or {})
    path = override_file or tree.get("file")
    if not path:
        raise KeyError("no tree file: set tree.file in the configuration or the 'tree' parameter")
    if not os.path.isabs(path):
        candidates = [os.path.join(harmoni_root(), path),
                      os.path.join(os.path.dirname(config.get("_path", "")), path)]
        path = next((c for c in candidates if os.path.exists(c)), candidates[0])
    return path, dict(tree.get("variables") or {}), float(tree.get("period_s", 0.2))
