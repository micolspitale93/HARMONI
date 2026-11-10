"""How leaves talk to services, independently of the middleware.

A :class:`ServiceClient` sends an action (REQUEST, DO, ...) with a string payload to a
service and returns a :class:`ServiceCall` that the leaf polls at every tick, so that a
tick never blocks. Implementations:

- :class:`LocalServiceClient`: runs a :class:`harmoni.services.base.ServiceBackend`
  in-process, in a worker thread (simulation, tests, single-process deployments);
- ``harmoni_nodes.ros_client.RosServiceClient`` (ros2/): sends a ROS2 action goal.
"""

import concurrent.futures
import enum
import logging
import threading
from typing import Callable, Dict, Optional

from harmoni.constants import ActionType

log = logging.getLogger("harmoni.clients")


class CallStatus(enum.Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"  # the service answered (check `ok` for the outcome)
    FAILED = "failed"  # the call itself failed (service unreachable, exception, ...)
    CANCELLED = "cancelled"


class ServiceCall:
    """Handle of a pending call. Subclasses must keep these attributes up to date."""

    def __init__(self):
        self.status = CallStatus.RUNNING
        self.ok = False
        self.message = ""

    @property
    def done(self):
        return self.status != CallStatus.RUNNING

    def cancel(self):  # pragma: no cover - overridden
        self.status = CallStatus.CANCELLED


class ServiceClient:
    def send(self, action: ActionType, data: str) -> ServiceCall:  # pragma: no cover - interface
        raise NotImplementedError


def as_action(action) -> ActionType:
    if isinstance(action, ActionType):
        return action
    if isinstance(action, int):
        return ActionType(action)
    return ActionType[str(action).upper()]


class _FutureCall(ServiceCall):
    def __init__(self, future: concurrent.futures.Future, on_cancel: Callable[[], None]):
        super().__init__()
        self._future = future
        self._on_cancel = on_cancel
        self._lock = threading.Lock()
        future.add_done_callback(self._done)

    def _done(self, future):
        with self._lock:
            if self.status == CallStatus.CANCELLED:
                return
            try:
                result = future.result()
                self.ok = bool(result.ok)
                self.message = result.message
                self.status = CallStatus.SUCCEEDED
            except Exception as e:  # noqa: BLE001 - reported to the leaf
                self.message = f"{type(e).__name__}: {e}"
                self.status = CallStatus.FAILED

    def cancel(self):
        with self._lock:
            if self.status != CallStatus.RUNNING:
                return
            self.status = CallStatus.CANCELLED
        self._future.cancel()
        try:
            self._on_cancel()
        except Exception:  # noqa: BLE001
            log.exception("error while cancelling")


class LocalServiceClient(ServiceClient):
    """Runs a service backend in-process; every call is executed in a worker thread"""

    def __init__(self, backend, max_workers: int = 1):
        self.backend = backend
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers,
                                                               thread_name_prefix=backend.service_id)

    def send(self, action, data: str) -> ServiceCall:
        action = as_action(action)
        future = self._executor.submit(self.backend.handle, action, data)
        return _FutureCall(future, self.backend.cancel)

    def shutdown(self):
        self._executor.shutdown(wait=False)


class ClientRegistry:
    """Maps service ids to clients. ``factory(service_id)`` creates missing clients lazily."""

    def __init__(self, clients: Optional[Dict[str, ServiceClient]] = None, factory=None):
        self._clients = dict(clients or {})
        self._factory = factory

    def __call__(self, service_id) -> ServiceClient:
        if service_id not in self._clients:
            if self._factory is None:
                raise KeyError(f"No client for service '{service_id}'")
            self._clients[service_id] = self._factory(service_id)
        return self._clients[service_id]

    def shutdown(self):
        for client in self._clients.values():
            if hasattr(client, "shutdown"):
                client.shutdown()
