from __future__ import annotations
from typing import Any

def has_role(user: dict[str, Any] | None, *needles: str) -> bool:
    if not user:
        return False
    role = str((user.get("rol") or "")).lower()
    return any(n.lower() in role for n in needles)