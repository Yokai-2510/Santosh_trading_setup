# Santosh Strategy — Complete Specification

## Overview

Trades one index option position at a time on `NIFTY` or `BANKNIFTY`.
One position. One expiry. One direction. No averaging, no pyramid.

---

## 1. Entry Conditions

Entry is evaluated on each bot cycle. All enabled checks must pass sequentially before any order is placed.

### 1.1 Pre-Gate Checks (Evaluated First)

These are hard blockers. If any fails, the cycle ends immediately — indicators are not evaluated.

| Check | Condition | Notes |
|---|---|---|
| Market hours | `now` is between `market_open` and `market_close` | Skipped if `ignore_market_hours = true` |
| No active position | `active_position` is `None` | One position max — hard constraint |
| Re-entry cooldown | `time_since_last_close >= reentry_wait_seconds_after_close` | Prevents immediate re-entry after a close |
| Spot LTP valid | `spot_ltp > 0` | If Upstox LTP call fails or returns 0, skip cycle |
| Candle data sufficient | `len(candles) >= min_candles_required` | Default 60 candles minimum for indicator warmup |

---

### 1.2 Indicator Gate (Sequential, All Must Pass)

Evaluated on the configured `timeframe_minutes` candles of the underlying index (e.g. `NSE_INDEX|Nifty 50`).

**Step 1 — RSI** *(always enabled by default)*

```
rsi_value = RSI(close, period=rsi.period)   // EWM-based RSI
pass = rsi_value > rsi.threshold              // operator configurable: ">" or "<"
```

- If `rsi.enabled = false`, this check is skipped entirely (not counted as pass or fail).
- Default: `RSI(14) > 60`

---

**Step 2 — Volume vs EMA** *(always enabled by default)*

```
vol_ema = EMA(volume, period=volume_vs_ema.ema_period)
pass = current_volume > vol_ema
```

- Confirms momentum behind the move — prevents entries on thin candles.
- If `volume_vs_ema.enabled = false`, skipped.

---

**Step 3 — MACD Confirmation** *(optional toggle)*

```
macd_line  = EMA(close, fast) - EMA(close, slow)
signal_line = EMA(macd_line, signal_period)
histogram   = macd_line - signal_line

pass = (macd_line > signal_line) AND (histogram >= min_histogram)
```

- Used to confirm bullish momentum. Both crossover and histogram floor must be met.
- Only active when `macd.enabled = true`.

---

**Step 4 — ADX Trend Strength** *(optional toggle)*

```
adx_value = ADX(high, low, close, period=adx.period)
pass = adx_value >= adx.min_threshold
```

- Filters out ranging/choppy markets. Entry only when trend has strength.
- Only active when `adx.enabled = true`.

---

**Signal result:** `ok = all(enabled checks pass)`
If `ok = false`, log the failed check and skip the cycle. Do not place any order.

---

## 2. Instrument Selection

Executed only when `signal.ok = true` and no active position exists.

### 2.1 Underlying Resolution

- Read `instrument_selection.underlying` from config: `NIFTY` or `BANKNIFTY`
- Map to spot instrument key:
  - `NIFTY` → `NSE_INDEX|Nifty 50`
  - `BANKNIFTY` → `NSE_INDEX|Nifty Bank`
- Look up pre-built option universe for this underlying

### 2.2 Expiry Resolution

Only one expiry is active at a time. Set via `instrument_selection.expiry_choice`:

- `current` → nearest upcoming expiry (from today)
- `next` → second nearest expiry

Universe is built at startup and held in memory. Master contract download happens once at boot.

### 2.3 Strike Selection

```
Inputs:
  spot_ltp        = current spot LTP
  option_type     = CE or PE
  strike_mode     = ATM | ITM | OTM
  strike_offset   = integer steps from base strike

ATM strike = strike in option chain closest to spot_ltp

strike resolution:
  if strike_mode == ATM:
      target = atm_index
  if strike_mode == OTM:
      CE: target = atm_index + strike_offset     (higher strike = cheaper)
      PE: target = atm_index - strike_offset     (lower strike = cheaper)
  if strike_mode == ITM:
      CE: target = atm_index - strike_offset     (lower strike = deeper ITM)
      PE: target = atm_index + strike_offset     (higher strike = deeper ITM)

Clamp target index within [0, len(strikes) - 1]
```

### 2.4 Lot Calculation

```
if quantity_mode == "lots":
    quantity = lots * contract.lot_size
    (e.g. lots=1, lot_size=50 → quantity=50)

if quantity_mode == "qty":
    quantity = quantity    (raw qty, no lot multiplier)
```

### 2.5 Contract Output

Selected contract carries:

| Field | Description |
|---|---|
| `instrument_key` | Upstox token for order placement |
| `trading_symbol` | Human-readable symbol |
| `strike` | Resolved strike price |
| `option_type` | CE or PE |
| `lot_size` | Lot size of the contract |
| `tick_size` | Min price step |
| `expiry` | Expiry date string |

