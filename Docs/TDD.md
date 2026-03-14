# Test-Driven Development Plan

## Principles (from llm_guidelines)

- Tests are written only for **high-risk logic** and **financial / state-critical paths**
- No boilerplate test suites
- No tests for trivial getters or pure config loading
- Tests must be **fast**, **deterministic**, and **free of external calls**
- All broker API calls must be **mocked at the function level** — never hit real endpoints in tests
- Test names describe the **scenario**, not just the function name

---

## Test Structure

```
tests/
├── unit/
│   ├── test_technical_indicators.py
│   ├── test_entry_conditions.py
│   ├── test_exit_conditions.py
│   ├── test_instrument_selection.py
│   ├── test_order_lifecycle.py
│   ├── test_position_sync.py
│   ├── test_config_loader.py
│   └── test_risk_guard.py
├── integration/
│   └── test_engine_cycle.py
└── fixtures/
    ├── sample_candles.py
    └── sample_universe.py
```

Run all: `python -m pytest tests/ -v`
Run unit only: `python -m pytest tests/unit/ -v`

---

## Unit Tests

---

### `test_technical_indicators.py`

**Coverage target:** RSI, EMA, MACD, ADX computations and entry gate evaluation.
These are financial calculations — any error here causes wrong entries.

| Test | Scenario |
|---|---|
| `test_rsi_overbought_fires` | RSI > 60 with clear overbought series → check passes |
| `test_rsi_oversold_blocked` | RSI = 45, threshold = 60 → check fails |
| `test_rsi_operator_less_than` | operator="<", RSI=30, threshold=40 → check passes |
| `test_volume_above_ema_passes` | Last volume > EMA(20) → check passes |
| `test_volume_below_ema_blocked` | Last volume < EMA(20) → check fails |
| `test_macd_bullish_crossover_passes` | MACD > signal and histogram > min → passes |
| `test_macd_histogram_below_min_blocked` | MACD > signal but histogram < min → fails |
| `test_adx_above_threshold_passes` | ADX = 28, threshold = 20 → passes |
| `test_adx_below_threshold_blocked` | ADX = 15, threshold = 20 → fails |
| `test_insufficient_candles_blocked` | len(candles) < min_required → returns ok=False, no crash |
| `test_empty_candles_returns_safe_result` | candles=[] → ok=False, no exception |
| `test_all_indicators_disabled_returns_false` | No enabled checks → ok=False (no checks = no entry) |
| `test_only_enabled_checks_are_evaluated` | macd disabled → macd not in checks dict |

---

### `test_entry_conditions.py`

**Coverage target:** The full signal gate — all checks combined.

| Test | Scenario |
|---|---|
| `test_all_enabled_checks_pass` | RSI + volume both pass → signal.ok=True |
| `test_rsi_fails_blocks_entry` | RSI fails, volume passes → signal.ok=False |
| `test_volume_fails_blocks_entry` | RSI passes, volume fails → signal.ok=False |
| `test_macd_enabled_and_fails_blocks_entry` | macd.enabled=True, MACD bearish → ok=False |
| `test_adx_enabled_and_fails_blocks_entry` | adx.enabled=True, ADX=10 → ok=False |
| `test_signal_values_populated_correctly` | Check that RSI, volume values are in result dict |
| `test_signal_checks_populated_correctly` | Check that checks dict has correct keys |

---

### `test_exit_conditions.py`

**Coverage target:** All exit trigger logic. This is directly financial — wrong SL = capital loss.

