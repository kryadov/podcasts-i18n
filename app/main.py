import json
import os
import time
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from .processing import (
    build_ssml,
    detect_intro,
    estimate_chunking_need,
    extract_speakers,
    parse_speaker_segments,
    split_segments_for_chunks,
    summarize_speakers,
)
from .tts_client import GeminiTtsClient


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("APP_DATA_DIR", "/data"))
UPLOAD_DIR = DATA_DIR / "uploads"
ARTIFACT_DIR = DATA_DIR / "artifacts"
AUDIO_DIR = DATA_DIR / "audio"
MAX_SSML_CHARS = int(os.getenv("MAX_SSML_CHARS", "5000"))

app = FastAPI()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def ensure_dirs() -> None:
    for path in (UPLOAD_DIR, ARTIFACT_DIR, AUDIO_DIR):
        path.mkdir(parents=True, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/process")
async def process_file(
    file: UploadFile = File(...),
    input_language: str = Form("ru-RU"),
    output_language: str = Form("en-US"),
    sample_rate_hz: int = Form(24000),
    volume_gain_db: float = Form(0.0),
    voice_map_json: str = Form("{}"),
):
    ensure_dirs()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY is not configured")

    timestamp = int(time.time())
    filename = f"{timestamp}_{file.filename}"
    upload_path = UPLOAD_DIR / filename
    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read upload: {exc}")
    finally:
        await file.close()

    async def stream():
        logs: List[str] = []

        def log(message: str) -> str:
            logs.append(message)
            payload = {"type": "log", "message": message}
            return f"{json.dumps(payload, ensure_ascii=False)}\n"

        def error(message: str) -> str:
            payload = {"type": "error", "message": message, "logs": logs}
            return f"{json.dumps(payload, ensure_ascii=False)}\n"

        try:
            yield log("Reading upload...")
            upload_path.write_bytes(content)
            yield log(f"Saved upload to {upload_path}")

            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                yield error("Input file must be UTF-8 text")
                return

            yield log("Parsing speaker segments...")
            segments = parse_speaker_segments(text)
            if not segments:
                yield error("No speaker segments detected")
                return
            yield log(f"Detected {len(segments)} segments.")

            speakers = extract_speakers(segments)
            yield log(f"Detected speakers: {', '.join(speakers)}")
            yield log(f"Speaker counts: {summarize_speakers(segments)}")

            intro = detect_intro(segments)
            if intro.text:
                yield log(
                    f"Intro detected ({intro.segment_count} segments). {intro.reason}"
                )
                yield log(f"Intro preview: {intro.text[:180]}...")
            else:
                yield log(f"No intro detected. {intro.reason}")

            try:
                voice_map: Dict[str, str] = json.loads(voice_map_json)
            except json.JSONDecodeError:
                yield error("Invalid voice map JSON")
                return

            client = GeminiTtsClient(api_key=api_key)

            translated_segments = []
            total_segments = len(segments)
            for index, segment in enumerate(segments, start=1):
                yield log(
                    f"Translating segment {index}/{total_segments} ({segment.speaker})"
                )
                translated_text = client.translate_text(
                    segment.text, input_language, output_language
                )
                translated_segments.append(
                    segment.__class__(
                        segment.speaker, segment.timestamp, translated_text
                    )
                )

            yield log("Building SSML...")
            ssml = build_ssml(translated_segments, voice_map, output_language)
            artifact_path = ARTIFACT_DIR / f"{timestamp}_prepared.ssml.txt"
            artifact_path.write_text(ssml, encoding="utf-8")
            yield log(f"Saved prepared SSML to {artifact_path}")

            chunk_needed = estimate_chunking_need(ssml, MAX_SSML_CHARS)
            audio_paths: List[Path] = []

            if chunk_needed:
                yield log("Input exceeds SSML limit, chunking enabled.")
                chunk_segments = split_segments_for_chunks(
                    translated_segments, MAX_SSML_CHARS
                )
                total_chunks = len(chunk_segments)
                yield log(f"Preparing {total_chunks} audio chunks...")
                for index, chunk in enumerate(chunk_segments, start=1):
                    yield log(f"Synthesizing chunk {index}/{total_chunks}")
                    chunk_ssml = build_ssml(chunk, voice_map, output_language)
                    audio_bytes = client.synthesize_ssml(
                        chunk_ssml,
                        voice_name=None,
                        language_code=output_language,
                        sample_rate_hz=sample_rate_hz,
                        volume_gain_db=volume_gain_db,
                    )
                    part_path = AUDIO_DIR / f"{timestamp}_part_{index}.mp3"
                    part_path.write_bytes(audio_bytes)
                    audio_paths.append(part_path)
                yield log(f"Generated {len(audio_paths)} audio chunks.")
            else:
                yield log("Synthesizing audio...")
                audio_bytes = client.synthesize_ssml(
                    ssml,
                    voice_name=None,
                    language_code=output_language,
                    sample_rate_hz=sample_rate_hz,
                    volume_gain_db=volume_gain_db,
                )
                audio_path = AUDIO_DIR / f"{timestamp}.mp3"
                audio_path.write_bytes(audio_bytes)
                audio_paths.append(audio_path)
                yield log("Generated single audio file.")

            download_urls = [f"/download?path={path.name}" for path in audio_paths]
            payload = {
                "type": "result",
                "status": "ok",
                "artifact": str(artifact_path),
                "downloads": download_urls,
                "logs": logs,
            }
            yield f"{json.dumps(payload, ensure_ascii=False)}\n"
        except Exception as exc:
            yield error(f"Processing failed: {exc}")

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.get("/download")
def download(path: str):
    ensure_dirs()
    candidate = AUDIO_DIR / path
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(candidate, media_type="audio/mpeg", filename=candidate.name)