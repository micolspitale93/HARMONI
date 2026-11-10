"""General purpose leaves: blackboard conditions and assignments, waiting."""

from typing import Any

import py_trees

from harmoni.leaves.base import HarmoniLeaf
from harmoni.tree.registry import Param, register_leaf

Status = py_trees.common.Status


@register_leaf(
    "CheckValue",
    params={
        "key": Param(str, required=True, doc="blackboard key, e.g. bot/agent"),
        "equals": Param(Any, doc="SUCCESS if the value is equal to this"),
        "not_equals": Param(Any, doc="SUCCESS if the value is different from this"),
        "one_of": Param(list, doc="SUCCESS if the value is in this list"),
        "truthy": Param(bool, doc="SUCCESS if bool(value) is equal to this"),
    },
    reads=["{key}"],
    category="condition",
    doc="Condition on a blackboard value: SUCCESS or FAILURE, never RUNNING",
)
class CheckValue(HarmoniLeaf):
    def __init__(self, name, context=None, key=None, equals=None, not_equals=None, one_of=None, truthy=None):
        super().__init__(name, context)
        self.key = key
        self.checks = {"equals": equals, "not_equals": not_equals, "one_of": one_of, "truthy": truthy}
        self.reads(key)

    def update(self):
        value = self.get(self.key)
        c = self.checks
        ok = True
        if c["equals"] is not None:
            ok = ok and value == c["equals"]
        if c["not_equals"] is not None:
            ok = ok and value != c["not_equals"]
        if c["one_of"] is not None:
            ok = ok and value in c["one_of"]
        if c["truthy"] is not None:
            ok = ok and bool(value) == c["truthy"]
        self.feedback_message = f"{self.key}={value!r}"
        return Status.SUCCESS if ok else Status.FAILURE


@register_leaf(
    "SetValue",
    params={"key": Param(str, required=True), "value": Param(Any, doc="value to write")},
    writes=["{key}"],
    category="blackboard",
    doc="Writes a constant on the blackboard",
)
class SetValue(HarmoniLeaf):
    def __init__(self, name, context=None, key=None, value=None):
        super().__init__(name, context)
        self.key, self.value = key, value
        self.writes(key)

    def update(self):
        self.set(self.key, self.value)
        return Status.SUCCESS


@register_leaf(
    "CopyValue",
    params={"source": Param(str, required=True), "target": Param(str, required=True)},
    reads=["{source}"],
    writes=["{target}"],
    category="blackboard",
    doc="Copies a blackboard value to another key",
)
class CopyValue(HarmoniLeaf):
    def __init__(self, name, context=None, source=None, target=None):
        super().__init__(name, context)
        self.source, self.target = source, target
        self.reads(source)
        self.writes(target)

    def update(self):
        self.set(self.target, self.get(self.source))
        return Status.SUCCESS


@register_leaf(
    "Wait",
    params={"seconds": Param(float, required=True, doc="time to wait")},
    category="timing",
    doc="RUNNING for the given time, then SUCCESS (e.g. a pause between robot turns)",
)
class Wait(HarmoniLeaf):
    def __init__(self, name, context=None, seconds=0.0):
        super().__init__(name, context)
        self.seconds = float(seconds)
        self.start = None

    def initialise(self):
        self.start = self.now()

    def update(self):
        return Status.SUCCESS if self.now() - self.start >= self.seconds else Status.RUNNING
