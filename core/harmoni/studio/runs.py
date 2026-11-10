"""Running and monitoring trees from HARMONI Studio.

Two sources of tree snapshots, both pushed to the browser as server-sent events:

- **simulation**: the tree runs in this process (TreeRunner) with the backends of a service
  configuration, usually ``mock`` ones; nothing else is needed;
- **ros2**: Studio observes a tree running on ROS 2 (``/harmoni/tree/status``) and sends commands
  (``/harmoni/tree/command``); only available when rclpy is installed (e.g. in the ROS 2 container).

In both cases Studio only *observes* and *sends commands between ticks*: it is never part of the
control loop, and closing the browser does not affect the interaction.
"""

import json
import logging
import queue
import threading
import time
from typing import Optional

from harmoni.services import create_backend
from harmoni.tree import BuildContext, ClientRegistry, LocalServiceClient, TreeRunner


class EventBus:
    """Fan-out of events to the connected browsers (one queue per client)"""

    def __init__(self, history: int = 200):
        self._clients = []
        self._lock = threading.Lock()
        self.last = {}
        self.log = []
        self.history = history

    def subscribe(self):
        q = queue.Queue(maxsize=500)
        with self._lock:
            self._clients.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    def publish(self, event, data):
        if event == "log":
            self.log = (self.log + [data])[-self.history:]
        else:
            self.last[event] = data
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait((event, data))
            except queue.Full:  # slow browser: drop, never block the runner
                pass


class _BusLogHandler(logging.Handler):
    def __init__(self, bus):
        super().__init__(logging.INFO)
        self.bus = bus

    def emit(self, record):
        try:
            self.bus.publish("log", {"time": record.created, "source": record.name.replace("harmoni.", ""),
                                     "level": record.levelname.lower(), "message": record.getMessage()})
        except Exception:  # noqa: BLE001
            pass


class SimulationSession:
    """A tree running in-process with the backends of a configuration"""

    def __init__(self, bus: EventBus, tree_path, services: dict, variables=None, period_s: float = 0.2, cast=None):
        self.bus = bus
        self.clients = ClientRegistry({
            service_id: LocalServiceClient(create_backend(dict(params).pop("backend"), service_id,
                                                          {k: v for k, v in params.items() if k != "backend"}))
            for service_id, params in services.items()
        }, factory=self._missing_service)
        self.runner = TreeRunner(str(tree_path), BuildContext(client_for=self.clients), variables, period_s, cast=cast)
        self.runner.observers.append(lambda snapshot: bus.publish("snapshot", dict(snapshot, source="simulation")))
        self._stop = threading.Event()
        self._thread = None
        self._handler = _BusLogHandler(bus)

    @staticmethod
    def _missing_service(service_id):
        raise KeyError(f"service '{service_id}' is not in the configuration")

    def start(self):
        for backend_client in self.clients._clients.values():
            backend_client.backend.setup()
        logging.getLogger("harmoni").addHandler(self._handler)
        logging.getLogger("harmoni").setLevel(logging.INFO)
        self.runner.load()
        self._thread = threading.Thread(target=self._loop, name="studio-simulation", daemon=True)
        self._thread.start()

    def _loop(self):
        try:
            while not self._stop.is_set():
                snapshot = self.runner.step()
                if snapshot["state"] in ("finished", "error", "stopped"):
                    break
                self._stop.wait(self.runner.period_s)
        finally:
            self.bus.publish("state", {"running": False, "state": self.runner.state, "error": self.runner.error})
            logging.getLogger("harmoni").removeHandler(self._handler)
            self.clients.shutdown()

    @property
    def alive(self):
        return self._thread is not None and self._thread.is_alive()

    def command(self, command):
        self.runner.command(command)

    def stop(self):
        self.runner.command("stop")
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)


class Ros2Bridge:
    """Observe and command a tree running on ROS 2 (requires rclpy)"""

    STATUS = "/harmoni/tree/status"
    COMMAND = "/harmoni/tree/command"

    def __init__(self, bus: EventBus):
        self.bus = bus
        self.node = None
        self._thread = None

    @staticmethod
    def available():
        try:
            import rclpy  # noqa: F401
            import std_msgs.msg  # noqa: F401
        except ImportError:
            return False
        return True

    def start(self):
        if self.node is not None:
            return
        import rclpy
        from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
        from std_msgs.msg import String

        if not rclpy.ok():
            rclpy.init()
        self.node = rclpy.create_node("harmoni_studio")
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)
        self.node.create_subscription(String, self.STATUS, self._on_status, qos)
        self._publisher = self.node.create_publisher(String, self.COMMAND, 10)
        self._String = String
        self._thread = threading.Thread(target=rclpy.spin, args=(self.node,), name="studio-ros2", daemon=True)
        self._thread.start()

    def _on_status(self, msg):
        try:
            self.bus.publish("snapshot", dict(json.loads(msg.data), source="ros2"))
        except ValueError:
            pass

    def command(self, command):
        if self.node is None:
            raise RuntimeError("not connected to ROS 2")
        self._publisher.publish(self._String(data=command))


class RunManager:
    def __init__(self, workspace, bus: EventBus):
        self.workspace = workspace
        self.bus = bus
        self.session: Optional[SimulationSession] = None
        self.ros2 = Ros2Bridge(bus)
        self.mode = "simulation"

    def start_simulation(self, tree, config, variables=None, period_s=0.2, cast=None):
        """Run a tree with the services, variables and cast of a configuration, plus run-time overrides"""
        self.stop()
        tree_path = self.workspace.tree_path(tree)
        if not tree_path.is_file():
            raise FileNotFoundError(tree)
        checked = self.workspace.read_config(config)
        services = (checked["parsed"] or {}).get("services") or {}
        errors = [i for i in checked["issues"] if i["level"] == "error" and i["path"].startswith("services")]
        if errors:
            raise ValueError("; ".join(f"{i['path']}: {i['message']}" for i in errors))
        effective = self.workspace.run_defaults(tree, config, cast, variables)
        self.bus.log = []
        self.bus.last.pop("snapshot", None)  # do not show the previous run
        self.session = SimulationSession(self.bus, tree_path, services, effective["config_variables"], float(period_s),
                                         cast=effective["config_cast"])
        self.session.start()
        self.mode = "simulation"
        self.bus.publish("state", {"running": True, "mode": "simulation", "tree": tree, "config": config})
        return {"running": True}

    def connect_ros2(self):
        if not self.ros2.available():
            raise RuntimeError("rclpy is not available: run Studio in the ROS 2 container (./harmoni.sh ros2 studio)")
        self.stop()
        self.ros2.start()
        self.mode = "ros2"
        self.bus.publish("state", {"running": True, "mode": "ros2"})
        return {"running": True, "mode": "ros2"}

    def command(self, command):
        if self.mode == "ros2":
            self.ros2.command(command)
        elif self.session is not None and self.session.alive:
            self.session.command(command)
        else:
            raise RuntimeError("nothing is running")

    def stop(self):
        if self.session is not None:
            self.session.stop()
            self.session = None
        self.mode = "simulation"

    def state(self):
        return {
            "mode": self.mode,
            "running": bool(self.session and self.session.alive) or self.mode == "ros2",
            "ros2_available": self.ros2.available(),
            "snapshot": self.bus.last.get("snapshot"),
            "log": self.bus.log[-100:],
        }
