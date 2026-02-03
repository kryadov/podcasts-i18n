from app.processing import (
    apply_non_speech_and_style,
    build_ssml,
    detect_intro,
    estimate_chunking_need,
    parse_speaker_segments,
    split_segments_for_chunks,
)


def test_parse_speaker_segments():
    text = """Спикер 1 00:00:00

Hello there.

Спикер 2 00:00:05
General Kenobi."""
    segments = parse_speaker_segments(text)
    assert len(segments) == 2
    assert segments[0].speaker == "Спикер 1"
    assert segments[0].timestamp == "00:00:00"
    assert "Hello" in segments[0].text


def test_detect_intro_short_sentences():
    text = """Спикер 1 00:00:00
Short. Small. Tiny.

Спикер 2 00:00:03
Fast intro goes here."""
    segments = parse_speaker_segments(text)
    intro = detect_intro(segments)
    assert intro.segment_count > 0
    assert intro.text


def test_apply_non_speech_and_style():
    raw = "[pause 1s] Hello [sfx laughter] [style whisper]secret[/style]"
    processed = apply_non_speech_and_style(raw)
    assert "<break time=\"1s\"/>" in processed
    assert "interpret-as=\"interjection\"" in processed
    assert "<prosody volume=\"x-soft\">secret</prosody>" in processed


def test_build_ssml_and_chunking():
    text = """Speaker A 00:00:00
""" + ("word " * 200)
    segments = parse_speaker_segments(text)
    ssml = build_ssml(segments, {"Speaker A": "voice-a"}, "en-US")
    assert ssml.startswith("<speak>")
    assert "<voice name=\"voice-a\">" in ssml
    assert estimate_chunking_need(ssml, 100)
    chunks = split_segments_for_chunks(segments, 50)
    assert chunks