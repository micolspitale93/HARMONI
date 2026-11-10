#!/usr/bin/env python3
"""Unit tests for the OpenAI/Azure Assistant service (harmoni_bot/assistant_service.py).

The OpenAI client is replaced by a fake, so no network access or API key is needed.
Run from the repository root with: python3 -m pytest harmoni_dialogues/harmoni_bot/test/unit
"""

import types

import openai
import pytest

from harmoni_common_lib.constants import DialogueNameSpace, State
from harmoni_bot import assistant_service
from harmoni_bot.assistant_service import FALLBACK_MESSAGE, AssistantOpenAIService

PARAMS = {
    "assistant_id": "asst_test",
    "service_id": "default",
    "participants": "Sarah, Jane, Alex",
    "num_speaker": 3,
    "scenario": "The topic of this group conversation is AI in society.",
}


def _event(name, text=None):
    data = None
    if text is not None:
        data = types.SimpleNamespace(content=[types.SimpleNamespace(text=types.SimpleNamespace(value=text))])
    return types.SimpleNamespace(event=name, data=data)


class FakeOpenAIClient:
    """Minimal stand-in for ``AzureOpenAI`` exposing the beta threads API"""

    def __init__(self, response_text='{"intervene": true}', error=None):
        self.created_messages = []
        self.runs = []
        self.response_text = response_text
        self.error = error
        client = self

        class Messages:
            def create(self, thread_id, role, content):
                client.created_messages.append((thread_id, role, content))

        class Runs:
            def create(self, **kwargs):
                client.runs.append(kwargs)
                if client.error is not None:
                    raise client.error
                return iter(
                    [
                        _event("thread.run.created"),
                        _event("thread.message.completed", client.response_text),
                        _event("thread.run.completed"),
                    ]
                )

        class Threads:
            messages = Messages()
            runs = Runs()

            def create(self):
                return types.SimpleNamespace(id="thread_123")

        self.beta = types.SimpleNamespace(threads=Threads())


@pytest.fixture
def service():
    s = AssistantOpenAIService("bot_default", dict(PARAMS))
    s.client = FakeOpenAIClient()
    s.thread_id = "thread_123"
    return s


# ---------------------------------------------------------------- parse_input
def test_parse_input_single_message():
    assert AssistantOpenAIService.parse_input("['*user* Sarah: Hello!']") == [
        {"role": "user", "content": "Sarah: Hello!"}
    ]


def test_parse_input_keeps_asterisks_inside_content():
    messages = AssistantOpenAIService.parse_input("['*user* I *really* like it']")
    assert messages[0]["content"] == "I *really* like it"


def test_parse_input_multiple_messages_and_roles():
    messages = AssistantOpenAIService.parse_input("['*system* be brief', '*user* hi']")
    assert [m["role"] for m in messages] == ["system", "user"]


def test_parse_input_accepts_quotes_produced_by_repr():
    payload = repr(["*user* Sarah: I'm not sure"])
    assert AssistantOpenAIService.parse_input(payload)[0]["content"] == "Sarah: I'm not sure"


@pytest.mark.parametrize("payload", ["", "not a list", "[]", "['no role here']", "['** empty role']"])
def test_parse_input_rejects_malformed_payloads(payload):
    with pytest.raises(ValueError):
        AssistantOpenAIService.parse_input(payload)


# ---------------------------------------------------------------- request
def test_request_success_returns_assistant_message(service, published):
    service.client.response_text = '{"intervene": true, "agent": "Mover", "response": "Hi all"}'
    result = service.request("['*user* Sarah: Hello!']")

    assert result == {"response": State.SUCCESS, "message": service.client.response_text}
    assert service.response_received is True
    # the last message is appended to the thread and a run is started on the assistant
    assert service.client.created_messages == [("thread_123", "user", "Sarah: Hello!")]
    run = service.client.runs[0]
    assert run["assistant_id"] == "asst_test"
    assert run["thread_id"] == "thread_123"
    assert run["stream"] is True
    # the response is also published on the bot topic
    assert published(DialogueNameSpace.bot.value + "default") == [service.client.response_text]


def test_request_sends_only_last_message(service):
    service.request("['*user* first', '*user* second']")
    assert service.client.created_messages == [("thread_123", "user", "second")]


@pytest.mark.parametrize(
    "error",
    [
        openai.APIError("api error"),
        openai.APIConnectionError("connection error"),
        openai.RateLimitError("rate limit"),
        RuntimeError("unexpected"),
    ],
)
def test_request_errors_release_the_server_with_fallback(service, error):
    service.client.error = error
    result = service.request("['*user* Hello']")
    assert result == {"response": State.FAILED, "message": FALLBACK_MESSAGE}
    # response_received must be True otherwise HarmoniServiceServer waits forever
    assert service.response_received is True


def test_request_with_malformed_input_fails_without_calling_openai(service):
    result = service.request("this is not a list")
    assert result["response"] == State.FAILED
    assert service.response_received is True
    assert service.client.runs == []


def test_request_before_setup_fails_gracefully():
    s = AssistantOpenAIService("bot_default", dict(PARAMS))
    result = s.request("['*user* Hello']")
    assert result["response"] == State.FAILED
    assert s.response_received is True


# ---------------------------------------------------------------- setup
def test_setup_oracle_creates_thread_and_json_schema(monkeypatch, published):
    monkeypatch.setattr(assistant_service, "AzureOpenAI", lambda **kwargs: FakeOpenAIClient())
    s = AssistantOpenAIService("bot_default", dict(PARAMS))
    s.setup_openai()

    assert s.thread_id == "thread_123"
    assert s.response_format["type"] == "json_schema"
    props = s.response_format["json_schema"]["schema"]["properties"]
    assert {"agent", "response", "intervene", "addressee"} <= set(props)
    assert "Sarah, Jane, Alex" in s.add_instructions
    assert published(DialogueNameSpace.bot.value + "default/thread_id") == ["thread_123"]


def test_setup_non_oracle_subscribes_to_shared_thread(monkeypatch):
    monkeypatch.setattr(assistant_service, "AzureOpenAI", lambda **kwargs: FakeOpenAIClient())
    params = dict(PARAMS, service_id="mover")
    s = AssistantOpenAIService("bot_mover", params)
    s.setup_openai()

    assert s.response_format == {"type": "text"}
    s.thread_callback(types.SimpleNamespace(data="thread_shared"))
    assert s.thread_id == "thread_shared"
