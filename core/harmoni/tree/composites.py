"""Composite node types available in tree files (thin wrappers around py_trees)."""

import py_trees

from harmoni.tree.registry import NodeType, Param, register_node


def _sequence(name, children, memory=True, **_):
    node = py_trees.composites.Sequence(name=name, memory=bool(memory))
    node.add_children(children)
    return node


def _selector(name, children, memory=True, **_):
    node = py_trees.composites.Selector(name=name, memory=bool(memory))
    node.add_children(children)
    return node


def _parallel(name, children, policy="all", synchronise=True, **_):
    if policy == "all":
        policy_obj = py_trees.common.ParallelPolicy.SuccessOnAll(synchronise=bool(synchronise))
    elif policy == "one":
        policy_obj = py_trees.common.ParallelPolicy.SuccessOnOne()
    else:
        raise ValueError(f"Unknown parallel policy '{policy}' (use 'all' or 'one')")
    node = py_trees.composites.Parallel(name=name, policy=policy_obj)
    node.add_children(children)
    return node


_MEMORY = Param(bool, default=True, doc="resume from the running child at the next tick")

register_node(NodeType("Sequence", _sequence, "composite", {"memory": _MEMORY},
                       doc="Runs the children in order, fails as soon as one fails", category="composite"))
register_node(NodeType("Selector", _selector, "composite", {"memory": _MEMORY},
                       doc="Tries the children in order until one succeeds (fallback)", category="composite"))
register_node(NodeType(
    "Parallel", _parallel, "composite",
    {
        "policy": Param(str, default="all", choices=["all", "one"],
                        doc="succeed when all children succeed, or when one does"),
        "synchronise": Param(bool, default=True, doc="with policy 'all', do not re-tick children that already succeeded"),
    },
    doc="Ticks all the children at every tick", category="composite"))

COMPOSITES = ("Sequence", "Selector", "Parallel")
