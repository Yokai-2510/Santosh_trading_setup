# Technical Implementation — System Architecture

## 1. Architecture Overview

The system is a single-process Python application composed of three layers:

```
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND (CTK GUI)                                             │
│  MainWindow → Sidebar → Views (Dashboard, Config, Orders, Logs) │
│  Reads RuntimeState | Sends commands via BotBridge              │
├─────────────────────────────────────────────────────────────────┤
│  BRIDGE LAYER                                                   │
│  BotBridge: starts/stops bot thread, exposes RuntimeState       │
│  RuntimeState: thread-safe shared state (SSOT)                  │
├─────────────────────────────────────────────────────────────────┤
│  BACKEND (Strategy Engine — runs in daemon thread)              │
│  run_bot.py → Engine → Modules → Broker API wrappers            │
└─────────────────────────────────────────────────────────────────┘
```

The GUI and bot engine live in the same process. The bot runs in a background thread.
Communication is via a shared `RuntimeState` object protected by a threading lock.
The GUI polls `RuntimeState` every second via CTK's `after()` mechanism.

---

## 2. Directory Structure

```
santosh_trading_setup/
├── run.py                              # Single top-level launcher (GUI or headless)
├── requirements.txt
├── llm_guidelines.txt
├── Docs/
│   ├── Strategy.md                     # Complete strategy specification
│   ├── Technical_Implementation.md     # This file
│   ├── TDD.md                          # Test plan and coverage targets
│   └── Project_Plan.md                 # Overhaul roadmap
│
├── Backend/
│   ├── run_bot.py                      # Headless bot entry point (linear orchestrator)
│   ├── brokers/
│   │   └── upstox/
│   │       ├── auth.py                 # OAuth helpers (pure functions)
│   │       ├── market_data.py          # LTP quote API
│   │       ├── orders.py               # Place / status / cancel order
│   │       ├── order_modify_v3.py      # Modify Order V3
│   │       ├── positions.py            # Short-term positions polling
│   │       ├── instruments.py          # Master contract download
│   │       └── historical_v3.py        # Historical candle V3
│   │
│   ├── modules/
│   │   ├── auth/
│   │   │   └── login_manager.py        # Cache-first Upstox auth flow
│   │   │
│   │   ├── data/
│   │   │   ├── candle_service.py       # Rolling candle cache + refresh
│   │   │   └── instrument_filter.py    # Master contract → option universe
│   │   │
│   │   ├── indicators/
│   │   │   └── technical_indicators.py # RSI, EMA, MACD, ADX computations
│   │   │
│   │   ├── strategy/
│   │   │   ├── engine.py               # Cycle coordinator (thin orchestrator)
│   │   │   ├── entry_conditions.py     # Entry signal gate
│   │   │   ├── exit_conditions.py      # SL / target / trailing / time exit
│   │   │   ├── instrument_selection.py # Contract resolver
│   │   │   ├── order_lifecycle.py      # Order state machine
│   │   │   └── position_sync.py        # Manual exit detection
│   │   │
│   │   ├── state/
│   │   │   └── runtime_state.py        # Thread-safe shared state (SSOT)
│   │   │
│   │   ├── risk/
│   │   │   └── risk_guard.py           # Daily loss / position limits
│   │   │
│   │   └── utils/
│   │       ├── config_loader.py        # Load + validate all configs
│   │       ├── logger.py               # Logger setup
│   │       └── market_hours.py         # Market open/close helpers
│   │
│   └── source/
│       ├── credentials.json            # API keys (not committed)
│       ├── credentials_example.json    # Template
│       ├── strategy_config.json        # Strategy parameters (SSOT)
│       └── system_config.json          # Runtime / broker / market config (SSOT)
│
├── Frontend/
│   ├── gui.py                          # CTK launcher
│   ├── app.py                          # MainWindow: sidebar + view container
│   ├── bridge/
│   │   └── bot_bridge.py               # Start/stop bot thread; expose RuntimeState
│   ├── views/
│   │   ├── dashboard_view.py           # Live position, signal, stats, controls
│   │   ├── config_view.py              # Strategy + System + Credentials editor
│   │   ├── orders_view.py              # Order history table
│   │   └── logs_view.py                # Scrolling log tail
│   └── widgets/
│       ├── position_card.py            # Active position display widget
│       ├── signal_panel.py             # Indicator values + pass/fail badges
│       ├── stat_card.py                # Metric tile (P&L, cycles, etc.)
│       └── status_bar.py               # Bottom bar: mode, market status, last update
│
├── tests/
│   ├── unit/
│   │   ├── test_technical_indicators.py
│   │   ├── test_entry_conditions.py
│   │   ├── test_exit_conditions.py
│   │   ├── test_instrument_selection.py
│   │   ├── test_order_lifecycle.py
│   │   ├── test_position_sync.py
│   │   ├── test_config_loader.py
│   │   └── test_risk_guard.py
│   ├── integration/
│   │   └── test_engine_cycle.py
│   └── fixtures/
│       ├── sample_candles.py
│       ├── sample_universe.py
│       └── sample_positions.py
│
└── Backend/data/
    ├── cache/
    │   ├── master.json.gz
    │   ├── master.json
    │   ├── index_option_universe.json
    │   └── access_token.json
    └── logs/
        └── bot.log
```

