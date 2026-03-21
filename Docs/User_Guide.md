# User Guide

## Prerequisites

- Python 3.10+
- Upstox trading account with API access
- Windows 10/11 (tested), Linux/macOS (should work)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/santosh_trading_setup.git
cd santosh_trading_setup

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for Upstox login)
playwright install chromium
```

## First-Time Setup

### 1. Configure Credentials

Create `Backend/configs/credentials.json`:
```json
{
  "upstox": {
    "api_key": "YOUR_API_KEY",
    "api_secret": "YOUR_API_SECRET",
    "redirect_uri": "https://127.0.0.1/callback",
    "totp_key": "YOUR_TOTP_SECRET",
    "mobile_no": "YOUR_MOBILE",
    "pin": "YOUR_PIN"
  }
}
```

Or use the GUI: Launch the app → Credentials tab → fill in fields → Save.

### 2. Launch the GUI

```bash
cd Frontend
python gui.py
```

### 3. Set Application Password (Optional)

Click "Set Password" at the bottom of the sidebar. The app will require this password on every launch.

## GUI Navigation

The sidebar is organized into three sections:

### MAIN
- **Dashboard** — Bot controls (Start/Stop/Pause/Login/Run Once), session stats, active position, and live signal panel
- **Trades** — Open position details with SL override and manual exit controls, plus closed trades history
- **Analytics** — Win rate, average win/loss, max drawdown, cumulative P&L chart, and trade log
- **Logs** — Live bot log viewer with level filtering

### CONFIG
- **Strategy** — Entry conditions (RSI, Volume, ADX, VWAP, Supertrend, Bollinger Bands), instrument selection (NIFTY/BANKNIFTY, expiry, strike), exit conditions (SL, target, trailing SL, time exit), order modify settings
- **System** — Runtime mode (paper/live), loop interval, market hours, risk guard, auth settings
- **Credentials** — Upstox API credentials
- **Connections** — Broker API, WebSocket, and data service connection status

### TOOLS
- **Status** — System health dashboard showing bot, auth, market, services, and runtime info
- **Backtesting** — Configure and run backtests with date range, indicator toggles, and results display

## Trading Modes

### Paper Mode (Default)
All orders fill instantly at the requested price. No real money involved. Use this to test your strategy.

### Live Mode
Orders are placed through the Upstox broker API. **Use with caution.** Change mode in System → Runtime → Mode → "live".

## Strategy Configuration

### Entry Indicators (all toggleable)
| Indicator | Default | Description |
|-----------|---------|-------------|
| RSI | Enabled, > 60 | Relative Strength Index |
| Volume vs EMA | Enabled, 20-period | Volume above its EMA |
| ADX | Disabled, >= 20 | Average Directional Index |
| VWAP | Disabled | Price vs Volume Weighted Average Price |
| Supertrend | Disabled, 10/3.0 | Trend direction indicator |
| Bollinger Bands | Disabled, 20/2.0 | Price relative to bands |
| MACD | Disabled, 12/26/9 | Moving Average Convergence Divergence |

### Exit Conditions
- **Stop-Loss** — Percent, points, or fixed price
- **Target** — Percent or points profit target
- **Trailing SL** — Activates after X% profit, trails by Y%
- **Time-based Exit** — Exit at a specific time (e.g., 15:15:00)

## Backtesting

1. Go to **Backtesting** in the sidebar
2. Select underlying (NIFTY/BANKNIFTY), option type, timeframe
3. Set date range
4. Toggle desired indicators
5. Configure exit settings
6. Click **Run Backtest**
7. View results including total P&L, win rate, drawdown, and trade details

## Headless Mode (CLI)

Run without the GUI:
```bash
cd Backend
python run_bot.py              # Run continuously
python run_bot.py --once       # Single cycle
python run_bot.py --force-login # Force fresh auth
```

## Troubleshooting

- **Auth fails**: Check credentials.json, ensure TOTP key is correct, try `--force-login`
- **No candle data**: Check market hours, verify instrument universe was built
- **WebSocket disconnect**: The bot will log a warning; it reconnects automatically
- **GUI freezes**: All bot operations run in daemon threads — if the GUI freezes, report a bug
