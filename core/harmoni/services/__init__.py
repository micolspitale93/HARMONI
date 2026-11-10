"""Service backends: the logic of HARMONI services, independent of ROS.

A backend implements ``request``/``do``/``start``/``stop`` on string payloads and returns a
:class:`~harmoni.services.base.Result`. Middleware layers only forward calls:

- ROS2: ``ros2 run harmoni_nodes harmoni_service --ros-args -p service_id:=bot_default ...``
- in-process: :class:`harmoni.tree.clients.LocalServiceClient` (simulation, tests)

Adding a new sensor/detector/actuator = writing one backend class and registering it with
``@register_backend("name")``; no ROS code is needed.
"""

from harmoni.services.base import (Result, ServiceBackend, available_backends, create_backend, describe_backends,
                                   register_backend)

# built-in backends (their third-party SDKs are imported lazily, in setup())
from harmoni.services import assistant, azure_diarization, mock, robots  # noqa: F401,E402

__all__ = ["Result", "ServiceBackend", "available_backends", "create_backend", "describe_backends", "register_backend"]
