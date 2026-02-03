from types import SimpleNamespace

from app import tts_client


class DummyResponse:
    def __init__(self, text: str):
        self.text = text


class DummyModels:
    def __init__(self, parent):
        self.parent = parent

    def generate_content(self, model, contents, config=None):
        self.parent.calls.append((model, contents, config))
        return DummyResponse("Hola")


class DummyGenAIClient:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.calls = []
        self.models = DummyModels(self)


class DummyGenAI:
    class types:
        class GenerateContentConfig:
            def __init__(self, temperature: float):
                self.temperature = temperature

    def __init__(self):
        self.last_client = None

    def Client(self, api_key=None, **kwargs):
        self.last_client = DummyGenAIClient(api_key=api_key)
        return self.last_client


class DummyTtsResponse:
    def __init__(self, audio_content: bytes):
        self.audio_content = audio_content


class DummyTtsClient:
    def __init__(self, client_options=None):
        self.client_options = client_options
        self.calls = []

    def synthesize_speech(self, input, voice, audio_config, timeout=None):
        self.calls.append((input, voice, audio_config, timeout))
        return DummyTtsResponse(b"audio")


class DummyTextToSpeechModule:
    AudioEncoding = SimpleNamespace(MP3="MP3")

    class SynthesisInput:
        def __init__(self, ssml: str):
            self.ssml = ssml

    class VoiceSelectionParams:
        def __init__(self, language_code: str, name=None):
            self.language_code = language_code
            self.name = name

    class AudioConfig:
        def __init__(self, audio_encoding, sample_rate_hertz: int, volume_gain_db: float):
            self.audio_encoding = audio_encoding
            self.sample_rate_hertz = sample_rate_hertz
            self.volume_gain_db = volume_gain_db

    def __init__(self):
        self.last_client = None

    def TextToSpeechClient(self, client_options=None):
        self.last_client = DummyTtsClient(client_options=client_options)
        return self.last_client


def setup_clients(monkeypatch):
    dummy_genai = DummyGenAI()
    dummy_tts = DummyTextToSpeechModule()
    monkeypatch.setattr(tts_client, "genai", dummy_genai)
    monkeypatch.setattr(tts_client, "texttospeech", dummy_tts)
    return dummy_genai, dummy_tts


def test_translate_text_uses_generative_model(monkeypatch):
    dummy_genai, _ = setup_clients(monkeypatch)
    client = tts_client.GeminiTtsClient(api_key="test-key", model="gemini-test")

    translated = client.translate_text("Hello", "en", "es")

    assert translated == "Hola"
    assert dummy_genai.last_client.api_key == "test-key"
    model, prompt, config = dummy_genai.last_client.calls[0]
    assert model == "gemini-test"
    assert prompt.startswith("Translate the following text")
    if hasattr(config, "temperature"):
        assert config.temperature == 0.2
    else:
        assert config == {"temperature": 0.2}


def test_synthesize_ssml_uses_texttospeech_client(monkeypatch):
    _, dummy_tts = setup_clients(monkeypatch)
    client = tts_client.GeminiTtsClient(api_key="test-key")

    audio = client.synthesize_ssml(
        "<speak>Hello</speak>",
        voice_name="voice-a",
        language_code="en-US",
        sample_rate_hz=24000,
        volume_gain_db=0.5,
        timeout=10.0,
    )

    assert audio == b"audio"
    assert dummy_tts.last_client.client_options == {"api_key": "test-key"}
    input_config, voice_params, audio_config, timeout = dummy_tts.last_client.calls[0]
    assert input_config.ssml == "<speak>Hello</speak>"
    assert voice_params.language_code == "en-US"
    assert voice_params.name == "voice-a"
    assert audio_config.sample_rate_hertz == 24000
    assert audio_config.volume_gain_db == 0.5
    assert timeout == 10.0