"""
technical_indicators — indicator calculations and entry status evaluation.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd


def evaluate_entry_indicators(candles: List[dict], entry_cfg: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "ok": False,
        "reason": "",
        "values": {},
        "checks": {},
    }
    if not candles:
        result["reason"] = "No candles available"
        return result

    frame = _build_frame(candles)
    min_required = int(entry_cfg.get("min_candles_required", 60))
    if len(frame) < min_required:
        result["reason"] = f"Insufficient candles: {len(frame)} < {min_required}"
        return result

    checks: List[bool] = []

    # RSI
    rsi_cfg = entry_cfg.get("rsi", {})
    if rsi_cfg.get("enabled", True):
        rsi_series = compute_rsi(frame["close"], int(rsi_cfg.get("period", 14)))
        current_rsi = float(rsi_series.iloc[-1])
        threshold = float(rsi_cfg.get("threshold", 60.0))
        operator = str(rsi_cfg.get("operator", ">")).strip()
        passed = (current_rsi > threshold) if operator == ">" else (current_rsi < threshold)
        result["values"]["rsi"] = current_rsi
        result["checks"]["rsi"] = passed
        checks.append(passed)

    # Volume > EMA
    # Note: NSE_INDEX spot instruments return 0 volume — skip check in that case
    vol_cfg = entry_cfg.get("volume_vs_ema", {})
    if vol_cfg.get("enabled", True):
        period = int(vol_cfg.get("ema_period", 20))
        vol_ema = compute_ema(frame["volume"], period)
        current_volume = float(frame["volume"].iloc[-1])
        current_vol_ema = float(vol_ema.iloc[-1])
        result["values"]["volume"] = current_volume
        result["values"]["volume_ema"] = current_vol_ema
        if current_vol_ema <= 0:
            # No volume data (index instrument) — skip, do not penalise entry
            result["values"]["volume_no_data"] = True
        else:
            passed = current_volume > current_vol_ema
            result["checks"]["volume_vs_ema"] = passed
            checks.append(passed)

    # ADX trend strength
    adx_cfg = entry_cfg.get("adx", {})
    if adx_cfg.get("enabled", False):
        adx_series = compute_adx(
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            period=int(adx_cfg.get("period", 14)),
        )
        current_adx = float(adx_series.iloc[-1])
        threshold = float(adx_cfg.get("threshold", 20.0))
        passed = current_adx >= threshold
        result["values"]["adx"] = current_adx
        result["checks"]["adx"] = passed
        checks.append(passed)

    result["ok"] = all(checks) if checks else False
    result["reason"] = "Entry conditions met" if result["ok"] else "One or more checks failed"
    return result


def _build_frame(candles: List[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(candles)
    frame["open"] = pd.to_numeric(frame["open"], errors="coerce")
    frame["high"] = pd.to_numeric(frame["high"], errors="coerce")
    frame["low"] = pd.to_numeric(frame["low"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame = frame.dropna(subset=["open", "high", "low", "close", "volume"]).copy()
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    return frame


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=max(1, int(period)), adjust=False).mean()


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(up, index=close.index).ewm(alpha=1 / max(period, 1), adjust=False).mean()
    roll_down = pd.Series(down, index=close.index).ewm(alpha=1 / max(period, 1), adjust=False).mean()
    rs = roll_up / roll_down.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(0.0)


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = compute_ema(close, fast)
    ema_slow = compute_ema(close, slow)
    macd = ema_fast - ema_slow
    macd_signal = compute_ema(macd, signal)
    histogram = macd - macd_signal
    return pd.DataFrame({"macd": macd, "signal": macd_signal, "histogram": histogram})


def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    period = max(2, int(period))
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=close.index).ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0.0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=close.index).ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0.0, np.nan)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0.0, np.nan)) * 100
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx.fillna(0.0)
