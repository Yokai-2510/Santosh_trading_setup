"""
brokers.upstox.websocket_v3 — Upstox v3 market-data WebSocket feed.

Connects to wss://api.upstox.com/v3/feed/market-data-feed using an access
token extracted from the standard auth headers.  Messages are protobuf-encoded
FeedResponse objects decoded via the upstox_client SDK proto stubs.
"""

from __future__ import annotations

import json
import ssl
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional

import websocket

try:
    from upstox_client.feeder.proto import MarketDataFeedV3_pb2 as _pb
    _PROTO_OK = True
except ImportError:
    _pb = None  # type: ignore
    _PROTO_OK = False

_WS_URL = "wss://api.upstox.com/v3/feed/market-data-feed"

FeedCallback = Callable[[str, Dict[str, Any]], None]


class UpstoxMarketFeedV3:
    """
    Thin, thread-safe WebSocket client for Upstox v3 market data.

    Parameters
    ----------
    access_token : str
        Raw Bearer token (without the "Bearer " prefix).
    instrument_keys : list[str]
        Instruments to subscribe on connect.
    mode : str
        Subscription mode — "full" | "ltpc" | "option_greeks"
    on_feed : callable(instrument_key, feed_data)
        Called for every decoded FeedResponse entry.
    on_connect / on_disconnect : optional callables
        Lifecycle hooks.
    """

    MODE_LTPC = "ltpc"
    MODE_FULL = "full"

    def __init__(
        self,
        access_token: str,
        instrument_keys: List[str],
        mode: str = "full",
        on_feed: Optional[FeedCallback] = None,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
    ) -> None:
        self.access_token = access_token
        self.instrument_keys = list(instrument_keys)
        self.mode = mode
        self.on_feed = on_feed
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect

        self._ws: Optional[websocket.WebSocketApp] = None
        self._lock = threading.Lock()
        self._connected = False

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start WebSocket in a background daemon thread (non-blocking)."""
        t = threading.Thread(target=self._run, name="upstox-ws-v3", daemon=True)
        t.start()

    def stop(self) -> None:
        with self._lock:
            ws = self._ws
        if ws:
            try:
                ws.close()
            except Exception:
                pass

    def is_connected(self) -> bool:
        return self._connected

    def subscribe(self, instrument_keys: List[str], mode: Optional[str] = None) -> None:
        """Subscribe additional instruments (while connected)."""
        with self._lock:
            ws = self._ws
        if ws and self._connected:
            msg = _build_request(instrument_keys, "sub", mode or self.mode)
            try:
                ws.send(msg, opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception:
                pass

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(self) -> None:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        sslopt: Dict[str, Any] = {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}
        ws = websocket.WebSocketApp(
            _WS_URL,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        with self._lock:
            self._ws = ws
        # reconnect=5 → auto-reconnect with 5-second delay on drop
        ws.run_forever(sslopt=sslopt, reconnect=5)

    def _on_open(self, ws) -> None:
        self._connected = True
        if self.instrument_keys:
            msg = _build_request(self.instrument_keys, "sub", self.mode)
            try:
                ws.send(msg, opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception:
                pass
        if self.on_connect:
            try:
                self.on_connect()
            except Exception:
                pass

    def _on_message(self, ws, message: bytes) -> None:
        if not _PROTO_OK or not self.on_feed:
            return
        try:
            feed_response = _pb.FeedResponse.FromString(message)
            for instrument_key, full_feed in feed_response.feeds.items():
                feed_data = _extract_feed_data(full_feed)
                if feed_data:
                    try:
                        self.on_feed(instrument_key, feed_data)
                    except Exception:
                        pass
        except Exception:
            pass

    def _on_error(self, ws, error) -> None:
        pass

    def _on_close(self, ws, code, msg) -> None:
        self._connected = False
        if self.on_disconnect:
            try:
                self.on_disconnect()
            except Exception:
                pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_request(instrument_keys: List[str], method: str, mode: str) -> bytes:
    req = {
        "guid": str(uuid.uuid4()),
        "method": method,
        "data": {
            "mode": mode,
            "instrumentKeys": instrument_keys,
        },
    }
    return json.dumps(req).encode("utf-8")


def _extract_feed_data(full_feed) -> Optional[Dict[str, Any]]:
    """Extract OHLCV + LTP data from a FullFeed protobuf object."""
    data: Dict[str, Any] = {}

    try:
        if full_feed.HasField("marketFF"):
            mff = full_feed.marketFF
            if mff.HasField("ltpc"):
                data["ltp"] = float(mff.ltpc.ltp)
                data["cp"] = float(mff.ltpc.cp)
            data["vtt"] = float(mff.vtt)
            data["feed_type"] = "market"
            data["ohlc"] = _parse_ohlc_list(mff.marketOHLC.ohlc)
            return data

        if full_feed.HasField("indexFF"):
            iff = full_feed.indexFF
            if iff.HasField("ltpc"):
                data["ltp"] = float(iff.ltpc.ltp)
                data["cp"] = float(iff.ltpc.cp)
            data["feed_type"] = "index"
            data["ohlc"] = _parse_ohlc_list(iff.marketOHLC.ohlc)
            return data
    except Exception:
        pass

    return None


def _parse_ohlc_list(ohlc_repeated) -> List[Dict[str, Any]]:
    out = []
    for ohlc in ohlc_repeated:
        out.append({
            "interval": ohlc.interval,
            "open":     float(ohlc.open),
            "high":     float(ohlc.high),
            "low":      float(ohlc.low),
            "close":    float(ohlc.close),
            "volume":   float(ohlc.vol),
            "ts":       ohlc.ts,
        })
    return out
