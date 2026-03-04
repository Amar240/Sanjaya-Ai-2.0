from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
from collections import defaultdict

from ..data_loader import CatalogStore
from .bm25 import BM25Index, tokenize as bm25_tokenize
from ..schemas.catalog import RoleMarket
from ..schemas.plan import CoursePurposeCard, EvidencePanelItem, PlanResponse

try:
    from langchain_core.documents import Document
    from langchain_core.embeddings import Embeddings

    LANGCHAIN_CORE_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency guard
    Document = None
    LANGCHAIN_CORE_AVAILABLE = False

    class Embeddings:  # type: ignore[no-redef]
        pass

try:
    from langchain_chroma import Chroma

    CHROMA_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency guard
    try:
        from langchain_community.vectorstores import Chroma

        CHROMA_AVAILABLE = True
    except Exception:  # pragma: no cover - optional dependency guard
        Chroma = None
        CHROMA_AVAILABLE = False


def _tokenize(text: str) -> set[str]:
    return set(_tokenize_for_bm25(text))


def _tokenize_for_bm25(text: str) -> list[str]:
    return bm25_tokenize(text)


class HashEmbeddings(Embeddings):
    """Lightweight deterministic embeddings to keep Chroma fully local/offline."""

    def __init__(self, dim: int = 192):
        self.dim = dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _tokenize(text):
            idx = int(hashlib.sha1(token.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec


class MarketEvidenceRetriever:
    """Retrieves market evidence and builds explainable course purpose cards."""

    def __init__(self, store: CatalogStore, persist_dir: str | None = None):
        self.store = store
        self._roles_by_id = store.roles_by_id
        self._skills_by_id = {s.skill_id: s for s in store.skills}
        self._sources_by_id = {s.source_id: s for s in store.sources}
        self._course_skill_strength = self._build_course_skill_strength(store)
        self._course_skill_map = self._build_course_skill_map(self._course_skill_strength)
        self._persist_dir = str(
            Path(
                persist_dir
                or os.getenv("SANJAYA_CHROMA_DIR", "").strip()
                or (_project_root() / "data" / "chroma")
            ).resolve()
        )
        self._index_marker_path = Path(self._persist_dir) / ".sanjaya_chroma_indexed"
        self._vector_index_reused = False

        self._role_rows = self._build_role_rows(store.roles)
        self._evidence_rows = self._build_evidence_rows()
        self._role_row_by_id = {row["role_id"]: row for row in self._role_rows}
        self._evidence_row_by_doc_id = {row["doc_id"]: row for row in self._evidence_rows}
        self._evidence_doc_ids_by_role = self._build_evidence_doc_ids_by_role(self._evidence_rows)
        self._role_bm25 = BM25Index(
            docs=[row["text"] for row in self._role_rows],
            doc_ids=[row["role_id"] for row in self._role_rows],
            tokenizer=_tokenize_for_bm25,
        )
        self._evidence_bm25 = BM25Index(
            docs=[row["text"] for row in self._evidence_rows],
            doc_ids=[row["doc_id"] for row in self._evidence_rows],
            tokenizer=_tokenize_for_bm25,
        )
        self._trust_weight_overrides = self._load_trust_weight_overrides()
        self._last_role_diagnostics: dict = {}
        self._last_evidence_diagnostics: dict = {}
        self._use_vector = False
        self._roles_store = None
        self._evidence_store = None
        self._build_vector_indexes()

    @property
    def using_chroma(self) -> bool:
        return self._use_vector

    @property
    def vector_index_reused(self) -> bool:
        return self._vector_index_reused

    @property
    def persist_dir(self) -> str:
        return self._persist_dir

    def get_store_stats(self) -> dict[str, int | bool | str | None]:
        roles_count: int | None = None
        evidence_count: int | None = None
        if self._roles_store is not None:
            roles_count = self._collection_doc_count(self._roles_store)
        if self._evidence_store is not None:
            evidence_count = self._collection_doc_count(self._evidence_store)
        return {
            "enabled": self._use_vector,
            "persist_dir": self._persist_dir if self._persist_dir else None,
            "roles_count": roles_count,
            "evidence_count": evidence_count,
        }

    def get_last_role_diagnostics(self) -> dict:
        return dict(self._last_role_diagnostics)

    def get_last_evidence_diagnostics(self) -> dict:
        return dict(self._last_evidence_diagnostics)

    def role_required_skills_match_count(self, role_id: str) -> tuple[int, int]:
        role = self._roles_by_id.get(role_id)
        if not role:
            return 0, 0
        required = {req.skill_id for req in role.required_skills}
        if not required:
            return 0, 0
        mapped = sum(1 for skill_id in required if self._skill_has_course_matches(skill_id))
        return mapped, len(required)

    def role_trust_weighted_evidence_availability(self, role_id: str) -> float:
        total = 0.0
        for row in self._evidence_rows:
            if row.get("role_id") != role_id:
                continue
            total += float(row.get("confidence", 0.0)) * self._trust_weight(
                source_provider=str(row.get("source_provider", "Unknown")),
                source_id=str(row.get("source_id", "UNKNOWN")),
            )
        return total

    def retrieve_roles_by_interest(self, interests: list[str], top_k: int = 5) -> list[str]:
        ranked = self.retrieve_roles_by_interest_scored(interests, top_k=top_k)
        return [item["role_id"] for item in ranked]

    def retrieve_roles_by_interest_scored(self, interests: list[str], top_k: int = 5) -> list[dict]:
        if not interests:
            out = [
                {
                    "role_id": role.role_id,
                    "score": 0.0,
                    "bm25": 0.0,
                    "vector": 0.0,
                    "overlap_tokens": 0,
                    "phrase_hits": 0,
                }
                for role in self.store.roles[:top_k]
            ]
            self._last_role_diagnostics = {
                "query": "",
                "candidate_count": len(out),
                "top": [
                    {
                        "role_id": item["role_id"],
                        "hybrid_score": 0.0,
                        "bm25": 0.0,
                        "vector": 0.0,
                    }
                    for item in out[:5]
                ],
            }
            return out

        query = " ".join(interests).strip()
        if not query:
            out = [
                {
                    "role_id": role.role_id,
                    "score": 0.0,
                    "bm25": 0.0,
                    "vector": 0.0,
                    "overlap_tokens": 0,
                    "phrase_hits": 0,
                }
                for role in self.store.roles[:top_k]
            ]
            self._last_role_diagnostics = {
                "query": "",
                "candidate_count": len(out),
                "top": [
                    {
                        "role_id": item["role_id"],
                        "hybrid_score": 0.0,
                        "bm25": 0.0,
                        "vector": 0.0,
                    }
                    for item in out[:5]
                ],
            }
            return out

        candidate_limit = max(top_k * 3, 8)
        bm25_scores = dict(self._role_bm25.score(query, top_k=candidate_limit))
        vector_scores = self._vector_role_scores(query, k=candidate_limit)
        candidate_ids = {
            row["role_id"] for row in self._role_rows
        } | set(bm25_scores.keys()) | set(vector_scores.keys())

        bm25_norm = self._normalize_scores(candidate_ids, bm25_scores)
        vector_norm = self._normalize_scores(candidate_ids, vector_scores)

        scored: list[dict] = []
        for role_id in sorted(candidate_ids):
            row = self._role_row_by_id.get(role_id)
            if row is None:
                continue
            row_tokens = _tokenize(row["text"])
            query_tokens = _tokenize(query)
            overlap_tokens = len(row_tokens & query_tokens)
            phrase_hits = sum(1 for term in interests if term.lower() in row["text"])
            phrase_bonus = 0.06 * phrase_hits
            metadata_bonus = 0.05 if role_id in bm25_scores and role_id in vector_scores else 0.0
            hybrid_score = (
                0.55 * bm25_norm.get(role_id, 0.0)
                + 0.45 * vector_norm.get(role_id, 0.0)
                + phrase_bonus
                + metadata_bonus
            )
            scored.append(
                {
                    "role_id": role_id,
                    "score": hybrid_score,
                    "bm25": bm25_scores.get(role_id, 0.0),
                    "vector": vector_scores.get(role_id, 0.0),
                    "overlap_tokens": overlap_tokens,
                    "phrase_hits": phrase_hits,
                }
            )

        scored.sort(key=lambda item: (-item["score"], item["role_id"]))
        ranked = [item for item in scored if item["score"] > 0]
        if not ranked:
            ranked = [
                {
                    "role_id": role.role_id,
                    "score": 0.0,
                    "bm25": 0.0,
                    "vector": 0.0,
                    "overlap_tokens": 0,
                    "phrase_hits": 0,
                }
                for role in self.store.roles[:top_k]
            ]
        else:
            ranked = ranked[:top_k]

        self._last_role_diagnostics = {
            "query": query,
            "candidate_count": len(scored),
            "top": [
                {
                    "role_id": item["role_id"],
                    "hybrid_score": round(item["score"], 6),
                    "bm25": round(item["bm25"], 6),
                    "vector": round(item["vector"], 6),
                }
                for item in scored[:5]
            ],
        }
        return ranked

    def retrieve_role_evidence(self, role: RoleMarket, top_k: int = 8) -> list[EvidencePanelItem]:
        required_skills = {req.skill_id for req in role.required_skills}
        query = " ".join(
            [
                role.title,
                role.summary,
                *[self._skill_name(skill_id) for skill_id in required_skills],
            ]
        )

        ranked_rows = self._rank_evidence_rows(role, required_skills, query, max(top_k * 3, 12))
        primary_rows = [row for row in ranked_rows if row["role_id"] == role.role_id]
        candidates: list[EvidencePanelItem] = []
        for row in primary_rows:
            source = self._sources_by_id.get(row["source_id"])
            snippet = row["evidence_note"]
            candidates.append(
                EvidencePanelItem(
                    evidence_id=self._evidence_item_id(
                        role_id=row["role_id"],
                        skill_id=row["skill_id"],
                        source_id=row["source_id"],
                        snippet=snippet,
                    ),
                    role_id=row["role_id"],
                    skill_id=row["skill_id"],
                    skill_name=self._skill_name(row["skill_id"]),
                    source_id=row["source_id"],
                    source_provider=source.provider if source else "Unknown",
                    source_title=source.title if source else "Unknown source",
                    source_url=str(source.url) if source else "",
                    snippet=snippet,
                    retrieval_method=row["retrieval_method"],
                    rank_score=float(row["score"]),
                    confidence=row["confidence"],
                )
            )
        panel = self._finalize_evidence_panel(candidates, top_k)
        self._last_evidence_diagnostics = {
            "query": query,
            "candidate_count": len(primary_rows),
            "top": [
                {
                    "evidence_id": row["evidence_id"],
                    "rank_score": round(float(row["score"]), 6),
                    "bm25": round(float(row["bm25"]), 6),
                    "vector": round(float(row["vector"]), 6),
                    "trust_weight": round(float(row["trust_weight"]), 6),
                    "provider": row["source_provider"],
                }
                for row in primary_rows[:5]
            ],
        }
        return panel

    def build_course_purpose_cards(
        self,
        plan: PlanResponse,
        role: RoleMarket,
        evidence_panel: list[EvidencePanelItem],
        max_evidence_per_course: int = 2,
    ) -> list[CoursePurposeCard]:
        role_required = {req.skill_id for req in role.required_skills}
        course_to_skills: dict[str, set[str]] = defaultdict(set)

        for cov in plan.skill_coverage:
            for course_id in cov.matched_courses:
                if cov.required_skill_id in role_required:
                    course = self.store.courses_by_id.get(course_id)
                    if not course:
                        continue
                    strength = self._course_skill_strength.get((course_id, cov.required_skill_id), 0)
                    if self._is_strong_skill_link(course, cov.required_skill_id, strength):
                        course_to_skills[course_id].add(cov.required_skill_id)

        for course_id, skill_ids in self._course_skill_map.items():
            course = self.store.courses_by_id.get(course_id)
            if not course:
                continue
            if course_id not in course_to_skills:
                course_to_skills[course_id] = set()
            for skill_id in skill_ids:
                if skill_id in role_required:
                    strength = self._course_skill_strength.get((course_id, skill_id), 0)
                    if self._is_strong_skill_link(course, skill_id, strength):
                        course_to_skills[course_id].add(skill_id)

        evidence_by_skill: dict[str, list[EvidencePanelItem]] = defaultdict(list)
        for item in evidence_panel:
            evidence_by_skill[item.skill_id].append(item)

        cards: list[CoursePurposeCard] = []
        for semester in plan.semesters:
            for course_id in semester.courses:
                course = self.store.courses_by_id.get(course_id)
                if not course:
                    continue
                skill_ids = sorted(course_to_skills.get(course_id, set()))
                skill_names = [self._skill_name(skill_id) for skill_id in skill_ids]

                if skill_names:
                    summary = ", ".join(skill_names[:3])
                    why = f"Supports {role.title} by building {summary}."
                else:
                    why = "Included as a prerequisite/support course to keep the roadmap feasible."

                card_evidence: list[EvidencePanelItem] = []
                for skill_id in skill_ids:
                    for ev in evidence_by_skill.get(skill_id, []):
                        if ev not in card_evidence:
                            card_evidence.append(ev)
                        if len(card_evidence) >= max_evidence_per_course:
                            break
                    if len(card_evidence) >= max_evidence_per_course:
                        break

                cards.append(
                    CoursePurposeCard(
                        course_id=course.course_id,
                        course_title=course.title,
                        why_this_course=why,
                        satisfied_skills=skill_ids,
                        evidence=card_evidence,
                    )
                )

        return cards

    def _build_vector_indexes(self) -> None:
        if not (LANGCHAIN_CORE_AVAILABLE and CHROMA_AVAILABLE and Document):
            return
        if not self._role_rows or not self._evidence_rows:
            return

        try:
            embeddings = HashEmbeddings()
            Path(self._persist_dir).mkdir(parents=True, exist_ok=True)
            self._roles_store = Chroma(
                collection_name="roles_collection",
                embedding_function=embeddings,
                persist_directory=self._persist_dir,
            )
            self._evidence_store = Chroma(
                collection_name="role_evidence_collection",
                embedding_function=embeddings,
                persist_directory=self._persist_dir,
            )

            rebuild_requested = os.getenv("SANJAYA_REBUILD_CHROMA", "").strip() == "1"
            role_ids = [self._role_doc_id(row["role_id"]) for row in self._role_rows]
            evidence_ids = [row["doc_id"] for row in self._evidence_rows]
            has_roles = self._has_doc_id(self._roles_store, role_ids[0]) if role_ids else False
            has_evidence = (
                self._has_doc_id(self._evidence_store, evidence_ids[0])
                if evidence_ids
                else False
            )
            has_existing_index = has_roles and has_evidence

            if rebuild_requested:
                self._clear_collection(self._roles_store)
                self._clear_collection(self._evidence_store)
                self._delete_index_marker()
                has_existing_index = False
            elif self._index_marker_path.exists() and not (has_roles ^ has_evidence):
                has_existing_index = True
            elif has_roles or has_evidence:
                # Keep collections consistent; partially indexed state is rebuilt deterministically.
                self._clear_collection(self._roles_store)
                self._clear_collection(self._evidence_store)
                has_existing_index = False

            if has_existing_index:
                self._vector_index_reused = True
                self._use_vector = True
                return

            role_docs = [
                Document(
                    page_content=row["text"],
                    metadata={"role_id": row["role_id"]},
                )
                for row in self._role_rows
            ]
            self._roles_store.add_documents(
                role_docs,
                ids=role_ids,
            )

            evidence_docs = [
                Document(
                    page_content=row["text"],
                    metadata={
                        "doc_id": row["doc_id"],
                        "role_id": row["role_id"],
                        "skill_id": row["skill_id"],
                        "source_id": row["source_id"],
                        "confidence": row["confidence"],
                        "evidence_note": row["evidence_note"],
                        "source_provider": row["source_provider"],
                    },
                )
                for row in self._evidence_rows
            ]
            self._evidence_store.add_documents(
                evidence_docs,
                ids=evidence_ids,
            )
            self._persist(self._roles_store)
            self._persist(self._evidence_store)
            self._write_index_marker()
            self._use_vector = True
        except Exception:
            self._roles_store = None
            self._evidence_store = None
            self._use_vector = False
            self._vector_index_reused = False

    def _build_role_rows(self, roles: list[RoleMarket]) -> list[dict]:
        rows = []
        for role in roles:
            skill_names = [self._skill_name(req.skill_id) for req in role.required_skills]
            text = f"{role.title} {role.summary} {' '.join(skill_names)}".lower()
            rows.append({"role_id": role.role_id, "text": text})
        return rows

    def _build_evidence_rows(self) -> list[dict]:
        rows: list[dict] = []
        used_doc_ids: set[str] = set()
        for ev in self.store.evidence_links:
            role = self._roles_by_id.get(ev.role_id)
            role_title = role.title if role else ev.role_id
            skill_name = self._skill_name(ev.skill_id)
            source_ids = ev.evidence_sources or ["UNKNOWN"]
            for source_id in source_ids:
                source = self._sources_by_id.get(source_id)
                source_title = source.title if source else "Unknown source"
                source_provider = source.provider if source else "Unknown"
                text = (
                    f"{role_title} {skill_name} {ev.evidence_note} "
                    f"{source_title}"
                ).lower()
                row = {
                    "role_id": ev.role_id,
                    "skill_id": ev.skill_id,
                    "source_id": source_id,
                    "source_provider": source_provider,
                    "confidence": float(ev.confidence),
                    "evidence_note": ev.evidence_note,
                    "text": text,
                }
                doc_id = self._evidence_doc_id(row)
                if doc_id in used_doc_ids:
                    suffix = 1
                    while f"{doc_id}::{suffix}" in used_doc_ids:
                        suffix += 1
                    doc_id = f"{doc_id}::{suffix}"
                used_doc_ids.add(doc_id)
                row["doc_id"] = doc_id
                rows.append(
                    row
                )
        return rows

    def _build_course_skill_strength(self, store: CatalogStore) -> dict[tuple[str, str], int]:
        mapping: dict[tuple[str, str], int] = {}
        for row in store.course_skills:
            key = (row.course_id, row.skill_id)
            mapping[key] = max(mapping.get(key, 0), int(row.strength))
        return mapping

    def _build_course_skill_map(
        self,
        strength_map: dict[tuple[str, str], int],
    ) -> dict[str, set[str]]:
        mapping: dict[str, set[str]] = defaultdict(set)
        for course_id, skill_id in strength_map:
            mapping[course_id].add(skill_id)
        return mapping

    def _skill_has_course_matches(self, skill_id: str) -> bool:
        for course_id, mapped_skill_id in self._course_skill_strength:
            if mapped_skill_id == skill_id and self._course_skill_strength[(course_id, mapped_skill_id)] > 0:
                return True
        return False

    def _build_evidence_doc_ids_by_role(self, rows: list[dict]) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            mapping[row["role_id"]].append(row["doc_id"])
        return mapping

    def _is_strong_skill_link(self, course, skill_id: str, strength: int) -> bool:
        if strength <= 0:
            return False
        if self._is_foundational_course(course):
            return False

        dept = course.department
        title = course.title.upper()
        desc = course.description.upper()
        text = f"{title} {desc}"

        if strength >= 4:
            return True

        if skill_id == "SK_BUSINESS_ANALYSIS" and strength >= 2:
            return dept in {"MISY", "BUAD", "ECON", "FINC", "ACCT"}

        if skill_id == "SK_DATA_VIZ" and strength >= 2:
            return dept == "BUAD" or any(k in text for k in ("VISUAL", "DASHBOARD", "TABLEAU", "POWER BI"))

        if skill_id == "SK_SQL" and strength >= 2:
            return dept in {"MISY", "CISC", "BINF"} and any(
                k in text for k in ("DATABASE", "SQL", "QUERY", "RELATIONAL")
            )

        return strength >= 3

    def _is_foundational_course(self, course) -> bool:
        m = re.search(r"-(\d{3})", course.course_id)
        cnum = int(m.group(1)) if m else None
        if cnum is not None and cnum < 100:
            return True
        title_upper = course.title.upper()
        foundational_terms = (
            "INTERMEDIATE ALGEBRA",
            "PRE-CALCULUS",
            "PRECALCULUS",
            "SURVEY OF",
            "CONTEMPORARY MATHEMATICS",
        )
        return any(term in title_upper for term in foundational_terms)

    def _rank_evidence_rows(
        self,
        role: RoleMarket,
        required_skills: set[str],
        query: str,
        top_k: int,
    ) -> list[dict]:
        doc_ids = self._evidence_doc_ids_by_role.get(role.role_id, [])
        if not doc_ids:
            return []

        bm25_scores = self._evidence_bm25.score_map(query) if self._evidence_bm25 else {}
        vector_scores = self._vector_evidence_scores(query, k=max(top_k * 4, 24))
        bm25_norm = self._normalize_scores(set(doc_ids), bm25_scores)
        vector_norm = self._normalize_scores(set(doc_ids), vector_scores)
        snippet_counts = self._snippet_duplicate_counts(doc_ids)
        use_bm25 = self._evidence_bm25 is not None
        use_vector = bool(vector_scores)

        ranked: list[dict] = []
        for doc_id in doc_ids:
            row = self._evidence_row_by_doc_id.get(doc_id)
            if not row:
                continue
            trust = self._trust_weight(
                source_provider=row.get("source_provider", "Unknown"),
                source_id=row.get("source_id", "UNKNOWN"),
            )
            skill_bonus = 0.06 if row["skill_id"] in required_skills else 0.0
            role_bonus = 0.04 if row["role_id"] == role.role_id else 0.0
            duplicate_penalty = 0.03 * max(0, snippet_counts.get(self._normalized_snippet_key(row["evidence_note"]), 1) - 1)
            score = (
                0.50 * bm25_norm.get(doc_id, 0.0)
                + 0.35 * vector_norm.get(doc_id, 0.0)
                + 0.15 * float(row.get("confidence", 0.0))
                + 0.10 * trust
                + skill_bonus
                + role_bonus
                - duplicate_penalty
            )
            retrieval_method = "hybrid" if use_bm25 and use_vector else "lexical" if use_bm25 else "vector"
            ranked.append(
                {
                    **row,
                    "evidence_id": self._evidence_item_id(
                        role_id=row["role_id"],
                        skill_id=row["skill_id"],
                        source_id=row["source_id"],
                        snippet=row["evidence_note"],
                    ),
                    "score": score,
                    "bm25": bm25_scores.get(doc_id, 0.0),
                    "vector": vector_scores.get(doc_id, 0.0),
                    "trust_weight": trust,
                    "retrieval_method": retrieval_method,
                }
            )

        ranked.sort(
            key=lambda row: (
                row["role_id"] != role.role_id,
                -row["score"],
                -float(row.get("confidence", 0.0)),
                row["source_id"],
                row["skill_id"],
                row["doc_id"],
            )
        )
        return ranked

    def _vector_role_scores(self, query: str, k: int) -> dict[str, float]:
        if not self._roles_store:
            return {}

        try:
            docs = self._roles_store.similarity_search(query, k=k)
            out: dict[str, float] = {}
            for idx, doc in enumerate(docs):
                role_id = str(doc.metadata.get("role_id", ""))
                if not role_id:
                    continue
                approx = 1.0 / float(idx + 1)
                out[role_id] = max(approx, out.get(role_id, float("-inf")))
            return out
        except Exception:
            return {}

    def _vector_evidence_scores(self, query: str, k: int) -> dict[str, float]:
        if not self._evidence_store:
            return {}

        try:
            docs = self._evidence_store.similarity_search(query, k=k)
            out: dict[str, float] = {}
            for idx, doc in enumerate(docs):
                doc_id = self._metadata_doc_id(doc)
                if not doc_id:
                    continue
                approx = 1.0 / float(idx + 1)
                out[doc_id] = max(approx, out.get(doc_id, float("-inf")))
            return out
        except Exception:
            return {}

    def _metadata_doc_id(self, doc) -> str:
        doc_id = str(doc.metadata.get("doc_id", "")).strip()
        if doc_id:
            return doc_id
        role_id = str(doc.metadata.get("role_id", "")).strip()
        skill_id = str(doc.metadata.get("skill_id", "")).strip()
        source_id = str(doc.metadata.get("source_id", "")).strip()
        snippet = str(doc.metadata.get("evidence_note", doc.page_content))
        if role_id and skill_id and source_id:
            return self._evidence_doc_id(
                {
                    "role_id": role_id,
                    "skill_id": skill_id,
                    "source_id": source_id,
                    "evidence_note": snippet,
                }
            )
        return ""

    def _normalize_scores(self, ids: set[str], raw_scores: dict[str, float]) -> dict[str, float]:
        values = [raw_scores.get(item_id, 0.0) for item_id in ids]
        if not values:
            return {}
        min_value = min(values)
        max_value = max(values)
        if max_value <= min_value:
            return {item_id: 0.0 for item_id in ids}
        scale = max_value - min_value
        return {
            item_id: (raw_scores.get(item_id, 0.0) - min_value) / scale
            for item_id in ids
        }

    def _snippet_duplicate_counts(self, doc_ids: list[str]) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for doc_id in doc_ids:
            row = self._evidence_row_by_doc_id.get(doc_id)
            if not row:
                continue
            key = self._normalized_snippet_key(row.get("evidence_note", ""))
            counts[key] += 1
        return counts

    def _load_trust_weight_overrides(self) -> dict[str, dict[str, float]]:
        provider_overrides: dict[str, float] = {}
        source_overrides: dict[str, float] = {}
        raw = os.getenv("SANJAYA_TRUST_WEIGHTS_JSON", "").strip()
        if not raw:
            return {"provider": provider_overrides, "source": source_overrides}
        try:
            payload = json.loads(raw)
        except Exception:
            return {"provider": provider_overrides, "source": source_overrides}
        if not isinstance(payload, dict):
            return {"provider": provider_overrides, "source": source_overrides}

        for key, value in payload.items():
            if not isinstance(key, str):
                continue
            try:
                weight = float(value)
            except (TypeError, ValueError):
                continue
            if key.startswith("source:"):
                source_overrides[key.split(":", 1)[1].strip().upper()] = weight
            else:
                provider_overrides[key.strip().lower()] = weight
        return {"provider": provider_overrides, "source": source_overrides}

    def _trust_weight(self, source_provider: str, source_id: str) -> float:
        source_key = (source_id or "").strip().upper()
        provider_key = (source_provider or "").strip().lower()

        source_overrides = self._trust_weight_overrides.get("source", {})
        provider_overrides = self._trust_weight_overrides.get("provider", {})
        if source_key in source_overrides:
            return float(source_overrides[source_key])
        if provider_key in provider_overrides:
            return float(provider_overrides[provider_key])

        if "bls" in provider_key or source_key.startswith("BLS"):
            return 1.0
        if "o*net" in provider_key or "onet" in provider_key or source_key.startswith("ONET"):
            return 0.95
        if "university" in provider_key or "catalog" in provider_key:
            return 0.9
        return 0.85

    def _skill_name(self, skill_id: str) -> str:
        skill = self._skills_by_id.get(skill_id)
        return skill.name if skill else skill_id

    def _role_doc_id(self, role_id: str) -> str:
        return f"role::{role_id}"

    def _evidence_item_id(
        self,
        *,
        role_id: str,
        skill_id: str,
        source_id: str,
        snippet: str,
    ) -> str:
        payload = f"{role_id}|{skill_id}|{source_id}|{snippet}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]

    def _evidence_doc_id(self, row: dict) -> str:
        snippet_hash = hashlib.sha1(
            str(row.get("evidence_note", "")).encode("utf-8")
        ).hexdigest()[:10]
        return (
            f"evidence::{row['role_id']}::{row['skill_id']}::{row['source_id']}::{snippet_hash}"
        )

    def _finalize_evidence_panel(
        self,
        candidates: list[EvidencePanelItem],
        top_k: int,
    ) -> list[EvidencePanelItem]:
        deduped: dict[str, EvidencePanelItem] = {}
        for item in candidates:
            key = self._normalized_snippet_key(item.snippet)
            current = deduped.get(key)
            if current is None:
                deduped[key] = item
                continue
            if self._better_evidence(item, current):
                deduped[key] = item

        ranked = sorted(
            deduped.values(),
            key=lambda item: (
                -(item.rank_score if item.rank_score is not None else float("-inf")),
                -(item.confidence if item.confidence is not None else 0.0),
                item.source_id,
            ),
        )
        selected = ranked[:top_k]
        provider_pool_size = len({item.source_provider for item in ranked})
        if (
            top_k >= 4
            and selected
            and provider_pool_size >= 2
            and len({item.source_provider for item in selected}) == 1
        ):
            selected = self._ensure_source_diversity(selected, ranked, top_k)
        return selected

    def _ensure_source_diversity(
        self,
        selected: list[EvidencePanelItem],
        ranked_pool: list[EvidencePanelItem],
        top_k: int,
    ) -> list[EvidencePanelItem]:
        selected = list(selected[:top_k])
        providers = {item.source_provider for item in selected}
        if len(providers) >= 2:
            return selected
        dominant_provider = selected[0].source_provider
        alternative = next(
            (item for item in ranked_pool if item.source_provider != dominant_provider),
            None,
        )
        if alternative is None:
            return selected
        replace_idx = min(
            range(len(selected)),
            key=lambda idx: (
                selected[idx].rank_score if selected[idx].rank_score is not None else float("-inf"),
                selected[idx].confidence if selected[idx].confidence is not None else 0.0,
                selected[idx].source_id,
            ),
        )
        selected[replace_idx] = alternative
        selected = sorted(
            selected,
            key=lambda item: (
                -(item.rank_score if item.rank_score is not None else float("-inf")),
                -(item.confidence if item.confidence is not None else 0.0),
                item.source_id,
            ),
        )
        return selected[:top_k]

    def _normalized_snippet_key(self, snippet: str) -> str:
        norm = re.sub(r"\s+", " ", (snippet or "").strip().lower())
        return hashlib.sha1(norm.encode("utf-8")).hexdigest()

    def _better_evidence(self, candidate: EvidencePanelItem, current: EvidencePanelItem) -> bool:
        candidate_rank = candidate.rank_score if candidate.rank_score is not None else float("-inf")
        current_rank = current.rank_score if current.rank_score is not None else float("-inf")
        if candidate_rank != current_rank:
            return candidate_rank > current_rank

        candidate_conf = candidate.confidence if candidate.confidence is not None else 0.0
        current_conf = current.confidence if current.confidence is not None else 0.0
        if candidate_conf != current_conf:
            return candidate_conf > current_conf

        return candidate.source_id < current.source_id

    def _collection_doc_count(self, store) -> int:
        try:
            payload = store.get(include=[])
            ids = payload.get("ids", []) if isinstance(payload, dict) else []
            return len(ids)
        except Exception:
            collection = getattr(store, "_collection", None)
            if collection is not None and hasattr(collection, "count"):
                try:
                    return int(collection.count())
                except Exception:
                    return 0
            return 0

    def _has_doc_id(self, store, doc_id: str) -> bool:
        if not doc_id:
            return False
        try:
            payload = store.get(ids=[doc_id], include=[])
            ids = payload.get("ids", []) if isinstance(payload, dict) else []
            return bool(ids)
        except Exception:
            collection = getattr(store, "_collection", None)
            if collection is not None and hasattr(collection, "get"):
                try:
                    payload = collection.get(ids=[doc_id], include=[])
                    ids = payload.get("ids", []) if isinstance(payload, dict) else []
                    return bool(ids)
                except Exception:
                    return False
            return False

    def _clear_collection(self, store) -> None:
        collection = getattr(store, "_collection", None)
        if collection is None or not hasattr(collection, "delete"):
            return
        try:
            collection.delete(where={})
        except Exception:
            pass

    def _persist(self, store) -> None:
        persist_fn = getattr(store, "persist", None)
        if callable(persist_fn):
            try:
                persist_fn()
            except Exception:
                pass

    def _write_index_marker(self) -> None:
        try:
            self._index_marker_path.write_text("indexed", encoding="utf-8")
        except Exception:
            pass

    def _delete_index_marker(self) -> None:
        try:
            if self._index_marker_path.exists():
                self._index_marker_path.unlink()
        except Exception:
            pass


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]
