from __future__ import annotations

from app.agents.job_extractor import extract_job_skills


def test_job_extractor_fallback_schema(monkeypatch, sample_store) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    text = (
        "Data Engineer role. Required skills include Python, SQL, and data pipelines. "
        "Preferred experience with cloud services and Docker for deployment workflows."
    )
    extracted, llm_status, llm_error = extract_job_skills(text, store=sample_store)
    assert llm_status == "disabled"
    assert llm_error is None
    assert isinstance(extracted.required_skills, list)
    assert isinstance(extracted.preferred_skills, list)
    assert isinstance(extracted.tools, list)
