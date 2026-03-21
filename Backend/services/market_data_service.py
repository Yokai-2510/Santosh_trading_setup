"""market_data_service — manages candle data, live feed, and indicator computation.

Serves as a clean data layer for both live trading and backtesting.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from data.candle_service import CandleService
from data.indicators import (
    build_dataframe,
    compute_adx,
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_rsi,
    compute_supertrend,
    compute_vwap,
)
from data.live_candle_builder import LiveCandleBuilder


class MarketDataService:
    """Provides candle data and indicator computations."""

    def __init__(self, headers: Dict[str, str], timeout: int = 20) -> None:
        self.candle_service = CandleService(headers=headers, timeout_seconds=timeout)
        self._live_builder: Optional[LiveCandleBuilder] = None

    def set_live_builder(self, builder: LiveCandleBuilder) -> None:
        self._live_builder = builder
        self.candle_service.set_live_builder(builder)

    def get_candles(self, instrument_key: str, timeframe: int) -> List[dict]:
        return self.candle_service.get_candles(instrument_key, timeframe)

    def compute_indicators(self, candles: List[dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """Compute all enabled indicators and return values dict."""
        if not candles:
            return {}

        frame = build_dataframe(candles)
        if len(frame) < 5:
            return {}

        result: Dict[str, Any] = {}

        # RSI
        rsi_cfg = config.get("rsi", {})
        if rsi_cfg.get("enabled", True):
            rsi = compute_rsi(frame["close"], int(rsi_cfg.get("period", 14)))
            result["rsi"] = float(rsi.iloc[-1])

        # EMA
        vol_cfg = config.get("volume_vs_ema", {})
        if vol_cfg.get("enabled", True):
            period = int(vol_cfg.get("ema_period", 20))
            vol_ema = compute_ema(frame["volume"], period)
            result["volume"] = float(frame["volume"].iloc[-1])
            result["volume_ema"] = float(vol_ema.iloc[-1])

        # ADX
        adx_cfg = config.get("adx", {})
        if adx_cfg.get("enabled", False):
            adx = compute_adx(frame["high"], frame["low"], frame["close"],
                              int(adx_cfg.get("period", 14)))
            result["adx"] = float(adx.iloc[-1])

        # MACD
        macd_cfg = config.get("macd", {})
        if macd_cfg.get("enabled", False):
            macd_df = compute_macd(frame["close"],
                                   int(macd_cfg.get("fast_period", 12)),
                                   int(macd_cfg.get("slow_period", 26)),
                                   int(macd_cfg.get("signal_period", 9)))
            result["macd"] = float(macd_df["macd"].iloc[-1])
            result["macd_signal"] = float(macd_df["signal"].iloc[-1])
            result["macd_histogram"] = float(macd_df["histogram"].iloc[-1])

        # VWAP
        vwap_cfg = config.get("vwap", {})
        if vwap_cfg.get("enabled", False):
            vwap = compute_vwap(frame["high"], frame["low"], frame["close"], frame["volume"])
            result["vwap"] = float(vwap.iloc[-1])

        # Supertrend
        st_cfg = config.get("supertrend", {})
        if st_cfg.get("enabled", False):
            st_df = compute_supertrend(frame["high"], frame["low"], frame["close"],
                                       int(st_cfg.get("period", 10)),
                                       float(st_cfg.get("multiplier", 3.0)))
            result["supertrend"] = float(st_df["supertrend"].iloc[-1])
            result["supertrend_direction"] = int(st_df["direction"].iloc[-1])

        # Bollinger Bands
        bb_cfg = config.get("bollinger_bands", {})
        if bb_cfg.get("enabled", False):
            bb_df = compute_bollinger_bands(frame["close"],
                                            int(bb_cfg.get("period", 20)),
                                            float(bb_cfg.get("std_dev", 2.0)))
            result["bb_upper"] = float(bb_df["upper"].iloc[-1])
            result["bb_middle"] = float(bb_df["middle"].iloc[-1])
            result["bb_lower"] = float(bb_df["lower"].iloc[-1])

        return result
