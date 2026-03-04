from __future__ import annotations

from collections import OrderedDict
import os
from threading import Lock

from .schemas.plan import PlanResponse


class PlanStore:
    def __init__(self, max_size: int | None = None):
        self.max_size = max_size if max_size and max_size > 0 else _store_size_from_env()
        self._items: OrderedDict[str, PlanResponse] = OrderedDict()
        self._evictions = 0
        self._lock = Lock()

    def put(self, plan_id: str, plan: PlanResponse) -> None:
        if not plan_id:
            return
        normalized = normalize_plan_snapshot(plan)
        normalized.plan_id = plan_id
        with self._lock:
            if plan_id in self._items:
                self._items.pop(plan_id)
            self._items[plan_id] = normalized.model_copy(deep=True)
            while len(self._items) > self.max_size:
                self._items.popitem(last=False)
                self._evictions += 1

    def get(self, plan_id: str) -> PlanResponse | None:
        if not plan_id:
            return None
        with self._lock:
            value = self._items.pop(plan_id, None)
            if value is None:
                return None
            self._items[plan_id] = value
            return value.model_copy(deep=True)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "count": len(self._items),
                "max_size": self.max_size,
                "evictions": self._evictions,
            }


def normalize_plan_snapshot(plan: PlanResponse) -> PlanResponse:
    snapshot = plan.model_copy(deep=True)
    snapshot.request_id = ""
    snapshot.node_timings = []
    snapshot.cache_status = "miss"
    snapshot.agent_trace = [
        entry for entry in snapshot.agent_trace if not entry.startswith("request_id:")
    ]
    return snapshot


def get_plan_store() -> PlanStore:
    return _PLAN_STORE


def reset_plan_store(max_size: int | None = None) -> None:
    global _PLAN_STORE
    _PLAN_STORE = PlanStore(max_size=max_size)


def _store_size_from_env(default_size: int = 512) -> int:
    raw = os.getenv("SANJAYA_PLAN_STORE_SIZE", "").strip()
    if not raw:
        raw = os.getenv("SANJAYA_PLAN_CACHE_SIZE", "").strip()
    if not raw:
        return default_size
    try:
        parsed = int(raw)
    except ValueError:
        return default_size
    return parsed if parsed > 0 else default_size


_PLAN_STORE = PlanStore()
