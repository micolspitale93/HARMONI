"""Base class and registry of service backends."""

import logging
import os
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from harmoni.constants import ActionType

log = logging.getLogger("harmoni.services")


@dataclass
class Result:
    ok: bool
    message: str = ""


def load_env():
    """Load credentials from the .env file named by HARMONI_ENV_FILE (if any).

    With docker compose the variables are already in the environment (env_file), so a
    missing file is not an error.
    """
    path = os.getenv("HARMONI_ENV_FILE")
    if not path or not os.path.exists(path):
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        log.warning("python-dotenv not installed: %s not loaded", path)
        return
    load_dotenv(path)


class ServiceBackend:
    """Base class of the service backends.

    Args:
        service_id: id of the service, e.g. ``bot_default`` (used in logs and topics)
        params: configuration of the service (from the services config file)
        emit: ``emit(channel, message)`` publishes side outputs (e.g. the assistant thread id);
              the ROS2 node maps each channel to the topic ``/harmoni/<service_id>/<channel>``
    """

    #: backend name used in configuration files (set by @register_backend)
    backend_name = ""

    def __init__(self, service_id: str, params: Optional[dict] = None,
                 emit: Optional[Callable[[str, str], None]] = None):
        self.service_id = service_id
        self.params = dict(params or {})
        self._emit = emit or (lambda channel, message: None)
        self.log = logging.getLogger(f"harmoni.{service_id}")

    # --------------------------------------------------------------- lifecycle
    def setup(self):
        """Connect to SDKs/robots. Called once before the first action."""

    def request(self, data: str) -> Result:
        raise NotImplementedError

    def do(self, data: str) -> Result:
        raise NotImplementedError

    def start(self, data: str = "") -> Result:
        return Result(True)

    def stop(self) -> Result:
        return Result(True)

    def pause(self) -> Result:
        return Result(True)

    def cancel(self):
        """Abort the action in progress (called from another thread)"""

    def on_input(self, channel: str, message: str):
        """Side input from another service (e.g. the shared thread id)"""

    def emit(self, channel: str, message: str):
        self._emit(channel, message)

    # --------------------------------------------------------------- dispatch
    def handle(self, action, data: str = "") -> Result:
        """Execute an action and always return a Result (never raises)"""
        action = ActionType(int(action))
        try:
            if action == ActionType.REQUEST:
                return self.request(data)
            if action == ActionType.DO:
                return self.do(data)
            if action == ActionType.ON:
                return self.start(data)
            if action == ActionType.OFF:
                return self.stop()
            return self.pause()
        except NotImplementedError:
            return Result(False, f"{self.service_id} does not support {action.name}")
        except Exception as e:  # noqa: BLE001 - reported to the caller
            self.log.exception("%s failed", action.name)
            return Result(False, f"{type(e).__name__}: {e}")


_BACKENDS: Dict[str, type] = {}


def register_backend(name):
    def decorator(cls):
        cls.backend_name = name
        _BACKENDS[name] = cls
        return cls

    return decorator


def available_backends():
    return dict(_BACKENDS)


def create_backend(name, service_id, params=None, emit=None) -> ServiceBackend:
    try:
        cls = _BACKENDS[name]
    except KeyError:
        raise KeyError(f"Unknown backend '{name}'. Available: {', '.join(sorted(_BACKENDS))}") from None
    return cls(service_id, params, emit)
