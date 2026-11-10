"""Shared pytest configuration for the HARMONI unit tests.

The unit tests in ``<package>/test/unit`` exercise the python logic of the HARMONI
services without a running ROS master, robots or cloud credentials. To do so this file:

1. adds the ``src`` folder of every HARMONI package to ``sys.path`` (no catkin build needed);
2. replaces ROS and third-party SDK modules (rospy, actionlib, message packages, openai,
   azure speech, furhat remote api, ...) with lightweight fakes.

The fakes are always installed, also inside the docker containers, so that unit tests are
deterministic and never talk to a real ROS master or cloud service. Integration tests that
need ROS are the ``rostest`` ``.test`` files of each package (see ``run_tests.sh``).
"""

import glob
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 1. Make every HARMONI python package importable from source
# ---------------------------------------------------------------------------
for src in sorted(glob.glob(os.path.join(ROOT, "harmoni_*", "*", "src"))):
    if src not in sys.path:
        sys.path.insert(0, src)


# ---------------------------------------------------------------------------
# 2. Fake modules
# ---------------------------------------------------------------------------
def _module(name, **attrs):
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    sys.modules[name] = module
    parent, _, child = name.rpartition(".")
    if parent and parent in sys.modules:
        setattr(sys.modules[parent], child, module)
    return module


class FakePublisher:
    """Records every message published, available in ``published``"""

    instances = []

    def __init__(self, topic, msg_type=None, queue_size=None, **kwargs):
        self.topic = topic
        self.msg_type = msg_type
        self.published = []
        FakePublisher.instances.append(self)

    def publish(self, msg):
        self.published.append(msg)


class FakeSubscriber:
    instances = []

    def __init__(self, topic, msg_type=None, callback=None, *args, **kwargs):
        self.topic = topic
        self.msg_type = msg_type
        self.callback = callback
        FakeSubscriber.instances.append(self)

    def unregister(self):
        pass


class FakeServiceProxy:
    """Callable service proxy; ``calls`` holds the arguments of every call"""

    def __init__(self, name, srv_type=None, *args, **kwargs):
        self.name = name
        self.calls = []
        self.side_effect = None

    def __call__(self, *args, **kwargs):
        self.calls.append(args)
        if self.side_effect is not None:
            raise self.side_effect
        return "done"


class FakeRate:
    def __init__(self, hz):
        self.hz = hz

    def sleep(self):
        pass


class _ROSException(Exception):
    pass


class _ServiceException(_ROSException):
    pass


class _ROSInterruptException(_ROSException):
    pass


_params = {}


def _get_param(name, default=KeyError):
    if name in _params:
        return _params[name]
    if default is KeyError:
        raise KeyError(name)
    return default


def _noop(*args, **kwargs):
    return None


_module(
    "rospy",
    Publisher=FakePublisher,
    Subscriber=FakeSubscriber,
    ServiceProxy=FakeServiceProxy,
    Service=_noop,
    Rate=FakeRate,
    sleep=_noop,
    spin=_noop,
    init_node=_noop,
    wait_for_service=_noop,
    is_shutdown=lambda: False,
    get_param=_get_param,
    set_param=lambda name, value: _params.__setitem__(name, value),
    loginfo=_noop,
    logwarn=_noop,
    logerr=_noop,
    logdebug=_noop,
    DEBUG=1,
    INFO=2,
    ROSException=_ROSException,
    ServiceException=_ServiceException,
    ROSInterruptException=_ROSInterruptException,
    Duration=lambda *args, **kwargs: types.SimpleNamespace(args=args),
    Time=types.SimpleNamespace(now=lambda: 0),
    get_rostime=lambda: 0,
)
_module("roslib", load_manifest=_noop)


class _RosPack:
    def get_path(self, package):
        matches = glob.glob(os.path.join(ROOT, "harmoni_*", package))
        if not matches:
            raise LookupError(package)
        return matches[0]


_module("rospkg", RosPack=_RosPack)


class _Msg:
    """Generic ROS message: keyword arguments become attributes"""

    def __init__(self, *args, **kwargs):
        if args:
            self.data = args[0]
        for key, value in kwargs.items():
            setattr(self, key, value)


def _msg_module(name, *msg_names, **extra):
    attrs = {msg: type(msg, (_Msg,), {}) for msg in msg_names}
    attrs.update(extra)
    return _module(name, **attrs)


