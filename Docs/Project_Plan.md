# Project Overhaul Plan

## Goal

Transform the current working prototype into a production-quality, modular system with:
- Clean backend architecture (SRP modules, SSOT config, no god classes)
- Full exit condition logic (SL, target, trailing SL, time-based)
- Thread-safe shared state enabling live GUI updates
- CTK GUI with sidebar nav, live dashboard, position tracking, bot controls
- TDD-first approach for all financial logic
- Clean config schema with no `_doc` fields mixed into data

---

## What Stays (No Changes Needed)

These modules are already clean, well-structured, and comply with llm_guidelines:

| File | Verdict |
|---|---|
| `brokers/upstox/auth.py` | Keep |
| `brokers/upstox/market_data.py` | Keep |
| `brokers/upstox/orders.py` | Keep |
| `brokers/upstox/order_modify_v3.py` | Keep |
| `brokers/upstox/positions.py` | Keep |
| `brokers/upstox/instruments.py` | Keep |
| `brokers/upstox/historical_v3.py` | Keep |
| `modules/auth/login_manager.py` | Keep |
| `modules/data/candle_service.py` | Keep |
| `modules/data/instrument_filter.py` | Keep |
| `modules/indicators/technical_indicators.py` | Keep |
| `modules/utils/logger.py` | Keep |

---

## What Gets Overhauled

### Phase 1 — Backend Core

**1A. Config Schema Cleanup**

- Remove all `_doc` keys from JSON files
- Rename `order_details` → `order_execution` in strategy_config
- Move `macd_confirmation` → `macd`, `adx_strength` → `adx`
- Add `exit_conditions` block (SL, target, trailing, time-based)
- Add `order_modify` block (extracted from `order_details`)
- Add `risk` block to system_config
- Update `config_loader.py` to validate the new schema

**1B. `modules/utils/market_hours.py`** (NEW)

Extract `_is_market_active()` from `engine.py` into a dedicated module.
Add `time_until_open()` and `is_expiry_today()`.

**1C. `modules/state/runtime_state.py`** (NEW)

Thread-safe dataclass: `RuntimeState` with lock-protected `read()` / `update()` methods.
Fields: bot status, auth status, market status, active position, working order, last signal, session P&L.
The engine writes to this after every cycle.
The GUI reads from this every second.

**1D. `modules/strategy/exit_conditions.py`** (NEW)

Full exit logic:
- `evaluate_exit(position, current_ltp, exit_cfg, now) → Optional[ExitSignal]`
- SL by percent / points / fixed price
- Target by percent / points
- Trailing SL with activation threshold and peak tracking
- Time-based forced exit
- Priority order: time → trailing → hard SL → target

**1E. `modules/risk/risk_guard.py`** (NEW)

Guards: max daily loss, max trades per session.
`is_entry_allowed(state, risk_cfg) → (bool, str)`

**1F. `modules/strategy/engine.py`** (OVERHAUL)

Current issue: `run_once()` is a 100-line method doing 8 different things.
Rewrite as a thin orchestrator — each step is a single function call.
All logic moves into appropriate modules.
Add exit condition evaluation step in the cycle.
Add runtime state update step at the end of every cycle.

**1G. `modules/strategy/order_lifecycle.py`** (EXTEND)

Add:
- `handle_exit_signal(exit_signal, headers) → LifecycleResult` — place exit order
- `poll_exit_order(headers) → LifecycleResult` — check exit order fill
- `exit_order` tracking state alongside `working_order` and `active_position`
- Peak LTP tracking for trailing SL (`peak_ltp` field on active_position)

**1H. `modules/strategy/position_sync.py`** (BUG FIX)

Fix the existing bug (visible in git diff — file is modified).
Ensure it handles the case where `get_positions()` returns `None` (API failure) without triggering a spurious exit.

**1I. `run_bot.py`** (TIGHTEN)

Currently has `main()` function with logic — violates llm_guidelines.
Extract all logic to modules, make `run_bot.py` a pure linear top-down orchestrator.

---

### Phase 2 — Frontend Overhaul

**2A. `Frontend/bridge/bot_bridge.py`** (NEW)

Owns the bot thread:
```
BotBridge.start_bot()        → start daemon thread
BotBridge.stop_bot()         → set engine.running=False, join thread
BotBridge.run_once()         → single cycle in new thread
BotBridge.force_login()      → re-authenticate
BotBridge.get_state()        → read RuntimeState copy
BotBridge.is_running()       → bool
```

**2B. `Frontend/app.py`** (FULL REWRITE)

Current: flat tabs, no sidebar, no live data.
New: sidebar navigation + dynamic content area.

Layout:
```
MainWindow
├── HeaderBar (title, mode badge, market status)
├── ContentFrame
│   ├── Sidebar (navigation buttons)
│   └── ViewContainer (swaps view on nav click)
└── StatusBar (bot status, auth, last update time)
```

Sidebar items: Dashboard, Config, Orders, Logs, About

View switching: hide/show view frames (no re-creation on switch).

