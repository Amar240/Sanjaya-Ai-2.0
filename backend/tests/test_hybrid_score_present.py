from __future__ import annotations

from app.rag import evidence_retriever


def test_evidence_items_include_rank_score_and_retrieval_method(sample_store, monkeypatch) -> None:
    monkeypatch.setattr(evidence_retriever, "CHROMA_AVAILABLE", False)
    retriever = evidence_retriever.MarketEvidenceRetriever(sample_store, persist_dir=None)
    panel = retriever.retrieve_role_evidence(sample_store.roles[0], top_k=5)
    assert panel
    for item in panel:
        assert item.rank_score is not None
        assert item.retrieval_method in {"hybrid", "lexical", "vector"}
