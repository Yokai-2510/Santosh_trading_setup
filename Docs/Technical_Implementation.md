# Technical Implementation

## Architecture

The project is split into:

- `Backend/brokers/upstox`: REST wrappers
- `Backend/modules`: orchestration and strategy logic
- `Backend/source`: JSON configs
- `Frontend`: CTK config editor and token utility

## Main Backend Flow

1. Load config files (`system`, `strategy`, `credentials`).
2. Authenticate with cache-first Upstox token flow.
3. Download/filter master contract and build `NIFTY/BANKNIFTY` option universe for one expiry (`current` or `next`).
4. Fetch one-month historical candles (V3) for selected index timeframe.
5. Evaluate entry indicators.
6. Resolve option contract and place order.
7. On repeated signal with open order, call Modify Order V3.
8. Poll order status until fill/reject.
9. Poll broker positions for manual exit detection.

## Key Modules

- `modules/auth/login_manager.py`
  - Handles cached token validation and fresh login flow.
- `modules/data/instrument_filter.py`
  - Master contract filtering and current/next expiry chain output.
- `modules/data/candle_service.py`
  - One-month bootstrap and rolling candle refresh.
- `modules/indicators/technical_indicators.py`
  - RSI, volume EMA, MACD, ADX calculations and condition evaluation.
- `modules/strategy/order_lifecycle.py`
  - One-position guard, place/modify behavior, order polling.
- `modules/strategy/position_sync.py`
  - Manual exit detection by positions polling.
- `modules/strategy/engine.py`
  - End-to-end cycle orchestration.

## Upstox APIs Used

- OAuth login/token exchange
- `GET /v3/market-quote/ltp`
- `GET /v3/historical-candle/...` (V3)
- `POST /v3/order/place`
- `PUT /v3/order/modify`
- `GET /v2/order/details`
- `GET /v2/portfolio/short-term-positions`
- Master contract download (`NSE.json.gz`)

## GUI Scope

The GUI is intentionally lightweight and currently focused on:

- Fetch/refresh access token
- Edit/save credentials config
- Edit/save strategy config
- Edit/save core system runtime config

No live market visualization is included in this version.