class _GoalStatus(_Msg):
    PENDING = 0
    ACTIVE = 1
    PREEMPTED = 2
    SUCCEEDED = 3
    ABORTED = 4
    REJECTED = 5
    PREEMPTING = 6
    RECALLING = 7
    RECALLED = 8
    LOST = 9


_module("std_msgs")
_msg_module("std_msgs.msg", "String", "Bool", "Float32", "Int32", "Int16", "Header")
_module("actionlib_msgs")
_msg_module("actionlib_msgs.msg", "GoalStatusArray", GoalStatus=_GoalStatus)
_module("audio_common_msgs")
_msg_module("audio_common_msgs.msg", "AudioData")
_module("sensor_msgs")
_msg_module("sensor_msgs.msg", "Image", "CompressedImage")
_module("harmoni_common_msgs")
_msg_module(
    "harmoni_common_msgs.msg",
    "harmoniAction",
    "harmoniGoal",
    "harmoniFeedback",
    "harmoniResult",
)


class _ActionClient:
    def __init__(self, *args, **kwargs):
        pass


class _SimpleActionServer:
    def __init__(self, *args, **kwargs):
        pass


_actionlib = _module("actionlib", SimpleActionServer=_SimpleActionServer, ActionServer=_SimpleActionServer)
_actionlib.__path__ = []  # behave as a package so that submodules can be imported
_module("actionlib.server_goal_handle", ServerGoalHandle=_ActionClient)
_module(
    "actionlib.action_client",
    ActionClient=_ActionClient,
    CommState=types.SimpleNamespace(DONE=8),
    get_name_of_constant=lambda cls, value: str(value),
)

# Generated service messages of harmoni_speaker (built by catkin from srv/nao_speak.srv)
import harmoni_speaker  # noqa: E402  (real package from src)

_module("harmoni_speaker.srv", nao_speak=type("nao_speak", (_Msg,), {}))


# --- OpenAI -----------------------------------------------------------------
class _OpenAIError(Exception):
    def __init__(self, message="error", *args, **kwargs):
        super().__init__(message)


class _APIError(_OpenAIError):
    pass


class _APIConnectionError(_APIError):
    pass


class _RateLimitError(_APIError):
    pass


_module(
    "openai",
    OpenAI=_noop,
    AzureOpenAI=_noop,
    OpenAIError=_OpenAIError,
    APIError=_APIError,
    APIConnectionError=_APIConnectionError,
    RateLimitError=_RateLimitError,
)

# --- python-dotenv (only if not installed) ------------------------------------
try:  # pragma: no cover - depends on the environment
    import dotenv  # noqa: F401
except ImportError:  # pragma: no cover
    _module("dotenv", load_dotenv=_noop)

# --- Azure speech SDK ---------------------------------------------------------
_module("azure")
_module("azure.cognitiveservices")
_speechsdk = _module(
    "azure.cognitiveservices.speech",
    ResultReason=types.SimpleNamespace(RecognizedSpeech="RecognizedSpeech", NoMatch="NoMatch"),
    SessionEventArgs=object,
    SpeechRecognitionEventArgs=object,
    SpeechConfig=_noop,
    PropertyId=types.SimpleNamespace(),
)
_speechsdk.audio = types.SimpleNamespace(AudioConfig=_noop)
_speechsdk.transcription = types.SimpleNamespace(ConversationTranscriber=_noop)

# --- Furhat remote API ----------------------------------------------------------
_module("furhat_remote_api", FurhatRemoteAPI=_noop)

# --- six (used by the STT services) ---------------------------------------------
try:  # pragma: no cover
    import six  # noqa: F401
except ImportError:  # pragma: no cover
    import queue as _queue

    _module("six")
    _module("six.moves", queue=_queue)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_fakes():
    """Each test starts with no recorded publishers/subscribers/params"""
    FakePublisher.instances.clear()
    FakeSubscriber.instances.clear()
    _params.clear()
    yield


@pytest.fixture
def ros_params():
    """Dictionary backing ``rospy.get_param`` for the current test"""
    return _params


@pytest.fixture
def published():
    """Return the list of messages published on a topic (by exact topic name)"""

    def _published(topic):
        return [m for p in FakePublisher.instances if p.topic == topic for m in p.published]

    return _published