---

## 3. Backend Module Responsibilities

### 3.1 `run_bot.py` — Linear Orchestrator

Hard constraints (from llm_guidelines):
- No function definitions
- No class definitions
- No business logic
- No conditional orchestration

Execution order (top-to-bottom):
```
parse_args()
build_paths()
load_all_configs()
setup_logger()
validate_risk_config()
initialize_engine()
run_engine()             # blocks until stop / KeyboardInterrupt
```

---

### 3.2 `brokers/upstox/` — Pure API Wrappers

Each file is a single-responsibility REST wrapper. All functions:
- Accept `headers: Dict[str, str]` as first arg (bearer token)
- Return a typed dict result with `success: bool`, `status_code: int`, `response: dict`
- Never raise — catch all exceptions and return `success=False`
- Never hold state — pure functions only

| File | Responsibility |
|---|---|
| `auth.py` | Load/save token cache, fetch OAuth code, exchange for token |
| `market_data.py` | `get_ltp(keys)` → `{key: float}` |
| `orders.py` | `place_order()`, `get_order_status()`, `cancel_order()` |
| `order_modify_v3.py` | `modify_order_v3()` — V3 HFT endpoint |
| `positions.py` | `get_positions()` → list of position dicts |
| `instruments.py` | `download_master_contract()` → bool |
| `historical_v3.py` | `fetch_historical_candles_v3()` → normalized candle list |

---

### 3.3 `modules/state/runtime_state.py` — SSOT

Central shared state. Written by the bot engine. Read by the GUI.

```python
@dataclass
class PositionSnapshot:
    instrument_token: str
    trading_symbol: str
    quantity: int
    entry_price: float
    current_ltp: float
    unrealised_pnl: float
    entry_time_epoch: float
    peak_ltp: float           # for trailing SL tracking
    status: str               # ACTIVE | CLOSED

@dataclass
class WorkingOrderSnapshot:
    order_id: str
    instrument_token: str
    trading_symbol: str
    price: float
    quantity: int
    status: str

@dataclass
class SignalSnapshot:
    ok: bool
    checks: Dict[str, bool]
    values: Dict[str, float]
    evaluated_at_epoch: float

@dataclass
class RuntimeState:
    # Bot lifecycle
    bot_running: bool
    last_cycle_epoch: float
    cycle_count: int
    error_message: str

    # Auth
    auth_ok: bool
    auth_message: str

    # Market
    market_active: bool

    # Strategy state
    active_position: Optional[PositionSnapshot]
    working_order: Optional[WorkingOrderSnapshot]
    last_signal: Optional[SignalSnapshot]

    # Session P&L
    session_realised_pnl: float
    session_trade_count: int
    last_closed_epoch: float
```