`after(1000, self._refresh_ui)` loop — reads `bridge.get_state()` and updates all visible widgets.

**2C. `Frontend/views/dashboard_view.py`** (NEW)

Sections:
- Bot controls row: `[Start Bot]` `[Stop Bot]` `[Force Login]` `[Run Once]`
- Active position card (conditional on state)
- Working order card (conditional on state)
- Signal panel (indicator values + pass/fail)
- Stats row (session P&L, trade count, cycle count)

All values update every second from RuntimeState.

**2D. `Frontend/views/config_view.py`** (REFACTOR from `app.py`)

Extract existing config editor into its own view.
Add missing fields:
- All `exit_conditions` settings (SL, target, trailing, time exit)
- `risk` settings (daily loss limit, max trades)
- All `order_execution` fields
- Market hours config

Proper input types:
- Dropdowns for enums (order_type, strike_mode, etc.)
- Switches for booleans
- Number entries with validation for floats/ints
- Masked entries for secrets

**2E. `Frontend/views/orders_view.py`** (NEW)

Table: Time | Symbol | Side | Qty | Entry Price | Exit Price | P&L | Reason
Populated from session trade history in RuntimeState.
Sorted newest-first. Scrollable.

**2F. `Frontend/views/logs_view.py`** (NEW)

Reads last N lines from `bot.log`.
Auto-refresh every 2s.
Scrollable text widget.
Level filter buttons: ALL / INFO / WARNING / ERROR.

**2G. Widgets** (NEW)

`position_card.py` — reusable card showing live position details + P&L.
`signal_panel.py` — grid of indicator name / value / threshold / badge.
`stat_card.py` — metric tile with label + value + optional color.
`status_bar.py` — bottom bar with small status indicators.

---

### Phase 3 — Tests

Write all tests per `Docs/TDD.md`.

Priority order:
1. `test_exit_conditions.py` — before implementing exit_conditions.py
2. `test_order_lifecycle.py` — before extending order_lifecycle.py
3. `test_position_sync.py` — before fixing the bug
4. `test_technical_indicators.py`
5. `test_entry_conditions.py`
6. `test_instrument_selection.py`
7. `test_config_loader.py`
8. `test_risk_guard.py`
9. `test_engine_cycle.py` (integration, written last)

---

### Phase 4 — Docs Update

Update `Strategy.md` and `Technical_Implementation.md` to reflect final implemented state.
Remove any plan-vs-reality discrepancies.

---

## Implementation Order

```
Phase 1A  Config schema cleanup           (no code changes, just JSON)
Phase 1B  market_hours.py                 (small, pure functions)
Phase 3a  Write test_exit_conditions.py   (TDD — tests first)
Phase 1D  exit_conditions.py             (make tests pass)
Phase 3b  Write test_order_lifecycle.py  (TDD)
Phase 1G  Extend order_lifecycle.py      (make tests pass)
Phase 3c  Write test_position_sync.py    (TDD)
Phase 1H  Fix position_sync.py bug       (make tests pass)
Phase 1C  runtime_state.py               (needed by engine + bridge)
Phase 1E  risk_guard.py                  (with tests)
Phase 1F  engine.py overhaul             (wire all new modules)
Phase 1I  run_bot.py tighten
Phase 2A  bot_bridge.py
Phase 2B  app.py rewrite
Phase 2C  dashboard_view.py
Phase 2D  config_view.py
Phase 2E  orders_view.py
Phase 2F  logs_view.py
Phase 2G  Widgets
Phase 4   Final doc sync
```

---

## What the New GUI Will Show (Checklist)

### Dashboard
- [ ] Bot Start / Stop button with running indicator
- [ ] Force Login button
- [ ] Run Once button
- [ ] Active position: symbol, strike, expiry, entry price, current LTP, unrealised P&L, quantity, entry time
- [ ] Working order: order ID, symbol, price, status, Cancel button
- [ ] Signal panel: RSI value+threshold, Volume vs EMA, MACD (if enabled), ADX (if enabled), each with pass/fail badge
- [ ] Session stats: realised P&L, trade count, cycle count, last action

### Config
- [ ] All entry condition parameters
- [ ] All exit condition parameters (SL, target, trailing, time-based)
- [ ] Instrument selection (underlying, expiry, option type, strike mode, offset, lots)
- [ ] Order execution (order type, product, validity, tick size, etc.)
- [ ] Order modify settings
- [ ] Position management settings
- [ ] Runtime mode (paper/live)
- [ ] Loop interval
- [ ] Market hours
- [ ] Risk guard settings
- [ ] Broker API timeouts
- [ ] Auth settings (headless, token reset time)
- [ ] All credentials fields

### Orders
- [ ] Session trade history table
- [ ] P&L per trade
- [ ] Exit reason per trade

### Logs
- [ ] Live log tail with auto-scroll
- [ ] Level filter
- [ ] Clear display button

### Status Bar (always visible)
- [ ] Bot running indicator (green dot / red dot)
- [ ] Paper / Live mode badge
- [ ] Market open / closed indicator
- [ ] Last update timestamp
