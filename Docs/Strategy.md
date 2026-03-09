# Santosh Strategy

## Overview

This strategy trades one index option position at a time for `NIFTY` or `BANKNIFTY`.

Entry is based on configurable minute candles (`2`, `3`, `5`) of the selected index:

1. RSI condition (default: `RSI > 60`)
2. Volume condition (default: `Volume > EMA(20)`)
3. Optional extra filters:
   - `MACD` confirmation toggle
   - `ADX` trend-strength toggle

## Expiry Selection

Exactly one expiry is selected at runtime:

- `current`
- `next`

No combined selection is allowed. This is enforced in config validation.

## Instrument Selection

After entry checks pass:

1. Load filtered option chain for selected underlying and chosen expiry.
2. Resolve contract by:
   - `option_type`: `CE` or `PE`
   - `strike_mode`: `ATM`, `ITM`, `OTM`
   - `strike_offset`: integer offset from ATM

## Order Lifecycle

Only one active position is allowed.

### New signal and no position

- Place entry order.

### New signal while entry order is still open/pending

- If `modify_on_reentry_signal=true`, modify the same order price.
- If `only_improve_price=true`, buy-order modification happens only when new price is lower.
- Example: old price `106`, new signal price `102` -> modify order to `102`.

### Manual exit detection

- Broker positions are polled periodically.
- If tracked instrument quantity becomes `0` (or instrument disappears), position is marked manually closed.

## Notes

- In `paper` mode, fills are immediate for simulation.
- In `live` mode, order status is polled and transition is based on broker response.
