from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_hash(data: dict[str, Any]) -> str:
    normalized = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def workflow_cache_key(workflow_name: str, version: str, data: dict[str, Any]) -> str:
    return f"{workflow_name}:{version}:{stable_hash(data)}"
