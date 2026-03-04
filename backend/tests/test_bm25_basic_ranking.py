from __future__ import annotations

from app.rag.bm25 import BM25Index


def test_bm25_ranks_most_relevant_document_first() -> None:
    index = BM25Index(
        docs=[
            "python data pipeline engineering",
            "finance accounting economics",
            "statistics probability",
        ],
        doc_ids=["doc-a", "doc-b", "doc-c"],
    )
    ranked = index.score("data pipeline", top_k=3)
    assert ranked
    assert ranked[0][0] == "doc-a"


def test_bm25_tie_breaks_by_doc_id() -> None:
    index = BM25Index(
        docs=["alpha beta", "alpha beta"],
        doc_ids=["doc-b", "doc-a"],
    )
    ranked = index.score("alpha", top_k=2)
    assert [doc_id for doc_id, _ in ranked] == ["doc-a", "doc-b"]