---

## 3. Exit Conditions

Exit logic runs in every cycle independently of entry checks. It governs when and how the active position is closed.

### 3.1 Stop-Loss Exit

```
sl_config = exit_conditions.stoploss

if sl_config.type == "percent":
    sl_price = entry_price * (1 - sl_value / 100)

if sl_config.type == "points":
    sl_price = entry_price - sl_value

if sl_config.type == "fixed_price":
    sl_price = sl_value

trigger = current_ltp <= sl_price
```

On trigger:
- In **live mode**: place an exit order (SL-M or MARKET) via `place_order(SELL)` for full quantity
- In **paper mode**: mark position closed with `exit_price = current_ltp`
- Log: `SL HIT | entry={entry_price} sl={sl_price} ltp={current_ltp}`

Stop-loss order on entry fill (bracket-style):
- If `stoploss.place_sl_order_on_fill = true`, a separate SL-M SELL order is placed immediately after entry is confirmed filled
- This offloads SL management to the broker

---

### 3.2 Target Exit

```
if target.type == "percent":
    target_price = entry_price * (1 + target.value / 100)

if target.type == "points":
    target_price = entry_price + target.value

trigger = current_ltp >= target_price
```

On trigger:
- Place LIMIT SELL at `target_price` (or MARKET if configured)
- In paper mode: mark closed with `exit_price = current_ltp`

---

### 3.3 Trailing Stop-Loss

```
activate_threshold = entry_price * (1 + trailing_sl.activate_at_percent / 100)

if trailing_sl activated:
    trail_price = peak_ltp * (1 - trailing_sl.trail_by_percent / 100)
    trigger = current_ltp <= trail_price
```

Tracking:
- `peak_ltp` is updated every cycle to `max(peak_ltp, current_ltp)` while position is active
- Trail activates only after `current_ltp >= activate_threshold` has been reached at least once
- Once activated, trailing never resets — if price falls back, the trail triggers

---

### 3.4 Time-Based Exit

```
if time_based_exit.enabled:
    exit_time = parse("exit_conditions.time_based_exit.exit_at_time")
    trigger = now.time() >= exit_time
```

- Used to force square-off before market close (e.g. `15:15:00`)
- Places MARKET SELL immediately
- Takes priority over all other checks

---

### 3.5 Manual Exit Detection (Broker Position Polling)

```
Poll interval: position_management.manual_exit_poll_interval_seconds

For each cycle poll:
  positions = get_positions(headers)
  matched = [p for p in positions if p.instrument_token == active.instrument_token]

  if not matched:
      mark_manual_exit(reason="NOT_FOUND")
  elif sum(p.quantity for p in matched) == 0:
      mark_manual_exit(reason="QTY_ZERO", exit_price=matched[0].last_price)
```

- Detects exits done manually from the broker app
- Does not place any orders — only syncs internal state
- Applies only in **live mode**

---

### 3.6 Exit Order Placement

When a strategy-driven exit is triggered:

```
place_order(
    instrument_token = active_position.instrument_token,
    transaction_type = "SELL",
    quantity         = active_position.quantity,
    order_type       = exit_order_type,   // from config (MARKET or SL-M)
    price            = exit_price if LIMIT else None,
    trigger_price    = sl_price if SL-M else 0.0
)
```

After placing exit order:
- Poll exit order status until `COMPLETE` or `REJECTED`
- On `COMPLETE`: mark position closed, record fill price
- On `REJECTED`: log error, do not clear position — retry on next cycle

---

### 3.7 Re-entry Cooldown After Exit

After any exit (manual, SL, target, trailing, time-based):

```
last_closed_epoch = time.time()

re-entry allowed when:
    time.time() - last_closed_epoch >= reentry_wait_seconds_after_close
```

This prevents whipsaw re-entry immediately after a close.

---

## 4. Order Modify on Re-entry Signal

Applies when an entry order is already **OPEN** (not yet filled) and a new signal fires for the same instrument.

```
conditions for modify:
  1. modify_on_reentry_signal == true
  2. Same instrument_token as working order
  3. time_since_last_modify >= modify_cooldown_seconds
  4. if only_improve_price == true: new_price < working_order.price  (lower is better for BUY)

if all conditions met:
    new_price = round_to_tick(current_option_ltp)
    modify_order_v3(order_id, price=new_price)
```

- Prevents stale limit orders from lingering at old prices
- `only_improve_price` protects against chasing the price upward

---

## 5. Paper Mode Behaviour

| Event | Paper Mode |
|---|---|
| Entry signal | Immediate fill at current LTP |
| SL trigger | Immediate close at current LTP |
| Target trigger | Immediate close at current LTP |
| Manual exit poll | Not performed (no broker positions) |
| Order modify | Not performed |
| Exit order | Not sent to broker |

---

## 6. Configuration Reference

All strategy behaviour is driven by `Backend/source/strategy_config.json`.
See `Docs/Technical_Implementation.md` for the full schema definition.
