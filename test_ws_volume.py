"""
Standalone WebSocket volume test.

Connects to Upstox v3 market data feed for NSE_INDEX|Nifty 50,
prints every OHLCV tick for 30 seconds, then summarises the
accumulated candle data from LiveCandleBuilder.

Run from the repo root:
    python test_ws_volume.py
"""

import json
import sys
import time
from pathlib import Path

# ── Resolve paths ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
TOKEN_FILE = ROOT / "Backend" / "data" / "cache" / "access_token.json"
sys.path.insert(0, str(ROOT / "Backend"))

# ── Load access token ─────────────────────────────────────────────────────────
def load_token() -> str:
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    token = data.get("access_token", "")
    if not token:
        sys.exit("ERROR: access_token.json has no access_token field")
    print(f"[TOKEN] valid_until={data.get('valid_until_ist')} | token[:20]={token[:20]}...")
    return token

# ── Import our modules ────────────────────────────────────────────────────────
from brokers.upstox.websocket_v3 import UpstoxMarketFeedV3
from modules.data.live_candle_builder import LiveCandleBuilder

# ── Instrument to test ────────────────────────────────────────────────────────
INSTRUMENT = "NSE_INDEX|Nifty 50"
TIMEFRAME  = 3   # minutes — matches strategy default

# ── Counters ──────────────────────────────────────────────────────────────────
tick_count = 0
print_limit = 10   # print first N ticks in full, then only every 10th

def on_feed(instrument_key: str, feed_data: dict) -> None:
    global tick_count
    tick_count += 1

    # Always feed into the builder
    builder.on_feed(instrument_key, feed_data)

    # Print detail for first few ticks, then occasional
    if tick_count > print_limit and tick_count % 10 != 0:
        return

    ltp      = feed_data.get("ltp", "N/A")
    vtt      = feed_data.get("vtt", "N/A")   # total volume today (market instruments)
    ohlc_lst = feed_data.get("ohlc", [])
    feed_type = feed_data.get("feed_type", "?")

    print(f"\n[TICK #{tick_count}] {instrument_key}  type={feed_type}")
    print(f"  LTP={ltp}  vtt={vtt}")

    if not ohlc_lst:
        print("  ⚠ No OHLC data in this tick")
    else:
        for ohlc in ohlc_lst:
            interval = ohlc.get("interval", "?")
            vol      = ohlc.get("volume", "N/A")
            ts       = ohlc.get("ts",     "N/A")
            print(
                f"  interval={interval:12s}  "
                f"O={ohlc.get('open',0):.2f}  "
                f"H={ohlc.get('high',0):.2f}  "
                f"L={ohlc.get('low',0):.2f}  "
                f"C={ohlc.get('close',0):.2f}  "
                f"VOL={vol}  "
                f"ts={ts}"
            )

def on_connect() -> None:
    print(f"\n✅ WebSocket connected — subscribed to {INSTRUMENT} in FULL mode\n")

def on_disconnect() -> None:
    print("\n⚠ WebSocket disconnected")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    access_token = load_token()

    builder = LiveCandleBuilder()

    ws = UpstoxMarketFeedV3(
        access_token=access_token,
        instrument_keys=[INSTRUMENT],
        mode=UpstoxMarketFeedV3.MODE_FULL,
        on_feed=on_feed,
        on_connect=on_connect,
        on_disconnect=on_disconnect,
    )

    print(f"Connecting to Upstox v3 WebSocket for {INSTRUMENT}...")
    ws.start()

    # Run for 30 seconds
    DURATION = 30
    print(f"Collecting data for {DURATION}s  (first {print_limit} ticks printed in full, then every 10th)\n")
    time.sleep(DURATION)
    ws.stop()

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total ticks received : {tick_count}")

    candles_1m  = builder.get_candles(INSTRUMENT, 1)
    candles_Nm  = builder.get_candles(INSTRUMENT, TIMEFRAME)
    current_vol = builder.get_current_volume(INSTRUMENT)

    print(f"1-min candles built  : {len(candles_1m)}")
    print(f"{TIMEFRAME}-min candles built  : {len(candles_Nm)}")
    print(f"Current candle volume: {current_vol}")

    if candles_1m:
        print(f"\nLast 5 x 1-min candles (with volume):")
        for c in candles_1m[-5:]:
            print(
                f"  {c['timestamp']}  "
                f"O={c['open']:.2f}  H={c['high']:.2f}  "
                f"L={c['low']:.2f}  C={c['close']:.2f}  "
                f"VOL={c['volume']:.0f}"
            )

    if candles_Nm:
        print(f"\nLast 3 x {TIMEFRAME}-min candles (with volume):")
        for c in candles_Nm[-3:]:
            print(
                f"  {c['timestamp']}  "
                f"O={c['open']:.2f}  H={c['high']:.2f}  "
                f"L={c['low']:.2f}  C={c['close']:.2f}  "
                f"VOL={c['volume']:.0f}"
            )

    if not candles_1m:
        print("\n⚠  No 1-min candles accumulated yet.")
        print("   This is normal if the candle boundary didn't roll over in 30s.")
        print("   The current-candle volume is still available (see 'Current candle volume' above).")

    print("\nDone.")
