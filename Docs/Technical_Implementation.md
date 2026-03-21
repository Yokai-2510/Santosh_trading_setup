# Technical Implementation Details

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND (CTK GUI)                                             │
│  App → Sidebar → Views (Dashboard, Analytics, Strategy, etc.)   │
│  Theme system | Password gate | Reads RuntimeState              │
├─────────────────────────────────────────────────────────────────┤
│  BRIDGE + SERVICES LAYER                                        │
│  BotBridge → LiveTradingService → TradingEngine                 │
│  BacktestService | ServiceRegistry (background polling)         │
│  StateStore: thread-safe shared state (SSOT)                    │
├─────────────────────────────────────────────────────────────────┤
│  BACKEND (Strategy Engine — runs in daemon thread)              │
│  engine.py → strategy/ → orders/ → data/ → brokers/upstox/     │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Directory Structure

```
santosh_trading_setup/
├── Backend/
│   ├── main/engine.py              # TradingEngine orchestrator
│   ├── main/paper_executor.py      # Simulated fills
│   ├── main/live_executor.py       # Real broker orders
│   ├── strategy/                   # Pure strategy logic
│   │   ├── pre_checks.py, entry_conditions.py
│   │   ├── exit_conditions.py, instrument_selection.py
│   │   └── risk_guard.py
│   ├── orders/                     # Order building + position SSOT
│   │   ├── order_builder.py, position_manager.py
│   ├── data/                       # Market data + indicators
│   │   ├── indicators.py           # RSI, EMA, MACD, ADX, VWAP, Supertrend, BB, OI
│   │   ├── candle_service.py, live_candle_builder.py
│   │   └── instrument_filter.py
│   ├── services/                   # Orchestration layer
│   │   ├── service_registry.py, live_trading_service.py
│   │   ├── market_data_service.py, backtest_service.py
│   ├── backtesting/                # Walk-forward backtesting
│   ├── brokers/upstox/             # API wrappers (pure functions)
│   ├── utils/                      # Config, state, auth, logging
│   ├── configs/                    # JSON config files
│   └── data_store/                 # Runtime cache + logs
├── Frontend/
│   ├── gui.py, app.py              # Entry point + main window
│   ├── theme/                      # colors.py, fonts.py, styles.py
│   ├── bridge/bot_bridge.py        # GUI ↔ Backend bridge
│   ├── views/                      # 10 sidebar views
│   └── widgets/                    # Reusable components
├── tests/, docs/
└── requirements.txt
```

## 3. Upstox API Integration

### Authentication Flow
1. Load cached token from `data_store/cache/access_token.json`
2. If expired → Playwright browser automation for OAuth2
3. Automated: mobile → TOTP → PIN → authorize → redirect capture
4. Token stored with expiry; reset at configurable time (default 03:30)

### API Endpoints
| Endpoint | Module | Purpose |
|----------|--------|---------|
| `POST /login/authorization/token` | auth.py | Token exchange |
| `GET /v3/historical-candle/...` | historical_v3.py | OHLCV data |
| `POST /v3/order/place` | orders.py | Place orders |
| `PUT /v3/order/modify` | order_modify_v3.py | Modify orders |
| `DELETE /v3/order/cancel` | orders.py | Cancel orders |
| `GET /v2/portfolio/short-term-positions` | positions.py | Position polling |
| `GET /v2/market-quote/ltp` | market_data.py | Last traded price |
| `GET assets.upstox.com/...` | instruments.py | Master contracts |

### WebSocket v3
- Protobuf binary format for market data
- Subscribes to index keys (e.g., `NSE_INDEX|Nifty 50`)
- Modes: LTPC, Full Quote, Option Greeks
- Auto-reconnect on disconnect

## 4. Position Manager State Machine

```python
class PositionManager:
    def on_entry_placed(...)    # IDLE → PENDING_ENTRY
    def on_entry_filled(...)    # PENDING_ENTRY → ACTIVE
    def on_entry_rejected(...)  # PENDING_ENTRY → IDLE
    def on_exit_placed(...)     # ACTIVE → PENDING_EXIT
    def on_manual_exit(...)     # ACTIVE → CLOSED
    def on_exit_filled(...)     # PENDING_EXIT → CLOSED
    def cleanup()               # CLOSED → IDLE (returns ClosedTrade)
```

### PositionData SSOT
```python
@dataclass
class PositionData:
    status: PositionStatus
    # Instrument: token, symbol, underlying, expiry, option_type, strike, lot_size, tick_size
    # Entry: order_id, price, quantity, time_epoch
    # Live: current_ltp, peak_ltp, unrealised_pnl
    # Exit: order_id, price, time_epoch, reason, realised_pnl
    # Working Order: id, price, status, created/modified_epoch
```

## 5. Exit Condition Evaluation

Priority order (first match wins):
1. **Time-based** — Hard cutoff at configured time
2. **Trailing SL** — After activation threshold, trail from peak
3. **Hard SL** — Fixed stop-loss (percent/points/price)
4. **Target** — Profit target (percent/points)

## 6. Indicator Functions

All pure functions in `data/indicators.py`:

| Function | Inputs | Output |
|----------|--------|--------|
| `compute_rsi` | close, period | Series |
| `compute_ema` | series, period | Series |
| `compute_macd` | close, fast, slow, signal | DataFrame |
| `compute_adx` | high, low, close, period | Series |
| `compute_vwap` | high, low, close, volume | Series |
| `compute_supertrend` | high, low, close, period, mult | DataFrame |
| `compute_bollinger_bands` | close, period, std_dev | DataFrame |
| `compute_oi_change` | oi_series | Series |

`evaluate_entry_indicators()` runs all enabled checks with AND logic.

## 7. Config Schema

### system_config.json
- `broker.api_timeouts` — per-endpoint timeout seconds
- `auth` — headless mode, token reset time, Playwright args
- `runtime` — mode (paper/live), loop interval, log level, ignore market hours
- `market` — exchange, open/close times
- `risk` — enabled flag, max daily loss, max trades

### strategy_config.json
- `entry_conditions` — timeframe, RSI, Volume EMA, ADX, VWAP, Supertrend, BB, MACD
- `instrument_selection` — underlying, expiry, option type, strike mode, lots
- `order_execution` — order type, product, tick size
- `exit_conditions` — SL, target, trailing SL, time exit
- `order_modify` — re-entry signal modify, cooldown, improve-only
- `position_management` — re-entry wait, manual exit detection

## 8. Frontend Architecture

### Password Gate
SHA-256 hashed password in `data_store/app_password.json`. Shown before main UI.

### Sidebar Navigation (3 sections)
- **MAIN**: Dashboard, Trades, Analytics, Logs
- **CONFIG**: Strategy, System, Credentials, Connections
- **TOOLS**: Status, Backtesting

### Theme System
Centralized in `Frontend/theme/`:
- `colors.py` — all color constants
- `fonts.py` — font family/size definitions
- `styles.py` — reusable widget factory functions

### Refresh Loop
Every 1s: `bridge.get_state()` → update header, status bar, active view.

## 9. Concurrency Model

- Main thread: CTK GUI event loop
- Bot thread: daemon thread running `engine.run_forever()`
- Background services: daemon threads for position polling, capital, health
- `StateStore` access protected by `threading.Lock`
- `read()` returns `deepcopy` — no shared mutable references
- Exit overrides from GUI protected by separate lock
