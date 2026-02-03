from typing import Optional

from google.cloud import texttospeech
import google.generativeai as genai


class GeminiTtsClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-pro-preview-tts",
    ) -> None:
        self.api_key = api_key
        self.model = model
        genai.configure(api_key=api_key)
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
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.2},
            )
        except Exception as exc:
            raise RuntimeError(f"Gemini translation request failed: {exc}") from exc

        translated = (response.text or "").strip()
        if not translated:
            raise RuntimeError("Gemini returned empty translation.")
        return translated

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