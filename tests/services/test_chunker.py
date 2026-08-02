"""Service tests for app/services/chunker.py: CHUNK_SIZE/CHUNK_OVERLAP
defaults and per-user UserPreferences overrides (CLAUDE.md Key Config).
"""
import pytest

pytestmark = pytest.mark.service


def test_chunk_text_respects_settings_defaults(monkeypatch):
    from app.services.chunker import ChunkerService
    from config.settings import settings

    monkeypatch.setattr(settings, "CHUNK_SIZE", 50)
    monkeypatch.setattr(settings, "CHUNK_OVERLAP", 0)

    text = "word " * 40  # ~200 chars
    chunks = ChunkerService.chunk_text(text)

    assert len(chunks) > 1
    assert all(len(c) <= 50 for c in chunks)


def test_chunk_text_uses_per_user_preference_override(db_session, monkeypatch):
    from app.services.chunker import ChunkerService
    from app.models.user_preferences import UserPreferences
    from config.settings import settings

    monkeypatch.setattr(settings, "CHUNK_SIZE", 1000)
    monkeypatch.setattr(settings, "CHUNK_OVERLAP", 100)
    db_session.add(UserPreferences(chunk_size=50, chunk_overlap=0))
    db_session.commit()

    text = "word " * 40
    chunks = ChunkerService.chunk_text(text)

    assert all(len(c) <= 50 for c in chunks)


def test_chunk_transcript_segments_merges_small_segments():
    from app.services.chunker import ChunkerService

    segments = [
        {"text": "Hello", "start": 0.0, "end": 1.0},
        {"text": "world", "start": 1.0, "end": 2.0},
        {"text": "this is a test", "start": 2.0, "end": 4.0},
    ]

    chunks = ChunkerService.chunk_transcript_segments(segments, chunk_size=1000)

    assert len(chunks) == 1
    assert "Hello" in chunks[0]["text"]
    assert chunks[0]["start"] == 0.0
    assert chunks[0]["end"] == 4.0
