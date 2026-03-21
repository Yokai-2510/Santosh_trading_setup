"""
analytics_view — session performance analytics with P&L chart and trade stats.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import customtkinter as ctk

from bridge.bot_bridge import BotBridge
from theme import colors as C, fonts as F
from utils.state import RuntimeState

_CHART_H = 180


class AnalyticsView(ctk.CTkScrollableFrame):
    def __init__(self, parent, bridge: BotBridge, **kwargs) -> None:
        super().__init__(parent, fg_color=C.BG_SECONDARY,
                         scrollbar_button_color=C.BG_CARD,
                         scrollbar_button_hover_color=C.BORDER_INPUT, **kwargs)
        self.bridge = bridge
        self._last_trade_count = 0

        # Title
        ctk.CTkLabel(self, text="Analytics", font=F.HEADING,
                     text_color=C.TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(16, 8))

        # Stats cards row
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.pack(fill="x", padx=16, pady=(0, 12))

        self._total_pnl = _StatTile(stats, "Total P&L")
        self._total_pnl.pack(side="left", padx=(0, 8))
        self._win_rate = _StatTile(stats, "Win Rate")
        self._win_rate.pack(side="left", padx=(0, 8))
        self._avg_win = _StatTile(stats, "Avg Win")
        self._avg_win.pack(side="left", padx=(0, 8))
        self._avg_loss = _StatTile(stats, "Avg Loss")
        self._avg_loss.pack(side="left", padx=(0, 8))
        self._trade_count = _StatTile(stats, "Trades")
        self._trade_count.pack(side="left", padx=(0, 8))
        self._max_dd = _StatTile(stats, "Max Drawdown")
        self._max_dd.pack(side="left")

        # Cumulative P&L chart area (simple text-based chart)
        chart_card = ctk.CTkFrame(self, fg_color=C.BG_CARD, corner_radius=10)
        chart_card.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(chart_card, text="Cumulative P&L", font=F.BODY_BOLD,
                     text_color=C.TEXT_MUTED).pack(anchor="w", padx=14, pady=(10, 4))

        self._chart_canvas = ctk.CTkTextbox(
            chart_card, height=_CHART_H, font=F.MONO,
            fg_color=C.BG_DARKEST, text_color=C.TEXT_CODE, state="disabled",
            wrap="none",
        )
        self._chart_canvas.pack(fill="x", padx=14, pady=(0, 14))

        # Trade log table
        log_card = ctk.CTkFrame(self, fg_color=C.BG_CARD, corner_radius=10)
        log_card.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkLabel(log_card, text="Trade Log", font=F.BODY_BOLD,
                     text_color=C.TEXT_MUTED).pack(anchor="w", padx=14, pady=(10, 4))

        hdr = ctk.CTkFrame(log_card, fg_color=C.BG_INPUT, corner_radius=0)
        hdr.pack(fill="x", padx=14, pady=(0, 2))
        for col, w in [("#", 30), ("Time", 70), ("Symbol", 160), ("Qty", 50),
                        ("Entry", 80), ("Exit", 80), ("P&L", 90), ("Reason", 120)]:
            ctk.CTkLabel(hdr, text=col, width=w, font=F.TINY_BOLD,
                         text_color=C.TEXT_MUTED, anchor="w").pack(side="left", padx=4, pady=3)

        self._log_frame = ctk.CTkFrame(log_card, fg_color="transparent")
        self._log_frame.pack(fill="x", padx=14, pady=(0, 14))

    def update_state(self, state: RuntimeState) -> None:
        trades = state.trade_history
        total_pnl = state.session_realised_pnl
        count = len(trades)

        self._total_pnl.set(f"{total_pnl:+.0f}", C.GREEN if total_pnl >= 0 else C.RED)
        self._trade_count.set(str(count))

        if count > 0:
            wins = [t for t in trades if t.pnl > 0]
            losses = [t for t in trades if t.pnl <= 0]
            wr = len(wins) / count * 100
            avg_w = sum(t.pnl for t in wins) / len(wins) if wins else 0
            avg_l = sum(t.pnl for t in losses) / len(losses) if losses else 0

            # Max drawdown
            cumulative = 0.0
            peak = 0.0
            max_dd = 0.0
            for t in trades:
                cumulative += t.pnl
                peak = max(peak, cumulative)
                dd = peak - cumulative
                max_dd = max(max_dd, dd)

            self._win_rate.set(f"{wr:.0f}%", C.GREEN if wr >= 50 else C.RED)
            self._avg_win.set(f"+{avg_w:.0f}", C.GREEN)
            self._avg_loss.set(f"{avg_l:.0f}", C.RED)
            self._max_dd.set(f"-{max_dd:.0f}", C.RED if max_dd > 0 else C.TEXT_MUTED)
        else:
            self._win_rate.set("--")
            self._avg_win.set("--")
            self._avg_loss.set("--")
            self._max_dd.set("--")

        # Rebuild trade log + chart if trades changed
        if count != self._last_trade_count:
            self._last_trade_count = count
            self._rebuild_log(trades)
            self._rebuild_chart(trades)

    def _rebuild_log(self, trades) -> None:
        for w in self._log_frame.winfo_children():
            w.destroy()

        for i, t in enumerate(reversed(trades), 1):
            row = ctk.CTkFrame(self._log_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            pnl_color = C.GREEN if t.pnl >= 0 else C.RED
            for val, w in [(str(i), 30), (t.exit_time or t.entry_time, 70),
                            (t.symbol, 160), (str(t.quantity), 50),
                            (f"{t.entry_price:.2f}", 80),
                            (f"{t.exit_price:.2f}" if t.exit_price else "--", 80),
                            (f"{t.pnl:+.2f}", 90), (t.exit_reason, 120)]:
                color = pnl_color if val == f"{t.pnl:+.2f}" else C.TEXT_SECONDARY
                ctk.CTkLabel(row, text=val, width=w, font=F.SMALL,
                             text_color=color, anchor="w").pack(side="left", padx=4)

    def _rebuild_chart(self, trades) -> None:
        """Simple text-based cumulative P&L sparkline."""
        if not trades:
            return
        cumulative = []
        total = 0.0
        for t in trades:
            total += t.pnl
            cumulative.append(total)

        if not cumulative:
            return

        mn = min(cumulative)
        mx = max(cumulative)
        rng = mx - mn if mx != mn else 1.0
        height = 8

        lines = []
        for row in range(height, -1, -1):
            threshold = mn + (rng * row / height)
            chars = []
            for val in cumulative[-60:]:  # last 60 trades
                chars.append("\u2588" if val >= threshold else " ")
            level = mn + (rng * row / height)
            lines.append(f"{level:>8.0f} |{''.join(chars)}")

        self._chart_canvas.configure(state="normal")
        self._chart_canvas.delete("1.0", "end")
        self._chart_canvas.insert("end", "\n".join(lines))
        self._chart_canvas.configure(state="disabled")


class _StatTile(ctk.CTkFrame):
    def __init__(self, parent, label: str, **kw):
        super().__init__(parent, corner_radius=10, fg_color=C.BG_CARD, width=140, height=72, **kw)
        self.pack_propagate(False)
        ctk.CTkLabel(self, text=label, font=F.TINY, text_color=C.TEXT_MUTED).pack(
            anchor="w", padx=12, pady=(10, 0))
        self._val = ctk.CTkLabel(self, text="--", font=(F.FAMILY, 20, "bold"),
                                  text_color=C.TEXT_PRIMARY)
        self._val.pack(anchor="w", padx=12, pady=(0, 10))

    def set(self, value: str, color: str = C.TEXT_PRIMARY) -> None:
        self._val.configure(text=value, text_color=color)
