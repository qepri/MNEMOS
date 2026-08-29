"""Pipeline tests for extract_text_file: plain-text documents (.txt, .md).

A text file needs no parsing step — the file already is the content — so the
extractor's whole job is reading it safely and handing it to the chunker.
"""
import pytest

pytestmark = pytest.mark.pipeline


class _Doc:
    """Minimal stand-in: the extractor only reads file_path."""
    def __init__(self, file_path):
        self.file_path = file_path


def _escribir(tmp_path, monkeypatch, nombre, contenido, encoding='utf-8'):
    from config.settings import settings
    monkeypatch.setattr(settings, "UPLOAD_FOLDER", str(tmp_path))
    ruta = tmp_path / nombre
    ruta.write_bytes(contenido.encode(encoding) if isinstance(contenido, str) else contenido)
    return _Doc(nombre)


def test_reads_utf8_and_chunks_it(tmp_path, monkeypatch):
    from app.tasks.pipeline import extract_text_file
    from config.settings import settings

    monkeypatch.setattr(settings, "CHUNK_SIZE", 120)
    monkeypatch.setattr(settings, "CHUNK_OVERLAP", 20)

    texto = " ".join(f"clause{i:03d}" for i in range(60))
    doc = _escribir(tmp_path, monkeypatch, "norma.txt", texto)

    chunks = extract_text_file(doc)

    assert len(chunks) > 1, "the fixture must actually be split"
    assert all(c["page"] == 1 for c in chunks), "a .txt has no pages; do not invent them"
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))
    unido = " ".join(c["text"] for c in chunks)
    assert "clause000" in unido and "clause059" in unido


def test_keeps_accents(tmp_path, monkeypatch):
    from app.tasks.pipeline import extract_text_file

    doc = _escribir(tmp_path, monkeypatch, "acuerdo.txt",
                    "Publicado en el Diario Oficial de la Federación. Señalización y protección.")
    texto = " ".join(c["text"] for c in extract_text_file(doc))

    assert "Federación" in texto
    assert "Señalización" in texto


def test_falls_back_to_latin1_instead_of_failing(tmp_path, monkeypatch):
    from app.tasks.pipeline import extract_text_file

    # cp1252/latin-1 is what old archives and government exports still produce.
    # Indexing it with a couple of odd characters beats rejecting the document.
    doc = _escribir(tmp_path, monkeypatch, "viejo.txt",
                    "Regulación publicada en 1994".encode("latin-1"))

    chunks = extract_text_file(doc)

    assert chunks and "1994" in " ".join(c["text"] for c in chunks)


def test_strips_null_bytes(tmp_path, monkeypatch):
    from app.tasks.pipeline import extract_text_file

    doc = _escribir(tmp_path, monkeypatch, "sucio.txt", "antes\x00despues")
    texto = " ".join(c["text"] for c in extract_text_file(doc))

    assert "\x00" not in texto, "Postgres rejects null bytes in text columns"


def test_empty_file_is_an_error_not_an_empty_document(tmp_path, monkeypatch):
    from app.tasks.pipeline import extract_text_file

    doc = _escribir(tmp_path, monkeypatch, "vacio.txt", "   \n\n  ")

    with pytest.raises(ValueError):
        extract_text_file(doc)


def test_markdown_and_txt_are_accepted_at_the_boundary():
    from app.api.documents import detect_file_type

    assert detect_file_type("nota.txt") == "text"
    assert detect_file_type("apuntes.md") == "text"
    assert detect_file_type("apuntes.MARKDOWN") == "text"
    # Unknown extensions are still rejected rather than guessed at.
    assert detect_file_type("hoja.xlsx") is None
    assert detect_file_type("sinextension") is None


def test_text_is_routed_by_the_extractor_registry():
    from app.tasks.pipeline import EXTRACTORS, extract_text_file

    assert EXTRACTORS["text"] is extract_text_file
