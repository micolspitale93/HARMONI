"""Generic leaf calling a HARMONI service (sensor, detector, dialogue, actuator).

Every HARMONI service exposes the same interface (an action with a type and a string
payload, answered with ok + message), so a single leaf type can call any of them. The
call is asynchronous: the tick never blocks, and ``timeout_s`` bounds how long the tree
waits for slow robots or cloud services.
"""

import json
from typing import Any

import py_trees

from harmoni.leaves.base import HarmoniLeaf
from harmoni.tree.clients import CallStatus, as_action
from harmoni.tree.registry import Param, register_leaf

Status = py_trees.common.Status
_OUTCOMES = ["failure", "success"]


class PendingCall:
    """A call in progress, with its own deadline (shared by the service leaves)"""

    def __init__(self, client, service, action, data, now, timeout_s=None):
        self.service = service
        self.started = now
        self.timeout_s = timeout_s
        self.call = client.send(action, data)

    def poll(self, now):
        """'running' | 'ok' | 'failed' | 'timeout' (a timed-out call is cancelled)"""
        call = self.call
        if call.status == CallStatus.RUNNING:
            if self.timeout_s is not None and now - self.started > self.timeout_s:
                call.cancel()
                return "timeout"
            return "running"
        return "ok" if call.status == CallStatus.SUCCEEDED and call.ok else "failed"

    @property
    def message(self):
        return self.call.message

    def cancel(self):
        if self.call.status == CallStatus.RUNNING:
            self.call.cancel()


@register_leaf(
    "ServiceAction",
    params={
        "service": Param(str, required=True, doc="service id, e.g. bot_default, speaker_furhat"),
        "action": Param(str, default="REQUEST", choices=["REQUEST", "DO", "ON", "OFF", "PAUSE"]),
        "input_key": Param(str, doc="blackboard key sent as payload"),
        "input_value": Param(Any, doc="constant payload"),
        "input_json": Param(dict, doc='JSON payload; strings starting with "@" are blackboard keys'),
        "output_key": Param(str, doc="blackboard key where the answer is written"),
        "timeout_s": Param(float, doc="give up after this many seconds (cancels the call)"),
        "on_timeout": Param(str, default="failure", choices=_OUTCOMES),
        "timeout_output": Param(Any, doc="value written to output_key on timeout"),
        "on_failure": Param(str, default="failure", choices=_OUTCOMES,
                            doc="status returned when the service fails ('success' keeps the interaction going)"),
        "failure_output": Param(Any, doc="value written to output_key on failure"),
    },
    reads=["{input_key}"],
    writes=["{output_key}"],
    category="service",
    doc="Calls a HARMONI service and waits (without blocking) for its answer",
)
class ServiceAction(HarmoniLeaf):
    def __init__(self, name, context=None, service=None, action="REQUEST", input_key=None, input_value=None,
                 input_json=None, output_key=None, timeout_s=None, on_timeout="failure", timeout_output=None,
                 on_failure="failure", failure_output=None):
        super().__init__(name, context)
        self.service = service
        self.action = as_action(action)
        self.input_key, self.input_value, self.input_json = input_key, input_value, input_json
        self.output_key = output_key
        self.timeout_s = float(timeout_s) if timeout_s is not None else None
        self.on_timeout, self.timeout_output = on_timeout, timeout_output
        self.on_failure, self.failure_output = on_failure, failure_output
        self.client = None
        self.call = None
        self.started = None
        self.reads(input_key)
        for value in (input_json or {}).values():
            if isinstance(value, str) and value.startswith("@"):
                self.reads(value[1:])
        self.writes(output_key)

    def setup(self, **kwargs):
        self._ensure_client()

    def _ensure_client(self):
        if self.client is None:
            if self.context is None or self.context.client_for is None:
                raise RuntimeError(f"{self.name}: no service client available for '{self.service}'")
            self.client = self.context.client_for(self.service)

    def payload(self):
        if self.input_json is not None:
            data = {}
            for k, v in self.input_json.items():
                if isinstance(v, str) and v.startswith("@"):
                    v = self.get(v[1:], "")
                data[k] = v
            return json.dumps(data)
        if self.input_key:
            value = self.get(self.input_key, "")
            return value if isinstance(value, str) else json.dumps(value)
        if self.input_value is not None:
            return self.input_value if isinstance(self.input_value, str) else json.dumps(self.input_value)
        return ""

    def initialise(self):
        self._ensure_client()
        self.started = self.now()
        self.call = self.client.send(self.action, self.payload())
        self.feedback_message = f"{self.action.name} sent to {self.service}"

    def _finish(self, outcome, output):
        if output is not None and self.output_key:
            self.set(self.output_key, output)
        return Status.SUCCESS if outcome == "success" else Status.FAILURE

    def update(self):
        call = self.call
        if call is None:
            return Status.FAILURE
        if call.status == CallStatus.RUNNING:
            if self.timeout_s is not None and self.now() - self.started > self.timeout_s:
                call.cancel()
                self.feedback_message = f"timeout after {self.timeout_s}s"
                return self._finish(self.on_timeout, self.timeout_output)
            return Status.RUNNING
        if call.status == CallStatus.SUCCEEDED and call.ok:
            self.feedback_message = "done"
            if self.output_key:
                self.set(self.output_key, call.message)
            return Status.SUCCESS
        self.feedback_message = f"{call.status.value}: {call.message}"
        return self._finish(self.on_failure, self.failure_output)

    def terminate(self, new_status):
        # interrupted by a parent (e.g. stop or reload of the tree): cancel the pending call
        if new_status == Status.INVALID and self.call is not None and self.call.status == CallStatus.RUNNING:
            self.call.cancel()
        if new_status != Status.RUNNING:
            self.call = None
