"""Mock backend: answers with configured responses (simulation, demos, tests)."""

import threading

from harmoni.services.base import Result, ServiceBackend, register_backend


@register_backend("mock")
class MockBackend(ServiceBackend):
    """Answers every action with the next configured response.

    Params:
        responses (list[str]): answers returned in order (an empty list echoes the payload)
        cycle (bool): restart from the first response at the end (default True)
        delay_s (float): simulated duration of each action (cancel interrupts it)
        ok (bool): outcome of the actions (default True)
    """

    def __init__(self, service_id, params=None, emit=None):
        super().__init__(service_id, params, emit)
        self.responses = list(self.params.get("responses") or [])
        self.cycle = bool(self.params.get("cycle", True))
        self.delay_s = float(self.params.get("delay_s", 0.0))
        self.ok = bool(self.params.get("ok", True))
        self.calls = []
        self._index = 0
        self._cancel = threading.Event()

    def _answer(self, kind, data):
        self.calls.append((kind, data))
        self.log.info("%s %s", kind, data)
        self._cancel.clear()
        if self.delay_s and self._cancel.wait(self.delay_s):
            return Result(False, "cancelled")
        if not self.responses:
            return Result(self.ok, data)
        if self._index >= len(self.responses):
            if not self.cycle:
                return Result(self.ok, self.responses[-1])
            self._index = 0
        message = self.responses[self._index]
        self._index += 1
        return Result(self.ok, message)

    def request(self, data):
        return self._answer("REQUEST", data)

    def do(self, data):
        return self._answer("DO", data)

    def cancel(self):
        self._cancel.set()
