from __future__ import annotations

from collections import Counter, defaultdict
import math
import re
from typing import Callable


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


class BM25Index:
    def __init__(
        self,
        docs: list[str],
        doc_ids: list[str],
        *,
        k1: float = 1.5,
        b: float = 0.75,
        tokenizer: Callable[[str], list[str]] | None = None,
    ):
        if len(docs) != len(doc_ids):
            raise ValueError("docs and doc_ids must have the same length")
        if len(set(doc_ids)) != len(doc_ids):
            raise ValueError("doc_ids must be unique")

        self._k1 = k1
        self._b = b
        self._tokenizer = tokenizer or tokenize
        self._doc_ids = list(doc_ids)
        self._doc_tfs: dict[str, Counter[str]] = {}
        self._doc_lens: dict[str, int] = {}
        self._doc_freq: dict[str, int] = defaultdict(int)
        self._n_docs = len(doc_ids)

        total_len = 0
        for doc_id, text in zip(doc_ids, docs):
            tokens = self._tokenizer(text)
            tf = Counter(tokens)
            self._doc_tfs[doc_id] = tf
            doc_len = len(tokens)
            self._doc_lens[doc_id] = doc_len
            total_len += doc_len
            for token in tf:
                self._doc_freq[token] += 1
        self._avgdl = (total_len / self._n_docs) if self._n_docs > 0 else 0.0

    @property
    def doc_ids(self) -> list[str]:
        return list(self._doc_ids)

    def score(self, query: str, top_k: int) -> list[tuple[str, float]]:
        if self._n_docs == 0:
            return []
        query_tokens = self._tokenizer(query)
        if not query_tokens:
            return []

        unique_query_tokens = list(dict.fromkeys(query_tokens))
        scored: list[tuple[str, float]] = []
        for doc_id in self._doc_ids:
            value = self._score_doc(doc_id, unique_query_tokens)
            if value > 0:
                scored.append((doc_id, value))

        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:top_k]

    def score_map(self, query: str) -> dict[str, float]:
        return dict(self.score(query, top_k=self._n_docs))

    def _score_doc(self, doc_id: str, query_tokens: list[str]) -> float:
        tf = self._doc_tfs.get(doc_id)
        if not tf:
            return 0.0
        dl = self._doc_lens.get(doc_id, 0)
        score = 0.0
        for token in query_tokens:
            f = tf.get(token, 0)
            if f <= 0:
                continue
            df = self._doc_freq.get(token, 0)
            if df <= 0:
                continue
            idf = math.log(1.0 + (self._n_docs - df + 0.5) / (df + 0.5))
            denom = f + self._k1 * (1 - self._b + self._b * (dl / self._avgdl if self._avgdl > 0 else 0))
            score += idf * ((f * (self._k1 + 1)) / denom)
        return score
