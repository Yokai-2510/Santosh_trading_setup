"""entry_conditions — indicator-based entry signal evaluation.

Pure function — delegates to data.indicators for computation.
Reusable by both live engine and backtesting.
"""

from __future__ import annotations

from typing import Any, Dict, List

from data.indicators import evaluate_entry_indicators


def evaluate_entry_signal(candles: List[dict], strategy_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate entry indicators against candle data.

    Returns dict with keys: ok, reason, values, checks.
    """
    entry_cfg = strategy_cfg.get("entry_conditions", {})
    return evaluate_entry_indicators(candles, entry_cfg)
