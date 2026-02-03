import json
import re
from collections import Counter
from typing import Dict, Iterable, List, Tuple

from .models import IntroInfo, Segment


SPEAKER_LINE_RE = re.compile(r"^(?P<speaker>.+?)\s+(?P<ts>\d{2}:\d{2}:\d{2})\s*$")
PAUSE_TAG_RE = re.compile(r"\[(?:pause|пауз[ау])\s*:?\s*(?P<duration>\d+(?:\.\d+)?)(?P<unit>ms|s)\]", re.IGNORECASE)
SFX_TAG_RE = re.compile(r"\[(?:sfx|sound|звук|sound effect)\s*:?\s*(?P<name>[^\]]+)\]", re.IGNORECASE)
STYLE_TAG_RE = re.compile(
    r"\[(?:style|стиль)\s*:?\s*(?P<style>[^\]]+)\](?P<content>.+?)\[/\s*(?:style|стиль)\s*\]",
    re.IGNORECASE | re.DOTALL,
)


def parse_speaker_segments(text: str) -> List[Segment]:
    segments: List[Segment] = []
    current_speaker = None
    current_ts = None
    buffer: List[str] = []

    def flush():
        nonlocal buffer
        if current_speaker and buffer:
            cleaned = "\n".join(line.strip() for line in buffer).strip()
            if cleaned:
                segments.append(Segment(current_speaker, current_ts, cleaned))
        buffer = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = SPEAKER_LINE_RE.match(line)
        if match:
            flush()
            current_speaker = match.group("speaker").strip()
            current_ts = match.group("ts")
        else:
            buffer.append(line)

    flush()
    return segments


def extract_speakers(segments: Iterable[Segment]) -> List[str]:
    seen = []
    for segment in segments:
        if segment.speaker not in seen:
            seen.append(segment.speaker)
    return seen


def detect_intro(segments: List[Segment]) -> IntroInfo:
    if not segments:
        return IntroInfo(text="", segment_count=0, reason="no segments")

    intro_candidates: List[Segment] = []
    total_words = 0
    short_sentence_hits = 0
    sentence_count = 0

    for segment in segments[:6]:
        sentences = re.split(r"[.!?…]+", segment.text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            continue
        intro_candidates.append(segment)
        for sentence in sentences:
            words = sentence.split()
            total_words += len(words)
            sentence_count += 1
            if len(words) <= 12:
                short_sentence_hits += 1

        if total_words > 140:
            break

    if not intro_candidates:
        return IntroInfo(text="", segment_count=0, reason="no intro candidates")

    short_ratio = short_sentence_hits / max(sentence_count, 1)
    is_intro = total_words <= 140 and short_ratio >= 0.6
    intro_text = " ".join(seg.text for seg in intro_candidates) if is_intro else ""
    reason = f"short_ratio={short_ratio:.2f}, total_words={total_words}"
    return IntroInfo(text=intro_text, segment_count=len(intro_candidates), reason=reason)


def normalize_text(text: str) -> str:
    normalized = text.replace("…", "...")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def apply_non_speech_and_style(text: str) -> str:
    def pause_repl(match: re.Match) -> str:
        duration = match.group("duration")
        unit = match.group("unit")
        return f"<break time=\"{duration}{unit}\"/>"

    def sfx_repl(match: re.Match) -> str:
        name = match.group("name").strip()
        return f"<say-as interpret-as=\"interjection\">{name}</say-as>"

    def style_repl(match: re.Match) -> str:
        style = match.group("style").strip().lower()
        content = match.group("content").strip()
        if style in {"whisper", "шепот", "шёпот"}:
            return f"<prosody volume=\"x-soft\">{content}</prosody>"
        if style in {"shout", "крик"}:
            return f"<prosody volume=\"x-loud\">{content}</prosody>"
        if style in {"fast", "быстро"}:
            return f"<prosody rate=\"fast\">{content}</prosody>"
        if style in {"slow", "медленно"}:
            return f"<prosody rate=\"slow\">{content}</prosody>"
        if style in {"soft", "тихо"}:
            return f"<prosody volume=\"soft\">{content}</prosody>"
        return content

    with_pause = PAUSE_TAG_RE.sub(pause_repl, text)
    with_sfx = SFX_TAG_RE.sub(sfx_repl, with_pause)
    with_style = STYLE_TAG_RE.sub(style_repl, with_sfx)
    return with_style


def build_ssml(
    segments: List[Segment],
    speaker_voice_map: Dict[str, str],
    output_language: str,
) -> str:
    parts: List[str] = ["<speak>"]
    for segment in segments:
        voice_name = speaker_voice_map.get(segment.speaker)
        voice_prefix = f"<voice name=\"{voice_name}\">" if voice_name else ""
        voice_suffix = "</voice>" if voice_name else ""
        content = apply_non_speech_and_style(normalize_text(segment.text))
        if output_language:
            content = f"<lang xml:lang=\"{output_language}\">{content}</lang>"
        parts.append(f"{voice_prefix}{content}{voice_suffix}<break time=\"400ms\"/>")
    parts.append("</speak>")
    return "".join(parts)


def estimate_chunking_need(ssml: str, max_chars: int) -> bool:
    return len(ssml) > max_chars


def split_segments_for_chunks(segments: List[Segment], max_chars: int) -> List[List[Segment]]:
    chunks: List[List[Segment]] = []
    current: List[Segment] = []
    current_len = 0

    for segment in segments:
        segment_len = len(segment.text)
        if current and current_len + segment_len > max_chars:
            chunks.append(current)
            current = []
            current_len = 0
        current.append(segment)
        current_len += segment_len

    if current:
        chunks.append(current)
    return chunks


def summarize_speakers(segments: List[Segment]) -> str:
    speakers = [segment.speaker for segment in segments]
    counts = Counter(speakers)
    return json.dumps(counts, ensure_ascii=False)