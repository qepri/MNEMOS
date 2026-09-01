"""Service tests for rejoining chunks: ChunkerService.strip_overlap /
merge_chunks and SummaryService._batch_text.

chunk_text() repeats CHUNK_OVERLAP characters between consecutive chunks on
purpose. Anything that stitches chunks back into continuous text has to drop
that repetition, or the seam is fed to the model twice.
"""
import pytest

pytestmark = pytest.mark.service


class _FakeChunk:
    def __init__(self, content, page_number=None):
        self.content = content
        self.page_number = page_number


def test_strip_overlap_removes_the_repeated_seam(monkeypatch):
    from app.services.chunker import ChunkerService
    from config.settings import settings

    monkeypatch.setattr(settings, "CHUNK_OVERLAP", 100)

    previous = "the operator must wear hearing protection at all times"
    following = "wear hearing protection at all times inside the plant"

    assert ChunkerService.strip_overlap(previous, following) == " inside the plant"


def test_strip_overlap_ignores_a_short_accidental_match(monkeypatch):
    from app.services.chunker import ChunkerService
    from config.settings import settings

    monkeypatch.setattr(settings, "CHUNK_OVERLAP", 100)

    # "ion" ends one and starts the other, but it is not the overlap.
    previous = "hearing protection"
    following = "ionizing radiation sources must be logged"

    assert ChunkerService.strip_overlap(previous, following) == following


def test_merge_chunks_round_trips_chunk_text(monkeypatch):
    from app.services.chunker import ChunkerService
    from config.settings import settings

    monkeypatch.setattr(settings, "CHUNK_SIZE", 120)
    monkeypatch.setattr(settings, "CHUNK_OVERLAP", 40)

    original = " ".join(f"clause{i:03d}" for i in range(120))
    chunks = ChunkerService.chunk_text(original)
    assert len(chunks) > 3, "the fixture must actually be split"

    merged = ChunkerService.merge_chunks(chunks, separator=" ")

    # No clause is lost, and none is duplicated by the overlap.
    for i in range(120):
        assert merged.count(f"clause{i:03d}") == 1


def test_batch_text_does_not_repeat_the_overlap(monkeypatch):
    from app.services.summary_service import SummaryService
    from config.settings import settings

    monkeypatch.setattr(settings, "CHUNK_OVERLAP", 60)

    chunks = [
        _FakeChunk("noise exposure above 80 dB requires a hearing programme", page_number=4),
        _FakeChunk("requires a hearing programme reviewed once a year", page_number=4),
    ]

    text = SummaryService._batch_text(chunks)

    assert text.count("requires a hearing programme") == 1
    assert "reviewed once a year" in text


def test_batch_text_marks_each_page_once(monkeypatch):
    from app.services.summary_service import SummaryService
    from config.settings import settings

    monkeypatch.setattr(settings, "CHUNK_OVERLAP", 0)

    chunks = [
        _FakeChunk("first clause", page_number=7),
        _FakeChunk("second clause", page_number=7),
        _FakeChunk("third clause", page_number=8),
    ]

    text = SummaryService._batch_text(chunks)

    assert text.count("[Page 7]") == 1
    assert text.count("[Page 8]") == 1
    assert "first clause" in text and "third clause" in text


def test_batch_text_survives_chunks_without_a_page(monkeypatch):
    from app.services.summary_service import SummaryService
    from config.settings import settings

    monkeypatch.setattr(settings, "CHUNK_OVERLAP", 0)

    text = SummaryService._batch_text([_FakeChunk("a clause with no page", page_number=None)])

    assert "[Page ?]" in text
