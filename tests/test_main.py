import json
from io import BytesIO

import pytest
from starlette.datastructures import UploadFile

from app import main


class DummyClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def translate_text(self, text: str, input_language: str, output_language: str):
        return text

    def synthesize_ssml(
        self,
        ssml: str,
        voice_name: str | None,
        language_code: str,
        sample_rate_hz: int,
        volume_gain_db: float,
    ) -> bytes:
        return b"audio"


@pytest.mark.anyio
async def test_process_file_streams_after_upload_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(main, "ARTIFACT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(main, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(main, "GeminiTtsClient", DummyClient)
    main.ensure_dirs()

    content = b"Speaker 1 00:00:01\nHello world"
    upload = UploadFile(filename="sample.txt", file=BytesIO(content))

    response = await main.process_file(
        file=upload,
        input_language="en-US",
        output_language="en-US",
        sample_rate_hz=24000,
        volume_gain_db=0.0,
        voice_map_json="{}",
    )

    await upload.close()

    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)

    body = "".join(
        chunk.decode("utf-8") if isinstance(chunk, (bytes, bytearray)) else chunk
        for chunk in chunks
    )
    payloads = [json.loads(line) for line in body.splitlines() if line.strip()]
    assert any(payload.get("type") == "result" for payload in payloads)