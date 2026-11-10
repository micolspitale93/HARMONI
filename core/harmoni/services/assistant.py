"""LLM orchestrator of the group interaction: OpenAI Assistants API (Azure or OpenAI)."""

import ast
import os

from harmoni.tree.registry import Param
from harmoni.services.base import Result, ServiceBackend, load_env, register_backend

FALLBACK_MESSAGE = "Can you please repeat what you said?"

ORCHESTRATOR_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "agent_response",
        "schema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string"},
                "response": {"type": "string"},
                "intervene": {"type": "boolean"},
                "explanation": {"type": "string"},
                "addressee": {"type": "string"},
            },
        },
    },
}


def parse_input(input_text):
    """``"['*user* Sarah: Hello!']"`` -> ``[{"role": "user", "content": "Sarah: Hello!"}]``

    Raises:
        ValueError: if the payload is not a non-empty list of ``*role* content`` messages
    """
    try:
        messages = ast.literal_eval(input_text)
    except (ValueError, SyntaxError) as e:
        raise ValueError(f"Malformed assistant input: {input_text!r}") from e
    if isinstance(messages, str):
        messages = [messages]
    if not isinstance(messages, (list, tuple)) or len(messages) == 0:
        raise ValueError(f"Assistant input must be a non-empty list: {input_text!r}")
    parsed = []
    for message in messages:
        m = str(message).split("*", 2)
        if len(m) != 3 or m[1].strip() == "":
            raise ValueError(f"Malformed assistant message: {message!r}")
        parsed.append({"role": m[1].strip(), "content": m[2].strip()})
    return parsed


@register_backend(
    "assistant",
    kind="dialogue",
    actions=["REQUEST"],
    doc="LLM orchestrator: OpenAI Assistants API (Azure or OpenAI)",
    params={
        "assistant_id": Param(str, required=True, doc="id of the assistant (asst_...)"),
        "create_thread": Param(bool, doc="create the conversation thread (default: true for *_default)"),
        "participants": Param(str, default="", doc="comma separated names of the participants"),
        "num_speaker": Param(int, doc="number of participants (default: number of names)"),
        "scenario": Param(str, default="", doc="topic of the conversation"),
        "api_version": Param(str, default="2025-01-01-preview", doc="Azure OpenAI API version"),
    },
    requirements=["openai>=1.0", "python-dotenv"],
    credentials=["AZURE_OPENAI_API_ENDPOINT", "AZURE_OPENAI_API_KEY"],
)
class AssistantBackend(ServiceBackend):
    """Appends the last user message to an Assistants thread and runs the assistant.

    Params:

    - ``assistant_id`` (str): id of the assistant (``asst_...``)
    - ``create_thread`` (bool): True for the orchestrator, which creates the conversation thread and
      emits its id on the ``thread_id`` channel; other assistants receive it as input
    - ``participants`` (str), ``scenario`` (str): added to the instructions
    - ``num_speaker`` (int): number of participants (default: number of names in ``participants``)
    - ``api_version`` (str): Azure OpenAI API version

    Credentials: AZURE_OPENAI_API_ENDPOINT + AZURE_OPENAI_API_KEY (Azure), or OPENAI_API_KEY.
    """

    def __init__(self, service_id, params=None, emit=None):
        super().__init__(service_id, params, emit)
        p = self.params
        self.assistant_id = p.get("assistant_id", "")
        self.create_thread = bool(p.get("create_thread", service_id.endswith("_default")))
        participants = str(p.get("participants", ""))
        num_speaker = p.get("num_speaker") or len([n for n in participants.split(",") if n.strip()]) or 1
        self.instructions = (
            f"The name of the {num_speaker} university students are: {participants}. "
            f"The scenarios is the following:{p.get('scenario', '')}"
        )
        self.response_format = ORCHESTRATOR_RESPONSE_FORMAT if self.create_thread else {"type": "text"}
        self.thread_id = ""
        self.client = None

    def _make_client(self):
        load_env()
        endpoint = os.getenv("AZURE_OPENAI_API_ENDPOINT")
        if endpoint:
            from openai import AzureOpenAI

            return AzureOpenAI(api_version=self.params.get("api_version", "2025-01-01-preview"),
                               azure_endpoint=endpoint, api_key=os.getenv("AZURE_OPENAI_API_KEY"))
        from openai import OpenAI

        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"), organization=os.getenv("OPENAI_ORGANIZATION") or None)

    def setup(self):
        if self.client is None:
            self.client = self._make_client()
        if self.create_thread and not self.thread_id:
            self.thread_id = self.client.beta.threads.create().id
            self.emit("thread_id", self.thread_id)

    def on_input(self, channel, message):
        if channel == "thread_id":
            self.thread_id = message

    def request(self, data):
        try:
            last = parse_input(data)[-1]
        except ValueError as e:
            self.log.warning("%s", e)
            return Result(False, FALLBACK_MESSAGE)
        if self.client is None:
            self.setup()
        if not self.thread_id:
            return Result(False, FALLBACK_MESSAGE)
        try:
            self.client.beta.threads.messages.create(self.thread_id, role=last["role"], content=last["content"])
            run = self.client.beta.threads.runs.create(
                thread_id=self.thread_id,
                assistant_id=self.assistant_id,
                stream=True,
                response_format=self.response_format,
                additional_instructions=self.instructions,
            )
            answer = ""
            for event in run:
                if event.event == "thread.message.completed":
                    answer = event.data.content[0].text.value
        except Exception as e:  # noqa: BLE001 - API, connection and rate limit errors
            self.log.warning("assistant request failed: %s", e)
            return Result(False, FALLBACK_MESSAGE)
        return Result(True, answer)
