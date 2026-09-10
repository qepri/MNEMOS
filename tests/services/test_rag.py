"""Service tests for app/services/rag.py against real Postgres/pgvector:
vector search, keyword search via plainto_tsquery, RRF merge, adjacent-chunk
expansion, and the documented no-document_ids -> no-sources behavior
(CLAUDE.md RAG Query Pipeline section). Only the LLM/embedding HTTP calls
are faked.
"""
import json
import os

import pytest

from tests.factories import make_chunk, make_document

pytestmark = pytest.mark.service


# ---------------------------------------------------------------------------
# Golden / characterization harness for the RAGService.query refactor (feature
# 009, US2). These snapshot the EXACT system_prompt, user_prompt and the
# returned dict shape that query() produces, so the decomposition + budget-fit
# rewrite can be proven behaviour-preserving (SC-003). The oracle file is
# captured against the pre-refactor code and committed; later runs compare.
# Delete rag_query_golden.json to re-capture against current code.
# ---------------------------------------------------------------------------

_GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "rag_query_golden.json")


def _assert_golden(key, value):
    data = {}
    if os.path.exists(_GOLDEN_PATH):
        with open(_GOLDEN_PATH, encoding="utf-8") as f:
            data = json.load(f)
    if key in data:
        assert value == data[key], (
            f"RAG behaviour changed for '{key}' — the refactor must preserve it byte-for-byte"
        )
    else:
        data[key] = value
        with open(_GOLDEN_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)


def _capture_query(rag, **kwargs):
    """Run query() while capturing the exact prompt handed to the LLM.

    Wrapping rag.llm.chat (rather than faking HTTP) gives the system/user
    strings directly and keeps the test independent of provider payload shape.
    """
    captured = {}

    def fake_chat(system=None, messages=None, images=None):
        captured["system"] = system
        captured["user"] = messages[0]["content"]
        captured["images"] = images
        return "CANNED-ANSWER"

    rag.llm.chat = fake_chat
    result = rag.query(**kwargs)
    return captured, result


def _normalized_sources(sources):
    """Drop nondeterministic ids so sources can be snapshotted."""
    return [
        {"document": s.get("document"), "location": s.get("location"), "type": s.get("type")}
        for s in sources
    ]


