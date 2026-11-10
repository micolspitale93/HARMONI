"""Speech-to-text with speaker diarization (Azure ConversationTranscriber)."""

import os
import threading
import time

from harmoni.tree.registry import Param
from harmoni.services.base import Result, ServiceBackend, load_env, register_backend

SILENCE_MESSAGE = "No one is talking. Please initiate a question to reignite the conversation."


@register_backend(
    "azure_diarization",
    kind="detector",
    actions=["REQUEST"],
    doc="Speech-to-text with speaker diarization (Azure Speech)",
    params={
        "language_id": Param(str, default="en-US"),
        "names": Param(str, default="", doc="participants in the order Azure detects them (Guest-1, ...)"),
        "max_silence": Param(float, default=10.0, doc="seconds without speech before the silence message"),
        "max_wait_s": Param(float, default=120.0, doc="upper bound of a request"),
        "device_name": Param(str, doc="ALSA microphone, e.g. hw:1,0 (default: the default microphone)"),
        "silence_message": Param(str, default=SILENCE_MESSAGE, doc="returned when nobody talks for max_silence"),
    },
    requirements=["azure-cognitiveservices-speech", "python-dotenv"],
    credentials=["MICROSOFT_SPEECH_KEY", "MICROSOFT_SPEECH_REGION"],
)
class AzureDiarizationBackend(ServiceBackend):
    """REQUEST returns the next utterance as ``"<speaker name>: <text>"``.

    Params:
        language_id (str): e.g. en-US
        names (str): participants in the order Azure detects them (Guest-1, Guest-2, ...)
        max_silence (float): seconds without speech after which SILENCE_MESSAGE is returned
        max_wait_s (float): upper bound of a request, even if people keep talking without pause

    Credentials: MICROSOFT_SPEECH_KEY, MICROSOFT_SPEECH_REGION.
    """

    def __init__(self, service_id, params=None, emit=None, clock=time.monotonic):
        super().__init__(service_id, params, emit)
        p = self.params
        self.language = p.get("language_id", "en-US")
        self.names = [n.strip() for n in str(p.get("names", "")).split(",")]
        self.max_silence = float(p.get("max_silence", 10))
        self.max_wait_s = float(p.get("max_wait_s", 120))
        self.device_name = p.get("device_name") or None
        self.silence_message = p.get("silence_message") or SILENCE_MESSAGE
        self.clock = clock
        self.transcriber = None
        self._done = threading.Event()
        self._cancelled = threading.Event()
        self._result = ""
        self._last_speech = 0.0

    def speaker_name(self, speaker_id):
        if not speaker_id:
            return "Unknown"
        try:
            index = int(str(speaker_id).split("-")[-1]) - 1
        except ValueError:
            return speaker_id
        if 0 <= index < len(self.names) and self.names[index]:
            return self.names[index]
        return speaker_id

    # ------------------------------------------------------------- SDK callbacks
    def on_transcribing(self, evt):
        self._last_speech = self.clock()

    def on_transcribed(self, evt):
        result = evt.result
        if getattr(result.reason, "name", str(result.reason)).endswith("RecognizedSpeech") and result.text:
            speaker = self.speaker_name(result.speaker_id)
            # single quotes are removed because the text is embedded in a python literal downstream
            self._result = f"{speaker}: {result.text}".replace("'", " ")
            self._done.set()

    # ------------------------------------------------------------- lifecycle
    def setup(self):
        if self.transcriber is not None:
            return
        load_env()
        import azure.cognitiveservices.speech as speechsdk

        config = speechsdk.SpeechConfig(subscription=os.getenv("MICROSOFT_SPEECH_KEY"),
                                        region=os.getenv("MICROSOFT_SPEECH_REGION"))
        config.speech_recognition_language = self.language
        config.set_property(speechsdk.PropertyId.SpeechServiceResponse_DiarizeIntermediateResults, "true")
        if self.device_name:
            audio = speechsdk.audio.AudioConfig(device_name=self.device_name)
        else:
            audio = speechsdk.audio.AudioConfig(use_default_microphone=True)
        self.transcriber = speechsdk.transcription.ConversationTranscriber(speech_config=config, audio_config=audio)
        self.transcriber.transcribing.connect(self.on_transcribing)
        self.transcriber.transcribed.connect(self.on_transcribed)

    @staticmethod
    def _wait(future):
        if future is not None and hasattr(future, "get"):
            future.get()

    def request(self, data=""):
        if self.transcriber is None:
            self.setup()
        self._done.clear()
        self._cancelled.clear()
        self._result = ""
        start = self._last_speech = self.clock()
        self._wait(self.transcriber.start_transcribing_async())
        try:
            while not self._done.wait(0.1):
                if self._cancelled.is_set():
                    return Result(False, "cancelled")
                now = self.clock()
                if now - self._last_speech > self.max_silence or now - start > self.max_wait_s:
                    self._result = self.silence_message
                    break
        finally:
            self._wait(self.transcriber.stop_transcribing_async())
        return Result(True, self._result)

    def cancel(self):
        self._cancelled.set()
