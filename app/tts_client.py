from typing import Optional

try:
    from google.cloud import texttospeech
except (ModuleNotFoundError, ImportError):  # pragma: no cover - handled by dependency install
    texttospeech = None

try:
    from google import genai
except (ModuleNotFoundError, ImportError):  # pragma: no cover - handled by dependency install
    genai = None


class GeminiTtsClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-pro",
    ) -> None:
        if genai is None or texttospeech is None:
            raise RuntimeError(
                "Missing Google client libraries. Install "
                "google-genai and google-cloud-texttospeech."
            )
        self.api_key = api_key
        self.model = model
        self._genai_client = genai.Client(api_key=api_key)
        self._tts_client = texttospeech.TextToSpeechClient(
            client_options={"api_key": api_key}
        )

    def translate_text(
        self,
        text: str,
        input_language: str,
        output_language: str,
        timeout: float = 60.0,
    ) -> str:
        if input_language.lower() == output_language.lower():
            return text

        prompt = (
            "Translate the following text from "
            f"{input_language} to {output_language}. "
            "Return only the translated text without commentary.\n\n"
            f"{text}"
        )

        try:
            config = {"temperature": 0.2}
            if hasattr(genai, "types") and hasattr(
                genai.types, "GenerateContentConfig"
            ):
                config = genai.types.GenerateContentConfig(temperature=0.2)
            if hasattr(self._genai_client, "models") and hasattr(
                self._genai_client.models, "generate_content"
            ):
                response = self._genai_client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
            else:
                response = self._genai_client.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
        except Exception as exc:
            raise RuntimeError(f"Gemini translation request failed: {exc}") from exc

        translated = self._extract_text(response).strip()
        if not translated:
            raise RuntimeError("Gemini returned empty translation.")
        return translated

    @staticmethod
    def _extract_text(response) -> str:
        if response is None:
            return ""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            text = response.get("text")
            if text:
                return str(text)
        text = getattr(response, "text", None)
        if text:
            return str(text)
        candidates = getattr(response, "candidates", None)
        if not candidates:
            return ""
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue
            parts = getattr(content, "parts", None)
            if not parts:
                continue
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    return str(part_text)
        return ""

    def synthesize_ssml(
        self,
        ssml: str,
        voice_name: Optional[str],
        language_code: str,
        sample_rate_hz: int,
        volume_gain_db: float,
        timeout: float = 120.0,
    ) -> bytes:
        input_config = texttospeech.SynthesisInput(ssml=ssml)
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name if voice_name else None,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            sample_rate_hertz=sample_rate_hz,
            volume_gain_db=volume_gain_db,
        )

        try:
            response = self._tts_client.synthesize_speech(
                input=input_config,
                voice=voice_params,
                audio_config=audio_config,
                timeout=timeout,
            )
        except Exception as exc:
            raise RuntimeError(f"Gemini TTS request failed: {exc}") from exc

        audio_content = response.audio_content
        if not audio_content:
            raise RuntimeError("No audio content returned from TTS API.")
        return audio_content