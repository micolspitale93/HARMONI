"""Leaves for scripted and LLM-orchestrated dialogues, with any number of humans and agents.

Blackboard keys used:

- ``stt/result``      last transcription, ``"<speaker name>: <text>"`` (written by the STT service)
- ``scene/*``         current scene of the script: ``utterance``, ``nlp`` (0 scripted, 1 LLM),
                      ``agent`` (role), ``number``, ``finished``
- ``bot/raw``         raw answer of the LLM orchestrator
- ``bot/*``           decision: ``message``, ``agent`` (a role of the cast, or null), ``addressee``, ``speak``

A script is a JSON file with one list of scenes per session (``"1session"``, ``"2session"``, ...: by
default the session is chosen from the number of humans in the cast). A scene is
``{"utterance": ..., "agent": <role>, "nlp": 0 | 1}``: ``nlp: 0`` scenes are said as written by the agent
with that role, ``nlp: 1`` scenes let the orchestrator decide. ``$USERNAME1``, ``$USERNAME2``... are
replaced by the names of the humans.
"""

import ast
import json

import py_trees

from harmoni.leaves.base import HarmoniLeaf
from harmoni.tree.registry import Param, register_leaf

Status = py_trees.common.Status

START_PROMPT = "Now you MUST START the negotiation giving your opinion without telling your name."


def format_user_utterance(text, role="user"):
    """Wrap a message in the payload format of the assistant service (``"['*user* ...']"``).

    repr() keeps the python literal valid whatever quotes the text contains.
    """
    return repr([f"*{role}* " + str(text if text is not None else "")])


def parse_agent_response(text):
    """Parse the orchestrator (LLM) answer; never raises.

    - JSON object or python-like dict -> its values (missing keys get safe defaults)
    - non-empty plain text            -> said as it is
    - empty / None                    -> nobody speaks

    Returns:
        dict: {"message": str, "agent": str, "intervene": bool, "addressee": str}
    """
    parsed = None
    if isinstance(text, dict):
        parsed = text
    elif isinstance(text, str) and text.strip():
        try:
            parsed = json.loads(text)
        except ValueError:
            try:
                parsed = ast.literal_eval(text.strip())
            except (ValueError, SyntaxError):
                parsed = None
    if not isinstance(parsed, dict):
        message = text.strip() if isinstance(text, str) else ""
        return {"message": message, "agent": "null", "intervene": bool(message), "addressee": "null"}
    intervene = parsed.get("intervene", True)
    if isinstance(intervene, str):
        intervene = intervene.strip().lower() not in ("false", "0", "no")
    return {
        "message": str(parsed.get("response", "")),
        "agent": str(parsed.get("agent") or "null"),
        "intervene": bool(intervene),
        "addressee": str(parsed.get("addressee") or "null"),
    }


