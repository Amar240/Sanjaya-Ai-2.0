from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import os
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


def _cache_size_from_env(default_size: int = 256) -> int:
    raw = os.getenv("SANJAYA_PLAN_CACHE_SIZE", "").strip()
    if not raw:
        return default_size
    try:
        value = int(raw)
    except ValueError:
        return default_size
    return value if value > 0 else default_size


class LruCache(Generic[T]):
    def __init__(self, max_size: int | None = None):
        self.max_size = max_size if max_size and max_size > 0 else _cache_size_from_env()
        self._items: OrderedDict[str, T] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> T | None:
        with self._lock:
            value = self._items.pop(key, None)
            if value is None:
                return None
            self._items[key] = value
            return deepcopy(value)

    def set(self, key: str, value: T) -> None:
        with self._lock:
            if key in self._items:
                self._items.pop(key)
            self._items[key] = deepcopy(value)
            while len(self._items) > self.max_size:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