Access pattern:
```python
state.update(lambda s: s.cycle_count += 1)    # write (lock held)
snapshot = state.read()                         # read (lock held, returns copy)
```

---

### 3.4 `modules/strategy/engine.py` — Cycle Coordinator

The engine is a **thin orchestrator** — no business logic inside. Each step is a single function call.

```python
def run_once(ctx: EngineContext) -> None:
    refresh_auth_if_needed(ctx)
    market_active = check_market_hours(ctx)
    if not market_active:
        return

    poll_working_order_if_any(ctx)
    poll_manual_exit_if_due(ctx)

    candles = fetch_candles(ctx)
    signal = evaluate_entry_signal(candles, ctx.strategy_cfg)
    update_signal_state(ctx, signal)

    if not signal_allows_entry(ctx, signal):
        return

    spot_ltp = fetch_spot_ltp(ctx)
    contract = resolve_contract(ctx, spot_ltp)
    option_ltp = fetch_option_ltp(ctx, contract)

    action = handle_entry_signal(ctx, contract, option_ltp)
    update_order_state(ctx, action)
```

All logic lives in individual modules, not in the engine itself.

---

### 3.5 `modules/strategy/exit_conditions.py` — Exit Logic

Evaluates whether the active position should be exited this cycle.

```python
def evaluate_exit(
    position: PositionSnapshot,
    current_ltp: float,
    exit_cfg: Dict[str, Any],
    now: datetime,
) -> Optional[ExitSignal]:
    ...

@dataclass
class ExitSignal:
    trigger: str       # "SL" | "TARGET" | "TRAILING_SL" | "TIME" | "SIGNAL_REVERSAL"
    reason: str
    exit_price: float
    order_type: str    # "MARKET" | "SL-M" | "LIMIT"
```

Checks evaluated in priority order:
1. Time-based exit (highest priority — always checked first)
2. Trailing SL (if activated)
3. Hard SL
4. Target

---

### 3.6 `modules/risk/risk_guard.py` — Risk Checks

```python
def is_entry_allowed(state: RuntimeState, risk_cfg: Dict[str, Any]) -> Tuple[bool, str]:
    # Check daily max loss
    # Check max trades per session
    # Returns (allowed, reason)
```

If `risk.enabled = false` in config, all checks pass by default.

---

### 3.7 `modules/utils/market_hours.py`

Extracted from `engine.py`. Pure functions only.

```python
def is_market_active(market_cfg: Dict[str, Any]) -> bool
def time_until_open(market_cfg: Dict[str, Any]) -> timedelta
def is_expiry_today(expiry_date: str) -> bool
```

---

## 4. Config Schema (SSOT)

### `system_config.json`

```json
{
  "broker": {
    "name": "upstox",
    "api_timeouts": {
      "request_seconds": 15,
      "order_seconds": 10,
      "positions_seconds": 10,
      "historical_seconds": 20,
      "master_contract_seconds": 60
    }
  },
  "auth": {
    "token_reset_time": "03:30",
    "token_expiry_buffer_min": 5,
    "headless": true,
    "playwright_args": [
      "--disable-web-security",
      "--no-sandbox",
      "--disable-blink-features=AutomationControlled"
    ]
  },
  "runtime": {
    "mode": "paper",
    "loop_interval_seconds": 5,
    "log_level": "INFO",
    "ignore_market_hours": false
  },
  "market": {
    "exchange": "NFO",
    "open": "09:15:00",
    "close": "15:30:00"
  },
  "risk": {
    "enabled": false,
    "max_daily_loss": 5000.0,
    "max_trades_per_session": 10
  },
  "data": {
    "paths": {
      "cache": "Backend/data/cache",
      "logs": "Backend/data/logs"
    }
  }
}
```

### `strategy_config.json`

