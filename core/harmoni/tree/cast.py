"""The cast of an interaction: any number of humans and of agents (robots, virtual agents).

In a tree file::

    "cast": {
      "humans": ["Sarah", "Jane", "Alex"],               # or "${participants}" = "Sarah, Jane, Alex"
      "agents": [
        {"role": "Mover", "name": "Manny", "robot": "Furhat",
         "services": {"speech": "speaker_furhat", "led": "led_furhat"}},
        {"role": "Opposer", "name": "Sam", "robot": "NAO",
         "services": {"speech": "speaker_nao", "led": "led_nao"}}
      ]
    }

- the **role** is how the interaction logic (and an LLM orchestrator) refers to an agent;
- the **name** is how the agent presents itself;
- **services** maps a channel (speech, led, gesture, ...) to the id of the HARMONI service that
  realizes it for this agent.

Leaves such as ``AgentSpeak`` and ``AgentsAction`` route by role and channel, so the same tree works
with 1 or N robots, and changing which robot plays which role (an experimental condition) is a
configuration change, not a tree change. A configuration or a run can override the cast:
``humans`` replaces the participants, ``agents`` as a list replaces the agents, ``agents`` as a
mapping ``{role: {...}}`` updates the agents with those roles.
"""

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Agent:
    role: str
    name: str = ""
    robot: str = ""
    services: Dict[str, str] = field(default_factory=dict)

    @property
    def display_name(self):
        return self.name or self.role

    def to_dict(self):
        return {"role": self.role, "name": self.name, "robot": self.robot, "services": dict(self.services)}


def _humans(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [h.strip() for h in value.split(",") if h.strip()]
    result = []
    for h in value:
        if isinstance(h, dict):
            h = h.get("name", "")
        if str(h).strip():
            result.append(str(h).strip())
    return result


@dataclass
class Cast:
    humans: List[str] = field(default_factory=list)
    agents: List[Agent] = field(default_factory=list)

    @classmethod
    def from_spec(cls, data: Optional[dict]) -> "Cast":
        data = data or {}
        agents = []
        for a in data.get("agents") or []:
            if not isinstance(a, dict):
                continue
            agents.append(Agent(role=str(a.get("role", "")).strip(), name=str(a.get("name", "") or ""),
                                robot=str(a.get("robot", "") or ""),
                                services={str(k): str(v) for k, v in (a.get("services") or {}).items() if v}))
        return cls(humans=_humans(data.get("humans")), agents=agents)

    def to_dict(self):
        return {"humans": list(self.humans), "agents": [a.to_dict() for a in self.agents]}

    @property
    def roles(self):
        return [a.role for a in self.agents]

    def agent(self, role) -> Optional[Agent]:
        if role is None:
            return None
        role = str(role).strip().lower()
        for a in self.agents:
            if a.role.lower() == role or (a.name and a.name.lower() == role):
                return a
        return None

    @property
    def default_agent(self) -> Optional[Agent]:
        return self.agents[0] if self.agents else None

    def services(self, channel=None):
        ids = []
        for a in self.agents:
            for ch, service in a.services.items():
                if (channel is None or ch == channel) and service not in ids:
                    ids.append(service)
        return ids

    def channels(self):
        return sorted({ch for a in self.agents for ch in a.services})


def merge_cast(base: Optional[dict], override: Optional[dict]) -> dict:
    """Apply a cast override (from a configuration or a run) to the cast of a tree"""
    result = copy.deepcopy(base or {})
    if not override:
        return result
    if "humans" in override and override["humans"] is not None:
        result["humans"] = copy.deepcopy(override["humans"])
    agents = override.get("agents")
    if isinstance(agents, list):
        result["agents"] = copy.deepcopy(agents)
    elif isinstance(agents, dict) and isinstance(result.get("agents"), dict):
        # two overrides by role (e.g. a condition extending another condition): merge them
        for role, update in agents.items():
            target = result["agents"].setdefault(role, {})
            update = dict(update or {})
            if "services" in update:
                target["services"] = dict(target.get("services") or {}, **(update.pop("services") or {}))
            target.update(update)
    elif isinstance(agents, dict):
        current = result.setdefault("agents", [])
        for role, update in agents.items():
            target = next((a for a in current if str(a.get("role")) == str(role)), None)
            if target is None:
                target = {"role": role}
                current.append(target)
            update = dict(update or {})
            if "services" in update:
                target["services"] = dict(target.get("services") or {}, **(update.pop("services") or {}))
            target.update(update)
    return result


def validate_cast(data) -> List[tuple]:
    """Return a list of (level, path, message)"""
    issues = []
    if data is None:
        return issues
    if not isinstance(data, dict):
        return [("error", "cast", "must be an object with 'humans' and 'agents'")]
    if not isinstance(data.get("agents", []), list):
        issues.append(("error", "cast.agents", "must be a list"))
        return issues
    seen = set()
    for i, agent in enumerate(data.get("agents") or []):
        path = f"cast.agents[{i}]"
        if not isinstance(agent, dict) or not str(agent.get("role", "")).strip():
            issues.append(("error", path, "an agent needs a role"))
            continue
        role = str(agent["role"]).strip().lower()
        if role in seen:
            issues.append(("error", path, f"duplicate role '{agent['role']}'"))
        seen.add(role)
        if not isinstance(agent.get("services", {}), dict):
            issues.append(("error", f"{path}.services", "must map channels to service ids"))
    return issues
