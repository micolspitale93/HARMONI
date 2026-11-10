"""Leaves of the multi-party group interaction (two robots moderated by an LLM).

Blackboard keys used:

- ``stt/result``      last transcription, ``"<speaker name>: <text>"`` (written by the STT service)
- ``scene/*``         current scene of the script: ``utterance``, ``nlp`` (0 scripted, 1 LLM),
                      ``agent``, ``number``, ``finished``
- ``bot/raw``         raw answer of the LLM orchestrator
- ``bot/*``           decision: ``message``, ``agent`` (Mover/Opposer/null), ``addressee``, ``speak``
"""

import ast
import json

import py_trees

from harmoni.leaves.base import HarmoniLeaf
from harmoni.tree.registry import Param, register_leaf

Status = py_trees.common.Status

START_DISCUSSION = "Now you can MUST START the discussion without telling your name."


def format_user_utterance(text):
    """Wrap a transcription in the payload format of the assistant service.

    repr() keeps the python literal valid whatever quotes the transcription contains.
    """
    return repr(["*user* " + str(text if text is not None else "")])


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
    "GroupScript",
    params={
        "script": Param(str, required=True, doc="JSON script, relative to the tree file"),
        "session": Param(str, required=True, doc="session of the script: 1session, 2session or 3session"),
        "user_names": Param(str, default="", doc="comma separated participants, replace $USERNAME1.."),
        "max_scenes": Param(int, default=30, doc="after this many turns the closing scene is said"),
    },
    reads=["stt/result"],
    writes=["scene/utterance", "scene/nlp", "scene/agent", "scene/number", "scene/finished", "stt/result"],
    category="group interaction",
    doc="Moves the group interaction to the next scene of the script",
)
class GroupScript(HarmoniLeaf):
    def __init__(self, name, context=None, script=None, session=None, user_names="", max_scenes=30):
        super().__init__(name, context)
        self.script_path = script
        self.session = str(session)
        self.user_names = [n.strip() for n in str(user_names or "").split(",") if n.strip()]
        self.max_scenes = int(max_scenes)
        self.scene_number = 0
        self.scenes = None
        self.writes("scene/utterance", "scene/nlp", "scene/agent", "scene/number", "scene/finished", "stt/result")

    def setup(self, **kwargs):
        path = self.context.resolve_path(self.script_path) if self.context else self.script_path
        with open(path, "r", encoding="utf-8") as f:
            script = json.load(f)
        if self.session not in script:
            raise KeyError(f"session '{self.session}' not in {path} (available: {', '.join(script)})")
        self.scenes = script[self.session]
        if self.get("stt/result") is None:
            self.set("stt/result", "")
        self.set("scene/finished", False)

    def _participants(self):
        try:
            return int(self.session[0])
        except (ValueError, IndexError):
            return len(self.user_names)

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
        utterance = format_user_utterance(self.get("stt/result", ""))
        if i == 1 + self._participants():
            utterance = format_user_utterance(START_DISCUSSION)
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
        self.feedback_message = f"scene {i} ({'scripted' if nlp == 0 else 'LLM'})"
        return Status.SUCCESS


@register_leaf(
    "ScriptedTurn",
    reads=["scene/utterance", "scene/agent"],
    writes=["bot/message", "bot/agent", "bot/addressee", "bot/speak"],
    category="group interaction",
    doc="The robot of the scene says the scripted utterance",
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
    category="group interaction",
    doc="Parses the LLM decision: who speaks, what, to whom, or silence",
)
class OrchestratorDecision(HarmoniLeaf):
    def __init__(self, name, context=None, input_key="bot/raw"):
        super().__init__(name, context)
        self.input_key = input_key
        self.reads(input_key)
        self.writes("bot/message", "bot/agent", "bot/addressee", "bot/speak")

    def update(self):
        decision = parse_agent_response(self.get(self.input_key))
        self.set("bot/message", decision["message"])
        self.set("bot/agent", decision["agent"])
        self.set("bot/addressee", decision["addressee"])
        self.set("bot/speak", decision["intervene"])
        self.feedback_message = (
            f"{decision['agent']} -> {decision['addressee']}" if decision["intervene"] else "silence"
        )
        return Status.SUCCESS
