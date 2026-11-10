"""Registry of the node types that can be used in a HARMONI tree file.

Every leaf declares its parameters and the blackboard keys it reads and writes. This
metadata is what makes a tree file checkable before it runs (see :mod:`harmoni.tree.spec`)
and is what an authoring tool shows in its palette (``python -m harmoni.tree describe``).

Example::

    @register_leaf(
        "CheckValue",
        params={"key": Param(str, required=True, doc="blackboard key")},
        reads=["{key}"],
        doc="SUCCESS if the blackboard value equals `equals`",
    )
    class CheckValue(py_trees.behaviour.Behaviour):
        def __init__(self, name, context, key, equals=None): ...

``reads``/``writes`` may reference parameters with ``{param}``; the value is substituted
when a tree is validated.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

_MISSING = object()


@dataclass
class Param:
    """Declaration of a node parameter"""

    type: Any = str
    required: bool = False
    default: Any = None
    doc: str = ""
    choices: Optional[List[Any]] = None

    def to_dict(self):
        types = self.type if isinstance(self.type, tuple) else (self.type,)
        return {
            "type": "|".join(getattr(t, "__name__", str(t)) for t in types),
            "required": self.required,
            "default": self.default,
            "doc": self.doc,
            "choices": self.choices,
        }


@dataclass
class NodeType:
    """A node type usable in tree files"""

    name: str
    factory: Callable
    kind: str  # "leaf" or "composite"
    params: Dict[str, Param] = field(default_factory=dict)
    reads: List[str] = field(default_factory=list)
    writes: List[str] = field(default_factory=list)
    doc: str = ""
    category: str = "general"

    def resolve_keys(self, keys, params):
        """Substitute ``{param}`` placeholders in the declared blackboard keys"""
        resolved = []
        for key in keys:
            try:
                value = key.format(**{k: v for k, v in params.items() if v is not None})
            except (KeyError, IndexError):
                continue  # placeholder for a parameter that is not set
            if value:
                resolved.append(normalize_key(value))
        return resolved

    def reads_for(self, params):
        return self.resolve_keys(self.reads, params)

    def writes_for(self, params):
        return self.resolve_keys(self.writes, params)

    def to_dict(self):
        return {
            "type": self.name,
            "kind": self.kind,
            "category": self.category,
            "doc": self.doc,
            "params": {name: p.to_dict() for name, p in self.params.items()},
            "reads": list(self.reads),
            "writes": list(self.writes),
        }


_REGISTRY: Dict[str, NodeType] = {}


def normalize_key(key):
    """Blackboard keys are absolute: ``scene/utterance`` -> ``/scene/utterance``"""
    key = str(key).strip()
    return key if key.startswith("/") else "/" + key


def register_node(node_type: NodeType):
    if node_type.name in _REGISTRY and _REGISTRY[node_type.name].factory is not node_type.factory:
        raise ValueError(f"Node type '{node_type.name}' is already registered")
    _REGISTRY[node_type.name] = node_type
    return node_type


def register_leaf(name, params=None, reads=(), writes=(), doc="", category="general"):
    """Class decorator registering a py_trees behaviour as a tree leaf.

    The class is instantiated as ``cls(name=<node name>, context=<BuildContext>, **params)``.
    """

    def decorator(cls):
        register_node(
            NodeType(
                name=name,
                factory=cls,
                kind="leaf",
                params=dict(params or {}),
                reads=list(reads),
                writes=list(writes),
                doc=doc or (cls.__doc__ or "").strip().split("\n")[0],
                category=category,
            )
        )
        cls.harmoni_type = name
        return cls

    return decorator


def get_node_type(name) -> NodeType:
    _ensure_builtin_nodes()
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"Unknown node type '{name}'. Known types: {', '.join(sorted(_REGISTRY))}") from None


def node_types() -> Dict[str, NodeType]:
    _ensure_builtin_nodes()
    return dict(_REGISTRY)


def describe():
    """Palette description of every node type, JSON serializable (for authoring tools)"""
    return [t.to_dict() for t in sorted(node_types().values(), key=lambda t: (t.kind, t.category, t.name))]


def _ensure_builtin_nodes():
    # importing the modules registers the built-in composites and leaves
    from harmoni.tree import composites  # noqa: F401
    import harmoni.leaves  # noqa: F401