def test_golden_query_docs_selected(db_session, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc = make_document(db_session, filename="paris.pdf", original_filename="paris.pdf")
    make_chunk(db_session, doc, content="Paris is the capital of France.", chunk_index=0)
    db_session.commit()

    rag = RAGService(db_session)
    captured, result = _capture_query(
        rag, question="What is the capital of France?", document_ids=[str(doc.id)]
    )

    _assert_golden("docs_selected.system", captured["system"])
    _assert_golden("docs_selected.user", captured["user"])
    _assert_golden("docs_selected.sources", _normalized_sources(result["sources"]))
    assert result["answer"] == "CANNED-ANSWER"
    assert set(result.keys()) == {"answer", "sources", "context_warning", "search_queries"}
    assert captured["images"] is None


def test_golden_query_vanilla_no_docs(db_session, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    rag = RAGService(db_session)
    captured, result = _capture_query(
        rag, question="Tell me a joke.", document_ids=[]
    )

    _assert_golden("vanilla.system", captured["system"])
    _assert_golden("vanilla.user", captured["user"])
    assert result["sources"] == []
    assert result["answer"] == "CANNED-ANSWER"
    assert set(result.keys()) == {"answer", "sources", "context_warning", "search_queries"}


def test_golden_query_images_passthrough(db_session, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    rag = RAGService(db_session)
    imgs = ["data:image/png;base64,AAAA"]
    captured, result = _capture_query(
        rag, question="What is in this image?", document_ids=[], images=imgs
    )

    # Vision path: no docs, images present -> still generates, images forwarded.
    assert captured["images"] == imgs
    _assert_golden("images.system", captured["system"])
    _assert_golden("images.user", captured["user"])


def test_golden_query_over_budget_trims_deterministically(db_session, fake_embeddings, monkeypatch):
    import app.services.rag as rag_mod
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc = make_document(db_session, filename="big.pdf", original_filename="big.pdf")
    # Eight distinct, sizeable chunks so the budget guard must drop several.
    for i in range(8):
        make_chunk(
            db_session,
            doc,
            content=f"Passage number {i} about topic {i}: " + ("lorem ipsum " * 20),
            chunk_index=i,
        )
    db_session.commit()

    # Deterministic char-based token counting + a small context window force
    # trimming without depending on tiktoken or a real model window.
    monkeypatch.setattr(rag_mod, "_count_tokens", lambda text, model="": len(text))
    monkeypatch.setattr(rag_mod, "_model_ctx_size", lambda model, provider="": 5096)

    rag = RAGService(db_session)
    captured, result = _capture_query(
        rag, question="Summarize everything.", document_ids=[str(doc.id)], top_k=8
    )

    # The scenario must actually exercise trimming: some but not all passages survive.
    survivors = sum(1 for i in range(8) if f"Passage number {i} " in captured["user"])
    assert 0 < survivors < 8, f"expected partial trim, {survivors} survived"
    _assert_golden("over_budget.user", captured["user"])


@pytest.fixture(autouse=True)
def openai_provider(monkeypatch):
    from config.settings import settings, LLMProvider
    from app.services.llm_client import reset_client

    monkeypatch.setattr(settings, "LLM_PROVIDER", LLMProvider.OPENAI)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    reset_client()
    yield
    reset_client()


def test_search_similar_chunks_finds_relevant_chunk_and_its_neighbor(db_session, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc = make_document(db_session, language="english")
    make_chunk(db_session, doc, content="pgvector stores embeddings efficiently.", chunk_index=0)
    target = make_chunk(db_session, doc, content="Reciprocal rank fusion merges vector and keyword search.", chunk_index=1)
    make_chunk(db_session, doc, content="Neighbor chunk that should be pulled in by adjacency expansion.", chunk_index=2)
    db_session.commit()

    rag = RAGService(db_session)
    results = rag.search_similar_chunks("reciprocal rank fusion", document_ids=[str(doc.id)], top_k=5)

    result_indices = {c.chunk_index for c in results}
    assert target.chunk_index in result_indices
    # Adjacent-chunk expansion (chunk_index +/-1) should have pulled in a neighbor.
    assert (target.chunk_index - 1 in result_indices) or (target.chunk_index + 1 in result_indices)


def test_search_similar_chunks_only_returns_chunks_from_requested_documents(db_session, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc_a = make_document(db_session, filename="a.pdf")
    make_chunk(db_session, doc_a, content="Content belonging to document A.", chunk_index=0)
    doc_b = make_document(db_session, filename="b.pdf")
    make_chunk(db_session, doc_b, content="Content belonging to document B.", chunk_index=0)
    db_session.commit()

    rag = RAGService(db_session)
    results = rag.search_similar_chunks("content", document_ids=[str(doc_a.id)], top_k=10)

    assert all(c.document_id == doc_a.id for c in results)


def test_query_without_document_ids_returns_no_sources(db_session, fake_llm, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    fake_llm.completion(text="A vanilla answer with no document context.", provider="openai")

    rag = RAGService(db_session)
    result = rag.query(question="What is the capital of France?", document_ids=[])

    assert result["sources"] == []
    assert result["answer"]


def test_query_with_document_ids_cites_sources(db_session, fake_llm, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc = make_document(db_session, filename="paris.pdf", original_filename="paris.pdf")
    make_chunk(db_session, doc, content="Paris is the capital of France.", chunk_index=0)
    db_session.commit()

    fake_llm.completion(text="Paris is the capital [Source: paris.pdf].", provider="openai")

    rag = RAGService(db_session)
    result = rag.query(question="What is the capital of France?", document_ids=[str(doc.id)])

    assert result["sources"]
    assert any(doc.filename in str(s) for s in result["sources"])


# ---------------------------------------------------------------------------
# _fit_to_budget: equivalence to the legacy pop-one-then-rebuild loop, plus the
# bounded-assembly property that motivated the rewrite (feature 009, SC-004/5).
# ---------------------------------------------------------------------------

import math  # noqa: E402


def _make_bundle(rag, chunks, system_prompt="SYS", conversation_context="", question="Q"):
    rag_context, sources = rag._build_hierarchical_context(chunks, [])
    user_prompt = rag._assemble_user_prompt(conversation_context, rag_context, question)
    return {
        "proceed": True,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "rag_context": rag_context,
        "sources": sources,
        "search_queries": [],
        "context_warning": None,
        "conversation_context": conversation_context,
        "question": question,
        "chunks": list(chunks),
        "graph_sections": [],
    }


def _legacy_fit(rag, rag_mod, chunks, conversation_context, question, model_name, budget):
    """Faithful re-implementation of the pre-009 trim loop as the oracle."""
    chunks = list(chunks)
    rag_context, _ = rag._build_hierarchical_context(chunks, [])
    user_prompt = rag._assemble_user_prompt(conversation_context, rag_context, question)
    prompt_tokens = rag_mod._count_tokens(user_prompt, model_name)
    if prompt_tokens > budget and chunks:
        while chunks and prompt_tokens > budget:
            chunks.pop()
            rag_context, _ = rag._build_hierarchical_context(chunks, [])
            user_prompt = rag._assemble_user_prompt(conversation_context, rag_context, question)
            prompt_tokens = rag_mod._count_tokens(user_prompt, model_name)
    return len(chunks), user_prompt


@pytest.mark.parametrize("scenario", ["no_trim", "partial", "drop_all"])
def test_fit_to_budget_matches_legacy_loop(db_session, fake_embeddings, monkeypatch, scenario):
    import app.services.rag as rag_mod
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc = make_document(db_session, filename="big.pdf", original_filename="big.pdf")
    chunks = [
        make_chunk(db_session, doc, content=f"Passage {i}: " + ("alpha beta " * 15), chunk_index=i)
        for i in range(7)
    ]
    db_session.commit()

    monkeypatch.setattr(rag_mod, "_count_tokens", lambda text, model="": len(text))
    rag = RAGService(db_session)

    # Full-prompt length drives the target budget for each scenario.
    full_bundle = _make_bundle(rag, chunks)
    full_len = len(full_bundle["user_prompt"])
    target = {"no_trim": full_len + 500, "partial": full_len // 2, "drop_all": 1}[scenario]

    # budget = ctx - reserve(4096, no prefs row) - len(system_prompt="SYS"=3)
    monkeypatch.setattr(rag_mod, "_model_ctx_size", lambda *a, **k: 4096 + 3 + target)

    legacy_keep, legacy_prompt = _legacy_fit(
        rag, rag_mod, chunks, "", "Q", rag.llm.model or "", target
    )

    bundle = _make_bundle(rag, chunks)
    rag._fit_to_budget(bundle)

    assert len(bundle["chunks"]) == legacy_keep, "kept-chunk count diverged from legacy loop"
    assert bundle["user_prompt"] == legacy_prompt, "final prompt diverged from legacy loop"


def test_fit_to_budget_assembles_a_bounded_number_of_times(db_session, fake_embeddings, monkeypatch):
    """The rewrite's point: assemble the full prompt O(log n), not O(n), times."""
    import app.services.rag as rag_mod
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc = make_document(db_session, filename="big.pdf", original_filename="big.pdf")
    n = 40
    chunks = [
        make_chunk(db_session, doc, content=f"Passage {i}: " + ("alpha beta " * 10), chunk_index=i)
        for i in range(n)
    ]
    db_session.commit()

    monkeypatch.setattr(rag_mod, "_count_tokens", lambda text, model="": len(text))
    rag = RAGService(db_session)
    full_len = len(_make_bundle(rag, chunks)["user_prompt"])
    # Force dropping almost everything so a linear loop would rebuild ~n times.
    monkeypatch.setattr(rag_mod, "_model_ctx_size", lambda *a, **k: 4096 + 3 + (full_len // 20))

    calls = {"n": 0}
    real_build = rag._build_hierarchical_context
    monkeypatch.setattr(
        rag, "_build_hierarchical_context",
        lambda c, g: (calls.__setitem__("n", calls["n"] + 1) or real_build(c, g)),
    )

    bundle = _make_bundle(rag, chunks)
    calls["n"] = 0  # count only assembles inside _fit_to_budget
    rag._fit_to_budget(bundle)

    bound = 2 * math.ceil(math.log2(n + 1)) + 4
    assert calls["n"] <= bound, f"assembled {calls['n']} times, expected <= {bound} (sub-linear)"
    assert 0 < len(bundle["chunks"]) < n, "scenario should partially trim"


def test_build_prompt_selects_rag_vs_vanilla_system_prompt(db_session, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc = make_document(db_session, filename="p.pdf", original_filename="p.pdf")
    chunk = make_chunk(db_session, doc, content="Some grounded fact.", chunk_index=0)
    db_session.commit()

    rag = RAGService(db_session)

    with_docs = rag._build_prompt(
        question="Q", chunks=[chunk], graph_sections=[], conversation_history=None,
        system_prompt=None, web_search=False, images=None, document_ids=[str(doc.id)],
    )
    assert with_docs["proceed"] is True
    assert "based ONLY on the provided context" in with_docs["system_prompt"]

    vanilla = rag._build_prompt(
        question="Q", chunks=[], graph_sections=[], conversation_history=None,
        system_prompt=None, web_search=False, images=None, document_ids=[],
    )
    assert vanilla["proceed"] is True
    assert "to the best of your ability" in vanilla["system_prompt"]
    assert vanilla["sources"] == []


def test_build_prompt_aborts_when_docs_requested_but_no_context(db_session, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    rag = RAGService(db_session)

    # Docs requested (not vanilla), nothing retrieved, no images -> abort.
    bundle = rag._build_prompt(
        question="Q", chunks=[], graph_sections=[], conversation_history=None,
        system_prompt=None, web_search=False, images=None, document_ids=["some-doc-id"],
    )
    assert bundle == {"proceed": False}

    # Same, but with an image present -> vision path proceeds.
    proceeds = rag._build_prompt(
        question="Q", chunks=[], graph_sections=[], conversation_history=None,
        system_prompt=None, web_search=False, images=["data:image/png;base64,AAAA"],
        document_ids=["some-doc-id"],
    )
    assert proceeds["proceed"] is True


def test_build_prompt_injects_user_memories(db_session, fake_embeddings):
    from app.services.rag import RAGService
    from app.models.user_preferences import UserPreferences
    from app.models.memory import UserMemory

    fake_embeddings.install()
    # flush (not commit) so the rows live only inside this test's rolled-back
    # transaction and never leak into other tests via the shared container.
    # Clear first so `.first()` is deterministic regardless of test ordering.
    db_session.query(UserMemory).delete()
    db_session.query(UserPreferences).delete()
    db_session.add(UserPreferences(memory_enabled=True))
    db_session.add(UserMemory(content="User prefers concise answers."))
    db_session.flush()

    rag = RAGService(db_session)
    bundle = rag._build_prompt(
        question="Q", chunks=[], graph_sections=[], conversation_history=None,
        system_prompt=None, web_search=False, images=None, document_ids=[],
    )
    assert "User Profile / Memories:" in bundle["system_prompt"]
    assert "User prefers concise answers." in bundle["system_prompt"]
