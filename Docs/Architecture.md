# Architecture

## Overview

Santosh Trading Setup is a modular Indian index options trading bot for NIFTY and BANKNIFTY using the Upstox broker API. It features a dark-themed desktop GUI built with CustomTkinter, a clean layered backend, and a walk-forward backtesting engine.

## Directory Structure

```
santosh_trading_setup/
├── Backend/
│   ├── main/                 # Core engine + executors
│   │   ├── engine.py         # TradingEngine — main orchestrator
│   │   ├── paper_executor.py # Simulated order execution
│   │   └── live_executor.py  # Real broker order execution
│   ├── strategy/             # Strategy logic (pure, no broker deps)
│   │   ├── pre_checks.py     # Market hours, paused, cooldown, risk
│   │   ├── entry_conditions.py
│   │   ├── exit_conditions.py
│   │   ├── instrument_selection.py
│   │   └── risk_guard.py
│   ├── orders/               # Order building + position SSOT
│   │   ├── order_builder.py  # OrderParams construction
│   │   └── position_manager.py # PositionManager state machine
│   ├── data/                 # Market data + indicators
│   │   ├── indicators.py     # RSI, EMA, MACD, ADX, VWAP, Supertrend, BB, OI
│   │   ├── candle_service.py # Historical + live candle merge
│   │   ├── live_candle_builder.py # WebSocket tick → N-min candles
│   │   └── instrument_filter.py  # Master contract download + filter
│   ├── services/             # Orchestration layer
│   │   ├── service_registry.py     # Background service lifecycle
│   │   ├── live_trading_service.py # Engine + services wrapper
│   │   ├── market_data_service.py  # Indicator computation service
│   │   └── backtest_service.py     # Background backtest runner
│   ├── backtesting/          # Walk-forward backtesting
│   │   ├── backtest_engine.py
│   │   ├── data_loader.py
│   │   └── report.py
│   ├── brokers/upstox/       # Upstox API wrappers
│   │   ├── auth.py, orders.py, positions.py
│   │   ├── market_data.py, historical_v3.py
│   │   ├── instruments.py, websocket_v3.py
│   │   └── order_modify_v3.py
│   ├── utils/                # Shared utilities
│   │   ├── state.py          # Thread-safe RuntimeState (SSOT)
│   │   ├── config_loader.py  # Config loading + validation
│   │   ├── login_manager.py  # OAuth2 + Playwright automation
│   │   ├── logger.py         # Structured logging
│   │   ├── market_hours.py   # Market open/close checks
│   │   └── password_manager.py # App password hashing
│   ├── configs/              # JSON config files
│   ├── data_store/           # Runtime cache + logs
│   ├── run_bot.py            # Headless CLI entry point
│   └── filter_instruments.py # Standalone instrument filter
├── Frontend/
│   ├── gui.py                # Entry point (sys.path setup)
│   ├── app.py                # Main CTK window + sidebar + password gate
│   ├── theme/                # Centralized dark theme
│   │   ├── colors.py, fonts.py, styles.py
│   ├── bridge/
│   │   └── bot_bridge.py     # GUI ↔ Backend thread-safe bridge
│   ├── views/                # Sidebar views
│   │   ├── dashboard_view.py, trades_view.py
│   │   ├── analytics_view.py, backtest_view.py
│   │   ├── strategy_view.py, system_view.py
│   │   ├── credentials_view.py, logs_view.py
│   │   ├── status_view.py, connections_view.py
│   │   └── orders_view.py, config_view.py
│   └── widgets/              # Reusable CTK components
│       ├── stat_card.py, position_card.py
│       ├── signal_panel.py, status_bar.py
├── tests/                    # Unit tests
├── docs/                     # Documentation
└── requirements.txt
```

## Core Design Patterns

### 1. OBSERVE/ACT Engine Cycle

Every engine cycle runs two phases:
- **OBSERVE** (always runs): Market status check + indicator evaluation → pushes to GUI state
- **ACT** (state-dependent): Poll orders, evaluate exits, attempt entries

This ensures the signal panel always shows live indicator values regardless of position state.

### 2. Position State Machine

```
IDLE → PENDING_ENTRY → ACTIVE → PENDING_EXIT → CLOSED → IDLE
```

All transitions are explicit methods on `PositionManager` — no direct field mutation.

### 3. Executor Pattern

`PaperExecutor` and `LiveExecutor` share the same interface. The engine doesn't know which it's using — mode is set at initialization.

### 4. Thread-Safe State Bridge

`StateStore` wraps `RuntimeState` with `threading.Lock`. The engine thread writes, the GUI thread reads via `deepcopy`. No shared mutable state.

### 5. Services Layer

`ServiceRegistry` manages background polling services (position polling, capital tracking, health checks) with start/stop lifecycle.

## Data Flow

```
WebSocket Ticks → LiveCandleBuilder → CandleService → Indicators
                                                     ↓
                                              TradingEngine
                                                     ↓
                                              StateStore (SSOT)
                                                     ↓
                                              BotBridge → GUI Views
```

## Configuration

Three JSON config files in `Backend/configs/`:
- `system_config.json` — runtime mode, market hours, risk, auth settings
- `strategy_config.json` — entry/exit conditions, instrument selection, indicators
- `credentials.json` — Upstox API credentials (gitignored)
