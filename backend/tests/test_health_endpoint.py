from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module


class _FakeRetriever:
    def get_store_stats(self) -> dict:
        return {
            "enabled": False,
            "persist_dir": None,
            "roles_count": None,
            "evidence_count": None,
        }


def test_health_endpoint_reports_data_version_and_counts(monkeypatch, sample_store) -> None:
    sample_store.data_version = "test-data-version"
    fake_retriever = _FakeRetriever()
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)
    monkeypatch.setattr(
        main_module,
        "get_retriever_for_store",
        lambda store, create_if_missing=True: fake_retriever,
    )

    with TestClient(main_module.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data_version"] == "test-data-version"
    assert payload["counts"]["courses"] == len(sample_store.courses)
    assert payload["counts"]["roles"] == len(sample_store.roles)
    assert payload["counts"]["skills"] == len(sample_store.skills)
    assert payload["counts"]["sources"] == len(sample_store.sources)
    assert payload["counts"]["role_skill_evidence_links"] == len(sample_store.evidence_links)
