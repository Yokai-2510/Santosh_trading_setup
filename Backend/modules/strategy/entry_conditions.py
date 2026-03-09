"""
entry_conditions — strategy entry gate evaluation.
"""

from __future__ import annotations

from typing import Any, Dict, List

from modules.indicators.technical_indicators import evaluate_entry_indicators


def evaluate_entry_signal(candles: List[dict], strategy_cfg: Dict[str, Any]) -> Dict[str, Any]:
    entry_cfg = strategy_cfg.get("entry_conditions", {})
    return evaluate_entry_indicators(candles, entry_cfg)
