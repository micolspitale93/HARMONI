"""Leaves for interactions with any number of humans and of agents (robots, virtual agents).

They route by **role** and **channel** through the cast of the tree (see :mod:`harmoni.tree.cast`),
so the same tree works with one or many robots, and swapping which robot plays which role is a
configuration change. Every spoken turn is appended to the conversation log (blackboard key
``conversation``), which monitoring tools display.
"""

import json
import re
import time
from typing import Any

import py_trees

from harmoni.leaves.base import HarmoniLeaf
from harmoni.leaves.service_action import PendingCall
from harmoni.tree.clients import as_action
from harmoni.tree.registry import Param, register_leaf

Status = py_trees.common.Status
_OUTCOMES = ["failure", "success"]
MAX_CONVERSATION = 300
SPEAKER_RE = re.compile(r"^\s*([^:\n]{1,40}):\s*(.*)$", re.S)


def log_turn(leaf: HarmoniLeaf, kind, speaker, text, role=None, to=None):
    """Append a turn to the conversation log (a new list, so snapshots see the change)"""
    log = list(leaf.get("conversation") or [])
    log.append({"n": len(log) + 1, "kind": kind, "speaker": speaker, "role": role, "to": to or None,
                "text": text, "time": round(time.time(), 3)})
    leaf.set("conversation", log[-MAX_CONVERSATION:])


def split_speaker(text):
    """``"Sarah: hello"`` -> ``("Sarah", "hello")``; no speaker -> ``(None, text)``"""
    match = SPEAKER_RE.match(str(text or ""))
    return (match.group(1).strip(), match.group(2).strip()) if match else (None, str(text or "").strip())


def _client_for(leaf, service):
    if leaf.context is None or leaf.context.client_for is None:
        raise RuntimeError(f"{leaf.name}: no service client available for '{service}'")
    return leaf.context.client_for(service)


def _cast(leaf):
    return leaf.context.cast if leaf.context is not None else None


@register_leaf(
    "AgentSpeak",
    params={
        "agent_key": Param(str, default="bot/agent", doc="blackboard key with the role (or name) of the agent"),
        "message_key": Param(str, default="bot/message", doc="blackboard key with the text to say"),
        "addressee_key": Param(str, default="bot/addressee", doc="blackboard key with the addressee (optional)"),
        "speak_key": Param(str, default="bot/speak", doc="if this value is false nobody speaks (SUCCESS)"),
        "default_role": Param(str, doc="agent used when the role is unknown (default: the first agent)"),
        "channel": Param(str, default="speech", doc="channel of the agent's services used to speak"),
        "action": Param(str, default="DO", choices=["DO", "REQUEST"]),
        "timeout_s": Param(float, doc="give up after this many seconds"),
        "on_timeout": Param(str, default="success", choices=_OUTCOMES),
        "on_failure": Param(str, default="success", choices=_OUTCOMES,
                            doc="'success' keeps the interaction going if a robot does not answer"),
    },
    reads=["{agent_key}", "{message_key}", "{speak_key}"],
    writes=["conversation"],
    category="multi-party",
    doc="The agent chosen on the blackboard speaks, with its own speech service (any number of agents)",
)
class AgentSpeak(HarmoniLeaf):
    def __init__(self, name, context=None, agent_key="bot/agent", message_key="bot/message",
                 addressee_key="bot/addressee", speak_key="bot/speak", default_role=None, channel="speech",
                 action="DO", timeout_s=None, on_timeout="success", on_failure="success"):
        super().__init__(name, context)
        self.agent_key, self.message_key, self.addressee_key = agent_key, message_key, addressee_key
        self.speak_key, self.default_role, self.channel = speak_key, default_role, channel
        self.action = as_action(action)
        self.timeout_s = float(timeout_s) if timeout_s is not None else None
        self.on_timeout, self.on_failure = on_timeout, on_failure
        self.pending = None
        self.reads(agent_key, message_key, addressee_key, speak_key)
        self.writes("conversation")

    def _choose_agent(self, cast):
        return (cast.agent(self.get(self.agent_key)) or (cast.agent(self.default_role) if self.default_role else None)
                or cast.default_agent)

    def initialise(self):
        self.pending = None
        if self.speak_key and self.get(self.speak_key, True) is False:
            self.feedback_message = "silence"
            return
        message = str(self.get(self.message_key, "") or "").strip()
        cast = _cast(self)
        agent = self._choose_agent(cast) if cast else None
        if not message:
            self.feedback_message = "nothing to say"
            return
        if agent is None or self.channel not in agent.services:
            self.feedback_message = f"no agent with a '{self.channel}' service in the cast"
            return
        addressee = self.get(self.addressee_key, "") if self.addressee_key else ""
        addressee = "" if str(addressee).lower() == "null" else addressee
        service = agent.services[self.channel]
        payload = json.dumps({"input": message, "addressee": addressee, "agent": agent.role, "name": agent.name})
        self.pending = PendingCall(_client_for(self, service), service, self.action, payload, self.now(), self.timeout_s)
        log_turn(self, "agent", agent.display_name, message, role=agent.role, to=addressee)
        self.feedback_message = f"{agent.display_name} ({agent.role}) via {service}"

    def update(self):
        if self.pending is None:
            return Status.SUCCESS
        outcome = self.pending.poll(self.now())
        if outcome == "running":
            return Status.RUNNING
        if outcome == "ok":
            return Status.SUCCESS
        self.feedback_message = f"{outcome}: {self.pending.message}"
        policy = self.on_timeout if outcome == "timeout" else self.on_failure
        return Status.SUCCESS if policy == "success" else Status.FAILURE

    def terminate(self, new_status):
        if new_status == Status.INVALID and self.pending is not None:
            self.pending.cancel()


