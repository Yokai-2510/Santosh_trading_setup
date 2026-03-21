"""
backtest_view — configure and run backtests with date range, indicator toggles,
and results display.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import customtkinter as ctk

from bridge.bot_bridge import BotBridge
from theme import colors as C, fonts as F
from utils.state import RuntimeState


class BacktestView(ctk.CTkScrollableFrame):
    def __init__(self, parent, bridge: BotBridge, **kwargs) -> None:
        super().__init__(parent, fg_color=C.BG_SECONDARY,
                         scrollbar_button_color=C.BG_CARD,
                         scrollbar_button_hover_color=C.BORDER_INPUT, **kwargs)
        self.bridge = bridge
        self._vars: dict = {}

        ctk.CTkLabel(self, text="Backtesting", font=F.HEADING,
                     text_color=C.TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(16, 12))

        # ── Config Card ──────────────────────────────────────────────
        config_card = ctk.CTkFrame(self, fg_color=C.BG_CARD, corner_radius=10)
        config_card.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(config_card, text="Configuration", font=F.BODY_BOLD,
                     text_color=C.TEXT_MUTED).pack(anchor="w", padx=14, pady=(10, 6))

        # Underlying
        _row(config_card, "Underlying", "underlying", "NIFTY", ["NIFTY", "BANKNIFTY"],
             self._vars, dropdown=True)

        # Option type
        _row(config_card, "Option Type", "option_type", "CE", ["CE", "PE"],
             self._vars, dropdown=True)

        # Timeframe
        _row(config_card, "Timeframe (min)", "timeframe", "3", ["2", "3", "5"],
             self._vars, dropdown=True)

        # Date range
        today = datetime.now()
        _row(config_card, "Start Date", "start_date",
             (today - timedelta(days=30)).strftime("%Y-%m-%d"), None, self._vars)
        _row(config_card, "End Date", "end_date",
             today.strftime("%Y-%m-%d"), None, self._vars)

        ctk.CTkFrame(config_card, fg_color="transparent", height=8).pack()

        # ── Indicator Toggles Card ────────────────────────────────────
        ind_card = ctk.CTkFrame(self, fg_color=C.BG_CARD, corner_radius=10)
        ind_card.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(ind_card, text="Indicators", font=F.BODY_BOLD,
                     text_color=C.TEXT_MUTED).pack(anchor="w", padx=14, pady=(10, 6))

        for name, key, default in [
            ("RSI", "bt_rsi", True),
            ("Volume vs EMA", "bt_volume", True),
            ("ADX", "bt_adx", False),
            ("VWAP", "bt_vwap", False),
            ("Supertrend", "bt_supertrend", False),
            ("Bollinger Bands", "bt_bollinger", False),
            ("MACD", "bt_macd", False),
        ]:
            _switch_row(ind_card, name, key, default, self._vars)

        ctk.CTkFrame(ind_card, fg_color="transparent", height=8).pack()

        # ── Exit Config Card ─────────────────────────────────────────
        exit_card = ctk.CTkFrame(self, fg_color=C.BG_CARD, corner_radius=10)
        exit_card.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(exit_card, text="Exit Settings", font=F.BODY_BOLD,
                     text_color=C.TEXT_MUTED).pack(anchor="w", padx=14, pady=(10, 6))

        _row(exit_card, "SL %", "bt_sl", "30.0", None, self._vars)
        _row(exit_card, "Target %", "bt_target", "50.0", None, self._vars)
        _switch_row(exit_card, "Enable Trailing SL", "bt_trail", False, self._vars)
        _row(exit_card, "Trail Activate %", "bt_trail_act", "20.0", None, self._vars)
        _row(exit_card, "Trail By %", "bt_trail_by", "10.0", None, self._vars)

        ctk.CTkFrame(exit_card, fg_color="transparent", height=8).pack()

        # ── Run Controls ──────────────────────────────────────────────
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.pack(fill="x", padx=16, pady=(0, 8))

        self._run_btn = ctk.CTkButton(
            ctrl, text="Run Backtest", width=160, height=38,
            fg_color=C.ACCENT_BLUE, hover_color=C.ACCENT_BLUE_HOVER,
            font=F.BODY_BOLD, command=self._run_backtest,
        )
        self._run_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = ctk.CTkButton(
            ctrl, text="Stop", width=80, height=38,
            fg_color=C.RED, hover_color=C.RED_DARK,
            font=F.BODY_BOLD, command=self._stop_backtest,
            state="disabled",
        )
        self._stop_btn.pack(side="left", padx=(0, 8))

        self._progress_bar = ctk.CTkProgressBar(ctrl, width=300, height=14,
                                                  progress_color=C.ACCENT_BLUE)
        self._progress_bar.pack(side="left", padx=(8, 8), pady=4)
        self._progress_bar.set(0)

        self._status_lbl = ctk.CTkLabel(ctrl, text="", font=F.SMALL,
                                         text_color=C.TEXT_MUTED)
        self._status_lbl.pack(side="left", padx=8)

        # ── Results Card ─────────────────────────────────────────────
        self._results_card = ctk.CTkFrame(self, fg_color=C.BG_CARD, corner_radius=10)
        self._results_card.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkLabel(self._results_card, text="Results", font=F.BODY_BOLD,
                     text_color=C.TEXT_MUTED).pack(anchor="w", padx=14, pady=(10, 6))

        self._results_text = ctk.CTkTextbox(
            self._results_card, height=260, font=F.MONO,
            fg_color=C.BG_DARKEST, text_color=C.TEXT_CODE, state="disabled",
            wrap="word",
        )
        self._results_text.pack(fill="x", padx=14, pady=(0, 14))

        # Poll progress
        self.after(500, self._poll_progress)

    def update_state(self, state: RuntimeState) -> None:
        pass  # backtest doesn't need live state refresh

    def _run_backtest(self) -> None:
        v = self._vars
        underlying = _sv(v, "underlying", "NIFTY")
        start = _sv(v, "start_date")
        end = _sv(v, "end_date")

        strategy_overrides = {
            "entry_conditions": {
                "timeframe_minutes": int(_sv(v, "timeframe", "3")),
                "rsi": {"enabled": _bv(v, "bt_rsi")},
                "volume_vs_ema": {"enabled": _bv(v, "bt_volume")},
                "adx": {"enabled": _bv(v, "bt_adx")},
                "vwap": {"enabled": _bv(v, "bt_vwap")},
                "supertrend": {"enabled": _bv(v, "bt_supertrend")},
                "bollinger_bands": {"enabled": _bv(v, "bt_bollinger")},
                "macd": {"enabled": _bv(v, "bt_macd")},
            },
            "instrument_selection": {
                "underlying": underlying,
                "option_type": _sv(v, "option_type", "CE"),
            },
            "exit_conditions": {
                "stoploss": {"enabled": True, "type": "percent",
                             "value": float(_sv(v, "bt_sl", "30"))},
                "target": {"enabled": True, "type": "percent",
                           "value": float(_sv(v, "bt_target", "50"))},
                "trailing_sl": {
                    "enabled": _bv(v, "bt_trail"),
                    "activate_at_percent": float(_sv(v, "bt_trail_act", "20")),
                    "trail_by_percent": float(_sv(v, "bt_trail_by", "10")),
                },
            },
        }

        self._run_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._progress_bar.set(0)
        self._status_lbl.configure(text="Starting...")

        self.bridge.backtest.run(
            underlying=underlying,
            start_date=start,
            end_date=end,
            strategy_overrides=strategy_overrides,
            on_complete=self._on_complete,
            on_error=self._on_error,
        )

    def _stop_backtest(self) -> None:
        self.bridge.backtest.stop()
        self._run_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_lbl.configure(text="Stopped")

    def _poll_progress(self) -> None:
        if self.bridge.backtest.is_running:
            pct = self.bridge.backtest.progress
            self._progress_bar.set(pct / 100.0)
            self._status_lbl.configure(text=self.bridge.backtest.status)
        self.after(500, self._poll_progress)

    def _on_complete(self, result) -> None:
        self._run_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._progress_bar.set(1.0)
        self._status_lbl.configure(text="Complete")
        self._display_results(result)

    def _on_error(self, msg: str) -> None:
        self._run_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_lbl.configure(text=f"Error: {msg[:60]}", text_color=C.RED)

    def _display_results(self, result) -> None:
        lines = []
        if result:
            lines.append(f"Total P&L:        {result.total_pnl:+.2f}")
            lines.append(f"Total Trades:     {result.total_trades}")
            lines.append(f"Winning Trades:   {result.winning_trades}")
            lines.append(f"Losing Trades:    {result.losing_trades}")
            lines.append(f"Win Rate:         {result.win_rate:.1f}%")
            lines.append(f"Average Win:      {result.avg_win:+.2f}")
            lines.append(f"Average Loss:     {result.avg_loss:+.2f}")
            lines.append(f"Max Drawdown:     {result.max_drawdown:.2f}")
            lines.append(f"Profit Factor:    {result.profit_factor:.2f}")
            lines.append(f"Sharpe Ratio:     {result.sharpe_ratio:.2f}")
            lines.append("")
            lines.append("--- Trade Details ---")
            for i, t in enumerate(result.trades, 1):
                lines.append(
                    f"  {i:3d}. {t.get('symbol', '?'):20s}  "
                    f"Entry:{t.get('entry_price', 0):.2f}  "
                    f"Exit:{t.get('exit_price', 0):.2f}  "
                    f"P&L:{t.get('pnl', 0):+.2f}  "
                    f"Reason:{t.get('exit_reason', '?')}"
                )
        else:
            lines.append("No results available.")

        self._results_text.configure(state="normal")
        self._results_text.delete("1.0", "end")
        self._results_text.insert("end", "\n".join(lines))
        self._results_text.configure(state="disabled")


# ── Helpers ──────────────────────────────────────────────────────────────

def _row(parent, label, key, default, values, store, dropdown=False):
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=14, pady=3)
    ctk.CTkLabel(row, text=label, width=180, anchor="w", font=F.BODY,
                 text_color=C.TEXT_SECONDARY).pack(side="left")
    var = ctk.StringVar(value=default)
    store[key] = var
    if dropdown and values:
        ctk.CTkOptionMenu(row, values=values, variable=var, width=180,
                           fg_color=C.BG_INPUT, button_color=C.BORDER_INPUT,
                           dropdown_fg_color=C.BG_SECONDARY,
                           text_color=C.TEXT_SECONDARY).pack(side="left", padx=8)
    else:
        ctk.CTkEntry(row, textvariable=var, width=180, fg_color=C.BG_INPUT,
                      text_color=C.TEXT_SECONDARY, border_color=C.BORDER_INPUT,
                      height=30).pack(side="left", padx=8)


def _switch_row(parent, label, key, default, store):
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=14, pady=3)
    ctk.CTkLabel(row, text=label, width=180, anchor="w", font=F.BODY,
                 text_color=C.TEXT_SECONDARY).pack(side="left")
    var = ctk.BooleanVar(value=default)
    store[key] = var
    ctk.CTkSwitch(row, text="", variable=var,
                   progress_color=C.ACCENT_BLUE).pack(side="left", padx=8)


def _sv(store, key, default="") -> str:
    v = store.get(key)
    return str(v.get()) if v else default


def _bv(store, key) -> bool:
    v = store.get(key)
    return bool(v.get()) if isinstance(v, ctk.BooleanVar) else False
