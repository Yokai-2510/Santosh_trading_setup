# Technical Design Document

## 1. System Overview

Santosh Trading Setup automates index options trading on NSE (NIFTY/BANKNIFTY) via the Upstox broker API. The system evaluates configurable technical indicators on intraday candle data, places entry orders when conditions are met, manages positions with SL/target/trailing, and records trade history.

## 2. Trading Engine (engine.py)

### Cycle Architecture

```
run_once() called every N seconds:
│
├── A. OBSERVE (always runs)
│   ├── A1. Check market active
│   └── A2. Fetch candles + evaluate indicators → push to GUI
│
└── B. ACT (state-dependent)
    ├── B1. Poll pending entry/exit orders (live mode)
    ├── B2. Cleanup closed positions → record trade
    ├── B3. If ACTIVE → evaluate exit conditions
    └── B4. If IDLE + market open + signal OK → prepare + execute entry
```

### Position Lifecycle

```
PositionStatus enum:
  IDLE → on_entry_placed() → PENDING_ENTRY
  PENDING_ENTRY → on_entry_filled() → ACTIVE
  PENDING_ENTRY → on_entry_rejected() → IDLE
  ACTIVE → on_exit_placed() → PENDING_EXIT
  ACTIVE → on_manual_exit() → CLOSED
  PENDING_EXIT → on_exit_filled() → CLOSED
  CLOSED → cleanup() → IDLE (returns ClosedTrade)
```

### PositionData SSOT

Single dataclass tracks the complete position lifecycle:
- **Instrument**: token, symbol, underlying, expiry, option_type, strike, lot_size, tick_size
- **Entry**: order_id, price, quantity, time
- **Live Tracking**: current_ltp, peak_ltp, unrealised_pnl
- **Exit**: order_id, price, time, reason, realised_pnl
- **Working Order**: id, price, status, created/modified timestamps

## 3. Technical Indicators

All indicators are pure functions in `data/indicators.py` — no side effects, no state.

| Function | Inputs | Output |
|----------|--------|--------|
| `compute_rsi` | close, period | Series |
| `compute_ema` | series, period | Series |
| `compute_macd` | close, fast, slow, signal | DataFrame (macd, signal, histogram) |
| `compute_adx` | high, low, close, period | Series |
| `compute_vwap` | high, low, close, volume | Series |
| `compute_supertrend` | high, low, close, period, multiplier | DataFrame (supertrend, direction) |
| `compute_bollinger_bands` | close, period, std_dev | DataFrame (upper, middle, lower) |
| `compute_oi_change` | oi_series | Series |

### Aggregated Gate

`evaluate_entry_indicators()` runs all enabled checks and returns:
```python
{"ok": bool, "reason": str, "values": dict, "checks": dict}
```
All enabled checks must pass (AND logic). The GUI signal panel displays individual check results.

## 4. Data Pipeline

### Historical Data
- Upstox Historical v3 API → 1-minute OHLCV candles → cached locally
- Aggregated to N-minute candles (2, 3, 5 min) by CandleService

### Live Data
- WebSocket v3 (protobuf) → tick-by-tick quotes
- LiveCandleBuilder aggregates ticks into N-minute candles
- CandleService merges historical + live candles seamlessly

### Volume Source
- Index instruments (NIFTY/BANKNIFTY) don't have volume on Upstox
- WebSocket provides real-time tick volume
- yfinance provides historical volume for backtesting

## 5. Order Execution

### Paper Mode
- `PaperExecutor` fills all orders instantly at requested price
- No broker API calls
- Useful for strategy testing

### Live Mode
- `LiveExecutor` delegates to `brokers/upstox/orders.py`
- Supports LIMIT, MARKET, SL, SL-M order types
- Order modify via v3 API for price improvement on re-signal
- Order slicing for quantities exceeding freeze qty

## 6. Services Layer

### ServiceRegistry
Manages background polling services with start/stop lifecycle:

- **PositionPollingService** — Polls broker positions to detect manual exits
- **CapitalService** — Polls funds/margin API for capital tracking
- **HealthCheckService** — Periodic system health verification

### LiveTradingService
Wraps `TradingEngine` + `ServiceRegistry` for the GUI bridge.

### BacktestService
Runs backtests in background threads with progress callbacks.

## 7. Thread Safety

- `StateStore` uses `threading.Lock` for all reads/writes
- `read()` returns `deepcopy` — GUI thread never holds a reference to engine data
- Exit overrides from GUI are protected by a separate lock
- All GUI operations dispatch to daemon threads via `BotBridge`

## 8. Configuration Validation

`config_loader.py` validates all configs at load time:
- Timeframe must be 1, 2, 3, or 5
- Underlying must be NIFTY or BANKNIFTY
- Strike mode must be ATM, ITM, or OTM
- Runtime mode must be paper or live
- Defaults are applied for missing fields