```json
{
  "entry_conditions": {
    "timeframe_minutes": 3,
    "min_candles_required": 60,
    "rsi": {
      "enabled": true,
      "period": 14,
      "operator": ">",
      "threshold": 60.0
    },
    "volume_vs_ema": {
      "enabled": true,
      "ema_period": 20
    },
    "macd": {
      "enabled": false,
      "fast_period": 12,
      "slow_period": 26,
      "signal_period": 9,
      "min_histogram": 0.0
    },
    "adx": {
      "enabled": false,
      "period": 14,
      "min_threshold": 20.0
    }
  },
  "instrument_selection": {
    "underlying": "NIFTY",
    "expiry_choice": "current",
    "option_type": "CE",
    "strike_mode": "ATM",
    "strike_offset": 0,
    "quantity_mode": "lots",
    "lots": 1
  },
  "order_execution": {
    "order_type": "LIMIT",
    "product": "D",
    "validity": "DAY",
    "entry_price_source": "ltp",
    "tick_size": 0.05,
    "disclosed_quantity": 0,
    "trigger_price": 0.0,
    "is_amo": false
  },
  "exit_conditions": {
    "stoploss": {
      "enabled": true,
      "type": "percent",
      "value": 30.0,
      "order_type": "SL-M",
      "place_sl_order_on_fill": false
    },
    "target": {
      "enabled": false,
      "type": "percent",
      "value": 50.0,
      "order_type": "LIMIT"
    },
    "trailing_sl": {
      "enabled": false,
      "activate_at_percent": 20.0,
      "trail_by_percent": 10.0
    },
    "time_based_exit": {
      "enabled": false,
      "exit_at_time": "15:15:00"
    }
  },
  "order_modify": {
    "modify_on_reentry_signal": true,
    "modify_cooldown_seconds": 10,
    "only_improve_price": true
  },
  "position_management": {
    "reentry_wait_seconds_after_close": 30,
    "manual_exit_detection_enabled": true,
    "manual_exit_poll_interval_seconds": 1
  }
}
```

### `credentials.json`

```json
{
  "upstox": {
    "api_key": "",
    "api_secret": "",
    "redirect_uri": "",
    "totp_key": "",
    "mobile_no": "",
    "pin": ""
  }
}
```

---

## 5. Frontend Architecture

### 5.1 Layout

```
┌───────────────────────────────────────────────────────────────┐
│  HEADER: "Santosh Trading" │ Mode Badge │ Market Status Chip   │
├──────────┬────────────────────────────────────────────────────┤
│          │                                                      │
│  SIDEBAR │  CONTENT AREA                                        │
│          │                                                      │
│  [●] Dashboard             │  (active view rendered here)       │
│  [ ] Config                │                                    │
│  [ ] Orders                │                                    │
│  [ ] Logs                  │                                    │
│  [ ] About                 │                                    │
│          │                                                      │
├──────────┴────────────────────────────────────────────────────┤
│  STATUS BAR: Bot status │ Auth status │ Last update HH:MM:SS   │
└───────────────────────────────────────────────────────────────┘
```

### 5.2 Dashboard View

Top row — Bot Controls:
- `[Start Bot]` / `[Stop Bot]` toggle button
- `[Force Login]` button — triggers fresh Upstox OAuth
- `[Run Once]` button — execute single cycle

Live Position Card (shown only when `active_position` is not None):
- Symbol, Strike, Expiry, Option Type
- Entry Price | Current LTP | Unrealised P&L (colored green/red)
- Quantity | Lots
- Entry time elapsed

Working Order Card (shown only when `working_order` is not None):
- Order ID, Symbol, Price, Status
- `[Cancel Order]` button

Signal Panel (last signal values):
- Each indicator: name | current value | threshold | Pass/Fail badge
- Signal timestamp

Stats Row:
- Session Realised P&L
- Trade count today
- Cycle count
- Last closed reason

### 5.3 Config View

Three sub-sections via inner tab or segmented button:
- **Credentials** — API Key, Secret, Redirect URI, TOTP, Mobile, PIN
- **Strategy** — All `strategy_config.json` fields with proper input types
- **System** — All `system_config.json` runtime/market/risk fields

