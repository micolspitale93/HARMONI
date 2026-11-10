"""Common helpers for HARMONI leaves."""

import py_trees

from harmoni.tree.registry import normalize_key

_UNSET = object()


class HarmoniLeaf(py_trees.behaviour.Behaviour):
    """Base class: blackboard access with absolute keys (``scene/utterance``)"""

    def __init__(self, name, context=None):
        super().__init__(name=name)
        self.context = context
        self.bb = self.attach_blackboard_client(name=name)

    @property
    def log(self):
        return self.context.logger if self.context is not None else None

    def reads(self, *keys):
        for key in keys:
            if key:
                self.bb.register_key(key=normalize_key(key), access=py_trees.common.Access.READ)

    def writes(self, *keys):
        for key in keys:
            if key:
                self.bb.register_key(key=normalize_key(key), access=py_trees.common.Access.WRITE)

    def get(self, key, default=None):
        try:
            return self.bb.get(normalize_key(key))
        except KeyError:
            return default

    def set(self, key, value):
        self.bb.set(normalize_key(key), value, overwrite=True)

    def now(self):
        return self.context.clock() if self.context is not None else 0.0