| Test | Scenario |
|---|---|
| `test_sl_percent_triggered` | Entry=100, SL=30%, LTP=65 → trigger fires |
| `test_sl_percent_not_triggered` | Entry=100, SL=30%, LTP=75 → no trigger |
| `test_sl_points_triggered` | Entry=100, SL=20pts, LTP=79 → trigger fires |
| `test_sl_fixed_price_triggered` | Entry=100, SL fixed=70, LTP=68 → trigger fires |
| `test_target_percent_triggered` | Entry=100, target=50%, LTP=152 → trigger fires |
| `test_target_not_triggered` | Entry=100, target=50%, LTP=130 → no trigger |
| `test_trailing_sl_activates_at_threshold` | Trail activates at 20% profit (LTP=120 from entry=100) |
| `test_trailing_sl_tracks_peak` | Peak=130, trail=10%, LTP=116 → trigger fires |
| `test_trailing_sl_does_not_trigger_below_activation` | LTP=110, activate_at=20% → not yet activated |
| `test_time_exit_fires_at_or_after_configured_time` | now=15:16, exit_at=15:15 → trigger |
| `test_time_exit_does_not_fire_before` | now=15:14, exit_at=15:15 → no trigger |
| `test_time_exit_highest_priority` | Time exit + SL both triggered → TIME takes priority |
| `test_no_exit_when_all_disabled` | All exit conditions disabled → returns None |

---

### `test_instrument_selection.py`

**Coverage target:** Strike resolution logic. Wrong strike = wrong instrument traded.

| Test | Scenario |
|---|---|
| `test_atm_ce_selects_nearest_strike` | spot=22450, strikes=[22400,22450,22500] → 22450 CE |
| `test_atm_rounds_to_nearest` | spot=22430, strikes=[22400,22450] → 22450 (closer) |
| `test_otm_ce_offset_1` | ATM=22450, OTM+1 CE → 22500 |
| `test_otm_pe_offset_1` | ATM=22450, OTM+1 PE → 22400 |
| `test_itm_ce_offset_1` | ATM=22450, ITM+1 CE → 22400 |
| `test_itm_pe_offset_1` | ATM=22450, ITM+1 PE → 22500 |
| `test_offset_clamped_at_chain_boundary` | offset=99, only 3 strikes → returns boundary |
| `test_no_contracts_returns_none` | Empty options dict → returns None |
| `test_quantity_lots_mode` | lots=2, lot_size=50 → quantity=100 |
| `test_quantity_qty_mode` | quantity_mode="qty", quantity=25 → quantity=25 |
| `test_underlying_not_in_universe_returns_none` | underlying="MIDCAP" → None |

---

### `test_order_lifecycle.py`

**Coverage target:** Order state machine transitions. Critical — controls real money movement.

| Test | Scenario |
|---|---|
| `test_paper_entry_fills_immediately` | mode=paper, signal fires → active_position set |
| `test_live_entry_places_new_order` | mode=live, no working order → place_order called |
| `test_live_second_signal_modifies_order` | working order open + new signal → modify_order called |
| `test_modify_skipped_if_price_not_improved` | only_improve_price=True, new_price > old_price → skip |
| `test_modify_skipped_if_cooldown_active` | last_modify=2s ago, cooldown=10s → skip |
| `test_modify_skipped_if_flag_disabled` | modify_on_reentry_signal=False → skip |
| `test_modify_skipped_if_different_instrument` | working order is different token → skip |
| `test_poll_fills_working_order` | status=complete → active_position created, working_order=None |
| `test_poll_rejects_working_order` | status=rejected → working_order=None, active_position=None |
| `test_active_position_blocks_new_entry` | active_position set → handle_entry_signal returns skip |
| `test_mark_manual_exit_clears_position` | active_position set → mark_manual_exit → position=None |
| `test_mark_manual_exit_no_position` | no active_position → returns failure result |
| `test_last_closed_epoch_set_on_exit` | after exit, last_closed_epoch is recent timestamp |
| `test_snapshot_reflects_current_state` | snapshot() returns correct working/position dicts |

---

### `test_position_sync.py`

**Coverage target:** Manual exit detection edge cases.