Each section has a `[Save]` button. No auto-save.
Config changes take effect on next bot cycle (engine reads config each cycle or on restart).

### 5.4 Orders View

Table columns: Time | Symbol | Side | Qty | Price | Status | P&L
Shows session history (in-memory, not persisted).
Sorted newest-first.

### 5.5 Logs View

Scrolling text panel showing last N lines from `bot.log`.
Auto-scrolls to bottom.
`[Clear]` button to wipe display (not the file).
Log level filter: ALL / INFO / WARNING / ERROR

---

## 6. Bridge Layer

### `Frontend/bridge/bot_bridge.py`

Owns the bot thread lifecycle:

```python
class BotBridge:
    def start_bot(self, config_paths: ConfigPaths) -> None
    def stop_bot(self) -> None
    def run_once(self, config_paths: ConfigPaths) -> None
    def force_login(self, config_paths: ConfigPaths) -> None
    def get_state(self) -> RuntimeState      # thread-safe read
    def is_running(self) -> bool
```

The GUI calls `bridge.get_state()` every second via `app.after(1000, refresh_ui)`.

---

## 7. Backend Flow (Full Sequence)

```
Startup:
  1. Parse CLI args (--once, --force-login)
  2. build_paths()
  3. load_all_configs()  →  validate_strategy_config() + validate_system_config()
  4. setup_logger()
  5. initialize_runtime_state()
  6. authenticate_upstox()  →  cache-first token load or fresh Playwright login
  7. build_index_option_universe()  →  download master.json.gz, filter NIFTY/BANKNIFTY
  8. bootstrap_candles()  →  fetch one month of historical candles for spot index
  9. Log "Engine ready"

Per-cycle (every loop_interval_seconds):
  1. check_market_hours()  →  skip if closed (unless ignore_market_hours)
  2. poll_working_order_if_any()  →  check fill/reject status
  3. evaluate_exit_conditions_if_position()  →  SL / target / time checks
  4. poll_manual_exit_if_due()  →  broker positions diff
  5. check_risk_guard()  →  daily loss, trade count
  6. fetch_spot_ltp()
  7. refresh_candles()  →  rolling 2-day refresh merged into cache
  8. evaluate_entry_signal(candles, strategy_cfg)
  9. if signal.ok and no position:
       resolve_contract()
       fetch_option_ltp()
       handle_entry_signal()  →  place or modify order
  10. update_runtime_state()  →  write all state to RuntimeState

Shutdown:
  1. engine.stop()  →  set running=False
  2. Log "Engine stopped"
```

---

## 8. Upstox APIs Used

| API | Endpoint | Module |
|---|---|---|
| OAuth code fetch | Playwright browser automation | `auth.py` |
| Token exchange | `POST /login/authorization/token` | `auth.py` |
| LTP quote | `GET /v3/market-quote/ltp` | `market_data.py` |
| Historical candles | `GET /v3/historical-candle/{key}/{unit}/{interval}/{to}/{from}` | `historical_v3.py` |
| Place order | `POST /v3/order/place` (HFT endpoint) | `orders.py` |
| Order status | `GET /v2/order/details` | `orders.py` |
| Cancel order | `DELETE /v3/order/cancel` (HFT endpoint) | `orders.py` |
| Modify order | `PUT /v3/order/modify` (HFT endpoint) | `order_modify_v3.py` |
| Positions | `GET /v2/portfolio/short-term-positions` | `positions.py` |
| Master contract | `GET assets.upstox.com/.../NSE.json.gz` | `instruments.py` |

---

## 9. Concurrency Model

- Main thread: CTK GUI event loop (or idle loop in headless mode)
- Bot thread: daemon thread, runs `engine.run_forever()`
- `RuntimeState` access protected by `threading.Lock`
- No shared mutable state outside of `RuntimeState`
- Thread names: `"santosh-bot-thread"`
