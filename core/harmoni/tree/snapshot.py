"""JSON snapshots of a running tree, for monitoring tools (dashboards, loggers).

Snapshots are produced *after* a tick by the runner and handed to observers; observers
never touch the tree, so a slow or crashed UI cannot delay the interaction.
"""

import json

import py_trees


def node_snapshot(behaviour):
    data = {
        "name": behaviour.name,
        "type": getattr(behaviour, "harmoni_type", type(behaviour).__name__),
        "status": behaviour.status.value,
        "message": behaviour.feedback_message or "",
    }
    if behaviour.children:
        data["children"] = [node_snapshot(child) for child in behaviour.children]
    return data


def _json_safe(value):
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return repr(value)


def blackboard_snapshot(prefixes=None):
    """Current blackboard values (optionally only keys starting with one of ``prefixes``)"""
    storage = py_trees.blackboard.Blackboard.storage
    return {
        key: _json_safe(value)
        for key, value in sorted(storage.items())
        if not prefixes or any(key.startswith(p) for p in prefixes)
    }
