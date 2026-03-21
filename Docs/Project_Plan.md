# Project Plan — Santosh Trading Setup

## Current Status: Complete

All phases have been implemented. The system is a fully modular trading bot with:
- Clean layered backend (main/, strategy/, orders/, data/, services/, utils/)
- 8 technical indicators (RSI, EMA, MACD, ADX, VWAP, Supertrend, Bollinger Bands, OI)
- Walk-forward backtesting engine with GUI integration
- Dark-themed desktop GUI with 10 sidebar views
- Password protection
- Paper and live trading modes
- Thread-safe state management

## Architecture Layers

```
Frontend (CTK GUI)  →  Bridge  →  Services  →  Engine  →  Strategy/Orders  →  Broker API
```

## Completed Phases

### Phase 1 — Backend Core
- [x] Config schema cleanup (configs/ folder, validated loading)
- [x] Market hours utility (pure functions)
- [x] Thread-safe RuntimeState (SSOT with lock-protected read/write)
- [x] Exit conditions (SL, target, trailing SL, time-based with priority)
- [x] Risk guard (daily loss limit, max trades per session)
- [x] TradingEngine overhaul (OBSERVE/ACT cycle, signal every cycle)
- [x] Position manager state machine (explicit transitions, ClosedTrade)
- [x] Paper executor (instant fills) + Live executor (broker API)
- [x] Order builder (params construction, tick rounding)

### Phase 2 — Data & Indicators
- [x] Candle service (historical cache + live merge)
- [x] Live candle builder (WebSocket ticks → N-min candles)
- [x] Instrument filter (master contract download + universe)
- [x] RSI, EMA, MACD, ADX (base indicators)
- [x] VWAP, Supertrend, Bollinger Bands, OI Change (enhanced)
- [x] Aggregated entry gate with AND logic

### Phase 3 — Services Layer
- [x] ServiceRegistry (background service lifecycle)
- [x] LiveTradingService (engine + services wrapper)
- [x] MarketDataService (indicator computation service)
- [x] BacktestService (background backtest runner)

### Phase 4 — Backtesting
- [x] BacktestEngine (walk-forward simulation)
- [x] Data loader (Upstox, yfinance, CSV)
- [x] Report generation (P&L, win rate, drawdown, Sharpe)

### Phase 5 — Frontend Overhaul
- [x] Theme system (colors, fonts, styles — centralized)
- [x] Password gate (SHA-256 hashed, on startup)
- [x] BotBridge rewrite (uses LiveTradingService + BacktestService)
- [x] App rewrite (expanded sidebar: 3 sections, 10 views)
- [x] Dashboard view (controls, stats, position, signal panel)
- [x] Strategy view (entry + instrument + exit tabs, new indicators)
- [x] System view (runtime, market, risk, auth)
- [x] Credentials view (Upstox API fields)
- [x] Trades view (open position + closed trades tabs)
- [x] Analytics view (win rate, drawdown, cumulative P&L chart)
- [x] Logs view (log tail with level filtering)
- [x] Status view (system health dashboard)
- [x] Connections view (broker, WebSocket, data service status)
- [x] Backtest view (config, indicator toggles, date range, results)
- [x] Signal panel (updated for new indicators)
- [x] Status bar (bot, market, mode, cycle)

### Phase 6 — Documentation
- [x] Architecture.md
- [x] User_Guide.md
- [x] Technical_Design.md
- [x] Technical_Implementation.md
- [x] TDD.md (test plan)
- [x] Project_Plan.md (this file)
- [x] Strategy.md (strategy specification)

### Phase 7 — Final
- [x] .gitignore (credentials, cache, logs, IDE files)
- [x] requirements.txt (all dependencies)
- [x] Import verification (all modules resolve correctly)

## Key Design Decisions

1. **OBSERVE/ACT cycle** — Indicators evaluate every cycle for GUI display, not just on IDLE
2. **Executor pattern** — Paper and live share the same interface; engine is mode-agnostic
3. **Position state machine** — Explicit transitions prevent impossible states
4. **deepcopy state reads** — GUI thread never holds references to engine data
5. **Services layer** — Background polling decoupled from engine cycle
6. **Theme system** — All colors/fonts centralized, no scattered hex codes
7. **Password gate** — Simple SHA-256 hash, no external auth dependencies
