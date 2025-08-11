import json, os
from typing import Dict, Any, Optional

class FactsStore:
    """Very simple JSON-backed KV store for canonical facts and learned params."""
    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(self.path):
            self._write({})
        self._cache = self._read()

    def _read(self) -> Dict[str, Any]:
        with open(self.path, 'r') as f:
            return json.load(f)

    def _write(self, data: Dict[str, Any]) -> None:
        with open(self.path, 'w') as f:
            json.dump(data, f, indent=2)

    def get(self, key: str, default=None):
        return self._cache.get(key, default)

    def set(self, key: str, value: Any):
        self._cache[key] = value
        self._write(self._cache)

    def all(self) -> Dict[str, Any]:
        return dict(self._cache)