@register_leaf(
    "AgentsAction",
    params={
        "channel": Param(str, required=True, doc="channel of the agents' services, e.g. led, gesture"),
        "action": Param(str, default="DO", choices=["DO", "REQUEST", "ON", "OFF"]),
        "input_value": Param(Any, doc="payload sent to every agent, e.g. 'red'"),
        "input_key": Param(str, doc="blackboard key used as payload instead of input_value"),
        "roles": Param(list, doc="only these roles (default: every agent with the channel)"),
        "wait": Param(bool, default=True, doc="wait for every agent to finish"),
        "timeout_s": Param(float),
        "on_timeout": Param(str, default="success", choices=_OUTCOMES),
        "on_failure": Param(str, default="success", choices=_OUTCOMES),
    },
    reads=["{input_key}"],
    category="multi-party",
    doc="Every agent (or the given roles) performs the same action on a channel, e.g. all LEDs red",
)
class AgentsAction(HarmoniLeaf):
    def __init__(self, name, context=None, channel=None, action="DO", input_value=None, input_key=None, roles=None,
                 wait=True, timeout_s=None, on_timeout="success", on_failure="success"):
        super().__init__(name, context)
        self.channel, self.action = channel, as_action(action)
        self.input_value, self.input_key, self.roles = input_value, input_key, roles
        self.wait = bool(wait)
        self.timeout_s = float(timeout_s) if timeout_s is not None else None
        self.on_timeout, self.on_failure = on_timeout, on_failure
        self.pending = []
        self.reads(input_key)

    def _payload(self):
        value = self.get(self.input_key) if self.input_key else self.input_value
        if value is None:
            return ""
        return value if isinstance(value, str) else json.dumps(value)

    def initialise(self):
        self.pending = []
        cast = _cast(self)
        agents = [a for a in (cast.agents if cast else [])
                  if self.channel in a.services and (not self.roles or a.role in self.roles)]
        payload = self._payload()
        for agent in agents:
            service = agent.services[self.channel]
            self.pending.append(PendingCall(_client_for(self, service), service, self.action, payload,
                                            self.now(), self.timeout_s))
        self.feedback_message = f"{self.action.name} {payload!r} on {len(self.pending)} agent(s)"

    def update(self):
        if not self.wait or not self.pending:
            return Status.SUCCESS
        outcomes = [p.poll(self.now()) for p in self.pending]
        if "running" in outcomes:
            return Status.RUNNING
        if all(o == "ok" for o in outcomes):
            return Status.SUCCESS
        failed = [p.service for p, o in zip(self.pending, outcomes) if o != "ok"]
        self.feedback_message = f"not done by {', '.join(failed)}"
        policy = self.on_timeout if "timeout" in outcomes and "failed" not in outcomes else self.on_failure
        return Status.SUCCESS if policy == "success" else Status.FAILURE

    def terminate(self, new_status):
        if new_status == Status.INVALID:
            for p in self.pending:
                p.cancel()


@register_leaf(
    "LogUtterance",
    params={
        "key": Param(str, default="stt/result", doc="blackboard key with the utterance, e.g. 'Sarah: hello'"),
        "speaker": Param(str, doc="fixed speaker name (default: the 'Name:' prefix of the text)"),
    },
    reads=["{key}"],
    writes=["conversation"],
    category="multi-party",
    doc="Adds a human utterance to the conversation log (who said what)",
)
class LogUtterance(HarmoniLeaf):
    def __init__(self, name, context=None, key="stt/result", speaker=None):
        super().__init__(name, context)
        self.key, self.speaker = key, speaker
        self.reads(key)
        self.writes("conversation")

    def update(self):
        text = self.get(self.key, "")
        if not str(text or "").strip():
            return Status.SUCCESS
        speaker, content = (self.speaker, str(text)) if self.speaker else split_speaker(text)
        cast = _cast(self)
        kind = "human" if speaker else "event"
        if speaker and cast and cast.humans and speaker not in cast.humans:
            kind = "human"  # unknown speaker (e.g. Guest-4): still a human turn
        log_turn(self, kind, speaker or "", content)
        return Status.SUCCESS