@register_leaf(
    "DialogueScript",
    params={
        "script": Param(str, required=True, doc="JSON script, relative to the tree file"),
        "session": Param(str, default="auto", doc="session of the script; 'auto': '<number of humans>session'"),
        "max_scenes": Param(int, default=30, doc="after this many turns the closing scene (the last one) is said"),
        "start_after": Param(int, doc="turn at which start_prompt is sent to the orchestrator "
                                      "(default: after the introductions, number of humans + 1; -1: never)"),
        "start_prompt": Param(str, default=START_PROMPT, doc="message telling the orchestrator to start"),
        "start_prompt_role": Param(str, default="assistant", choices=["assistant", "user", "system"]),
        "input_key": Param(str, default="stt/result", doc="what the humans said"),
        "user_names": Param(str, doc="comma separated names; default: the humans of the cast"),
    },
    reads=["{input_key}"],
    writes=["scene/utterance", "scene/nlp", "scene/agent", "scene/number", "scene/finished", "{input_key}"],
    category="multi-party",
    doc="Moves the dialogue to the next scene of a script (scripted lines or orchestrator turns)",
)
class DialogueScript(HarmoniLeaf):
    def __init__(self, name, context=None, script=None, session="auto", max_scenes=30, start_after=None,
                 start_prompt=START_PROMPT, start_prompt_role="assistant", input_key="stt/result", user_names=None):
        super().__init__(name, context)
        self.script_path = script
        self.session = str(session or "auto")
        self.max_scenes = int(max_scenes)
        self.start_after = start_after
        self.start_prompt, self.start_prompt_role = start_prompt, start_prompt_role
        self.input_key = input_key
        self._user_names = [n.strip() for n in str(user_names).split(",") if n.strip()] if user_names else None
        self.scene_number = 0
        self.scenes = None
        self.reads(input_key)
        self.writes("scene/utterance", "scene/nlp", "scene/agent", "scene/number", "scene/finished", input_key)

    @property
    def user_names(self):
        if self._user_names is not None:
            return self._user_names
        return list(self.context.cast.humans) if self.context is not None else []

    def setup(self, **kwargs):
        path = self.context.resolve_path(self.script_path) if self.context else self.script_path
        with open(path, "r", encoding="utf-8") as f:
            script = json.load(f)
        session = self.session
        if session == "auto":
            session = f"{len(self.user_names)}session"
            if session not in script:
                session = next(iter(script))
        if session not in script:
            raise KeyError(f"session '{session}' not in {path} (available: {', '.join(script)})")
        self.session_name = session
        self.scenes = script[session]
        if self.get(self.input_key) is None:
            self.set(self.input_key, "")
        self.set("scene/finished", False)

    def _start_turn(self):
        if self.start_after is None:
            return len(self.user_names) + 1
        return int(self.start_after)

    def _replace_names(self, text):
        for i, name in enumerate(self.user_names, start=1):
            text = text.replace(f"$USERNAME{i}", name)
        return text

    def update(self):
        if self.scenes is None:
            self.setup()
        i = self.scene_number
        scene = self.scenes[min(i, len(self.scenes) - 1)]
        nlp = scene.get("nlp", 1)
        agent = scene.get("agent", "")
        utterance = format_user_utterance(self.get(self.input_key, ""))
        if i == self._start_turn():
            utterance = format_user_utterance(self.start_prompt, self.start_prompt_role)
        if nlp == 0:
            utterance = scene["utterance"]
        finished = False
        if i >= self.max_scenes or i >= len(self.scenes) - 1:
            closing = self.scenes[-1]
            nlp, agent, utterance, finished = 0, closing.get("agent", agent), closing["utterance"], True
        self.set("scene/utterance", self._replace_names(utterance))
        self.set("scene/nlp", nlp)
        self.set("scene/agent", agent)
        self.set("scene/number", i)
        self.set("scene/finished", finished)
        self.scene_number += 1
        self.feedback_message = f"{self.session_name} scene {i} ({'scripted' if nlp == 0 else 'orchestrator'})"
        return Status.SUCCESS


# Name used by the first HARMONI 2.0 trees (same leaf)
@register_leaf(
    "GroupScript",
    params={
        "script": Param(str, required=True), "session": Param(str, default="auto"),
        "user_names": Param(str), "max_scenes": Param(int, default=30),
    },
    reads=["stt/result"],
    writes=["scene/utterance", "scene/nlp", "scene/agent", "scene/number", "scene/finished", "stt/result"],
    category="multi-party",
    doc="Deprecated name of DialogueScript",
)
class GroupScript(DialogueScript):
    pass


@register_leaf(
    "ScriptedTurn",
    reads=["scene/utterance", "scene/agent"],
    writes=["bot/message", "bot/agent", "bot/addressee", "bot/speak"],
    category="multi-party",
    doc="The agent of the scene (its role) says the scripted utterance",
)
class ScriptedTurn(HarmoniLeaf):
    def __init__(self, name, context=None):
        super().__init__(name, context)
        self.reads("scene/utterance", "scene/agent")
        self.writes("bot/message", "bot/agent", "bot/addressee", "bot/speak")

    def update(self):
        self.set("bot/message", self.get("scene/utterance", ""))
        self.set("bot/agent", self.get("scene/agent") or "null")
        self.set("bot/addressee", "null")
        self.set("bot/speak", True)
        return Status.SUCCESS


@register_leaf(
    "OrchestratorDecision",
    params={"input_key": Param(str, default="bot/raw", doc="raw answer of the LLM")},
    reads=["{input_key}"],
    writes=["bot/message", "bot/agent", "bot/addressee", "bot/speak"],
    category="multi-party",
    doc="Parses the orchestrator decision: which agent (role) speaks, what, to whom, or silence",
)
class OrchestratorDecision(HarmoniLeaf):
    """An agent that is not in the cast becomes ``null`` (AgentSpeak then uses its default agent)."""

    def __init__(self, name, context=None, input_key="bot/raw"):
        super().__init__(name, context)
        self.input_key = input_key
        self.reads(input_key)
        self.writes("bot/message", "bot/agent", "bot/addressee", "bot/speak")

    def update(self):
        decision = parse_agent_response(self.get(self.input_key))
        cast = self.context.cast if self.context is not None else None
        if cast and cast.agents and decision["agent"] != "null":
            agent = cast.agent(decision["agent"])
            decision["agent"] = agent.role if agent else "null"
        self.set("bot/message", decision["message"])
        self.set("bot/agent", decision["agent"])
        self.set("bot/addressee", decision["addressee"])
        self.set("bot/speak", decision["intervene"])
        self.feedback_message = (
            f"{decision['agent']} -> {decision['addressee']}" if decision["intervene"] else "silence"
        )
        return Status.SUCCESS
