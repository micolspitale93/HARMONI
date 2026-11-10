"""Runs a HARMONI tree, independently of any UI and of the middleware.

Design rules (so that authoring/monitoring tools never sit in the control loop):

- the runner ticks the tree on its own clock (``period_s``);
- tools send *commands* (``pause``, ``resume``, ``stop``, ``reload``) that are queued and
  applied between two ticks, never during one;
- after every tick the runner hands a JSON *snapshot* to observers (e.g. a ROS2 publisher);
  an observer that raises is logged and ignored.

The ROS2 node ``harmoni_nodes/tree_node.py`` drives this class from a ROS timer; the
``python -m harmoni.tree simulate`` command drives it from a plain loop.
"""

import logging
import queue
import time
from typing import Any, Callable, Dict, List, Optional

import py_trees

from harmoni.tree.builder import BuildContext, build_tree
from harmoni.tree.registry import normalize_key
from harmoni.tree.snapshot import blackboard_snapshot, node_snapshot

log = logging.getLogger("harmoni.runner")

COMMANDS = ("pause", "resume", "stop", "reload")


class TreeRunner:
    """
    Args:
        source: tree file path (or dict)
        context: :class:`BuildContext` giving access to the services
        variables: overrides of the tree variables
        period_s: time between ticks used by :meth:`run`
        blackboard_prefixes: blackboard keys included in snapshots (None = all)
    """

    def __init__(self, source, context: Optional[BuildContext] = None, variables: Optional[Dict[str, Any]] = None,
                 period_s: float = 0.5, blackboard_prefixes=None):
        self.source = source
        self.context = context or BuildContext()
        self.variables = dict(variables or {})
        self.period_s = period_s
        self.blackboard_prefixes = blackboard_prefixes
        self.observers: List[Callable[[dict], None]] = []
        self.state = "idle"  # idle | running | paused | stopped | finished | error
        self.error = ""
        self.warnings = []
        self.tree = None
        self.spec = None
        self.stop_key = None
        self._commands = queue.Queue()

    # ------------------------------------------------------------------ loading
    def load(self):
        """(Re)build the tree from its file. Raises TreeSpecError on invalid trees."""
        if self.tree is not None:
            self.tree.interrupt()
            self.tree.shutdown()
        py_trees.blackboard.Blackboard.clear()
        root, self.spec, self.warnings = build_tree(self.source, self.context, self.variables)
        for warning in self.warnings:
            log.warning("%s", warning)
        self.stop_key = normalize_key(self.spec["stop_when"]) if self.spec.get("stop_when") else None
        self.tree = py_trees.trees.BehaviourTree(root)
        # no timeout: py_trees implements it with signals, which only work in the main thread,
        # and the runner is loaded from worker threads (ROS 2 executor, Studio)
        self.tree.setup()
        self.state = "running"
        self.error = ""
        return self

    # ------------------------------------------------------------------ commands
    def command(self, command: str):
        """Queue a command; thread safe, applied before the next tick"""
        command = str(command).strip().lower()
        if command not in COMMANDS:
            raise ValueError(f"unknown command '{command}' (use one of {', '.join(COMMANDS)})")
        self._commands.put(command)

    def _apply_commands(self):
        while not self._commands.empty():
            command = self._commands.get_nowait()
            log.info("command: %s", command)
            if command == "pause" and self.state == "running":
                self.state = "paused"
            elif command == "resume" and self.state == "paused":
                self.state = "running"
            elif command == "stop":
                self.stop()
            elif command == "reload":
                try:
                    self.load()
                except Exception as e:  # noqa: BLE001 - invalid edit: keep the runner alive
                    self.state, self.error = "error", str(e)
                    log.error("reload failed: %s", e)

    # ------------------------------------------------------------------ ticking
    def step(self) -> dict:
        """Apply pending commands, tick once if running, notify observers. Returns the snapshot."""
        if self.tree is None and self.state == "idle":
            self.load()
        self._apply_commands()
        if self.state == "running":
            try:
                self.tree.tick()
            except Exception as e:  # noqa: BLE001 - a broken leaf must not kill the host process
                log.exception("tick failed")
                self.state, self.error = "error", f"{type(e).__name__}: {e}"
                self.tree.interrupt()
            else:
                if self.stop_key and self._stop_requested():
                    self.state = "finished"
        snapshot = self.snapshot()
        for observer in list(self.observers):
            try:
                observer(snapshot)
            except Exception:  # noqa: BLE001
                log.exception("observer failed (ignored)")
        return snapshot

    def _stop_requested(self):
        if self.tree.root.status == py_trees.common.Status.RUNNING:
            return False
        return bool(py_trees.blackboard.Blackboard.storage.get(self.stop_key, False))

    def run(self, max_ticks: Optional[int] = None, sleep=time.sleep):
        """Tick until stopped/finished/error (or ``max_ticks``)"""
        ticks = 0
        while True:
            self.step()
            ticks += 1
            if self.state in ("stopped", "finished", "error"):
                break
            if max_ticks is not None and ticks >= max_ticks:
                break
            sleep(self.period_s)
        return self.state

    def stop(self):
        if self.tree is not None:
            self.tree.interrupt()
        self.state = "stopped"

    def shutdown(self):
        self.stop()
        if self.tree is not None:
            self.tree.shutdown()

    # ------------------------------------------------------------------ monitoring
    def snapshot(self) -> dict:
        return {
            "tree": (self.spec or {}).get("name", ""),
            "state": self.state,
            "error": self.error,
            "tick": self.tree.count if self.tree else 0,
            "time": time.time(),
            "root": node_snapshot(self.tree.root) if self.tree else None,
            "blackboard": blackboard_snapshot(self.blackboard_prefixes),
        }
