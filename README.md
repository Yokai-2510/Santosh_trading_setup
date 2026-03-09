# Santosh Trading Setup

Standalone Upstox trading bot project focused on a simple configurable index options strategy:

- Timeframe: `2`, `3`, or `5` minute candles
- Entry core: `RSI` + `Volume > EMA(20)`
- Additional optional indicators: `MACD` and `ADX`
- Expiry selection: exactly one choice at a time: `current` or `next`
- One active position at a time
- Pending/open order price modification on repeated signal
- Manual exit detection via broker positions polling

## Run

```bash
python Backend/run_bot.py
```

## GUI (config editor + token fetch)

```bash
python Frontend/gui.py
```

## Notes

- This project is independent from the Vijay bot code path.
- Config files live in `Backend/source/`.
- Token cache is stored in `Backend/data/cache/access_token.json`.
