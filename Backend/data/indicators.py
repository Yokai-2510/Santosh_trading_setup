"""indicators — technical indicator calculations.

Supported: RSI, EMA, MACD, ADX, VWAP, Supertrend, Bollinger Bands, OI Change.
Pure computation functions — no broker or state dependencies.
Reusable by both live engine and backtesting.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Entry indicator evaluation (aggregated gate)
# ---------------------------------------------------------------------------

def evaluate_entry_indicators(candles: List[dict], entry_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate all enabled indicator checks against candle data.

    Returns dict with keys: ok, reason, values, checks.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "reason": "",
        "values": {},
        "checks": {},
    }
    if not candles:
        result["reason"] = "No candles available"
        return result

    frame = build_dataframe(candles)
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
    vol_cfg = entry_cfg.get("volume_vs_ema", {})
    if vol_cfg.get("enabled", True):
        period = int(vol_cfg.get("ema_period", 20))
        vol_ema = compute_ema(frame["volume"], period)
        current_volume = float(frame["volume"].iloc[-1])
        current_vol_ema = float(vol_ema.iloc[-1])
        result["values"]["volume"] = current_volume
        result["values"]["volume_ema"] = current_vol_ema
        if current_vol_ema <= 0:
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

    # VWAP — price above/below VWAP
    vwap_cfg = entry_cfg.get("vwap", {})
    if vwap_cfg.get("enabled", False):
        vwap_series = compute_vwap(frame["high"], frame["low"], frame["close"], frame["volume"])
        current_vwap = float(vwap_series.iloc[-1])
        current_close = float(frame["close"].iloc[-1])
        operator = str(vwap_cfg.get("operator", ">")).strip()
        passed = (current_close > current_vwap) if operator == ">" else (current_close < current_vwap)
        result["values"]["vwap"] = current_vwap
        result["values"]["close_vs_vwap"] = current_close
        result["checks"]["vwap"] = passed
        checks.append(passed)

    # Supertrend — direction check
    st_cfg = entry_cfg.get("supertrend", {})
    if st_cfg.get("enabled", False):
        st_df = compute_supertrend(
            frame["high"], frame["low"], frame["close"],
            int(st_cfg.get("period", 10)),
            float(st_cfg.get("multiplier", 3.0)),
        )
        current_dir = int(st_df["direction"].iloc[-1])
        required_dir = int(st_cfg.get("required_direction", 1))  # 1=bullish, -1=bearish
        passed = current_dir == required_dir
        result["values"]["supertrend"] = float(st_df["supertrend"].iloc[-1])
        result["values"]["supertrend_direction"] = current_dir
        result["checks"]["supertrend"] = passed
        checks.append(passed)

    # Bollinger Bands — price near upper/lower band
    bb_cfg = entry_cfg.get("bollinger_bands", {})
    if bb_cfg.get("enabled", False):
        bb_df = compute_bollinger_bands(
            frame["close"],
            int(bb_cfg.get("period", 20)),
            float(bb_cfg.get("std_dev", 2.0)),
        )
        current_close = float(frame["close"].iloc[-1])
        bb_upper = float(bb_df["upper"].iloc[-1])
        bb_lower = float(bb_df["lower"].iloc[-1])
        bb_middle = float(bb_df["middle"].iloc[-1])
        result["values"]["bb_upper"] = bb_upper
        result["values"]["bb_middle"] = bb_middle
        result["values"]["bb_lower"] = bb_lower
        # Check: price above middle band (bullish) or below (bearish)
        mode = str(bb_cfg.get("mode", "above_middle"))
        if mode == "above_middle":
            passed = current_close > bb_middle
        elif mode == "below_middle":
            passed = current_close < bb_middle
        elif mode == "near_lower":
            band_width = bb_upper - bb_lower
            passed = (current_close - bb_lower) < band_width * 0.2 if band_width > 0 else False
        elif mode == "near_upper":
            band_width = bb_upper - bb_lower
            passed = (bb_upper - current_close) < band_width * 0.2 if band_width > 0 else False
        else:
            passed = True
        result["checks"]["bollinger_bands"] = passed
        checks.append(passed)

    result["ok"] = all(checks) if checks else False
    result["reason"] = "Entry conditions met" if result["ok"] else "One or more checks failed"
    return result


# ---------------------------------------------------------------------------
# DataFrame builder
# ---------------------------------------------------------------------------

def build_dataframe(candles: List[dict]) -> pd.DataFrame:
    """Convert raw candle dicts to a clean, sorted DataFrame."""
    frame = pd.DataFrame(candles)
    for col in ("open", "high", "low", "close", "volume"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(subset=["open", "high", "low", "close", "volume"]).copy()
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    return frame


# ---------------------------------------------------------------------------
# Individual indicator functions
# ---------------------------------------------------------------------------

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


def compute_vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """Volume Weighted Average Price — cumulative within the given data window."""
    typical_price = (high + low + close) / 3.0
    cumulative_tp_vol = (typical_price * volume).cumsum()
    cumulative_vol = volume.cumsum().replace(0.0, np.nan)
    return (cumulative_tp_vol / cumulative_vol).fillna(0.0)


def compute_supertrend(
    high: pd.Series, low: pd.Series, close: pd.Series,
    period: int = 10, multiplier: float = 3.0,
) -> pd.DataFrame:
    """Supertrend indicator. Returns DataFrame with 'supertrend' and 'direction' columns.

    direction: 1 = bullish (price above supertrend), -1 = bearish.
    """
    period = max(2, int(period))
    hl2 = (high + low) / 2.0

    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()

    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    supertrend = pd.Series(np.nan, index=close.index)
    direction = pd.Series(1, index=close.index, dtype=int)

    for i in range(1, len(close)):
        # Lower band
        if lower_band.iloc[i] > lower_band.iloc[i - 1] or close.iloc[i - 1] < lower_band.iloc[i - 1]:
            pass  # keep current lower_band
        else:
            lower_band.iloc[i] = lower_band.iloc[i - 1]

        # Upper band
        if upper_band.iloc[i] < upper_band.iloc[i - 1] or close.iloc[i - 1] > upper_band.iloc[i - 1]:
            pass  # keep current upper_band
        else:
            upper_band.iloc[i] = upper_band.iloc[i - 1]

        # Direction
        if i == 1:
            direction.iloc[i] = 1
        elif supertrend.iloc[i - 1] == upper_band.iloc[i - 1]:
            direction.iloc[i] = -1 if close.iloc[i] > upper_band.iloc[i] else 1 if close.iloc[i] < upper_band.iloc[i] else direction.iloc[i - 1]
        else:
            direction.iloc[i] = 1 if close.iloc[i] < lower_band.iloc[i] else -1 if close.iloc[i] > lower_band.iloc[i] else direction.iloc[i - 1]

        # Fix direction mapping: 1 = bullish (use lower band), -1 = bearish (use upper band)
        # But we store the supertrend line
        if direction.iloc[i] == -1:
            supertrend.iloc[i] = lower_band.iloc[i]
        else:
            supertrend.iloc[i] = upper_band.iloc[i]

    # Remap: direction = 1 means bullish (price above), -1 means bearish
    direction = direction * -1  # flip so 1 = bullish
    return pd.DataFrame({"supertrend": supertrend, "direction": direction})


def compute_bollinger_bands(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands. Returns DataFrame with 'upper', 'middle', 'lower' columns."""
    period = max(2, int(period))
    middle = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return pd.DataFrame({
        "upper": upper.fillna(0.0),
        "middle": middle.fillna(0.0),
        "lower": lower.fillna(0.0),
    })


def compute_oi_change(oi_series: pd.Series) -> pd.Series:
    """Open Interest change (absolute). Returns the period-over-period difference."""
    return oi_series.diff().fillna(0.0)


def compute_oi_change_pct(oi_series: pd.Series) -> pd.Series:
    """Open Interest change (percentage). Returns % change."""
    return oi_series.pct_change().fillna(0.0) * 100.0
