"""
Raw WebSocket diagnostic — prints every frame the server sends
before/after subscription, including close codes and raw bytes.

Run from repo root:
    python test_ws_raw.py
"""

import json
import sys
import time
import uuid
from pathlib import Path

TOKEN_FILE = Path(__file__).parent / "Backend" / "data" / "cache" / "access_token.json"

# ── Token ─────────────────────────────────────────────────────────────────────
with open(TOKEN_FILE) as f:
    token_data = json.load(f)
ACCESS_TOKEN = token_data["access_token"]
print(f"Token (first 30): {ACCESS_TOKEN[:30]}...")

# ── Imports ───────────────────────────────────────────────────────────────────
import ssl
import websocket

INSTRUMENT = "NSE_INDEX|Nifty 50"
WS_URL     = "wss://api.upstox.com/v3/feed/market-data-feed"

# Try different subscription payload modes
SUBSCRIBE_MSG = json.dumps({
    "guid": str(uuid.uuid4()),
    "method": "sub",
    "data": {
        "mode": "full",
        "instrumentKeys": [INSTRUMENT],
    },
}).encode("utf-8")

print(f"Subscribe payload : {SUBSCRIBE_MSG.decode()}\n")

msg_count = 0

def on_open(ws):
    print(">>> WS OPEN")
    print(f"    Sending subscribe as BINARY ({len(SUBSCRIBE_MSG)} bytes)...")
    ws.send(SUBSCRIBE_MSG, opcode=websocket.ABNF.OPCODE_BINARY)

def on_message(ws, message):
    global msg_count
    msg_count += 1

    if isinstance(message, bytes):
        print(f"\n>>> MESSAGE #{msg_count}  ({len(message)} bytes, binary)")
        print(f"    raw hex (first 80 bytes): {message[:80].hex()}")

        # Try protobuf decode
        try:
            sys.path.insert(0, str(Path(__file__).parent / "Backend"))
            from upstox_client.feeder.proto import MarketDataFeedV3_pb2 as pb
            feed = pb.FeedResponse.FromString(message)
            print(f"    Proto decode OK | type={feed.type} | feeds={list(feed.feeds.keys())}")
            for ikey, ff in feed.feeds.items():
                print(f"      instrument: {ikey}")
                if ff.HasField("indexFF"):
                    iff = ff.indexFF
                    ohlc_list = list(iff.marketOHLC.ohlc)
                    print(f"        indexFF | ltp={iff.ltpc.ltp} | ohlc entries={len(ohlc_list)}")
                    for o in ohlc_list:
                        print(f"          interval={o.interval!r}  open={o.open}  high={o.high}  low={o.low}  close={o.close}  vol={o.vol}  ts={o.ts!r}")
                elif ff.HasField("marketFF"):
                    mff = ff.marketFF
                    ohlc_list = list(mff.marketOHLC.ohlc)
                    print(f"        marketFF | ltp={mff.ltpc.ltp} | vtt={mff.vtt} | ohlc entries={len(ohlc_list)}")
                    for o in ohlc_list:
                        print(f"          interval={o.interval!r}  open={o.open}  high={o.high}  low={o.low}  close={o.close}  vol={o.vol}  ts={o.ts!r}")
        except Exception as e:
            print(f"    Proto decode FAILED: {e}")
    else:
        # Text frame
        print(f"\n>>> MESSAGE #{msg_count}  (text): {message[:500]}")

def on_error(ws, error):
    print(f"\n>>> ERROR: {type(error).__name__}: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"\n>>> CLOSE  code={close_status_code}  msg={close_msg!r}")
    print(f"    Total messages received before close: {msg_count}")


ws = websocket.WebSocketApp(
    WS_URL,
    header={"Authorization": f"Bearer {ACCESS_TOKEN}"},
    on_open=on_open,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close,
)

print(f"Connecting to {WS_URL} ...\n")
sslopt = {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}

# Run for 20s then stop
import threading
def stopper():
    time.sleep(20)
    print("\n[stopper] 20s elapsed, closing...")
    ws.close()
threading.Thread(target=stopper, daemon=True).start()

ws.run_forever(sslopt=sslopt)
print("\nDone.")
