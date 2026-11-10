"""ROS2 implementation of the core ServiceClient: sends Harmoni action goals."""

from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup

from harmoni.tree.clients import CallStatus, ServiceCall, ServiceClient, as_action
from harmoni_interfaces.action import Harmoni


class RosServiceCall(ServiceCall):
    """Tracks one goal; updated from the executor threads, polled by the tree leaf"""

    def __init__(self, action_client, goal):
        super().__init__()
        self._goal_handle = None
        self._cancel_requested = False
        action_client.send_goal_async(goal).add_done_callback(self._on_goal_response)

    def _on_goal_response(self, future):
        try:
            goal_handle = future.result()
        except Exception as e:  # noqa: BLE001
            self.message, self.status = f"goal not sent: {e}", CallStatus.FAILED
            return
        if not goal_handle.accepted:
            self.message, self.status = "goal rejected", CallStatus.FAILED
            return
        self._goal_handle = goal_handle
        if self._cancel_requested:
            goal_handle.cancel_goal_async()
            return
        goal_handle.get_result_async().add_done_callback(self._on_result)

    def _on_result(self, future):
        if self.status == CallStatus.CANCELLED:
            return
        try:
            response = future.result()
        except Exception as e:  # noqa: BLE001
            self.message, self.status = f"no result: {e}", CallStatus.FAILED
            return
        if response.status == GoalStatus.STATUS_SUCCEEDED:
            self.ok = bool(response.result.do_action)
            self.message = response.result.message
            self.status = CallStatus.SUCCEEDED
        else:
            self.message, self.status = f"goal ended with status {response.status}", CallStatus.FAILED

    def cancel(self):
        if self.status != CallStatus.RUNNING:
            return
        self.status = CallStatus.CANCELLED
        if self._goal_handle is not None:
            self._goal_handle.cancel_goal_async()
        else:
            self._cancel_requested = True


class _FailedCall(ServiceCall):
    def __init__(self, message):
        super().__init__()
        self.status, self.message = CallStatus.FAILED, message

    def cancel(self):
        pass


class RosServiceClient(ServiceClient):
    def __init__(self, node, service_id):
        self.service_id = service_id
        self.action_client = ActionClient(node, Harmoni, service_id, callback_group=ReentrantCallbackGroup())

    def is_ready(self):
        return self.action_client.server_is_ready()

    def send(self, action, data):
        if not self.action_client.server_is_ready():
            return _FailedCall(f"service '{self.service_id}' is not available")
        goal = Harmoni.Goal()
        goal.action_type = int(as_action(action))
        goal.optional_data = data or ""
        return RosServiceCall(self.action_client, goal)
