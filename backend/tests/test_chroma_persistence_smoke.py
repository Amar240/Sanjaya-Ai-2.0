from __future__ import annotations

import pytest

from app.rag import evidence_retriever


def test_chroma_persistence_reuses_existing_index(sample_store, tmp_path) -> None:
    if not (
        evidence_retriever.CHROMA_AVAILABLE
        and evidence_retriever.LANGCHAIN_CORE_AVAILABLE
    ):
        pytest.skip("Chroma/LangChain not available in environment")

    retriever_first = evidence_retriever.MarketEvidenceRetriever(
        sample_store, persist_dir=str(tmp_path / "chroma")
    )
    if not retriever_first.using_chroma:
        pytest.skip("Vector store unavailable in runtime environment")

    retriever_second = evidence_retriever.MarketEvidenceRetriever(
        sample_store, persist_dir=str(tmp_path / "chroma")
    )

    assert retriever_second.using_chroma is True
    assert retriever_second.vector_index_reused is True
