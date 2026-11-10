"""Build a py_trees tree from a HARMONI tree file."""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

import py_trees

from harmoni.tree.cast import Cast
from harmoni.tree.registry import get_node_type, normalize_key
from harmoni.tree.spec import TreeSpecError, has_errors, load_spec, resolve_spec, validate


@dataclass
class BuildContext:
    """What leaves can use from their environment.

    Attributes:
        client_for: callable returning the :class:`harmoni.tree.clients.ServiceClient` of a service id
        base_dir: directory used to resolve relative paths of the tree file (scripts, ...)
        clock: monotonic clock in seconds (injectable for tests of timeouts)
        logger: logger used by the leaves
        cast: the humans and agents of the interaction (set from the tree file when it is built)
    """

    client_for: Optional[Callable[[str], Any]] = None
    base_dir: Optional[str] = None
    clock: Callable[[], float] = time.monotonic
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("harmoni.tree"))
    cast: Cast = field(default_factory=Cast)

    def resolve_path(self, path):
        return path if os.path.isabs(path) else os.path.normpath(os.path.join(self.base_dir or os.getcwd(), path))


def build_node(node: Dict[str, Any], context: BuildContext):
    node_type = get_node_type(node["type"])
    name = node.get("name") or node["type"]
    params = {k: v for k, v in (node.get("params") or {}).items()}
    for key, decl in node_type.params.items():
        if key not in params and decl.default is not None:
            params[key] = decl.default
    if node_type.kind == "composite":
        children = [build_node(child, context) for child in node.get("children") or []]
        behaviour = node_type.factory(name=name, children=children, **params)
    else:
        behaviour = node_type.factory(name=name, context=context, **params)
    behaviour.harmoni_type = node_type.name
    return behaviour


def build_tree(source, context: Optional[BuildContext] = None, variables: Optional[Dict[str, Any]] = None,
               cast: Optional[dict] = None):
    """Validate a tree file and build its py_trees root.

    Args:
        source: path of a tree file or a tree dict
        context: :class:`BuildContext` (base_dir defaults to the folder of the tree file)
        variables: overrides of the tree variables
        cast: override of the cast (humans, agents) of the tree

    Returns:
        tuple: (py_trees root behaviour, resolved spec, list of warnings)

    Raises:
        TreeSpecError: if the tree has errors
    """
    spec = load_spec(source)
    resolved, issues = resolve_spec(spec, variables, cast)
    issues += validate(resolved, resolved=True)
    if has_errors(issues):
        raise TreeSpecError(issues)
    context = context or BuildContext()
    if context.base_dir is None:
        context.base_dir = spec.get("_base_dir")
    context.cast = Cast.from_spec(resolved.get("cast"))
    # initial blackboard values: the cast, an empty conversation log, the values of the tree file
    initial = {
        "cast/humans": list(context.cast.humans),
        "cast/agents": [a.to_dict() for a in context.cast.agents],
        "cast/roles": context.cast.roles,
        "conversation": [],
    }
    initial.update(resolved.get("blackboard") or {})
    writer = py_trees.blackboard.Client(name="harmoni_initial_values")
    for key, value in initial.items():
        key = normalize_key(key)
        writer.register_key(key=key, access=py_trees.common.Access.WRITE)
        writer.set(key, value)
    root = build_node(resolved["root"], context)
    return root, resolved, [i for i in issues if i.level == "warning"]
