"""Shared fail-closed spread policy for historical research runners."""
from __future__ import annotations

import math
from typing import Any


def with_fail_closed_spread_gate(costs: dict[str, Any] | None) -> dict[str, Any]:
    """Require a positive defensible maximum spread for every research replay.

    A zero or missing cap intentionally blocks entries through the MTF engine.
    This prevents optimizer/calibration/walk-forward reports from silently
    bypassing the P2.5 gate while the cost-scenario runner is correctly blocked.
    """
    normalized = dict(costs or {})
    try:
        cap = float(normalized.get("max_spread_points", 0.0))
    except (TypeError, ValueError) as exc:
        raise ValueError("max_spread_points must be a finite non-negative number") from exc
    if not math.isfinite(cap) or cap < 0:
        raise ValueError("max_spread_points must be a finite non-negative number")
    normalized["max_spread_points"] = cap
    normalized["require_spread_limit"] = True
    return normalized