| Test | Scenario |
|---|---|
| `test_no_action_in_paper_mode` | mode=paper → returns None |
| `test_no_action_when_no_active_position` | no active_position → returns None |
| `test_exits_when_position_not_in_broker_response` | our token absent from positions list → manual exit |
| `test_exits_when_net_quantity_zero` | matched position has qty=0 → manual exit with last_price |
| `test_no_exit_when_position_active_at_broker` | matched position qty=50 → returns None |
| `test_handles_empty_positions_response` | positions=[] → exit detected (not found) |
| `test_handles_none_positions_response` | get_positions returns None → returns None (API fail, don't exit) |

---

### `test_config_loader.py`

**Coverage target:** Validation logic that auto-corrects invalid config values.

| Test | Scenario |
|---|---|
| `test_invalid_timeframe_corrected_to_3` | timeframe_minutes=7 → corrected to 3 |
| `test_invalid_underlying_corrected` | underlying="FINNIFTY" → corrected to "NIFTY" |
| `test_invalid_expiry_choice_corrected` | expiry_choice="weekly" → corrected to "current" |
| `test_invalid_strike_mode_corrected` | strike_mode="DEEP" → corrected to "ATM" |
| `test_invalid_option_type_corrected` | option_type="CALL" → corrected to "CE" |
| `test_mode_normalised_to_paper_by_default` | mode="PAPER" → normalised to "paper" |
| `test_live_mode_preserved` | mode="live" → preserved as "live" |
| `test_max_active_positions_always_1` | max_active_positions forced to 1 regardless of config |

---

### `test_risk_guard.py`

**Coverage target:** Guards that prevent trading beyond configured limits.

| Test | Scenario |
|---|---|
| `test_entry_allowed_when_risk_disabled` | risk.enabled=False → always allowed |
| `test_entry_blocked_when_daily_loss_exceeded` | realised_pnl < -max_daily_loss → blocked |
| `test_entry_blocked_when_max_trades_reached` | trade_count >= max_trades → blocked |
| `test_entry_allowed_when_within_limits` | pnl=-1000, max=-5000, trades=3, max=10 → allowed |
| `test_returns_reason_string_when_blocked` | blocked result includes human-readable reason |

---

## Integration Tests

### `test_engine_cycle.py`

**Coverage target:** Full engine cycle with all external calls mocked.
Tests that the orchestration sequence is correct end-to-end.

| Test | Scenario |
|---|---|
| `test_full_cycle_produces_paper_fill` | All signals pass, paper mode → active_position set after cycle |
| `test_cycle_skips_entry_when_rsi_fails` | RSI check fails → no order placed |
| `test_cycle_skips_entry_outside_market_hours` | time=18:00, ignore_hours=False → no entry check |
| `test_cycle_respects_reentry_cooldown` | last_closed 5s ago, cooldown=30s → no entry |
| `test_cycle_updates_runtime_state` | After cycle, runtime_state.last_cycle_epoch is recent |
| `test_sl_triggers_exit_on_live_cycle` | active_position + LTP below SL → exit order placed |

---

## Test Fixtures

### `fixtures/sample_candles.py`

```python
def make_rising_candles(n=80, base_price=22000.0) -> List[dict]:
    """Rising price series with high volume — designed to trigger RSI > 60."""
    ...

def make_flat_candles(n=80, price=22000.0) -> List[dict]:
    """Flat price series — RSI stays near 50."""
    ...

def make_thin_candles(n=80) -> List[dict]:
    """Low volume series — volume < EMA."""
    ...
```

### `fixtures/sample_universe.py`

```python
def make_nifty_universe(spot=22450.0, expiry="2025-07-03") -> Dict[str, Any]:
    """Minimal NIFTY option universe with CE/PE strikes 22000–22900 in 50pt steps."""
    ...
```

---

## Coverage Targets

| Module | Target | Priority |
|---|---|---|
| `technical_indicators.py` | 95% | Critical |
| `exit_conditions.py` | 95% | Critical |
| `order_lifecycle.py` | 90% | Critical |
| `entry_conditions.py` | 90% | High |
| `instrument_selection.py` | 85% | High |
| `position_sync.py` | 85% | High |
| `config_loader.py` | 80% | Medium |
| `risk_guard.py` | 80% | Medium |
| `engine.py` | 70% (integration) | Medium |

Broker API wrappers (`brokers/upstox/`) are **not unit tested** — they are thin REST wrappers.
Integration with Upstox is tested manually against the paper environment.
